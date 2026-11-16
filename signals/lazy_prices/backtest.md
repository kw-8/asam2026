# lazy_prices — backtest

Signal: `filing_sim` (1995–2025), built and validated in `progress.md`: cosine similarity of a firm's latest original 10-K with its previous one, usable from `published_date`, at most 15 months old. Low = "changer".
Script: `signals/lazy_prices/backtest_lazy_prices.py` → `data/lazy_prices/backtest/` (log, tables, charts; Git ignores `data/`).

## Plan (fixed 2026-11-15, before any portfolio return was computed)
**Use for ASAM:** an **avoid screen** — hold the investable universe but leave out the biggest changers. The paper's long-short (non-changers minus changers) is reported only as a description.

**Choices reused from the `issuance_insider` backtest (your choices of 2026-11-16 there), so the two signals can be compared:** rebalance **monthly** as the main test, with **annual (December, buy-and-hold for the next calendar year)** as a check; universe **investable only**.

**Universe:** at each month-end *t*, panel stocks with |price| ≥ $5 and market value ≥ $250 million (`me` ≥ 250,000 in $ thousands), financials included, with a `filing_sim` value. Formation months 1998-01 to 2025-11 (1995–97 have too few values while EDGAR phases in). Return = next month's CRSP return (`mthret` at *t*+1, which includes delisting returns); a stock with no next-month return drops out of that month's average.

