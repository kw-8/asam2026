# capex_intensity — progress

Started: 2026-11-12 · Process: `prompts/data_acquisition.md`

## Idea (user's words)
"What factors/signals are behind the recent decline in AI-related stocks?"

## Step 0 — Ready ✅
- Repo up to date with origin/main (f2985c5).
- Panel present: `data/crsp_monthly_ratios_clean.parquet` (364 MB; 1980-01 to 2025-12).

## Step 1 — Hypothesis ✅ (approved: Option 1)
- **A (driver):** capital-expenditure intensity / growth from the latest annual filing.
- **B (target):** next-month stock returns (also 1–12 months ahead).
- **C (direction, mechanism):** higher capex growth → lower future returns. Investors over-extrapolate the payoff from spending booms; managers over-invest when they have discretion.
- **Predictive, not reactive:** capex is in filings published before the returns predicted; Step 6 enforces publish dates.
- **Universe:** stocks only; ETFs marked n/a (not dropped).
- **Catalog check:** none similar. Catalog has 26 panel ratios (value, profitability, leverage, liquidity, efficiency, quality); no investment/capex signal.
- **Context:** Nov 2026 AI selloff; commentary blames heavy AI spending, post-midterm policy risk to data-centre build-out, profit-taking. Panel ends 2025-12, so the selloff itself is out of sample.

## Step 2 — Search ✅ (approved)
| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Titman, Wei & Xie (2004), JFQA 39(4) 677–700 | Abnormal capital investment: capex/sales vs its average over the prior 3 years | Same (closest) | Firm-level |
| Anderson & Garcia-Feijóo (2006), JF | Capex growth vs 2 years ago (`grcapx`); 3-year variant (`grcapx3y`) | Same | Firm-level |
| Cooper, Gulen & Schill (2008), JF | Total asset growth | Related (broader) | Firm-level |
| Fama-French CMA (2015) / Hou-Xue-Zhang I/A (2015) | Investment factor (asset growth) | Related | Factor returns |
| Open Source Asset Pricing (Chen & Zimmermann) | Has `grcapx`, `grcapx3y`, `AssetGrowth` (annual Compustat lagged 6 months) | Ready-made versions | Firm-level + portfolios |
| JKP Global Factor Data | Investment-theme characteristics and factor portfolios | Related / possibly same | Both (firm-level via WRDS) |

## Step 3 — Download or build ✅ (approved: Case 2, build)
- Case 1 (download, e.g. OSAP `grcapx`): fast; fixed 6-month lag; coverage ends at the library's last release; keyed permno + yyyymm (needs CCM for gvkey).
- Case 2 (build from Compustat via WRDS): exact publish dates, data through latest filings, can use the TWX definition; more steps (6–8).
- Recommendation: Case 2, with OSAP `grcapx` kept as a cross-check in Step 9.

