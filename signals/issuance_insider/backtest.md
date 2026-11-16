# issuance_insider — backtest

Signals: `net_issuance` (1980–2025) and `insider_cluster` (2006–2025), built and validated in `progress.md`.
Script: `signals/issuance_insider/backtest_issuance_insider.py` → `data/issuance_insider/backtest/` (log, tables, charts; Git ignores `data/`).

## Plan (fixed 2026-11-16, before any portfolio return was computed)
**Your choices (2026-11-16):** rebalance **monthly** as the main test, with **annual (December, buy-and-hold for the next calendar year)** as a check; universe **investable only**.

**Fixed earlier (Steps 1 and 4b, before any return test):** primaries `net_issuance` and `insider_cluster`; C1 = net shrinker (`net_issuance` < 0) **and** a cluster buy (`insider_cluster` ≥ 1); C2 = average of the month's cross-sectional percentile ranks of −`net_issuance` and `insider_cluster`; only these four are tested; equal- and value-weighted; controls for short-term reversal and `bm`; `insider_cluster` split 2006–2016 vs 2017–2025. Named checks reported side by side, never swapped in for the primary.

**Universe:** at each month-end *t*, panel stocks with |price| ≥ $5 and market value ≥ $250 million (`me` ≥ 250,000 in $ thousands), financials included, with the signal(s) needed. Return = next month's CRSP return (`mthret` at *t*+1, which includes delisting returns); a stock with no next-month return drops out of that month's average (its money goes to the others).

**Portfolios (formed at each month-end, held one month):**
| | Long-only portfolio | Spread (zero-investment) | Sample (return months) |
|---|---|---|---|
| `net_issuance` | Q5 = top fifth of −`net_issuance` (largest net buybacks) | Q5 − Q1 | 1980-02 to 2025-12 |
| `insider_cluster` | stocks with `insider_cluster` ≥ 1 | cluster − no cluster | 2006-04 to 2025-12 |
| C1 | net shrinker **and** cluster buy | C1 − all stocks with both signals | 2006-04 to 2025-12 |
| C2 | Q5 of the average rank | Q5 − Q1 | 2006-04 to 2025-12 |
Quintiles: percentile ranks within the month, ties kept together. Equal-weighted (EW) and value-weighted by `me` at *t* (VW).

**Benchmarks:** market = all panel stocks, value-weighted by last month's `me` (as in the gpa notebook); the universe itself (EW and VW); 1-month T-bill and Fama–French 5 factors + momentum from Ken French's data library (monthly, through 2026-09).

