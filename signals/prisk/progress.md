# prisk — progress

Started: 2026-11-24 (overnight, assistant researcher) · Process: `prompts/data_acquisition.md` (run without step-by-step approvals; every choice recorded here for review)

## Idea (user's words)
"would something like exposure to political turmoil be a factor? … is there something that scores this kind of risk … per firm" → firm-level political risk (Hassan, Hollander, van Lent & Tahoun 2019).

## Pre-registration (written 2026-11-24 BEFORE any return was looked at)
- **Hypothesis (primary, one-sided):** higher firm-level political risk (PRisk) at the December formation date → higher returns over the next 12 months (risk premium: political risk is undiversifiable for the marginal investor / firms facing it cut investment and hiring, Hassan et al. 2019 §VI; Pástor & Veronesi 2013 for the aggregate version). `higher_better = True`.
- **Secondary (reported, not used to pick):** the opposite sign (overreaction / distress story).
- **Primary signal:** `prisk4` = mean of the firm's last 4 quarterly PRisk scores published by the month-end (raw quarterly PRisk is noisy: one call's word counts). Raw `prisk` and within-firm-demeaned `prisk_dm` are robustness variants, not alternatives to pick from.
- **Sample:** the PRisk data cover earnings calls 2002-04 to 2021-03. Formation each December, cohorts Dec 2002 … Dec 2020 (hold years 2003 … 2021; 19 years).
  - **Design:** cohorts Dec 2002 – Dec 2011 (hold years 2003–2012, 10 years; `design_end = 2012-12-31`).
  - **Holdout:** cohorts Dec 2012 – Dec 2020 (hold years 2013–2021, 9 years). Looked at once, after the design-sample verdict is written down.
- **Primary test:** book p.258 screen (rule A verdict, rule B flag) + top-minus-bottom quintile ZIP of `prisk4` (EW, annual, NW alpha on mktrf/smb/hml/umd) + annual Fama-MacBeth with controls. Universe = the lab default (NYSE median size, price ≥ $5, vol36 available).
- **Multiple testing:** every variant run below counts as a trial (`n_trials`); reported with a deflated-Sharpe haircut. Book p.247: with 20 noise signals one will show t ≈ 2.
- **EPU beta (added 2026-11-24, before any return was looked at):** `epu_beta` = slope on Δlog(US EPU) in a rolling 60-month regression (≥36 months) of the stock's excess return on mktrf and Δlog EPU (Baker, Bloom & Davis 2016 news-based index, `public_data/epu_us_monthly.csv`). Pre-registered sign: **high EPU beta → lower returns** (`higher_better = False`; stocks that hedge policy-uncertainty shocks are worth more, Brogaard & Detzel 2015 Management Science; Bali, Brown & Tang 2017 JFE for macro uncertainty beta — citations not re-checked tonight). Tested on the lab default sample (cohorts 1985–2024, design hold years 1986–2005, holdout 2006–2025) and on the PRisk sample; interaction with PRisk via Fama-MacBeth on the product of ranks. **DROPPED, not run** (coordinator 2026-11-24: keep it simple; earnings stability added instead). No EPU return was looked at; the downloaded series was deleted.

## Data and definition
- Source: firmlevelrisk.com `firmquarter_2021q1.csv` (Dropbox link on the download page), 330,539 firm-calls, calls 2002-04 to 2021-03. Hassan, Hollander, van Lent & Tahoun (2019), "Firm-Level Political Risk: Measurement and Effects", QJE 134(4), 2135-2202, doi:10.1093/qje/qjz021.
- PRisk = share of an earnings-call transcript's bigrams that are political bigrams used within 10 words of a risk/uncertainty synonym (scale as delivered; not re-derived). Also kept: NPRisk (non-political risk), Risk (all risk words), PSentiment, 8 topic PRisk scores.
- Build: `signals/prisk/build_prisk.py` → `data/prisk/prisk_events.parquet`, `data/prisk/prisk_monthly.parquet` (585,062 permno-months, 5,803 permnos, 2002-04 to 2021-09).
- Timing: call date known exactly; published_date = next business day (call hour unknown, after-close rule). A month uses the latest call published by month-end; a call older than 6 months is not used. `prisk4` = mean of last 4 calls (≥3). `prisk_dm(4)` = minus the mean of the firm's previous 8 calls (≥4).
- Link: gvkey → panel gvkey → permno (every permno of the gvkey gets it, e.g. GOOG/GOOGL). 89.5% of US-HQ events match; unmatched are mostly funds/OTC.
- Validation (`validate_prisk.py`): 0 duplicates; 100% published ≤ month-end; December coverage 40% of panel stocks in 2003 → ~70% 2017-19; in the test universe 415 of 823 stocks (71% cap) in Dec 2002, then 77-94% of names and 83-95% of cap. 14% zeros, heavy right tail (max 11,057) → ranks only.

