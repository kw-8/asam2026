# short_interest: progress

## Hypothesis (written before any return test, 2026-11-24)
- A (heavily shorted stocks) earn lower future returns than lightly shorted ones (B), within months. Short sellers are informed and shorting is costly, so a large short position marks overpricing that the market has not yet corrected (Desai, Ramesh, Thiagarajan & Balachandran 2002; Asquith, Pathak & Ritter 2005; Hong, Li, Ni, Scheinkman & Xiong 2016 for days to cover).
- Long-only use: low short interest = long; or drop the most-shorted quintile from the long book.
- Predictive, not reactive: the position is public only after the settlement date; we use it from 8 business days after settlement.

## Pre-registration
- **Primary:** `si_ratio` (shares short / shares outstanding), annual December formation, low-minus-high quintile, EW, default universe (NYSE-median size, price >= $5, vol36). higher_better = False.
- **Same signal, monthly:** formation every month-end, held 1 month, low-minus-high quintile EW. This is the horizon the papers use.
- **Variants (each a trial):** VW legs; terciles; `dtc` (days to cover) instead of si_ratio; "avoid" screen = EW universe without the most-shorted quintile minus the EW universe. Annual: 5, monthly: 4 (primary, VW, dtc, avoid). n_trials = 9.
- **Sample:** short interest on this WRDS account starts 2006-07. Annual cohorts Dec 2006 - Dec 2024, hold years 2007-2025. Design = hold years 2007-2015, holdout = 2016-2025. Monthly: return months 2006-09 - 2015-12 design, 2016-01 - 2025-12 holdout.

## Data
- Source: Compustat `comp.sec_shortint` (WRDS), 5,429,728 rows, 33,066 gvkeys, settlement dates 2006-07-14 to 2026-11-13, twice a month. Pulled with `pull_short_interest.py` (user ran it; WRDS read-only).
- Link: (gvkey, iid) -> permno with `crsp.ccmxpf_lnkhist` (LU/LC, liid = iid, settlement date inside the link window). 50.8% of settlement rows link (the rest: OTC, ADRs, funds with no CRSP link).
- Build: `build_short_interest.py` -> `data/short_interest/si_events.parquet`, `si_monthly.parquet` (896,318 permno-months, 9,088 permnos, 2006-07 to 2025-12).
- si_ratio = shortint / (panel shrout x 1000). Shares from the last panel month-end on or before the settlement date (end-of-month settlements use that month), so both are on the same side of a split. dtc = shortint / (panel mthvol / 21).
- Timing: published_date = settlement date + 8 business days (exchange/FINRA publication schedule; `assumed`). A month uses the latest published settlement; one older than 45 days at the month-end is not used. In practice a month-end uses the mid-month settlement (median 16 days old).

## Validation (`validate_short_interest.py`)
- 0 duplicate permno-months; published_date >= period_end and <= date everywhere; 100% `assumed` (publication lag).
- December coverage among price >= $5 stocks: 94% (2006) to 99% (2024) of stocks, >98% of market cap.
- si_ratio median 1.6%, 99th pct 25%; 13 rows > 1 (tiny share counts, e.g. permno 22200 with 199k shares) - use ranks.
- Split: AAPL 4:1 on 2020-08-31 - si_ratio 0.12-0.24% on both sides, no jump (fixed: first build divided pre-split short interest by post-split shares).
- Spot checks: AAPL 0.1-0.8% every December; TSLA 14-23% in 2011-2017, falling to under 1% from 2021 (matches its well-known short history).
