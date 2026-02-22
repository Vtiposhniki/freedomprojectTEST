# ai/nlp.py
"""
nlp.py  v2
----------
Improvements:
- Spam detection via URL/marketing patterns BEFORE keyword scoring
- Wider "Смена данных" keywords (KZ phrases, новый номер, верификация)
- Confidence threshold: low-score → "Консультация" with warning flag
- Improved KZ detection using word dictionary
- Short-text handling
"""

from __future__ import annotations
import re
from typing import Final


# ─────────────────────────────────────────────────────────────────────────────
# SPAM PATTERNS — checked first, before keyword scoring
# ─────────────────────────────────────────────────────────────────────────────

_SPAM_URL_RE = re.compile(r"https?://\S{25,}", re.IGNORECASE)
_SPAM_PATTERNS: Final[list[re.Pattern]] = [
    re.compile(r"(тюльпан|срезка|питомник|вашутино)", re.I),
    re.compile(r"(скидк|акци|распродаж).{0,30}(склад|цен|заказ|прайс)", re.I),
    re.compile(r"(предлагаем|предлагает).{0,40}(оборудован|товар|продукц|услуг)", re.I),
    re.compile(r"(дайджест|newsletter|digest|рассылк).{0,20}(digital|маркет)", re.I),
    re.compile(r"поздравляем.{0,40}(день рождения|юбиле)", re.I),
    re.compile(r"(приглашаем|приглашает).{0,40}(мероприяти|вебинар|конференц|день инвестора)", re.I),
    re.compile(r"(минимальный заказ|упаковка|транспортировка|отгрузка).{0,60}(шт|руб|кг)", re.I),
    re.compile(r"unsubscribe|отписаться от рассылки", re.I),
    re.compile(r"(2gis|2гис).{0,30}(система|карт|появ)", re.I),
    re.compile(r"(iqas|интеллектуальн).{0,20}(лига|quiz|квиз)", re.I),
    re.compile(r"wunder\s*digital", re.I),
]

_MIN_SPAM_TEXT_LEN = 200  # short texts can't be spam by pattern


def _is_spam(text: str) -> bool:
    """True if text matches known spam patterns."""
    if len(text) < _MIN_SPAM_TEXT_LEN and not _SPAM_URL_RE.search(text):
        return False
    url_count = len(_SPAM_URL_RE.findall(text))
    if url_count >= 3:
        return True
    for pat in _SPAM_PATTERNS:
        if pat.search(text):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# TYPE KEYWORDS
# ─────────────────────────────────────────────────────────────────────────────

