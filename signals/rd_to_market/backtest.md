# rd_to_market — backtest

Signal: `rdm` (R&D-to-market) from `data/rd_to_market/rd_to_market_monthly.parquet`, built and validated in `progress.md` (Steps 0–10). This file records the backtest plan, fixed before any portfolio return on `rdm` was computed, and then the results.

## Strategy-lab version: `rdm` in the `rr_strategy_lab.ipynb` engine (plan fixed 2026-11-23, before any return was computed)
- **Why:** the ASAM question in the lab's format: does a 40-stock, once-a-year, long-only portfolio built on R&D-to-market beat the lab's equal-weighted universe, and does adding `rdm` to the lab's defensive composite help?
- **Engine:** the lab's section A code, unchanged (copied verbatim into `signals/rd_to_market/rdm_strategy_lab.ipynb`). Lab settings unchanged:
  - December formation, 12-month buy-and-hold, first cohort 1983-12.
  - Universe: NYSE-median size screen, price >= $5, `vol36` required.
  - 40 names, at most 30% per FF12 sector.
  - FF3 + UMD alpha (Newey-West 6).
  - Design sample = returns through 2009-12; holdout = 2010-01 on.
- **Signal:** `rdm` = latest annual R&D (`xrd`, from a 10-K public by the formation month-end, usable up to 18 months after fiscal year-end) ÷ the firm's market value at that month-end (all share classes).
  - Merged by permno and month. Higher = better (Chan, Lakonishok & Sougiannis 2001; Hou, Xue & Zhang 2020).
  - Only firms that report R&D have it: about 41% of the December universe before the `vol36` screen, 232–631 firms per cohort (median 367; counted before any return was computed).
  - A stock without `rdm` stays in the universe, so `EW_UNIV` is the lab's universe, but it is ineligible for the RDM strategies.
- **One class per firm:** the signal sits on each firm's primary share class only, so no `one_class()` filter is needed. Using one would be harmful: it could drop the class that carries the signal when another class is larger. Checked after the run: no firm twice in any RDM portfolio.
- **Stated in advance (what could go against it):**
  - The published spread (HXZ 2020: 0.68%/month high-minus-low, value-weighted deciles) includes small stocks. This universe is above the NYSE median, where the effect may be weaker.
  - `rdm` rises when the price falls, so overlap with value (HML) and with past losers is expected. FF3 + UMD alpha controls for both.
  - R&D is concentrated in business equipment and health, so the 30% sector cap will often bind.
