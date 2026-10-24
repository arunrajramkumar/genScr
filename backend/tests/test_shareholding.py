import json
from contextlib import contextmanager

import httpx

from app.ingest.shareholding import load_symbol, parse_holdings_xbrl, parse_master

# Trimmed from NSE's corporate-share-holdings-master response for TCS (fields we don't use removed).
MASTER_JSON = """
[
 {"broadcastDate": "19-OCT-2026 18:37:52", "date": "30-SEP-2026", "isin": "INE467B01029",
  "name": "Tata Consultancy Services Limited", "pr_and_prgrp": "71.77", "public_val": "28.23",
  "revisedData": "N", "symbol": "TCS",
  "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/SHP_1741905_19102026063741_WEB.xml"},
 {"broadcastDate": "21-JUL-2026 15:44:00", "date": "30-JUN-2026", "isin": "INE467B01029",
  "name": "Tata Consultancy Services Limited", "pr_and_prgrp": "71.77", "public_val": "28.23",
  "revisedData": "N", "symbol": "TCS"},
 {"broadcastDate": "17-SEP-2026 13:00:28", "date": "31-MAR-2026", "isin": "INE467B01029",
  "name": "Tata Consultancy Services Limited", "pr_and_prgrp": "71.77", "public_val": "28.23",
  "revisedData": "Revised", "symbol": "TCS"},
 {"broadcastDate": "19-JAN-2024 16:38:23", "date": "31-DEC-2023", "isin": "INE467B01029",
  "name": "Tata Consultancy Services Limited", "pr_and_prgrp": "72.41", "public_val": "27.59",
  "revisedData": "N", "symbol": "TCS"}
]
"""

# Trimmed from one TCS quarter's shareholding XBRL (BSE taxonomy). Category totals only; the
# Indian-category context is included to show it is ignored (it repeats the promoter figure).
XBRL = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:in-bse-shp="http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp">
<xbrli:context id="Indian_ContextI"><xbrli:entity><xbrli:identifier scheme="http://www.bseindia.com/in-bse-shp/ScripCode">532540</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:IndianMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="ShareholdingOfPromoterAndPromoterGroup_ContextI"><xbrli:entity><xbrli:identifier scheme="http://www.bseindia.com/in-bse-shp/ScripCode">532540</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:ShareholdingOfPromoterAndPromoterGroupMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="MutualFundsOrUTI_ContextI"><xbrli:entity><xbrli:identifier scheme="http://www.bseindia.com/in-bse-shp/ScripCode">532540</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:MutualFundsOrUTIMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="InstitutionsDomestic_ContextI"><xbrli:entity><xbrli:identifier scheme="http://www.bseindia.com/in-bse-shp/ScripCode">532540</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:InstitutionsDomesticMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="InstitutionsForeign_ContextI"><xbrli:entity><xbrli:identifier scheme="http://www.bseindia.com/in-bse-shp/ScripCode">532540</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:InstitutionsForeignMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<in-bse-shp:NumberOfShares contextRef="InstitutionsForeign_ContextI" decimals="INF" unitRef="shares">2300000000</in-bse-shp:NumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="Indian_ContextI" decimals="INF" unitRef="pure">0.7177</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI" decimals="INF" unitRef="pure">0.7177</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="MutualFundsOrUTI_ContextI" decimals="INF" unitRef="pure">0.0565</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="InstitutionsDomestic_ContextI" decimals="INF" unitRef="pure">0.1357</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="InstitutionsForeign_ContextI" decimals="INF" unitRef="pure">0.0901</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
</xbrli:xbrl>
"""


def test_master_real_sample_newest_first():
    rows = parse_master(json.loads(MASTER_JSON))
    assert [r["period_end"].isoformat() for r in rows] == ["2026-09-30", "2026-06-30", "2026-03-31", "2023-12-31"]
    assert [r["promoter_pct"] for r in rows] == [71.77, 71.77, 71.77, 72.41]
    assert [r["public_pct"] for r in rows] == [28.23, 28.23, 28.23, 27.59]
    assert rows[0]["xbrl"].endswith("SHP_1741905_19102026063741_WEB.xml")
    assert rows[1]["xbrl"] is None


def test_revision_replaces_original_when_broadcast_is_later():
    data = json.loads(MASTER_JSON)
    revised = dict(data[2], broadcastDate="20-SEP-2026 10:00:00", pr_and_prgrp="71.50")  # synthetic: same quarter, later broadcast
    rows = parse_master([data[2], revised])
    assert len(rows) == 1
    assert rows[0]["promoter_pct"] == 71.5
    # and the reverse order gives the same answer
    assert parse_master([revised, data[2]])[0]["promoter_pct"] == 71.5


def test_master_skips_rows_without_promoter_or_date():
    data = [
        {"date": "30-SEP-2026", "pr_and_prgrp": "-", "public_val": "-"},
        {"date": "not a date", "pr_and_prgrp": "70.0", "public_val": "30.0"},
        {"date": "31-MAR-2026", "pr_and_prgrp": "70.0", "public_val": None, "broadcastDate": None},
    ]
    rows = parse_master(data)
    assert len(rows) == 1
    assert rows[0]["period_end"].isoformat() == "2026-03-31"
    assert rows[0]["public_pct"] is None


def test_xbrl_category_totals_become_percent():
    assert parse_holdings_xbrl(XBRL, 71.77, 28.23) == {"fii_pct": 9.01, "dii_pct": 13.57, "mf_pct": 5.65}
    assert parse_holdings_xbrl(XBRL) == {"fii_pct": 9.01, "dii_pct": 13.57, "mf_pct": 5.65}  # default: fractions


# Trimmed from an older TCS filing (2022 taxonomy, Dec-2023 quarter): the same unit holds percents, not fractions,
# and the mutual fund member is spelled MutualFundsOrUtiMember.
XBRL_OLD_PERCENT = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:in-bse-shp="http://www.bseindia.com/xbrl/shp/2022-09-30/in-bse-shp">
<xbrli:context id="ShareholdingOfPromoterAndPromoterGroupI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:ShareholdingOfPromoterAndPromoterGroupMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="PublicShareholdingI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:PublicShareholdingMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="InstitutionsForeignI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:InstitutionsForeignMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="InstitutionsDomesticI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:InstitutionsDomesticMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<xbrli:context id="MutualFundsOrUtiI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">in-bse-shp:MutualFundsOrUtiMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroupI" unitRef="pure" decimals="INF">72.41</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="PublicShareholdingI" unitRef="pure" decimals="INF">27.59</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="InstitutionsForeignI" unitRef="pure" decimals="INF">12.47</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="InstitutionsDomesticI" unitRef="pure" decimals="INF">10.09</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="MutualFundsOrUtiI" unitRef="pure" decimals="INF">3.51</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
</xbrli:xbrl>
"""


