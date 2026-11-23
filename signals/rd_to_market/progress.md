# rd_to_market — progress

Started: 2026-11-22 · Process: `prompts/data_acquisition.md`

## Idea (user's words)
"Evaluate a R&D to Market Capitalization mispricing signal/factor over 40 years of financial data available through Compustat/CRSP ... evaluate if this a worthwhile signal/factor to choose a portfolio with."

## Final record (Step 10)
- **Status:** dataset built and validated 2026-11-22 (`have-data`). Not yet backtested: the process stops before testing whether the signal works.
- **Definition:** `rdm` = R&D expense (Compustat `xrd`) from the latest annual 10-K public by the month-end ÷ the firm's market value at that month-end (all its listed share classes in the panel, by CRSP `permco`) = 1000 x `xrd` ($ millions) / `me_firm` ($ thousands). R&D firms only: zero or missing R&D → `has_rd` = 0 and `rdm` blank. Signal on the primary (CCM-linked) share class. Usable until 18 months after fiscal year-end. Canadian-dollar R&D blank. Check column `rdm_hxz` = Hou-Xue-Zhang "Rdm" (June-fixed).
- **Timing:** 10-K filing date (`comp.co_filedate`), time converted from UTC to New York; before 4 p.m. → that trading day, otherwise next trading day; no 10-K date → fiscal year-end + 6 months (`assumed`, 8.6% of signal rows). `version = restated`.
- **Citation:** Chan, Lakonishok & Sougiannis (2001), "The Stock Market Valuation of Research and Development Expenditures," *Journal of Finance* 56(6), 2431–2456, doi:10.1111/0022-1082.00411. See also Hou, Xue & Zhang (2020), "Replicating Anomalies," *Review of Financial Studies* 33(5), 2019–2133, doi:10.1093/rfs/hhy131 (Rdm); Chen & Zimmermann, Open Source Asset Pricing (`RD`).
- **Intuition:** R&D is expensed immediately, so firms that invest heavily in research look unprofitable and have little book value, even when that research builds valuable intangible capital. If investors anchor on the reported numbers, R&D-heavy firms — especially beaten-down ones whose market value is small next to their research budget — are under-priced and earn higher returns later. A risk explanation (R&D firms are more volatile and uncertain) predicts the same direction; the backtest has to tell them apart.
- **Differences from the sources:**
  - *Chan, Lakonishok & Sougiannis (2001):* same ratio (one year's R&D ÷ market value, R&D firms only). They formed portfolios once a year on 1975–1995 data; ours is monthly, uses each firm's actual 10-K date, and the panel's universe (U.S.-incorporated common stocks on NYSE/AMEX/NASDAQ, 1980–2025).
  - *Hou, Xue & Zhang `Rdm`:* they fix the value each June (prior fiscal year's R&D ÷ prior December's market value). Ours updates at each 10-K and with every month's price. Their version is kept as `rdm_hxz` (December rank correlation with ours: median 0.89).
  - *Open Source Asset Pricing `RD`:* same formula, but a fixed 6-month lag and zero R&D kept as 0. Ours uses the exact 10-K date and blanks zero-R&D firms. Values are identical when both use the same fiscal year; rank correlation 0.99.
  - *JKP `rd_me`:* assumes accounting data public after 4 months and converts currencies; ours uses filing dates and leaves the few Canadian-dollar values blank.
- **Known limitations:** (1) Compustat's current (restated) values, not as first reported. (2) Market value counts only listed share classes (e.g. Alphabet Class B left out), as in OSAP. (3) Extreme values from tiny or distressed firms (up to 457x) — use ranks or winsorize. (4) One-off acquired in-process R&D inflates some firm-years (e.g. Merck 2023) — test with and without firm-years where R&D tripled. (5) 8.6% of signal rows use the assumed 6-month date (more in the early 1980s). (6) Paper published December 2001, so 2002–2025 is out of sample.

## Step 0 — Ready ✅ (approved 2026-11-22: "yeah this is the idea i want to evaluate")
- Repo up to date with origin/main (a19773f; local `main` = `origin/main` = GitHub, checked 2026-11-22).
- Panel present: `data/crsp_monthly_ratios_clean.parquet` (364 MB; 1980-01 to 2025-12 per `reference/panel_dictionary.md`). A 40-year window fits inside it.
- No existing `signals/rd_to_market/` folder, so nothing to resume. Folder name proposed; no objection.
- Already on disk from `capex_intensity` and reusable here: `data/capex_intensity/co_filedate.parquet` (Compustat filing dates with timestamps), `ccm_links.parquet`, `company.parquet`. Its `funda_raw.parquet` has no R&D (`xrd`), so R&D needs a new pull.
- Environment note carried over from `capex_intensity` Step 7: with this repo's requirements (pandas 3.1 + wrds 3.1.6), `db.raw_sql()` fails; pull scripts here use the same cursor workaround.
- Scope: this process builds and validates the signal dataset only; it does not test whether the signal works. The backtest (`claude/rdm_backtest.py` in the class project) runs after Step 10, on the saved signal file.

## Step 1 — Hypothesis ✅ (approved 2026-11-22: Option 1, rank R&D firms only)
- **A (driver):** a firm's R&D spending from its latest public annual report, divided by its market value of equity at month-end (R&D-to-market, "rdm").
- **B (target):** the stock's returns over the following 1–12 months (the signal changes once a year, and the fund rebalances annually).
- **C (direction, mechanism, horizon):** higher R&D-to-market → higher future returns. U.S. accounting expenses R&D at once, so heavy researchers report low earnings and book value even when the research builds valuable intangible capital. Investors who anchor on reported numbers under-price these firms, most of all beaten-down ones whose market value is small next to their R&D budget (Chan, Lakonishok & Sougiannis 2001). A risk story predicts the same sign (R&D firms are more volatile and uncertain); telling the two apart is for the backtest, not this process. Horizon: slow, months to years.
- **Predictive, not reactive:** R&D comes from a filing already public at month-end t (Step 6 sets the exact date); market value is known at t; the returns predicted start in t+1. The signal does partly move with recent price falls (market value is the denominator); that is part of the mechanism, not look-ahead, but it means rdm overlaps with value and reversal, which the backtest must control for.
- **Universe:** stocks only. ETFs have no R&D → n/a (the panel has no ETFs anyway, per the catalog).
- **Catalog check:** no R&D or intangibles signal. Closest relatives are the panel's value ratios (`bm`, `sp`, `ep`, `cfp`). Note rdm = (R&D / sales) x (sales / price), so it is partly the panel's `sp`.
- **Judgement call — whose returns does the claim cover?**
  1. *(recommended)* Among firms that report R&D: rdm ranks R&D firms only. Firms with no R&D are kept, flagged, with a blank signal. Matches the paper (R&D firms as a group earn about the same as non-R&D firms; the effect is within R&D firms).
  2. All stocks, rdm = 0 when no R&D is reported. Simpler, but the low end then mixes "no research" with "little research per dollar of value".

## Step 2 — Search ✅ (approved 2026-11-22)
| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Chan, Lakonishok & Sougiannis (2001), JF 56(6) 2431–2456 | R&D expense / market value of equity; quintiles of R&D firms, held a year (sample 1975–1995) | **Same (original)** | Firm-level (paper) |
| Hou, Xue & Zhang (2020), RFS 33(5) 2019–2133, "Rdm" | `xrd` for fiscal year ending in t−1 / December t−1 market equity (share classes merged); **positive R&D only**; deciles formed end of June t, held July t–June t+1; from 1976 | **Same** (closest to our Option 1). Reported high-minus-low 0.68%/month (t = 2.58), NYSE breakpoints, value-weighted | Firm-level definition; their returns in the paper |
| Hou, Xue & Zhang (2020), "Rdmq" | Quarterly `xrdq` (quarter ending ≥ 4 months earlier) / last month's market equity; positive only; monthly; from 1990 | Same idea, quarterly variant | Firm-level definition |
| Open Source Asset Pricing (Chen & Zimmermann), `RD` | `xrd` / market value of equity at the PERMCO level, annual Compustat made available datadate + 6 months, updated monthly as market value changes. Keeps `xrd` = 0 as 0 (drops missing) | **Same**, ready-made; differs from Option 1 on zeros | Firm-level (`permno`, `yyyymm`) + long-short portfolio returns. Latest release Oct 2025, data through Dec 2024 |
| JKP Global Factor Data, `rd_me` ("R&D-to-market", theme Intangibles) | `xrd` / company market equity; accounting assumed public 4 months after period end | Same, ready-made | Factor returns on jkpfactors.com; firm-level via WRDS `contrib_global_factor` |
| Lev & Sougiannis (1996), JAE; Chambers, Jennings & Thompson (2002), RAST | R&D capital (past R&D, amortized) / market value; CJT argue the premium is mostly risk | Related | Firm-level (papers) |
| OSAP `RDcap` (Li 2011, RFS), `SurpriseRD` (Eberhart, Maxwell & Siddique 2004, JF), `RDAbility` (Cohen, Diether & Malloy 2013, RFS) | R&D capital / assets; unexpected R&D increase; R&D "ability" | Related, different signals | Firm-level + portfolios |
| R&D / sales (CLS 2001; HXZ `Rds`; OSAP placebo `rd_sale`) | `xrd` / sales | Related; **did not predict returns** in CLS or HXZ, so the market-value denominator matters | Firm-level |

Notes for later steps:
- All published versions use annual `xrd` from Compustat with a fixed lag (6 months OSAP, 4 months JKP, June-of-next-year HXZ). None uses the exact filing date; our Step 6 can.
- OSAP's version is a ready-made cross-check for Step 9 (match on `permno` + month).

## Step 3 — Download or build ✅ (approved 2026-11-22: Case 2, build; OSAP `RD` kept as Step 9 cross-check)
- **Case 1 — download** OSAP `RD` (firm-level, `permno` + `yyyymm`): quickest, no WRDS query. But: ends Dec 2024 (panel runs to Dec 2025); fixed 6-month lag for everyone, so every row is `assumed`; no fiscal period end in the file, so the required `period_end` / `published_date` columns can't be filled; zeros kept as 0 (fixable by blanking them); needs CCM to add `gvkey`.
- **Case 2 — build** from Compustat (`comp.funda` `xrd`) + the panel's market value: exact 10-K filing dates from `data/capex_intensity/co_filedate.parquet` (already on disk, with timestamps for the after-close rule), fallback 6 months `assumed`; data through the latest filings (covers 2025); our own choices on positive-R&D-only and firm-level market value; all required columns. Cost: one new WRDS query (you run it) plus Steps 5–8. CCM links and company names are already on disk.
- **Recommendation: Case 2**, keeping OSAP `RD` as the Step 9 cross-check (same approach the capex signal took).

## Step 4b — Definition ✅ (approved 2026-11-22: **A**, plus **B** built from the same pull as a check; C dropped — fewer years, more gaps, little gain for an annual fund)
Common to all: R&D firms only (`xrd` > 0); firms with zero or missing R&D stay in the file with `has_rd` = 0 and a blank signal; ETFs n/a. Market value = the firm's total across share classes. Units: `xrd` is $ millions, panel `me` is $ thousands, so rdm = 1000 x xrd / me.
- **A. Annual R&D, current market value** — recommended. rdm(t) = latest annual `xrd` whose 10-K was public by month-end t ÷ firm market value at month-end t. Moves every month with the price, changes R&D once a year. Same as OSAP `RD` / JKP `rd_me` (and CLS), so the Step 9 cross-check lines up. Fields: `comp.funda` `xrd`, `datadate`, `fyear`, `fyr`, `curcd`; filing dates (on disk); panel `me`; share-class link (CCM `lpermco`, on disk).
- **B. HXZ "Rdm", fixed each June.** `xrd` for the fiscal year ending in calendar t−1 ÷ market value at December t−1; value held fixed July t to June t+1. Exactly the replication-literature version; ignores actual filing dates and recent price moves. Same fields as A, so it can be built later from the same pull as a check.
- **C. Quarterly R&D, trailing 12 months (HXZ "Rdmq"-style).** Sum of the last 4 quarters' `xrdq` (each public by its `rdq` date) ÷ month-end market value. Fresher (updates every quarter) but quarterly R&D only starts around 1989–1990, so about 35 years, not 40. Fields: `comp.fundq` `xrdq`, `rdq`, `datadate`, `fqtr` (a different, larger pull); panel `me`.

## Step 5 — Inventory ✅ (approved 2026-11-22; nothing extra on the shared drive)
Panel (`data/crsp_monthly_ratios_clean.parquet`, 1980-01 to 2025-12): has `me` (prc x shrout, $ thousands), `permno`, `gvkey` (11.5% null), `siccd`, `primaryexch`. **No R&D column** (none of the 26 ratios uses R&D). No `permco`.

| Needed for A (and B) | Have? | Where |
|---|---|---|
| Annual R&D `xrd` | ❌ **missing** | `comp.funda` — the one new WRDS pull (Step 7) |
| `datadate`, `fyear`, `fyr`, `curcd` | ✅ (but re-pull with `xrd`, same filters) | `data/capex_intensity/funda_raw.parquet` (536,680 firm-years, 1975+; capx, sale, ceq, at, ppent — no xrd) |
| 10-K filing dates | ✅ 1975–2026; time of day only from ~2006 (≈91% by 2010) and stored as a UTC clock time | `data/capex_intensity/co_filedate.parquet` (`comp.co_filedate`). Only 40–65% of Compustat firm-years have a `10K` row → look into in Step 6 |
| Second exact-date source (EDGAR acceptance times) | ✅ 2002–2025 | `data/issuance_insider/filings_10kq.parquet` + `data/lazy_prices/ciklink.parquet` |
| Trading calendar (after-close → next trading day) | ✅ 1993–2025 | `data/lazy_prices/trading_days.parquet` |
| Market value, monthly | ✅ | panel `me` |
| Share-class link (`permco`) | ✅ | `data/issuance_insider/crsp_monthly.parquet` (every permno-month 1974–2025) and CCM `permco` |
| CCM links | ✅ | `data/capex_intensity/ccm_links.parquet` |
| Company names (spot checks) | ✅ | `data/capex_intensity/company.parquet` |
| Ticker history (Step 9 ticker change) | ✅ | `data/lazy_prices/security_info.parquet` |
| Split factors (Step 9 split check) | ✅ | `data/issuance_insider/crsp_monthly.parquet` (`mthcumfacshr`, `mthcumfacpr`) |
| OSAP `RD` (Step 9 cross-check) | ❌ | download at Step 9 with `openassetpricing`, copying `signals/issuance_insider/get_osap_shareiss.py` |

Missing: `xrd` only (plus the optional OSAP `RD` file).

## Step 6 — Timing ✅ (approved 2026-11-22: Option 1, 10-K filing date; trust very late dates; accept restated values)
- **Late-reported?** `xrd` yes (annual accounting). Market value no (CRSP month-end, no lag).
- **Which document carries `xrd`?** The 10-K for sure. Many R&D-heavy firms also show R&D in the earnings press release, but not all (Compustat also takes R&D from 10-K notes when it is buried in other expense lines).
- **Exact dates on disk (`comp.co_filedate`, srctype `10K`)**, measured on Compustat firm-years linked to a CRSP stock (293,928, 1975–2025):
  - Share with a 10-K date: 62% (1975–79), 69–75% (1980s–early 90s), 76–81% (1995–2025). The rest → fallback, `assumed`.
  - One `10K` row per firm-year (amendments are a separate `10K/A` type, not used).
  - Real dates, not imputed: 0.1% fall on a weekend (an imputed fiscal-year-end + 90 days would hit weekends ~28% of the time). Before 2002 about a quarter are exactly 90 days after year-end — firms filing on the old 90-day deadline.
  - Time of day: only from about 2006 (≥ 91% from 2010). Stored as a **UTC clock time** (the date part is the pull date): matched against EDGAR acceptance times for 80,851 filings, it runs exactly +4 h in summer and +5 h in winter → convert to New York time.
  - After-close matters: 35% of 10-Ks are accepted between 4 and 5 p.m. ET, 20% between 5 and 6 p.m.
  - Very late dates: 1,832 firm-years filed > 1 year after year-end; ~1,700 are fiscal 1996–97 10-Ks almost all stamped Mar–Apr 1999 (looks like a data glitch); the rest look like genuinely late filers.
- **Options:**
  1. *(recommended)* **10-K filing date.** Time known and before 4:00 p.m. ET → public that day; at/after 4:00 p.m. or no time → next trading day. `date_source = exact`. No 10-K date → `datadate` + 6 months as month-end, `assumed` (team default). Trading calendar: `data/lazy_prices/trading_days.parquet` (1993+); before 1993, CRSP's daily index dates (added to the Step 7 pull).
  2. **Q4 earnings-release date (`rdq` from `comp.fundq`).** 3–6 weeks earlier, but needs a second, larger pull, and risks using R&D before it was public for firms whose release doesn't show it.
  3. **Fixed 6-month lag for all** (what OSAP does). Simplest; all rows `assumed`.
- **Sub-choices (recommendations):**
  - Very late dates: **trust them** (conservative: never use R&D before the recorded date). Cost: a coverage dip in 1997–99 for the glitch firms; check its size at Step 9. Alternative: treat dates > 1 year late as missing and use the 6-month fallback (keeps coverage, risks look-ahead for real late filers).
  - Restatements: **accept Compustat's current (restated) values**, `version = restated` on every row, and say so in the definition. Same as OSAP/JKP/HXZ. A point-in-time source (Compustat Snapshot, VERIFY in our subscription) is a possible later upgrade.

## Step 7 — Pull ✅ (run by user 2026-11-22; checked)
Results (`data/rd_to_market/pull_log.txt`):
- `funda_rd.parquet`: 536,754 firm-years, 46,165 firms, fiscal years 1974–2026; no duplicate `gvkey`+`datadate` (116 firms have two year-ends in one `fyear` after changing fiscal year — each is its own event). Currencies: USD and CAD only. `xrd` never negative.
- Spot-checks match the 10-Ks: Microsoft FY2024 (June) $29,510M; Intel 2023 $16,046M; Merck 2023 $30,531M (includes the one-off acquired in-process R&D charge — note for Step 9 outliers).
- `trading_days_pre1993.parquet`: `crsp.dsi` has no `caldt` column, so the IBM fallback ran: 4,571 days 1975-01-02 to 1993-01-29. Matches `lazy_prices/trading_days` on the January 1993 overlap; the 1977-07-14 blackout and 1985-09-27 hurricane closures are correctly absent.
- `exrt_mth.parquet`: 76,446 rows, GBP-based cross rates (`fromcurm` = GBP, `tocurm`, `exratm`), 1982-01 to 2026-11.
- On CRSP-linked firm-years 1978–2025 (293,928): 107,201 have positive R&D (36%). Exact 10-K date for 71% of them in 1978–79, 81–86% from 1980 on → ~15–19% `assumed`. Non-USD (CAD): ~1% (1,119 firm-years).

## Step 8 — Construct ✅ (choices approved 2026-11-22: primary share class with firm market value; CAD R&D blank; 18-month limit. Run by user 2026-11-22: output identical to the test run)
- Script: `signals/rd_to_market/build_rd_to_market.py` (no WRDS needed; ~15 seconds). Run from the repo root:
  `python signals\rd_to_market\build_rd_to_market.py` → `rd_events.parquet`, `rd_to_market_monthly.parquet`, `build_log.txt` in `data/rd_to_market/`.
- Tested on a stand-in panel (the panel file times out when copied to the workspace): `lazy_prices_monthly` rows (= the panel's rows) + market value from `issuance_insider/crsp_monthly` (|price| x shares, the panel's own formula).
- Test results: 536,754 events (46,165 firms); publish dates: 241,415 fallback (mostly firms never in CRSP), 212,712 filing date without time, 44,423 after 4 p.m. ET, 38,204 before 4 p.m.; 0 published before period end. Monthly file = 2,796,065 rows (the panel exactly), 0 duplicates. Signal on 37.9% of panel rows (1,058,889); blanks: no R&D reported 56.3%, no CCM link 2.2%, no 10-K public yet 1.7%, secondary share class 1.1%, older than 18 months 0.8%, non-USD R&D 0.0%. Exact dates on 91.4% of signal rows. rdm median 0.039 (p1 0.001, p99 1.27). `rdm_hxz` on 958,376 rows.
- Spot-checks: Microsoft FY2024 10-K filed after the close on 2024-07-30 → used from the July 2024 month-end, rdm 0.0095; Alphabet GOOGL carries the signal, GOOG blank ("secondary share class"), firm market value = both; NVIDIA's 10-Ks (filed 4:20–5:30 p.m. ET) count from the next trading day; Mercury Interactive left the panel in Jan 2006 (delisted for not filing), so its stale 2004 figure is never used.
- Known limitation: firm market value counts only share classes in the panel; unlisted classes (e.g. Alphabet Class B) are left out — same as OSAP's PERMCO market value.

### Plan as approved
- **Event file** `data/rd_to_market/rd_events.parquet`, one row per `gvkey` x fiscal year-end: `permno, gvkey, period_end (= datadate), published_date, date_source, source, version = restated, xrd, xrd_usd, curcd, fyear, fyr`. `published_date` per Step 6: 10-K date (UTC time → New York time; before 4:00 p.m. → that day, else next trading day), else `datadate` + 6 months as month-end (`assumed`).
- **Monthly file** `data/rd_to_market/rd_to_market_monthly.parquet`: every panel `permno` x month-end that links to Compustat; latest event with `published_date` ≤ month-end. `rdm = 1000 x xrd_usd / firm market value ($ thousands)`; `has_rd` = 1 if `xrd` > 0, else 0 with `rdm` blank. Extra column `rdm_hxz` = Definition B (June-fixed) from the same events.
- **Splits:** no adjustment needed — R&D is in dollars and market value (price x shares) doesn't change at a split. Shown in Step 9.
- **Choice 1 — share classes:** *(recommended)* signal on the CCM-linked (primary) share class only, divided by the whole firm's market value (all classes, by `permco`); other classes stay in with a blank signal, so a firm is never counted twice. Alternative: give every class the same value.
- **Choice 2 — Canadian-dollar reporters:** first measured on all CRSP stocks (~1% of R&D firm-years). Re-measured on the panel after the user asked why Canadian firms matter: the panel is U.S.-incorporated companies only (2,795,878 of 2,796,065 rows have CRSP `usincflg = Y`, checked via `lazy_prices_monthly`, which has exactly the panel's rows), so Canadian companies listed in the U.S. are already excluded. Only 14 stocks / 247 panel rows (0.02% of rows with R&D) carry Canadian-dollar R&D — mostly firms that started in Canada and later re-incorporated in the U.S. (e.g. Inovio, Mirati, Oncothyreon, Maxar). **Revised recommendation: leave those blank** (simplest; no exchange-rate step). Converting is still possible with `exrt_mth`.
- **Choice 3 — how long an R&D figure stays usable if no newer 10-K arrives:** *(recommended)* until 18 months after fiscal year-end (≈ OSAP's 12 months after its 6-month lag; leaves ~3 months' grace for late filers). Alternatives: 24 months, or no limit.
- Script: `signals/rd_to_market/pull_compustat_rd.py` (read-only). Run from the repo root with the .venv active:
  `python signals\rd_to_market\pull_compustat_rd.py --user YOUR_WRDS_USERNAME`
- Pulls:
  1. `comp.funda`: `gvkey, datadate, fyear, fyr, curcd, xrd, sale`; standard filters (`INDL/STD/D/C`); fiscal years ending 1975 onward → `data/rd_to_market/funda_rd.parquet`.
  2. Trading days 1975-01 to 1993-01 from `crsp.dsi` (fallback: the days IBM, permno 12490, traded in `crsp.dsf_v2`) → `trading_days_pre1993.parquet`. Joins `data/lazy_prices/trading_days.parquet` (1993+) for the next-trading-day rule.
  3. `comp.exrt_mth` (optional, small) → `exrt_mth.parquet`, in case Step 8 converts non-USD reporters.
- Reused, not re-downloaded: `co_filedate`, `ccm_links`, `company` from `data/capex_intensity/`.
- Uses the cursor workaround for `raw_sql()` (same `query()` helper as capex). Prints an R&D status table by decade and a spot-check (Microsoft, Intel, Merck), and writes everything printed to `data/rd_to_market/pull_log.txt`.
- Tested against a fake WRDS connection (all three queries, the IBM fallback after a failed query, saved file types).

## Step 9 — Validate ✅ (all checks PASS incl. optional OSAP; approved 2026-11-22)
Script: `signals/rd_to_market/validate_rd_to_market.py` (reads the build output, ~10 seconds) → `data/rd_to_market/validate_log.txt`. Run on the real build output on 2026-11-22.

| # | Check | Result |
|---|---|---|
| 1 | Duplicates | PASS — 0 `permno`+`date`, 0 `gvkey`+`period_end` |
| 2 | Match to panel | PASS — monthly file = the panel's 2,796,065 rows exactly. Signal 37.9%; no R&D reported 56.3%; no CCM link 2.2% (92% of these have no `gvkey` in the panel either); 10-K not yet public 1.7%; secondary share class 1.1%; older than 18 months 0.8%; no market value 847 rows; non-USD R&D 231 rows |
| 3 | Timing | PASS — 0 events published before period end; 0 signal rows using a 10-K not yet public; 0 older than 18 months. Fiscal year-end → public: median 88 days (p1 39, p99 184). `assumed`: 8.6% of signal rows (23% 1980–84, 12–15% 1985–99, ≤ 4% from 2000) |
| 4 | Ticker change | PASS — FB → META (permno 13407, 2022-06-09): same `permno` and `gvkey`, rdm changes only with price |
| 5 | Splits | PASS — NVIDIA 10-for-1 (June 2024): price /10, shares x10, rdm 0.0032 → 0.0029 (price move only). Across 5,513 split months, 0.3% show a jump equal to the split ratio (the error signature). Reverse-split months often move more than the price return (16%) because the firm also issues shares that month (more shares than the split leaves, not undone the next month) — real, not an error. Note: CRSP's cumulative share factor *falls* at a forward split |
| 6 | Coverage; ETFs | PASS — signal on 30% (1980) rising to 50% (2025) of panel rows; 6,933 ETF permnos in CRSP, 0 in the panel → 0 rows n/a, none dropped |
| 7 | Outliers; 3 firms | PASS — Microsoft FY2024 $29,510M, Intel 2023 $16,046M, Merck 2023 $30,531M all match their 10-Ks; Dec 2024 rdm recomputed by hand (MSFT 0.0094, INTC 0.1848, MRK 0.1213). rdm p50 0.039, p95 0.40, p99 1.27, max 457 (AEON Biopharma Feb 2025: $381M R&D vs $0.8M market value). The extremes are tiny or distressed firms (also Cyngn, Centrus 2014, Spansion 2009); 33 firm-years where R&D tripled above $1bn (one-off acquired in-process R&D, e.g. Merck 2023, Ironwood 2023) |
| 8 | Definition B | PASS — December rank correlation of rdm with `rdm_hxz`: median 0.89 (0.70–0.93) over 45 years |
| 9 | OSAP `RD` | PASS — run by user 2026-11-22 (`get_osap_rd.py`; OSAP release covers 1950-12 to 2025-12, correcting the Step 2–3 note that it ends in 2024). 93% of our signal rows are in OSAP; median monthly rank correlation 0.99; 85% within 10%. When both use the same fiscal year (6–12 months after year-end) the values are identical (median ratio 1.0000). All larger differences are timing: we switch to a new 10-K on its filing date (~3 months after year-end), OSAP waits 6 months. Our rows not in OSAP (7.4%): OSAP has no row for those stock-months (31% are within 6 months of year-end, before OSAP's lag starts) |

Notes for the backtest (not data problems): sort on ranks or winsorize (extremes above); price ≥ $5 / size filters remove most extremes; acquired-R&D spikes inflate rdm for one year (try with and without firm-years whose R&D tripled); check results with `rdm_hxz` too.

## Step 10 — Save (files written 2026-11-22; upload is yours)
- **Catalog:** row `rd_to_market` added to `public_data/factor_catalog.csv` (category `intangibles`, status `have-data`; `test_results` left empty until a backtest). Appended only; the 29 existing rows are unchanged.
- **GitHub (stage exactly these 6 files):** `signals/rd_to_market/progress.md`, `pull_compustat_rd.py`, `build_rd_to_market.py`, `validate_rd_to_market.py`, `get_osap_rd.py`, and `public_data/factor_catalog.csv`. Never `data/` (`.gitignore` already excludes `data/` and `*.parquet`).
- **Shared drive (same layout, `data/rd_to_market/`):** `rd_to_market_monthly.parquet` (48.7 MB), `rd_events.parquet` (7.5 MB), `funda_rd.parquet` (4.3 MB), `trading_days_pre1993.parquet`, `osap_RD.parquet` (10.9 MB; OSAP firm-level data goes on the drive per `reference/wrds_guide.md`), `exrt_mth.parquet` (12 MB; pulled but not used), and `pull_log.txt`, `build_log.txt`, `validate_log.txt`. Nothing goes in `public_data/` besides the catalog row: everything else is built from licensed WRDS data.
- **Upload (SETUP.md "Save and upload your work"):** first "Get the most recent version" (merge `origin/main`), then Source Control → stage the 6 files → commit → Sync Changes. If anything else shows up under Changes (data files, `.venv`), or VS Code reports a conflict, stop and ask.
- **Next (outside this process):** backtest `rdm` (and `rdm_hxz`) from `data/rd_to_market/rd_to_market_monthly.parquet`, following the team's backtests (`signals/issuance_insider/backtest.md`), then fill `test_results` in the catalog.

## Open questions
- (none)
