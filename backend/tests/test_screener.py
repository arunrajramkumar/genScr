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


def test_build_sql_includes_total_match_count():
    sql, _ = build_sql([{"field": "roe", "op": ">", "value": 10}])
    assert "count(*) OVER () AS total_matches" in sql


def test_new_fields_and_aliases():
    assert parse_query("streak >= 10 and vol < 30 and cagr5 > 15") == [
        {"field": "dividend_streak", "op": ">=", "value": 10.0},
        {"field": "volatility_1y", "op": "<", "value": 30.0},
        {"field": "cagr_5y", "op": ">", "value": 15.0},
    ]


def test_distribution_percentiles_and_histogram():
    from app.services.screener import distribution

    d = distribution(list(range(1, 101)))
    assert d["count"] == 100 and d["p50"] == pytest.approx(50.5)
    assert sum(d["hist"]) == pytest.approx(97, abs=2)  # 2nd..98th percentile window
    assert distribution([]) == {"count": 0}


def test_every_field_has_description_and_group():
    from app.services.screener import DESCRIPTIONS, FIELDS, GROUPS

    grouped = {f for fs in GROUPS.values() for f in fs}
    assert set(FIELDS) == set(DESCRIPTIONS) == grouped


def test_insights_sql_params_line_up_with_placeholders():
    from app.services.screener import insights_sql

    filters = [{"field": "roe", "op": ">", "value": 15}, {"field": "pe", "op": "<", "value": 20}]
    sql, params = insights_sql(filters, "Information Technology")
    assert sql.count("%s") == len(params)
    # funnel: step 1 = roe; step 2 = roe, pe; step 3 = roe, pe, sector; then 4 size buckets x (roe, pe, sector)
    assert params == [15.0, 15.0, 20.0, 15.0, 20.0, "Information Technology"] + [15.0, 20.0, "Information Technology"] * 4


def test_insights_maps_funnel_steps():
    from app.services.screener import insights

    row = {"step_0": 100, "step_1": 40, "step_2": 10, "size_large": 2, "size_mid": 3, "size_small": 5, "size_unknown": 0}
    out = insights(row, [{"field": "roe", "op": ">", "value": 15}], "Energy")
    assert out["universe"] == 100
    assert out["funnel"] == [{"key": "roe", "remaining": 40}, {"key": "sector", "remaining": 10}]
    assert sum(out["sizes"].values()) == 10


def test_matches_sql_shares_params():
    from app.services.screener import matches_sql

    msql, ssql, params = matches_sql([{"field": "roe", "op": ">", "value": 15}], "Energy")
    assert msql.count("%s") == ssql.count("%s") == len(params) == 2
    assert "percentile_cont" in msql and "GROUP BY s.sector" in ssql