_TYPE_KEYWORDS: Final[dict[str, list[tuple[str, int]]]] = {
    "Жалоба": [
        ("жалоба", 3), ("жалуюсь", 3), ("жалобу", 3),
        ("недоволен", 2), ("недовольна", 2), ("недовольны", 2),
        ("плохой сервис", 3), ("плохое обслуживание", 3),
        ("заблокировали", 3), ("заблокирован", 3), ("заблокированы", 3),
        ("не имеете права", 3), ("без причины", 2),
        ("возмутительно", 3), ("безобразие", 3), ("возмущен", 2),
        ("нарушаете", 2), ("нарушение прав", 3),
        ("это издевательство", 3), ("издевательство", 2),
        ("complaint", 3), ("шагым", 3),
    ],
    "Смена данных": [
        ("смена", 2), ("смену", 2), ("сменить", 2),
        ("изменить", 2), ("изменение", 2), ("изменить данные", 3),
        ("обновить", 2), ("поменять", 2),
        ("данные", 1), ("реквизиты", 2),
        ("адрес", 1), ("телефон", 1), ("номер телефона", 2),
        ("новый номер", 3), ("сменила номер", 3), ("сменил номер", 3),
        ("ауыстырып", 3),           # каз. "поменять"
        ("жаңа нөмір", 3),          # каз. "новый номер"
        ("нөмірімді", 3),           # каз. "мой номер"
        ("нөміріне ауыстыр", 3),    # каз. "замените на номер"
        ("удостоверение", 2), ("уд.личности", 3), ("уд личности", 3),
        ("просрочен", 2), ("просроченный", 2), ("просрочено", 2),
        ("верификаци", 1),          # часто связана со сменой данных
        ("восстановить доступ", 2),
        ("изменились данные", 3), ("изменились мои данные", 3),
        ("обновить данные", 3),
        ("change data", 2), ("update", 1),
        ("деректерді өзгерту", 3),
        ("менің деректер", 2),
    ],
    "Консультация": [
        ("вопрос", 2), ("как", 1), ("подскажите", 2),
        ("консультация", 3), ("помогите", 1), ("объясните", 2),
        ("уточните", 2), ("уточнить", 2),
        ("можно ли", 2), ("каким образом", 2),
        ("имеет ли право", 4),
        ("как можно", 2), ("как мне", 2),
        ("подскажи", 2), ("объясни", 2),
        ("помогите пожалуйста", 3),
        ("question", 2), ("help", 1), ("how to", 2), ("could you", 2),
        ("please tell", 2), ("please advise", 2),
        ("кеңес", 3), ("түсіндіріп", 3), ("көмектесіп", 3),
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
        ("аннулировать", 3), ("дублирующие списания", 3),
        ("официально заявляю", 3), ("официальный ответ", 2),
        ("afsa", 3), ("аррфр", 3), ("национальный банк", 2),
        ("claim", 3), ("талап", 3),
    ],
    "Неработоспособность приложения": [
        ("не работает", 3), ("не работают", 3),
        ("приложение", 2), ("не открывается", 3),
        ("ошибка", 2), ("выдает ошибку", 3), ("выдаёт ошибку", 3),
        ("баг", 3), ("зависает", 3), ("сбой", 3),
        ("не могу войти", 3), ("не удается войти", 3), ("не удаётся войти", 3),
        ("не могу зайти", 3), ("не пускает", 2),
        ("не приходит смс", 3), ("смс не приходит", 3),
        ("смс не приходят", 3), ("код не приходит", 3),
        ("пароль не принимает", 3), ("не принимает пароль", 3),
        ("не могу восстановить", 2), ("восстановление пароля", 2),
        ("войти не могу", 3), ("выкидывает", 3),
        ("не загружает", 3), ("не грузится", 3), ("сайт не открывается", 3),
        ("постоянно выкидывает", 3),
        ("app crash", 3), ("error", 2), ("something went wrong", 3),
        ("қолданба", 2), ("жұмыс істемейді", 3), ("ашылмай", 3),
        ("кірмеймін", 3),
    ],
    "Мошеннические действия": [
        ("мошенник", 3), ("мошенники", 3),
        ("мошеннич", 3), ("мошенничество", 3),
        ("мошеннической", 3), ("мошенническая", 3),
        ("обман", 3), ("обманули", 3),
        ("украли", 3), ("украли деньги", 3),
        ("несанкционированный", 2), ("без моего ведома", 3),
        ("жертвой мошенников", 3), ("жертва мошенников", 3),
        ("подозрительн", 2), ("взлом", 3), ("взломали", 3),
        ("таргетированной рекламы", 2), ("от лица фридом", 3),
        ("представляются сотрудниками", 3),
        ("поддельный сертификат", 3), ("действительный сертификат", 2),
        ("fraud", 3), ("scam", 3), ("phishing", 3),
        ("hacked", 3), ("unauthorized", 3),
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
_LOW_CONFIDENCE_THRESHOLD: Final[int] = 2


class TypeClassifier:
    """Classify a support ticket into a predefined category."""

    def classify(self, text: str) -> str:
        # Fast path: spam detection
        if _is_spam(text):
            return "Спам"

        # Very short / empty
        stripped = text.strip()
        if len(stripped) < 5:
            return _DEFAULT_TYPE

        lowered = stripped.lower()
        scores: dict[str, int] = {cat: 0 for cat in _TYPE_KEYWORDS}

        for category, pairs in _TYPE_KEYWORDS.items():
            for keyword, weight in pairs:
                if keyword in lowered:
                    scores[category] += weight

        best_cat = max(scores, key=lambda c: scores[c])
        best_score = scores[best_cat]

        # Low confidence → default
        if best_score < _LOW_CONFIDENCE_THRESHOLD:
            return _DEFAULT_TYPE

        return best_cat

    def classify_with_score(self, text: str) -> tuple[str, int]:
        """Return (category, score) — useful for LLM fallback decision."""
        if _is_spam(text):
            return "Спам", 99
        lowered = text.lower()
        scores: dict[str, int] = {cat: 0 for cat in _TYPE_KEYWORDS}
        for category, pairs in _TYPE_KEYWORDS.items():
            for keyword, weight in pairs:
                if keyword in lowered:
                    scores[category] += weight
        best = max(scores, key=lambda c: scores[c])
        return (best if scores[best] >= _LOW_CONFIDENCE_THRESHOLD else _DEFAULT_TYPE), scores[best]


# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_KAZAKH_SPECIFIC_CHARS: Final[frozenset[str]] = frozenset("әіңғүұқөһ")
_LATIN_CHARS: Final[frozenset[str]] = frozenset("abcdefghijklmnopqrstuvwxyz")
_CYRILLIC_CHARS: Final[frozenset[str]] = frozenset("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")

# Common Kazakh words that don't use special chars but are clearly Kazakh
_KAZAKH_WORDS: Final[frozenset[str]] = frozenset({
    "сәлеметсіз", "сәлем", "рахмет", "өтінем", "беруңіз", "сұраймын",
    "жүйесінде", "болды", "жатыр", "керек", "мүмкін", "ашылмай",
    "ауыстырып", "нөмір", "жаңа", "алмадым", "бар", "ашуға",
    "нөмірімді", "деректерді", "жібересіздер", "ма", "бе",
    "сізге", "маған", "бізге", "оларға", "сіздің", "менің",
    "ашылмай", "тіркелу", "верификациядан", "өткен", "өтем",
    "оттим", "жатырмын", "жатырмыз",
    "куалигим", "жеке", "куаліг", "мекенжай",
})


class LanguageDetector:
    """Detect primary language: KZ, ENG, or RU (default)."""

    def detect(self, text: str) -> str:
        lowered = text.lower()
        tokens = set(re.findall(r"[а-яёa-zәіңғүұқөһ]+", lowered, re.IGNORECASE))

        # Kazakh special chars
        kz_char_count = sum(1 for ch in lowered if ch in _KAZAKH_SPECIFIC_CHARS)
        if kz_char_count >= 1:
            return "KZ"

        # Kazakh word match
        kz_word_count = sum(1 for w in tokens if w in _KAZAKH_WORDS)
        if kz_word_count >= 1:
            return "KZ"

        # Latin vs Cyrillic ratio
        latin_count = sum(1 for ch in lowered if ch in _LATIN_CHARS)
        cyrillic_count = sum(1 for ch in lowered if ch in _CYRILLIC_CHARS)

        total = latin_count + cyrillic_count
        if total == 0:
            return "RU"

        if latin_count > cyrillic_count:
            return "ENG"

        return "RU"