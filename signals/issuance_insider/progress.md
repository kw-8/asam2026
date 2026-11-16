# issuance_insider — progress

Started: 2026-11-14 · Process: `prompts/data_acquisition.md`

**Status (2026-11-16):** Both signals built and validated: **`net_issuance`** (1980–2025; validation 9 PASS) and **`insider_cluster`** (2006–2025; validation 8 PASS; all 17 hand-checked Form 4s match). **Step 10:** both catalog rows written to `public_data/factor_catalog.csv` (2026-11-15, one row per signal). **Left for you:** (a) upload the data files to the team's private drive (ask the teammate who shared the panel where it is); (b) commit and sync (see "Next"); (c) the library e-mail about LSEG insider access, if not sent. Backtest done 2026-11-16 and re-run after the share-class fix (`net_issuance` now firm level; see `backtest.md`).

## Summary — `net_issuance` (signal 1 of 2)
- **Signal:** `net_issuance` — the 12-month log change in a firm's split-adjusted shares outstanding. **Positive = net issuer, negative = net buyer-back.**
- **Definition:** `ln(adj[t−4] / adj[t−16])`, adj = CRSP `shrout × mthcumfacshr` (CIZ `crsp.msf_v2`), at each panel month-end *t*. The 4-month skip ensures the share counts were public (see timing). No value unless every month of the window has a CRSP price. **Firm level (since 2026-11-16):** a firm with 2+ listed share classes gets one value for all its classes — the log change in its total units, each class valued at its month-*t* price (per-class value kept in `net_issuance_class`).
- **Citation:** Pontiff, J., & Woodgate, A. (2008). Share Issuance and Cross-sectional Returns. *Journal of Finance*, 63(2), 921–945. doi:10.1111/j.1540-6261.2008.01335.x. Related: Fama & French (2008), *JF* 63, 2971–95 (net share issues); Daniel & Titman (2006), *JF* 61 (composite issuance); Ikenberry, Lakonishok & Vermaelen (1995), *JFE* 39 (underreaction to buybacks).
- **Intuition:** managers know more about their firm than the market. They sell new shares when they think the stock is expensive and buy shares back when they think it is cheap; investors underreact, so prices adjust slowly. Net issuers tend to do worse afterwards and net buyers-back better. Slow-moving: the share count changes over a year or more.
- **How ASAM can use it (long-only):** tilt toward net buyers-back and away from heavy issuers; and, as planned, combine with `insider_cluster` (C1: buyer-back **and** insider cluster buy; C2: average rank) — the firm's money and the insiders' own money pointing the same way.
- **Timing (the main finding):** CRSP dates many share counts at the fiscal quarter end (balance sheet), weeks before the 10-Q/10-K that reports them is public. Measured on 518,903 share changes 2003–2025: with a 1-month skip, 34–56% would be used before public; 2 months 6–24%; 3 months 1–4.5%; **4 months under 1%** → primary uses 4. A no-skip version (as JKP) would flatter exactly the buyers-back a long-only fund buys.
- **Files:** `data/issuance_insider/net_issuance_monthly.parquet` (one row per panel row: `permno, gvkey, date, net_issuance, period_end, published_date, date_source, source, applies` + named checks `comp_issuance, net_issuance_5y, net_issuance_skip3, net_issuance_skip6, net_issuance_pit` with their dates) and `net_issuance_events.parquet` (one row per share-count change, with its filing date where matched). Not tested for returns here, by design.
- **Named checks (fixed before any return test; the primary is never swapped for whichever looks best):** `net_issuance_skip3` (3-month skip), `net_issuance_skip6` (6-month skip, as OSAP), `net_issuance_pit` (each share count dated by its 10-K/10-Q's public time where matched), `comp_issuance` (Daniel–Titman 1-year composite issuance, counts dividends as payout), `net_issuance_5y` (5-year change).
- **Known limitations:** (1) timing is a fixed, measured lag (`assumed`); before 2003 it could not be measured (no EDGAR match) and 10-K deadlines were slower then (90 days), so a few early-year counts may still be used before public; the 6-month check guards against this. (2) SPACs are in the panel; their trust redemptions look like large buybacks → backtest with and without SIC 6770. (3) Share changes from mergers paid in stock count as issuance (as in the paper; CRSP's 1980s–90s TSOO/SP events). (4) 88.7% of panel rows have a value (new listings need 16 months). (5) `version = original` assumes CRSP does not revise share history (VERIFY). (6) OSAP `ShareIss1Y` cross-check not yet run (optional).

## Differences from the source (Pontiff & Woodgate 2008)
| | Paper | Here |
|---|---|---|
| Measure | ln(adj. shares *t*) − ln(adj. shares *t*−11) | ln(adj. shares *t*−4) − ln(adj. shares *t*−16): a full 12 months, skipping the latest 4 |
| Timing | shares as of month *t* in the formula (OSAP's replication skips 6 months) | 4-month skip chosen from a measurement of when CRSP's share counts became public; 3- and 6-month and exact-date versions as checks |
| Data | CRSP (legacy `shrout`, share-adjustment factor) | CRSP CIZ `msf_v2` (`shrout × mthcumfacshr`; direction verified on 24,185 split months) |
| Data quality | — | price rule: no value if any month of the window has no CRSP price (unrecorded splits while off-exchange, e.g. Delcath 2019–20) |
| Sample | predictive after 1970, not before (published 2008) | 1980-01 to 2025-12 (2008–2025 is after publication) |
| Share classes | — | firm level: one value per firm across its listed classes (2026-11-16; per-class values let class conversions look like buybacks, e.g. Berkshire A → B) |
| Use | cross-sectional return prediction (long-short) | long-only tilt for ASAM, and half of the planned combination with insider cluster buying |

## Idea (user's words)
"I want to look into a combination of net share issuance and insider cluster buying."

## Step 0 — Ready ✅
- Local `main` = GitHub `main` = b080bff (lazy_prices commit; checked 2026-11-14, no newer commits on GitHub). Merge `origin/main` again before pulling data if a few days pass.
- Panel present: `data/crsp_monthly_ratios_clean.parquet` (364 MB; 1980-01 to 2025-12).
- `capex_intensity` remains paused at Step 7 (separate example).

## Step 1 — Hypothesis ✅ (approved 2026-11-14: two separate signals; build `net_issuance` first, then `insider_cluster`, then test the combination)

**Decision (user, 2026-11-14):** build two separate signals; combine them only in the backtest (option B below). Safeguard against data snooping: the combination rules are named now, before any return is seen.

### Signal 1 — `net_issuance` (name provisional)
- **A (driver):** change in split-adjusted shares outstanding over the past year (exact window in Step 4b).
- **B (target):** next-month returns, also 1–12 months.
- **C (direction, mechanism):** more issuance → lower future returns; net buybacks → higher. Managers sell shares when they think the stock is expensive and buy back when cheap; investors underreact. Slow signal (a year or more).
- **Predictive, not reactive:** firms tend to issue after price run-ups → backtest controls for momentum and `bm`. Share counts dated from when they were reported (Step 6).
- **Universe:** stocks only; ETFs `n/a` (share counts move with investor creations/redemptions).

### Signal 2 — `insider_cluster` (name provisional)
- **A (driver):** several insiders (officers, directors) buying shares on the open market within a short window (Form 4). Window, minimum number of insiders and any routine-trade filter in Step 4b.
- **B (target):** next-month returns, also 1–12 months (most of the effect expected in the first months).
- **C (direction, mechanism):** recent cluster buy → higher future returns. Insiders know more than the market; several buying at once filters out one person's private reasons.
- **Predictive, not reactive:** insiders tend to buy after price falls and in value stocks → backtest controls for short-term reversal and `bm`. Dated by Form 4 filing (after-close rule), never trade date (Step 6).
- **Universe:** stocks only; ETFs `n/a` (no corporate insiders).

### Combination (backtest only; named now, before any return test)
- **C1 — confirmation flag:** net shrinker (net issuance < 0) **and** a cluster buy in the recent window.
- **C2 — average rank:** mean of each month's cross-sectional rank of −`net_issuance` and of `insider_cluster`.
- Only C1, C2 and each signal alone are tested. Any other combination is a new hypothesis and recorded as such.

### Storage and order (approved; names `net_issuance` and `insider_cluster` kept as no change was asked)
- One folder `signals/issuance_insider/`; **two monthly files and two catalog rows**, each with its own `period_end`, `published_date`, `date_source`, `source` (different data and dates). The backtest joins them on `permno` + `date`.
- Build **`net_issuance` first** (simpler, covers almost every stock, real split adjustment), then `insider_cluster` (new database; individual trades aggregated to firm-months). Step 2 searches both at once.

### Original draft (before the decision)
- **A (driver):** two signals from the people who know the firm best, with different money at stake:
  1. **Net share issuance** — change in split-adjusted shares outstanding over the past year. Negative = the firm is buying back (its own money says "cheap"); positive = issuing.
  2. **Insider cluster buying** — several insiders (officers, directors) buying shares on the open market with their own money within a short window (SEC Form 4).
- **B (target):** next-month stock returns (also 1–12 months).
- **C (direction, mechanism):** firms that are shrinking their share count *and* have a recent insider cluster buy earn higher future returns than either signal alone. A buyback alone can be cheap talk; insiders buying with personal money make it credible; several insiders buying at once filters out one person's private reasons (taxes, liquidity). Horizons differ: insider news is fast (weeks to months), issuance is slow (a year or more).
- **Use for ASAM (long-only):** a **buy list** (the mirror image of the lazy_prices avoid screen).
- **Predictive, not reactive:**
  - Insiders tend to buy after price falls and in value stocks; firms tend to issue after run-ups. The signal could just repeat past returns or book-to-market → the backtest must control for reversal, momentum and `bm`.
  - Everything dated when it became public (Form 4 filing date, not trade date; share counts from when they were reported) → Step 6.
- **Universe:** stocks only. ETF share counts move with investor creations/redemptions, not management's view, and ETFs have no corporate insiders → `n/a`, not dropped. (Panel has no ETFs.)
- **Catalog check:** nothing similar (26 panel ratios + `filing_sim`). Note for Step 5: panel has `shrout` but no share-adjustment factor (`mthcumfacshr`), so splits can't be removed from the panel alone.

### How to combine (pick one before any return test)
- **A. Confirmation flag (recommended).** Hypothesis = "both agree". Save both parts as columns plus a flag when both point up (net shrinker + cluster buy in the last few months). One clear test; each part can still be checked alone. Risk: rare and small-cap heavy → count names per month in Step 9.
- **B. Two separate signals, combine later.** Most flexible, but leaves the key choice open until returns are seen (data-snooping risk).
- **C. Composite score** (average rank of −issuance and insider buying). Covers every stock, but most firms have no insider buys in a given month, so for them it is just issuance.

### Literature seen so far (full table in Step 2)
- Pontiff & Woodgate (2008), *JF* 63(2), 921–945 — share issuance predicts returns post-1970.
- Kang, Kim & Wang (2018), "Cluster Trading of Corporate Insiders" (working paper) — cluster purchases earn about twice the 21-day abnormal return of single purchases.
- Babenko, Tserlukevich & Vedrashko (2012), *JFQA* 47(5), 1059–1088 — buyback announcement returns are higher after insider purchases; insider purchases predict post-announcement returns.
- Cziraki, Lyandres & Michaely (2021), *J. Corporate Finance* 66 — insider net buying rises before buybacks and falls before SEOs.
- Cohen, Malloy & Pomorski (2012), *JF* 67(3), 1009–1043 — routine insider trades carry no information; opportunistic ones do.
- Lakonishok & Lee (2001) — insider signal much stronger in small stocks.

## Step 2 — Search (`net_issuance`) ✅ (approved 2026-11-14)
| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Pontiff & Woodgate (2008), *JF* 63(2) 921–945, doi:10.1111/j.1540-6261.2008.01335.x | ISSUE = ln(adjusted shares_t) − ln(adjusted shares_t−11); adjusted shares = CRSP shares outstanding with CRSP's share-adjustment factor. Predicts returns after 1970, not before. | **Same** (the reference definition) | Firm-level (no data file) |
| Fama & French (2008), "Average Returns, B/M, and Share Issues," *JF* 63, 2971–95 | Net share issues: change in log split-adjusted shares from fiscal year-end t−2 to t−1, used from June of t | Same idea, annual fiscal-year timing | Firm-level (no data file) |
| Ken French Data Library — "Portfolios Formed on Net Share Issues" (+ "25 Portfolios Formed on Size and Net Share Issues") | FF (2008) NI; sorted each June with NYSE breakpoints; NI < 0, NI = 0, quintiles, deciles; monthly from July 1963 | Same idea | **Factor/portfolio returns only** (comparison) |
| Open Source Asset Pricing `ShareIss1Y` (Chen & Zimmermann; checked `SignalDoc.csv` and `ShareIss1Y.py`) | Growth in split-adjusted shares from t−18 to t−6 (i.e. skips the latest 6 months); shares = `shrout × cfacshr` in the code (SignalDoc text says `shrout/cfacshr` — a typo, the code multiplies) | **Same** (PW replication) | **Firm-level** (permno, yyyymm) + portfolio returns |
| OSAP `ShareIss5Y` (Daniel & Titman 2006) | 5-year growth in split-adjusted shares | Related (longer window) | Firm-level |
| Daniel & Titman (2006), *JF* 61, 1605–43 — composite equity issuance; OSAP `CompEquIss` | 5-year growth of market equity minus 5-year stock return (catches stock-paid mergers, employee stock, and dividends) | Related (broader) | Firm-level |
| JKP Global Factor Data (`bkelly-lab/jkp-data`, theme "Issuance") | `chcsho_12m` = shares × adjustment factor ÷ same 12 months earlier − 1 (no skipped months); also `chcsho_1m/3m/6m`; `eqnpo_12m` = 12-month net payout (log return-index growth minus log market-equity growth; the opposite of composite issuance) | `chcsho_12m` **same**; `eqnpo_12m` related | Firm-level via WRDS (`contrib_global_factor`, **VERIFY**) + factor returns on jkpfactors.com |
| Bradshaw, Richardson & Sloan (2006), *JAE* — OSAP `NetEquityFinance` | Cash-flow statement: (sale of stock `sstk` − purchase of stock `prstkc`) ÷ average total assets | Related (dollars, not share count; annual accounting data) | Firm-level |
| Boudoukh et al. (2007), *JF* — OSAP `NetPayoutYield` | (dividends + buybacks − issuance) ÷ market equity | Related (valuation) | Firm-level |

**What the search shows**
- The idea is well established and ready-made versions exist (OSAP, JKP), so Step 3 is a real choice between downloading and building.
- **Sources disagree on timing:** JKP uses the change up to the current month; OSAP skips the latest 6 months; Fama-French use fiscal-year-end shares and wait until June. This is the main Step 6 question: when is a change in CRSP shares outstanding actually public? (PW note that CRSP builds shares outstanding from company reports.)
- **Split adjustment is the core of the signal:** raw `shrout` jumps at every split. CIZ equivalent of `cfacshr` is `mthcumfacshr` (`wrds_guide.md` §3; direction still **VERIFY** on a known split).
- No issuance effect before 1970 (PW; FF find the same for 1927–1963). The panel starts 1980, so not an issue.

## Step 3 — Download or build (`net_issuance`) ✅ (approved 2026-11-14: Case 2, build from CRSP)
- **Decision:** build from CRSP CIZ monthly data (`crsp.msf_v2`: shares outstanding + share-adjustment factor).
- Why: CIZ-only rule (OSAP/JKP files are built by others from their own CRSP cuts); we set the timing ourselves (the main open issue, Step 6); data through 2025-12; one short query.
- OSAP `ShareIss1Y` (firm-level download) kept as a **Step 9 cross-check** only (rank correlation with ours, after aligning its 6-month skip). Firm-level OSAP files go to the drive, not GitHub.

## Step 4b — Definition (`net_issuance`) ✅ (approved 2026-11-14: A primary; B and C built as named robustness columns)
All three use only CRSP monthly data. Pick one now as **the** signal, before any return is seen; the others may be named now as the only robustness checks.

- **A. 12-month log change in split-adjusted shares (Pontiff & Woodgate 2008) — recommended.**
  `net_issuance_t = ln(shrout_t × mthcumfacshr_t) − ln(shrout_t−12 × mthcumfacshr_t−12)`
  - Positive = net issuer, negative = net buyer-back, 0 = no change (a large group; Ken French reports NI = 0 separately).
  - Log change (as PW): symmetric for issuing and buying back, and dampens huge jumps.
  - Full 12 months (as JKP; PW's formula spans t−11 to t). Which recent months to skip for reporting delay is a **Step 6** decision, not part of the definition.
  - Counts every reason the share count changes (offerings, buybacks, stock-paid mergers, employee stock), as in the papers.
  - Security level (`permno`), as in the papers; dual-class firms are measured per share class.
  - Fields: `permno`, `mthcaldt`, `shrout`, `mthcumfacshr` (`crsp.msf_v2`). Factor direction (multiply vs divide) confirmed on a known split in Step 7.
- **B. 12-month composite issuance (Daniel & Titman 2006, 1-year version; JKP `eqnpo_12m` with the sign flipped).**
  `ι_t = ln(ME_t / ME_t−12) − ln(total-return growth t−12 → t)`
  - Also treats dividends as a payout, so it measures all money flowing between the firm and its shareholders, not only the share count.
  - Needs **no split adjustment** (a split leaves market value unchanged).
  - Fields: `me`, `mthret` (already in the panel).
  - Broader than the approved hypothesis (share count) → best as a robustness check.
- **C. 5-year log change in split-adjusted shares (Daniel & Titman 2006; OSAP `ShareIss5Y`).**
  - Slower and steadier; needs 5 years of history, so younger firms have no value. Fields as A.
  - Different horizon from the approved hypothesis (past year) → robustness check at most.

**Recommendation:** A as the signal. Name B now as the only robustness check (free: built from panel columns). Drop C unless you want it.

**Decision (user, 2026-11-14): build A, B and C, each as its own column** — setup below approved 2026-11-14:
| Column | Definition | Role |
|---|---|---|
| `net_issuance` | A: 12-month log change in split-adjusted shares | **Primary** — the hypothesis; used in combination rules C1 and C2 |
| `comp_issuance` | B: 12-month composite issuance (log ME growth − log total-return growth) | Named robustness check |
| `net_issuance_5y` | C: 5-year log change in split-adjusted shares | Named robustness check |
- All three named **now**, before any return is seen. The backtest reports all three side by side; the primary is never swapped for whichever looks best.
- C1 / C2 use `net_issuance` only (adding B and C to the combinations would triple the number of tests).
- One monthly file, three columns, one set of date columns: all three depend on share counts, so they share the Step 6 timing rule.
- Missing-value rules (Step 8): A needs adjusted shares > 0 at both ends; B needs market value at both ends and all 12 monthly returns; C needs adjusted shares at both ends 60 months apart. No winsorizing in the file.
- Pull window (Step 7): CRSP from 1974 so that C has values from 1980 and any skipped months (Step 6) are covered.
- Catalog (Step 10): one row per column, with B and C marked "robustness for `net_issuance`".

## Step 5 — Inventory (`net_issuance`) ✅ (approved 2026-11-14; nothing extra on the shared drive)
| Need | Used by | In panel / local `data/`? | Source if missing |
|---|---|---|---|
| `permno`, `date` (month-end), universe of stock rows | all | ✅ panel (2,796,065 rows, 1980-01 to 2025-12) | — |
| `shrout` (thousands) | A, C (and ME for B) | ⚠️ panel has it, but **only from 1980**; A needs 1979 and C needs 1975 for the first panel year (plus any months Step 6 skips) | `crsp.msf_v2`, 1974-01 to 2025-12 |
| **Share-adjustment factor** `mthcumfacshr` | A, C | ❌ not in panel (panel has `vol_adj` but not the factor) | `crsp.msf_v2` |
| `mthret` (total return), price → `me` | B | ⚠️ panel has `mthret`, `prc`, `me`, **only from 1980** | `crsp.msf_v2` (`mthret`, `mthprc`); cross-check vs panel `me`/`mthret` in Step 9 |
| When each share count took effect, and its source | Step 6 timing | ❌ | CRSP CIZ share-history table (StkShares; WRDS name and columns **VERIFY** in Step 7) |
| Split / distribution events (dates, share factors) | factor-direction check (Step 7), split trace (Step 9) | ❌ | CRSP CIZ distributions table (StkDistributions; WRDS name **VERIFY** in Step 7) |
| ETF flag, ticker history | ETFs `n/a`; ticker-change trace (Step 9) | ✅ `data/lazy_prices/security_info.parquet` (191,048 rows, 40,518 permnos, 1925–2025; 6,933 ETF permnos, **0 in the panel**) | reuse |
| `gvkey` | key column | ⚠️ panel has it (11.5% null) | ✅ reuse `data/lazy_prices/ccm_links.parquet` (33,324 LU/LC, P/C links; identical copy in `capex_intensity/`) |
- **One source for A, B and C:** pull `shrout`, `mthcumfacshr`, `mthret`, `mthprc` from `crsp.msf_v2` for 1974–2025 rather than mixing pulled 1974–79 rows with panel rows; the panel is used for the row universe and as a cross-check.
- Not usable: `crsp_last_3_yrs.csv` in the ASAM folder outside the repo (3 years only).
- **Question for you:** anything on the shared drive that isn't in your local `data/` (e.g. a CRSP monthly file with adjustment factors, or a share-history pull)? → **No** (user, 2026-11-14).

## Step 6 — Timing (`net_issuance`) ✅ (approved 2026-11-14: option 1 as primary + option 2 as a named check)

**Decision (user, 2026-11-14):** both.
- **Primary (option 1):** skip 1 month — signal at month-end *t* uses share counts at end of *t*−1 and *t*−13 (C: *t*−61; B over the same window). Step 7 measures, on 2003–2025, how far CRSP's `OBS` share changes are dated before the 10-Q/10-K that reported them was public. If more than ~5% would still be used before public with 1 month, the primary moves to a **2-month** skip — decided before any return is seen.
- **Named check (option 2):** extra column `net_issuance_skip6` = A with a 6-month skip (share counts at *t*−6 and *t*−18, as OSAP), plus `period_end_skip6` = month-end *t*−6. For A only (not B or C), to keep the number of tests small. `published_date` is month-end *t* for both versions; only `period_end` differs.
- `net_issuance_skip6` must equal `net_issuance` shifted 5 months within each permno (4 if the primary moves to 2 months) → a free consistency check in Step 9.
- Why (professional view): option 1 mirrors live trading (you would hold the latest 10-Q/10-K share count) and is verified with data; the look-ahead risk is lopsided — offerings are public at once, but buybacks show up only in the next 10-Q/10-K, which would flatter the repurchasers ASAM would buy. Option 2 is the version no reviewer can dispute; if results hold only with the fresher signal, that is a warning sign.
- Signal set now fixed: **primary** `net_issuance`; **named checks** `comp_issuance`, `net_issuance_5y`, `net_issuance_skip6`. C1 / C2 use the primary only.

### Options as drafted
**Is it late-reported?**
- **Share counts: yes, partly.** CRSP's share history (CIZ `StkShares`) records each count with a `ShrStartDt` = "first effective date of a shares outstanding observation"; `ShrSource` = `OBS` (observation from a data source, e.g. a filing's cover page), `EV` (event, e.g. a split) or `NC` (name change). The CRSP guide does **not** say whether `ShrStartDt` is the as-of date in the report or the date CRSP learned it. Pontiff & Woodgate note CRSP builds shares outstanding from company reports, whose cover-page counts are dated a few days to weeks **before** the filing is public. So a month-end share count can include a number not yet public → small look-ahead.
- **Splits / stock dividends: no.** Announced before the ex-date; handled by the adjustment factor. Its level is set to 1 on the last trading day, so it includes later splits, but those cancel in the 12-month ratio → no look-ahead.
- **Prices and returns: no lag** (market data, `timing_guide.md` §6).
- B uses market value (price × shares), so it gets the same rule as A and C, over the same window.

**Options** (`date_source` = `assumed` for 1–3):
1. **Skip 1 month, then measure (recommended).** Signal at month-end *t* uses share counts at end of *t*−1 and *t*−13 (C: *t*−61); B over the same window. In Step 7, measure on 2003–2025 how many days CRSP's `OBS` share changes are dated before the 10-Q/10-K that reported them was public (EDGAR filing dates via WRDS, as in lazy_prices). If more than ~5% would still be used before they were public with a 1-month skip, move to 2 months — decided **before any return is seen**.
2. **Skip 6 months (OSAP; close to Fama-French).** Safest without measuring; the signal is half a year staler.
3. **No skip (JKP).** Freshest, but accepts the look-ahead above — breaks the core rule; not recommended.
4. **Exact dates per share change.** Match each `OBS` change to the EDGAR filing that reported it; acceptance time, after 4 p.m. → next trading day; `exact` from ~1996, fallback lag before. Most accurate, most work; some counts come from exchanges or news, not filings. Possible later upgrade.

**Monthly-file dates (option 1):** `period_end` = month-end *t*−1 (latest share count used); `published_date` = month-end *t*; `date_source = assumed`; `source = crsp.msf_v2`.

## Step 7 — Pull (`net_issuance`) ✅ (run 2026-11-14 16:22; log `data/issuance_insider/pull_log.txt`)
**Results:**
- B1 `crsp_monthly`: 3,200,575 rows, 23,480 permnos (= all panel permnos), 1974-01 to 2025-12; 0 duplicates; missing `shrout` 0%, `mthcumfacshr` 0.54%, `mthprc` 2.17%, `mthret` 2.20%; **100% of panel rows** have a CRSP row; 299,543 rows from 1974–79 (history before the panel).
- B2 `share_history`: 1,837,088 rows, all panel permnos; sources `OBS` 1,742,065, `NC` 67,656, `EVS` 27,367 (CRSP's code is `EVS`, not `EV`).
- B3 `distributions`: 41,715 share-changing events. B4 `filings_10kq`: 802,853 original 10-K/10-Q-family filings, 36,297 filers, 2002–2025.
- **C2 factor direction: MULTIPLY** — split-adjusted shares = `shrout × mthcumfacshr`. Across 24,185 split months, median |log change| 0.0001 (×) vs 0.81 (÷) vs 0.41 raw; 90% within 5%. Apple Aug 2020: 4,275,634 × 4 = 17,102,536 = August's count; NVIDIA June 2024: 2,459,834 × 10 ≈ 24,568,840. `wrds_guide.md` §3 is right; its VERIFY can be closed.
- **C3: 54% of OBS share counts are dated on a month's last day** → CRSP dates many counts at the fiscal period end, not when they were published (see the timing measurement).

## Step 6 follow-up — Timing measurement ✅ (run 2026-11-14 on copies of the real data; decided 2026-11-14)
**Decision (user, 2026-11-14): "all of the above"** — built as one primary plus named checks, all fixed before any return is seen:
- **Primary `net_issuance`: 4-month skip** (shares at *t*−4 vs *t*−16) — the only skip under 1% early on every measure.
- Named check `net_issuance_skip3`: 3-month skip (*t*−3 vs *t*−15).
- Named check `net_issuance_pit`: exact dates — at each month-end, the latest share count public by then (its 10-K/10-Q's public date where matched, 2003–2025; otherwise the count's month-end + 4 months, `assumed`), vs the same 12 months earlier.
- Named check `net_issuance_skip6` stays (*t*−6 vs *t*−18). B (`comp_issuance`) and C (`net_issuance_5y`) use the primary's 4-month skip.
- **Final signal set:** primary `net_issuance`; checks `net_issuance_skip3`, `net_issuance_pit`, `net_issuance_skip6`, `comp_issuance`, `net_issuance_5y`. The backtest reports all six; C1/C2 use the primary only. More checks = more chances one looks good by luck, so none may replace the primary after returns are seen.
- Matching extended (2026-11-14) to share changes through 2025-12 so the exact-date version has late-2025 counts (statistics unchanged; window to 2025-08).
Script: `signals/issuance_insider/measure_share_timing.py` (no WRDS) → `data/issuance_insider/timing_log.txt`, `share_changes_matched.parquet`.
- **What CRSP's share counts are.** Most quarters CRSP records two counts from the same 10-Q/10-K: the **balance-sheet** count dated at the fiscal period end (Apple: 2024-03-28 = 15,337,686) and the **cover-page** count dated a few days before filing (Apple: 2024-04-19 = 15,334,082); that 10-Q was filed 2024-05-03, so the first is dated 5 weeks before anyone could see it.
- 518,903 real share changes 2003–2025 (10,294 permnos); 97.2% linked to a CIK. Source: balance sheet 37.4% (public a median 41 days after CRSP's date, 90th pct 75), cover page 34.8% (median 7, 90th pct 21), other 27.7% (no matching 10-K/10-Q — exchange data, prospectuses...; lower bound treats them as public on their date, upper bound as public with the next 10-K/10-Q).

| skip *k* | balance sheet | of which 10-K | of which 10-Q | cover page | ALL lower | ALL upper | ALL upper, size-weighted |
|---|---|---|---|---|---|---|---|
| 1 | 89.4% | 99.0% | 86.6% | 1.7% | 34.0% | 55.6% | 55.1% |
| 2 | 16.7% | 70.9% | 0.8% | 0.0% | 6.3% | 23.7% | 24.0% |
| 3 | 2.1% | 7.7% | 0.5% | 0.0% | 0.8% | 4.5% | 6.4% |
| 4 | 0.5% | 0.9% | 0.4% | 0.0% | 0.2% | 0.5% | 0.9% |
| 6 | 0.2% | 0.4% | 0.2% | 0.0% | 0.1% | 0.1% | 0.2% |

- By year, *k* = 3 upper bound: 6.2–6.6% in 2003–2006, 3.6–4.7% from 2007. 10-K balance-sheet counts become public a median 76 days after year-end in 2003–2006 (90th pct 91–94) and 63–69 days later on; before 2003 all firms had 90 days for a 10-K, so the 1980s–1990s likely look like 2003–2006 or slower (not measurable: EDGAR filings in the pull start 2002).
- **Approved rule** (k = 2 if k = 1 fails) **does not cover this:** k = 2 also fails (6.3–23.7%). Smallest k within 5% on both bounds: 3; within 1% on every measure: 4.
- **Options (decide before Step 8, before any return is seen):**
  1. **k = 4 (recommended):** ≤ 0.9% on every measure, incl. 10-K year-end counts and size-weighting; same as `timing_guide.md` §6's quarterly fallback (period end + 4 months); safe for the slower pre-2003 deadlines. Costs one month of freshness vs k = 3 (small for a 12-month change).
  2. **k = 3:** smallest k inside 5% on average (0.8–4.5%), but 6.4% size-weighted, above 5% in 2003–2006, and likely above before 2003.
  3. **Exact dates per share count** (Step 6 option 4): date each count by its filing (the matching now exists); freshest (cover-page counts usable ~1 week after filing); more build work, and "other" counts (28%) and pre-2003 still need an assumed lag. Possible later upgrade.
- The named check `net_issuance_skip6` (k = 6) stays as approved; with k = 4 it is only 2 months apart from the primary.
- **Lesson for the team:** a 1-month skip — or none, as in JKP — would use a share count before it was public for a third to half of all share changes, because CRSP dates balance-sheet counts at the quarter end. For buybacks this would flatter exactly the stocks a long-only fund buys.
Script: `signals/issuance_insider/pull_net_issuance.py` (read-only SELECTs; your own WRDS login). Saves to `data/issuance_insider/` (Git ignores it) and logs to `data/issuance_insider/pull_log.txt`.
- **A1** finds the CIZ tables and prints their columns (CRSP's guide names them StkShares and StkDistributions; WRDS names confirmed at run time). If `msf_v2` has no `mthcumfacshr`, it uses CRSP's monthly cumulative-factor table instead.
- **B1** `crsp_monthly.parquet`: `crsp.msf_v2` 1974–2025 (`permno, permco, mthcaldt, shrout, mthcumfacshr, mthcumfacpr, mthprc, mthret, mthretx`), in 5-year chunks, kept to the panel's permnos; adds `date` = calendar month-end.
- **B2** `share_history.parquet`: CRSP share-count history (`shrstartdt, shrenddt, shrout, shrsource, shrfactype, shradrflg`), panel permnos.
- **B3** `distributions.parquet`: CRSP distributions with a share factor (splits, stock dividends, reverse splits) from 1974, panel permnos.
- **B4** `filings_10kq.parquet`: original 10-K/10-Q-family filings 2002–2025 from `wrdssec.wrds_forms` (`cik, accession, form, fdate, rdate, secadate, secatime`) for the timing measurement.
- **Checks printed:** C1 rows, duplicates, missing values, panel coverage; **C2 factor direction** (across split months, which of shrout × factor or shrout ÷ factor stays flat; Apple Aug 2020 and NVIDIA June 2024 month by month); C3 share-history sources and OBS changes per year, and how often OBS start dates fall on a month-end; C4 filings per year and form.
- Reused, not re-pulled: `data/lazy_prices/ccm_links.parquet`, `ciklink.parquet`, `security_info.parquet`.
- **Tested on a stand-in database** (made-up data, claude.ai workspace): all pulls and checks run; C2 picks the right direction under either convention; the separate-factor-table fallback works.
- After your run: Claude reads the log, then writes the timing measurement (no WRDS) that settles the 1- vs 2-month skip before Step 8. → done, see "Step 6 follow-up".

## Step 8 — Construct (`net_issuance`) ✅ (tested 2026-11-14; price rule added after Step 9; your run 2026-11-15 matches the test run)
Script: `signals/issuance_insider/build_net_issuance.py` (no WRDS, ~1 minute) → `data/issuance_insider/net_issuance_monthly.parquet`, `net_issuance_events.parquet`, `build_log.txt`.
**Rules implemented:**
1. Split-adjusted shares = `shrout × mthcumfacshr` (Step 7). Splits therefore cannot move the signal (Apple Aug 2020, NVIDIA June 2024 checked in Step 7; full split check in Step 9).
2. Calendar-month lags matched on (permno, month-end): a missing month gives a missing value, never a shifted one.
3. Missing rules as approved in 4b (B needs all 12 monthly returns). No winsorizing, no ranking.
4. Exact-date version: CRSP share history (OBS rows that change the count, plus each security's first count); each count adjusted with the share factor on its own date (monthly factor × any split later in that month); published date from `share_changes_matched.parquet` (balance sheet / cover page → filing's public date, `exact`), else count's month-end + 4 months (`assumed`), never before the count's date; at each month-end the count with the latest date among those already public.
5. Event file (late data): one row per share-count change: `permno, gvkey, period_end` (CRSP's date), `published_date, date_source, source, version` (`original`*), inputs `shrout, prev_shrout, adj_factor, shrout_adj, count_source, form10`.
6. Monthly file on the panel's rows: `permno, gvkey, date, net_issuance, period_end` (= month-end *t*−4), `published_date` (= *t*), `date_source` (`assumed`), `source` (`crsp.msf_v2`), `applies`, then `comp_issuance, net_issuance_5y, net_issuance_skip3, period_end_skip3, net_issuance_skip6, period_end_skip6, net_issuance_pit, period_end_pit, published_date_pit, date_source_pit`.
7. gvkey: CCM link (LU/LC, P/C) valid at the month-end; if none, the panel's gvkey.
8. ETFs: CRSP security subtype ETF at the date → `applies = n/a (ETF)`, values blank (panel has none).
\* `version = original`: CRSP share counts are as reported; whether CRSP ever revises them is **VERIFY** (not documented in the guide).

**Test run on a copy of the real data (claude.ai workspace, pandas 3.0.5):**
- Monthly file 2,796,065 rows = the panel exactly; 0 duplicates. gvkey from CCM equals the panel's in 99.50% of rows where both exist; 2.6% missing after fallback. ETF rows: 0.
- Rows with a value: `net_issuance` 89.5%, `comp_issuance` 88.7%, `net_issuance_5y` 65.7%, `skip3` 90.2%, `skip6` 88.3%, `pit` 89.2%; by year 86–96% for the primary (1980: 92%).
- `net_issuance`: median 0.006, 1st pct −0.19, 99th pct +1.10 (log); exactly 0 in 9.1% of rows, negative (net buyback) in 21.2%.
- Rank correlation with the primary: `pit` 0.96, `skip3` 0.94, `skip6` 0.88, `comp_issuance` 0.88, `net_issuance_5y` 0.59.
- Exact-date version: newest count has an exact date in 73.4% of rows from 2004; count used is a median 3.1 months old from 2004 (primary: 4 by construction).
- Spot checks: Apple −2% to −9% a year 2020–2025 (buybacks); NVIDIA ~0 with no jump at the June 2024 split; Microsoft ~0. Apple Dec 2025 (exact-date) uses its 10-K cover count of 2025-10-17, public 2025-10-31.
- Largest values are real: Helios & Matheson (MoviePass, permno 85320) 2018–19, +10.6 log (~70,000× split-adjusted shares through repeated offerings and a 1-for-250 reverse split); Aditxt (permno 19460) 2025, serial reverse splits and dilution. Kept (no winsorizing); Step 9 reviews outliers.

**Your run (2026-11-14):** `timing_log.txt` and `build_log.txt` identical to the test run apart from the timestamp; monthly file identical (only blank-vs-blank differences).

**Change after Step 9 (2026-11-14) — price rule:** no value unless every month of the window, from the earlier share count to the later one, has a CRSP price. Found in check 7: Delcath (permno 89169) stopped trading on a CRSP exchange Mar 2019 – Apr 2020 (no price, share count frozen at 499 million) and returned after a 1-for-700 reverse split that CRSP never recorded as a distribution, so its factor stayed 1 and the reverse split looked like a 99% buyback (−4.97, the most negative value — it would have ranked as the biggest buyer-back). 2.17% of months inside securities' CRSP spans have no price. Effect: primary coverage 89.5% → 88.7%; rows below −1 (shares ÷ 2.7 in a year) 3,061 → 1,904; rank correlations between versions unchanged. B (`comp_issuance`) was already protected (needs market value at both ends and all 12 returns).

## Step 9 — Validate (`net_issuance`) ✅ (run on a copy of the real data 2026-11-14; **your run 2026-11-15: `build_log.txt` and `validate_log.txt` identical to the test run** apart from the timestamp and a path separator; 9 PASS, 1 optional SKIPPED)
Script: `signals/issuance_insider/validate_net_issuance.py` (no WRDS, under a minute) → `data/issuance_insider/validate_log.txt`.
1. **Duplicates:** 0 monthly (permno, date), 0 event (permno, period_end). PASS
2. **Match to the panel:** monthly file = the panel's 2,796,065 rows exactly; 88.7% have the primary. Missing: 92.9% new in CRSP (under 16 months of history), 7.0% a month without a CRSP price in the window (price rule), 0.05% zero shares. PASS
3. **Dates:** no value dated before its period end or used before its published date (primary, exact-date version, events). Primary 100% `assumed` (fixed 4-month skip, backed by the timing measurement: under 1% of share changes used before public); exact-date version 74.7% exact from 2004; events exact 70–74% a year from 2003, 0% before (no EDGAR match). PASS
4. **Ticker change:** Facebook → Meta (permno 13407, ticker FB until 2022-06-08): a value every month of 2022, one gvkey (170617), largest month-to-month change 0.017. Ticker FB later reused by a ProShares fund (permno 26867) — keyed on permno, no mix-up. PASS
5. **Splits:** raw shares jump ×5 (Tesla Aug 2020), ×3 (Tesla Aug 2022), ×10 (NVIDIA June 2024); split-adjusted shares and the signal do not. Across all 18,419 CRSP splits/stock dividends (type FRS, |factor| ≥ 20%), CRSP's share factor moves by exactly the split size in 99.96%; the 2.2% of split months where adjusted shares still move are months where the raw count also changed for other reasons (e.g. an offering next to a reverse split) — real, and counted. Not splits: CRSP events of type TSOO ("total shares outstanding observation": mergers, offerings, 1980s–90s) and SP ("security payment", mostly mergers) carry a share factor but no price factor and the price does not fall; CRSP does not adjust for them, so they count as issuance (e.g. Newmont +57% in 1997). PASS
6. **Coverage:** primary 80–96% of panel rows each year (lowest 1987 79.5%, 1984 79.6%, 2021 81.8% — listing waves). ETFs: 6,933 in CRSP, 0 in the panel, 0 rows n/a, none dropped. PASS
7. **Outliers and three firms:** primary 1st/99th percentile −0.19 / +1.04; |value| > 1 in 1.0% of rows. Largest = serial diluters (Helios & Matheson/MoviePass 2018–19, Aditxt 2025); most negative = SPAC trust redemptions (shares fall 70–85% at a flat ~$10 price) and big tender offers (e.g. Peerless Systems 2011) — market value falls about as much as shares, unlike an unrecorded split. Price rule: 0 values with an unpriced month in the window; Delcath has no value comparing across its gap. Apple (Dec values) −6.7% (2019) to −2.4% (2025) every year; Microsoft −0.9% to 0.0%; Tesla +4.9%, +4.0%, +7.2% (2019–21; stock offerings 2020) then +0.6% to +1.3%; each equals the log change in split-adjusted shares August to August. PASS
8. **Versions agree where they must:** `net_issuance_skip6`(t) = primary(t−2) and `net_issuance_skip3`(t) = primary(t+1) in 100.0000% of 2.4–2.5 million comparable rows. PASS
9. **Market value:** pulled price × shares matches the panel's `me` within 0.1% in 100.00% of 2,792,750 rows. PASS
10. **OSAP cross-check:** SKIPPED until `osap_ShareIss1Y.parquet` is downloaded (Hugging Face is not reachable from the claude.ai workspace). Optional helper: `signals/issuance_insider/get_osap_shareiss.py` (needs `pip install openassetpricing`). The check compares OSAP's ShareIss1Y (same 6-month skip, percentage change) with our `net_issuance_skip6`.

**Notes for the backtest (not data problems):** SPACs are in the panel and their trust redemptions look like huge buybacks; consider excluding blank-check shells (SIC 6770) or report with and without. Test equal- and value-weighted.

## Change after the backtest — firm level across share classes (`net_issuance`) ✅ (your OK 2026-11-16: "yes please")
- **Why:** building the end-2025 screen showed that per-class values can put one class in Q5 when the company did not shrink: Berkshire Class A −3.8% (A converts into B; B +2.4%; company +0.1%), Alphabet Class C −2.8% (Class A −0.7%; company −1.7%), Zillow Class A −8.0% (company about +5%). Alphabet Class C alone was 16% of the value-weighted screen.
- **Rule (in `build_net_issuance.py`):** a firm (gvkey) with 2+ classes (permnos) in the panel at *t* gets one value, given to every class: ln( Σ W_c / Σ W_c·exp(−x_c) ), W_c = class market value at *t* (panel `me`) — the log change in total units with each class at its month-*t* price (class price ratios are near-constant: Berkshire A = 1,500 B; Alphabet A ≈ C). Applies to the primary and every share-count check (skip3, skip6, pit, comp_issuance, 5y). Classes without a value or market value are left out of the sums. New columns `net_issuance_class` (per-class primary) and `n_classes`.
- **Run on a copy (claude.ai workspace, 2026-11-16; build 74 s):** 28,784 rows (14,392 firm-months, 0.99% of rows) belong to multi-class firms; values changed in 27,656 rows; single-class rows identical in every column; coverage of the primary 88.74% → 88.77% (classes without their own history now carry the firm's value).
- **Validation re-run: 10 PASS, 1 SKIPPED (OSAP, optional).** Check 7's price rule now tests the per-class value; check 8's identities are tested on single-class rows (100%); **new check 11:** single-class rows unchanged (100% of 2,767,281), one value per multi-class firm-month (100% of 14,392), recomputed independently (100% of 14,168), Berkshire A = B = +0.0010, Alphabet C = A = −0.0174.
- **Backtest re-run:** conclusions unchanged (see `backtest.md`, v1 → v2).
- **Your machine:** the updated scripts, logs, backtest outputs and screen were copied. The rebuilt `net_issuance_monthly.parquet` (93 MB) was too large to copy → you re-ran `build_net_issuance.py` and `validate_net_issuance.py` (2026-11-15 21:17 / 21:19 your time): **10 PASS, 1 SKIPPED; both logs identical to the workspace run apart from timestamps; `net_issuance_monthly.parquet` equal to the workspace file within 3e-15** (floating-point rounding between Windows and Linux; same missing values, same non-numeric columns).

## Step 10 — Save (`net_issuance`) ✅ catalog row written 2026-11-15 (your OK: one row per signal); upload and commit: yours (see "Next")
- **Storage:** CRSP/WRDS data is licensed, so nothing goes to `public_data/` except the catalog row. Keep `data/issuance_insider/` locally; upload `net_issuance_monthly.parquet` (82 MB) and `net_issuance_events.parquet` (17 MB) to the team's shared drive. The pulled inputs (`crsp_monthly`, `share_history`, `distributions`, `filings_10kq`, `share_changes_matched`) can be rebuilt from the scripts; upload them too if the drive has room.
- **Catalog:** the plan in 4b was one row per column. With six columns now (one primary, five checks), **recommended: one row for `net_issuance`**, with the five checks named in `notes` and `location` — they are robustness columns of the same file, not separate signals, and six near-identical rows could lead someone to test a check as its own signal. Alternative: one row per column as first planned. New category `issuance` (the catalog has value, profitability, leverage, liquidity, efficiency, quality, text; JKP uses "Issuance").
- **Row as written (2026-11-15; `notes` updated to name `insider_cluster` and C1/C2):**
  - `name` net_issuance · `category` issuance · `status` have-data · `data_shape` firm-level · `in_panel` no · `frequency` monthly · `coverage_start` 1980-01 · `coverage_end` 2025-12 · `added_by` raghavrc · `date_added` 2026-11-15 · `test_results` (empty)
  - `hypothesis`: Firms that shrink their split-adjusted share count (net buybacks) earn higher future returns and net issuers lower: managers sell shares when they think the stock is expensive and buy back when cheap, and investors underreact. Slow (a year or more). For ASAM (long-only): tilt toward net buyers-back; one half of the planned issuance + insider-cluster combination.
  - `definition`: 12-month log change in split-adjusted shares outstanding (CRSP shrout x mthcumfacshr) with a 4-month skip: ln(adj[t-4]/adj[t-16]). Positive = net issuer, negative = net buyer-back. No value unless every month of the window has a CRSP price.
  - `source`: CRSP CIZ crsp.msf_v2 (shrout, mthcumfacshr, mthprc); timing measured with CRSP share history (crsp.stkshares) and EDGAR filing dates (wrdssec.wrds_forms)
  - `citation`: Pontiff & Woodgate (2008), Share Issuance and Cross-sectional Returns, Journal of Finance 63(2), 921-945, doi:10.1111/j.1540-6261.2008.01335.x
  - `inputs_required`: CRSP monthly shares outstanding, cumulative share-adjustment factor, price; for the checks also total return, CRSP share history, EDGAR 10-K/10-Q filing dates, CIK-gvkey and CCM links
  - `location`: data/issuance_insider/net_issuance_monthly.parquet:net_issuance (checks in the same file: net_issuance_skip3, net_issuance_skip6, net_issuance_pit, comp_issuance, net_issuance_5y; events: data/issuance_insider/net_issuance_events.parquet); shared drive
  - `timing_rule`: assumed: share counts used 4 months after their month. CRSP dates many counts at the fiscal period end, before the 10-K/10-Q is public; measured 2003-2025, a 4-month skip uses under 1% of share changes before public (1 month: 34-56%). Check net_issuance_pit uses each count's 10-K/10-Q public time (at or before 4 p.m. -> same trading day, else next) where matched.
  - `notes`: Stocks only (panel has no ETFs; ETF rows would be n/a). Primary fixed before any return test; named checks in the same file: net_issuance_skip3, net_issuance_skip6, net_issuance_pit, comp_issuance (Daniel-Titman 1-year composite issuance, counts dividends), net_issuance_5y. 88.7% of panel rows have a value (new listings need 16 months). Extremes are real (serial diluters; SPAC trust redemptions look like large buybacks - consider excluding SIC 6770). One half of the issuance_insider project with insider_cluster; combinations C1 (net shrinker and insider cluster buy) and C2 (average rank) use the two primaries only. Process and decisions: signals/issuance_insider/progress.md.
- **Commit:** one commit for both signals — see Step 10 of `insider_cluster` below.

## Next
**Both signals (now) — Step 10, your part:**
0. ~~Rebuild `net_issuance` at the firm level~~ ✅ done 2026-11-15 your time (10 PASS; matches the workspace run).
1. Upload the data files to the team's private drive (list in Step 10 of `insider_cluster`; ask the teammate who shared the panel where the drive is).
2. Commit and sync per SETUP.md "Save and upload your work": stage only the 12 files in `signals/issuance_insider/` (the 10 listed in Step 10 of `insider_cluster` + `backtest_issuance_insider.py` + `backtest.md`) and `public_data/factor_catalog.csv` (list and message in Step 10 of `insider_cluster`). If Source Control shows anything in `data/` or `.venv`, stop and ask.
3. Send the library e-mail about LSEG Insiders access (draft in the chat), if not sent yet. If access comes through: extend `insider_cluster` back to 1986 as a new, separately recorded step.

**Backtest (2026-11-16):** done — plan, results and bottom line in `signals/issuance_insider/backtest.md` (script `backtest_issuance_insider.py`; outputs in `data/issuance_insider/backtest/`). In short: `net_issuance` works (Fama–MacBeth 5.6%/yr, t 3.1; Q5 beats the market ~2%/yr) but is mostly profitability/value/investment exposure and weaker since 2008; `insider_cluster` shows no premium in investable stocks; C1/C2 are not better than `net_issuance` alone. Commit `backtest_issuance_insider.py` and `backtest.md` with the other files. `test_results` for both rows written to the catalog (2026-11-16, your OK). **Share-class fix done (2026-11-16):** `net_issuance` is now firm level across share classes; validation 10 PASS; backtest re-run, conclusions unchanged; screen rebuilt (see `backtest.md`).

**Optional, any time:** OSAP `ShareIss1Y` cross-check for `net_issuance` (`get_osap_shareiss.py`, then re-run `validate_net_issuance.py`).

---
# Signal 2 — `insider_cluster`
Hypothesis approved in Step 1 (2026-11-14; see "Signal 2" above): several insiders buying on the open market within a short window → higher returns over the next weeks to months; dated by Form 4 filing, never trade date; stocks only; controls for reversal and `bm` in the backtest.

## Summary — `insider_cluster` (signal 2 of 2)
- **Signal:** `insider_cluster` — the number of different officers and directors whose open-market purchase was part of a **tight cluster** (another officer/director of the same firm bought on the same or an adjacent trading day) and became public in the last 3 months. **0 = no cluster; 2 or more = a cluster** (1 only when a partner's filing fell outside the window).
- **Definition:** Form 4/5 code P, acquired, common stock, original filings, filed 0–90 days after the trade; officers and directors only (a joint filing counts as one insider); counted at month-end *t* when both filings of the cluster were public in months *t*−2..*t*. Firm level (gvkey), given to every permno of the firm. 0 when the firm's filings are visible and nobody clustered; blank when the firm is not linked to SEC filings, or before 2006-03.
- **Citation:** Kang, C.-M., Kim, D., & Wang, Q. (2018). Cluster Trading of Corporate Insiders. Working paper (UNSW / UW-Milwaukee / UCF). Published evidence on the same effect: Alldredge, D. M., & Blank, B. (2019). Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading. *Journal of Financial Research*, 42(2), 331–360, doi:10.1111/jfir.12172. Related: Lakonishok & Lee (2001), *Review of Financial Studies* 14(1), 79–111 (insider purchases informative, sales little); Cohen, Malloy & Pomorski (2012), *Journal of Finance* 67(3), 1009–1043 (routine vs opportunistic insiders).
- **Intuition:** insiders know more about their firm than the market. One insider buying can be personal (diversification, signalling, a bonus to invest); several buying within a day of each other is harder to explain without shared good news. Investors underreact to Form 4 filings, so prices adjust over weeks to months. Sales carry little information (mostly liquidity and diversification).
- **How ASAM can use it (long-only):** a buy-side screen; combined with `net_issuance` in C1 (net buyer-back **and** a cluster buy) and C2 (average rank) — the firm's money and the insiders' own money pointing the same way.
- **Timing:** exact. Each filing is public on the next trading day after its filing date (the SEC data sets have no time of day, so after the close is assumed); a cluster purchase counts only once its earliest partner's filing is public too. Median 2 days from trade to filing; 85% within 5 days.
- **Files:** `data/issuance_insider/insider_cluster_monthly.parquet` (one row per panel row: `permno, gvkey, date, insider_cluster, period_end, published_date, date_source, source, applies` + named checks) and `insider_cluster_events.parquet` (one row per insider, trade day and direction: 348,824 purchases, 870,492 sales, with filing and public dates, cluster flag and size, `cik_link`). Not tested for returns here, by design.
- **Named checks (fixed in Step 4b before any return test):** `insider_buyers_1m` (officer/director buyers made public in month *t*), `insider_buy_value_3m` (purchase dollars over 3 months ÷ firm market value), `insider_npr_6m` (net purchase ratio over 6 months, insider-days).
- **Known limitations:** (1) 2006–2025 only — the SEC data sets start in 2006 and LSEG's insider data (1986+) is not readable on your WRDS account (library asked). (2) "Keep everything": every code P counts, including purchases in IPOs and offerings (7 of the 10 largest clusters fall in the stock's IPO month; 4.8% of cluster months are a stock's first 3 months) and plan-like fractional purchases (e.g. Old Line Bancshares 2016). (3) `insider_buy_value_3m` keeps price typos (up to 377,051 × market value) → use by rank only. (4) Filing time of day unknown → next trading day (conservative; exact EDGAR acceptance times are a possible upgrade). (5) Dropped: 764 purchases whose CIK links to several firms with none dated; filings of firms with no CIK link (mostly outside CRSP/Compustat). (6) 3.1% of panel rows from 2006-06 blank.

## Differences from the source (Kang, Kim & Wang 2018)
| | Paper | Here |
|---|---|---|
| Data | U.S. insider trading data, 1986–2016 | SEC Insider Transactions Data Sets (Forms 3/4/5 as filed), 2006–2025; 2017–2025 is after the paper's sample |
| Cluster | several insiders of a firm trading in the same direction on the same day or consecutive trading days | same window: ≥ 2 different officers/directors buying on the same or an adjacent trading day |
| Direction | purchases and sales (cluster sales predict little) | purchases only; sales enter only check `insider_npr_6m` |
| Insiders | — | officers and directors; 10% holders and "other" excluded; a joint filing counts as one insider |
| Measure | abnormal returns after cluster trades (cluster purchases about twice the 21-day abnormal return of single purchases) | monthly firm signal: number of cluster buyers made public in the last 3 months |
| Timing | — | dated by when both filings were public (filing date → next trading day), never the trade date |
| Cleaning | — | none beyond the rules ("keep everything"): IPO, offering and plan-like purchases included; no price check |
| Use | return prediction | long-only buy screen for ASAM, and half of the combination with `net_issuance` |

## Step 2 — Search (`insider_cluster`) ✅ (approved 2026-11-15, with this direction)
**Direction (approved 2026-11-15):** anchor on Kang, Kim & Wang's cluster definition (purchases only); keep "all insider buying" (Lakonishok & Lee) as a named check in case clusters are too sparse; routine-trader filter (Cohen, Malloy & Pomorski) optional, decided in 4b; data: LSEG insider filings on WRDS first, SEC data sets as fallback.

| Source | Definition | Same / related | Shape |
|---|---|---|---|
| Kang, Kim & Wang (2018), "Cluster Trading of Corporate Insiders," working paper (UNSW / UW-Milwaukee / UCF) | Cluster = several insiders of a firm trading in the same direction on the same day or consecutive trading days; U.S. data 1986–2016; >40% of insider trades are clustered. Cluster purchases: about twice the 21-day abnormal return of single purchases (3.8% vs 2%); cluster sales predict little | **Same** (closest) | Paper only |
| Alldredge & Blank (2019), "Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading," *J. Financial Research* 42(2), 331–360, doi:10.1111/jfir.12172 | Insiders cluster around trades of colleagues, especially those they work closely with; clustered purchases followed by >2% abnormal return the next month; CEOs/CFOs >4× as likely to buy when the other bought in the previous 2 days | **Same** idea | Paper only |
| Lakonishok & Lee (2001), "Are Insider Trades Informative?," *RFS* 14(1), 79–111, doi:10.1093/rfs/14.1.79 | All insider trades, NYSE/AMEX/Nasdaq 1975–95; firms with heavy insider buying beat heavy selling (7.8% over 12 months, 4.8% after size and B/M); information is in **purchases**, sales predict nothing; result driven by smaller firms; insiders are contrarian (buy after falls, value stocks) | Related (all buying, not clusters) | Paper only |
| Cohen, Malloy & Pomorski (2012), *JF* 67(3), 1009–1043 | Routine insiders (same month each year) carry no information; opportunistic ones do | Related (a possible filter) | Paper only |
| Babenko, Tserlukevich & Vedrashko (2012, *JFQA*); Cziraki, Lyandres & Michaely (2021, *JCF*) | Insider buying makes buyback announcements credible; insider net buying rises before buybacks | Related (the combination) | Paper only |
| Open Source Asset Pricing, JKP, Ken French | No insider-trading signal (checked OSAP `SignalDoc.csv`: 0; JKP `characteristics.csv`: 0) | — | **Nothing ready-made** |

**Data sources (for Step 5; availability in your WRDS subscription VERIFY):**
- **LSEG (formerly Thomson Reuters) Insider Filing Data on WRDS** — Forms 3, 4, 5 and 144; cleansed from 1986; "Table 1" = stock transactions; has a flag to exclude problematic records; amendment concordance from Oct 2002. The usual academic source.
- **SEC Insider Transactions Data Sets** — free, from the XML of Forms 3/4/5, posted quarterly; 2000s onward (start VERIFY); as filed, no cleaning. A cross-check or fallback.

**What the search shows:**
- Nothing to download → Step 3 will almost surely be Case 2 (build).
- The cluster window differs: same or next trading day (Kang et al.), within ~2 days (Alldredge & Blank), "a short period" (practitioners). Window, minimum number of insiders, purchases only, and a routine-trade filter are Step 4b choices.
- Purchases carry the information; sales little → buying side only, as in the hypothesis.
- Strongest in smaller firms → capacity for a value-weighted fund is the open question (test equal- and value-weighted).
- Timing: Form 4 must be filed within 2 business days of the trade (current rule); the signal must be dated by the filing, not the trade.

## Step 3 — Download or build (`insider_cluster`) ✅ (2026-11-15: Case 2, build)
Nothing ready-made in OSAP, JKP or Ken French → build from insider filings (source settled in Step 5).

## Step 4b — Definition (`insider_cluster`) ✅ (approved 2026-11-15: A primary; B, C, D named checks; A settings: 3-month window, ≥ 2 insiders, officers and directors only)
**Decision (user, 2026-11-15):** build all four as separate columns; **A is the primary**, fixed before any return is seen; B, C, D are named checks; C1/C2 use A only. The backtest reports all four side by side and reads them as: A > B → tight timing matters; A > C → number of people matters more than dollars; A > D → clustering adds something beyond insider buying in general.
**Evaluation (2026-11-15):** A — closest to the hypothesis, strongest evidence, natural flag for C1; risk: sparse (few names, small firms) and some clusters may be mechanical (buying right after the post-earnings blackout lifts). B — fires more often, rankable count; looser (unrelated buys weeks apart count). C — captures conviction; one large buyer can dominate, scaling by market value tilts further to tiny firms, price/share errors make outliers. D — broadest coverage, long track record; includes sales (mostly noise per Lakonishok & Lee), ignores size, slow (6 months).
**For the backtest (all four):** insiders buy after price falls and in cheap stocks, and the effect is strongest in small firms → control for short-term reversal and `bm`; test equal- and value-weighted.

**Rules common to all options (proposed):** open-market purchases only (Form 4 code P, common stock); officers and directors only (pure 10% holders — often funds — excluded); amendments and records flagged as problematic dropped; each insider counted once per firm per window; dated by when the Form 4 became public (Step 6), never the trade date; stocks only (ETFs `n/a`).

| Option | What counts | Monthly value at month-end *t* | People or dollars | Fields needed |
|---|---|---|---|---|
| **A. Tight cluster (Kang, Kim & Wang) — recommended primary** | ≥ 2 different insiders buying on the **same or next trading day** | number of insiders in tight clusters made public in the last 3 months (0 = none; ≥ 2 = cluster) | people | insider ID, firm ID (CUSIP), trade date, filing date/time, transaction code, role, quality flag |
| B. Monthly buyer count (practitioner "cluster buy") | different insiders buying, any days, within one month | number of different insiders whose purchases were made public in the last month (cluster = ≥ 2) | people | as A |
| C. Dollar intensity | all open-market purchases | dollars bought by insiders, made public in the last 3 months ÷ market value | dollars | as A + shares, price; market value from the panel |
| D. Net purchase ratio (Lakonishok & Lee) — the "all buying" check | purchases and sales | (buys − sells) ÷ (buys + sells), by number of insiders' transactions, last 6 months | people | as A, incl. sales (code S) |

**Recommendation:** A as the primary (closest to the hypothesis and the anchor paper); B, C, D as named checks fixed now (all come from the same pull, as with `net_issuance`). C1 / C2 use A only. Choices inside A to confirm: 3-month window (the paper's effect runs ~1–3 months), ≥ 2 insiders, officers and directors only. → approved as above.

## Step 5 — Inventory (`insider_cluster`) ✅ (approved 2026-11-15; nothing extra on the shared drive)
| Need | Used by | In panel / local `data/`? | Source if missing |
|---|---|---|---|
| `permno`, `date` (month-end), row universe | all | ✅ panel | — |
| Market value `me` (thousands $) | C | ✅ panel | — |
| `gvkey` | key column | ⚠️ panel (11.5% blank) | ✅ reuse `data/lazy_prices/ccm_links.parquet` |
| ETF flag | `n/a` marking | ✅ `data/lazy_prices/security_info.parquet` | — |
| **Insider transactions:** insider ID, firm CUSIP, trade date, filing date (and time, if any), transaction code (P buy / S sell), acquired/disposed, shares, price, role (officer/director/10% owner), data-quality flag, amendment info | A–D | ❌ | LSEG Insider Filing Data on WRDS ("Table 1"); **in your subscription? VERIFY in Step 7**; fallback: SEC Insider Transactions Data Sets |
| **CUSIP → permno history** (insider data is keyed by CUSIP) | linking | ❌ (`security_info` has no CUSIP column; panel neither) | CRSP CIZ security-info history (CUSIP field; name VERIFY) |
| Trading-day calendar **1986–1992** | "same or next trading day"; after-4 p.m. rule | ⚠️ `trading_days.parquet` covers 1993–2025 only | CRSP daily index dates |
| Form 4 acceptance time | after-4 p.m. rule (Step 6) | ❌ | probably not in LSEG; EDGAR index via `wrdssec.wrds_forms` (form 4) from ~2003 — Step 6 decides |
- **Question for you:** anything on the shared drive that isn't in your local `data/` — e.g. an insider-trading pull a teammate already made? → **No** (user, 2026-11-15).

## Step 6 — Timing (`insider_cluster`) ✅ (approved 2026-11-15: option 1)
**Decision (user, 2026-11-15): option 1** — each Form 4 public from the trading day after its filing date (`exact`); paper-era filings (before 2003-07-30) + an assumed 5-trading-day lag (`assumed`; Claude's judgement, not a documented figure); no filing date → legal deadline from the trade date (`assumed`). A cluster is dated by the public date of the last Form 4 needed for it. Backtest also reports 1986–2002 and 2003–2025 separately (the paper-era lag is an assumption; 2003+ dates are exact). Option 2 (exact EDGAR times) is a possible later upgrade.

**Rules (checked 2026-11-15):** for trades on or after **2002-08-29** (Sarbanes-Oxley §403), Form 4 is due by 5:30 p.m. ET on the **second business day** after the trade; before, by the **10th day of the month after the trade month** (up to ~40 days hidden). Electronic (EDGAR) filing of Form 4 mandatory by **2003-07-30**; earlier Form 4s were mostly paper.
**Consequences:** the trade date is never the public date (before 2002 it can be 40 days early); clusters are defined by trade dates (same or next trading day) but a cluster is only **known when the last Form 4 needed for it is public**; windows ("last 3 months", "last month", "last 6 months") count filings by public date.

**Options:**
1. **Filing date, next trading day (recommended).** Every Form 4 is public from the trading day after its filing date (we have no filing time; the deadline is 5:30 p.m., after the close, so assume after close — conservative by at most one day). `date_source = exact` (date known). **Paper era (before 2003-07-30):** add an assumed 5-trading-day lag for the paper form to reach the public (`assumed`). Records with no filing date: legal deadline from the trade date (2 business days from 2002-08-29; 10th of the next month before), `assumed`; share reported. Step 9 checks trade-to-filing gaps by era.
2. As 1, plus exact EDGAR acceptance times for 2003+ (match each Form 4 to `wrdssec.wrds_forms`) so filings before 4 p.m. count the same day. Only changes filings made on a month's last trading day before 4 p.m.; needs insider-to-EDGAR matching. Not worth it now.
3. As 1, but no paper-era lag (treat paper filing dates like electronic ones). Simpler; possibly a few days optimistic for 1986–2003.

## Step 7 — Pull (`insider_cluster`) ✅ (probe run 2026-11-15: LSEG insider data not readable → SEC Insider Transactions Data Sets; SEC pull run 2026-11-15: 80/80 quarters)
The LSEG insider data's WRDS library, table and column names (and whether your subscription has it) are not known, so a short read-only **probe** comes first; the real pull is written against what it finds (as in lazy_prices).
Script: `signals/issuance_insider/probe_insiders.py` → `data/issuance_insider/probe_insiders_log.txt`.
- **P1** libraries you can see whose names suggest insider data (LSEG / Thomson Reuters, e.g. `tr_insiders`, `tfn`).
- **P2** their tables, columns and approximate row counts; picks the stock-transaction table ("Table 1").
- **P3** Apple's latest rows; for 2024 the values of transaction code, buy/sell flag, role, data-quality ("cleanse") flag and form type; days from trade to filing for purchases in 2024 and 1995 (before/after the 2-day rule); purchases per year (1986, 1995, 2005, 2015, 2024).
- **P4** CRSP CIZ security-info history: CUSIP columns (to link CUSIP → permno).
- **P5** CRSP CIZ daily dates 1986–1992 (trading-day calendar), using IBM (permno 12490).
- Tested on a stand-in database (made-up data): runs end to end; a library you cannot access is reported and skipped.

**Probe results (your run 2026-11-15 12:53; log `data/issuance_insider/probe_insiders_log.txt`):**
- `tfn.table1` (LSEG/Thomson Insider Filing Data, ~17.5 million rows, 48 columns: `fdate, trandate, trancode, acqdisp, personid, rolecode1–4, cusip6, cusip2, shares, tprice, cleanse, amend, formtype, ...`) is listed, but reading it fails: **"permission denied for schema tr_insiders"** — not in your subscription.
- `wrds_insiders_samp` = a free **sample** (~1,200 rows) of WRDS's own SEC-based insider product; the full library is not visible → not subscribed.
- CRSP CIZ `stksecurityinfohist` has `cusip`, `cusip9`, `hdrcusip`, `hdrcusip9` (Apple 03783310). CRSP `dsf_v2` (`dlycaldt`) gives 1,771 trading days 1986–1992 (IBM).

**Fallback checked (2026-11-15): SEC Insider Transactions Data Sets** — free, official, from the XML of Forms 3/4/5, "as filed"; quarterly zips **2006 Q1 – 2026 Q3**, 8–17 MB each (~1 GB in total). Tab-delimited tables per quarter, joined on `ACCESSION_NUMBER`: `SUBMISSION` (`FILING_DATE`, `PERIOD_OF_REPORT`, `DOCUMENT_TYPE` 3/4/5 and amendments, `ISSUERCIK`, `ISSUERTRADINGSYMBOL`), `REPORTINGOWNER` (`RPTOWNERCIK`, `RPTOWNERNAME`, `RPTOWNER_RELATIONSHIP` = OFFICER / DIRECTOR / TENPERCENTOWNER / OTHER, `RPTOWNER_TITLE`), `NONDERIV_TRANS` (`TRANS_DATE`, `TRANS_CODE` (P = open-market or private purchase, S = sale), `TRANS_SHARES`, `TRANS_PRICEPERSHARE`, `TRANS_ACQUIRED_DISP_CD`, `TRANS_TIMELINESS` (L = late), `SECURITY_TITLE`, `DIRECT_INDIRECT_OWNERSHIP`). Dates DD-MON-YYYY. Linked by issuer CIK → gvkey (`ciklink.parquet`) → permno (CCM) — no CUSIP needed.

**Data-source options (decision needed):**
1. **SEC data sets, 2006–2025 (recommended).** Free, official, every Form 4 since 2006; all electronic, so every date is exact (the paper-era lag no longer applies). Overlaps Kang, Kim & Wang's sample for 2006–2016; 2017–2025 is after it (out of sample). Cost: no 1986–2005. You run a download script (no WRDS; the SEC asks downloaders to give an e-mail in the request header — you type it yourself).
2. **Ask UCLA Anderson's library / WRDS contact** whether LSEG Insiders (`tr_insiders`) can be added to your account. Would add 1986–2005 and a cleaned version; uncertain and slow. Can run in parallel with 1; if granted, extend later.
3. **Third-party EDGAR build from 2003** (Harvard Dataverse dataset behind a 2023 *Scientific Data* paper). Adds only 2003–2005, not official; not worth it.
**Consequences of 1:** `insider_cluster` and the C1/C2 combinations cover 2006–2025 (net_issuance still 1980–2025); Step 6 simplifies (all dates exact; the 1986–2002 vs 2003–2025 split becomes 2006–2016 vs 2017–2025); CUSIP link and 1986–1992 calendar no longer needed.

**Decision (user, 2026-11-15): option 1 now, option 2 in parallel** ("go ahead with what you can for the time being"). Pre-2006 routes noted: LSEG via WRDS (1986–2005, subscription), EDGAR XML builds from mid-2003 (e.g. the Harvard Dataverse dataset), paper only before 2003. If LSEG access comes through, extend back to 1986 as a later step.
**Updates to earlier steps from this decision:**
- Step 5: CUSIP history and the 1986–1992 calendar are **not needed**; link = issuer CIK → gvkey (`data/lazy_prices/ciklink.parquet`, valid links) → permno (CCM). Trading days 2006–2025 are in `trading_days.parquet`. **No WRDS pull is needed for signal 2.**
- Step 6: every filing is electronic → all public dates `exact` (filing date → next trading day); the paper-era lag does not apply. Robustness split: 2006–2016 (overlaps Kang, Kim & Wang) vs 2017–2025 (after their sample). The SEC data also carry the accession number, so exact EDGAR acceptance times (option 2 of Step 6) are an easy later upgrade.

**SEC pull script (written 2026-11-15):** `signals/issuance_insider/pull_sec_insiders.py` (no WRDS; you pass your name and e-mail for the SEC's required request header — sent only to sec.gov, not saved).
- Downloads the 80 quarterly zips 2006 Q1 – 2025 Q4 to `data/issuance_insider/sec_raw/` (~1 GB; skips files already there; ≤ 2 requests a second).
- Reads `NONDERIV_TRANS` (keeps codes P and S), `SUBMISSION` and `REPORTINGOWNER` (only filings with a P or S row); parses DD-MON-YYYY dates and numbers with thousands separators.
- Saves `sec_trans.parquet`, `sec_submissions.parquet`, `sec_owners.parquet`; log `pull_sec_log.txt` with rows per year, form types, codes, insider relationships, trade-to-filing gaps (share within 2 and 5 days), late flags, duplicates across quarters, Apple's latest rows.
- Tested on fake quarterly zips in the documented layout: filters, dates, numbers, missing-quarter handling and checks work.

**SEC pull results (your run 2026-11-15 13:02; log `data/issuance_insider/pull_sec_log.txt`) ✅**
- 80/80 quarters downloaded in 149 s; 3,441,089 P/S transactions in 1,253,418 filings; 0 duplicate filings or transactions across quarters. Filing dates 2006-01-03 to 2025-12-31; 15,428 issuers; 145,375 insiders.
- Purchases (P) per year 22,432 (2025) to 115,271 (2008 — insiders bought into the crisis); sales 70,349–442,415.
- Forms with a P/S row: Form 4 1,219,594; 4/A 26,966; Form 5 6,522; 5/A 336.
- Codes: P+acquired 846,591; S+disposed 2,585,020; inconsistent P+disposed 4,295 and S+acquired 5,183.
- Relationships are free-form: "Officer", "Director", "TenPercentOwner", "Director,Officer", … and some without commas ("TenPercentOwnerOther", "DirectorOther").
- Purchases: median 2 days from trade to filing; 85.3% filed within 5 days; 703 filed before the trade date; 0.6% flagged late.
- Apple's latest rows: sales by Tim Cook (Oct 2025) and Kevan Parekh (CFO), matching public filings.

**Profile on a copy (claude.ai workspace, 2026-11-15) — purchases, Form 4/5 originals, P + acquired: 821,040 rows in 393,381 filings:**
- 20% of purchase filings have no officer or director as reporting owner (pure 10% holders / other); 0.8% are joint filings with 2+ officers/directors.
- Trade-to-filing gap: > 30 days 7.8%, > 90 days 5.4%, > 180 days 3.7%; Form 5 = 2.2% of purchases, median 232 days late.
- Security title: 97.9% common stock / class / shares; the rest mostly partnership units.
- Price 0 or missing: 2.0%.
- Linking: 90.4% of issuers with purchases have a gvkey via a valid CIK link; 81.2% of issuer-dates link to a permno at the filing date; 84% of those permnos are in the panel. **98.2% of panel rows 2006–2025 have a gvkey with a valid CIK link** (so "no insider buying" can be told apart from "no data").

## Step 8 — Construct (`insider_cluster`) ✅ (rules approved 2026-11-15; price check: option 3, keep everything; **your run 2026-11-15 14:49: `insider_cluster_monthly.parquet` (2,796,065 rows) and `insider_cluster_events.parquet` (1,206,567 rows) identical to the test run**; log `data/issuance_insider/build_insider_log.txt` identical apart from the timestamp and the order of tied rows in the "largest clusters" table — that sort made deterministic afterwards, data unaffected)
1. **Trades:** purchases = code P + acquired; sales = S + disposed (drop the ~9,500 inconsistent rows). Form 4 and Form 5 originals; amendments (4/A, 5/A) dropped.
2. **Insiders:** reporting owner whose relationship contains "officer" or "director" (any spelling or combination); pure 10% holders and "other" excluded. A joint filing counts as **one** insider (the first officer/director on it), so a director and her trust are not a "cluster".
3. **Stale trades:** drop trades filed **more than 90 days** after the trade (5.4%, mostly Form 5) — they are old news when public.
4. **Public date:** next trading day after the filing date (Step 6); trades filed before their trade date (703) dropped.
5. **Link:** issuer CIK → gvkey (valid CIK links) → permno (CCM link valid at the filing date; primary link if several).
6. **A (primary):** a purchase is *clustered* if a different officer/director of the same firm bought on the same or an adjacent trading day; it counts once **both** filings are public. Value at month-end *t* = number of different insiders with clustered purchases public in the last 3 months (0 = none).
7. **B:** number of different officer/director buyers public in the last month. **C:** purchase dollars (shares × price; rows with no price skipped) public in the last 3 months ÷ market value at *t* (panel `me`). **D:** (buy − sell) ÷ (buy + sell) over 6 months, counting **insider-days** (one per insider, day and direction), so a sale split into many rows counts once.
8. **Zero vs blank:** firm-months whose gvkey has a valid CIK link get 0 when no insider bought; firms without a CIK link stay blank (we cannot see their filings). Before 2006 (and before each window is full: A and C from 2006-03, D from 2006-06): blank. D blank if no insider traded in the 6 months.
9. **Files:** event file = one row per insider purchase/sale (permno, gvkey, `period_end` = trade date, `published_date`, `date_source = exact`, `source`, `version = original`, inputs); monthly file on the panel's rows with A–D, `period_end` (latest trade used), `published_date` (latest filing used), `date_source`, `source`.

**Approved (user, 2026-11-15: "Okay").** Column names: `insider_cluster` (A, primary), `insider_buyers_1m` (B), `insider_buy_value_3m` (C), `insider_npr_6m` (D).
**Details added while writing the script** (within the approved rules):
- Common stock only (Step 4b rule): titles naming preferred, warrants, notes, debentures, bonds, rights or options dropped (0.8% of purchases, almost all preferred).
- CIK → gvkey must be valid **at the filing date**; if several gvkeys qualify: one with a CRSP link at that date, then source CRSP/Compustat Merged > Compustat Security > Compustat Company > Capital IQ, then latest link start. **Extended in Step 9 (2026-11-15, link fix):** if no link is dated at the filing date but the CIK links to exactly one gvkey, use it (`cik_link = undated`).
- Signals computed per **firm** (gvkey) and given to each of its permnos; C divides by the firm's total market value (sum of `me` over its permnos; `me` is in $ thousands).
- A filing that repeats exactly the same insider, day, direction, shares and dollars as an earlier one is dropped (3,287 re-reports).
- An insider-day is public at its earliest filing; a cluster purchase counts once its earliest partner is also public.
- `date_source`: `exact` when A > 0, `no event` when A = 0, blank when A is blank.

**Test run on a copy of your data (claude.ai workspace, 2026-11-15; 106 s):**
- Kept purchases (rows): 850,886 → code agrees 846,591 → original Form 4/5 821,040 → common stock 814,823 → filed within 0–90 days 771,066 → officer/director 561,227 → linked to a gvkey 540,529 (96.3%). Sales: 2,590,203 → 2,186,269.
- 343,353 purchase and 863,214 sale insider-days; 12,167 firms; 114,946 insiders.
- **46.1% of purchase insider-days are clustered** (Kang, Kim & Wang's abstract: over 40% of insider trades are clustered — consistent). Cluster sizes: 2 insiders 39%, 3 18%, 4 11%, 5 8%, 6+ 24%.
- Panel rows from 2006-06: 96.9% observable (value 0 or more); A > 0 in 6.8% (2008: 11.3%; 2024: 4.7%); A = 1 only 0.03%. B > 0 9.2%; C > 0 21.1%; D has a value 69.7%.
- Rank correlations: A–B 0.41, A–C 0.55, A–D 0.39, C–D 0.68.
- All A > 0 rows: published_date ≤ date, period_end ≤ published_date; median 1.5 months from latest trade to month-end.

**Problems found in the test (decision needed):**
1. **Not every code P is an open-market buy** (P = "open market or private purchase"). The 5 largest same-day clusters (Eastern Bankshares 24 insiders 2020-10-14, Chicopee Bancorp, CBOE Holdings, UL Solutions, Danvers Bancorp) all happened in the stock's **first CRSP month — insiders buying in the IPO / bank conversion**. 4.5% of purchase insider-days are dated before the stock's first CRSP month-end (7.0% of clustered ones). Others recur like a plan: California Water Service had 17–21 insiders buying in early March of each year 2010–2013.
2. **Price typos break C:** e.g. a 2024 purchase reported at about $5.4 million per share gives C = 377,051 × the firm's market value; 1,255 firm-months have C > 10% of market value. 1.3% of purchases are priced more than 2× away from the CRSP month-end price.
**Options:**
- **1 (recommended). CRSP daily price check:** keep a purchase or sale only if the stock traded on CRSP that day and the reported price is within that day's low–high range (with a 5% tolerance for rounding and averaged prices). Removes pre-listing (IPO) purchases, purchases in discounted offerings, and price typos in one rule. Needs one small WRDS pull (daily low, high, close for the trade days only). Plan purchases at market price remain.
- 2. No new data: drop trades dated before the stock's first CRSP month, and prices more than 2× off the CRSP month-end price. Cruder; misses offering purchases.
- 3. Keep as is (anchor paper taken literally) and deal with outliers in Step 9.
- Not recommended now: a routine-trader filter (Cohen, Malloy & Pomorski) as a fifth column — the named checks were fixed in Step 4b.

**Decision (user, 2026-11-15): option 3 — keep everything** ("Keep everything."). The build stays as tested: every code P / S row that passes rules 1–9 counts, including IPO, offering and plan-like purchases; no price check. Consequences to carry into Step 9 and the backtest:
- Step 9 reports the outliers (C above 10% of market value; the largest clusters and whether they fall in the stock's first CRSP month) and the 3-firm checks; no values are changed.
- `insider_buy_value_3m` (C) keeps the price-typo outliers (up to 377,051 × market value) → the backtest should use it by rank (or cross-sectional percentile), never raw.
- A (primary) counts people, not dollars, so price typos do not affect it; IPO-month clusters do (they enter a new stock's first 1–3 panel months).
- If the backtest suggests mechanical clusters matter, the daily price check (option 1) can be added later as a new, separately recorded version — not a silent change to A.

## Step 9 — Validate (`insider_cluster`) ✅ (done 2026-11-16; link fix adopted; **your runs 2026-11-15 17:06 / 17:10: 8 PASS, 0 FAIL, 2 INFO — build log, validation log, `insider_cluster_monthly.parquet` (2,796,065 rows) and `insider_cluster_events.parquet` (1,219,316 rows) identical to the test run apart from timestamps**; hand check of the EDGAR links: **all 17 Form 4s match**, checked by Claude at your request on 2026-11-16)
**Script:** `signals/issuance_insider/validate_insider_cluster.py` (no WRDS; changes nothing; log `data/issuance_insider/validate_insider_log.txt`; ~1.5 min).

**First test run (copy, before the link fix): 7 PASS, 0 FAIL, 3 INFO.** It found the **link-date gap**: filings whose issuer CIK links to exactly one gvkey but whose link dates start later (99%) or end earlier than the filing were dropped — 1,191 purchases (0.22% of those kept) and 45,468 sales in panel months, 34,969 of them Google Inc 2006-01 to 2007-04 (its link starts 2007-04-14). Such firms still counted as observable, so the gap produced **false zeros** (e.g. 155 firm-months with A = 0 where a cluster happened), not blanks.
**Decision (user, 2026-11-15: "fix"):** if no Valid link is dated at the filing date and the issuer CIK links to exactly one gvkey, use that gvkey (a CIK is one company's permanent ID; the link dates add nothing). Event-file column `cik_link` = `dated` / `undated`. Observability (0 vs blank) unchanged. Build and validation updated; the independent recomputation applies the same rule.

**Test run after the fix (copy, 2026-11-15; build 106 s, validation 83 s): 8 PASS, 0 FAIL, 2 INFO.**
- Build: +7,401 purchase and +55,202 sale rows (587 issuers) via undated links; events 1,219,316 (12,757 undated); purchase insider-days 348,824, 46.1% clustered; A > 0 rows 63,607 → 63,762; monthly file identical to the fallback test run.
1. Keys ✅ — monthly file = the panel's 2,796,065 rows; no duplicate stock-months or events.
2. Coverage ✅ — 96.9% of panel rows from 2006-06 have a value (2006 80% because of the window start; 96–99% after). Blank rows (3.1%): no gvkey 5,194; gvkey without any Valid CIK link 20,864; link not dated at the month-end 2,971. ETFs: none in the panel.
3. Dates ✅ — every event public on the next trading day after its filing, filed 0–90 days after the trade, `exact`; every A > 0 value (63,762 rows) uses only filings public by its month-end.
4. **Independent recomputation ✅ — 86,501 values (A, B, C, D) in 308 firms rebuilt from the raw SEC rows with separate plain-loop code: 0 mismatches.** Sample: 150 firms with clusters, 100 with buys only, 50 with sales only, + Meta, Alphabet, NVIDIA, Tesla, Apple and the hand-check firms (seed 2026; firms whose CIKs link only to them).
5. Name / CIK change ✅ — Meta (rename 2021-10-28, same CIK): 2,441 events from one CIK, 1,751 before / 690 after; no blank months 2012-06+. Google Inc (CIK 1288776, events 2006-01-04 to 2015-10-05; 434 recovered by the fix) → Alphabet (CIK 1652044, from 2015-10-13): one gvkey, 8 days apart, no blank months.
6. Splits ✅ — reported prices are in trade-date units: median price ÷ CRSP unadjusted month-end price 0.97–1.01 in the 12 months before and after NVIDIA 2024-06 (10-for-1) and Tesla 2020-08 (5-for-1), 2022-08 (3-for-1); 96–100% within 1.5×. So dollar values (C) do not jump at splits.
7. Consistency ✅ — A, B whole numbers ≥ 0; C ≥ 0; D in [−1, 1]; every A > 0 row from 2006-06 has D (2006-03 to 05: D not yet defined, by design). A = 1 in 268 rows (0.42% of A > 0: partner made public outside the window). A > 0 but C = 0 in 793 rows (1.25%: no usable price).
8. Link fix ✅ — all 12,900 recovered insider-days are in the event file. Still dropped: 4,771 rows (764 purchases, 32 issuers) whose CIK links to several gvkeys with none dated (ambiguous); 29,170 rows (12,533 purchases, 1,152 issuers) whose CIK has no Valid link at all (mostly firms outside CRSP/Compustat).
9. Outliers (INFO) — C > 10% of market value in 1,265 firm-months (418 firms); > 100% in 180. The 10 largest are all price typos: the reported "price" is the total dollar amount (e.g. 1,580,180 shares at "$5,420,020" vs CRSP $4.05). Largest same-day clusters: 7 of the top 10 in the stock's first CRSP month (IPOs). A > 0 rows in a stock's first 3 CRSP months: 3,037 of 63,762 (4.8%); A > 0 in 23.3% of such young-stock months vs 6.6% of others. Kept, as decided in Step 8.
10. Three firms to check by hand (INFO) — links to each Form 4 in the log:
   - General Electric, 2008-11: CEO Jeffrey Immelt and Michael Neal (officer) each bought 50,000 shares on 2008-11-13 (reported $16.42 and $14.99), filed the same day → A = 2 for 2008-11 to 2009-01.
   - Old Line Bancshares (small bank, CIK 1253317), 2016-05 to 07: directors Suit, Graham and Shah bought 2,000–5,000 shares on 2016-05-10/11 at about $19; more in June; on 2016-06-24 and 07-01 officers and a director bought **fractions of a share** (4–19 shares), all filed 2016-07-07 — plan-type purchases (e.g. dividend reinvestment) coded P, kept under "keep everything" → A = 4–6 in 2016-06 to 10.
   - Eli Lilly, 2025-08: 6 insiders (CEO David Ricks, 3 directors, 2 officers) bought 117–1,632 shares each on 2025-08-12/13 at $634–660 → A = 6 for 2025-08 to 10.
   - Apple: A > 0 in 0 of 238 months; any buyer in 4 months; median D −1 (only sales).
   **Hand check (Claude, in the built-in browser at your request, 2026-11-16): all 17 Form 4s match** — read from the SEC's own copies of each filing (`<accession>.txt`, the XML inside): issuer, reporting owner, role, form type, filing date, and every transaction row (27 rows: date, code P, acquired, shares, price, common stock).
   - Multi-row filings add up as the build summed them: Immelt's 50,000 = 5 rows of 21,700 + 7,518 + 6,400 + 3,400 + 10,982 at $16.41–16.45 (share-weighted $16.42); Rivest 2016-06-01 = 4 rows totalling 1,700 at $17.32 average; Fyrwald 686 + 879 = 1,565 at $642.33; Suit 2016-06-24 = 8.637 + 3.23 = 11.867 (one row for his trust, one for his spouse's trust, F1/F2).
   - Roles as filed: Immelt Chairman and CEO; Neal Vice Chairman; Hubbard SVP, CFO; Semanie COO; Ricks President, Chair and CEO; Skovronsky EVP, CSO; Van Naarden EVP, Lilly Oncology.
   - Old Line's fractional purchases: the filings give no reason (no footnote on Hubbard's or Semanie's). Several insiders buying fractions of a share on the same days at identical prices ($17.92 on 2016-06-24, $17.96 on 07-01) looks like an automatic plan (e.g. dividend reinvestment) — not confirmed. Kept under "keep everything".

## Step 10 — Save (`insider_cluster`) ⏳ (catalog row written 2026-11-15; upload and commit: yours)
- **Catalog:** your OK (2026-11-15): one row per signal. **Both rows appended to `public_data/factor_catalog.csv`** — `net_issuance` (category `issuance`, new) and `insider_cluster` (category `insider`, new); the 27 existing rows unchanged; same 19 columns and Windows line endings as the file. GitHub's copy is identical to yours apart from line endings, and GitHub `main` is still b080bff (checked 2026-11-16), so no one else has pushed since your last sync → no conflict expected.
- `insider_cluster` row in short: `status` have-data · `data_shape` firm-level · `in_panel` no · `frequency` monthly (updates with each Form 4) · `coverage_start` 2006-03 · `coverage_end` 2025-12 · `added_by` raghavrc · `date_added` 2026-11-15 · `test_results` empty; `location` names the three checks and the event and raw files; `timing_rule` exact (filing date → next trading day; cluster counts once its partner is public); `notes` state the "keep everything" decision, the price typos in check C, the 2006 start and the out-of-sample years.
- **Storage (private drive, same folder layout as `data/`):** `data/issuance_insider/insider_cluster_monthly.parquet` (4.7 MB) and `insider_cluster_events.parquet` (35 MB), plus `net_issuance_monthly.parquet` (82 MB) and `net_issuance_events.parquet` (17 MB). Optional: `sec_trans.parquet`, `sec_submissions.parquet`, `sec_owners.parquet` (116 MB; anyone can rebuild them free with `pull_sec_insiders.py`); not `sec_raw/` (1 GB of zips). The SEC data is public, but these files carry gvkey/permno and CRSP market values (licensed) → private drive, not `public_data/`.
- **Commit (one commit for both signals; never `data/`):** in VS Code Source Control, stage only
  - `signals/issuance_insider/`: `pull_net_issuance.py`, `measure_share_timing.py`, `build_net_issuance.py`, `validate_net_issuance.py`, `get_osap_shareiss.py`, `probe_insiders.py`, `pull_sec_insiders.py`, `build_insider_cluster.py`, `validate_insider_cluster.py`, `progress.md`
  - `public_data/factor_catalog.csv`
  - message: `Add issuance_insider signals: net_issuance and insider_cluster (scripts, progress notes, catalog rows)` → Commit → Sync Changes.

## Open questions
- ~~Combination rule (A / B / C)~~ → B (two signals), with combination rules C1 and C2 named in advance.
- ~~Signal names and build order~~ → `net_issuance` first, then `insider_cluster` (approved 2026-11-14).
- ~~Step 4b~~ → A, B, C all built (A primary, B and C named robustness checks), approved 2026-11-14.
- ~~Step 5: anything extra on the shared drive?~~ → no.
- ~~Step 6: skip rule~~ → 1 (primary, 2 months if the measurement says so) + 2 as `net_issuance_skip6` (approved 2026-11-14).
- ~~Factor direction~~ → **multiply** (Step 7, C2).
- ~~Skip after the timing measurement~~ → primary 4 months; 3-month and exact-date versions as named checks (2026-11-14).
- `version = original` for CRSP share counts — does CRSP ever revise share history? (VERIFY; affects only the label.)
- SPACs in the panel: trust redemptions look like huge buybacks → backtest with and without SIC 6770 (decide before looking at returns).
- ~~Step 6: which months to skip~~ → measured; 4 months (2026-11-14).
- Catalog layout for `net_issuance`: one row (recommended) or one per column — awaiting your OK.

**For signal 2 (`insider_cluster`):**
- Size and capacity: insider-buying returns are concentrated in small, illiquid stocks → test equal- and value-weighted; check names per month.
- Disagreement case: firm buying back while insiders sell — treat differently? (Step 4b.)
- Routine vs opportunistic insider filter, cluster window, number of insiders → Step 4b definitions.
- Insider data source on WRDS (Thomson/LSEG insider filings? SEC Form 4 data sets?) → Step 5 **(VERIFY)**.
