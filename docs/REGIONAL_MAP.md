> **Status: paused (2026-10-24).** Drawing a map of India carries boundary-compliance risk. A map-free "Footprint" variant
> (BRSR exports, plants, markets served) was also built and parked on the `footprint-parked` branch. Kept for reference.

# Companies by state: data, legal, design

Researched 2026-10-24. Status: design only, nothing built.

## 1. Where the location comes from

Tested live on 10 symbols (script kept outside the repo):

| Source | What it gives | Coverage | Automatable? | Verdict |
|---|---|---|---|---|
| **BRSR XBRL on NSE**: index `www.nseindia.com/api/corporate-bussiness-sustainabilitiy?index=equities&symbol=X`, file on `nsearchives` | `CorporateIdentityNumber`, `AddressOfRegisteredOfficeOfCompany`, `AddressOfCorporateOfficeOfCompany` (both addresses include the pincode) | Mandatory for the **top 1,000 listed companies by market cap**. 8/10 in the test (TCS, HATSUN, INFY, ADANIENT, ITC, DRREDDY, HGINFRA, GREENPLY); HAMPTON and HALDER had none | Yes. It's the same session-cookie pattern as `ingest/results.py`: 2 requests per company, about 1 MB XML | **Primary** |
| **CIN itself** | Characters 7–8 are the Registrar of Companies (RoC) state of the registered office (`L22210MH1995PLC084781` → MH). A new CIN is issued when a company moves its office to another state | Every company that has a CIN | Pure function | **State without any address** |
| **MCA company master** on data.gov.in ([catalog](https://www.data.gov.in/catalog/company-master-data), updated 13 Oct 2026) | CIN, name, status, class, *Registered State*, RoC (older extracts also had the registered office address; check this once we have a key) | Every company registered in India | Bulk CSV/API with a free data.gov.in key. **No ISIN**, so join on a normalised name restricted to listed CINs (start with `L`, about 8k rows), then check by hand anything with a fuzzy score below 0.95 | **Fallback for the ~1,600 smaller companies** |
| **India Post pincode directory** on data.gov.in ([resource](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month)) | pincode → office, district, state, latitude/longitude | About 19k pincodes (165k post offices) | One bulk download, refreshed yearly | **pincode → district + map point** (take the median lat/long per pincode: some rows have swapped or blank coordinates) |
| NSE `quote-equity`, BSE `api.bseindia.com` CorpInfo/ComHeader | Address, if you can get the response at all | — | **Blocked**: Akamai returned 403 for every request from curl or httpx in testing. These are undocumented endpoints whose terms don't allow automated access | Don't use |
| Annual report PDF (NSE `api/annual-reports`) | The CIN and address are on the first pages | Patchy (the HAMPTON index was empty); files run to 16 MB | Heavy, and needs PDF parsing | Last resort; manual fixes only |
| MCA21 portal ("View company master data") | Full address | All | Captcha, and the portal's terms forbid scraping | Don't use |

**Recommended chain:**
1. BRSR gives the CIN plus both addresses.
2. Otherwise, the MCA master (name match) gives the CIN and state, and the address if it's in the dataset.
3. The state always comes from the CIN's state code.
4. The pincode is parsed from the address with `\b\d{3}\s?\d{3}\b` and looked up in the India Post directory for the district and map point.
5. Cross-check: the CIN state, the state named in the address and the pincode's state should all agree. Mismatches go to a `needs_review` list, not onto the map.

**Registered office vs corporate HQ.** The registered office is the statutory address: it exists for every company and is what the CIN encodes. The corporate office is where the company is actually run.
- In testing, HGINFRA's registered office is in Jodhpur and its corporate office in Jaipur.
- Many companies register in one city and work from another (Mumbai-registered, Bengaluru-run, for example).
- Default the map to the **registered office**, which can be had for every company. Offer a "Corporate office" toggle for the ~1,000 companies whose BRSR states it.
- Always label which of the two is shown.

## 2. Legal checklist

- [ ] **data.gov.in (MCA master, pincode directory):** licensed under the [Government Open Data License – India](https://www.data.gov.in/government-open-data-license-india). Commercial use is allowed with attribution. Credit "Ministry of Corporate Affairs / Department of Posts, via data.gov.in (GODL-India)" on the page.
- [ ] **NSE BRSR filings:** these are statutory public disclosures. We extract three facts (CIN, two addresses) and link to the filing; we don't republish the documents.
  - Same stance and rate (`REQUEST_DELAY_SECONDS`) as the results ingest.
  - The NSE data-licence caveat in ROADMAP §1 still applies before any monetisation.
- [ ] **DPDP Act 2023:** company addresses aren't personal data.
  - **Never store or show** director names, DINs, signatory details or the BRSR contact person's name, email or phone. The BRSR and governance XBRL files contain these; the parser must whitelist the 3 tags it needs.
  - Some small companies use a promoter's house as their registered office. Show **city/district only** on the map, never the full street address.
- [ ] **Map of India:** must show the official external boundary: all of J&K and Ladakh, including PoK, Gilgit-Baltistan and Aksai Chin, plus Arunachal Pradesh. Showing it wrongly risks action under the Criminal Law Amendment Act 1961 §2, and app stores and hosts take maps down on complaint.
  - Use the [DataMeet](https://github.com/datameet/maps) `Country/india-composite.geojson` outline, whose stated aim is to match Survey of India's official boundary. Its licence is CC-0.
  - Use DataMeet `States/` for the internal boundaries (MIT repository licence; the SOI-derived layers are CC-BY-SA 2.5 / ODbL). Clip the states to the composite outline.
  - **Before launch, check the result by eye against the Survey of India political map** (surveyofindia.gov.in). Also add "External boundaries as per Survey of India; internal boundaries indicative" plus the attribution.
  - The 2021 geospatial guidelines liberalised access to geospatial data, but they don't relax the requirement to show the boundary correctly.
  - Don't use Natural Earth or OSM world boundaries unmodified: both show the de facto lines.
- [ ] **SEBI wording:** descriptive counts only. No "best state to invest", no "emerging hubs to watch", and state rankings are titled "by number of listed companies" or "by combined market cap".
  - Extend `test_compliance_repo.py` to cover the new page.
- [ ] **Accuracy notice:** "Location is the registered office from company filings and MCA records; may lag recent changes."

## 3. Product design

Rendering:
- Build an **inline SVG with `d3-geo` and `topojson-client`** (about 30 KB gzipped combined), pre-projected at build time.
  - There are no tiles and no third-party requests, so the current CSP (`connect-src 'self' api`) is unchanged, and it works in the static export.
  - Leaflet and MapLibre would add 150 KB or more plus tile servers, and they're the wrong tool for a choropleth.
- Simplify the states with mapshaper (`-simplify 2% keep-shapes`, then `-o format=topojson quantization=1e5`). The target is **≤120 KB raw / ~40 KB gzipped**, served from `/public/geo/india-states.topo.json` and lazy-loaded below the fold.
- District boundaries (about 780 districts, ~600 KB) are only needed for the drill-down. Use pincode bubbles instead, so no district polygons are needed.

`/regions` page:
1. **India choropleth.**
   - The metric toggle is: number of listed companies, combined market cap, or median 1Y return. Use a sequential single-hue scale.
   - Hovering a state shows a card with the count, combined market cap, top 3 sectors and the 3 largest companies by market cap, listed as facts.
   - A legend sits alongside, and a "Data covers N of M stocks" coverage note sits below.
2. **Sidebar ranking:** a state list sorted by the selected metric, with bars. It's also the accessible fallback for screen readers and anyone who can't use the map.
3. **State drill-down** (`/regions/gujarat`, static params for 36 states/UTs):
   - Zoom to the state, with district bubbles sized by count or market cap from the pincode lat/long.
   - Sector split as a stacked bar, reusing `Glance`'s Stacked component.
   - Median P/E, ROE and 1Y return for the state vs all of India.
   - A sortable table of every company in the state, reusing the screener table.
4. **"Companies near a pincode":** type a 6-digit pincode and see listed companies whose registered office is within 25 km. This uses the haversine distance over the ~2,600 points, calculated in the browser from a small JSON file (symbol, lat, lon).
   - Nothing about the user is sent or stored.
5. **Screener:** add a `state` filter (dropdown with counts, like the sector filter) and a `region` (North, South, East, West, North-East) quick chip.
6. **Stock page:** a "Registered office: Ahmedabad, Gujarat" line linking to the state page.

Mobile:
- The map becomes a full-width SVG: tap to select a state, no hover.
- Show the ranked list first and the map second below 640 px.
- Small states and UTs (Goa, Delhi, Chandigarh, the north-east) get tappable chips because their polygons are too small to tap.

## 4. Schema and pipeline

```sql
CREATE TABLE IF NOT EXISTS company_locations (
    symbol         TEXT PRIMARY KEY REFERENCES stocks(symbol),
    cin            TEXT,
    reg_address    TEXT,          -- stored for parsing and review; the UI shows city/district only
    reg_pincode    TEXT,
    corp_pincode   TEXT,
    district       TEXT,
    state          TEXT,          -- from CIN state code, else pincode directory
    lat            NUMERIC(8,5),
    lon            NUMERIC(8,5),
    source         TEXT NOT NULL, -- 'brsr' | 'mca_master' | 'manual'
    source_url     TEXT,
    needs_review   BOOLEAN NOT NULL DEFAULT false,
    as_of          DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS company_locations_state_idx ON company_locations (state);
CREATE TABLE IF NOT EXISTS pincodes (pincode TEXT PRIMARY KEY, district TEXT, state TEXT, lat NUMERIC(8,5), lon NUMERIC(8,5));
```

This is additive only: there are no changes to existing tables.

Pipeline:
- `app/ingest/locations.py --source brsr|mca|pincodes`, run from a new workflow `locations.yml` (manual dispatch plus a monthly schedule).
- **BRSR:** the first run is about 1,000 companies × 2 requests at a 1.5 s delay, so about 50 minutes; afterwards only newly filed reports (BRSR season is June–September).
- **MCA master and pincodes:** a bulk CSV download each quarter, with the matching done in SQL and Python.
- A CIN plus state parser with tests: the RoC code map, the pincode regex, and the agree/disagree cross-check.
- **API:** `GET /api/regions` (per-state aggregates, cached), `GET /api/regions/{state}` (companies plus district bubbles), and `state` added to the screener fields whitelist.

## 5. Effort and risks

Effort, about 4–5 focused days:
- Ingest and tests: 1.5 days
- MCA name match and the review list: 1 day
- API: 0.5 day
- Map page and drill-down: 1.5 days
- Screener and stock-page hooks: 0.5 day

Risks:
- **Small-cap coverage depends on the MCA name match.** This needs a free data.gov.in API key (`DATA_GOV_IN_KEY` secret). Whether the current master still includes the registered office address must be confirmed. If it doesn't, small caps get a state (from the CIN) but no district dot.
- **BRSR tag names may change** with SEBI's BRSR Core taxonomy updates. Pin the tags in tests and alert when more than 5% of runs return a blank.
- **Map boundary:** must get a manual visual check against the SOI before publishing. This is the main legal exposure.
- **NSE access:** the session-cookie pattern works today, but the quote APIs are already blocked by Akamai, and the BRSR index could follow. Store `source_url` so a refresh can work straight from the archive links.
- **Concentration:** Maharashtra (mostly Mumbai) will dominate counts and market cap. Offer log or "per-state share" scales, so the map isn't one dark state against a grey country.
