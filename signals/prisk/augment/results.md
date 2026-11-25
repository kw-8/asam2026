# PRisk augmentation: results (2026-11-24)

Pre-registered in `signals/prisk/progress.md` ("Augmentation research") before any return was computed. Base dm4 = mean of last 4 calls minus mean of the 8 before (= prisk_dm4). Spec: Q5-Q1, EW, annual Dec formation, lab universe. Design hold years 2003-2012 (9 years: dm4 needs ~2 years of call history).

**Candidates (all higher = long)**
- A1 dm4_ind: dm4 ranked within FF12 sector (firm-specific rise, not industry shocks)
- A2 dm4_o_sent: dm4 orthogonal to the change in PSentiment (risk, not news)
- A3 sys_dm4: dm4 of economic+trade+tax topic PRisk (aggregate, undiversifiable)
- A4 dm4_o_np: dm4 orthogonal to the change in NPRisk (political, not all risk)
- A5 dm4_z: dm4 / sd of the previous 8 calls (SUE-style surprise)

**DESIGN** (mean %/yr, t NW, alpha t NW/OLS, Sharpe): A1 2.15, 2.5, 3.8/1.4, 0.47 | A2 1.07, 1.4, 1.9/1.1, 0.42 | A3 0.55, 0.5, 0.3/0.1, 0.15 | A4 1.12, 1.1, 1.6/0.8, 0.33 | A5 1.94, 1.7, 3.0/0.8, 0.44 | ref dm4 1.20, 1.4, 3.5/1.1, 0.42.

**Finalists** (top 2 design Sharpe): A1, A5. **HOLDOUT 2013-2021 (seen once):** A1 -0.50%/yr (t -0.5), Sharpe -0.18: fails. A5 +1.67%/yr (t 2.2), alpha 2.9 (t OLS 1.8), Sharpe 0.57; ref dm4 +1.26, Sharpe 0.79. FULL: A5 Sharpe 0.50 vs dm4 0.55.

**DSR** (n_trials = 15: 10 earlier + 5; hurdle 0.68): A5 design 0.28, holdout 0.38, full 0.25; A1 full 0.02.

**FM with lab controls (FULL slope %/yr, t NW):** A5 1.00 (1.1); + beta60 1.09 (1.2); holdout slope 0.0 for A5 and dm4. Spearman with vol36, me, beta60 all |rho| <= 0.01: not volatility/size/beta in disguise. A5 ~ dm4 0.91.

**Verdict:** no augmentation robustly improves on plain prisk_dm4. A5 meets the pre-registered letter (design Sharpe 0.44 > 0.42, holdout mean > 0) but by 0.02, its full-sample Sharpe is below dm4's, DSR 0.25, and FM with controls is insignificant. A1's design lead reversed out of sample. The factor is plain prisk_dm4 (~+1.2%/yr, modest, uncorrelated with vol/size/beta), weak after controls; A5 is the one variant worth re-running on EDGAR data.

**Re-run on EDGAR:** `python signals/prisk/augment/build_augment.py eprisk <events.parquet> data/prisk/augment/aug_eprisk_monthly.parquet` then `python signals/prisk/augment/test_augment.py data/prisk/augment/aug_eprisk_monthly.parquet eprisk A5,A1` (needs an event-level file with gvkey, published_date, eprisk).

Files: signals/prisk/augment/{build_augment.py, test_augment.py, test_tables_prisk.md, results.md}; data/prisk/augment/aug_prisk_monthly.parquet.
