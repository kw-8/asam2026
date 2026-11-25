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

## EDGAR PRisk (current-data rebuild) - definition fixed 2026-11-24, before any build or return test
- Why: the free call-based PRisk ends with calls of 2022-03-31 (`data/prisk/firmquarter_2022q1.csv`; site says "updated through March 31, 2021"); our WRDS account cannot read `ciq_transcripts` (permission denied). EDGAR 10-K/10-Q text is free and current.
- Method = Hassan et al. eq. (1) (NBER w24029 p.10) applied to filings instead of call transcripts:
  EPRisk_{i,f} = sum over bigrams b of filing f of 1[b in P\N] x 1[|b - r| < 10] x w_b, divided by the number of bigrams in f.
  - P\N and w_b: their published list `combined_politicaltbb_npb_finalbigrams.csv` (188,878 bigrams, tf*idf x 100,000) -> `data/prisk/edgar/political_bigrams.csv`.
  - r = position of the nearest risk synonym: the 124 words of their Appendix Table 3 (p.70; "question", "questions", "venture" excluded).
  - Text: primary document of the filing only (no exhibits), HTML stripped, lowercase, punctuation removed, alphabetic tokens.
- Filings: 10-K, 10-K405, 10-Q of firms ever in the lab universe (Dec cohorts 2001-2025: 2,155 gvkeys, ~150k filings before link-date filtering). List: `wrdssec.wrds_forms`; CIK-gvkey: `wrdssec.wciklink_gvkey` (link valid at the filing date).
- Timing: published_date = first trading day after SEC acceptance date (`secadate`), date_source = exact. Monthly file: latest filing published by month-end, not older than 6 months. Signals mirror the call version: `eprisk4` = mean of last 4 filings (>= 3), `eprisk_dm4` = eprisk4 minus mean of the 8 filings before.
- Validation before any return test (2002-2022 overlap with call PRisk, same firm, filing vs call in the same fiscal quarter): per-quarter cross-sectional Spearman of eprisk vs prisk, and of eprisk_dm4 vs prisk_dm4. Rule fixed now: median Spearman < 0.2 -> report it as a different measure, not a PRisk substitute, before any return test.
- Pilot first: 50 random universe firms, filings 2015-2019, to check parsing and the validation numbers; then the full pull.

## Augmentation research (pre-registered 2026-11-24, before any augmentation return was computed)
- Question: does a logical augmentation of PRisk beat plain `prisk_dm4` (already seen: +1.2%/yr design and holdout) or `prisk4` (no spread)?
- Notation per firm (gvkey), per call/filing, base b (parameter: `prisk` now, `eprisk` later): b4 = mean of last 4 (>=3); past8 = mean of the 8 before (>=4); dm4 = b4 - past8 (= prisk_dm4). Monthly mapping = build_prisk.py rule (latest event published by month-end, not older than 6 months). Code: `signals/prisk/augment/`, data: `data/prisk/augment/`.
- Candidates (all: higher -> higher next-12-month return, `higher_better=True`):
  - **A1 dm4_ind** = pct rank of dm4 within (cohort, FF12 sector). Rationale: an industry-wide political shock (e.g. health reform) is priced at once in the whole industry; the firm-specific rise in exposure is the slow-moving part.
  - **A2 dm4_o_sent** = per-cohort residual of rank(dm4) on rank(psent_dm4), psent_dm4 = psent4 - past8(psent). Rationale: separate risk (second moment) from good/bad political news (first moment, a different and possibly opposite-signed effect).
  - **A3 sys_dm4** = dm4 of s = priskt_economic + priskt_trade + priskt_tax. Rationale: economic/trade/tax policy risk is shared across firms (aggregate, undiversifiable, Pastor-Veronesi), so it is the part that should carry a premium.
  - **A4 dm4_o_np** = per-cohort residual of rank(dm4) on rank(nprisk_dm4). Rationale: a firm that talks more about all risks (distress, demand) is not the same as one facing more political risk; keep the political part.
  - **A5 dm4_z** = dm4 / sd(previous 8 values) (>=4, sd>0). Rationale: SUE-style surprise; the same change means more for a firm with a stable PRisk history and less for a noisy transcript.
- Not chosen: PRisk x aggregate EPU (a scalar at each date does not change cross-sectional ranks; EPU timing on 10 design years is untestable); vol/beta conditioning (kept as the disguise check, not a candidate).
- Primary spec (each): q = 0.2, EW, annual December formation, lab universe; FM with lab CONTROLS (vol36, gprof, debt_at, ep, mom, me, bm). Disguise check: comove with vol36, me, beta60 (60-month market beta, >=36 months) and FM with CONTROLS + beta60.
- Selection on DESIGN only (cohorts Dec 2002-Dec 2011, design_end 2012-12-31): finalists = the top 2 candidates by design Sharpe with design mean > 0. "Improves on PRisk" iff finalist design Sharpe > prisk_dm4 design Sharpe AND holdout mean > 0. HOLDOUT computed once, only for the finalists; non-finalists' holdout is not computed.
- n_trials = 15 (10 earlier PRisk variants + A1-A5). DSR: design Sharpe of each finalist vs the 15 design Sharpes; FULL-period DSR of the finalists using the same 15-trial dispersion.

### EDGAR PRisk pilot validation and revision 1 (2026-11-24, no returns seen)
- Pilot (whole primary document, 575 of 742 filings scored when checked; 36 firms matched to a call within 45 days): per-quarter cross-sectional Spearman eprisk vs prisk median 0.106 (15 quarters, min -0.36, max 0.33); pooled 0.105; 10-K 0.168, 10-Q 0.074; within-firm 0.080; per-firm time-series median 0.006. Below the 0.2 rule: whole-document eprisk is a different measure from call PRisk.
- Revision 1 (one shot, logged as a change; validation against PRisk only, no return test): score only the MD&A section (10-K Item 7, 10-Q Item 2: from the "managements discussion and analysis" heading with the longest span to the next "quantitative and qualitative disclosures" / "financial statements and supplementary data" / "controls and procedures" heading), since MD&A is management's own discussion, the filing text closest to a call. Same eq. (1), same pilot firms and years, same 0.2 rule. If it fails, EDGAR PRisk is dropped and the call-based prisk_dm4 (through the 2022q1 vintage) is the delivered factor.
- Revision 1 result (MD&A only, 733 of 742 scored, 37 firms matched): per-quarter Spearman median 0.079 (20 quarters, min -0.29, max 0.42); pooled 0.088; 10-K 0.132, 10-Q 0.054; within-firm 0.075; per-firm time-series median 0.035. Fails the 0.2 rule. EDGAR PRisk dropped as pre-registered; no full pull. Factor = call-based prisk_dm4 (data through the 2021q1/2022q1 vintages). Scripts kept: signals/prisk/pull_prisk_edgar.py (User-Agent from env SEC_USER_AGENT).
