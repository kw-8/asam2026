# Timing Reference

When was a number actually knowable? Use this in the timing-profile step, before any download.
Authoritative over the model's memory; if this file is silent or wrong, stop and ask. Items marked **(VERIFY)** are not confirmed against an official source.

**Core rule:** A value can be used at month-end *t* only if its `published_date <= t`. Record `date_source = exact` when the date comes from a real field (`rdq`, EDGAR acceptance time). Record `assumed` when it comes from a fallback lag.

---

## 1. SEC periodic report deadlines (current rules)

Days are calendar days after the period end. If the deadline falls on a weekend or holiday, it moves to the next business day.

| Filer category | Public float (roughly) | 10-K (annual) | 10-Q (quarterly) |
|---|---|---|---|
| Large accelerated | ≥ $700M | **60 days** | **40 days** |
| Accelerated | $75M – $700M | **75 days** | **40 days** |
| Non-accelerated (incl. most small reporting companies) | < $75M, or revenue < $100M since 2020 | **90 days** | **45 days** |

- No 10-Q is filed for fiscal Q4. Q4 figures first appear in the earnings release, then in the 10-K.
- **Late filers:** Form NT 10-K / NT 10-Q (Rule 12b-25) gives an automatic extra **15 days** for a 10-K and **5 days** for a 10-Q. Some firms file even later. Deadlines are a typical date, not a guarantee.
- **History matters:** before the 2002–2006 phase-in, *all* filers had **90 days (10-K) / 45 days (10-Q)**. Accelerated deadlines phased in for fiscal periods ending around Dec 2003 (10-K 75 days), Dec 2004 (10-Q 40 days), and Dec 2006 (large accelerated 10-K 60 days). **(VERIFY: exact phase-in dates)** For 1980s–1990s data, assume the 90/45-day rules.
- Filer category is not in CRSP/Compustat directly. When unsure, assume the **slowest (non-accelerated)** deadline.

## 2. Earnings announcements and Form 8-K

- Most firms announce earnings in a **press release before the 10-Q/10-K**, typically 3–6 weeks after quarter end for large firms and later for small ones.
- Form 8-K **Item 2.02** (Results of Operations) is required when a company publicly releases earnings, due within **4 business days**. In practice it is usually furnished the same day as the press release.
- The press release often has headline numbers (EPS, revenue, sometimes a balance sheet) but not every line item. Detailed items such as segment data, footnotes or some cash-flow lines may only be known at the 10-Q/10-K filing date. Choose the date that matches the **specific inputs** the signal uses.

## 3. Compustat `rdq` (report date of quarterly earnings)

- Field in `comp.fundq` only. It is the date quarterly earnings were **first publicly reported**, usually the earnings press release, **not** the 10-Q filing date.
- For annual data, use the fiscal Q4 row's `rdq` from `fundq` as the annual announcement date.
- **Coverage gaps:**
  - Sparse or missing in early years (roughly before the early-to-mid 1970s, and patchy into the 1980s). **(VERIFY: coverage by year on our sample; compute % non-null `rdq` by year)**
  - Missing for some small firms and for some fiscal quarters even in recent years.
- **Sanity filters** (common practice): keep `rdq` only if `rdq > datadate` and `rdq - datadate <= ~180 days`. Otherwise treat it as missing and use the fallback.
- Even with `rdq`, an announcement made **after the close** is only tradable the next trading day (section 4). `rdq` has no time of day, so the conservative rule is: tradable from the trading day after `rdq`.

## 4. EDGAR: filing date vs acceptance timestamp

- Every EDGAR filing has a **filing date** and an **acceptance date-time** (`acceptanceDateTime` in EDGAR's submissions JSON / filing index).
- **5:30 p.m. rule (Reg S-T Rule 13(a)):** a filing submitted by 5:30 p.m. ET gets that day's filing date. Most filings submitted after 5:30 p.m. get the **next business day** as their filing date and are published at 6:00 a.m. that day. (Forms 3, 4, 5, 144 are exceptions and are accepted until 10 p.m. with a same-day date.)
- **After-close rule (team rule):** US markets close at **4:00 p.m. ET**. Anything accepted after 4:00 p.m. counts from the **next trading day**. Filing date alone is not enough: a 4:45 p.m. filing has today's filing date but is after the close.
- If only the filing date is known (no timestamp), assume it is tradable from the **next trading day**.
- EDGAR electronic filing was phased in from 1993 to 1996 **(VERIFY)**. Earlier filings have no EDGAR dates, so use `rdq` or the fallback lag.

## 5. Restatements and point-in-time data

- **Compustat overwrites history.** When a firm restates, `funda` / `fundq` (`datafmt='STD'`) generally show the **revised** numbers, not what investors saw on the original date. That is look-ahead bias, usually small for most items but large for restating firms.
- What to do:
  1. Prefer the **earliest available** version when the source offers one. Compustat has "as first reported" or unrestated quarterly data and a point-in-time product (Compustat Snapshot). **(VERIFY: our WRDS subscription and table names, e.g. `comp_snapshot` library)**
  2. If only restated data is available, keep `version = restated` in the event file and say so in the signal definition (success criterion 8).
  3. EDGAR XBRL data (2009+) holds each filing's originally reported values, which makes it a point-in-time alternative for recent years.
- Ratios built from the WRDS Financial Ratios Suite inherit Compustat's restated values.

## 6. Recommended fallback lags (no exact date available)

Use these only when `rdq` / EDGAR dates are missing. Record `date_source = assumed`.

| Data | Fallback `published_date` | Why |
|---|---|---|
| Quarterly (`fundq`) | `datadate` + **4 months**, as month-end | Covers the 45-day 10-Q deadline plus late and NT filers; common in the literature (e.g. Hou–Xue–Zhang use `rdq`, otherwise a lag) |
| Annual (`funda`) | `datadate` + **6 months**, as month-end | Fama–French convention (fiscal year *t* data used from June of *t+1*); covers 90-day 10-K plus late filers |
| Market data (CRSP prices, returns, volume) | No lag; known at month-end | Not late-reported |
| WRDS Financial Ratios Suite | Use `public_date` as given (about 2 months after period end) | Can be **too early** for small firms, so consider adding a lag for small-cap signals and check per signal |

- More aggressive lags (e.g. 3 months quarterly, 4 months annual) need user approval in the timing step, with the reason recorded in `state.yaml`.
- Always convert to the panel's convention: `date` = calendar month-end, and the signal at `date` uses the latest event with `published_date <= date`.

## 7. Quick checklist for the timing-profile step

1. Is the data late-reported (accounting, filings) or market data?
2. Is there an exact date field? (`rdq`, EDGAR acceptance time, `public_date`) What is its coverage by year?
3. Which documents carry the specific inputs (press release vs 10-Q/10-K)?
4. Apply the after-close rule: count from the next trading day.
5. Restated or original values? Record `version`.
6. Missing dates: apply the section 6 fallback, record `date_source = assumed`, and report the share of assumed dates.
