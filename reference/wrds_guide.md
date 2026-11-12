# WRDS Reference

How the data acquisition agent pulls data from WRDS. Authoritative over the model's memory; if this file is silent or wrong, stop and ask.
Items marked **(VERIFY)** could not be confirmed against official docs. Before relying on one, check it with `describe_table` or a small test query.

**Rule:** All CRSP pulls use the **CIZ (v2)** tables, never the legacy (SIZ) ones such as `crsp.msf`, `crsp.msenames` or `cfacpr`.

---

## 1. Connecting (the user runs this; the agent never sees credentials)

```python
# pip install -U wrds            (team uses wrds >= 3.1; supports Python 3.8–3.12)
import wrds
db = wrds.Connection(wrds_username="your_wrds_username")   # prompts for password in the terminal
```
- The **user types their own password** at the prompt. Never paste it into code, notebooks, chat, or files.
- On the first login the package asks whether to create a `.pgpass` file, which saves the password locally (`~/.pgpass`) so you are not asked again. Answering `y` is fine on a personal machine. `db.create_pgpass_file()` does the same later. **(VERIFY: prompt wording)**
- Duo / two-factor approval may be required on first login.
- Close when done: `db.close()`, or use `with wrds.Connection() as db: ...`.

## 2. Exploring

```python
db.list_libraries()                                  # libraries you have access to
db.list_tables(library="crsp")                       # tables in a library
db.describe_table(library="crsp", table="msf_v2")    # columns, types, approximate row count
db.get_table(library="comp", table="company", columns=["gvkey", "conm"], rows=10)  # quick peek
df = db.raw_sql(sql, date_cols=["mthcaldt"])         # real pulls: always SQL with explicit columns + date range
```
- Pull only the columns and dates you need. Never `select *` on large tables.
- `raw_sql(..., params={...})` with `%(name)s` placeholders avoids string-pasting. **(VERIFY)**

---

## 3. CRSP CIZ (v2): monthly stock data

| What | Table | Key fields |
|---|---|---|
| Monthly security data (legacy MSF) | `crsp.msf_v2` (also `crsp_m_stock.msf_v2`; CRSP's name is *StkMthSecurityData*) | `permno`, `permco`, `mthcaldt` (month's last trading date), `mthret`, `mthretx`, `mthprc`, `shrout` (**thousands**), `mthvol`, `mthcumfacpr`, `mthcumfacshr`, `primaryexch`, `siccd` |
| Security info history (share type, exchange, ticker over time) | `crsp.stksecurityinfohist` | `permno`, `secinfostartdt`, `secinfoenddt`, `sharetype`, `securitytype`, `securitysubtype`, `usincflg`, `issuertype`, `primaryexch`, `conditionaltype`, `tradingstatusflg`, `ticker` **(VERIFY: ticker column name)** |
| Names history, WRDS convenience view (legacy `stocknames`) | `crsp.stocknames_v2` **(VERIFY: exact name + columns)** | permno, ticker, company name, date ranges |
| Cumulative adjustment factors (separate CRSP file) | *StkMthCumulativeAdjFactor*; also carried on `msf_v2` as `mthcumfacpr` / `mthcumfacshr` | |

`mthcaldt` is the last *trading* day of the month. The panel uses calendar month-end, so convert it: `date = mthcaldt + MonthEnd(0)`.

### Tickers change; PERMNO does not
- Always key on `permno`. A ticker can move between companies and a company can change its ticker.
- To find a firm's permno from a ticker, look up `stksecurityinfohist` (or `stocknames_v2`) **with the date range**, because the same ticker can belong to different firms in different years.

### Common stock vs ETF filters (CIZ)
Standard US common stock filter (as used by the WRDS INDRATIOS-CIZ macro and Tidy Finance):
```
sharetype = 'NS' AND securitytype = 'EQTY' AND securitysubtype = 'COM'
AND usincflg = 'Y' AND issuertype IN ('ACOR','CORP')
AND primaryexch IN ('N','A','Q') AND conditionaltype IN ('RW','NW') AND tradingstatusflg = 'A'
```
- **ETFs:** `securitysubtype = 'ETF'` (ETNs are `'ETN'`). The common-stock filter above **excludes** ETFs, so for ETFs drop the `COM` / `usincflg` / `issuertype` conditions. **(VERIFY: full ETF code set; run `SELECT DISTINCT sharetype, securitytype, securitysubtype, issuertype` on a few known ETF permnos such as SPY)**
- Do not silently drop ETFs. Mark them "not applicable" for accounting signals (success criterion 6).

