import pytest

from app.services.screener import PRESETS, build_sql, parse_query


def test_parse_query_with_aliases():
    assert parse_query("ROE > 18 and de < 0.5\nmcap >= 1000") == [
        {"field": "roe", "op": ">", "value": 18.0},
        {"field": "debt_to_equity", "op": "<", "value": 0.5},
        {"field": "market_cap", "op": ">=", "value": 1000.0},
    ]


@pytest.mark.parametrize("bad", ["roe >", "foo > 1", "roe > 1; DROP TABLE stocks", "roe ~ 3"])
def test_parse_query_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_query(bad)


def test_build_sql_uses_bound_params():
    sql, params = build_sql([{"field": "roe", "op": ">", "value": 15}], sector="IT", sort="pe", order="asc", limit=9999)
    assert "m.roe > %s" in sql and "s.sector = %s" in sql
    assert "ORDER BY m.pe ASC NULLS LAST" in sql
    assert params == [15.0, "IT", 500]


def test_build_sql_rejects_unknown_sort_and_op():
    with pytest.raises(ValueError):
        build_sql([], sort="symbol; --")
    with pytest.raises(ValueError):
        build_sql([{"field": "roe", "op": "LIKE", "value": 1}])


def test_presets_parse():
    for p in PRESETS:
        assert parse_query(p["query"])
