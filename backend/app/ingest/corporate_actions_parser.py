"""Parse NSE corporate-action 'subject' strings into structured events (pure, no I/O).

NSE subjects are free text that changed style over 20 years, e.g.
  "Agm/Div-Rs.3.70 Per Share", "Dividend-500%", "Intdiv-Rs 3persh/Bonus1:1",
  "Annual General Meeting / Final Dividend - Rs.8/- / Special Dividend - Rs.8/-",
  "Dividend-Rs.8.50 Per Share (Including Special Dividend Of Rs.2/- Per Share)",
  "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share", "Bonus 1:2", "Demerger".
"""

import re

_AMOUNT = re.compile(r"(?:rs|re|inr|₹)\.?\s*([\d]+(?:\.\d+)?)", re.IGNORECASE)
_PERCENT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
_PER_SHARE = re.compile(r"([\d]+(?:\.\d+)?)\s*/?-?\s*(?:per|pr)\s*sh", re.IGNORECASE)  # "Dividend 3 Per Share"
_BONUS = re.compile(r"bonus\s*(?:issue)?\s*-?\s*(\d+)\s*:\s*(\d+)", re.IGNORECASE)
_SPLIT = re.compile(
    r"(?:split|sub-?division).*?from\s*(?:rs|re|inr|₹)?\.?\s*([\d.]+).*?to\s*(?:rs|re|inr|₹)?\.?\s*([\d.]+)",
    re.IGNORECASE,
)
_RIGHTS = re.compile(r"rights\s*(?:issue)?\s*-?\s*(\d+)\s*:\s*(\d+)(?:.*?(?:@|premium|price)\D*([\d.]+))?", re.IGNORECASE)
# Split a subject into parts on "/" (but not the "/-" in "Rs.31/-") and on " and ".
_PARTS = re.compile(r"/(?!-)|\band\b", re.IGNORECASE)
_DIVIDEND_WORDS = re.compile(r"\b(div|dividend|intdiv|int\s*div|final|interim|special)", re.IGNORECASE)
_IGNORED = re.compile(r"\b(interest|redemption|debenture|bond|ncd|warrant)\b", re.IGNORECASE)


def _dividend_amount(part: str, face_value: float | None) -> float | None:
    text = re.split(r"\(?\s*including\b", part, flags=re.IGNORECASE)[0]  # "(including special ...)" is already in the total
    amounts = [float(a) for a in _AMOUNT.findall(text)]
    if amounts:
        return amounts[0]
    pct = _PERCENT.search(text)
    if pct and face_value:
        return round(float(pct.group(1)) / 100 * face_value, 4)
    if m := _PER_SHARE.search(text):
        return float(m.group(1))
    return None


def parse_subject(subject: str, face_value: float | None = None) -> list[dict]:
    """Structured events for one corporate-action subject. Dividends on the same line are summed."""
    s = " ".join((subject or "").split())
    if not s or _IGNORED.search(s):
        return []
    events: list[dict] = []

    if m := _BONUS.search(s):
        events.append({"kind": "bonus", "ratio_new": int(m.group(1)), "ratio_held": int(m.group(2))})
    if m := _SPLIT.search(s):
        old, new = float(m.group(1)), float(m.group(2))
        if old > new > 0:
            events.append({"kind": "split", "old_fv": old, "new_fv": new})
    if m := _RIGHTS.search(s):
        events.append({
            "kind": "rights", "ratio_new": int(m.group(1)), "ratio_held": int(m.group(2)),
            "price": float(m.group(3)) if m.group(3) else None,
        })
    elif re.search(r"\brights\b", s, re.IGNORECASE):
        events.append({"kind": "rights", "ratio_new": None, "ratio_held": None, "price": None})
    if re.search(r"\bbuy\s*-?\s*back\b", s, re.IGNORECASE):
        events.append({"kind": "buyback"})
    if re.search(r"\b(demerger|scheme of arrangement)\b", s, re.IGNORECASE):
        events.append({"kind": "demerger"})

    total = 0.0
    found = False
    for part in _PARTS.split(s):
        if not _DIVIDEND_WORDS.search(part) or _BONUS.search(part) or _SPLIT.search(part):
            continue
        amount = _dividend_amount(part, face_value)
        if amount:
            total += amount
            found = True
    if found:
        events.append({"kind": "dividend", "amount": round(total, 4)})
    return events
