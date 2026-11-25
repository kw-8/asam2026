# shareholder_yield — backtest

Signal: `net_payout_yield` (dividends + buybacks − stock issued over the last fiscal year ÷ the firm's market value) from `data/shareholder_yield/shareholder_yield_monthly.parquet`, built and validated in `progress.md` (Steps 0–10). This file records the backtest plan, fixed before any portfolio return on `net_payout_yield` was computed, and then the results. Same format and engine as `signals/net_operating_assets/backtest.md`, `signals/rd_to_market/backtest.md` and the strategy-lab section of `signals/issuance_insider/backtest.md`.

## Strategy-lab version: `net_payout_yield` in the `rr_strategy_lab.ipynb` engine (plan fixed 2026-11-24, before any return was computed)
- **Why:** the ASAM question in the lab's format: does a 40-stock, once-a-year, long-only portfolio of the highest net payout yields beat the lab's equal-weighted universe, does it lift the Sharpe ratio, and does adding `net_payout_yield` to the lab's defensive composite help?
- **Engine:** the lab's section A code, unchanged (copied verbatim from `signals/net_operating_assets/noa_strategy_lab.ipynb`, itself a verbatim copy of `rr_strategy_lab.ipynb`) into `signals/shareholder_yield/sy_strategy_lab.ipynb`. Lab settings unchanged:
  - December formation, 12-month buy-and-hold, first cohort 1983-12.
  - Universe: NYSE-median size screen, price >= $5, `vol36` required.
  - 40 names, at most 30% per FF12 sector.
  - FF3 + UMD alpha (Newey-West 6).
  - Design sample = returns through 2009-12; holdout = 2010-01 on.
- **Signal:** `net_payout_yield` = 1000 × (`dvc` + `prstkc` + preferred decrease − (`sstk` − preferred increase)) ÷ firm market value ($ thousands), from the latest 10-K public by the formation month-end (usable up to 18 months after fiscal year-end); Boudoukh, Michaely, Richardson & Roberts (2007) as published, blank buybacks/issuance = 0 (OSAP's rule). Merged by permno and month. **Higher = better.**
- **Eligibility for the payout strategies (as in the paper and OSAP's replication):**
  - **Financial firms** (CRSP SIC 6000–6999 that month, the `financial` flag) are ineligible: banks' and insurers' dividends, buybacks and stock sales are largely set by capital regulation, and OSAP's replication of the paper drops them.
  - **Firms with common equity ≤ 0** (`ceq_nonpos`) are ineligible: the paper requires positive book equity.
  - Both stay in the universe, so `EW_UNIV` is the lab's universe.
  - Counted before any return was computed (December universe 1983–2024 before the `vol36` screen): 664–1,386 stocks per cohort (median 900); 97.6% have `net_payout_yield`, 17.5% are financial, 3.0% have common equity ≤ 0; eligible 77.7%, 534–1,001 per cohort (median 699).
- **One class per firm:** the signal sits on each firm's primary share class only, so no `one_class()` filter is needed (as for `rdm` and `noa`). Checked after the run.
- **Stated in advance (what could go against it):**
  - **It is a value signal.** Payout per dollar of price is cheapness, and value had a long drought from about 2007 to 2020, most of the holdout (2010–2025). The lab's defensive composite already holds `ep`, so the composite may gain little.
  - **In-sample design period.** The paper's cross-section is July 1984 – Dec 2003, inside the design sample (1984–2009); the paper was published in 2007, so the holdout is entirely post-publication. Expect the holdout to be weaker.
  - **Value traps.** A price collapse raises the yield before dividends are cut, so the top 40 can hold distressed firms. The momentum filter (`SY_MOM_EW`) is the guard.
  - **The issuance part works mostly on the short side.** Your monthly `net_issuance` study found most of the spread in heavy issuers (Q1), and Q5's FF5 + UMD alpha was small. A long-only top-yield portfolio holds only the payers.
  - **Preferred-stock conversions** (IPO years, reorganizations) count as payouts in the paper's formula and made up over half the yield for 10% of the top quintile (firms ≥ $250M, Decembers) in Step 9; the `_XPREF` rerun measures whether that matters.
  - **Sector concentration.** Payout norms differ by industry (utilities, energy, tobacco and REIT-like firms pay out heavily); the sector cap may bind. `SY_IND_EW` ranks within sector.
  - **Factor model.** FF3 + UMD leaves out profitability (RMW) and investment (CMA); firms that pay out tend to be profitable and invest little, so an FF5 + UMD diagnostic is added.
- **New strategies (8 new trials, so `n_trials` = 10 + 8 = 18):**
  - `SY_EW`: rank of `net_payout_yield` (higher = better), equal weight.
  - `SY_MOM_EW`: same, excluding the bottom 10% on 12−1 momentum (the lab's `mom_ok`).
  - `SY_VW`: as `SY_EW`, value weight.
  - `SY_IND_EW`: `net_payout_yield` ranked within the firm's FF12 sector in each cohort, equal weight.
  - `DEF_SY_EW`: the lab's `DEF_SPEC` composite (low `vol36`, high `gprof`, low `debt_at`, high `ep`) plus high `net_payout_yield`, equal ranks, with `mom_ok`. Eligible firms only.
  - `DEF_SYELIG_EW` (control, not a pick candidate): the `DEF_SPEC` composite among the same eligible firms, without the payout yield. Separates "adding the payout yield" from "eligible firms only".
  - After the pick (not pick candidates): `<PICK>_GROSS`, the picked strategy rerun with `payout_yield` (the named check fixed in Step 1: gross payout, ignores issuance); and `<PICK>_XPREF`, rerun with `net_payout_yield_xpref` (robustness from Step 9: no preferred-stock adjustment). Per `progress.md`, `net_payout_yield` is the result; these only answer "does issuance matter?" and "do preferred conversions matter?".
  - Baselines in the same run (already counted in the lab's 10): `LOWVOL_EW`, `DEF_EW`, `DEF_IV`, `DEF_MV`.
- **Pick rule (design sample only):** the strategy with the highest design-sample Sharpe ratio among `SY_EW`, `SY_MOM_EW`, `SY_VW`, `SY_IND_EW` and `DEF_SY_EW`. The holdout is then computed once and reported for every strategy.
- **What counts as success for the pick in the holdout:** Sharpe above `EW_UNIV` (Jobson-Korkie z > 0; significance at |z| > 2 noted, not required) and FF3 + UMD alpha > 0.
- **Named checks:**
  - `DEF_SY_EW` vs `DEF_SYELIG_EW`: does the payout yield help, holding the firms fixed?
  - `DEF_SY_EW` vs `DEF_EW`: is it better than the lab's strategy?
  - `<PICK>` vs `<PICK>_GROSS` and vs `<PICK>_XPREF`.
  - All as z of the Sharpe difference, in the design sample and the holdout.
  - Deflated Sharpe ratio on the design sample at `n_trials` = 18 and, as a stricter check, 30.
  - Share of names replaced per year.
  - Sharpe by formation month (12 runs, MV excluded) and the staggered portfolio.
- **Diagnostics (not trials):**
  - Eligible firms per cohort.
  - Sector mix of `SY_EW` and how often the cap binds.
  - What `SY_EW` holds: share of dividend payers, buyers-back and net issuers, share with a zero-filled item, share where the preferred-stock change is over half the yield, median yield vs the eligible universe.
  - Full FF3 + UMD loadings of the payout strategies, and **FF5 + UMD** (adds RMW and CMA, from `data/ff_monthly_kf.csv`): is it value, profitability or investment under another name?
  - Annualized Sharpe ratio of each strategy next to `VW_MKT` (your earlier question: can a long-only signal reach about 0.9?).
- **Factors:** `data/ff_factors_monthly.csv` (Ken French FF3 + Momentum, as in the other lab runs); `data/ff_monthly_kf.csv` (FF5 + Momentum, percent) for the FF5 diagnostic only.
- **Data:** the panel's lab columns (`permno, date, primaryexch, siccd, mthret, prc, me, me_lag, gprof, debt_at, ep`; all 2,796,065 rows, 1980-01 to 2025-12) — for the workspace run, read from the same columns extracted to `data/shareholder_yield/backtest/lab_panel_*.parquet` (the full panel file is too large to copy); the notebook itself reads `data/crsp_monthly_ratios_clean.parquet`.

### Pick, recorded before the holdout was looked at (2026-11-24)
- **Pick:** `DEF_SY_EW` (design Sharpe 0.75). The others: `SY_MOM_EW` 0.68, `SY_IND_EW` 0.60, `SY_EW` 0.60, `SY_VW` 0.55. For comparison, `EW_UNIV` 0.48, `VW_MKT` 0.41, `DEF_EW` 0.83 and the control `DEF_SYELIG_EW` 0.80.
- **Named checks, design:** `DEF_SY_EW` vs `DEF_SYELIG_EW` z = −1.01; vs `DEF_EW` z = −1.60. Reruns of the pick: `DEF_SY_EW_GROSS` 0.78 (z +1.46 vs the pick; 94% of names shared), `DEF_SY_EW_XPREF` 0.75 (z −0.30; 98% shared).
- Design-sample run only (notebook executed through the pick cell; no holdout return computed yet). Built-in checks passed first: `SY_EW` selection = a plain loop in every cohort; buy-and-hold loop vs engine max difference 6e-17; 40 names, ≤ 12 per sector, no firm twice, every pick eligible; 0 picks with a 10-K not yet public or older than 18 months; 89.3% exact dates.

### Results (run 2026-11-24 on the workspace copy of your data; notebook executed end to end after the pick was recorded; executed copy with charts: `data/shareholder_yield/backtest/sy_strategy_lab_executed.ipynb`, not committed)
- **Checks before reading the numbers:**
  - `SY_EW` selection recomputed by a plain loop for all 42 cohorts: identical.
  - Buy-and-hold returns recomputed by a loop for 6 portfolio-years: max difference 6e-17.
  - Every payout portfolio has 40 names in every cohort, at most 12 per sector, no firm (`permco`) twice; every pick carries the signal, none is financial or has common equity ≤ 0.
  - Timing, over all 8,600 `SY_EW` picks: every 10-K was public by its formation date and every fiscal year ended within 18 months; 89.3% exact filing dates.
  - Universe 621–1,105 stocks per cohort (median 813), of which 504–834 eligible (median 649). Returns 1984-01 to 2025-12 (504 months).
  - The baselines match the NOA and R&D lab runs (`DEF_EW` 0.83 design / 1.13 holdout, `EW_UNIV` 0.48 / 0.74). Headline Sharpe ratios and the pick's alpha recomputed independently from the monthly returns: identical.
- **Pick (design sample, 1984–2009):** `DEF_SY_EW` (Sharpe 0.75), ahead of `SY_MOM_EW` 0.68, `SY_IND_EW` 0.60, `SY_EW` 0.60, `SY_VW` 0.55. Universe `EW_UNIV` 0.48; market `VW_MKT` 0.41; `DEF_EW` 0.83; control `DEF_SYELIG_EW` 0.80.
- **Holdout (2010–2025, looked at once):** `DEF_SY_EW` Sharpe 1.05 vs `EW_UNIV` 0.74 (z 3.0), FF3 + UMD alpha 4.9%/yr (t 3.0) → **passes the success criteria.**
- **Named checks: the payout yield is not why it passes — it slightly hurts.**
  - Same firms without the yield (`DEF_SYELIG_EW`): Sharpe 1.12 in the holdout. `DEF_SY_EW` − `DEF_SYELIG_EW` z = −0.93 in the holdout, −1.01 in the design sample.
  - Against the lab's `DEF_EW` (1.13 in the holdout): z = −0.93 in the holdout, −1.60 in the design sample.
  - Full sample: `DEF_SY_EW` 0.87 vs `DEF_SYELIG_EW` 0.92 and `DEF_EW` 0.94. Holdout alpha 4.9% vs 5.0% (`DEF_SYELIG_EW`) and 5.1% (`DEF_EW`).
  - Adding the yield replaces about a third of the names (69% overlap with `DEF_SYELIG_EW`, 64% with `DEF_EW`).
- **`net_payout_yield` alone:**

| | Design Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) | Holdout Sharpe | z vs EW_UNIV | FF3+UMD alpha (t) | Full Sharpe |
|---|---|---|---|---|---|---|---|
| SY_EW | 0.60 | 1.3 | 3.4% (2.2) | 0.77 | 0.3 | 3.0% (1.7) | 0.66 |
| SY_MOM_EW | 0.68 | 2.1 | 3.3% (2.2) | 0.79 | 0.5 | 2.3% (1.4) | 0.73 |
| SY_VW | 0.55 | 0.6 | 2.7% (1.6) | 0.91 | 1.2 | 5.4% (2.3) | 0.68 |
| SY_IND_EW | 0.60 | 1.5 | 3.7% (2.7) | 0.80 | 0.7 | 2.3% (1.5) | 0.68 |
| EW_UNIV | 0.48 | | 0.7% (1.1) | 0.74 | | −0.4% (−0.6) | 0.58 |
| VW_MKT | 0.41 | | | 0.87 | | | 0.58 |

  - **A real but modest edge, smaller after publication.** All four versions beat the universe in the design sample (z 0.6–2.1; FF3 + UMD alpha about 3%/yr, t ≈ 2). In the holdout the edge over the universe shrinks to z 0.3–1.2 and is no longer significant, except that value weighting did better there (0.91, alpha 5.4%, t 2.3) — the same "VW only works in the holdout" pattern as `RDM_VW` and `NOA_VW`; not a pick candidate result anyone should lean on.
  - **Explained by known factors (FF5 + UMD, diagnostic).** Design: `SY_EW` loads on value (HML +0.22, t 3.2), profitability (RMW +0.40, t 6.3) and conservative investment (CMA +0.39, t 5.1), and against momentum (UMD −0.22, t −8.3); FF5 + UMD alpha 0.3%/yr (t 0.3). Holdout: alpha 2.7% (t 1.6), RMW drops to +0.09, CMA +0.26. The same picture as your monthly `net_issuance` study: firms that pay out are cheap, profitable and investing little, and those factors account for the return.
  - **Riskier than the lab's strategies, not safer:** volatility 18–19% vs 16% for the universe and 14% for `DEF_EW`; beta about 1.0; max drawdown −52% design (2008) and −36% holdout. Worst years: 2008 (−34.9% vs −37.6% universe, −24.0% `DEF_EW`), 2002 (−12.3%), 1990 (−10.8%), 2018 (−8.9%). Worst against the universe: 2020 (−15.4 points), 1998 (−9.6), 2005 (−7.7); best: 2009 (+30.1), 2001 (+21.3), 2022 (+16.2) — a value tilt.
  - `SY_EW` beat the universe in 15 of 26 design years and 8 of 16 holdout years; `SY_MOM_EW` 19 and 9; `DEF_SY_EW` 15 and 11.
  - By decade (Sharpe, `SY_EW` / `EW_UNIV` / `VW_MKT`): 1984–99 0.76 / 0.68 / 0.77; 2000–09 0.41 / 0.21 / −0.11; 2010–19 0.95 / 0.95 / 1.01; 2020–25 0.60 / 0.51 / 0.71. The edge came mostly in 2000–09.
- **What the top-40 holds:** median net yield 13.1% vs 2.0% for eligible firms (lowest pick 5.3%; no net issuer ever). 82% pay dividends, 93% buy back stock, 71% also issue some stock (employee plans). 5.6% have a zero-filled item; in 9.6% the preferred-stock change is over half the yield. Picks are as large as the universe (median $4.7bn vs $4.9bn) and as volatile, cheaper (`ep` 0.065 vs 0.051), more indebted (`debt_at` 0.31 vs 0.24) and with weak momentum (median 12−1 return 4% vs 14%).
- **Sector concentration:** utilities 14% of `SY_EW` names on average (20% in design cohorts, at the 12-name cap in 23% of cohorts); in the holdout the mix moved to retail/shops 17%, business equipment 16% and "other" 15% — the shift from dividends to buybacks.
- **`_GROSS` (named check) and `_XPREF` (robustness):** gross payout yield (ignoring stock issued) did slightly better than the net yield: `DEF_SY_EW_GROSS` 1.07 vs 1.05 in the holdout (z +1.17), 0.78 vs 0.75 in the design (z +1.46), 94% of names shared — not significant. Without the preferred-stock adjustment: 1.05 vs 1.05 (z −0.50), 98% shared — **preferred conversions do not matter here.** Per the plan, `net_payout_yield` remains the result.
- **Turnover:** the payout strategies replace 76–78% of their names each year, vs 40% for `DEF_EW` and 46% for `DEF_SY_EW` (costs not included) — the yield moves with every new 10-K and with the price.
- **Formation month:**
  - `SY_EW` Sharpe 0.58–0.67 across the 12 months, above `EW_UNIV` (0.58–0.61) in 11 of 12; staggered 0.65 vs 0.60 (z 0.8).
  - `DEF_SY_EW` staggered 0.84 vs `DEF_EW` 0.91 and `DEF_SYELIG_EW` 0.88.
  - Not a December artifact.
- **Deflated Sharpe ratio (design):** at 18 trials 0.95–0.99 for the payout strategies (0.97 `SY_EW`, 0.995 `DEF_SY_EW`); at 30 trials 0.94–0.99. The hurdle (0.20 at 18, 0.22 at 30) is against zero excess return, not against the universe, so it does not separate the strategies.
- **Overlap with the lab's strategies:** `SY_EW` shares only 3% of names with `DEF_EW`, yet their excess returns correlate 0.87 (design) and 0.84 (holdout).
- **Your Sharpe question (can a long-only signal reach about 0.9?):** over 1984–2025, `SY_EW` 0.66 and `SY_VW` 0.68 vs 0.58 for the market — better than the market, well short of 0.9. Only the defensive composites get there (`DEF_EW` 0.94, `DEF_SY_EW` 0.87), and the yield does not add to them. The 2010–2025 numbers (`SY_VW` 0.91, market 0.87) reflect an unusually strong market, not the signal.
- **Bottom line:** shareholder yield is a real, modest long-only tilt, mostly value + profitability + low investment.
  - Alone, it beat the equal-weighted universe by about 3%/yr in the design sample (t ≈ 2); after publication the edge is smaller and not significant, and FF5 + UMD explains nearly all of it.
  - It is not a defensive strategy: as volatile as the market, deeper drawdowns than the lab's composite, and 3× the turnover.
  - Adding it to the defensive composite does not help (z −0.9 against the same firms without it in the holdout, −1.0 in the design sample). The pick passes on the strength of the defensive screens, as with `noa` and `net_issuance`.
  - For ASAM, `DEF_EW` remains the better lab strategy. Ideas worth planning as new trials: shareholder yield as a **screen** inside `DEF_EW` (drop net issuers, the bottom quintile), which uses the issuance side's short-leg evidence without displacing the defensive names; and the gross yield, which did a little better in both samples.

## Formulas (added 2026-11-24, after the run; documents the lab's code, changes nothing in the plan)
Everything except the signal and the scores is identical to `signals/rd_to_market/backtest.md`, "Formulas" (growth of $1, buy-and-hold returns, weights, universe, percentile rank, selection, `mom`, `vol36`, the momentum filter, benchmarks and evaluation): the lab's section A, unchanged.

**Signal**
```
sy(i,c)     = net_payout_yield(i,c)       [shareholder_yield_monthly.parquet; see progress.md]
            = 1000 x (dvc + prstkc + max(pstkrv_prev - pstkrv, 0) - (sstk - max(pstkrv - pstkrv_prev, 0))) / me_firm(i,c)
              payouts from the latest 10-K public by c, fiscal year ended <= 18 months before c; blank prstkc/sstk = 0;
              me_firm = market value of all the firm's share classes in the panel at c ($ thousands); primary share class only
sy_el(i,c)  = sy(i,c) if the firm is not financial (CRSP SIC 6000-6999) and its common equity > 0, else blank
q_ind(x_i)  = percentile rank of x_i within its cohort and FF12 sector      (higher yield ranked best)
```

**Scores** [`composite` = average of the ranks, blank if any input is missing; q(−x) = lower is better]

| Strategy | Score | Weights |
|---|---|---|
| `SY_EW` | q(sy_el) | EW |
| `SY_MOM_EW` | q(sy_el), if q(mom) > 0.10 | EW |
| `SY_VW` | q(sy_el) | VW |
| `SY_IND_EW` | q_ind(sy_el) | EW |
| `DEF_SY_EW` | ⅕ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep) + q(sy_el)], if q(mom) > 0.10 | EW |
| `DEF_SYELIG_EW` (control) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 and sy_el exists | EW |
| `DEF_SY_EW_GROSS` (named check) | as `DEF_SY_EW` with `payout_yield` in place of `net_payout_yield` | EW |
| `DEF_SY_EW_XPREF` (robustness) | as `DEF_SY_EW` with `net_payout_yield_xpref` in place of `net_payout_yield` | EW |
| `DEF_EW` (lab) | ¼ [q(−vol36) + q(gprof) + q(−debt_at) + q(ep)], if q(mom) > 0.10 | EW |

**FF5 + UMD diagnostic:** e(t) = a + b1·MktRF + b2·SMB + b3·HML + b4·RMW + b5·CMA + b6·UMD + u(t), Ken French FF5 and momentum (`data/ff_monthly_kf.csv`), Newey-West 6 lags. Returns are before trading costs and taxes.

## Files
- GitHub: `signals/shareholder_yield/backtest.md` and `sy_strategy_lab.ipynb` (outputs cleared).
- Not committed (licensed data): `data/shareholder_yield/backtest/sy_strategy_lab_executed.ipynb` (executed copy with tables and charts), `sy_growth_of_1.png`, `sy_lab_monthly_returns.csv`, and the panel extract `lab_panel_*.parquet` with `extract_lab_panel.py` (only needed to copy the panel to Claude's workspace; can be deleted).
- `public_data/factor_catalog.csv`: `test_results` for `shareholder_yield` not filled yet; fill it once the team agrees on the wording.
