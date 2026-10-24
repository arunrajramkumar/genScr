from datetime import date

from app.ingest.results import not_loaded


def _f(y, m, d, consolidated=True):
    return {"period_end": date(y, m, d), "consolidated": consolidated, "xbrl": f"{y}{m}{consolidated}.xml"}


def test_not_loaded_skips_stored_periods():
    filings = [_f(2026, 9, 30), _f(2026, 6, 30), _f(2026, 3, 31)]
    have = {date(2026, 6, 30): True, date(2026, 3, 31): True}
    assert not_loaded(filings, have) == [filings[0]]


def test_not_loaded_upgrades_standalone_to_consolidated():
    have = {date(2026, 6, 30): False}
    assert not_loaded([_f(2026, 6, 30, consolidated=True)], have)
    assert not not_loaded([_f(2026, 6, 30, consolidated=False)], have)
