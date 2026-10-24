import re
from pathlib import Path

from app.routers.market import HEATMAP_COLUMNS, HEATMAP_LIMIT, HEATMAP_MAX_MCAP, _group_by_sector, _short_name

INIT_SQL = Path(__file__).resolve().parents[2] / "db" / "init.sql"


def test_heatmap_periods_use_existing_stock_metrics_columns():
    sql = INIT_SQL.read_text(encoding="utf-8")
    block = re.search(r"CREATE TABLE IF NOT EXISTS stock_metrics \((.*?)\n\);", sql, re.S).group(1)
    for col in HEATMAP_COLUMNS.values():
        assert re.search(rf"^\s+{col}\s", block, re.M), f"stock_metrics has no column {col}"
    assert set(HEATMAP_COLUMNS) == {"1d", "1m", "1y"} and HEATMAP_LIMIT == 500
    assert 1_600_000 < HEATMAP_MAX_MCAP < 1_300_000_000  # above Reliance, below the FIVESTAR outlier


def test_short_name_drops_company_suffix():
    assert _short_name("Tata Consultancy Services Limited") == "Tata Consultancy Services"
    assert _short_name("Reliance Industries Ltd.") == "Reliance Industries"
    assert _short_name("Infosys") == "Infosys"


def test_group_by_sector_sums_sizes_and_rounds():
    rows = [  # already sorted by market cap desc, as the SQL returns them
        {"symbol": "TCS", "name": "Tata Consultancy Services Limited", "sector": "IT", "market_cap": 900000.4, "value": 1.23456},
        {"symbol": "HDFCBANK", "name": "HDFC Bank Limited", "sector": "Financials", "market_cap": 1000000.0, "value": -0.5},
        {"symbol": "INFY", "name": "Infosys Limited", "sector": "IT", "market_cap": 600000.6, "value": 2.0},
        {"symbol": "ODD", "name": "Odd Co", "sector": "Unclassified", "market_cap": 1000.0, "value": 0.0},
    ]
    out = _group_by_sector(rows)
    assert [g["sector"] for g in out] == ["IT", "Financials", "Unclassified"]  # largest sector first
    it = out[0]
    assert it["market_cap"] == 1500001
    assert it["stocks"][0] == {"symbol": "TCS", "name": "Tata Consultancy Services", "market_cap": 900000, "value": 1.23}
    assert out[1]["stocks"] == [{"symbol": "HDFCBANK", "name": "HDFC Bank", "market_cap": 1000000, "value": -0.5}]
