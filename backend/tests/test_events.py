from datetime import date

import pytest

from app.ingest.events import categories, to_rows

# Same shape as NSE's /api/event-calendar response (trimmed to a few records).
SAMPLE = [
    {"symbol": "TCS", "company": "Tata Consultancy Services Limited", "purpose": "Financial Results",
     "bm_desc": "To consider and approve the financial results for the period ended September 30, 2026",
     "date": "09-Oct-2026"},
    {"symbol": "ITC", "company": "ITC Limited", "purpose": "Financial Results/Dividend/Other business matters",
     "bm_desc": "To consider and approve the unaudited financial results and interim dividend",
     "date": "30-Oct-2026"},
    {"symbol": "OLAELEC", "company": "Ola Electric", "purpose": "Fund Raising/Other business matters",
     "bm_desc": "To consider Fund Raising and other business matters", "date": "07-Nov-2026"},
    {"symbol": "SAKUMA", "company": "Sakuma Exports Limited", "purpose": "Board meeting Rescheduled",
     "bm_desc": "Sakuma Exports Limited has informed the Exchange that the meeting is rescheduled", "date": "30-Sep-2026"},
    # Revised notice for the same meeting: one row, first description kept.
    {"symbol": "LLOYDSME", "company": "Lloyds Metals", "purpose": "Fund Raising",
     "bm_desc": "Notice of Board Meeting to be held on Wednesday, 14th October 2026", "date": "14-Oct-2026"},
    {"symbol": "LLOYDSME", "company": "Lloyds Metals", "purpose": "Fund Raising",
     "bm_desc": "Revised Notice of Board Meeting to be held on Wednesday, 14th October 2026", "date": "14-Oct-2026"},
    # Cancelled: nothing stored for that symbol on that date.
    {"symbol": "KOTYARK", "company": "Kotyark Ltd", "purpose": "Fund Raising/Other business matters",
     "bm_desc": "To consider Fund Raising", "date": "12-Oct-2026"},
    {"symbol": "KOTYARK", "company": "Kotyark Ltd", "purpose": "Other business matters",
     "bm_desc": "Intimation regarding Cancellation of Board Meeting scheduled on 12 October 2026", "date": "12-Oct-2026"},
    {"symbol": "bad", "company": "No date", "purpose": "Financial Results", "bm_desc": "x", "date": "not a date"},
]


@pytest.mark.parametrize("purpose, expected", [
    ("Financial Results", ["results"]),
    ("Financial Results/Dividend", ["results", "dividend"]),
    ("Financial Results/Dividend/Other business matters", ["results", "dividend"]),
    ("Financial Results/Fund Raising/Other business matters", ["results", "fund_raising"]),
    ("Dividend", ["dividend"]),
    ("Fund Raising/Other business matters", ["fund_raising"]),
    ("Financial Results/Stock split/Other business matters", ["results"]),  # other only when nothing else matched
    ("Buyback/Other business matters", ["other"]),
    ("Other business matters", ["other"]),
    ("Board meeting Rescheduled", ["other"]),
    ("", ["other"]),
    (None, ["other"]),
])
def test_categories(purpose, expected):
    assert categories(purpose) == expected


def test_to_rows_one_row_per_category_and_meeting():
    rows = {(r["symbol"], r["event_date"], r["purpose"]): r for r in to_rows(SAMPLE)}
    assert set(rows) == {
        ("TCS", date(2026, 10, 9), "results"),
        ("ITC", date(2026, 10, 30), "results"),
        ("ITC", date(2026, 10, 30), "dividend"),
        ("OLAELEC", date(2026, 11, 7), "fund_raising"),
        ("SAKUMA", date(2026, 9, 30), "other"),
        ("LLOYDSME", date(2026, 10, 14), "fund_raising"),
    }


def test_description_is_the_companys_agenda_text():
    rows = {(r["symbol"], r["purpose"]): r for r in to_rows(SAMPLE)}
    assert rows[("TCS", "results")]["description"] == (
        "To consider and approve the financial results for the period ended September 30, 2026")
    assert rows[("LLOYDSME", "fund_raising")]["description"].startswith("Notice of Board Meeting")


def test_cancelled_date_is_dropped_but_other_dates_stay():
    symbols = {r["symbol"] for r in to_rows(SAMPLE)}
    assert "KOTYARK" not in symbols
    cancel_only = [r for r in SAMPLE if r["symbol"] == "KOTYARK"][1:]
    keep = [{**r, "date": "20-Nov-2026"} for r in SAMPLE if r["symbol"] == "KOTYARK"][:1]
    assert [r["symbol"] for r in to_rows(cancel_only + keep)] == ["KOTYARK"]


def test_symbols_are_upper_case_and_blank_or_bad_records_are_skipped():
    out = to_rows([{"symbol": " tcs ", "purpose": "Dividend", "bm_desc": "", "date": "01-Dec-2026"},
                   {"symbol": "", "purpose": "Dividend", "date": "01-Dec-2026"},
                   {"symbol": "INFY", "purpose": "Dividend", "date": None}])
    assert out == [{"symbol": "TCS", "event_date": date(2026, 12, 1), "purpose": "dividend", "description": None}]


def test_empty_input():
    assert to_rows([]) == []