## Results (`test_prisk.py` → `test_results.md`, `test_prisk.png`; run 2026-11-24)
Design and holdout were computed in one script run (pre-registration fixed before it); no parameter was changed after seeing returns except restricting the joint FM to the 2003-2021 overlap (a labelling fix).
- **Design (hold years 2003-2012), primary prisk4, Q5-Q1 EW:** mean -3.4%/yr (t NW -1.4), FF4 alpha -2.4%/yr (t NW -5.3, t OLS -1.5), positive in 3 of 10 years. **Screen: FAIL rule A** (shorting high PRisk earns significant alpha) and rule-B flag. FM alone -3.2 (t -1.1); with controls -0.9 (t -0.5). Pre-registered sign (high PRisk → higher return) **not supported**; the design sample leans the other way.
- **Holdout (2013-2021):** Q5-Q1 +0.7%/yr (t 0.5), alpha -0.5 (t -1.1); screen pass; FM alone +1.0 (t 0.6), with controls +1.6 (t NW 2.0, t OLS 1.3). Quintile means flat (16.4 / 16.6 / 15.4 / 16.8 / 17.1%).
- **Full 2003-2021:** mean -1.45%/yr (t -0.9), alpha -1.2 (t -1.9), Sharpe -0.20. Driven by 2009 (-21.6%) and 2010 (-12.6%), and 2020 (-13.9%): excluding 2008-09 and 2020 the mean is +0.2%/yr. High-PRisk names lost in the junk/beta rebound of 2009 and in COVID 2020.
- **Variants (10 trials):** only the *within-firm change* versions are positive: prisk_dm4 +1.2%/yr full (t 2.3), design +1.2 / holdout +1.3 (both positive, 67% of years); prisk_dm (last call) +2.5 design (t 3.4) but -0.25 holdout. Orth to Risk +1.1%/yr full (t 0.9). Everything else (VW, terciles, raw, FF12-neutral, orth NPRisk, no size screen) is within ±1.5%/yr of zero, t < 1.5 on mean.
- **DSR:** n_trials = 10, primary Sharpe -0.20, hurdle 0.39, DSR 0.00. prisk_dm4 Sharpe 0.55 clears the 0.39 hurdle only barely, and it was not the pre-registered primary.
- **Comovement:** prisk4 ~ Risk 0.71, ~ NPRisk 0.43, ~ gprof -0.19, ~ vol36 -0.04, ~ roa_sd5 -0.03. PRisk is mostly "talks about risk", little to do with volatility.
- **Joint FM 2003-2021 (19 years):** prisk4 -1.5 (t -0.8), nprisk4 +0.7 (t 0.7), vol36 -2.1 (t -0.6), roa_sd5 -2.1 (t -0.9); with the full control set prisk4 -0.5 (t -0.4). PRisk has nothing to "survive": it is not priced alone either. Slopes are oriented so positive = the hypothesised direction (vol36, roa_sd5: low is good).

## Verdict
Level PRisk is **not a usable return signal** in large caps 2003-2021: wrong sign in the design sample, zero in the holdout, fails the p.258 screen in design, DSR 0. The only lead is the within-firm *change* (prisk_dm4), positive in both halves but a non-primary variant after 10 tries.

## Limitations
- 19 annual observations (10 design, 9 holdout). NW t with T=10 is unreliable (lag 2 on 10 points: design alpha t NW -5.3 vs OLS -1.5); read the OLS t and the share of positive years.
- Large caps only (NYSE median screen); Hassan et al.'s effects are in investment/hiring, not in returns.
- Data end 2021-03: no cohorts after Dec 2020. The 2022-2025 vintages exist on firmlevelrisk.com (not pulled tonight).
- Raw PRisk counts are length-dependent; ranks absorb level differences but not transcript-format changes over time.

## What else to try (ranked)
1. **prisk_dm4 as its own pre-registered signal** on fresh data: pull the 2021q2-2025 vintage and test 2021-2025 as a true out-of-sample year set; also in small caps (size screen off).
2. **Political-risk *sentiment* / NPRisk-minus-PRisk and topic scores** (trade, tax, health) around specific events (2018 tariffs, 2020) — event windows, not annual sorts.
3. **Conditional use:** PRisk as a risk *filter* (avoid top-decile PRisk in high-EPU months) inside a low-vol/quality strategy rather than as a stand-alone tilt.
4. Monthly (not annual) rebalance with a 1-3 month horizon: the information is quarterly and may decay within the year.
5. EPU beta (dropped tonight) if the group wants a macro-exposure signal later.
