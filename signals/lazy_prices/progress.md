# lazy_prices — progress

Started: 2026-11-12 · Process: `prompts/data_acquisition.md`

**Status (2026-11-14):** Steps 3–10 done; data built and validated; catalog row added. **Left for you:** re-run build + validate (flag now 2010–2014), upload the two data files to the shared drive, commit and sync (see Step 10). Steps 0, 1, 2 and 5 were drafted in a claude.ai chat and never formally ticked; everything built on them was approved later.

## Summary
- **Signal:** `filing_sim` — how similar a firm's 10-K is to its previous year's 10-K (cosine similarity of word counts, 0 to 1). **Low = "changer".**
- **Definition:** for each original 10-K (10-K, 10-K405, 10-KT, 10-KSB variants; no amendments), WRDS's cosine similarity with the firm's most recent *original* 10-K among the four previous 10-K-family filings, only if that one was filed 9–15 months earlier. Each panel month-end takes the latest value with `published_date <=` month-end, at most 15 months old.
- **Citation:** Cohen, L., Malloy, C., & Nguyen, Q. (2020). Lazy Prices. *Journal of Finance*, 75(3), 1371ff. doi:10.1111/jofi.12885
- **Intuition:** firms keep most 10-K text unchanged year to year; when they do rewrite it, something usually changed (new risks, litigation, a weaker business). Few investors compare filings side by side, so the news reaches prices slowly. Changers then tend to underperform, and most of the paper's return came from the short side.
- **How ASAM can use it (long-only, no shorting):** as an **avoid screen** — leave out (or underweight) the bottom fifth each month. A left-out stock acts like a short relative to the market (textbook Ch. 2 §2.3.3), but the gain is capped by the stock's benchmark weight, so test both equal- and value-weighted.
- **Files:** `data/lazy_prices/lazy_prices_monthly.parquet` (one row per panel row: `permno, gvkey, date, filing_sim, period_end, published_date, date_source, source, applies, format_change_2010_14`) and `data/lazy_prices/lazy_prices_events.parquet` (one row per 10-K, with inputs). Not tested for returns here, by design.
- **Known limitations:** (1) values from 10-Ks published 2010–2014 are flagged `format_change_2010_14`: a filing-format change tripled 10-K length and, in 2010–2012, made the largest firms 57–63% of the bottom fifth (English-only words did not fix it) — run the backtest with and without these months; (2) usable from 1998; filings end 2024-12, so 2025 values are 2024 10-Ks; (3) 85% of 1998–2024 stock-months have a value (new listings need two comparable 10-Ks first); (4) 11 events lack a `period_end` and 41 have a doubtful one (WRDS `rdate`); timing does not use it.

## Differences from the source (Cohen, Malloy & Nguyen 2020)
| | Paper | Here |
|---|---|---|
| Filings | 10-Ks and 10-Qs, each vs the same filing a year earlier | 10-Ks only (one update a year); 10-Qs left for later |
| Measures | four (cosine, Jaccard, minimum edit distance, simple **(VERIFY)**) | cosine only, chosen before seeing returns |
| Similarity source | authors' own processing of EDGAR text | WRDS SEC Analytics `bow_cossim` (pre-computed; amendments skipped by us) |
| Sample | EDGAR 1995–2014 | 1994–2024 (2015–2024 is after publication) |
| Timing | filing month | SEC acceptance time; after 4 p.m. → next trading day; unusable acceptance dates replaced by the EDGAR filing date |
| Use | long-short quintile portfolios (non-changers minus changers) | long-only avoid screen for ASAM |
| Data issues found | — | 2010–2014 format change flagged; lookback counting amendments fixed; WRDS re-processing dates fixed |


## Idea (user's words)
"How much a firm changes its 10-K wording ('Lazy Prices,' Cohen, Malloy & Nguyen, 2020)" … "using the logic that bad stocks are not part of a portfolio and that we can use this as a potential screener on stocks to avoid, let's try and create a signal based off of this."

## Step 0 — Ready ⏳
- Local `main` = GitHub `main` = a00ee81 (checked 2026-11-12). Merge `origin/main` again before you start.
- Panel present: `data/crsp_monthly_ratios_clean.parquet` (364 MB; 1980-01 to 2025-12).

