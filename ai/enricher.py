"""
enricher.py
-----------
AI enrichment layer orchestrator.

TicketEnricher is the single entry-point for the AI layer.
It composes all AI sub-modules and returns a structured enrichment dict
that the routing core (FIREEngine) can consume — without containing any
NLP/AI logic itself.
"""

from typing import Any, Optional, Tuple

from ai.sentiment import SentimentEngine
from ai.nlp import TypeClassifier, LanguageDetector
from ai.summarizer import SimpleSummarizer, RecommendationEngine
from ai.geo import GeoNormalizer
from ai.llm_analyzer import analyze_with_llm


# ---------------------------------------------------------------------------
# Priority configuration
# ---------------------------------------------------------------------------

# Types that immediately push priority to a high baseline
_HIGH_PRIORITY_TYPES: frozenset[str] = frozenset({
    "Мошеннические действия",
    "Жалоба",
    "Претензия",
})

_BASE_PRIORITY: int = 5          # neutral baseline (1-10 scale)
_HIGH_TYPE_BONUS: int = 3        # added for high-priority types
_NEGATIVE_SENTIMENT_BONUS: int = 2
_VIP_BONUS: int = 2              # added when ticket["segment"] == "VIP"
_PRIORITY_MIN: int = 1
_PRIORITY_MAX: int = 10


def _clamp(value: int, lo: int, hi: int) -> int:
    """Return *value* clamped to [lo, hi]."""
    return max(lo, min(hi, value))



def _safe_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    return value if isinstance(value, int) else default


def _extract_llm_city(llm: dict[str, Any]) -> str:
    geo = llm.get("geo")
    if isinstance(geo, dict):
        return _safe_str(geo.get("city"), "")
    return ""


def analyze_ticket_with_fallback(text: str) -> Optional[dict[str, Any]]:
    """
    LLM-first ticket analysis.
    Returns dict if LLM produced a usable result, else None.
    """
    llm = analyze_with_llm(text)
    if isinstance(llm, dict) and llm:
        return llm
    return None


class TicketEnricher:
    """Enrich a raw ticket dict with AI-derived fields.

    All AI modules are initialised once at construction time and reused
    across calls, making enrichment stateless and thread-safe (assuming
    the sub-modules themselves are stateless, which they are).

    Usage::

        enricher = TicketEnricher()
        result = enricher.enrich(ticket)
    """

    def __init__(self) -> None:
        # Instantiate all AI sub-modules exactly once
        self._sentiment_engine = SentimentEngine()
        self._type_classifier = TypeClassifier()
        self._lang_detector = LanguageDetector()
        self._summarizer = SimpleSummarizer()
        self._recommender = RecommendationEngine()
        self._geo = GeoNormalizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """Return an enrichment dict for the given *ticket*.

        Expected ticket fields (all optional — missing ones degrade gracefully):
            text     (str)  : main ticket body
            city     (str)  : client city name
            segment  (str)  : client segment, e.g. "VIP", "STANDARD"

        Returns a dict with keys:
            ai_type        (str)            : classified ticket category
            ai_lang        (str)            : detected language code
            sentiment      (str)            : 'POS' | 'NEU' | 'NEG'
            priority       (int)            : 1–10
            summary        (str)            : short extractive summary
            recommendation (str)            : recommended agent action
            lat            (float | None)   : client city latitude
            lon            (float | None)   : client city longitude
        """
        text: str = _safe_str(ticket.get("text", ""), "")
        city_from_ticket: str = _safe_str(ticket.get("city", ""), "")
        segment: str = _safe_str(ticket.get("segment", ""), "")

        # --- LLM-first (optional) --------------------------------------
        llm: Optional[dict[str, Any]] = analyze_ticket_with_fallback(text)

        if llm is not None:
            # Pull fields from LLM, fallback to rule-based per-field
            ai_type: str = _safe_str(llm.get("ai_type"), "") or self._type_classifier.classify(text)
            ai_lang: str = _safe_str(llm.get("ai_lang"), "") or self._lang_detector.detect(text)
            sentiment: str = _safe_str(llm.get("sentiment"), "") or self._sentiment_engine.analyze(text)

            llm_priority: Optional[int] = _safe_int(llm.get("priority"))
            if llm_priority is not None:
                priority: int = _clamp(llm_priority, _PRIORITY_MIN, _PRIORITY_MAX)
            else:
                priority = self._calculate_priority(ai_type, sentiment, segment)

            summary: str = _safe_str(llm.get("summary"), "") or self._summarizer.summarize(text)
            recommendation: str = _safe_str(llm.get("recommendation"), "") or self._recommender.recommend(
                ai_type, priority, sentiment
            )

            # City: prefer LLM geo.city if present, else ticket city
            city_for_geo: str = _extract_llm_city(llm) or city_from_ticket
        else:
            # --- Core NLP (rule-based) -----------------------------------
            ai_type = self._type_classifier.classify(text)
            ai_lang = self._lang_detector.detect(text)
            sentiment = self._sentiment_engine.analyze(text)

            # --- Priority calculation ------------------------------------
            priority = self._calculate_priority(ai_type, sentiment, segment)

            # --- Summarisation & recommendation --------------------------
            summary = self._summarizer.summarize(text)
            recommendation = self._recommender.recommend(ai_type, priority, sentiment)

            city_for_geo = city_from_ticket

        # --- Geo ---------------------------------------------------------
        lat, lon = self._geo.geocode(city_for_geo)

        return {
            "ai_type": ai_type,
            "ai_lang": ai_lang,
            "sentiment": sentiment,
            "priority": priority,
            "summary": summary,
            "recommendation": recommendation,
            "lat": lat,
            "lon": lon,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_priority(ai_type: str, sentiment: str, segment: str) -> int:
        """Compute a 1–10 priority score from type, sentiment, and segment.

        Rules (additive):
            * Fraud / Complaint / Claim types   → +3 on top of base (5)
            * Negative sentiment                → +2
            * VIP segment                       → +2
        """
        score: int = _BASE_PRIORITY

        if ai_type in _HIGH_PRIORITY_TYPES:
            score += _HIGH_TYPE_BONUS

        if sentiment == "NEG":
            score += _NEGATIVE_SENTIMENT_BONUS

        if segment.strip().upper() == "VIP":
            score += _VIP_BONUS

        return _clamp(score, _PRIORITY_MIN, _PRIORITY_MAX)