def test_xbrl_percent_format_is_not_scaled_again():
    got = parse_holdings_xbrl(XBRL_OLD_PERCENT, 72.41, 27.59)
    assert got == {"fii_pct": 12.47, "dii_pct": 10.09, "mf_pct": 3.51}


def test_scale_falls_back_to_public_when_promoter_is_zero():
    # Widely held company: promoter is 0 in both sources, so only the public category tells the units apart.
    public_fact = (
        '<xbrli:context id="Pub_ContextI"><xbrli:scenario><xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis">'
        'in-bse-shp:PublicShareholdingMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>'
        '<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="Pub_ContextI" decimals="INF" unitRef="pure">0.2823'
        '</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>'
    )
    xml = XBRL.replace('ShareholdingOfPromoterAndPromoterGroup_ContextI" decimals="INF" unitRef="pure">0.7177',
                       'ShareholdingOfPromoterAndPromoterGroup_ContextI" decimals="INF" unitRef="pure">0')
    xml = xml.replace("</xbrli:xbrl>", public_fact + "</xbrli:xbrl>")
    assert parse_holdings_xbrl(xml, 0.0, 28.23) == {"fii_pct": 9.01, "dii_pct": 13.57, "mf_pct": 5.65}


def test_xbrl_without_category_facts_gives_nothing():
    assert parse_holdings_xbrl("<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'></xbrli:xbrl>") == {}


class _FakeNse:
    """Serves the master JSON, the XBRL fixture, and a 404 for one filing."""

    def __init__(self):
        self.gone = "https://nsearchives.nseindia.com/corporate/xbrl/gone.xml"

    def json(self, url):
        data = json.loads(MASTER_JSON)
        data[0]["xbrl"] = "https://nsearchives.nseindia.com/corporate/xbrl/SHP_1741905_19102026063741_WEB.xml"
        data[1]["xbrl"] = self.gone
        return data

    def text(self, url):
        if url == self.gone:
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url), response=httpx.Response(404))
        return XBRL


class _FakeConn:
    def __init__(self):
        self.upserted = []
        self.commits = 0

    @contextmanager
    def cursor(self):
        yield self

    def executemany(self, sql, rows):
        self.upserted.extend(rows)

    def commit(self):
        self.commits += 1


def test_load_symbol_maps_rows_and_keeps_master_numbers_when_xbrl_is_gone():
    conn = _FakeConn()
    n = load_symbol(_FakeNse(), conn, "TCS", quarters=2)
    assert n == 2 and conn.commits == 1
    first, second = conn.upserted
    assert first["symbol"] == "TCS" and first["period_end"].isoformat() == "2026-09-30"
    assert (first["promoter_pct"], first["public_pct"]) == (71.77, 28.23)
    assert (first["fii_pct"], first["dii_pct"], first["mf_pct"]) == (9.01, 13.57, 5.65)
    assert (second["fii_pct"], second["dii_pct"], second["mf_pct"]) == (None, None, None)
    assert second["promoter_pct"] == 71.77