## Step 1 — Hypothesis ⏳ (proposed)
- **A (driver):** how much a firm's 10-K / 10-Q text changed versus the same filing a year earlier (textual similarity; low similarity = "changer").
- **B (target):** next-month stock returns (also 1–12 months; the paper finds no reaction on the filing date and returns that build over the following months).
- **C (direction, mechanism):** big changers earn lower future returns. Firms rewrite filings when something changed (new risks, litigation, weaker business); few investors compare filings side by side, so prices adjust slowly.
- **Use for ASAM (long-only):** an **avoid screen**. Leave out (or underweight) the biggest changers. Leaving a stock out works like a short relative to the market (textbook Ch. 2, §2.3.3, "holes"), but the gain is capped by the stock's benchmark weight.
- **Predictive, not reactive:** uses only filings already on EDGAR; Step 6 enforces acceptance times.
- **Universe:** stocks only. ETFs don't file 10-Ks / 10-Qs → marked n/a, not dropped.
- **Catalog check:** nothing similar (26 panel ratios; `capex_intensity` in progress). Nearest in spirit: `accrual` (earnings quality).

## Step 2 — Search ⏳ (proposed)
| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Cohen, Malloy & Nguyen (2020), "Lazy Prices," *JF* 75(3), p. 1371ff, doi 10.1111/jofi.12885 | Similarity of each 10-K/10-Q with the firm's earlier filing; four measures (cosine, Jaccard, minimum edit distance, simple **(VERIFY)**); quintile sorts. Long non-changers / short changers earns up to 188 bp/month alpha (risk-factor section). EDGAR sample ends 2014. | Same | Firm-level; no public data file found |
| CXO Advisory summary of the paper | Extreme-quintile hedge returns 0.18–0.53%/month equal-weighted, 0.34–0.55% value-weighted; **most of the return from the short side**; warns of data snooping across the four measures | Same (summary) | — |
| Brown & Tucker (2011), *J. Accounting Research* **(VERIFY details)** | Year-over-year MD&A modification score | Related (earlier, MD&A only) | Firm-level |
| Adosoglou, Lombardo & Pardalos (2021), *Expert Systems with Applications* 164 | Neural-embedding ("semantic") similarity of 10-Ks; non-changers do better | Related (different measure) | Firm-level |
| Quantpedia / Brain data (Padysak) | Similarity of *positive* language only; sign reverses (low positive similarity does better) | Related — warning that sub-measures can flip | Firm-level, commercial |
| Advisor Perspectives practitioner study (June 2026) | Jaccard similarity of 10-Ks, EDGAR mid-1990s onward; says it held up after factor controls; strongest as a "value-trap filter" | Same idea, after publication | Portfolio results only |
| Open Source Asset Pricing (Chen & Zimmermann) | Checked `SignalDoc.csv` (331 signals): **no text-based signal** | Not available | — |
| WRDS SEC Analytics Suite — Bag of Words | Cosine, Jaccard, minimum edit distance "between current and previous filings"; 1993–2022 per a 2023 Stanford note **(VERIFY current coverage)**; web queries and server files at `/wrds/wrdsapps/sasdata/bagofwords/`; needs the SEC Analytics subscription | Same measures, ready-made — **if** "previous" means the same filing a year earlier | Firm × filing |
| Loughran–McDonald SRAF (Notre Dame) | Cleaned 10-X text 1993–2021 (44 GB zip), free for academic use | Raw input for building it ourselves | Text |

## Step 3 — Download or build ✅ (approved 2026-11-13)
- **Decision: Case 1, download from `wrdssec.bow_cossim`.** Sample: filings up to 2024-12-31 (where the table ends); evaluation ends 2024-12. 2025 filings may be computed later from `bow_2025` word counts if the signal looks worth it.
- **Case 1 (download):** WRDS Bag of Words similarity, if our account can reach it. Fast. Two checks before trusting it: (a) what each filing is compared with — the paper compares like with like; "previous filing" could mean last quarter's 10-Q; (b) coverage end date.
- **Case 2 (build):** text from SRAF (1993–2021) + EDGAR (2022–2025); compute similarity ourselves. Full control; weeks of work; downloads run on your computer (Claude's chat workspace can't reach SEC or SRAF).
- **Recommendation:** run the probe. If ready-made scores exist and compare like with like → Case 1, plus a hand check on ~20 filings. Otherwise Case 2, starting with 10-Ks only.
- **After run 1:** our account has the full SEC Analytics Suite, including Bag of Words (`wrdssec.bow_cossim`, `bow_filingsummary`, `bow_wordsummary`, yearly `bow_1993` … `bow_2025`).
- **After run 2 — updated recommendation: Case 1 (download) from `wrdssec.bow_cossim`.** It compares each 10-K with the firm's earlier 10-Ks, one year back per `lookback` step (1–16), and already has cosine, Jaccard and minimum edit distance. Gap: it ends with filings of 2024-12-31. For 2025 filings, either end the evaluation at 2024 or compute them later from `bow_2025` word counts (same method).

