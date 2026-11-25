# shareholder_yield — progress

Started: 2026-11-24 · Process: `prompts/data_acquisition.md` · Name `shareholder_yield` is provisional.

**Status (2026-11-24):** Built and validated (9 PASS, 1 INFO; your runs identical to the test runs). **Step 10:** catalog row written to `public_data/factor_catalog.csv` (2026-11-24). **Left for you:** (a) upload `data/shareholder_yield/` to the team's shared drive; (b) commit and sync the 6 files listed in Step 10.

## Summary — `shareholder_yield`
- **Signal:** `net_payout_yield` — cash a firm paid its shareholders over its last fiscal year, net of cash it raised from them, divided by its market value at the month-end. **Higher = more returned per dollar of price.**
- **Definition (Boudoukh, Michaely, Richardson & Roberts 2007, as published; annual Compustat, $ millions):** net payout = `dvc` + `prstkc` + max(`pstkrv`[t−1] − `pstkrv`[t], 0) − (`sstk` − max(`pstkrv`[t] − `pstkrv`[t−1], 0)), from the latest 10-K public by the month-end; ÷ the firm's market value (all its share classes in the panel, by CRSP `permco`) = 1000 × payout ÷ `me_firm` ($ thousands). Blank `prstkc`/`sstk` count as 0 (OSAP's rule; listed in `zero_filled`); blank `dvc` → blank. Non-payers keep 0. On the CCM-linked (primary) share class; usable until 18 months after fiscal year-end; non-USD reporters blank; no trimming.
- **Named check:** `payout_yield` = (`dvc` + `prstkc` + preferred decrease) ÷ market value (gross, ignores issuance). **Robustness only:** `net_payout_yield_xpref` = (`dvc` + `prstkc` − `sstk`) ÷ market value (no preferred adjustment). Both fixed before any return test; the primary is never swapped for whichever looks best.
- **Citation:** Boudoukh, J., Michaely, R., Richardson, M., & Roberts, M. R. (2007). On the Importance of Measuring Payout Yield: Implications for Empirical Asset Pricing. *Journal of Finance*, 62(2), 877–915. doi:10.1111/j.1540-6261.2007.01226.x. Replications: Hou, Xue & Zhang (2020), *RFS* 33(5) (`Op`, `Nop`); Chen & Zimmermann, Open Source Asset Pricing (`NetPayoutYield`, `PayoutYield`). Practitioner term "shareholder yield": Priest & McClelland (2007); Faber (2013).
- **Intuition:** since the 1980s US firms return more cash through buybacks than dividends, so dividend yield alone misses much of the payout; cash actually returned per dollar of price is a clean value measure. Managers also buy back when they think the stock is cheap and issue when it is expensive (the `net_issuance` story), and paying out cash leaves less to waste. Slow-moving (payout policy changes over a year or more).
- **How ASAM can use it (long-only):** tilt toward the highest net payout yields; avoid heavy net issuers.
- **Timing:** 10-K filing date and time (`comp.co_filedate`; before 4 p.m. ET same day, otherwise next trading day); no 10-K date → fiscal year-end + 6 months (`assumed`, 11.0% of signal rows). `version = restated`.
- **Files:** `data/shareholder_yield/shareholder_yield_monthly.parquet` (every panel row: `permno, gvkey, date, net_payout_yield, payout_yield, net_payout_yield_xpref, zero_filled, financial, ceq_nonpos, status, period_end, published_date, date_source, source, version, timing_rule, me_firm, n_classes, curcd, siccd, permco, gvkey_panel`) and `payout_events.parquet` (one row per firm × fiscal year with the inputs and dollar payouts). Not tested for returns here, by design.

