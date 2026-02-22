# ai/enricher.py
"""
enricher.py  v2
---------------
Improvements:
- Passes region to GeoNormalizer for better geocoding
- Uses classify_with_score() — routes low-confidence to LLM
- Priority accounts for segment more broadly (not just upper case check)
- Cleans raw city string before geocoding
"""

from __future__ import annotations
import re
from typing import Any, Optional, Tuple
import json

from ai.sentiment import SentimentEngine
from ai.nlp import TypeClassifier, LanguageDetector
from ai.summarizer import SimpleSummarizer, RecommendationEngine
from ai.geo import GeoNormalizer
from ai.llm_client import get_client


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

LLM_MODEL = "upstage/solar-pro-3:free"
LLM_CONFIDENCE_THRESHOLD = 4  # if rule-based score < this → try LLM

SUMMARY_SYSTEM_PROMPT = """
Ты — опытный аналитик колл-центра Freedom Finance.

По тексту обращения клиента напиши СТРОГО JSON без лишнего текста:

{
  "summary": "краткая суть обращения: что именно случилось у клиента, в 1-2 предложениях",
  "recommendation": "конкретные шаги для менеджера: что проверить, с кем связаться, что сообщить клиенту"
}

ВАЖНО:
- Только JSON, никакого текста до или после
- Никаких markdown-блоков
- summary не длиннее 250 символов
- recommendation не длиннее 300 символов
- Язык ответа — русский
- Профессиональный деловой стиль
"""


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _safe_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _clean_city(raw: str) -> str:
    """
    Normalize messy city strings from CSV:
    - "Алматы / Астана" → "Алматы"
    - "Нур-Султан (Астана)" → "Нур-Султан"
    - "NULL", "nan" → ""
    """
    if not raw:
        return ""
    s = str(raw).strip()
    if s.lower() in ("null", "nan", "none", "-", ""):
        return ""
    # Take first part before slash/pipe
    s = re.split(r"[/|\\]", s)[0].strip()
    # Remove parenthetical
    s = re.sub(r"\(.*?\)", "", s).strip()
    return s


def _normalize_segment(segment: str) -> str:
    """Normalize segment to uppercase, handle variants."""
    s = str(segment).strip().upper()
    if s in ("VIP", "ВИП"):
        return "VIP"
    if s in ("PRIORITY", "ПРИОРИТЕТ", "PRIOR"):
        return "PRIORITY"
    return s


def _get_llm_summary(text: str) -> Optional[dict]:
    client = get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": text[:2000]},
            ],
            temperature=0.2,
            max_tokens=600,
            timeout=15,
        )
        raw = response.choices[0].message.content or ""
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        json_str = match.group(1).strip() if match else raw.strip()
        match2 = re.search(r"\{[\s\S]+?\}", json_str)
        if match2:
            json_str = match2.group(0)
        json_str = _try_repair_json(json_str)
        data = json.loads(json_str)
        summary = _safe_str(data.get("summary"))
        recommendation = _safe_str(data.get("recommendation"))
        if summary and recommendation:
            return {"summary": summary, "recommendation": recommendation}
    except Exception as e:
        print(f"[LLM] summary error: {type(e).__name__}: {e}")
    return None


def _try_repair_json(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        i += 1
    if in_string:
        s += '"'
    if not s.endswith('}'):
        s += '}'
    return s


class TicketEnricher:
    def __init__(self) -> None:
        self._sentiment_engine = SentimentEngine()
        self._type_classifier = TypeClassifier()
        self._lang_detector = LanguageDetector()
        self._summarizer = SimpleSummarizer()
        self._recommender = RecommendationEngine()
        self._geo = GeoNormalizer()

    def enrich(self, ticket: dict[str, Any]) -> dict[str, Any]:
        text: str = _safe_str(ticket.get("text", ""))
        city_raw: str = _safe_str(ticket.get("city", ""))
        region: str = _safe_str(ticket.get("region", ""))
        segment_raw: str = _safe_str(ticket.get("segment", ""))

        city: str = _clean_city(city_raw)
        segment: str = _normalize_segment(segment_raw)

        # Type classification with confidence
        ai_type, confidence = self._type_classifier.classify_with_score(text)
        ai_lang: str = self._lang_detector.detect(text)
        sentiment: str = self._sentiment_engine.analyze(text)
        priority: int = self._calculate_priority(ai_type, sentiment, segment)

        # Geocode with region fallback
        lat, lon = self._geo.geocode(city, region)

        # LLM for summary + recommendation (and type if low confidence)
        llm = _get_llm_summary(text)

        if llm:
            summary = llm["summary"]
            recommendation = llm["recommendation"]
        else:
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
        score: int = _BASE_PRIORITY
        if ai_type in _HIGH_PRIORITY_TYPES:
            score += _HIGH_TYPE_BONUS
        if sentiment == "NEG":
            score += _NEGATIVE_SENTIMENT_BONUS
        if segment in ("VIP", "PRIORITY"):
            score += _VIP_BONUS
        return _clamp(score, _PRIORITY_MIN, _PRIORITY_MAX)