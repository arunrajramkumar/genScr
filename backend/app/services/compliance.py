"""Guardrails against advice-like or promotional language (SEBI RA / finfluencer rules).

genScr shows data and education only. Any text we generate or display must not recommend
buying/selling/holding a security, set price targets, or promise/assure returns.
A phrase is allowed when it is clearly negated nearby, e.g. "not a recommendation to buy".
"""

import re

# (pattern, reason). Patterns are phrase-level so they don't trip on ordinary code/words.
BANNED: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.IGNORECASE), reason)
    for p, reason in [
        (r"\b(strong|must|should|good to)\s+(buy|sell|accumulate)\b", "buy/sell recommendation"),
        (r"\b(buy|sell|hold|accumulate|exit)\s+(now|call|rating|signal|recommendation|today)\b", "buy/sell recommendation"),
        (r"\b(we|i)\s+recommend(s|ed)?\b", "recommendation"),
        (r"\byou\s+should\s+(buy|sell|invest|hold|exit)\b", "personal advice"),
        (r"\b(price\s+target|target\s+price|target\s+of\s+(rs\.?|₹|inr))", "price target"),
        (r"\bmulti[\s-]?baggers?\b", "promotional claim"),
        (r"\b(guaranteed|assured|fixed|sure[\s-]?shot)\s+(returns?|profits?|gains?|income)\b", "assured returns"),
        (r"\bsure[\s-]?shot\b", "promotional claim"),
        (r"\brisk[\s-]?free\s+(returns?|profits?|investment|trade)\b", "risk-free claim"),
        (r"\b(jackpot|can'?t\s+lose|no[\s-]?loss)\b", "promotional claim"),
        (r"\b(stock|intraday|trading)\s+tips?\b|\btips?\s+of\s+the\s+day\b", "stock tips"),
        (r"\bwill\s+(double|triple|10x|surge|skyrocket|rally|hit|reach)\b", "price prediction"),
        (r"\bexpected\s+returns?\b", "return projection"),
        (r"\b(upside|downside)\s+(target|potential)\s+of\b", "price target"),
    ]
]

_NEGATION = re.compile(r"\b(not|no|never|nor|without|isn'?t|aren'?t|don'?t|doesn'?t|cannot|can'?t)\b", re.IGNORECASE)
_NEGATION_WINDOW = 80  # characters before the match


def violations(text: str) -> list[str]:
    """Advice-like phrases found in `text` (empty list when compliant)."""
    found = []
    for pattern, reason in BANNED:
        for m in pattern.finditer(text or ""):
            window = text[max(0, m.start() - _NEGATION_WINDOW): m.start()]
            # A negation in the same sentence makes it a disclaimer, not advice.
            # Sentences end at . ! ? or a blank line (source text often wraps mid-sentence).
            sentence = re.split(r"[.!?]|\n\s*\n", window)[-1]
            if _NEGATION.search(sentence):
                continue
            found.append(f"{reason}: '{m.group(0)}'")
    return found


def is_compliant(text: str) -> bool:
    return not violations(text)


def filter_compliant(items: list[dict], fields: tuple[str, ...] = ("title", "text")) -> list[dict]:
    """Drop any generated item whose user-facing text contains advice-like language."""
    return [it for it in items if all(is_compliant(str(it.get(f, ""))) for f in fields)]
