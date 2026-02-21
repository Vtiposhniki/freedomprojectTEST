"""
summarizer.py
-------------
Extractive text summarisation and rule-based recommendation generation.
No external dependencies. Deterministic behaviour.
"""

import re
from typing import Final

_MAX_SUMMARY_LEN: Final[int] = 300
_MIN_SENTENCE_LEN: Final[int] = 10  # ignore very short fragments


class SimpleSummarizer:
    """Extract a concise summary from raw ticket text.

    Strategy:
        1. Normalise whitespace.
        2. Split into sentences on common terminators (. ! ?).
        3. Pick the first 1-2 meaningful sentences (>= 10 chars each).
        4. Truncate to 300 characters.
    """

    def summarize(self, text: str) -> str:
        """Return a short summary of *text* (max 300 chars).

        Args:
            text: Raw input string.

        Returns:
            Cleaned, truncated summary string.
        """
        # Normalise whitespace
        cleaned = re.sub(r"\s+", " ", text).strip()

        # Split on sentence-ending punctuation, keeping the delimiter
        parts = re.split(r"(?<=[.!?])\s+", cleaned)

        meaningful: list[str] = [
            s.strip() for s in parts if len(s.strip()) >= _MIN_SENTENCE_LEN
        ]

        if not meaningful:
            # Fallback: just truncate the cleaned text
            return cleaned[:_MAX_SUMMARY_LEN]

        # Take up to 2 sentences, join, then truncate
        summary = " ".join(meaningful[:2])
        return summary[:_MAX_SUMMARY_LEN]


# ---------------------------------------------------------------------------
# Recommendation rules
# ---------------------------------------------------------------------------

# (ticket_type_fragment, priority_min, sentiment) -> recommendation text
# Rules are evaluated top-to-bottom; first match wins.
_RECOMMENDATION_RULES: Final[list[tuple[str, int, str, str]]] = [
    # (type_contains, min_priority, sentiment_or_ANY, recommendation)
    ("Мошеннические", 1, "ANY",
     "Немедленно заблокируйте счёт клиента и передайте заявку в службу безопасности."),
    ("Претензия", 7, "NEG",
     "Приоритетная претензия: свяжитесь с клиентом в течение 1 часа, предложите компенсацию."),
    ("Претензия", 1, "ANY",
     "Рассмотрите претензию в течение 24 часов и предоставьте письменный ответ."),
    ("Жалоба", 7, "NEG",
     "Высокоприоритетная жалоба: эскалируйте руководителю и свяжитесь с клиентом сегодня."),
    ("Жалоба", 1, "ANY",
     "Обработайте жалобу в течение рабочего дня, предложите решение проблемы."),
    ("Неработоспособность", 7, "ANY",
     "Критический сбой приложения: передайте в L2-поддержку немедленно."),
    ("Неработоспособность", 1, "ANY",
     "Проверьте техническую проблему и при необходимости передайте в L2-поддержку."),
    ("Смена данных", 1, "ANY",
     "Верифицируйте личность клиента перед внесением изменений."),
    ("Спам", 1, "ANY",
     "Отметьте контакт как спам и при необходимости заблокируйте отправителя."),
    ("Консультация", 1, "POS",
     "Предоставьте консультацию и предложите дополнительные продукты."),
    ("Консультация", 1, "ANY",
     "Предоставьте полную консультацию и зафиксируйте результат."),
]

_DEFAULT_RECOMMENDATION: Final[str] = (
    "Обработайте обращение в стандартные сроки согласно регламенту."
)


class RecommendationEngine:
    """Generate a human-readable action recommendation for a ticket.

    The recommendation is derived deterministically from ticket type,
    calculated priority, and sentiment — no ML involved.
    """

    def recommend(self, ticket_type: str, priority: int, sentiment: str) -> str:
        """Return a recommended action string.

        Args:
            ticket_type: Category label from TypeClassifier.
            priority:    Integer priority 1-10 (higher = more urgent).
            sentiment:   'POS', 'NEU', or 'NEG' from SentimentEngine.

        Returns:
            Recommendation string in Russian.
        """
        for type_fragment, min_prio, req_sentiment, recommendation in _RECOMMENDATION_RULES:
            type_match = type_fragment in ticket_type
            prio_match = priority >= min_prio
            sentiment_match = req_sentiment == "ANY" or req_sentiment == sentiment

            if type_match and prio_match and sentiment_match:
                return recommendation

        return _DEFAULT_RECOMMENDATION
