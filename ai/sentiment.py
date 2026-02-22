# ai/sentiment.py
"""
sentiment.py  v2
----------------
Improvements:
- Broader negative phrase list from real ticket data
- Stronger weighting for serious phrases (fraud, lawsuit, escalation threats)
- POS phrases for clearly satisfied clients
- Short text handling
"""

from __future__ import annotations
import re
from typing import Final


_POSITIVE_WORDS: Final[frozenset[str]] = frozenset({
    "хорошо", "отлично", "спасибо", "благодарю", "помогли", "решили",
    "доволен", "довольна", "рад", "рада", "быстро", "удобно",
    "успешно", "замечательно", "прекрасно", "превосходно",
    "всё работает", "все работает", "заработало",
    "thank", "thanks", "thank you", "good", "great", "excellent",
    "perfect", "awesome", "helpful", "resolved", "satisfied", "happy",
    "рахмет", "жақсы", "өте жақсы",
})

_NEGATIVE_WORDS: Final[frozenset[str]] = frozenset({
    # General negative
    "плохо", "ужасно", "отвратительно", "безобразие", "возмутительно",
    "недоволен", "недовольна", "недовольны", "возмущен", "возмущена",
    "издевательство", "кошмар",

    # Technical problems
    "проблема", "не работает", "не работают", "ошибка", "сбой", "баг",
    "зависает", "не открывается", "не пускает", "не принимает",
    "не могу войти", "не могу зайти", "не удается войти", "не удаётся войти",
    "смс не приходит", "смс не приходят", "код не приходит",
    "не приходит смс", "пароль не принимает",
    "не получается", "не удаётся", "не удается",
    "не загружается", "не грузится", "сайт не открывается",
    "выкидывает", "постоянно выкидывает",

    # Blocking
    "заблокирован", "заблокированы", "заблокировали",

    # Money / claims
    "верните", "верните деньги", "не пришло", "не поступило",
    "не зачислено", "не на моем счету", "не дошло",
    "списали", "незаконно", "незаконно списали",
    "в суд", "подам в суд", "правоохранительные органы",
    "аннулировать", "дублирующие списания",

    # Fraud
    "мошенник", "мошенники", "обман", "обманули",
    "украли", "без моего ведома", "несанкционированный",
    "жертвой мошенников", "взломали", "взлом",

    # Complaints
    "жалоба", "жалуюсь", "нарушение", "нарушили", "нарушаете",
    "не имеете права", "без причины", "требую",

    # Escalation threats
    "afsa", "аррфр", "национальный банк", "финансовый регулятор",

    # English
    "bad", "terrible", "horrible", "fraud", "scam", "stolen",
    "error", "broken", "issue", "problem", "angry", "blocked",
    "rejected", "cannot", "unable", "hacked",

    # Kazakh
    "жаман", "нашар",
})

# Multi-word phrases matched against full text (not tokens)
_NEGATIVE_PHRASES: Final[tuple[tuple[str, int], ...]] = (
    # (phrase, weight)
    ("не работает", 1),
    ("не работают", 1),
    ("не могу войти", 2),
    ("не могу зайти", 2),
    ("не удается войти", 2),
    ("не удаётся войти", 2),
    ("смс не приходит", 2),
    ("смс не приходят", 2),
    ("код не приходит", 2),
    ("не приходит смс", 2),
    ("пароль не принимает", 2),
    ("не получается", 1),
    ("верните деньги", 3),
    ("не пришло", 1),
    ("не поступило", 1),
    ("не зачислено", 1),
    ("не на моем счету", 2),
    ("не дошло", 1),
    ("незаконно списали", 3),
    ("в суд", 3),
    ("подам в суд", 3),
    ("без моего ведома", 3),
    ("не имеете права", 2),
    ("без причины", 2),
    ("жертвой мошенников", 3),
    ("правоохранительные органы", 3),
    ("заблокировали", 2),
    ("заблокированы", 2),
    ("это издевательство", 3),
    ("ваша компания ведет себя как мошенническая", 4),
    ("дублирующие списания", 2),
    ("аннулировать дублирующие", 2),
    ("инициирую заявление", 3),
    ("взломали", 3),
    ("взлом аккаунта", 3),
    ("не загружается", 1),
    ("не грузится", 1),
    ("сайт не открывается", 2),
    ("выкидывает из приложения", 2),
    ("постоянно выкидывает", 2),
)

_NEG_TOKEN_WEIGHT: Final[int] = 2


class SentimentEngine:
    """Classify text sentiment: POS, NEU, or NEG."""

    def analyze(self, text: str) -> str:
        if not text or len(text.strip()) < 3:
            return "NEU"

        lowered = text.lower()
        tokens = self._tokenize(lowered)

        pos_score: int = sum(1 for t in tokens if t in _POSITIVE_WORDS)
        neg_score: int = sum(1 for t in tokens if t in _NEGATIVE_WORDS)

        # Phrase matching with weights
        for phrase, weight in _NEGATIVE_PHRASES:
            if phrase in lowered:
                neg_score += weight

        # Multi-word positive phrases
        if any(p in lowered for p in ("всё работает", "все работает", "заработало", "спасибо большое")):
            pos_score += 2

        net = pos_score - (neg_score * _NEG_TOKEN_WEIGHT)

        if net > 0:
            return "POS"
        if net < 0:
            return "NEG"
        return "NEU"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[а-яёa-zәіңғүұқөһ]+", text, re.IGNORECASE)