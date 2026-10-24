import pytest

from app.ingest.corporate_actions_parser import parse_subject


def by_kind(events):
    return {e["kind"]: e for e in events}


@pytest.mark.parametrize("subject, amount", [
    ("Dividend - Rs 8 Per Share", 8),
    ("Interim Dividend - Rs 6.50 Per Share", 6.5),
    ("Agm/Div.Rs.31/- Per Share", 31),
    ("Agm/Div-Re. 3.50/- Pr Shr", 3.5),
    ("Int Div-Rs.3/- Per Sh    Purpose Revised", 3),
    ("3rd Int Div - Rs 3 Per Sh", 3),
    ("Annual General Meeting / Final Dividend - Rs.8/- / Special Dividend - Rs.8/-", 16),
    ("Interim Dividend - Rs 5 Per Share And Special Dividend - Rs 40 Per Share", 45),
    (" Dividend-Rs.8.50 Per Share (Including Special Dividend Of Rs.2/- Per Share).", 8.5),
    ("Annual General Meeting And Dividend Rs.5.25 Per Share", 5.25),
    ("Interim Dividend - Rs    5 Per Share", 5),
    ("Interim Dividend 3 Per Share", 3),
])
def test_dividend_amounts(subject, amount):
    ev = by_kind(parse_subject(subject, face_value=1))
    assert ev["dividend"]["amount"] == pytest.approx(amount)


def test_percentage_dividend_uses_face_value():
    assert by_kind(parse_subject("Agm/Dividend-500%", face_value=1))["dividend"]["amount"] == pytest.approx(5)
    assert by_kind(parse_subject("Agm/Final Dividend-450%", face_value=2))["dividend"]["amount"] == pytest.approx(9)
    assert parse_subject("Agm/Dividend-500%", face_value=None) == []  # can't convert without face value


def test_combined_bonus_and_dividend():
    ev = by_kind(parse_subject("Intdiv-Rs 3persh/Bonus1:1", face_value=1))
    assert ev["bonus"] == {"kind": "bonus", "ratio_new": 1, "ratio_held": 1}
    assert ev["dividend"]["amount"] == 3
    ev = by_kind(parse_subject(" Bonus 1:1 /Dividend- Rs 29 Per Share", face_value=1))
    assert ev["bonus"]["ratio_new"] == 1 and ev["dividend"]["amount"] == 29


@pytest.mark.parametrize("subject, new, held", [("Bonus 1:1", 1, 1), (" Bonus 1:2", 1, 2), ("Bonus Issue 3:2", 3, 2)])
def test_bonus_ratios(subject, new, held):
    ev = by_kind(parse_subject(subject))["bonus"]
    assert (ev["ratio_new"], ev["ratio_held"]) == (new, held)


@pytest.mark.parametrize("subject, old, new", [
    ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share", 10, 1),
    ("Face Value Split From Rs 10 To Rs 2", 10, 2),
    ("Sub-Division Of Equity Shares From Rs.5/- To Re.1/-", 5, 1),
])
def test_splits(subject, old, new):
    ev = by_kind(parse_subject(subject))["split"]
    assert (ev["old_fv"], ev["new_fv"]) == (old, new)


def test_other_kinds():
    assert by_kind(parse_subject("Demerger"))["demerger"] == {"kind": "demerger"}
    assert by_kind(parse_subject(" Buyback"))["buyback"] == {"kind": "buyback"}
    assert by_kind(parse_subject("Buy Back"))["buyback"] == {"kind": "buyback"}
    rights = by_kind(parse_subject("Rights 1:5 @ Premium Rs 100/-"))["rights"]
    assert (rights["ratio_new"], rights["ratio_held"], rights["price"]) == (1, 5, 100)


@pytest.mark.parametrize("subject", ["Interest Payment", "Redemption Of NCD", "Annual General Meeting", ""])
def test_non_equity_or_empty_subjects_ignored(subject):
    assert [e for e in parse_subject(subject) if e["kind"] == "dividend"] == []


def test_real_nse_subjects_parse_without_errors():
    """Every non-dividend subject we saw for ITC/TCS, plus samples from an all-symbols query."""
    for s in ["Agm/Div-Rs.2.65/- Per Sh", "2nd Int Div-Rs.3/- Per Shpurpose Revised", "Bonus 1:1/Div-Rs.5 Per Sh",
              "2nd Interim Dividend-Rs.2/- Per Share", "Third Interim Dividend - Rs 5/- Per Share",
              "Int Div Rs 4 Per Sh", "Dividend - Rs 10.15 Per Share", "Annual General Meeting/Dividend Rs 27/- Per Share"]:
        events = parse_subject(s, face_value=1)
        assert events, s
