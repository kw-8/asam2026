# net_operating_assets — backtest

Signal: `noa` (net operating assets ÷ last year's total assets) from `data/net_operating_assets/noa_monthly.parquet`, built and validated in `progress.md` (Steps 0–10). This file records the backtest plan, fixed before any portfolio return on `noa` was computed, and then the results. Same format and engine as `signals/rd_to_market/backtest.md`.

## Strategy-lab version: `noa` in the `rr_strategy_lab.ipynb` engine (plan fixed 2026-11-23, before any return was computed)
- **Why:** the ASAM question in the lab's format: does a 40-stock, once-a-year, long-only portfolio that avoids bloated balance sheets (lowest `noa`) beat the lab's equal-weighted universe, and does adding `noa` to the lab's defensive composite help?
- **Engine:** the lab's section A code, unchanged (copied verbatim from `signals/rd_to_market/rdm_strategy_lab.ipynb`, itself a verbatim copy of `rr_strategy_lab.ipynb`) into `signals/net_operating_assets/noa_strategy_lab.ipynb`. Lab settings unchanged:
  - December formation, 12-month buy-and-hold, first cohort 1983-12.
  - Universe: NYSE-median size screen, price >= $5, `vol36` required.
  - 40 names, at most 30% per FF12 sector.
  - FF3 + UMD alpha (Newey-West 6).
  - Design sample = returns through 2009-12; holdout = 2010-01 on.
- **Signal:** `noa` = (`ceq` + `pstk` + `mib` + `dltt` + `dlc` − `che`) ÷ total assets of the previous fiscal year, from the latest 10-K public by the formation month-end (usable up to 18 months after fiscal year-end). Hirshleifer, Hou, Teoh & Zhang (2004) as published.
  - Merged by permno and month. **Lower = better** (HHTZ 2004; Hou, Xue & Zhang 2020).
  - **Financial firms (CRSP SIC 6000–6999 that month, the `financial` flag) are ineligible for the NOA strategies.** For banks and insurers, deposits and policy liabilities count as operating liabilities, so NOA is mechanically low and would fill the long portfolio with financials; Hou, Xue & Zhang exclude them. They stay in the universe, so `EW_UNIV` is the lab's universe.
  - Counted before any return was computed (December universe before the `vol36` screen): 664–1,386 stocks per cohort (median 903); 96.7% have `noa`, 17.5% are financial; eligible (non-financial with `noa`) 80%, 539–1,015 per cohort (median 729).
- **One class per firm:** the signal sits on each firm's primary share class only, so no `one_class()` filter is needed (as for `rdm`). Checked after the run.
- **Stated in advance (what could go against it):**
  - HHTZ and Stambaugh, Yu & Yuan (2012) find most of the NOA effect in the **short** leg (high-NOA firms underperform). A long-only portfolio of low-NOA firms gets only the long leg, which may be weak.
  - The paper was published in December 2004, so the holdout (2010–2025) is entirely post-publication and the design sample (1984–2009) is mostly in the paper's own sample. Expect the holdout to be weaker.
  - NOA overlaps with investment (asset growth) and accruals. FF3 + UMD does not control for investment (CMA) or profitability (RMW); an FF5 + UMD diagnostic is added below.
  - Low NOA also picks firms whose assets are funded by operating liabilities or that have negative equity (e.g. Boeing 2021–23), which are not all healthy. The momentum filter may help.
  - From fiscal 2019, Compustat puts operating-lease liabilities in debt (ASC 842), raising NOA for retailers and restaurants (known limitation, not fixed), so they should drop out of the low-NOA portfolio for accounting reasons after 2019.
- **New strategies (7 new trials, so `n_trials` = 10 + 7 = 17):**
  - `NOA_EW`: rank of `noa` (lower = better), equal weight.
  - `NOA_MOM_EW`: same, excluding the bottom 10% on 12−1 momentum (the lab's `mom_ok`).
  - `NOA_VW`: as `NOA_EW`, value weight.
  - `NOA_IND_EW`: `noa` ranked within the firm's FF12 sector in each cohort (lower = better), equal weight. Added because NOA levels differ a lot by industry (asset-heavy utilities and telecoms vs software) and the 2019 lease shift is concentrated in a few industries.
  - `DEF_NOA_EW`: the lab's `DEF_SPEC` composite (low `vol36`, high `gprof`, low `debt_at`, high `ep`) plus low `noa`, equal ranks, with `mom_ok`. Needs every input, so non-financial firms with `noa` only.
  - `DEF_NFIN_EW` (control, not a pick candidate): the `DEF_SPEC` composite among the same firms (non-financial, with `noa`), without `noa`. Separates "adding `noa`" from "non-financial firms with `noa` only".
  - `<PICK>_MI` (robustness, not a pick candidate): after the pick, the picked strategy rerun with `noa_mi` (minority-interest fix from fiscal 2009) in place of `noa`. Per `progress.md`, `noa` is the result; this only answers whether the 2009 accounting change matters.
  - Baselines in the same run (already counted in the lab's 10): `LOWVOL_EW`, `DEF_EW`, `DEF_IV`, `DEF_MV`.
- **Pick rule (design sample only):** the strategy with the highest design-sample Sharpe ratio among `NOA_EW`, `NOA_MOM_EW`, `NOA_VW`, `NOA_IND_EW` and `DEF_NOA_EW`. The holdout is then computed once and reported for every strategy.
- **What counts as success for the pick in the holdout:** Sharpe above `EW_UNIV` (Jobson-Korkie z > 0; significance at |z| > 2 noted, not required) and FF3 + UMD alpha > 0.
- **Named checks:**
  - `DEF_NOA_EW` vs `DEF_NFIN_EW`: does `noa` help, holding the firms fixed?
  - `DEF_NOA_EW` vs `DEF_EW`: is it better than the lab's strategy?
  - Both are z of the Sharpe difference, in the design sample and the holdout.
  - Deflated Sharpe ratio on the design sample at `n_trials` = 17 and, as a stricter check, 30.
  - Share of names replaced per year.
  - Sharpe by formation month (12 runs, MV excluded) and the staggered portfolio.
- **Diagnostics (not trials):**
  - Eligible firms per cohort.
  - Sector mix of `NOA_EW` and how often the cap binds.
  - Full FF3 + UMD loadings of the NOA strategies.
  - **FF5 + UMD** alpha and loadings (adds RMW and CMA, from `data/ff_monthly_kf.csv`, Ken French): is it investment (CMA) or profitability under another name?
  - Retail and restaurant names (FF12 `Shops`) in `NOA_EW` by cohort, 2015–2024: the 2019 lease shift should push them out.
- **Factors:** `data/ff_factors_monthly.csv` (Ken French FF3 + Momentum, 1979-01 to 2026-09), as in the R&D lab; `data/ff_monthly_kf.csv` (FF5 + Momentum, percent) for the FF5 diagnostic only.
- **Data:** `data/crsp_monthly_ratios_clean.parquet` (2,796,065 rows, 1980-01 to 2025-12), so returns run to 2025-12.

### Pick, recorded before the holdout was looked at (2026-11-23)
- **Pick:** `DEF_NOA_EW` (design Sharpe 0.82). The others: `NOA_IND_EW` 0.49, `NOA_MOM_EW` 0.40, `NOA_EW` 0.40, `NOA_VW` 0.34. For comparison, `EW_UNIV` 0.48, `DEF_EW` 0.83 and the control `DEF_NFIN_EW` 0.80.
- **Named checks, design:** `DEF_NOA_EW` vs `DEF_NFIN_EW` z = +0.40; vs `DEF_EW` z = −0.15.
- `DEF_NOA_EW_MI` (with `noa_mi`) is identical to `DEF_NOA_EW` in the design sample, as expected: the minority-interest fix only changes fiscal 2009 and later, which first enters the December 2009 cohort (holdout returns).

### Results (run 2026-11-23 on the workspace copy of your data; notebook executed end to end; executed copy with charts: `data/net_operating_assets/backtest/noa_strategy_lab_executed.ipynb`, not committed)
- **Checks before reading the numbers:**
  - `NOA_EW` and `NOA_MOM_EW` selection recomputed by a plain loop for all 43 cohorts: identical.
  - Buy-and-hold returns recomputed by a loop for 6 portfolio-years: max difference 8e-17.
  - Every NOA portfolio has 40 names in every cohort, at most 12 per sector, no firm (`permco`) twice, every name carries `noa`, and none is a financial firm or a SPAC.
  - Timing, over all 8,600 NOA picks: every 10-K was public by its formation date and every fiscal year ended within 18 months; 92.5% of the dates are exact filing dates, the rest the assumed datadate + 6 months.
  - Universe 621–1,105 stocks per cohort (median 813), of which 511–857 are eligible (non-financial with `noa`; median 670). Returns 1984-01 to 2025-12 (504 months).
  - The baselines match the R&D lab run (`DEF_EW` 0.83, `EW_UNIV` 0.48 design).
- **Pick (design sample, 1984–2009):** `DEF_NOA_EW` (Sharpe 0.82), ahead of `NOA_IND_EW` 0.49, `NOA_MOM_EW` 0.40, `NOA_EW` 0.40, `NOA_VW` 0.34. Universe `EW_UNIV` 0.48; `DEF_EW` 0.83; control `DEF_NFIN_EW` 0.80.
- **Holdout (2010–2025, looked at once):** `DEF_NOA_EW` Sharpe 1.05 vs `EW_UNIV` 0.74 (z 2.8), FF3 + UMD alpha 3.8%/yr (t 2.4) → **passes the success criteria.**
- **Named checks: `noa` is not why it passes — it slightly hurts.**
  - Same firms without `noa` (`DEF_NFIN_EW`): Sharpe 1.12 in the holdout. `DEF_NOA_EW` − `DEF_NFIN_EW` z = −1.39 in the holdout, +0.40 in the design sample.
  - Against the lab's `DEF_EW` (1.13 in the holdout): z = −1.23 in the holdout, −0.15 in the design sample.
  - Over the full sample, `DEF_NOA_EW` 0.91 vs `DEF_NFIN_EW` 0.92 and `DEF_EW` 0.94. Holdout alpha 3.8% vs 5.0% (`DEF_NFIN_EW`) and 5.1% (`DEF_EW`).
  - Adding `noa` replaces about a third of the names (69% overlap with `DEF_NFIN_EW`).
- **`noa` alone:**

| | Design Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) | Holdout Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) |
|---|---|---|---|---|---|---|
| NOA_EW | 0.40 | −0.8 | 3.2% (2.1) | 0.75 | 0.0 | 1.1% (0.5) |
| NOA_MOM_EW | 0.40 | −0.7 | 2.9% (2.0) | 0.75 | 0.0 | 0.4% (0.2) |
| NOA_VW | 0.34 | −1.2 | 2.5% (1.2) | 0.96 | 1.4 | 3.9% (1.5) |
| NOA_IND_EW | 0.49 | 0.1 | 3.0% (2.6) | 0.75 | 0.1 | 0.2% (0.1) |
| EW_UNIV | 0.48 | | 0.7% (1.1) | 0.74 | | −0.4% (−0.6) |
| VW_MKT | 0.41 | | | 0.87 | | |

  - **No Sharpe gain in either sample.** The lowest-NOA portfolio trails the universe in the design sample and ties it in the holdout. The FF3 + UMD alpha that existed in the design sample (about 3%/yr, t ≈ 2) is gone in the holdout (0.2–1.1%, t < 0.5) for the equal-weighted versions. Ranking within industry does not change that.
  - **Much riskier than the universe:** volatility 19–22% vs 16%, beta 1.02–1.12, design max drawdown −60% (`NOA_EW`). Worst years: 2008 (−35.0% vs −37.6% universe), 2022 (−30.5% vs −13.6%) and 2002 (−30.4% vs −17.9%).
  - `NOA_EW` beat the universe in 11 of 26 design years and 11 of 16 holdout years; `DEF_NOA_EW` in 19 of 26 and 13 of 16.
  - Value weighting only worked in the holdout (0.96, z 1.4, alpha not significant) — the same pattern as `RDM_VW`; not a pick candidate result anyone should lean on.
- **What "lean" means here: small, asset-light, unprofitable growth firms.** The median `noa` in `NOA_EW` is 0.14 against 0.66 for the eligible universe, and 23% of its picks have negative NOA (cash larger than debt + equity, or negative equity).
  - FF3 + UMD loadings (design): SMB +0.52 (t 3.8), HML −0.40 (t −6.5): small and growth, not value.
  - FF5 + UMD (diagnostic): profitability RMW −0.41 (t −4.2) design and −0.43 (t −3.2) holdout — the low-NOA firms are *less* profitable than average. Investment CMA +0.11 (t 0.7) design and −0.40 (t −3.1) holdout: **not** conservative investment in disguise; if anything the opposite in the holdout. FF5 + UMD alpha of `NOA_EW`: 5.3%/yr (t 3.1) design, 2.4% (t 1.1) holdout.
  - The defensive composite adds the profitability that low NOA lacks: `DEF_NOA_EW` loads RMW +0.42/+0.47.
- **Sector concentration:** business equipment is 27% of `NOA_EW` names and at its 12-slot cap in 79% of cohorts; then "Other" 23%, health 15%, manufacturing 10%, shops 10%. Holdout cohorts: business equipment 30%, other 26%, health 21%, shops 12%.
- **2019 lease shift (diagnostic):** the expected drop of retailers and restaurants from `NOA_EW` after 2019 did not show: shops names were 4–5 per cohort in 2017–2020 and 7–8 in 2021–2024, against a steady 11–13% of eligible firms. The lowest-NOA retailers are mostly negative-NOA firms (cash-rich or negative equity), which the lease liabilities do not push out of the bottom of the ranking. The known limitation did not drive these results.
- **`noa_mi` (the 2009 minority-interest fix):** `DEF_NOA_EW_MI` holds 99.4% of the same names; holdout Sharpe 1.05 vs 1.05 (z 0.4), alpha 3.8% vs 3.8%. The accounting change does not matter here.
- **Turnover:** `NOA_EW` replaces 44% of its names each year, `NOA_MOM_EW` 52%, `NOA_IND_EW` 50%, `DEF_NOA_EW` 44%, vs `DEF_EW` 40% (costs not included).
- **Formation month:**
  - `NOA_EW` Sharpe 0.49–0.58 across the 12 months, below `EW_UNIV` (0.58–0.61) in every month; staggered 0.54 vs 0.60 (z −0.75).
  - `DEF_NOA_EW` staggered 0.88 vs `DEF_EW` 0.91 and `DEF_NFIN_EW` 0.88.
  - Not a December artifact.
- **Deflated Sharpe ratio (design):**
  - At 17 trials: 0.52 for `NOA_EW`, 0.52 for `NOA_MOM_EW`, 0.39 for `NOA_VW`, 0.69 for `NOA_IND_EW`, and 0.97–0.98 for the defensive composites (`DEF_EW`, `DEF_NFIN_EW`, `DEF_NOA_EW`).
  - At 30 trials: 0.41, 0.42, 0.30, 0.59 and 0.95–0.96.
  - The hurdle (0.39 at 17, 0.44 at 30) is against zero excess return, not against the universe.
- **Overlap with the lab's strategies:** `NOA_EW` shares only 5% of names with `DEF_EW`, yet their excess returns correlate 0.70 (both long-only, beta near 1).
- **Bottom line:** in the lab's format, buying the leanest balance sheets is not a useful long-only strategy.
  - The low-NOA portfolio is a high-volatility, tech- and health-heavy tilt toward small, unprofitable growth firms. Its design-sample alpha (about 3%/yr) vanished after publication, and its Sharpe ratio never beat the equal-weighted universe.
  - Consistent with the literature saying the effect sits in the short leg (high-NOA firms underperform), which a long-only fund cannot hold.
  - Adding `noa` to the defensive composite does not help (z −1.4 against the same firms without it in the holdout). The pick passes on the strength of the defensive screens, not `noa`.
  - For ASAM, `DEF_EW` remains the better lab strategy.
  - Next tests worth doing (new trials, plan them first): `noa` as an **exclusion screen** — `DEF_EW` without the highest-NOA decile or quintile — which is the long-only way to use a short-leg signal ("avoiding stocks in a broadly diversified fund is almost like shorting them", Ch. 22); and the full long-short spread (lowest vs highest NOA quintile) to see whether the short side still works after 2004.

## Formulas (added 2026-11-23, after the run; documents the lab's code, changes nothing in the plan)
Everything except the signal and the scores is identical to `signals/rd_to_market/backtest.md`, "Formulas" (growth of $1, buy-and-hold returns, weights, universe, percentile rank, selection, `mom`, `vol36`, the momentum filter, benchmarks and evaluation): the lab's section A, unchanged.

**Signal**
```
noa(i,c)    = (ceq + pstk + mib + dltt + dlc − che)(i) / at_prev(i)      [noa_monthly.parquet; see progress.md]
              balance sheet from the latest 10-K public by c, fiscal year ended ≤ 18 months before c;
              at_prev = total assets of the previous fiscal year (10–14 months earlier); primary share class only
noa_nf(i,c) = noa(i,c) if the firm is not financial (CRSP SIC 6000–6999) that month, else blank
q_ind(x_i)  = percentile rank of x_i within its cohort and FF12 sector      (lower noa ranked best)
```

**Scores** [`composite` = average of the ranks, blank if any input is missing; q(−x) = lower is better]

| Strategy | Score | Weights |
|---|---|---|
| `NOA_EW` | q(−noa_nf) | EW |
| `NOA_MOM_EW` | q(−noa_nf), if q(mom) > 0.10 | EW |
| `NOA_VW` | q(−noa_nf) | VW |
| `NOA_IND_EW` | q_ind(−noa_nf) | EW |
| `DEF_NOA_EW` | ⅕ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep) + q(−noa_nf)], if q(mom) > 0.10 | EW |
| `DEF_NFIN_EW` (control) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 and noa_nf exists | EW |
| `DEF_NOA_EW_MI` (robustness) | as `DEF_NOA_EW` with `noa_mi` in place of `noa` | EW |
| `DEF_EW` (lab) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 | EW |

**FF5 + UMD diagnostic:** e(t) = a + b1·MktRF + b2·SMB + b3·HML + b4·RMW + b5·CMA + b6·UMD + u(t), Ken French FF5 and momentum (`data/ff_monthly_kf.csv`), Newey-West 6 lags. Returns are before trading costs and taxes.

## Files
- GitHub: `signals/net_operating_assets/backtest.md` and `noa_strategy_lab.ipynb` (outputs cleared), together with the 8 files listed in `progress.md` (Step 10).
- Not committed (licensed data): `data/net_operating_assets/backtest/noa_strategy_lab_executed.ipynb` (executed copy with tables and charts) and `noa_growth_of_1.png`.
- `public_data/factor_catalog.csv`: `test_results` for `net_operating_assets` not filled yet; fill it once the team agrees on the wording.
