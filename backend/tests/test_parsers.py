from datetime import date

from app.ingest.parsers import parse_bhavcopy, parse_equity_list, parse_index_constituents

UDIFF = """TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
2026-10-22,2026-10-22,CM,NSE,STK,19078,IN0020200104,SGBJUN28,GB,,,,,2.5%GOLDBONDS2028SR-III,14411.89,14411.89,14210.01,14250.00,14250.00,14411.89,,14250.00,,,49,698435.99,15,F1,1,,,,,
2026-10-22,2026-10-22,CM,NSE,STK,2885,INE002A01018,RELIANCE,EQ,,,,,RELIANCE INDUSTRIES LTD,1400.00,1420.50,1395.10,1415.20,1415.00,1401.30,,1415.20,,,1000000,1412345678.90,54321,F1,1,,,,,
"""

LEGACY = """SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,
TCS,EQ,3900,3950,3880,3940,3941,3895,123456,486000000,05-JUL-2024,23456,INE467B01029,
TCS,BL,3900,3900,3900,3900,3900,3895,100,390000,05-JUL-2024,1,INE467B01029,
"""


def test_parse_udiff_filters_non_equity():
    rows = parse_bhavcopy(UDIFF)
    assert [r["symbol"] for r in rows] == ["RELIANCE"]
    r = rows[0]
    assert r["trade_date"] == date(2026, 10, 22)
    assert r["close"] == 1415.20 and r["prev_close"] == 1401.30
    assert r["volume"] == 1_000_000 and r["trades"] == 54321


def test_parse_legacy_format():
    rows = parse_bhavcopy(LEGACY)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "TCS"
    assert rows[0]["trade_date"] == date(2024, 7, 5)
    assert rows[0]["turnover"] == 486_000_000


def test_parse_equity_list_strips_header_spaces():
    text = "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n" \
           "20MICRONS,20 Microns Limited,EQ,06-OCT-2008,5,1,INE144J01027,5\n"
    [row] = parse_equity_list(text)
    assert row == {
        "symbol": "20MICRONS", "name": "20 Microns Limited", "series": "EQ",
        "listing_date": date(2008, 10, 6), "isin": "INE144J01027", "face_value": 5.0,
    }


def test_parse_index_constituents():
    text = "Company Name,Industry,Symbol,Series,ISIN Code\n360 ONE WAM Ltd.,Financial Services,360ONE,EQ,INE466L01038\n"
    assert parse_index_constituents(text) == [
        {"symbol": "360ONE", "sector": "Financial Services", "name": "360 ONE WAM Ltd."}
    ]