- **New strategies (5 new trials, so `n_trials` = 10 + 5 = 15):**
  - `RDM_EW`: rank of `rdm`, equal weight.
  - `RDM_MOM_EW`: same, excluding the bottom 10% on 12−1 momentum (the lab's `mom_ok`).
  - `RDM_VW`: as `RDM_EW`, value weight.
  - `DEF_RDM_EW`: the lab's `DEF_SPEC` composite (low `vol36`, high `gprof`, low `debt_at`, high `ep`) plus `rdm`, equal ranks, with `mom_ok`. The composite needs every input, so this strategy holds R&D firms only.
  - `DEF_RD_EW` (control, not a pick candidate): the `DEF_SPEC` composite among R&D firms only, without `rdm`. It separates "adding `rdm`" from "R&D firms only" in the named check.
  - Baselines in the same run (already counted in the lab's 10): `LOWVOL_EW`, `DEF_EW`, `DEF_IV`, `DEF_MV`.
- **Pick rule (design sample only):** the strategy with the highest design-sample Sharpe ratio among `RDM_EW`, `RDM_MOM_EW`, `RDM_VW` and `DEF_RDM_EW`. The holdout is then computed once and reported for every strategy.
- **What counts as success for the pick in the holdout:** Sharpe above `EW_UNIV` (Jobson-Korkie z > 0; significance at |z| > 2 noted, not required) and FF3 + UMD alpha > 0.
- **Named checks:**
  - `DEF_RDM_EW` vs `DEF_RD_EW`: does `rdm` help, holding the firms fixed?
  - `DEF_RDM_EW` vs `DEF_EW`: is it better than the lab's strategy?
  - Both are z of the Sharpe difference, in the design sample and the holdout.
  - Deflated Sharpe ratio on the design sample at `n_trials` = 15 and, as a stricter check, 30.
  - Share of names replaced per year.
  - Sharpe by formation month (12 runs, MV excluded) and the staggered portfolio.
- **Diagnostics (not trials):**
  - R&D firms per cohort.
  - Sector mix of `RDM_EW` and how often the cap binds.
  - Full FF3 + UMD loadings of the RDM strategies: is it value under another name?
- **Factors:** `data/ff_factors_monthly.csv` (Ken French FF3 + Momentum, 1979-01 to 2026-09). It is the file the `net_issuance` lab built and checked against the website, in the lab's format.
- **Data:** `data/crsp_monthly_ratios_clean.parquet` (2,796,065 rows, 1980-01 to 2025-12), so returns run to 2025-12.

### Pick, recorded before the holdout was looked at (2026-11-23)
- **Pick:** `DEF_RDM_EW` (design Sharpe 0.79). The others: `RDM_MOM_EW` 0.60, `RDM_EW` 0.54, `RDM_VW` 0.39. For comparison, `EW_UNIV` 0.48, `DEF_EW` 0.83 and the control `DEF_RD_EW` 0.86.
- **Named checks, design:** `DEF_RDM_EW` vs `DEF_RD_EW` z = −1.33; vs `DEF_EW` z = −0.54.

### Results (run 2026-11-23 on the workspace copy of your data; notebook executed end to end; executed copy with charts: `data/rd_to_market/backtest/rdm_strategy_lab_executed.ipynb`, not committed)
- **Checks before reading the numbers:**
  - `RDM_EW` and `RDM_MOM_EW` selection recomputed by a plain loop for all 43 cohorts: identical.
  - Buy-and-hold returns recomputed by a loop for 6 portfolio-years: max difference 4e-17.
  - Every RDM portfolio has 40 names in every cohort, at most 12 per sector, no firm (`permco`) twice, and every name carries `rdm`.
  - Timing, over all 6,880 RDM picks: every 10-K was public by its formation date and every fiscal year ended within 18 months; 92% of the dates are exact filing dates, 8% the assumed datadate + 6 months.
  - No SPACs (SIC 6770) reach the universe. Universe 621–1,105 stocks per cohort (median 813), of which 221–461 have `rdm` (median 348). Returns 1984-01 to 2025-12 (504 months).
  - The baselines match the `net_issuance` lab run (`DEF_EW` 0.83, `EW_UNIV` 0.48 design).
- **Pick (design sample, 1984–2009):** `DEF_RDM_EW` (Sharpe 0.79), ahead of `RDM_MOM_EW` 0.60, `RDM_EW` 0.54, `RDM_VW` 0.39. Universe `EW_UNIV` 0.48; `DEF_EW` 0.83; control `DEF_RD_EW` 0.86.
- **Holdout (2010–2025, looked at once):** `DEF_RDM_EW` Sharpe 1.15 vs `EW_UNIV` 0.74 (z 3.7), FF3 + UMD alpha 5.4%/yr (t 4.4) → **passes the success criteria.**
- **Named checks: `rdm` is not why it passes.**
  - Same R&D firms without `rdm` (`DEF_RD_EW`): Sharpe 1.10 in the holdout. `DEF_RDM_EW` − `DEF_RD_EW` z = +0.70 in the holdout, −1.33 in the design sample.
  - Against the lab's `DEF_EW` (1.13 in the holdout): z = +0.17 in the holdout, −0.54 in the design sample.
  - Over the full sample, `DEF_RDM_EW` 0.91 vs `DEF_RD_EW` 0.95 and `DEF_EW` 0.94.
  - Adding `rdm` replaces about a third of the names (64% overlap with `DEF_RD_EW`). Across the two samples the replacements did no better.
- **`rdm` alone:**

| | Design Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) | Holdout Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) |
|---|---|---|---|---|---|---|
| RDM_EW | 0.54 | 0.6 | 6.5% (2.8) | 0.93 | 1.6 | 5.0% (2.3) |
| RDM_MOM_EW | 0.60 | 1.4 | 5.7% (2.8) | 0.99 | 2.4 | 5.6% (3.0) |
| RDM_VW | 0.39 | −0.8 | 2.1% (1.1) | 0.99 | 1.5 | 5.4% (2.4) |
| EW_UNIV | 0.48 | | 0.7% (1.1) | 0.74 | | −0.4% (−0.6) |
| VW_MKT | 0.41 | | | 0.87 | | |

  - **The alpha is consistent; the Sharpe gain is small.** FF3 + UMD alpha is 5–6.5%/yr with t > 2 in both samples for the equal-weighted versions. Yet the Sharpe ratio is only modestly above the universe, because the portfolio is much riskier:
    - Volatility 19–23% vs 16%, beta 1.0–1.15.
    - Design max drawdown −53% (`RDM_EW`).
    - Worst years: 2008 (−37.2% vs −37.6% universe), 2002 (−24.7% vs −17.9%) and 2022 (−14.8% vs −13.6%).
  - `RDM_EW` beat the universe in 13 of 26 design years and 11 of 16 holdout years.
  - Value weighting only worked in the holdout.