## Step 4b — Definition ✅ (approved 2026-11-13)
- **Decision: B — 10-Ks only (no amendments), each compared with the firm's previous 10-K (`lookback = 1`); the signal is `cosine`.** Chosen before seeing any returns. `jaccard` and `mineditdist` are pulled for data checks only, never as the signal. **Amended 2026-11-14 (Step 9, before any return test):** use `cosine_eng` (English words only) if, in each of 2010, 2011 and 2012, at most 30% of that year's bottom fifth are the largest fifth of firms; otherwise keep `cosine` and flag 2010–2013 values (`format_change_2010_13`; **extended to 2010–2014, `format_change_2010_14`, on 2026-11-14 after Step 9**). The build applies this rule and prints the evidence; `--measure` overrides it. 10-Qs may be added later if they are compared like for like (checked in Step 7).

Options as drafted:
- **A (recommended): cosine similarity, full filing, like for like.** Each 10-K vs the prior 10-K; each 10-Q vs the 10-Q for the same fiscal quarter a year earlier. Updates ~4×/year. Closest to the paper. Fields: CIK, form, period of report, filing date/time, accession, similarity (or text).
- **B: Jaccard similarity, 10-Ks only.** Simplest; one update a year; what the practitioner study used. Staler between filings.
- **C: risk-factors section (Item 1A) only.** The paper's strongest result, but needs section parsing, and Item 1A only exists from fiscal 2005 10-Ks **(VERIFY)**. Most work.
- **After run 2:** B is ready-made (`bow_cossim`, 10-K rows, `lookback = 1`). A depends on how `bow_cossim` handles 10-Qs (one more check; the first 200,000 rows were all 10-Ks). C would have to be built from `sec_item_words_freq` (word counts by section, incl. Item 1A) and that table ends May 2021 → drop C for now. **Updated recommendation: B now, with `cosine`** (pick one measure before looking at returns; `jaccard`, `mineditdist` and the English-words-only `*_eng` versions stay unused, or are named now as the only robustness checks). Add 10-Qs later if they turn out to be like for like.
- The saved file stores the continuous similarity. The screen itself (e.g. "drop the bottom 20% each month") is a backtest choice, not made here.
- Amendments (10-K/A, 10-Q/A): exclude; compare original filings only (`version = original`).

## Step 5 — Inventory ⏳ (proposed)
| Need | In panel? | Source if missing |
|---|---|---|
| permno, date, mthret, me, siccd | ✅ | — |
| gvkey | ✅ (11.5% null) | still link via CCM in Step 8 |
| CIK | ❌ | `wrdssec.wciklink_gvkey` ✔ found (1.09M rows; several sources per CIK with date ranges; Apple has 4 valid links) |
| Filing list (form, period, accession, filing date) | ❌ | `wrdssec.wrds_forms` ✔ found (27.4M rows; `fdate`, `accession`, `form`, `rdate` = period, `secadate`/`secatime` = SEC acceptance, `cik` as zero-padded text, `fname`, `wrdsfname`). 10-Ks ≈ 6,500–10,300/yr, 10-Qs ≈ 15,000–29,000/yr, 1996–2026 |
| Acceptance time | ❌ | `wrds_forms.secatime` ✔ (Apple: 06:01 and 08:05 → probably New York time; **VERIFY in run 2**). `comp.co_filedate` has times for only ~30% of 10-K/10-Q rows |
| Similarity (or text) | ❌ | `wrdssec.bow_cossim` ✔ found (21.0M rows; filings 1993-08 to 2024-12; carries its own `cik`, `accession`, `form`, `fdate`, `rdate`, `secadate`, `secatime`) |
| CCM link | ❌ | `crsp.ccmxpf_lnkhist` (capex already pulled `data/capex_intensity/ccm_links.parquet`; reuse or re-pull) |
- **Question for you:** anything on the shared drive that isn't in your local `data/` (EDGAR text, SRAF files)?

