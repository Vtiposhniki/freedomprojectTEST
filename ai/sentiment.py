"""
sentiment.py
------------
Score-based sentiment analysis engine.
No external dependencies. Deterministic behaviour.
"""

from typing import Final


_POSITIVE_WORDS: Final[frozenset[str]] = frozenset({
    "хорошо", "отлично", "спасибо", "благодарю", "помогли", "решили",
    "доволен", "довольна", "рад", "рада", "быстро", "удобно", "работает",
    "успешно", "замечательно", "прекрасно", "thank", "thanks", "good",
    "great", "excellent", "perfect", "awesome", "helpful", "resolved",
    "satisfied", "happy", "рахмет", "жақсы", "өте жақсы",
})

_NEGATIVE_WORDS: Final[frozenset[str]] = frozenset({
    # Общие негативные
    "плохо", "ужасно", "отвратительно", "безобразие", "возмутительно",
    "недоволен", "недовольна", "недовольны", "злой", "злая", "возмущен",

    # Технические проблемы
    "проблема", "проблемы",
    "не работает", "не работают", "ошибка", "сбой", "баг", "зависает",
    "не открывается", "не пускает", "не принимает",
    "не могу войти", "не могу зайти", "не удается войти",
    "смс не приходит", "смс не приходят", "код не приходит",
    "не приходит смс", "пароль не принимает",
    "не получается", "не удаётся", "не удается",

    # Блокировки
    "заблокирован", "заблокированы", "заблокировали", "заблокирован",

    # Деньги / претензии
    "верните", "верните деньги", "не пришло", "не поступило",
    "не зачислено", "не на моем счету", "не дошло",
    "списали", "незаконно", "незаконно списали",
    "в суд", "подам в суд", "правоохранительные органы",

    # Мошенничество
    "мошенник", "мошенники", "мошеннич", "обман", "обманули",
    "украли", "без моего ведома", "несанкционированный",
    "жертвой мошенников",

    # Жалобы
    "жалоба", "жалуюсь", "нарушение", "нарушили", "нарушаете",
    "не имеете права", "без причины", "требую",

    # Английские
    "bad", "terrible", "horrible", "fraud", "scam", "stolen",
    "error", "broken", "issue", "problem", "angry", "blocked",
    "rejected", "cannot", "unable",

    # Казахские
    "жаман", "нашар",
})

# Отдельный список многословных фраз (не токенизируются)
_NEGATIVE_PHRASES: Final[tuple[str, ...]] = (
    "не работает", "не работают",
    "не могу войти", "не могу зайти",
    "не удается войти", "не удаётся войти",
    "смс не приходит", "смс не приходят",
    "код не приходит", "не приходит смс",
    "пароль не принимает",
    "не получается", "не удаётся", "не удается",
    "верните деньги",
    "не пришло", "не поступило", "не зачислено",
    "не на моем счету", "не дошло",
    "незаконно списали",
    "в суд", "подам в суд",
    "без моего ведома",
    "не имеете права",
    "без причины",
    "жертвой мошенников",
    "правоохранительные органы",
    "заблокировали", "заблокированы",
)

_NEG_WEIGHT: Final[int] = 2


class SentimentEngine:
    """Classify text sentiment using weighted keyword scoring."""

    def analyze(self, text: str) -> str:
        """Return 'POS', 'NEU', or 'NEG' for the given text."""
        lowered = text.lower()
        tokens = self._tokenize(lowered)

        pos_score: int = sum(1 for t in tokens if t in _POSITIVE_WORDS)
        neg_score: int = sum(1 for t in tokens if t in _NEGATIVE_WORDS)

        # Фразовый матч — ловит многословные выражения
        for phrase in _NEGATIVE_PHRASES:
            if phrase in lowered:
                neg_score += 1

        # Фразовый матч по _NEGATIVE_WORDS (те что содержат пробел)
        for phrase in _NEGATIVE_WORDS:
            if " " in phrase and phrase in lowered:
                neg_score += 1

        net = pos_score - (neg_score * _NEG_WEIGHT)

        if net > 0:
            return "POS"
        if net < 0:
            return "NEG"
        return "NEU"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into lowercase word tokens."""
        import re
        return re.findall(r"[а-яёa-zәіңғүұқөһ]+", text, re.IGNORECASE)