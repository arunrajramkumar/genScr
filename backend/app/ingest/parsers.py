"""Pure parsers for NSE public files (no network / DB, easy to test)."""

import csv
import io
from datetime import date, datetime

# EQ = regular equity, BE/BZ = trade-for-trade, SM/ST = SME platform.
EQUITY_SERIES = frozenset({"EQ", "BE", "BZ", "SM", "ST"})


def _num(v: str | None) -> float | None:
    v = (v or "").strip().replace(",", "")
    if not v or v == "-":
        return None
    return float(v)


def _int(v: str | None) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _parse_date(v: str) -> date:
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {v!r}")


def _rows(text: str):
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    for raw in reader:
        yield {(k or "").strip(): (v or "").strip() for k, v in raw.items()}


def parse_bhavcopy(text: str, series: frozenset[str] = EQUITY_SERIES) -> list[dict]:
    """Parse an NSE cash-market bhavcopy. Supports the UDiFF format (from 8 Jul 2024)
    and the legacy cmDDMONYYYYbhav.csv format. One row per symbol, preferring EQ."""
    by_symbol: dict[str, dict] = {}
    for r in _rows(text):
        if "TckrSymb" in r:
            if r.get("Sgmt") != "CM" or r.get("SctySrs") not in series:
                continue
            row = {
                "symbol": r["TckrSymb"], "series": r["SctySrs"], "isin": r.get("ISIN"),
                "trade_date": _parse_date(r["TradDt"]),
                "open": _num(r["OpnPric"]), "high": _num(r["HghPric"]), "low": _num(r["LwPric"]),
                "close": _num(r["ClsPric"]), "prev_close": _num(r["PrvsClsgPric"]),
                "volume": _int(r["TtlTradgVol"]), "turnover": _num(r["TtlTrfVal"]),
                "trades": _int(r.get("TtlNbOfTxsExctd")),
            }
        elif "SYMBOL" in r:
            if r.get("SERIES") not in series:
                continue
            row = {
                "symbol": r["SYMBOL"], "series": r["SERIES"], "isin": r.get("ISIN"),
                "trade_date": _parse_date(r["TIMESTAMP"]),
                "open": _num(r["OPEN"]), "high": _num(r["HIGH"]), "low": _num(r["LOW"]),
                "close": _num(r["CLOSE"]), "prev_close": _num(r["PREVCLOSE"]),
                "volume": _int(r["TOTTRDQTY"]), "turnover": _num(r["TOTTRDVAL"]),
                "trades": _int(r.get("TOTALTRADES")),
            }
        else:
            raise ValueError("Unrecognised bhavcopy format")

        existing = by_symbol.get(row["symbol"])
        if existing is None or (row["series"] == "EQ" and existing["series"] != "EQ"):
            by_symbol[row["symbol"]] = row
    return list(by_symbol.values())


def parse_equity_list(text: str) -> list[dict]:
    """Parse NSE EQUITY_L.csv (all listed equities)."""
    out = []
    for r in _rows(text):
        if not r.get("SYMBOL"):
            continue
        out.append({
            "symbol": r["SYMBOL"],
            "name": r["NAME OF COMPANY"],
            "series": r.get("SERIES"),
            "listing_date": _parse_date(r["DATE OF LISTING"]) if r.get("DATE OF LISTING") else None,
            "isin": r.get("ISIN NUMBER"),
            "face_value": _num(r.get("FACE VALUE")),
        })
    return out


def parse_index_constituents(text: str) -> list[dict]:
    """Parse NSE index constituent files (e.g. ind_nifty500list.csv) for sector data."""
    return [
        {"symbol": r["Symbol"], "sector": r["Industry"], "name": r["Company Name"]}
        for r in _rows(text)
        if r.get("Symbol")
    ]
