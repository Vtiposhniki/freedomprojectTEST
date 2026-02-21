"""
sentiment.py
------------
Score-based sentiment analysis engine.
No external dependencies. Deterministic behaviour.
"""

from typing import Final


# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: Final[frozenset[str]] = frozenset({
    "хорошо", "отлично", "спасибо", "благодарю", "помогли", "решили",
    "доволен", "довольна", "рад", "рада", "быстро", "удобно", "работает",
    "успешно", "замечательно", "прекрасно", "thank", "thanks", "good",
    "great", "excellent", "perfect", "awesome", "helpful", "resolved",
    "satisfied", "happy", "рахмет", "жақсы", "өте жақсы",
})

_NEGATIVE_WORDS: Final[frozenset[str]] = frozenset({
    "плохо", "ужасно", "не работает", "ошибка", "проблема", "жалоба",
    "мошенник", "обман", "украли", "недоволен", "недовольна", "злой",
    "злая", "отвратительно", "безобразие", "верните", "требую",
    "претензия", "сбой", "баг", "зависает", "не могу", "невозможно",
    "задержка", "долго", "bad", "terrible", "horrible", "fraud",
    "scam", "stolen", "error", "broken", "issue", "problem", "angry",
    "жаман", "нашар",
})

# How many negative hits cancel one positive hit.
_NEG_WEIGHT: Final[int] = 2


class SentimentEngine:
    """Classify text sentiment using weighted keyword scoring.

    Negative words carry double the weight of positive words, so a single
    negative hit can override two positive hits.
    """

    def analyze(self, text: str) -> str:
        """Return 'POS', 'NEU', or 'NEG' for the given *text*.

        Args:
            text: Raw input string (any language).

        Returns:
            'POS' if net score > 0, 'NEG' if net score < 0, else 'NEU'.
        """
        lowered = text.lower()
        tokens = self._tokenize(lowered)

        pos_score: int = sum(1 for t in tokens if t in _POSITIVE_WORDS)
        neg_score: int = sum(1 for t in tokens if t in _NEGATIVE_WORDS)

        # Check multi-word negative phrases in raw lowered text
        for phrase in _NEGATIVE_WORDS:
            if " " in phrase and phrase in lowered:
                neg_score += 1

        net = pos_score - (neg_score * _NEG_WEIGHT)

        if net > 0:
            return "POS"
        if net < 0:
            return "NEG"
        return "NEU"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into lowercase word tokens, stripping punctuation."""
        import re
        return re.findall(r"[а-яёa-zәіңғүұқөһ]+", text, re.IGNORECASE)
