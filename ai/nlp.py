"""
nlp.py
------
Keyword-weighted ticket type classification and language detection.
No external dependencies. Deterministic behaviour.
"""

from typing import Final


_TYPE_KEYWORDS: Final[dict[str, list[tuple[str, int]]]] = {
    "Жалоба": [
        ("жалоба", 3), ("жалуюсь", 3), ("жалобу", 3),
        ("недоволен", 2), ("недовольна", 2), ("недовольны", 2),
        ("плохой сервис", 3), ("плохое обслуживание", 3),
        ("заблокировали", 3), ("заблокирован", 3), ("заблокированы", 3),
        ("не имеете права", 3), ("без причины", 2),
        ("возмутительно", 3), ("безобразие", 3), ("возмущен", 2),
        ("нарушаете", 2), ("нарушение прав", 3),
        ("complaint", 3), ("шагым", 3),
    ],
    "Смена данных": [
        ("смена", 2), ("смену", 2), ("сменить", 2),
        ("изменить", 2), ("изменение", 2), ("изменить данные", 3),
        ("обновить", 2), ("поменять", 2),
        ("данные", 1), ("реквизиты", 2),
        ("адрес", 1), ("телефон", 1), ("номер телефона", 2),
        ("удостоверение", 2), ("уд.личности", 3), ("уд личности", 3),
        ("просрочен", 2), ("просроченный", 2),
        ("change data", 2), ("update", 1),
        ("деректерді өзгерту", 3),
    ],
    "Консультация": [
        ("вопрос", 2), ("как", 1), ("подскажите", 2),
        ("консультация", 3), ("помогите", 1), ("объясните", 2),
        ("уточните", 2), ("уточнить", 2),
        ("можно ли", 2), ("имеет ли право", 2),
        ("как можно", 2), ("каким образом", 2),
        ("question", 2), ("help", 1), ("how to", 2),
        ("кеңес", 3),
    ],
    "Претензия": [
        ("претензия", 3), ("претензию", 3),
        ("требую", 3), ("верните", 3), ("верните деньги", 3),
        ("возврат", 2), ("возвратите", 3),
        ("компенсация", 3), ("компенсацию", 3),
        ("нарушение", 2), ("нарушили", 2),
        ("в суд", 3), ("подам в суд", 3),
        ("правоохранительные органы", 3), ("полицию", 2),
        ("списали", 2), ("незаконно списали", 3),
        ("не пришло", 2), ("не зачислено", 2), ("не поступило", 2),
        ("не на моем счету", 3), ("не дошло", 2),
        ("claim", 3), ("талап", 3),
    ],
    "Неработоспособность приложения": [
        ("не работает", 3), ("не работают", 3),
        ("приложение", 2), ("не открывается", 3),
        ("ошибка", 2), ("выдает ошибку", 3),
        ("баг", 3), ("зависает", 3), ("сбой", 3),
        ("не могу войти", 3), ("не удается войти", 3),
        ("не могу зайти", 3), ("не пускает", 2),
        ("не приходит смс", 3), ("смс не приходит", 3),
        ("смс не приходят", 3), ("код не приходит", 3),
        ("пароль не принимает", 3), ("не принимает пароль", 3),
        ("не могу восстановить", 2), ("восстановление пароля", 2),
        ("не могу войти", 3), ("войти не могу", 3),
        ("app crash", 3), ("error", 2),
        ("қолданба", 2), ("жұмыс істемейді", 3),
    ],
    "Мошеннические действия": [
        ("мошенник", 3), ("мошенники", 3),
        ("мошеннич", 3), ("мошенничество", 3),
        ("мошеннической", 3), ("мошенническая", 3),
        ("обман", 3), ("обманули", 3),
        ("украли", 3), ("украли деньги", 3),
        ("несанкционированный", 2), ("без моего ведома", 3),
        ("жертвой мошенников", 3), ("жертва мошенников", 3),
        ("подозрительн", 2),
        ("fraud", 3), ("scam", 3), ("phishing", 3),
        ("алаяқтық", 3),
    ],
    "Спам": [
        ("спам", 3), ("рассылка", 2), ("нежелательный", 2),
        ("реклама", 2), ("рекламная рассылка", 3),
        ("spam", 3), ("advertisement", 2), ("unwanted", 2),
        ("спам-хабар", 3),
    ],
}

_DEFAULT_TYPE: Final[str] = "Консультация"

_KAZAKH_SPECIFIC: Final[frozenset[str]] = frozenset("әіңғүұқөһ")
_LATIN_CHARS: Final[frozenset[str]] = frozenset("abcdefghijklmnopqrstuvwxyz")
_CYRILLIC_CHARS: Final[frozenset[str]] = frozenset(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
)


class TypeClassifier:
    """Classify a support ticket into a predefined category using keyword scoring."""

    def classify(self, text: str) -> str:
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
    """

    def detect(self, text: str) -> str:
        lowered = text.lower()

        kazakh_count = sum(1 for ch in lowered if ch in _KAZAKH_SPECIFIC)
        latin_count = sum(1 for ch in lowered if ch in _LATIN_CHARS)
        cyrillic_count = sum(1 for ch in lowered if ch in _CYRILLIC_CHARS)

        if kazakh_count >= 2:
            return "KZ"

        total = latin_count + cyrillic_count
        if total == 0:
            return "RU"

        if latin_count > cyrillic_count:
            return "ENG"

        return "RU"