## Step 6 — Timing ✅ (approved 2026-11-13)
- **Decision:** `published_date` = `secadate` if accepted at or before 4:00 p.m. New York time; otherwise, or if there is no time (before 2003), the next trading day. **Amended 2026-11-14 (Step 9):** if `secadate` is after the EDGAR filing date or more than 4 days before it, use the EDGAR filing date with no time (next trading day). `date_source = exact`, `version = original`. Each month-end uses the latest 10-K with `published_date <=` month-end, at most 15 months old.

Notes as drafted:
- **Late-reported?** Yes. The text is knowable only once the filing is on EDGAR.
- **Exact date:** EDGAR acceptance time → `date_source = exact`. Team rule: accepted after 4:00 p.m. ET counts from the **next trading day**. Source: `secadate` + `secatime` (in `bow_cossim` itself and in `wrds_forms`). **Run 2 confirmed `secatime` is New York time** (and `comp.co_filedate` is UTC). Times exist for 100% of 10-K/10-Q filings from 2003, 64% in 2002, 0% before → before 2003, use the date only and count from the next trading day. In a sample of 177,720 recent (2020+) 10-K/10-Q filings, 55% were accepted between 4 and 6 p.m. and 62% after 4 p.m., so the after-close rule matters.
- **Date but no time:** tradable from the next trading day (timing guide §4); still `exact`.
- **No fallback lag:** no filing means no signal. EDGAR starts 1993–96, and a comparison needs a filing a year earlier, so the signal starts ~1996.
- **Monthly file:** latest similarity with `published_date <=` month-end. Open: how long a value stays valid if the next filing is late (proposal: until the next like-for-like filing, capped at 6 months for A, 15 months for B; decide in Step 8).

## WRDS check — run 1 (`probe_wrds.py`, 2026-11-12 20:34) ✅
Output: `data/lazy_prices/probe_output.txt`.
- **312 libraries** visible. SEC Analytics libraries: `wrdssec` (314 tables), `wrdssec_bow`, `wrdssec_secsa` (Bag of Words to 2024 only), `wrdssec_premium`, `wrdssec_all`, `wrdssec_common`, `wrds_sec_search`, samples `secsamp*`. Use `wrdssec`.
- **Bag of Words present:** `bow_cossim`, `bow_filingsummary`, `bow_wordsummary`, `bow_1993` … `bow_2025`. Columns not printed (script bug, below).
- **Possible section-level data:** `sec_item_scores`, `sec_item_scores_trans`, `sec_item_words_filings`, `sec_item_words_freq` — may make definition C (risk factors) feasible.
- **Filing list, CIK link, filing times:** see Step 5.
- **Ignore the run's summary line.** It said "Case 1 looks possible" because of false matches (PitchBook "similar company" tables, RavenPack news "event similarity"). Two script bugs, now fixed in `probe_wrds.py`: it treated `taqmsec` (trade data, 39,224 tables) as an SEC library, and ranked tables by column names, so `bow_cossim` was listed but not opened.

## WRDS check — run 2 (`probe_bow.py`, 2026-11-12 20:47) ✅
Output: `data/lazy_prices/probe_bow_output.txt`.
- **`wrdssec.bow_cossim`** (21.0M rows; `fdate` 1993-08-13 to 2024-12-31). One row per filing × `lookback` (1–16); `accession2` = the earlier filing compared with. Measures: `cosine`, `jaccard`, `jaccard_m`, `mineditdist`, and English-words-only `cosine_eng`, `jaccard_eng`, `jaccard_m_eng`, `mineditdist_eng`. Also `sample`, `form`, `wcnt`, `engwcnt`.
- **Apple's 2024 10-K** (0000320193-24-000123): `lookback` 1 → 2023 10-K (cosine 0.988), 2 → 2022 10-K (0.980), 3 → 2021, 4 → 2020, … 16 → 2009 10-K (0.753). So `lookback = 1` = last year's 10-K, as in the paper.
- **Still to check (fold into the Step 7 pull):** values of `sample` and `form` (10-Qs? amendments? 10-K405 / 10-KSB in early years); for 10-Qs, what `lookback = 1` points to.
- **`sec_item_scores`** (4.9M rows, 1995-01 to 2021-05): one row per filing × section, items include `1A`, `7`, `7A`, `WHOLE`; scores, not similarity. **`sec_item_words_freq`** (352M rows): word counts by filing × section — input for a risk-factor version, but only to 2021.
- **`bow_2024`** (742M rows): `accession`, `word`, `noccur` — the word counts behind the similarity; `bow_2025` exists, so 2025 could be computed the same way.
- **`bow_filingsummary`** (25.4M rows, 1980 to 2025-04): one row per filing of every form type (Form 4, 144, …); not needed.
- **Acceptance time:** see Step 6.