**Evidence fixed as primary (for each signal and combination):**
1. Fama–MacBeth: each month, regress next-month returns on the percentile rank (0–1) of the signal, alone and with controls (ranks of last month's return = reversal, `bm`, size `me`; missing `bm` → rank 0.5); report the average slope with Newey–West (6) t-stat. Slope = return of going from the lowest to the highest rank.
2. The long-only portfolio's Fama–French 5 + momentum alpha (EW and VW), Newey–West (6) t-stat — what a long-only fund would have earned beyond known factors.
Everything else is descriptive: excess return and Sharpe, return over the market, spreads and their alphas, quintile means, factor loadings, average number of stocks, monthly turnover.

**Named checks (Fama–MacBeth with controls, same specification, side by side):** `net_issuance_skip3`, `_skip6`, `_pit`, `comp_issuance`, `net_issuance_5y` (all with sign flipped, so high = buyback); `insider_buyers_1m`, `insider_buy_value_3m`, `insider_npr_6m`.

**Sub-periods:** `net_issuance` 1980–2007 (before Pontiff & Woodgate 2008 was published) vs 2008–2025, and 2006-04 to 2025 (the insider window); `insider_cluster`, C1, C2: 2006-04 to 2016-12 (overlaps Kang, Kim & Wang) vs 2017–2025.

**Annual check:** the same four long-only portfolios formed each December and held for the next calendar year (buy-and-hold; a stock that delists mid-year has its last return paid out and its money spread over the rest, as in the gpa notebook), EW and VW, vs the market.

**Reading the results:** |t| around 2 or more is the usual bar, but four portfolios × two weightings × several statistics means some will look good or bad by chance (course text, Ch. 16). The decision rests on the primary evidence above, the sub-periods agreeing, and the annual check for a once-a-year fund.

**Not done here:** transaction costs (turnover is reported so they can be judged, Ch. 25); out-of-sample weighting of the combination.

## Results (run 2026-11-16, on a copy of your data in the claude.ai workspace; **updated the same day after the share-class fix — numbers below are v2**)
**How it was run:** the plan above, unchanged. Fama–French factors from Ken French's data library (file created from the 2026-09 CRSP database), fetched through the built-in browser and copied byte-for-byte (SHA-256 checked) to `data/ff_monthly_kf.csv`. Log and tables: `data/issuance_insider/backtest/`. One bug was found and fixed before the results below were read: the annual check loaded returns only for stocks with a `net_issuance` value, so young stocks (e.g. IPO-month clusters) were silently dropped from the December cluster portfolios; the script now stops if a picked stock has no returns. Only the annual insider numbers changed (EW alpha +0.3% → −0.8%).

### `net_issuance` — works, but mostly as known factor tilts; weaker after publication
- **Long-only Q5 (largest net buybacks), 1980–2025:** beat the market by **+2.8%/yr EW (t 2.0)** and **+2.2%/yr VW (t 2.4)**; Sharpe 0.67 EW / 0.73 VW vs the market's 0.56. About 366 stocks; turnover ~11% a month.
- **Spread Q5 − Q1:** 6.3%/yr EW (t 3.4), 4.6%/yr VW (t 2.7). Most of it is the short side: heavy issuers (Q1) earned 5.2%/yr over T-bills EW vs 9.5–9.8% for Q2–Q4 and 11.4% for Q5.
- **Fama–MacBeth with reversal, `bm` and size: 5.6%/yr (t 3.0)** — primary passes. All five named checks agree (4.9–5.9%/yr, t 2.7–3.2).
- **FF5 + momentum alpha of Q5: +0.4%/yr EW (t 0.6), +0.7%/yr VW (t 1.3)** — primary does not pass. Q5 loads on profitability (RMW +0.37 EW / +0.26 VW), value (HML) and conservative investment (CMA, VW): firms that buy back stock are profitable, cheap and investing little, and those factors explain most of the return. (Q5 − Q1 EW keeps 2.3%/yr alpha, t 2.2 — the short side, which ASAM cannot use.)
- **After publication (Pontiff & Woodgate 2008), 2008–2025:** Q5 − Q1 5.0%/yr EW (t 1.7), 3.1%/yr VW (t 1.1); Fama–MacBeth 2006+ 3.6%/yr (t 1.4); Q5 VW Sharpe 0.73 vs the market's 0.65. Before: Q5 − Q1 7.1% EW (t 3.1), 5.6% VW (t 2.6).
- **Annual check (December, held a year), 1981–2025:** Q5 VW +1.6%/yr vs the market (t 2.2), EW +2.4% (t 1.9); FF alpha ~0. So it also works for a once-a-year fund, with the same caveat.
- **v1 → v2 (per share class → firm level), key numbers:** Q5 VW vs market +2.1% (t 2.29) → +2.2% (t 2.42); Q5 VW alpha +0.6% (t 1.11) → +0.7% (t 1.30); Q5 − Q1 VW 4.5% (t 2.62) → 4.6% (t 2.67); Fama–MacBeth 5.64% (t 3.05) → 5.62% (t 3.04). Insider results unchanged; C1/C2 change in the second decimal. v1 log kept as `backtest_log_v1_per_class.txt`.

### `insider_cluster` — no premium in investable stocks
- **Long-only cluster portfolio (~116 stocks), 2006-04 to 2025-12:** vs the market **−2.9%/yr EW (t −1.3), −3.9%/yr VW (t −1.6)**; **FF5 + momentum alpha −0.8%/yr EW (t −0.5), −2.5%/yr VW (t −1.1)**. Loads on small size (SMB +0.96 EW) and negatively on momentum (UMD −0.22 VW): insiders buy smaller stocks after price falls.
- **Fama–MacBeth with controls: −1.4%/yr (t −0.6)** — primary does not pass. Named checks: buyers last month +0.8% (t 0.4), dollars bought +1.2% (t 0.8), net purchase ratio +1.6% (t 1.1) — none significant.
- **Sub-periods:** 2006–2016 cluster − none +0.8% EW (t 0.4), −3.6% VW (t −1.3); 2017–2025 −3.4% EW (t −1.9), −4.5% VW (t −1.1). Not positive in either.
- **Annual check:** EW −2.8%/yr vs the market (t −1.1); VW −9.9%/yr (t −4.0), but that VW number is not a reliable signal: each December one stock is 11–43% of the portfolio and the top five 42–81% (e.g. GE 43% at end-2006; AIG, Bank of America and Wachovia at end-2007 before the crisis; Consolidated Edison almost every year — plan-like buying). Diagnostic, not a test.
- Turnover ~32–36% a month (costs not included).
- **Possible reasons (not tested):** the papers find the effect mainly in small firms, which the investable universe excludes; Kang, Kim & Wang measure it over ~21 days, part of which is before the Form 4 is public; "keep everything" includes IPO, offering and plan purchases.

### Combinations
- **C1 (net shrinker and a cluster buy, ~30 stocks):** vs the market −2.6%/yr EW (t −0.9), −3.3%/yr VW (t −0.9); annual VW −7.1%/yr (t −2.1). The insider condition drags it down.
- **C2 (average rank):** behaves like `net_issuance` alone. Q5 alpha +1.2%/yr EW (t 1.2), +0.1%/yr VW (t 0.1); Fama–MacBeth 3.6%/yr (t 1.3); with both ranks in one regression, `net_issuance` 3.6%/yr (t 1.3) and `insider_cluster` −1.0%/yr (t −0.4). The two signals are unrelated (rank correlation −0.03), so the combination could only help if the insider signal had value.

### Bottom line for ASAM (long-only, investable stocks)
- `net_issuance` is a sensible tilt — avoid heavy issuers, lean toward buyers-back — but it is mostly a cheap way to hold profitability, value and low-investment exposure, and its edge has been smaller since 2008. Worth keeping as a screen or a component, not as a standalone source of alpha.
- `insider_cluster`, as defined and dated here, adds nothing for a large-cap long-only fund; C1 and C2 are not better than `net_issuance` alone.
- Anything further (e.g. small caps, a 1-month window, a routine-trader filter) would be a new hypothesis, recorded as such before testing.

### Text for the catalog's `test_results` column (written to `public_data/factor_catalog.csv` 2026-11-16, your OK)
- `net_issuance`: Backtest 2026-11-16 (firm level across share classes; investable: price >= $5, me >= $250M; monthly; 1980-2025): Q5 (net buyback) beat the market +2.2%/yr VW (t 2.4), +2.8% EW (t 2.0); Q5-Q1 6.3%/yr EW (t 3.4); Fama-MacBeth with reversal, bm, size 5.6%/yr (t 3.0); FF5+UMD alpha of Q5 small (VW +0.7%, t 1.3; loads on RMW, HML, CMA); weaker 2008-2025 (Q5-Q1 VW 3.1%, t 1.1); annual December check Q5 VW +1.6%/yr vs market (t 2.2). Details: signals/issuance_insider/backtest.md.
- `insider_cluster`: Backtest 2026-11-16 (investable; monthly; 2006-04 to 2025-12): no premium. Cluster portfolio vs market -2.9%/yr EW (t -1.3), -3.9% VW (t -1.6); FF5+UMD alpha -0.8% EW (t -0.5), -2.5% VW (t -1.1); Fama-MacBeth with controls -1.4%/yr (t -0.6); named checks not significant; C1 underperforms, C2 = net_issuance alone. Small caps not tested. Details: signals/issuance_insider/backtest.md.

## After the backtest: screen for 2026 and the share-class fix (2026-11-16)
- **Issue found while building the screen:** `net_issuance` was computed per share class (permno). For firms with two listed classes, conversions between classes or buybacks concentrated in one class put one class in Q5 when the company as a whole did not shrink: Berkshire Class A (−3.8%; A converts into B, B +2.4%), Alphabet Class C (−2.8%; Class A −0.7%), Zillow Class A (−8.0%; Class C +8.4%). The end-2025 value-weighted screen had 19% of its weight in such firms (Alphabet Class C alone 16%).
- **Fix (your OK, 2026-11-16):** `net_issuance` and every share-count check are now **firm level**: a firm (gvkey) with 2+ classes in the panel gets one value, given to every class, = ln( Σ W_c / Σ W_c·exp(−x_c) ) with W_c = the class's market value at *t* (the log change in the firm's total units, each class at its month-*t* price). Single-class firms are exactly unchanged (99% of rows). Validation re-run: 10 PASS (new check 11: single-class rows unchanged, one value per multi-class firm-month in all 14,392, recomputed independently 100%; Berkshire +0.10%, Alphabet −1.74%). Backtest re-run: see v1 → v2 above.
- **Screen (v2):** `net_issuance` Q5 in the investable universe, formed 2025-12-31 (share counts Aug 2024 → Aug 2025) — the portfolio the annual December version holds for 2026. 443 stocks = 441 firms (Bio-Rad and Central Garden have both classes in Q5; listed once). Cutoff: the firm's split-adjusted shares down at least 2.6%. Berkshire, Alphabet and Zillow are no longer in it; Union Pacific (−2.7%) is. Value-weighted, the top 10 are 39% and the top 25 56%. Saved to `data/issuance_insider/backtest/screen_2025-12_net_issuance_q5.csv` (licensed CRSP data → stays out of Git).