**Portfolios (formed at each month-end, held one month):** quintiles of `filing_sim` within the month (percentile ranks, ties kept together). Q1 = lowest similarity (biggest changers), Q5 = highest (non-changers). Equal-weighted (EW) and value-weighted by `me` at *t* (VW).
| | What it is |
|---|---|
| **Screened** (the long-only portfolio) | universe minus Q1, i.e. Q2–Q5 |
| **Screen effect** | Screened − universe: what leaving out Q1 adds to a fund that holds the universe |
| Q5, Q1 − universe, Q5 − Q1 | descriptive (Q5 − Q1 is the paper's long-short) |

**Benchmarks:** market = all panel stocks, value-weighted by last month's `me` (as in `issuance_insider`); the universe itself (EW and VW); 1-month T-bill and Fama–French 5 factors + momentum from `data/ff_monthly_kf.csv` (Ken French, through 2026-09).

**Evidence fixed as primary:**
1. Fama–MacBeth: each month, regress next-month returns on the percentile rank (0–1) of `filing_sim`, alone and with controls (ranks of last month's return = reversal, `bm`, size `me`; missing `bm` → rank 0.5); average slope with Newey–West (6) t-stat. **Primary = the slope with controls.** Slope = return of going from the lowest to the highest similarity.
2. The **screen effect's** Fama–French 5 + momentum alpha (EW and VW), Newey–West (6) t-stat — what leaving out the changers added beyond known factors.
Everything else is descriptive: excess return and Sharpe of Screened vs universe vs market, quintile means, spreads and their alphas, factor loadings, the share of the universe's value that Q1 holds (the most the screen can move a value-weighted fund), average number of stocks, monthly turnover of Screened vs the universe.

**Named checks (side by side, never swapped in for the primary):** Fama–MacBeth with the same controls, and the screen effect:
- (a) **without the flagged values:** `filing_sim` from 10-Ks published 2010–2014 (`format_change_2010_14`) treated as missing;
- (b) **bottom tenth** left out instead of the bottom fifth (screen effect only);
- (c) **paper-style timing:** only stocks whose 10-K was published in the last 3 months (the month of publication and the next two), ranked against all stocks that month — close to the paper's design, which enters stocks the month after a filing and holds them 3 months.

**Sub-periods:** 1998-02 to 2014-12 (overlaps the paper's 1995–2014 sample) vs 2015-01 to 2025-12 (after it: out of sample).

**Annual check:** Screened and the universe formed each December and held for the next calendar year (buy-and-hold; a stock that delists mid-year has its last return paid out and its money spread over the rest, as in `issuance_insider`), EW and VW; screen effect and vs the market.

**Reading the results:** |t| around 2 or more is the usual bar, but several portfolios × two weightings × several statistics means some will look good or bad by chance (course text, Ch. 16). The decision rests on the primary evidence, the two sub-periods agreeing, and the checks not contradicting it. A screen that removes a fifth of the stocks can only add about (Q1's weight) × (how much Q1 lags the rest), so a small number is expected even if the signal is real.

**Not done here:** transaction costs (turnover is reported so they can be judged, Ch. 25); underweighting instead of leaving out; the `cosine_eng` version (it had the same 2010–2012 size tilt, `progress.md` Step 10).

## Results (run 2026-11-15, on a copy of your data in the claude.ai workspace)
**How it was run:** the plan above, with one fix after the first run, before the write-up: months with fewer than 50 stocks with a value are skipped. It changes only check (a) — with the flagged values removed, 2011–2014 have no values at all and three edge months had 1, 25 and 48 stocks (a one-stock "portfolio" is noise). The four headline numbers (both screen effects, Q1 vs universe, the Fama–MacBeth slope) were recomputed with separate code and matched exactly. Fama–French factors: the same `data/ff_monthly_kf.csv` as `issuance_insider`. Log, tables and charts: `data/lazy_prices/backtest/`.
**Sample:** formation 1998-01 to 2025-11 (335 return months), 2,014 stocks a month on average = 85% of investable stocks and 90% of investable market value. Late 2025 is thin (208–367 stocks in 2025-07 to 2025-11): filings end 2024-12, so only firms with mid-2024 10-Ks still have a value.

### Primary evidence — neither passes
- **Fama–MacBeth with reversal, `bm` and size: +1.2%/yr (t 1.04)** from the most-changed to the least-changed stock (alone: +0.7%, t 0.5).
- **Screen effect, FF5 + momentum alpha: +0.18%/yr EW (t 1.5), +0.25%/yr VW (t 1.1).** Raw screen effect +0.18%/yr EW (t 1.3), +0.31%/yr VW (t 1.2). Screened VW Sharpe 0.55 vs the universe's 0.53 and the market's 0.51.

### What the screen leaves out
- Q1 is 20% of the stocks and on average **22% of the universe's market value** (4%–74%; 54–70% in 2010–2012, when the format change put the largest firms in Q1).
- **The changers did lag, value-weighted:** Q1 VW −1.6%/yr vs the universe (t −2.0; FF alpha −1.6%, t −2.0); EW −0.7%/yr (t −1.3). Leaving out a fifth of the market turns that into about +0.3%/yr for the fund — the "holes" limit (Ch. 2).
- Non-changers (Q5) did not beat the universe (+0.0% VW, +0.2% EW). Whatever information there is sits on the changer side, which suits an avoid screen, but it is small.
- **The paper's long-short, Q5 − Q1:** +1.0%/yr EW (t 0.9), +1.6%/yr VW (t 1.1); FF alpha +1.2% / +1.8% (t 1.4 / 1.3) — far below the paper's "up to 188 basis points per month" (different design: whole 10-K only, investable stocks, each value kept up to 15 months).
- Loadings: the screen effect leans to value (HML +0.03, t 6.3 EW) and momentum (UMD +0.01, t 2.5 EW) — changers tend to be growth stocks with weak recent returns. The alphas above already remove this.

### When it worked: two bursts
- **1998–2014 (the paper's years): nothing.** Screen effect +0.1%/yr EW (t 0.4), +0.2%/yr VW (t 0.5); alphas ≈ 0. Fama–MacBeth +1.0% (t 0.7).
- **2015–2025: +0.4%/yr EW (t 1.4), +0.5%/yr VW (t 1.3);** EW alpha +0.5%/yr (t 3.0) — the only statistic past the bar. Fama–MacBeth +1.4% (t 0.7).
- **But by year the gain is concentrated** (log section 6b, chart `screen_effect.png`): 2000–2002 and **2022 (+5.9 points VW, +3.1 EW)**. Described here, not tested: without 2022, 2015–2025 is +0.1%/yr EW (t 0.4) and 0.0% VW (t 0.0); without 2000–02 and 2022, the whole period is slightly negative (−0.03% EW, −0.1% VW).
- VW lost in 2012–2013 (−2.5 and −1.5 points) while Q1 held the largest firms for a format reason.

### Checks
- **(a) without the flagged 2010–2014 values** (in practice drops 2010-11 to 2015-01): Fama–MacBeth +1.6% (t 1.2); screen effect +0.3%/yr EW (t 1.7; alpha t 2.2), +0.4%/yr VW (t 1.5). A little better without the format-change years; still borderline.
- **(b) leave out the bottom tenth:** smaller, +0.1%/yr EW and VW (t 0.9–1.0).
- **(c) paper-style timing (only 10-Ks from the last 3 months):** nothing — Fama–MacBeth −4.4% (t −1.1); screen effect ≈ 0.
- **Annual check (December, held a year):** −0.1%/yr EW (t −0.7) and VW (t −0.2); 2015–2025 −0.2% EW, −0.4% VW. A once-a-year fund would have gained nothing.
- **Turnover:** the screen adds 1.6 (EW) to 2.3 (VW) points a month of one-way trading (screened 5.8% / 6.0% vs universe 4.2% / 3.7%), about 20–28% a year. Costs not included.

### Bottom line for ASAM (long-only, investable stocks)
- **Not a reliable avoid screen.** Neither primary test passes; the effect is about +0.2–0.3% a year, comes from two episodes (the 2000–02 bust and 2022), is absent in the paper's own years, and vanishes with annual rebalancing.
- The one solid fact: value-weighted changers lagged by ~1.6% a year (t −2.0). As a screen that is diluted to ~0.3%. Much weaker than `net_issuance` (Q5 VW +2.1%/yr vs the market, t 2.3).
- Anything further would be a new hypothesis, recorded before testing: changes in specific sections (risk factors, MD&A — where the paper finds the effect; WRDS's section data end in 2021), 10-Q changes, or smaller stocks.

### Draft text for the catalog's `test_results` column (not yet written)
- `filing_sim`: Backtest 2026-11-15 (investable: price >= $5, me >= $250M; monthly; 1998-2025): as an avoid screen (leave out bottom fifth) +0.18%/yr EW (FF6 alpha t 1.5), +0.31%/yr VW (alpha +0.25%, t 1.1); Fama-MacBeth with reversal, bm, size +1.2%/yr (t 1.0). Q1 VW lags universe -1.6%/yr (t -2.0) but holds ~22% of value. Nothing in 1998-2014; 2015-2025 +0.4-0.5%/yr, mostly 2022. Annual December check -0.1%/yr. Paper-style 3-month timing: nothing. Details: signals/lazy_prices/backtest.md.