## Step 7 — Pull ✅ (version 3, final run 2026-11-13 21:42; details of versions 1–2 below, version 3 in Step 9)
Script: `signals/lazy_prices/pull_bow_cossim.py`. Saves to `data/lazy_prices/` (Git ignores it).

**Run 1 (2026-11-13 15:54; log kept as `pull_log_v1.txt`)** — all pulls saved:
- `bow_cossim_10k.parquet` 203,464 10-Ks (lookback 1), 26,778 firms; no duplicates; no missing or out-of-range cosine.
- `ciklink.parquet` 1,091,129 rows (948,714 are "No Link"; valid links from CRSP/Compustat Merged, Capital IQ, Compustat Company, Compustat Security, some flagged "Link with Name Mismatch").
- `ccm_links.parquet` 33,324 links. `trading_days.parquet` 8,307 days, 1993-01-04 to 2025-12-31 (248–254 a year).
- **Problem found: `lookback` counts amendments.** For 16.5% of 10-Ks, lookback 1 is an amendment (10-K/A etc.), often a short partial filing. Those rows have median cosine 0.923 vs 0.990 for original-vs-original, and they are **47% of the bottom fifth** (16.5% overall), so they would flood the avoid list. Original-vs-original rows are 9–15 months apart 94.5% of the time.
- **Missed forms:** the filter `^10-K` skipped small-business 10-Ks spelled without a hyphen (`10KSB` 30,015; `10KSB40` 2,469; `10KT405` 67 at lookback 1).
- **10-Qs (for later):** lookback 3 is ~12 months back for most 10-Qs, but amendments shift the count too, so 10-Qs would need the same "latest original" rule.
- Acceptance times: none before 2002, 22% in 2002, 100% from 2003; 51–64% of 10-Ks a year accepted after 4 p.m. Apple's 10-Ks 2019–2023 were accepted ~6 p.m. the day before their EDGAR filing date.
- Typical similarity dips in 2011–2012 (median 0.900 in 2012; in 2011 mainly the longest 10-Ks, median 0.800 in the top fifth by length) and 2023 (0.940): format changes hitting many filers at once.

**Version 2** — pulls lookback 1–4 for the whole 10-K family (`form ~ '^10-?K'`, no amendments) plus each compared filing's form and dates, so Step 8 can use each 10-K's most recent **original** 10-K. Run 2026-11-13 19:15 (`pull_log.txt`):
- `bow_cossim_10k.parquet` 807,259 rows = 236,104 10-K-family filings × lookback 1–4; 30,138 firms; no duplicates; no missing or out-of-range cosine. Forms: 10-K 187,052; 10KSB 30,016; 10-K405 15,952; 10KSB40 2,469; 10-KT 547; 10KT405 67; 10-KSB 1.
- An original 10-K exists among lookback 1–4 for 99.4% of filings (at lookback 1: 195,412; 2: 31,847; 3: 6,013; 4: 1,413). It is 9–15 months earlier for 94.0%; 3,747 are 0 months apart (two originals in one month).
- With the 9–15-month rule: 220,641 filings, median cosine 0.989. **34% of the bottom fifth differs from version 1's**, which shows how much the amendment problem mattered. Small-business forms are 12.6% of filings and 11.6% of the bottom fifth (no tilt).
- Links: 83.6% of the 220,641 filings have a "Valid CIK-GVKEY Link" (log, over all 234,685: 82.3% valid, 84.1% including "Name Mismatch"). 2.4% of CIKs with valid links map to more than one gvkey. Capital IQ links mostly lack dates (89%).
- Other files unchanged from run 1.

