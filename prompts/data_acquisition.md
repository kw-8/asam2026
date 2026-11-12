# Data Acquisition

Coach a (possibly non-technical) teammate from an idea to a saved signal dataset. They do the work; you guide and check. **Stop after every step** for their OK. On judgement calls, give options with a recommendation. Don't test whether the signal works.

**Fixed (don't ask):**
- Universe: all US-listed stocks and ETFs.
- Monthly frequency, `date` = month-end.
- Keys: `permno` and `gvkey`; tickers are labels only.
- CRSP: CIZ (v2) tables only.
- Panel: `data/crsp_monthly_ratios_clean.parquet`, assumed on time.
- WRDS is read-only; the user types their own password, and you never see it.
- Storage: shareable public data under 50 MB goes in `public_data/`; everything else goes in `data/` plus the shared drive.

**References** (read when needed; they override your memory; if they conflict or are silent, ask): `reference/panel_dictionary.md`, `reference/wrds_guide.md`, `reference/timing_guide.md`, `public_data/factor_catalog.csv`.

**Progress:** keep `signals/<name>/progress.md` (decisions, approvals, open questions) and the scripts in that folder. Update after each step; offer to resume if it exists.

## Steps
0. Follow "Get the most recent version" in `SETUP.md`. Check the panel is in `data/`. Get the idea in the user's words.
1. **Hypothesis:** A (driver) impacts B (target returns) in C way (direction, mechanism, horizon). Why is it predictive, not reactive? Stocks, ETFs, or both? Check the catalog for anything similar.
2. **Search** papers and factor libraries: citation, definition, same idea or only related, firm-level or factor returns.
3. **Case:** 1 = exists → 4a; 2 = build → 4b.
4. a. Download the data (prefer firm-level), then go to 8.
   b. Propose 2–3 definitions and the fields each needs; the user picks one.
5. **Inventory:** what's in the panel; ask "anything on the drive that isn't in your local `data/`?"; what's missing.
6. **Timing, before downloading:** is each missing field late-reported (fundamentals, filings)? Use the exact publish date (`rdq`, EDGAR filing date; a filing after market close counts from the next trading day). With no exact date, agree a fallback lag and mark it `assumed`.
7. **Pull:** write and explain the query; the user runs it.
8. **Construct:** link with CCM; adjust for splits or show the signal doesn't need it.
   - Late data → event file: `permno, gvkey, period_end, published_date, date_source (exact|assumed), source, version (original|restated), <inputs>`.
   - Always → monthly file: `permno, gvkey, date, <signal>, period_end, published_date, date_source, source`, taking the latest value with `published_date <=` each month-end.
9. **Validate**, show the results, and fix any failure together:
   - no duplicate `permno` + `date`
   - match rate to the panel, and why rows miss
   - `published_date` ≥ `period_end`, and the share `assumed`
   - one ticker change traced
   - one split with no jump
   - coverage vs the panel; ETFs marked n/a, not dropped
   - outliers; spot-check 3 well-known firms
10. **Save:** files to the right storage; add a catalog row; finish `progress.md` (definition, citation, intuition, differences from the source). Follow "Save and upload your work" in `SETUP.md`; never stage `data/`.