- **Not value under another name:** the HML loading is about zero (0.00 design, 0.01 holdout; t ≈ 0), against the expectation stated in the plan.
  - What it does load on: small stocks within the universe (SMB 0.44 design, 0.36 holdout) and past losers (UMD −0.21, t −3.2 design).
  - The momentum filter removes the loser tilt (UMD −0.08 and −0.02) and gives the best standalone version.
  - The alpha is against FF3 + UMD only. The profitability and investment factors are not in the lab's model and may explain part of it (not tested here).
- **Sector concentration:** business equipment fills its 12-slot cap in every cohort (30% of names). Manufacturing (21%), health (20%) and durables (16%) make up most of the rest, with manufacturing and health at the cap in roughly 40% of cohorts.
- **Turnover:** `RDM_EW` replaces 36% of its names each year, less than `DEF_EW` (40%); `RDM_MOM_EW` 45%, `DEF_RDM_EW` 44% (costs not included).
- **Formation month:**
  - `RDM_EW` Sharpe 0.63–0.72 across the 12 months (December, 0.67, is mid-range); staggered 0.70 vs the universe's 0.60 (z 1.4).
  - `RDM_MOM_EW` staggered 0.73 (z 2.0); `DEF_RDM_EW` staggered 0.89 vs `DEF_EW` 0.91.
  - Not a December artifact.
- **Deflated Sharpe ratio (design):**
  - At 15 trials: 0.90 for `RDM_EW`, 0.94 for `RDM_MOM_EW`, 0.70 for `RDM_VW`, and 0.99 for the defensive composites (`DEF_EW`, `DEF_RD_EW`, `DEF_RDM_EW`).
  - At 30 trials: 0.84, 0.90 and 0.61 respectively.
  - The hurdle (0.29–0.34) is against zero excess return, not against the universe.
- **Overlap with the lab's strategies:** `RDM_EW` shares only 3.5% of names with `DEF_EW`, yet their excess returns correlate 0.75 (both long-only, beta near 1).
- **Bottom line:** in the lab's format, R&D-to-market is a real but noisy edge.
  - On its own it earns about 5–6%/yr of FF3 + UMD alpha in both samples. But it is a high-volatility, tech-heavy, smaller-cap portfolio whose Sharpe ratio beats the equal-weighted universe significantly only with the momentum filter, and only in the holdout.
  - It does not improve the defensive composite: the pick passes on the strength of the defensive screens, not `rdm`.
  - For ASAM, `DEF_EW` remains the better lab strategy. `RDM_MOM_EW` is the version worth keeping if the fund wants an R&D/innovation sleeve.
  - Next tests worth doing (new trials):
    - alpha against FF5 / q-factors;
    - a mix of `DEF_EW` with `RDM_MOM_EW`, given only 3.5% name overlap.

## Formulas (added 2026-11-23, after the run; documents the lab's code, changes nothing in the plan)
Notation: *i* = stock, *t* = month, *c* = the formation December, *r* = CRSP monthly total return (`mthret`, dividends included), ME = |price| × shares outstanding (`me`, $ thousands). The code that implements each formula is named in brackets; it is the lab's section A, identical in `rr_strategy_lab.ipynb` and `rdm_strategy_lab.ipynb`.

**Growth of $1** (the y-axis of `rdm_growth_of_1.png`)
```
W(1983-12) = 1
W(T) = (1 + R(1984-01)) × (1 + R(1984-02)) × … × (1 + R(T))
annual return = W(2025-12)^(12/504) − 1          (504 months = 42 years)
```