## Step 8 — Construct ✅ (runs 2026-11-13 21:23 and 21:44; one more run for the 2010–2014 flag, see Next)
1. **Filings:** every original 10-K-family filing (10-K, 10-K405, 10-KT, 10KSB, 10KSB40, 10KT405), compared with its most recent original 10-K among lookback 1–4, **only if that one was filed 9–15 months earlier**; otherwise no value. → 220,641 filings.
2. **Signal:** `filing_sim` = that `cosine`. Low = "changer". No winsorizing or ranking in the file; ranking happens in the backtest.
3. **`published_date`:** first trading day on or after `secadate` if accepted at or before 4:00 p.m. New York time; otherwise, or with no time (before 2003), the first trading day after `secadate`. `period_end` = `rdate` (fiscal year end). `date_source = exact`, `version = original`, `source = wrdssec.bow_cossim`.
4. **CIK → gvkey:** "Valid CIK-GVKEY Link" rows only (not "Name Mismatch"). Prefer a link whose dates contain the filing date, in this order: CRSP/Compustat Merged, Compustat Security, Compustat Company, Capital IQ. If more than one gvkey is still possible, drop the filing and count it.
5. **gvkey → permno:** CCM per `wrds_guide.md` §5 (`LU`/`LC`, `P`/`C`), link window containing `published_date`.
6. **Event file** `data/lazy_prices/lazy_prices_events.parquet`: `permno, gvkey, period_end, published_date, date_source, source, version`, plus inputs `cik, accession, form, filing_sim, accession_prev, fdate_prev, months_apart, lookback_used, secadate, secatime`.
7. **Monthly file** `data/lazy_prices/lazy_prices_monthly.parquet`, built on the panel's (permno, month-end) rows: latest event with `published_date <=` month-end and at most 15 months old. Columns `permno, gvkey, date, filing_sim, period_end, published_date, date_source, source`, plus `applies` = `stock` / `n/a (ETF)`.
8. **ETFs:** the panel has no ETF flag. Needs one small extra pull: CRSP security types (`crsp.stksecurityinfohist`, `securitysubtype = 'ETF'`), per `wrds_guide.md`.
9. **Splits:** not needed. `filing_sim` comes from text only (no prices or share counts), so splits cannot move it. Shown with one split in Step 9.

**Scripts:** `pull_security_info.py` (WRDS, ~1 min: CRSP security types and ticker history → `data/lazy_prices/security_info.parquet`), then `build_lazy_prices.py` (no WRDS; ~1 min → `lazy_prices_events.parquet`, `lazy_prices_monthly.parquet`, `build_log.txt`).

**How the rules were implemented (details beyond the approved list):**
- Item 4: if a CIK has exactly one valid gvkey, it is used whatever the link's dates (97.6% of CIKs); the dated CCM link in item 5 then decides whether it is a CRSP stock on that date. Link dates only decide between several gvkeys.
- Item 3: accepted at exactly 4:00:00 p.m. counts as before the close. If WRDS has a time but no acceptance date (6 events, 2020), the EDGAR filing date is used with that time (can only make the date later, never earlier).
- `period_end` after the acceptance date is impossible (WRDS `rdate` error, 2 events) → set to missing; `rdate` is missing for 8 more.
- Two filings for the same permno on the same published date → keep the later filing (145 dropped).
- Monthly `gvkey`: the event's linked gvkey when there is a value, otherwise the panel's.

**Test run on a copy of the real data (claude.ai workspace, stand-in ETF file):** 220,641 kept filings → 182,809 linked to a gvkey (36,165 with no valid CIK link; 1,667 ambiguous) → 126,301 linked to a permno (35,052 gvkeys with no CCM link at all, mostly non-CRSP filers: small-business 10-Ks are 28% of these vs 3% of kept; 21,456 with a CCM link far from the filing date, median 4.3 years) → **126,156 events, 14,970 permnos**. 0 duplicates; 0 `published_date` before `period_end`; 10 missing `period_end`; 0% `assumed`. Median 75 days from fiscal year end to `published_date`; 61% of timed filings move to the next trading day. Monthly file: one row per panel row (2,796,065), 0 duplicates; **78–92% of the panel's stock rows have a value in 1999–2024, 84–90% in most years** (5–39% in 1995–97 and 72% in 1998 while EDGAR phases in; 78–80% in 1999–2000 and 2021–22; 48% in 2025, as filings end in 2024). Linked gvkey equals the panel's gvkey in 99.75% of rows where both exist. The panel seems to contain no ETFs (SPY, QQQ absent) — the security pull will confirm. Unit tests passed for the timing rule (before/at/after 4 p.m., Friday after close, Saturday, July 4 holiday, no time, no date) and the 15-month cap.