## Differences from the source (Boudoukh et al. 2007)
| | Paper | Here |
|---|---|---|
| Items | `dvc`, `prstkc` + preferred decrease, `sstk` − preferred increase (items 21, 115, 108, 56) | same, word for word |
| Missing items | sample = firms with non-missing dividends, repurchases and sales | blank `prstkc`/`sstk` = 0 (OSAP's rule), flagged in `zero_filled`; blank `dvc` → blank |
| Denominator | year-end market cap of the same year | firm market value (all listed classes) at each month-end |
| Timing | fiscal year *t*−1 used July *t* to June *t*+1 | each 10-K's filing date and time; fallback fiscal year-end + 6 months |
| Zeros / extremes | zero yields their own group; top 5% (payout) and top/bottom 2.5% (net) trimmed | non-payers kept at 0; no trimming (rank or winsorize in the backtest) |
| Data | Compustat as of the 2000s | Compustat current (restated) values via WRDS |
| Sample | cross-section July 1984 – Dec 2003 | 1980-01 to 2025-12 (2004–2025 out of sample) |
| Extra columns | — | `payout_yield` (named check), `net_payout_yield_xpref` (robustness: no preferred adjustment) |

## Idea (user's words)
"Can you help me set up a signal for shareholder yield?" Earlier in the same conversation: shareholder yield = dividends + buybacks − new share issues, divided by price.

## Step 0 — Ready ✅
- Local `main` = `origin/main` = GitHub `main` = 4973b76 (checked 2026-11-24). Merge `origin/main` again before pulling data if a few days pass.
- Panel present: `data/crsp_monthly_ratios_clean.parquet` (364 MB; 1980-01 to 2025-12).
- No earlier `signals/shareholder_yield/` folder, so nothing to resume.

## Step 1 — Hypothesis ✅ (approved 2026-11-24: option 3 — net payout yield is the primary, gross payout yield a named check; name `shareholder_yield` kept as no change was asked)

**Decision (user, 2026-11-24):** "Let's do both, with net as a main signal." Primary = net payout yield; named check = gross payout yield. Both fixed now, before any return test; the primary is never swapped for whichever looks best.

- **A (driver):** net cash paid to shareholders over the past 12 months — dividends + share buybacks − new share issues — divided by market value of equity.
- **B (target):** next-month returns, also 1–12 months.
- **C (direction, mechanism):** higher net payout yield → higher future returns. Slow signal (payout policy changes over a year or more). Three reasons:
  1. *Valuation:* cash actually returned per dollar of price is a cleaner "cheapness" measure than earnings, which accounting choices can shape. Since the 1980s US firms pay out more through buybacks than dividends, so dividend yield alone misses much of the payout (Boudoukh, Michaely, Richardson & Roberts 2007).
  2. *Market timing:* managers buy back when they think the stock is cheap and issue when they think it is expensive; investors underreact (same mechanism as `net_issuance`).
  3. *Discipline:* paying out free cash flow leaves less to waste on poor investments (Jensen 1986).
- **Predictive, not reactive:**
  - Price is in the denominator, so the yield rises mechanically after a price fall, and firms tend to buy back after falls and issue after run-ups. The signal could just repeat past returns or `bm` → the backtest must control for reversal, momentum and `bm`.
  - Dividends, buybacks and issuance come from the cash-flow statement, which is public only when the 10-Q/10-K (or the earnings release) is out → dated in Step 6, never by fiscal period end.
- **Universe:** stocks only. ETFs `n/a`, not dropped (an ETF's distributions pass through its holdings' dividends, and its share count moves with investor creations and redemptions, not management's choices). The panel has no ETFs.
- **How ASAM can use it (long-only):** tilt toward the highest net payout yields; avoid heavy net issuers.

### Catalog check: related, not the same
| Catalog row | What it is | Overlap |
|---|---|---|
| `divyield` (panel, WRDS ratio) | dividends ÷ price | one part of the numerator; no buybacks or issuance |
| `net_issuance` (yours, 2026-11-15) | 12-month log change in split-adjusted share **count** (4-month skip) | the buyback − issuance part, but counted in shares, not dollars; no dividends |
| `net_issuance` check `comp_issuance` | Daniel–Titman 1-year composite issuance: market-value growth minus total return; counts dividends as payout | close in spirit to minus net payout yield, but from market values (also catches stock-paid mergers and employee stock), not cash flows |

So the new signal adds the **dollar cash flows from the cash-flow statement, scaled by price**. Whether it adds information beyond these three is a backtest question, not decided here.

### Judgement call: which yield is the hypothesis? (option 3 chosen)
- **1. Net payout yield (recommended):** (dividends + buybacks − issuance) ÷ market equity. Matches your words; the version Boudoukh et al. found strongest; covers both the valuation and the market-timing story.
- **2. Gross payout yield:** (dividends + buybacks) ÷ market equity. Pure valuation; less overlap with `net_issuance`; but ignores dilution (a firm can buy back with one hand and issue employee stock with the other).
- **3. Both:** 1 as the primary, 2 as a named check fixed now, before any return test (the team convention). Exact formulas and fields are Step 4b. ← **chosen**

## Step 2 — Search ✅ (approved 2026-11-24)
| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Boudoukh, Michaely, Richardson & Roberts (2007), *JF* 62(2) 877–915, doi:10.1111/j.1540-6261.2007.01226.x (checked the published PDF) | Payout = common dividends (Compustat item 21 = `dvc`) + repurchases (purchase of common and preferred stock, item 115 = `prstkc`, plus any decrease in preferred stock, item 56 = `pstkrv`). Issuance = sale of common and preferred stock (item 108 = `sstk`) minus any increase in preferred stock. Net payout = payout − issuance. ÷ year-end market cap of the same year. Fiscal year t−1 used for returns July t to June t+1. Zero-yield stocks form their own group; trims the top 5% of payout yields and the top and bottom 2.5% of net payout yields. Alternative repurchase measure: change in Treasury stock (from 1983). Cross-section 1984–2003. | **Same** — the reference for both our yields | Firm-level (no data file) |
| Open Source Asset Pricing `NetPayoutYield` (Chen & Zimmermann; checked `SignalDoc.csv` and `pyCode/Predictors/NetPayoutYield.py`, release 2026.10) | BMRR items exactly: (`dvc` + `prstkc` + preferred decrease) − (`sstk` − preferred increase), ÷ market cap (permco) 6 months earlier. Annual Compustat used from 6 months after `datadate`. Drops financials (SIC 6000–6999), `ceq` ≤ 0, firms with < 24 months of data, and **net yields of exactly 0**. | **Same** (our primary) | **Firm-level** (permno, yyyymm) + portfolio returns |
| OSAP `PayoutYield` (`PayoutYield.py`) | Gross version of the above. **Drops yields ≤ 0, i.e. all non-payers.** Keeps missing `ceq`. | **Same** (our named check) | **Firm-level** + portfolio returns |
| OSAP `NetPayoutYield_q`, `PayoutYield_q` (placebos) | One quarter's flows from `fundq` (`dvpsxq × cshoq × ajexq`, `prstkcyq`, `sstkyq`) | Related (fresher, noisier) | Firm-level |
| JKP Global Factor Data (`bkelly-lab/jkp-data`, checked `aux_functions.py`): `eqnpo_me`, `eqpo_me` | eqpo = dividends (`dvt`, else `dv` — includes preferred dividends) + buybacks (`prstkc` + `purtshr`); eqnpo = dividends − (`sstk` − buybacks); ÷ market equity. No preferred-stock adjustment. Also `div12m_me` (CRSP 12-month dividends ÷ ME) and `eqnpo_12m` (CRSP market-based net payout; already in `net_issuance` Step 2). | Same idea; small definitional differences | Firm-level via WRDS `contrib_global_factor` (**VERIFY**) + factor returns on jkpfactors.com |
| Hou, Xue & Zhang (2020), "Replicating Anomalies," *RFS* 33(5) 2019–2133 | `Op`, `Nop` (BMRR, annual) and `Opq`/`Nopq` quarterly variants (1-, 6-, 12-month holding) | Same (replication) | Factor/portfolio returns (global-q.org, **VERIFY**) |
| Priest & McClelland (2007), *Free Cash Flow and Shareholder Yield*; Faber (2013), *Shareholder Yield*; Cambria SYLD ETF | Practitioner "shareholder yield" = dividend yield + net buyback yield, sometimes + net debt paydown yield | Same name; the debt-paydown version is broader | No firm-level data (books); ETF returns only |
| Ken French Data Library — portfolios formed on D/P | Dividend-yield sorts | Related (dividends only) | Returns only |
| Your catalog: `divyield`, `net_issuance` (+ `comp_issuance`) | See Step 1 | Related (the pieces) | Firm-level (have) |

**What the search shows**
- A ready-made firm-level version exists (OSAP `NetPayoutYield` and `PayoutYield`), so Step 3 is a real choice between downloading and building.
- Sources differ on details that change which stocks rank high (decide in Steps 4b and 6):
  - **Timing:** BMRR wait until July after the fiscal year; OSAP 6 months after `datadate`; JKP's lag not confirmed (**VERIFY**); team rule = exact publish date (10-K filing date, as `capex_intensity` found in `comp.co_filedate`, or Q4 `rdq`).
  - **Denominator:** market cap at fiscal year-end (BMRR; OSAP via its 6-month lag) vs at each month-end (JKP). Month-end price updates the yield every month, so it behaves more like a price ratio.
  - **Zeros:** OSAP drops non-payers from the gross yield and exact zeros from the net yield; BMRR keep zero-yield stocks as their own group.
  - **Dividends:** `dvc` (common only; BMRR, OSAP) vs `dvt` (includes preferred; JKP).
  - **Preferred stock:** `prstkc` and `sstk` mix common and preferred; BMRR and OSAP net it out with the change in `pstkrv`; JKP do not.
  - **Employee stock:** `sstk` includes option exercises and employee purchases, so the net yield penalizes firms that pay staff in stock.
  - **Annual vs trailing four quarters:** quarterly data are fresher and have exact `rdq` dates.
  - **Debt paydown:** in some practitioner versions; not in your definition.
- Sample: BMRR's cross-section ends 2003 and the paper is from 2007, so 2004–2025 in our panel is out of sample and largely post-publication.

## Step 3 — Download or build ✅ (approved 2026-11-24: Case 2, build from Compustat; OSAP `NetPayoutYield` / `PayoutYield` downloaded later as Step 9 cross-checks)
- **Case 1 — download OSAP `NetPayoutYield` + `PayoutYield`** (`openassetpricing`, firm-level, permno + yyyymm, release 2026.10). Fast; a published, tested replication of BMRR. But: fixed 6-month lag for everyone (`date_source = assumed` throughout); market cap from 6 months earlier, not the month you trade; non-payers dropped from the gross yield and exact zeros from the net yield, plus financials and `ceq` ≤ 0, so coverage is well below the panel; no `gvkey` (CCM needed); ends at the release's last month.
- **Case 2 — build from Compustat via WRDS.** Exact publish dates (team rule); non-payers kept at a yield of 0; your choice of market-cap date; financials and coverage decided by us; same event-file + monthly-file layout as the other signals. More work (Steps 5–9), but much is already on disk: `data/capex_intensity/co_filedate.parquet` (10-K filing dates with time stamps) and `ccm_links.parquet`, and `capex_intensity/pull_compustat.py` is a template for the `funda` pull.
- **Recommendation: Case 2**, with OSAP `NetPayoutYield` and `PayoutYield` downloaded as Step 9 cross-checks (rank correlation where definitions overlap). Same pattern as `capex_intensity` and `net_issuance`.

## Step 4b — Definition ✅ (approved 2026-11-24: A, Boudoukh et al. annual — "since it follows something published"; settings 1–6 as recommended, no change asked)
Common to all: `comp.funda` / `comp.fundq` with standard filters (INDL/STD/D/C); CCM link LU/LC, P/C; Compustat dollars are in **millions**, panel `me` in **thousands**. A CRSP-based net payout (market-value growth minus total return) is **not** offered: you already have it as `comp_issuance` in `net_issuance`.

- **A. Boudoukh et al. annual (recommended).** Fiscal-year flows from `funda`:
  - pref_down = max(`pstkrv`[t−1] − `pstkrv`[t], 0); pref_up = max(`pstkrv`[t] − `pstkrv`[t−1], 0); a missing preferred change counts as 0 (as OSAP).
  - **Primary** `net_payout_yield` = (`dvc` + `prstkc` + pref_down − (`sstk` − pref_up)) ÷ firm market cap.
  - **Named check** `payout_yield` = (`dvc` + `prstkc` + pref_down) ÷ firm market cap.
  - Fields: `gvkey, datadate, fyear, fyr, curcd, dvc, prstkc, sstk, pstkrv` (+ `ceq` and SIC as flags). Dates: 10-K filing time from `co_filedate` (already on disk).
  - Pros: same items as the paper and OSAP, so the Step 9 cross-check is clean; one 10-K per year with exact filing dates; annual flows smooth out lumpy buybacks. Cons: flows can be up to ~15 months old by the time the next 10-K arrives.
- **B. Trailing four quarters.** Same formula from `fundq`: quarterly flows = year-to-date `dvy`, `prstkcy`, `sstky` minus the previous quarter's year-to-date (Q1 = YTD), summed over the last 4 quarters (all 4 required); preferred change from `pstkq` over 4 quarters. Dates: 10-Q/10-K filing time (or `rdq`).
  - Pros: updates every quarter (fresher). Cons: year-to-date differencing errors and missing quarters; `dvy` includes preferred dividends; quarterly cash-flow items start later than annual (coverage **VERIFY**); the OSAP check would compare against an annual signal.
- **C. Practitioner "shareholder yield" (Priest & McClelland; Faber).** A plus net debt paydown: + (`dltr` − `dltis` − `dlcch`) in the numerator, i.e. long-term debt repaid minus issued, plus the fall in short-term debt.
  - Pros: matches the term as practitioners use it. Cons: broader than your definition; debt flows are noisy and large for utilities, leasing firms and acquirers; no academic replication to cross-check against.

**Settings for A (recommended; fixed with the definition, before any return test):**
1. **Denominator:** firm market cap at **each month-end** (sum over all the firm's listed share classes, as `net_issuance`'s firm-level fix) — the price you trade at, updated monthly like the panel's `ep`/`bm`. Alternative: market cap at fiscal year-end (paper).
2. **Non-payers:** kept with a yield of 0 (paper keeps them as their own group; OSAP drops them).
3. **Dividends:** `dvc` (common only), as the paper and OSAP.
4. **Missing flows:** ~~a missing `dvc`, `prstkc` or `sstk` leaves the yield missing (as OSAP)~~ **Corrected in Step 7 (approved 2026-11-24): OSAP's rule — blank `prstkc` or `sstk` count as 0 (listed in `zero_filled`); a blank `dvc` leaves both yields blank.** A difference from the paper's wording, which requires non-missing data.
5. **Financials, `ceq` ≤ 0:** kept in the file with flags (`is_financial` from SIC 6000–6999, `ceq_nonpos`); excluding them is a backtest choice.
6. **Outliers:** no trimming in the file (the paper trims for its sorts); extremes reported in Step 9.

## Step 5 — Inventory ✅ (approved 2026-11-24; user: nothing extra on the shared drive "that I'm aware of")
| Need | Have? | Where |
|---|---|---|
| `permno`, `date`, `me` (thousands $), `siccd`, `gvkey` | ✅ | panel (`gvkey` 11.5% null → link with CCM anyway) |
| `permco`, to add up market cap across a firm's share classes | ✅ | `data/issuance_insider/crsp_monthly.parquet` (permno, permco, shrout, mthprc; 1974-01 to 2025-12; all 23,480 panel permnos; 33,274 firm-months with 2+ classes) |
| CCM links (LU/LC, P/C) | ✅ | `data/capex_intensity/ccm_links.parquet` (33,324 rows, has permco) |
| 10-K filing dates and times | ✅ | `data/capex_intensity/co_filedate.parquet` (2.63M rows; 313,653 `10K`, plus `10K/A`; `filedatetime`) — Step 6 decides how to use them |
| SIC, company name, CIK | ✅ | `data/capex_intensity/company.parquet`; panel `siccd` |
| Exchange rates (for non-USD reporters) | ✅ | `data/rd_to_market/exrt_mth.parquet` — Step 8 decides convert vs drop |
| `divyield` (Step 9 comparison) | ✅ | panel |
| `dvc`, `prstkc`, `sstk`, `pstkrv` (+ `datadate, fyear, fyr, curcd, ceq`) | ❌ | `comp.funda` — **new pull** (no earlier pull has them: capex had capx/sale/ceq/at/ppent; NOA had pstk, not pstkrv; R&D had xrd/sale) |
| OSAP `NetPayoutYield`, `PayoutYield` (Step 9 cross-check) | ❌ | `openassetpricing` download (public data, no WRDS) |
| Trading-day calendars (after-close rule) | ✅ | `data/lazy_prices/trading_days.parquet`, `data/rd_to_market/trading_days_pre1993.parquet` |

## Step 6 — Timing ✅ (approved 2026-11-24: Option 1, 10-K filing date with the `rd_to_market` / NOA rule and code; sub-choices as recommended — trust very late dates, accept restated values — no change asked)
- **Late-reported?** Yes: `dvc`, `prstkc`, `sstk` and `pstkrv` are annual accounting data. Last year's `pstkrv` comes from the previous 10-K (already public). Market cap (denominator) is market data at month-end: no lag.
- **Which document carries the inputs?** The 10-K for sure. Buybacks and stock sales are cash-flow-statement items, and `pstkrv` (preferred stock at redemption value) is often only in the notes; many Q4 earnings releases have no cash-flow statement (`reference/timing_guide.md` §2: choose the date that matches the specific inputs). Year-to-date buybacks are partly public earlier in 10-Qs, so waiting for the 10-K is conservative (a little stale, never early).
- **Exact dates on disk:** `data/capex_intensity/co_filedate.parquet` (srctype `10K`). Measured for NOA on CRSP-linked firm-years 1978–2025: exact 10-K date for 62% (late 1970s), 69% (early 1980s), 79–87% from 1985 on; median 87 days from fiscal year-end to public (p10 56, p90 94). Re-measured on this signal's rows in Step 9.
- **Options:**
  1. *(recommended)* **10-K filing date, the same rule and code as `rd_to_market` and `net_operating_assets`.** Time known and before 4:00 p.m. ET (UTC clock converted to New York) → public that day; at/after 4:00 p.m. or no time → next trading day. `date_source = exact`. No 10-K date → `datadate` + 6 months as month-end, `assumed`. Consistent with the team's other accounting signals.
  2. **Q4 earnings-release date (`rdq`, `comp.fundq`).** 3–6 weeks earlier, but a second, larger pull, and it would use buybacks and issuance before they were public for firms whose release has no cash-flow statement.
  3. **Fixed 6-month lag for all** (what OSAP does). Simplest and makes the OSAP cross-check like-for-like; every row `assumed`, and about 3 months staler than the median 10-K.
- **Sub-choices (recommendations, same as `rd_to_market` / NOA):** trust very late filing dates (never use a year's numbers before its recorded 10-K date); accept Compustat's current (restated) values, `version = restated` on every row (Compustat Snapshot, the point-in-time version, is not readable on this WRDS account — found during NOA).

## Step 7 — Pull ✅ (run by user 2026-11-24; checked; one decision below before Step 8)
- **`signals/shareholder_yield/pull_compustat_payout.py`** (read-only; needs your WRDS login). One query:
  ```sql
  SELECT gvkey, datadate, fyear, fyr, curcd, dvc, prstkc, sstk, pstkrv, ceq
  FROM comp.funda
  WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
    AND datadate >= '1975-01-01'
  ```
  Saves `data/shareholder_yield/funda_payout.parquet` + `pull_log.txt`. Prints: rows, firms, duplicates, currencies; missing share of each item by decade; payout shape (non-payers, dividend payers, buyers-back, issuers, net > 0 / = 0 / < 0) where the yields can be computed; negative values; spot-check fiscal 2021+ for Apple, Microsoft, ExxonMobil, Tesla, Bank of America (gvkeys, to compare with their 10-K cash-flow statements). Uses the team's cursor workaround for `raw_sql()` (pandas 3 + wrds 3.1.6).
- **`signals/shareholder_yield/get_osap_payout.py`** (no WRDS): downloads OSAP `NetPayoutYield`, `PayoutYield` → `data/shareholder_yield/osap_payout.parquet`, for Step 9.
- Tested here against a fake WRDS connection (synthetic rows incl. a preferred-stock change, a non-payer issuer, missing items, a future fiscal year): runs end to end; preferred adjustment arithmetic checked by hand.
- Run from the repo root, with the .venv active:
  1. `python signals\shareholder_yield\pull_compustat_payout.py --user YOUR_WRDS_USERNAME`
  2. `pip install openassetpricing` (if not already installed for NOA), then `python signals\shareholder_yield\get_osap_payout.py`

### Results (`data/shareholder_yield/pull_log.txt`; OSAP file read directly)
- `funda_payout.parquet`: 536,764 firm-years, 46,165 firms, fiscal years 1974–2026; 0 duplicate `gvkey`+`datadate`. Currencies USD 87.8%, CAD 12.1%, blank 0.1%. One fiscal year-end in the future (gvkey 065286, 2027-05, all blank — same row NOA found; must not reach the monthly file).
- **CRSP-linked firm-years 1978–2025 (233,331; CCM LU/LC, P/C, link window, panel permnos):** all three flows present 80–92% by decade (85.7% overall); one or two missing 7–17% — almost always `prstkc` and/or `sstk` (`dvc` missing 0.3–4.5%); all three missing < 5%.
- Payout shape (all Compustat rows with the three flows): 36–51% pay nothing by decade; dividend payers fell from 54% (1970s) to 31–37%; buyers-back rose from 26% to 48% (2020s); net payout < 0 (net issuers) in 17% (1970s) to 33–41% since 1980.
- Negatives: `dvc` 28, `prstkc` 144, `sstk` 857, `pstkrv` 32 firm-years (data errors or sign flips; Step 9 outliers). `ceq` ≤ 0: 47,441 firm-years (flag only).
- `osap_payout.parquet`: 1,896,593 rows, 15,525 permnos, 1952-11 to 2025-12; `NetPayoutYield` 1.80M values (37.8% negative), `PayoutYield` 1.38M (all > 0: non-payers dropped).

### Spot-check against filings (fiscal 2021+)
- **Microsoft** (cash-flow statement, FY2022–24): stock issued 1,841 / 1,866 / 2,002 and repurchased 32,696 / 22,245 / 17,254 = Compustat `sstk` / `prstkc` exactly. `dvc` (dividends *declared*, 22,293 in FY2024) differs from dividends *paid* — expected, the paper's item.
- **ExxonMobil:** dividends to shareholders 14,924 / 14,939 / 14,941 / 16,704 (2021–24) and stock acquired 15,155 / 17,748 / 19,629 / 20,273 (2022–25) = `dvc` / `prstkc` exactly. The 545 million shares issued for Pioneer (2024, non-cash) are **not** in `sstk`: a stock-paid merger is not a cash issuance, so the net yield ignores it (unlike `net_issuance`, which counts share counts).
- **Apple** (FY2023–24): `prstkc` 82,981 / 100,390 = repurchases 77,550 / 94,949 **plus** taxes paid for net share settlement of employee awards 5,431 / 5,441 — Compustat counts shares withheld for employees' taxes as a buyback. Apple's cash-flow statement has **no stock-issuance line**, so `sstk` is blank (FY2022–24), not missing information.
- **Tesla, Bank of America:** values look plausible (Tesla: no dividends or buybacks; employee stock issuance 541–1,241); not checked against the filings here — Step 9's spot-check covers three firms.

### Finding: Step 4b setting 4 needs a correction (decide before Step 8)
- Setting 4 said a missing `dvc`, `prstkc` or `sstk` leaves the yield missing "as OSAP". **That is not what OSAP does**: its Compustat download fills blank `prstkc` and `sstk` with 0 before any signal is built (`DataDownloads/CompustatAnnual.py`, "missing-as-zero convention"); only `dvc` must be present. OSAP's Apple `NetPayoutYield` equals its `PayoutYield` in 2023–25, confirming it. (JKP's SAS-style sums do the same.)
- A blank here usually means the line is not in the firm's cash-flow statement (Apple, Alphabet 2019–25, Chevron 2015–17 for buybacks), i.e. zero, not unknown.
- Coverage of linked firm-years with the yields: **strict rule 85.7%** (80–92% by decade) vs **OSAP rule 97.9%** (95.5–99.7%); the difference is 28,385 firm-years, including the largest buyback firms.
- **Options:**
  1. *(recommended)* **OSAP's actual rule:** blank `prstkc` or `sstk` → 0; blank `dvc` → yields missing. Add a column `zero_filled` naming the items filled, so Step 9 and the backtest can check those rows. Matches the published replication (Step 9 cross-check like-for-like) and keeps Apple and Alphabet.
  2. **Keep setting 4 as approved:** any blank → missing. Loses 12% of linked firm-years, tilted toward big buyback firms with no stock-issuance line.
- No return has been looked at; this is a data-handling fix found in the pull, recorded before Step 8.
- **User (2026-11-24): "Use the OSAP rule. That's what the paper refers to, correct?"** Checked the paper's text: **no**. BMRR never say how blank Compustat items are coded, but their cross-section uses stocks "containing nonmissing data" for dividends, repurchases and sales (Table III and Figure 3 notes; Table VI: firms "with data for dividends paid to common shareholders, repurchases of common stock, and sales of common stock"). That reads as the **strict** rule. Zero-filling is OSAP's (and JKP's) implementation choice, not the paper's stated rule. Asked the user to confirm the choice knowing this.
- **Decision ✅ (user, 2026-11-24): "Let's use this OSAP rule."** Option 1. Recorded as a difference from the paper; the paper's strict sample = rows with `zero_filled` empty.

## Step 8 — Construct ✅ (choices 1–3 approved 2026-11-24 by running the script; **your run: `payout_events.parquet` and `shareholder_yield_monthly.parquet` identical to the test run**, `build_log.txt` identical apart from Windows line endings)
Script: `signals/shareholder_yield/build_shareholder_yield.py` (no WRDS). Inputs all on disk: `funda_payout.parquet`, `co_filedate`, `ccm_links`, `crsp_monthly` (permco), trading calendars, the panel. Timing, linking and monthly matching are the same code as `rd_to_market` / NOA.
- **Event file** `data/shareholder_yield/payout_events.parquet`, one row per `gvkey` × fiscal year-end: `permno, gvkey, period_end (= datadate), published_date, date_source, source, version = restated, timing_rule, filedate, filetime_et, fyear, fyr, curcd`; inputs `dvc, prstkc, sstk, pstkrv, pstkrv_prev, pref_down, pref_up, zero_filled, ceq, ceq_nonpos`; dollars `gross_payout, issuance, net_payout` (+ `_usd` versions).
- **Monthly file** `data/shareholder_yield/shareholder_yield_monthly.parquet`: every panel row; latest 10-K public by the month-end. `net_payout_yield` (primary) and `payout_yield` (named check) = 1000 × payout ($ millions) ÷ `me_firm` ($ thousands); flags `zero_filled`, `financial`, `ceq_nonpos`; `status` says why a yield is blank; plus `period_end, published_date, date_source, source, version, timing_rule, me_firm, n_classes, curcd, siccd, permco, gvkey_panel`.
- **Splits:** no adjustment needed — dollar payouts over dollar market value, nothing per share (checked on a split in Step 9).
- **Choices (recommended = what you approved for `rd_to_market`, the closest sibling: an annual flow ÷ firm market value):**
  1. **Share classes:** yields on the CCM-linked (primary) class only, divided by the whole firm's market value (all classes, by `permco`); other classes stay in with a blank ("secondary share class"), so a firm is never counted twice. Alternative: every class gets the same value (as `net_issuance`).
  2. **Non-USD reporters** (Canadian dollars): left blank ("not in USD"), 0.1% of panel rows. Alternative: convert with `exrt_mth`.
  3. **Staleness:** a 10-K is usable until 18 months after its fiscal year-end. Alternatives: 24 months, no limit.
- **Test run here** (real Compustat pull, filing dates, links; panel columns taken from your `rd_to_market` / NOA monthly files, which carry every panel row — the 364 MB panel itself was too large to copy over): 536,764 events (46,165 firms); publish dates 241,425 fallback (mostly firms never in CRSP), 212,712 filing date without time, 44,423 after 4 p.m. ET, 38,204 before 4 p.m.; 0 published before period end. Net payout on 435,037 firm-years (384,637 in USD); zero-filled: `prstkc` 19,610, `prstkc+sstk` 18,992, `sstk` 5,998. Arithmetic check: max error 9e-13. Monthly file = 2,796,065 rows (the panel), 0 duplicate `permno`+`date`.
  - Yields on **91.8%** of panel rows. Blank: no `dvc` 2.3%, no CCM link 2.2%, no 10-K public yet 1.7%, secondary share class 1.1%, older than 18 months 0.8%, no market value 0.1%, non-USD 0.1%.
  - On rows with yields: exact dates 89.0%; financial 16.7%; `ceq` ≤ 0 4.6%; zero-filled 12.5%. `net_payout_yield` < 0 38.7%, = 0 10.9%, > 0 50.4% (median 0.0002; p1 −1.08, p99 0.44). `payout_yield` = 0 (non-payers) 40.0% (median 0.006; p99 0.51).
  - Spot-check vs OSAP: our value at month *t* equals OSAP's at *t* + 6 months (same numerator; OSAP uses the market value from 6 months earlier and waits 6 months) — Apple 0.0306, Microsoft 0.0120, ExxonMobil 0.0633 identical to 4 decimals. Alphabet: GOOGL carries the yield, GOOG blank, firm value = both. Tesla: net −0.0005 to −0.0012, gross 0 (OSAP drops it from `PayoutYield`). Microsoft's 10-Ks, filed after 4 p.m., count from the next trading day.

## Step 9 — Validate ✅ (2026-11-24: 9 PASS, 1 INFO; **your runs: `build_log.txt` identical to the test run, `validate_log.txt` identical plus the panel-only line: `payout_yield` vs `divyield` December rank correlation 0.60**)
Script: `signals/shareholder_yield/validate_shareholder_yield.py` → `data/shareholder_yield/validate_log.txt`. Run here on your own output files (identical to the test build); check 10's `divyield` line needs the panel and will appear in your run.
| # | Check | Result |
|---|---|---|
| 1 | Duplicates | PASS — 0 monthly `permno`+`date`, 0 event `gvkey`+`period_end` |
| 2 | Match to panel | PASS — monthly file = the panel's 2,796,065 rows exactly. Yields 91.8%; no `dvc` 2.3% (mostly 1980s–90s); no CCM link 2.2% (92% of these have no `gvkey` in the panel either); 10-K not yet public 1.7%; secondary share class 1.1%; older than 18 months 0.8%; no market value 0.1%; non-USD 0.1% |
| 3 | Timing | PASS — 0 events published before period end; 0 rows using a 10-K not yet public; 0 older than 18 months; the future-dated Compustat row never used. Fiscal year-end → public: median 89 days (p1 41, p99 184). `assumed`: 11.0% of signal rows (32% 1980–84, 15–19% 1985–99, ≤ 4% from 2000). Apple FY2024 10-K: EDGAR acceptance 2024-11-01 06:01 ET → ours 2024-11-01 |
| 4 | Ticker change (FB → META, June 2022) | PASS — same permno 13407 and gvkey 170617 throughout; implied payout $50,052M constant within the FY2021 10-K; the yield moves only with the share price |
| 5 | Splits | PASS — NVIDIA 10-for-1 (June 2024): price ÷ 9, shares × 10, firm market value and yield smooth. All 13,600 split months (single-class, same 10-K): market value follows the price-only return within 10% in 93.8%; in the rest, CRSP's shares outstanding did not move by the split factor (99.9%) — a panel `me` limitation (share count updated a month late at some splits, mostly 2020s penny-stock reverse splits; 247 months off by > 2x), not this build |
| 6 | Coverage; ETFs | PASS — yields on 83–98% of panel rows each year (84% in 1980–90 when `dvc` is more often blank; 96–98% from 1995). Panel has no ETFs (0 n/a) |
| 7 | Outliers; 3 firms | PASS — Microsoft FY2024 `sstk` 2,002, `prstkc` 17,254; ExxonMobil 2024 `dvc` 16,704, `prstkc` 19,629; Apple FY2024 `prstkc` 100,390 (= 94,949 + 5,441), `sstk` blank → 0: all match. Net yield p1 −1.08, p99 0.44 (firms ≥ $250M: p1 −0.33, p99 0.29). |yield| > 1 in 1.51% of rows: 80% have market value < $50M; 20% are mostly a preferred-stock change (see finding) |
| 8 | Net vs gross; zero-filled | PASS — December rank correlation 0.75 (0.57–0.85). Zero-filled 12.5% of signal rows (7–18% by decade). Apple FY2022–24 zero-filled `sstk`, FY2025 not |
| 9 | OSAP | PASS — where both use the same fiscal year and market-value month (1,036,816 rows): net within 1% of OSAP in 99.8%, gross 99.9%; monthly rank correlation 0.93 (OSAP also drops financials, `ceq` ≤ 0, zeros, first 2 years) |
| 10 | Overlap (info only) | December rank correlation of `net_payout_yield` with −`net_issuance` 0.48, with −`comp_issuance` 0.64; `payout_yield` with panel `divyield` 0.60 (your run) |

### Finding: preferred-stock conversions count as payouts (decide before your run)
- The paper's formula (checked word for word in the published PDF): repurchases = item 115 "**plus** any reduction in the value of the net number of preferred stocks outstanding"; issuance = item 108 "minus any increase" in it. OSAP the same; JKP has no preferred adjustment.
- So when preferred stock **converts into common** — venture-backed preferred at an IPO, or a bankruptcy reorganization — the fall in preferred stock counts as cash paid out although no cash moved. Examples (firms ≥ $250M): Zymergen, Bloom Energy, Bird Global, Samsara (IPO years); Dade Behring 2003 (reorganization, yield 19.6).
- Size: a preferred adjustment in 13.9% of signal rows; worth > 10% of market value in 3.8% (2.3% for firms ≥ $250M). In the **top net-yield quintile** each December (firms ≥ $250M), the preferred change is more than half the yield in **10%** of rows — i.e. a long-only "high shareholder yield" list would partly hold IPO conversions.
- **Options:**
  1. *(recommended)* Keep the paper's formula as `net_payout_yield` (primary, unchanged — fixed before any test; matches OSAP) and add one robustness column `net_payout_yield_xpref` = (`dvc` + `prstkc` − `sstk`) ÷ firm market value, no preferred adjustment (as JKP). The backtest reports the primary as the result; `xpref` only answers "did preferred conversions matter?" and is never picked because it does better (same rule as NOA's `noa_adj`). Small build change, then rerun build + validate.
  2. Keep as is; list it as a known limitation only.
  3. Make the no-preferred version the primary. Economically cleaner, but no longer the paper's number, and the OSAP cross-check no longer applies.
- **Decision ✅ (user, 2026-11-24): Option 1.** `net_payout_yield` (the paper's formula) stays the **primary signal**, unchanged; `net_payout_yield_xpref` = 1000 × (`dvc` + `prstkc` − `sstk`) ÷ `me_firm` added as a **robustness column only**. Rule for the backtest: report `net_payout_yield` as the result; `xpref` answers "did preferred conversions matter?" and is never picked because it does better.
- Build and validation scripts updated and re-run here (2026-11-24): every existing column identical to your run; new column on the same 2,566,396 rows. `xpref` = primary in 86.1% of rows with yields (all rows with no preferred change); elsewhere the gap is exactly (`pref_down` + `pref_up`) ÷ market value. December rank correlation with the primary 0.91 (min 0.89); firms ≥ $250M: 90.4% of the primary's top quintile also in `xpref`'s. Upper tail smaller without the preferred adjustment (p99 0.26 vs 0.44). Validation: 9 PASS, 1 INFO.
- **Next (yours):** rerun `build_shareholder_yield.py`, then `validate_shareholder_yield.py`.

### Known limitations so far
1. Compustat's current (restated) values, not as first reported (`version = restated`).
2. Preferred conversions counted as payouts (the paper's formula; `net_payout_yield_xpref` shows the effect).
3. Panel market value at some split months uses a CRSP share count updated a month late (check 5) — shared by every price-scaled signal on the panel.
4. Blank `prstkc`/`sstk` = 0 (OSAP's rule; the paper requires non-missing data) — `zero_filled` marks them.
5. Firm market value counts only share classes in the panel (as `rd_to_market` and OSAP-like).
6. Stock-paid mergers are not issuance (cash-flow definition), unlike `net_issuance`.
7. 11.0% of signal rows use the assumed 6-month date (more in the early 1980s). Paper published 2007, cross-section ends 2003, so 2004–2025 is out of sample.

## Open questions
- Redundancy: how correlated will it be with `divyield`, `net_issuance` and `comp_issuance`? Report in the backtest, not used to choose the definition.

## Step 10 — Save ✅ catalog row written 2026-11-24 (your OK: `category = value`, which already holds `divyield`, `bm`, `ep`, `cfp`; appended as line 35, the 33 existing rows unchanged byte for byte); upload and commit: yours
- **Catalog row** (one row, `name = shareholder_yield`, `category = value`, `status = have-data`, `added_by = raghavrc`, `date_added = 2026-11-24`): hypothesis, definition (primary + named check + robustness column), source, citation, inputs, location, timing rule, and notes with the validation results and the six known limitations above — same layout as the `rd_to_market` and `net_operating_assets` rows. Tested: appends as row 34 of `public_data/factor_catalog.csv` with the file's Windows line endings, plain ASCII, columns in the file's order.
- **GitHub (stage exactly these 6 files):** `signals/shareholder_yield/progress.md`, `pull_compustat_payout.py`, `get_osap_payout.py`, `build_shareholder_yield.py`, `validate_shareholder_yield.py`, and `public_data/factor_catalog.csv`. Never `data/` (`.gitignore` already excludes `data/`, `*.parquet` and `*.csv` outside `public_data/`).
- **Shared drive (same layout, `data/shareholder_yield/`):** `shareholder_yield_monthly.parquet` (72.7 MB), `payout_events.parquet` (20.5 MB), `funda_payout.parquet` (6.6 MB), `osap_payout.parquet` (27.2 MB; OSAP firm-level data goes on the drive per `reference/wrds_guide.md`), and the logs `pull_log.txt`, `build_log.txt`, `validate_log.txt`. Nothing goes in `public_data/` besides the catalog row: everything else comes from licensed WRDS data.
