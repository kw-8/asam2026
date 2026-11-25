# EPU exposure (policy-uncertainty beta) - progress

## Data
- Baker, Bloom & Davis (2016), "Measuring Economic Policy Uncertainty", QJE 131(4), 1593-1636; www.PolicyUncertainty.com (free, attribution required).
- `signals/epu/build_epu.py` -> `public_data/epu_monthly.csv`: epu_news (1900-), epu_3comp and 11 category indices (1985-), month-end dates, through 2026-10.
- EPU is one number per month for the whole US: it cannot rank stocks. A firm's exposure is its return sensitivity to EPU shocks.

## Definition (pre-registered 2026-11-24, before any return test)
- Shock: u_s = ln EPU_s - ln EPU_{s-1} (monthly log change). Log change because the index is persistent and its level variance grows with its level (2025-04: 725).
- Exposure of stock i at month-end t: OLS over months s = t-60 .. t-1 (>= 36 with a return):
  r_{i,s} - rf_s = a_i + b_i mktrf_s + beta_i u_s + e_{i,s}.
  beta_i is the signal; b_i (market beta) is kept as a check column.
- Timing: month t's EPU is published early in month t+1, so the window stops at t-1 (no look-ahead at formation month-end t). published_date = t; date_source = assumed (index posted after month-end; vintage as downloaded 2026-11-24, later revisions folded in).
- Signals (one per index):
  1. epu_beta - epu_news (primary).
  2. epu_trade_beta - epu_trade_policy.
  3. epu_natsec_beta - epu_national_security.
  Dropped before testing: epu_sovereign_debt_fx (38 zero months since 1985, sd of log change 1.68: too noisy); epu_3comp (its tax-expiration and forecaster-disagreement parts are not known in real time).
- Direction (stated in advance): low (more negative) beta = higher return, higher_better = False. Stocks that rise when uncertainty jumps are a hedge and should earn less (Brogaard & Detzel 2015, Management Science; Bali, Brown & Tang 2017, JFE - from memory, not checked against the papers).
- Sample: lab default universe and evaluation (annual December formation, NYSE-median size, price >= $5). Category indices start 1985-01, so the first cohort with 36 shocks is Dec 1988: design hold years 1989-2005, holdout 2006-2025. Holdout read once, after the design verdict.
- Tests per signal: coverage, p.258 screen, low-minus-high quintile ZIP, Fama-MacBeth alone and with controls (incl. vol36 and market beta b_i).
- Trials counted for DSR: the 3 signals + variants (VW legs, terciles, 36-month window for epu_beta).

## Log
- 2026-11-24: data pulled, definition fixed.
- 2026-11-24: built `data/epu/epu_beta_monthly.parquet` (build_epu_beta.py; 90 random betas match direct OLS to 1e-8). Excess return done in numpy: pandas `W.sub(rf, axis=0)` returned NaN for 928,476 of 2,791,759 cells.
- 2026-11-24: test_epu.py -> test_results.md. No signal. Low-minus-high EW quintile ZIP, mean %/yr design / holdout: epu_beta -0.02 / +0.75, epu_trade_beta -3.93 / +0.11, epu_natsec_beta -0.55 / -1.61; no |t| > 1.7. FM slopes with controls |t| < 1.5. FULL DSR 0.21 over 8 trials (best epu_beta36, Sharpe 0.19). Design screen "pass" is rule A only; all three carry the rule-B flag in at least one period.
