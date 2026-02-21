"""
enricher.py
-----------
AI enrichment layer orchestrator.

Стратегия:
  - ai_type, ai_lang, sentiment, priority, lat/lon → rule-based (мгновенно)
  - summary + recommendation                       → LLM (если доступен)
  - Если LLM недоступен → summary и recommendation тоже rule-based
"""

from typing import Any, Optional, Tuple

from ai.sentiment import SentimentEngine
from ai.nlp import TypeClassifier, LanguageDetector
from ai.summarizer import SimpleSummarizer, RecommendationEngine
from ai.geo import GeoNormalizer
from ai.llm_client import get_client


# ---------------------------------------------------------------------------
# Priority configuration
# ---------------------------------------------------------------------------

_HIGH_PRIORITY_TYPES: frozenset[str] = frozenset({
    "Мошеннические действия",
    "Жалоба",
    "Претензия",
})

_BASE_PRIORITY: int = 5
_HIGH_TYPE_BONUS: int = 3
_NEGATIVE_SENTIMENT_BONUS: int = 2
_VIP_BONUS: int = 2
_PRIORITY_MIN: int = 1
_PRIORITY_MAX: int = 10

LLM_MODEL = "qwen/qwen3-next-80b-a3b-instruct"

SUMMARY_SYSTEM_PROMPT = """
Ты — помощник оператора колл-центра.

По тексту обращения клиента напиши СТРОГО JSON:

{
  "summary": "краткая суть обращения в 1-2 предложения",
  "recommendation": "конкретная рекомендация менеджеру что делать"
}

Никакого текста вне JSON. Язык ответа — русский.
"""


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _safe_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _get_llm_summary(text: str) -> Optional[dict]:
    """
    Запросить у LLM только summary и recommendation.
    Возвращает dict с ключами summary/recommendation или None при ошибке.
    """
    import json
    import re

    client = get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": text[:3000]},
            ],
            temperature=0.3,
            max_tokens=300,
            timeout=15,
        )

        raw = response.choices[0].message.content or ""
        print(f"[LLM] summary | chars: {len(raw)}")

        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        json_str = match.group(1).strip() if match else raw.strip()
        match2 = re.search(r"\{[\s\S]+\}", json_str)
        if match2:
            json_str = match2.group(0)

        data = json.loads(json_str)
        summary = _safe_str(data.get("summary"))
        recommendation = _safe_str(data.get("recommendation"))

        if summary and recommendation:
            return {"summary": summary, "recommendation": recommendation}
        return None

    except Exception as e:
        print(f"[LLM] summary error: {type(e).__name__}: {e}")
        return None


class TicketEnricher:
    """
    Обогащает тикет AI-полями.

    Rule-based (мгновенно):
        ai_type, ai_lang, sentiment, priority, lat, lon

    LLM (только если доступен):
        summary, recommendation
    """

    def __init__(self) -> None:
        self._sentiment_engine = SentimentEngine()
        self._type_classifier = TypeClassifier()
        self._lang_detector = LanguageDetector()
        self._summarizer = SimpleSummarizer()
        self._recommender = RecommendationEngine()
        self._geo = GeoNormalizer()

    def enrich(self, ticket: dict[str, Any]) -> dict[str, Any]:
        text: str = _safe_str(ticket.get("text", ""))
        city: str = _safe_str(ticket.get("city", ""))
        segment: str = _safe_str(ticket.get("segment", ""))

        # ── Rule-based: классификация ────────────────────────────────────
        ai_type: str = self._type_classifier.classify(text)
        ai_lang: str = self._lang_detector.detect(text)
        sentiment: str = self._sentiment_engine.analyze(text)
        priority: int = self._calculate_priority(ai_type, sentiment, segment)

        # ── Rule-based: гео ──────────────────────────────────────────────
        lat, lon = self._geo.geocode(city)

        # ── LLM: только summary + recommendation ─────────────────────────
        llm = _get_llm_summary(text)

        if llm:
            summary = llm["summary"]
            recommendation = llm["recommendation"]
        else:
            # Fallback если LLM недоступен
            summary = self._summarizer.summarize(text)
            recommendation = self._recommender.recommend(ai_type, priority, sentiment)

        return {
            "ai_type":        ai_type,
            "ai_lang":        ai_lang,
            "sentiment":      sentiment,
            "priority":       priority,
            "summary":        summary,
            "recommendation": recommendation,
            "lat":            lat,
            "lon":            lon,
        }

    @staticmethod
    def _calculate_priority(ai_type: str, sentiment: str, segment: str) -> int:
        """
        Правила (аддитивные):
            base                                → 5
            Мошенничество / Жалоба / Претензия  → +3
            Негативная тональность              → +2
            VIP или Priority сегмент            → +2
        """
        score: int = _BASE_PRIORITY

        if ai_type in _HIGH_PRIORITY_TYPES:
            score += _HIGH_TYPE_BONUS

        if sentiment == "NEG":
            score += _NEGATIVE_SENTIMENT_BONUS

        if segment.strip().upper() in ("VIP", "PRIORITY"):
            score += _VIP_BONUS

        return _clamp(score, _PRIORITY_MIN, _PRIORITY_MAX)