## Step 4b — Definition ✅ (approved: A, TWX abnormal capex — "for right now"; B kept as Step 9 cross-check)
Annual Compustat (`comp.funda`, standard filters INDL/STD/D/C); CCM link LU/LC, P/C.
- **A. Abnormal capex (TWX 2004)** — recommended. CE = capx / sale; CI_t = CE_t / mean(CE_t-1, CE_t-2, CE_t-3) − 1. Paper filters: sales ≥ $10M, ≥ 4 years of data, excludes financials/REITs/trusts/ADRs. Fields: `capx`, `sale`. (Paper's equation is garbled in the PDF; this is the reading consistent with its text "CI = 0 means equal to the prior 3-year average".)
- **B. 2-year capex growth (Anderson & Garcia-Feijóo 2006; OSAP `grcapx`)**: (capx_t − capx_t-2) / capx_t-2; ppent change if capx missing. Fields: `capx`, `ppent`. Use as Step 9 cross-check vs OSAP.
- **C. Capex-to-assets level**: capx_t / at_t-1. Fields: `capx`, `at`. Measures industry capital-intensity more than a spending surge.

## Step 5 — Inventory ✅ (approved; user: nothing extra on the shared drive)
| Need | In panel? | Source if missing |
|---|---|---|
| permno, date, mthret, me, siccd | ✅ | — |
| gvkey | ✅ (11.5% null) | still link via CCM in Step 8 |
| capx, sale (annual) | ❌ | `comp.funda` |
| ceq (paper's non-negative book equity filter) | ❌ (bm is only a proxy) | `comp.funda` |
| datadate, fyear | ❌ | `comp.funda` |
| publish date (Q4 `rdq`) | ❌ | `comp.fundq` (Step 6 decides) |
| ADR / closed-end fund / trust flags | ❌ | CRSP security info — optional, decide in Step 8 |
| financials / REITs | ✅ via siccd | — |
- User's own `wrds_ff_factors.py` already queries `comp.funda` for capx, sale, ceq + CCM → reuse in Step 7.
- No cached Compustat file found locally (ASAM folder has CRSP CSV only).

## Step 6 — Timing ✅ (approved: Option 1, 10-K filing date → next trading day; fallback datadate + 6 months, `assumed`)
All inputs (capx, sale, ceq) are late-reported annual accounting data. capx is a cash-flow-statement item, so it may not appear in the earnings press release; the 10-K is the document guaranteed to carry it.
- **1 (recommended):** exact 10-K filing date (EDGAR era, ~1993–96 onward), tradable from the next trading day → `date_source = exact`; otherwise `datadate` + 6 months as month-end → `assumed`. WRDS table for 10-K dates to be confirmed in Step 7 (team guide doesn't name one).
- **2:** Q4 `rdq` (earnings release) with sanity filters (rdq > datadate, ≤ 180 days), next trading day → `exact`; fallback 6 months. Wider coverage, but risks using capx before it was public.
- **3:** fixed lag for all → `assumed`. 6 months = team default (also TWX/Fama-French). 4 months = course textbook ch. 20 convention; needs explicit approval + reason recorded.

## Step 7 — Pull ✅ (awaiting OK)
- Script: `signals/capex_intensity/pull_compustat.py` (read-only). Pulls `comp.funda` (capx, sale, ceq, at, ppent; standard filters; datadate ≥ 1975), `comp.company` (conm, cik, sic, fic), `crsp.ccmxpf_lnkhist` (LU/LC, P/C). Saves to `data/capex_intensity/*.parquet`. Also lists candidate 10-K filing-date tables (comp tables with "file"; `wrdssec`) — pick one before pulling dates.
- **Run 1 done (2026-11-12):** `funda_raw` 46,162 firms, fiscal years 1974–2026, 77.8% of rows have both capx and sale; `company` 58,761 rows; `ccm_links` 33,324 rows. Spot-check capex/sales (FY2025 or latest): MSFT 0.35 (FY26), META 0.35, GOOGL 0.23, AMZN 0.18, NVDA 0.03. Preview CI (not a test): MSFT +0.93, GOOGL +0.86, AMZN +0.60, META +0.49, NVDA −0.24 → heavy spenders score high, supplier NVDA does not.
- Filing-date sources found: `comp.co_filedate` (gvkey, datadate, srctype, filedate, **filedatetime**; ~2.67M rows) — same keys as funda, has timestamps for the after-close rule → chosen. Also available: `comp.filings` (~34M rows, cik/form/date), `wrdssec` (forms, `wciklink_gvkey`).
- Part 2 script: `signals/capex_intensity/pull_filedates.py` → `data/capex_intensity/co_filedate.parquet` + checks (srctype values, 10-K coverage by decade, exact-date share of capex rows, MSFT/NVDA eyeball).
- Environment issue found: repo requirements resolve to pandas 3.1 + wrds 3.1.6 + SQLAlchemy 1.4, and `db.raw_sql()` then fails ("'Connection' object has no attribute 'cursor'"). wrds ≥ 3.2 needs pandas < 2.3. Script works around it with the DB cursor. **Flag to team** (affects everyone's `raw_sql` / `get_table`).

## Open questions
- Spenders vs suppliers: own-capex captures heavy spenders (hyperscalers). The hardest-hit names in 2026 include suppliers (memory, power) that benefit from others' capex — a different signal. Note for later.
- Exact TWX definition and OSAP/JKP variable names to confirm in Step 4.
