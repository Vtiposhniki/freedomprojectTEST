"""
nlp.py
------
Keyword-weighted ticket type classification and language detection.
No external dependencies. Deterministic behaviour.
"""

from typing import Final


# ---------------------------------------------------------------------------
# Type classification keyword map
# Each category maps to a list of (keyword, weight) pairs.
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: Final[dict[str, list[tuple[str, int]]]] = {
    "Жалоба": [
        ("жалоба", 3), ("жалуюсь", 3), ("недоволен", 2), ("недовольна", 2),
        ("плохой сервис", 3), ("complaint", 3), ("шагым", 3),
    ],
    "Смена данных": [
        ("смена", 2), ("изменить", 2), ("обновить", 2), ("поменять", 2),
        ("данные", 1), ("реквизиты", 2), ("адрес", 1), ("телефон", 1),
        ("change data", 2), ("update", 1), ("деректерді өзгерту", 3),
    ],
    "Консультация": [
        ("вопрос", 2), ("как", 1), ("подскажите", 2), ("консультация", 3),
        ("помогите", 1), ("объясните", 2), ("question", 2), ("help", 1),
        ("how to", 2), ("кеңес", 3),
    ],
    "Претензия": [
        ("претензия", 3), ("требую", 3), ("верните", 3), ("возврат", 2),
        ("компенсация", 3), ("нарушение", 2), ("claim", 3), ("талап", 3),
    ],
    "Неработоспособность приложения": [
        ("не работает", 3), ("приложение", 2), ("не открывается", 3),
        ("ошибка", 2), ("баг", 3), ("зависает", 3), ("сбой", 3),
        ("app crash", 3), ("error", 2), ("қолданба", 2), ("жұмыс істемейді", 3),
    ],
    "Мошеннические действия": [
        ("мошенник", 3), ("мошенничество", 3), ("обман", 3), ("украли", 3),
        ("fraud", 3), ("scam", 3), ("phishing", 3), ("алаяқтық", 3),
        ("несанкционированный", 2), ("без моего ведома", 3),
    ],
    "Спам": [
        ("спам", 3), ("реклама", 2), ("рассылка", 2), ("нежелательный", 2),
        ("spam", 3), ("advertisement", 2), ("unwanted", 2), ("спам-хабар", 3),
    ],
}

_DEFAULT_TYPE: Final[str] = "Консультация"

# ---------------------------------------------------------------------------
# Language detection character sets
# ---------------------------------------------------------------------------

_KAZAKH_SPECIFIC: Final[frozenset[str]] = frozenset("әіңғүұқөһ")
_LATIN_CHARS: Final[frozenset[str]] = frozenset("abcdefghijklmnopqrstuvwxyz")
_CYRILLIC_CHARS: Final[frozenset[str]] = frozenset(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
)


class TypeClassifier:
    """Classify a support ticket into a predefined category using keyword scoring.

    Categories (Казахский / Russian):
        Жалоба, Смена данных, Консультация, Претензия,
        Неработоспособность приложения, Мошеннические действия, Спам
    """

    def classify(self, text: str) -> str:
        """Return the best-matching category name for *text*.

        Args:
            text: Raw ticket body.

        Returns:
            Category string. Falls back to 'Консультация' when no keywords match.
        """
        lowered = text.lower()
        scores: dict[str, int] = {cat: 0 for cat in _TYPE_KEYWORDS}

        for category, pairs in _TYPE_KEYWORDS.items():
            for keyword, weight in pairs:
                if keyword in lowered:
                    scores[category] += weight

        best_cat = max(scores, key=lambda c: scores[c])
        return best_cat if scores[best_cat] > 0 else _DEFAULT_TYPE


class LanguageDetector:
    """Detect the primary language of a text string.

    Supported outputs: 'KZ' (Kazakh), 'ENG' (English), 'RU' (Russian, default).
    Detection is heuristic: character frequency rather than statistical models.
    """

    def detect(self, text: str) -> str:
        """Return 'KZ', 'ENG', or 'RU' for the detected language.

        Args:
            text: Input string of any length.

        Returns:
            Language code string.
        """
        lowered = text.lower()

        # Count characters belonging to each set
        kazakh_count = sum(1 for ch in lowered if ch in _KAZAKH_SPECIFIC)
        latin_count = sum(1 for ch in lowered if ch in _LATIN_CHARS)
        cyrillic_count = sum(1 for ch in lowered if ch in _CYRILLIC_CHARS)

        # Kazakh uses Cyrillic + specific extra letters
        if kazakh_count >= 2:
            return "KZ"

        total = latin_count + cyrillic_count
        if total == 0:
            return "RU"  # default

        if latin_count > cyrillic_count:
            return "ENG"

        return "RU"