**Monthly return of a portfolio formed in December c**: buy-and-hold for k = 1…12 [`bh_returns`]
```
v(i,1) = w(i,0)
v(i,k) = w(i,0) × (1 + r(i,1)) × … × (1 + r(i,k−1))      while stock i is alive
R(k)   = Σ v(i,k) × r(i,k) / Σ v(i,k)                    (sum over stocks still alive)
```
A stock is alive while it has a return in every month so far. At its first missing return it drops out, and its value is spread across the rest pro rata.

**Starting weights**, normalized to sum to 1 in each cohort [`w_equal`, `w_value`]
```
EW:  w(i,0) = 1 / 40          (1 / N for EW_UNIV)
VW:  w(i,0) = ME(i,c) / Σ ME(j,c)
```

**Universe at December c** [`form_universe`]
```
ME, price and vol36 available   and   |price(i,c)| ≥ $5
and   ME(i,c) ≥ median ME of the NYSE stocks (primaryexch = 'N') that pass the screens above
```

**Percentile rank** within the cohort's universe [`rank`]
```
q(x_i) = rank of x_i among non-missing values / number of non-missing values      (ties averaged; 1 = best)
```
For lower-is-better inputs the ranking is reversed, so the lowest value gets 1.

**Selection** [`select`]: sort by score, highest first (ties to the lower PERMNO). Keep at most floor(0.30 × 40) = 12 names per Fama-French 12 sector (from SIC; "Other" counts as a sector). Take the first 40.

**Signals**
```
rdm(i,c)   = 1000 × xrd(i) / ME_firm(i,c)                   [rd_to_market_monthly.parquet; see progress.md]
             xrd ($ millions) from the latest 10-K public by c, fiscal year ended ≤ 18 months before c, xrd > 0;
             ME_firm = Σ ME over the firm's share classes (permco); primary share class only
mom(i,c)   = (1 + r(i,c−11)) × … × (1 + r(i,c−1)) − 1      [add_momentum; all 11 months required]
vol36(i,c) = standard deviation of r(i,c−35) … r(i,c)        [add_volatility; at least 24 months]
momentum filter: keep i only if q(mom) > 0.10                 [mom_ok]
```
`gprof`, `debt_at` and `ep` are taken from the panel as they are: gross profit ÷ total assets, total debt ÷ total assets, and earnings ÷ price.

**Scores** [`composite` = average of the ranks, blank if any input is missing]

| Strategy | Score | Weights |
|---|---|---|
| `RDM_EW` | q(rdm) | EW |
| `RDM_MOM_EW` | q(rdm), if q(mom) > 0.10 | EW |
| `RDM_VW` | q(rdm) | VW |
| `DEF_RDM_EW` | ⅕ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep) + q(rdm)], if q(mom) > 0.10 | EW |
| `DEF_RD_EW` (control) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 and rdm exists | EW |
| `DEF_EW` (lab) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 | EW |

**Benchmarks**
```
EW_UNIV: every stock in the universe, w(i,0) = 1/N, same 12-month buy-and-hold
VW_MKT:  R_M(t) = Σ ME(i,t−1) × r(i,t) / Σ ME(i,t−1)     [vw_market; all panel stocks, no screens, reweighted monthly]
```

**Evaluation (the results tables)** [`perf`, `jk_test`]. Excess return: e(t) = R(t) − rf(t). T = number of months.
```
ann ret = (Π (1 + R(t)))^(12/T) − 1
vol     = std(R) × √12
Sharpe  = mean(e) / std(e) × √12
alpha   : e(t) = a + b1·MktRF + b2·SMB + b3·HML + b4·UMD + u(t);  alpha %/yr = 1200·a;  t(alpha) with Newey-West, 6 lags
z vs B  = (s1 − s2) / √[(2 − 2ρ + ½(s1² + s2² − 2·s1·s2·ρ²)) / T]
          s1, s2 = monthly Sharpe ratios of the strategy and benchmark B; ρ = correlation of their excess returns (Jobson-Korkie)
```
Returns are before trading costs and taxes. The chart uses total returns; the risk-free rate is subtracted only for Sharpe, alpha and z.