**Real run (2026-11-13 21:23, `build_log.txt`):** identical to the test run: 126,156 events, 14,970 permnos; monthly file 2,796,065 rows, 0 duplicates. `pull_security_info.py`: 191,048 rows, 40,518 permnos; SPY, QQQ, IWM, GLD all `FUND`/`ETF`; 6,933 ETF permnos in CRSP, **0 in the panel** → 0 rows marked n/a (correct: the panel holds common stocks only).

## Step 9 — Validate ✅ (final run 2026-11-13 21:45: 6 PASS, check 7 = CHECK by design → flagged; flag extended to 2010–2014 on 2026-11-14)
Script: `signals/lazy_prices/validate_lazy_prices.py` (no WRDS) → `data/lazy_prices/validate_log.txt`. Run in the claude.ai chat on copies of the Step 8 files.

**Failure 1 — dates (check 3).** For 63,884 of the 236,104 pulled 10-Ks (mostly filed 1994–2002), WRDS's acceptance date (`secadate`) is *after* the EDGAR filing date, which is impossible for an original filing (EDGAR dates a filing when it accepts it). It looks like a later re-processing date. The approved rule trusted it, so 34,644 events got a published_date 1 day to 8 years too late (Lockheed's 1996 10-K appeared as 2004 news).
- **Proposed fix (changes the approved Step 6 rule):** if the acceptance date is after the EDGAR filing date, or more than 4 days before it, use the EDGAR filing date with no time (first trading day after it). Tested: 33,574 events move earlier (median 2 days); every published_date is then −3 to +7 days from the filing date; 126,276 events. The event file records the basis of each date (`published_basis`).

**Failure 2 — a filing-format change in 2010–2013 (check 7).** The median 10-K grew from ~53,000 words (2010) to 161,000 (2012) and ~200,000 from 2013; it doubled for 59% of firms in 2012, and the English-word share fell from 95% to 85% (added tokens are mostly not English words — consistent with machine-readable XBRL data in the submission, not confirmed). The change reached the largest firms first: their median `filing_sim` fell to 0.718 (2011) and 0.632 (2012) vs ~0.99 normally, and 52–57% of each year's bottom fifth in 2010–2012 were the largest fifth of firms (20% if no tilt; 9% in 2013). Apple's, Microsoft's and Boeing's lowest-ever values are 2010–2012. For a value-weighted avoid screen, those years would mostly avoid big firms for a format reason.
- **Proposed fix:** re-pull the English-words-only versions WRDS provides (`cosine_eng`, plus `jaccard_eng`, `mineditdist_eng` for checks) and compare by year and firm size — **without looking at returns**. If `cosine_eng` removes the 2010–2013 tilt, switch the signal to `cosine_eng` (a data-quality change, documented before any return test). If not, flag 2010–2013 months so the backtest can treat them separately.

**Implemented 2026-11-14:** `pull_bow_cossim.py` version 3 adds `cosine_eng`, `jaccard_eng`, `mineditdist_eng` (earlier logs kept as `pull_log_v1.txt`, `_v2.txt`). `build_lazy_prices.py` applies fix 1 (column `published_basis`) and rule 10 (columns `cosine`, `cosine_eng`, `measure` in the event file; `format_change_2010_13` in the monthly file only if `cosine` is kept). `validate_lazy_prices.py` check 7 now reports the measure and the size tilt. Tested in the claude.ai chat: pull v3 on a stand-in database; build + validate on copies of the real data — without `cosine_eng` (keeps `cosine`, tilt 57–63% in 2010–2012 using panel market values, 161,023 monthly rows flagged, check 7 = CHECK), with a made-up untilted `cosine_eng` (switches, check 7 = PASS), with a made-up tilted one (keeps `cosine`), and with `--measure` overrides.