### Split / share adjustment (CIZ equivalents of `cfacpr` / `cfacshr`)
- `mthcumfacpr` = cumulative factor to adjust **prices** (legacy `cfacpr`).
- `mthcumfacshr` = cumulative factor to adjust **shares** (legacy `cfacshr`).
- Comparable across time: `adj_price = abs(mthprc) / mthcumfacpr`, `adj_shares = shrout * mthcumfacshr`.
- Per-share accounting items (EPS, DPS) from Compustat: either use Compustat's own `ajex` / `ajexq` factor, or match the CRSP factor **as of the same date**. Ratios such as price/EPS taken on the same date need no adjustment (split-invariant).
- **(VERIFY:** the factor's direction convention (divide vs multiply) on a known split, e.g. AAPL 2020-08 4:1.)

---

## 4. Compustat

| Table | Use | Key fields |
|---|---|---|
| `comp.funda` | Annual fundamentals | `gvkey`, `datadate` (fiscal period end), `fyear`, items (`at`, `ceq`, `sale`, `ib`, …) |
| `comp.fundq` | Quarterly fundamentals | `gvkey`, `datadate`, `fyearq`, `fqtr`, `rdq` (**report date of quarterly earnings**), items end in `q` (`atq`, `ibq`, `saleq`, …) |
| `comp.company` | Header info | `gvkey`, `conm`, `cik`, `sic` |

**Always apply the standard filters:**
```
indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
```
(plus `curcd = 'USD'` if you want to drop non-USD reporters).
- `rdq` exists only in `fundq`. For annual data, use Q4's `rdq` from `fundq` (same `gvkey`, fiscal year, `fqtr = 4`), or a fallback lag (see `timing_guide.md`).
- Compustat overwrites with restated values; see `timing_guide.md`.

---

## 5. CRSP–Compustat link (CCM)

Table: `crsp.ccmxpf_lnkhist` (columns `gvkey`, `lpermno`, `lpermco`, `linktype`, `linkprim`, `linkdt`, `linkenddt`). `crsp.ccmxpf_linktable` is the same data with extra columns; Tidy Finance uses that one.

Rules (fixed, no judgement):
- `linktype IN ('LU','LC')`: research-quality links only.
- `linkprim IN ('P','C')`: primary security only.
- The accounting date must fall inside the link window: `linkdt <= date <= linkenddt`.
- `linkenddt` is **NULL for links still active**. Replace it with today's date (`COALESCE(linkenddt, CURRENT_DATE)`) before comparing, or those firms will be dropped.
- After merging, check that `(permno, date)` is unique and report the match rate against the panel.

---

## 6. WRDS Financial Ratios Suite

- Firm-level table: `wrdsapps_finratio.firm_ratio` **(VERIFY: exact name; the IBES-augmented version is `wrdsapps_finratio_ibes.firm_ratio_ibes`)**.
- IDs: `permno`, `gvkey`, `ticker`, `cusip`, `public_date`, `adate` (fiscal year end the data refers to), `qdate` (fiscal quarter end).
- `public_date` is a **month-end** date that WRDS treats as when the data was public. WRDS documentation describes a **2-month lag** of accounting data after the period end, with values carried forward until the next filing. The team panel matches this (ratios change about 2 months after quarter end). **(VERIFY: exact rule, and whether the lag is 2 or 3 months for annual items; older WRDS macro code used `datadate + 3 months`.)**
- The 2-month lag can be **too early** for slow filers: non-accelerated 10-K filers have 90 days. Check per signal.
- Firm-level ratios are raw (not winsorized).

---

## 7. Example queries

**A. CIZ monthly returns for US common stocks, with share-type filters as of each month**
```sql
SELECT m.permno, m.mthcaldt, m.mthret, m.mthretx, m.mthprc, m.shrout,
       m.mthcumfacpr, m.mthcumfacshr, s.primaryexch
FROM crsp.msf_v2 AS m
JOIN crsp.stksecurityinfohist AS s
  ON m.permno = s.permno
 AND m.mthcaldt BETWEEN s.secinfostartdt AND s.secinfoenddt
WHERE m.mthcaldt BETWEEN '1980-01-01' AND '2025-12-31'
  AND s.sharetype = 'NS' AND s.securitytype = 'EQTY' AND s.securitysubtype = 'COM'
  AND s.usincflg = 'Y' AND s.primaryexch IN ('N','A','Q');
```

**B. Quarterly fundamentals with report date, linked to PERMNO**
```sql
SELECT f.gvkey, l.lpermno AS permno, f.datadate, f.fyearq, f.fqtr, f.rdq,
       f.ibq, f.atq, f.ceqq
FROM comp.fundq AS f
JOIN crsp.ccmxpf_lnkhist AS l
  ON f.gvkey = l.gvkey
 AND l.linktype IN ('LU','LC') AND l.linkprim IN ('P','C')
 AND f.datadate >= l.linkdt
 AND f.datadate <= COALESCE(l.linkenddt, CURRENT_DATE)
WHERE f.indfmt = 'INDL' AND f.datafmt = 'STD' AND f.popsrc = 'D' AND f.consol = 'C'
  AND f.datadate BETWEEN '1979-01-01' AND '2025-12-31';
```

**C. Ticker history for one firm (spot-check a rename)**
```sql
SELECT permno, ticker, secinfostartdt, secinfoenddt, primaryexch
FROM crsp.stksecurityinfohist
WHERE permno = 14593          -- Apple
ORDER BY secinfostartdt;
```

---

## 8. Factor libraries

Check here before building a signal (Case 1: it already exists). **Data shape:** *firm-level* means a value per stock per month, so it can rank stocks. *Factor returns* means one return series per portfolio, so it is only for comparison.

| Library | Access | Shape | License / where it may live |
|---|---|---|---|
| **Open Source Asset Pricing** (Chen & Zimmermann) | `pip install openassetpricing`, then:<br>`import openassetpricing as oap; openap = oap.OpenAP()`<br>`openap.dl_signal_doc('pandas')` (signal list)<br>`openap.dl_signal('pandas', ['BM'])` (firm-level)<br>`openap.dl_port('op', 'pandas', ['BM'])` (portfolio returns)<br>Also on Hugging Face: `OpenSourceAP/CrossSection` | Both: ~200+ firm-level signals (keyed `permno`, `yyyymm`) **and** long-short portfolio returns | Hugging Face dataset is CC BY 4.0, code GPL-2.0. A few signals (`Price`, `Size`, `STreversal`) are built from CRSP and need your own WRDS login; `dl_all_signals` needs WRDS. Signal date `yyyymm` = tradable at the end of that month (already lagged). Portfolio returns → `public_data/` (GitHub, cite). Firm-level signals → **drive** (too large for GitHub; `Price`/`Size`/`STreversal` are CRSP-derived). |
| **Ken French Data Library** | `pip install pandas-datareader`:<br>`import pandas_datareader.data as web`<br>`ff = web.DataReader('F-F_Research_Data_5_Factors_2x3', 'famafrench', start='1980')`<br>Returns a dict of DataFrames (`ff[0]` monthly, `ff['DESCR']`). `pandas_datareader.famafrench.get_available_datasets()` lists names. Or download CSVs from the website. | Factor and portfolio **returns** only (in percent) | No explicit license stated. Built from CRSP/Compustat. **Drive** until redistribution terms are confirmed; then `public_data/`. **(VERIFY: redistribution terms)** |
| **JKP Global Factor Data** (Jensen, Kelly, Pedersen) | Factor returns: download from jkpfactors.com. Firm-level characteristics: WRDS library `contrib_global_factor` (contributed data form "Global Factor Data"). Code: GitHub `bkelly-lab/jkp-data`. | Factor returns (153 factors, 13 themes, 93 countries) on the site; firm-level characteristics via WRDS | Site data: CC BY-NC 4.0 (cite JKP 2023 JF). Site factor returns → `public_data/` (GitHub, cite JKP; non-commercial use is fine for a class). WRDS firm-level data → **drive** (WRDS terms). **(VERIFY: WRDS table name inside `contrib_global_factor`)** |
| **AQR Data Library** | Download only: Excel files from aqr.com/Insights/Datasets (e.g. BAB, QMJ, HML Devil, Value and Momentum Everywhere). No API. | Factor **returns** only | Terms of use are in a tab inside each spreadsheet; credit "AQR Capital Management, LLC". Histories are revised on every update, so record the download date. `public_data/` if the terms tab allows redistribution, otherwise **drive**. |

Rule: **the drive is for anything that can't go on GitHub.** Public data whose license allows sharing and is under ~50 MB goes in `public_data/` (GitHub caps files at 100 MB). WRDS-derived, license-restricted, unverified-license, or large files go on the shared drive (local copy in `data/`).
