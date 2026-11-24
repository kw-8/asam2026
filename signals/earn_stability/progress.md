# earn_stability — progress

Started: 2026-11-24 (overnight, assistant researcher, added by the coordinator). Built from the panel only; no new pull.

## Definition (coordinator's spec)
- `roa_sd5` = standard deviation (ddof=1) of the panel's `roa` at months t, t-3, …, t-57 (20 quarterly samples over the trailing 60 months; the ratios update quarterly), at least 12 non-missing. Lower = more stable → `higher_better = False`.
- `gprof_sd5` = the same on `gprof`, as a check.
- Note: the panel's `roa` is a trailing-12-month ratio (WRDS Financial Ratios Suite), so consecutive quarterly samples overlap by 9 months; the std measures variation of TTM ROA, smoother than quarterly-earnings volatility.
- Timing: panel ratios assumed public by the month-end (catalog: "panel assumed on time", ~2-month lag after quarter end). `date_source = assumed`.
- Build: `signals/earn_stability/build_earn_stability.py` → `data/earn_stability/earn_stability_monthly.parquet` (1,804,842 permno-months, 15,403 permnos, 1982-10 to 2025-12).
- Checks: 0 duplicate permno-months; AAPL Dec 2019 by hand (20 quarterly roa values) 0.04326 = file 0.04326; roa_sd5 median 0.038, p99 0.34; Spearman with gprof_sd5 0.83.

## Pre-registration
Hypothesis: stable earnings (low roa_sd5) → higher 12-month returns (quality / low-risk anomaly). Lab default sample: cohorts Dec 1985-Dec 2024, design hold years 1986-2005, holdout 2006-2025. Primary: p.258 screen + Q1-Q5 EW ZIP + FM with controls (incl. vol36). Variants counted as trials: VW, terciles, gprof_sd5 (4 trials; vol36 shown as a reference, not counted).

## Results (`test_earn_stability.py` → `test_results.md`, run 2026-11-24)
- **Design 1986-2005:** low-minus-high +2.7%/yr (t NW 0.8), FF4 alpha -4.1%/yr (t -1.1); screen pass. FM alone +2.3 (t 0.6); with controls +1.8 (t 0.6); with vol36 only +3.5 (t 1.2).
- **Holdout 2006-2025:** -1.9%/yr (t -0.9), alpha -2.0 (t -0.9); screen pass. FM alone -2.4 (t -1.0); with controls -0.7 (t -0.3).
- **Variants:** VW is negative: alpha -6.8%/yr full (t NW -3.1, OLS -2.8) — stable large caps underperform after FF4 (they load on hml/low beta). Terciles ~0; gprof_sd5 alpha -3.7 (t -2.0). DSR (4 trials): primary Sharpe 0.02, hurdle 0.07, DSR 0.37.
- **Comovement:** roa_sd5 ~ vol36 0.65, ~ ep -0.43, ~ me -0.34, ~ bm -0.23.
- **Beyond vol36?** FM vol36 + roa_sd5: design roa_sd5 +3.5 (t 1.2), holdout -2.1 (t -1.0); overlap 2003-2021 (with PRisk, `signals/prisk/test_results.md`) -1.8 (t -0.7). **No:** it adds nothing reliable beyond vol36, and vol36 itself is not priced in this universe/annual setup (Q1-Q5 -1.9%/yr full).

## Verdict
No premium for earnings stability in large caps, annual rebalance, 1986-2025: raw spread ~0, FF4 alpha negative, sign flips between design and holdout. Correlated 0.65 with vol36 and adds nothing beyond it.

## Limitations
TTM ROA smooths the series; panel ratio timing assumed; large caps only; no sector-neutral or small-cap run.