**Final run (2026-11-13: pull v3 21:42, build 21:44, validate 21:45; logs `pull_log.txt`, `build_log.txt`, `validate_log.txt`):**
- Pull v3: 807,259 rows, now with `cosine_eng`, `jaccard_eng`, `mineditdist_eng`.
- Rule 10: `cosine_eng` is tilted just like `cosine` (largest fifth = 57%, 64%, 63% of the bottom fifth in 2010–2012 vs 57%, 63%, 62%) → **`filing_sim` = `cosine`; 161,023 monthly rows flagged `format_change_2010_13`.** English-only words do not remove the format effect.
- Build: 126,276 events (14,981 permnos); `published_date` basis: 35,199 same day (accepted by 4 p.m.), 56,059 next trading day (after 4 p.m.), 34,774 EDGAR filing date (acceptance date unusable), 244 acceptance date without time. 47.2% of all stock rows (85.1% in 1998–2024) have a value.
- Validate: checks 1–6 PASS; check 7 CHECK (values in [0, 1]; the 2010–2012 tilt is handled by the flag).
- **Observation (2014):** the lowest tenth of similarity is still low in 2014 (10th percentile 0.80, like 2013's 0.79; ~0.95–0.97 in 2008–2010 and 2015–2017), while the large-firm tilt is gone (17%). The format change seems to reach the low tail of smaller firms through 2014. The approved flag covers 2010–2013 only — see Open questions.

**Checks that passed (with fix 1 applied):** 0 duplicates; monthly file = the panel's rows exactly; 85.1% of 1998–2024 stock rows have a value (missing: 64.6% before a stock's first comparable pair of 10-Ks, 26.3% never linked — a third of those also lack a gvkey in the panel —, 9.1% older than 15 months; foreign companies 57 rows); 0 published_date before period_end, 0% assumed, 11 missing and 41 doubtful period_ends (e.g. Western Alliance's 2011 10-K has rdate 2001-12-31); ticker change FB → META (permno 13407) keeps gvkey and values, and ticker FB was later reused by a ProShares fund (permno 26867); NVIDIA's June 2024 10-for-1 split: price 0.11×, filing_sim unchanged; ETFs: 0 in panel; filing_sim within [0, 1].

## Step 10 — Save ⏳ (catalog row ✅; your part below)
- **Flag extended to 2010–2014** (approved 2026-11-14): `build_lazy_prices.py` now writes `format_change_2010_14`. Tested on a copy of the real v3 data: identical events and `filing_sim`; 198,837 monthly rows flagged (was 161,023); validation 6 PASS + check 7 CHECK (handled by the flag).
- **Catalog row ✅** appended to `public_data/factor_catalog.csv` as approved (`filing_sim`, category `text`, have-data, not in panel, 1994-12 to 2025-12, added_by raghavrc, 2026-11-13); the existing 26 rows are unchanged.
- **Storage:** WRDS data is licensed, so nothing goes to `public_data/`. Keep `data/lazy_prices/` locally and upload `lazy_prices_monthly.parquet` and `lazy_prices_events.parquet` to the team's shared drive.
- **Commit (never `data/`):** `signals/lazy_prices/` (`probe_wrds.py`, `probe_bow.py`, `pull_bow_cossim.py`, `pull_security_info.py`, `build_lazy_prices.py`, `validate_lazy_prices.py`, `progress.md`) and `public_data/factor_catalog.csv`.

## Open questions
- Long-only value is capped by benchmark weights. If changers are mostly small firms, avoiding them does little for a value-weighted fund → backtest both equal- and value-weighted.
- Pick one similarity measure before looking at returns (data snooping).
- Paper's data end in 2014 → treat 2015–2025 as the out-of-sample test.
- Similarity levels shift in some years (2011–2012, 2023) for many firms at once → rank within each month (as planned). Step 9 confirmed 2010–2012 is dominated by large firms (flagged). **Decided 2026-11-14: flag extended to 2014** (10th percentile still 0.80; data-quality decision before any return test) → `format_change_2010_14`, 198,837 monthly rows. 2023 (median 0.94) shows no size tilt (largest fifth = 23% of the bottom fifth; 19–25% in 2017–2024), so it is not flagged.
- Small-business forms (`10KSB`, `10KSB40`; filed until 2009): kept (Step 8 item 1, approved 2026-11-13).

## Next
1. Re-run (no password), from the repo root with the `.venv` active:
   `python signals\lazy_prices\build_lazy_prices.py` then `python signals\lazy_prices\validate_lazy_prices.py`
2. Upload `data/lazy_prices/lazy_prices_monthly.parquet` and `lazy_prices_events.parquet` to the shared drive.
3. Commit and sync per SETUP.md "Save and upload your work" (files listed in Step 10). Suggested message: `Add lazy_prices (filing_sim) signal: scripts, progress notes, catalog row`.
4. Later: backtest as an avoid screen (equal- and value-weighted; with and without `format_change_2010_14` months; 2015–2024 as the out-of-sample test).
