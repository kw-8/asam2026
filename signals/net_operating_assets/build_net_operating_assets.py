"""
build_net_operating_assets.py
=============================
Step 8 (Construct) of prompts/data_acquisition.md for signals/net_operating_assets.

Builds two files from data already on disk (no WRDS login needed):

  data/net_operating_assets/noa_events.parquet
      One row per firm (gvkey) x fiscal year-end: the balance-sheet inputs, the
      signals, the parts of NOA, and the date the 10-K became public.
  data/net_operating_assets/noa_monthly.parquet
      Every row of the panel (permno x month-end) with the signals and, when they
      are blank, the reason.

Definitions agreed in Steps 1-8 (see progress.md). All divided by total assets of
the previous fiscal year (at_prev) unless stated:
  noa          PRIMARY SIGNAL. Hirshleifer-Hou-Teoh-Zhang (2004), as published:
               (OA - OL) / at_prev, OA = at - che, OL = at - dlc - dltt - mib - pstk - ceq,
               i.e. (ceq + pstk + mib + dltt + dlc - che) / at_prev.
  noa_mi       robustness only: minority-interest fix for fiscal 2009+ (FAS 160).
               OL = lt - dlc - dltt, so nonredeemable minority interest counts as
               financing. Identical to noa before 2009. The 2019 operating-lease
               shift (ASC 842) is NOT fixed (no access to the lease items).
  noa_at_cur   side check (Definition B): noa's numerator / this year's at.
  dnoa         change in NOA dollars from the previous fiscal year / at_prev.
  asset_growth at / at_prev - 1.
  p_*          parts (event file only): p_oa = p_rect + p_invt + p_ppent + p_intan
               + p_other_oa (p_gdwl is inside p_intan); p_ol (with p_ap inside it);
               p_equity + p_debt - p_cash = noa = p_oa - p_ol.
Missing che, dlc, dltt, mib, pstk count as 0 (as HHTZ / OSAP); at > 0 and ceq are
required; at_prev only from a fiscal year-end 10-14 months earlier, and > 0.

Timing (Step 6): published_date = 10-K filing date (comp.co_filedate, srctype 10K),
  UTC clock time converted to New York: before 4:00 p.m. counts that day, otherwise
  (or with no time) from the next trading day. No 10-K date: datadate + 6 months as
  month-end, date_source = assumed. Very late filing dates are trusted. Values are
  Compustat's current (restated) numbers: version = restated. Same code as
  signals/rd_to_market/build_rd_to_market.py.
Choices (Step 8): signal on the CCM-linked (primary) share class only, other
  classes blank; financial = panel CRSP siccd 6000-6999 that month; a balance sheet
  is usable until 18 months after its fiscal year-end; raw values, no winsorizing.
Splits: no adjustment needed (dollar amounts only, nothing per share, no price).

Run from the repo root, with the .venv active (after the Step 7 pulls):
    python signals\\net_operating_assets\\build_net_operating_assets.py
Everything printed is also saved to data/net_operating_assets/build_log.txt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "net_operating_assets"

PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
FUNDA = OUT / "funda_noa.parquet"
NCI = OUT / "funda_nci.parquet"                                   # check only
FILEDATES = DATA / "capex_intensity" / "co_filedate.parquet"
CCM = DATA / "capex_intensity" / "ccm_links.parquet"
CRSP_IDS = DATA / "issuance_insider" / "crsp_monthly.parquet"     # permco for every panel row
TDAYS_1993 = DATA / "lazy_prices" / "trading_days.parquet"
TDAYS_PRE = DATA / "rd_to_market" / "trading_days_pre1993.parquet"

FALLBACK_MONTHS = 6          # Step 6: no 10-K date -> datadate + 6 months (month-end), assumed
MAX_AGE_MONTHS = 18          # Step 8: usable until 18 months after fiscal year-end
CLOSE_ET = 16                # 4:00 p.m. New York
PREV_DAYS = (300, 430)       # previous fiscal year-end must be 10-14 months earlier
SOURCE = "comp.funda balance sheet (restated); comp.co_filedate 10-K date"
SIGNALS = ["noa", "noa_mi", "noa_at_cur", "dnoa", "asset_growth"]
PARTS = ["p_oa", "p_rect", "p_invt", "p_ppent", "p_intan", "p_gdwl", "p_other_oa",
         "p_ol", "p_ap", "p_equity", "p_debt", "p_cash"]


class Tee:
    """Print to the screen and to build_log.txt at the same time."""
    def __init__(self, path: Path):
        self.file = open(path, "w", encoding="utf-8")
        self.screen = sys.stdout

    def write(self, text):
        self.screen.write(text)
        self.file.write(text)

    def flush(self):
        self.screen.flush()
        self.file.flush()


def ns(s: pd.Series) -> pd.Series:
    """Same datetime unit everywhere (parquet files come back as ms, us or ns)."""
    return pd.to_datetime(s).astype("datetime64[ns]")


# ----------------------------------------------------------------------------
# Trading calendar and the after-close rule (same as rd_to_market)
# ----------------------------------------------------------------------------
def trading_calendar() -> pd.DatetimeIndex:
    pre = ns(pd.read_parquet(TDAYS_PRE)["date"])
    post = ns(pd.read_parquet(TDAYS_1993)["date"])
    days = pd.DatetimeIndex(sorted(set(pre) | set(post)))
    # after the last calendar day (2026 filings), weekdays stand in for trading days
    extra = pd.bdate_range(days.max() + pd.Timedelta(days=1), "2027-12-31")
    return days.append(extra)


def next_trading_day(dates: pd.Series, days: pd.DatetimeIndex, same_day_ok: pd.Series) -> pd.Series:
    """First trading day on/after `dates` where same_day_ok, else strictly after."""
    d = dates.to_numpy(dtype="datetime64[ns]")
    side = np.where(same_day_ok.to_numpy(), "left", "right")
    out = np.empty(len(d), dtype="datetime64[ns]")
    for s in ("left", "right"):
        m = side == s
        out[m] = days.values[np.minimum(np.searchsorted(days.values, d[m], side=s), len(days) - 1)]
    return pd.Series(out, index=dates.index)


# ----------------------------------------------------------------------------
# 1. Signals on the annual file
# ----------------------------------------------------------------------------
def compute_signals(f: pd.DataFrame) -> pd.DataFrame:
    f = f.sort_values(["gvkey", "datadate"]).reset_index(drop=True)
    z = {c: f[c].fillna(0.0) for c in ["che", "dlc", "dltt", "mib", "pstk"]}
    f["noa_dollars"] = f["ceq"] + z["pstk"] + z["mib"] + z["dltt"] + z["dlc"] - z["che"]
    oa = f["at"] - z["che"]
    ol = f["at"] - z["dlc"] - z["dltt"] - z["mib"] - z["pstk"] - f["ceq"]
    # minority-interest fix: operating liabilities = total liabilities - debt
    ol_mi = (f["lt"] - z["dlc"] - z["dltt"]).where(f["lt"].notna(), ol)

    g = f.groupby("gvkey", sort=False)
    gap = (f["datadate"] - g["datadate"].shift(1)).dt.days
    prev_ok = gap.between(*PREV_DAYS)
    f["at_prev"] = g["at"].shift(1).where(prev_ok)
    noa_dollars_prev = g["noa_dollars"].shift(1).where(prev_ok)

    base = (f["at"] > 0) & f["ceq"].notna()
    valid = base & (f["at_prev"] > 0)
    d = f["at_prev"]
    f["noa"] = (f["noa_dollars"] / d).where(valid)
    f["noa_mi"] = ((oa - ol_mi) / d).where(valid)
    f["noa_at_cur"] = (f["noa_dollars"] / f["at"]).where(base)
    f["dnoa"] = ((f["noa_dollars"] - noa_dollars_prev) / d).where(valid & noa_dollars_prev.notna())
    f["asset_growth"] = (f["at"] / d - 1).where((f["at"] > 0) & (d > 0))

    f["p_oa"] = (oa / d).where(valid)
    for c in ["rect", "invt", "ppent", "intan", "gdwl", "ap"]:
        f[f"p_{c}"] = (f[c] / d).where(valid)
    have4 = f[["rect", "invt", "ppent", "intan"]].notna().all(axis=1)
    f["p_other_oa"] = ((oa - f["rect"] - f["invt"] - f["ppent"] - f["intan"]) / d).where(valid & have4)
    f["p_ol"] = (ol / d).where(valid)
    f["p_equity"] = ((f["ceq"] + z["pstk"] + z["mib"]) / d).where(valid)
    f["p_debt"] = ((z["dlc"] + z["dltt"]) / d).where(valid)
    f["p_cash"] = (z["che"] / d).where(valid)
    return f


# ----------------------------------------------------------------------------
# 2. Event file
# ----------------------------------------------------------------------------
def build_events(days: pd.DatetimeIndex, ccm: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_parquet(FUNDA)
    f["datadate"] = ns(f["datadate"])
    f["gvkey"] = f["gvkey"].astype(str)
    if NCI.exists():
        nci = pd.read_parquet(NCI, columns=["gvkey", "datadate", "mibn"])
        nci["gvkey"] = nci["gvkey"].astype(str)
        nci["datadate"] = ns(nci["datadate"])
        f = f.merge(nci, on=["gvkey", "datadate"], how="left")
    else:
        f["mibn"] = np.nan
    f = compute_signals(f)

    fd = pd.read_parquet(FILEDATES)
    fd = fd[fd["srctype"] == "10K"].copy()
    fd["gvkey"] = fd["gvkey"].astype(str)
    fd["datadate"] = ns(fd["datadate"])
    fd["filedate"] = ns(fd["filedate"])
    # earliest 10-K per firm-year (one row each in practice)
    fd = fd.sort_values("filedate").drop_duplicates(["gvkey", "datadate"], keep="first")
    # the stored timestamp's date is the download date; only its clock time (UTC) is real
    t = pd.to_datetime(fd["filedatetime"])
    fd["utc_clock"] = t - t.dt.normalize()

    e = f.merge(fd[["gvkey", "datadate", "filedate", "utc_clock"]], on=["gvkey", "datadate"], how="left")
    has_time = e["utc_clock"].notna()
    utc = (e.loc[has_time, "filedate"] + e.loc[has_time, "utc_clock"]).dt.tz_localize("UTC")
    ny = utc.dt.tz_convert("America/New_York").dt.tz_localize(None)
    e["filetime_et"] = pd.Series(pd.NaT, index=e.index, dtype="datetime64[ns]")
    e.loc[has_time, "filetime_et"] = ny.astype("datetime64[ns]")
    # same day only if the time is known, before the close, and still on the filing date in New York
    same_day = has_time & (e["filetime_et"].dt.normalize() == e["filedate"]) & (e["filetime_et"].dt.hour < CLOSE_ET)
    exact = e["filedate"].notna()
    e["published_date"] = pd.NaT
    e.loc[exact, "published_date"] = next_trading_day(e.loc[exact, "filedate"], days, same_day[exact])
    e.loc[~exact, "published_date"] = e.loc[~exact, "datadate"] + pd.offsets.MonthEnd(FALLBACK_MONTHS)
    e["published_date"] = ns(e["published_date"])
    e["date_source"] = np.where(exact, "exact", "assumed")
    e["timing_rule"] = np.select(
        [exact & same_day, exact & has_time, exact],
        ["filed before 4pm ET: same day", "filed 4pm ET or later: next trading day",
         "filing date, no time: next trading day"],
        default=f"no 10-K date: datadate + {FALLBACK_MONTHS} months")

    e = e.rename(columns={"datadate": "period_end"})
    e["source"] = SOURCE
    e["version"] = "restated"

    # permno for the event = primary CCM link on the fiscal year-end (else on the publish date)
    for when in ("period_end", "published_date"):
        lk = e[["gvkey", when]].merge(ccm[["gvkey", "permno", "linkprim", "linkdt", "linkenddt"]], on="gvkey")
        lk = lk[(lk[when] >= lk["linkdt"]) & (lk[when] <= lk["linkenddt"])]
        lk = lk.sort_values("linkprim", key=lambda s: s.map({"P": 0, "C": 1})).drop_duplicates(["gvkey", when])
        col = f"permno_{when}"
        e = e.merge(lk[["gvkey", when, "permno"]].rename(columns={"permno": col}), on=["gvkey", when], how="left")
    e["permno"] = e["permno_period_end"].fillna(e["permno_published_date"]).astype("Int64")

    cols = (["permno", "gvkey", "period_end", "published_date", "date_source", "source", "version",
             "timing_rule", "filedate", "filetime_et", "fyear", "fyr", "curcd"]
            + SIGNALS + PARTS
            + ["at", "at_prev", "che", "dlc", "dltt", "mib", "mibn", "pstk", "ceq", "lt",
               "rect", "invt", "ppent", "intan", "gdwl", "ap", "noa_dollars"])
    return e[cols].sort_values(["gvkey", "period_end"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# 3. Monthly file
# ----------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    p = pd.read_parquet(PANEL, columns=["permno", "gvkey", "date", "siccd"])
    p["permno"] = p["permno"].astype("int64")
    p["date"] = ns(p["date"])
    p["siccd"] = pd.to_numeric(p["siccd"], errors="coerce").astype("Int64")
    p = p.rename(columns={"gvkey": "gvkey_panel"})
    ids = pd.read_parquet(CRSP_IDS, columns=["permno", "permco", "date"])
    ids["permno"] = ids["permno"].astype("int64")
    ids["date"] = ns(ids["date"])
    p = p.merge(ids, on=["permno", "date"], how="left")
    p["permco"] = p["permco"].fillna(-p["permno"]).astype("int64")   # unknown permco: the stock stands alone
    return p


def build_monthly(events: pd.DataFrame, ccm: pd.DataFrame) -> pd.DataFrame:
    p = load_panel()
    print(f"  panel: {len(p):,} rows, {p['permno'].nunique():,} permnos, "
          f"{p['date'].min():%Y-%m} to {p['date'].max():%Y-%m}")

    # gvkey from the CCM link in force at the month-end (primary links only)
    lk = p[["permno", "date"]].merge(ccm[["permno", "gvkey", "linkprim", "linkdt", "linkenddt"]], on="permno")
    lk = lk[(lk["date"] >= lk["linkdt"]) & (lk["date"] <= lk["linkenddt"])]
    lk["prim_rank"] = lk["linkprim"].map({"P": 0, "C": 1})
    lk = lk.sort_values("prim_rank").drop_duplicates(["permno", "date"])
    p = p.merge(lk[["permno", "date", "gvkey", "prim_rank"]], on=["permno", "date"], how="left")
    # one permno per gvkey and month (if two are linked, keep P before C)
    p = p.sort_values(["prim_rank", "permno"], na_position="last")
    dup = p["gvkey"].notna() & p.duplicated(["gvkey", "date"], keep="first")
    p.loc[dup, "gvkey"] = np.nan
    # a share class with no link of its own, whose firm (permco) has a linked class that month
    p["firm_linked"] = p["gvkey"].notna().groupby([p["permco"], p["date"]]).transform("any")

    # latest event public by the month-end; an event that is older than one already
    # public (a late refiling of an earlier year) never replaces the newer one
    ev = events.sort_values(["gvkey", "published_date", "period_end"]).copy()
    ev["newest_so_far"] = ev.groupby("gvkey")["period_end"].cummax()
    ev = ev[ev["period_end"] >= ev["newest_so_far"]]
    ev = ev.sort_values("published_date")
    keep = ["gvkey", "period_end", "published_date", "date_source", "source", "version",
            "timing_rule", "at", "ceq", "at_prev"] + SIGNALS
    linked = p[p["gvkey"].notna()].sort_values("date")
    linked = pd.merge_asof(linked, ev[keep], left_on="date", right_on="published_date",
                           by="gvkey", direction="backward")
    p = pd.concat([linked, p[p["gvkey"].isna()]], ignore_index=True)

    stale = p["period_end"].notna() & (p["date"] > p["period_end"] + pd.offsets.MonthEnd(MAX_AGE_MONTHS))
    has_event = p["period_end"].notna() & ~stale
    no_base = has_event & ~((p["at"] > 0) & p["ceq"].notna())
    p["status"] = np.select(
        [has_event & p["noa"].notna(),
         no_base,
         has_event,
         stale,
         p["gvkey"].notna(),
         p["gvkey"].isna() & p["firm_linked"],
         p["gvkey"].isna()],
        ["ok",
         "no total assets or common equity",
         "no prior-year report (first year)",
         f"latest 10-K older than {MAX_AGE_MONTHS} months",
         "no annual report public yet",
         "secondary share class",
         "no CCM link"],
        default="?")
    # stale rows keep no accounting fields
    for c in ["period_end", "published_date", "date_source", "version", "timing_rule"] + SIGNALS:
        p[c] = p[c].mask(stale)
    p["source"] = p["source"].fillna(SOURCE)
    p["financial"] = p["siccd"].between(6000, 6999).fillna(False).astype(bool)

    cols = (["permno", "gvkey", "date"] + SIGNALS
            + ["financial", "status", "period_end", "published_date", "date_source", "source", "version",
               "timing_rule", "siccd", "permco", "gvkey_panel"])
    return p[cols].sort_values(["permno", "date"]).reset_index(drop=True)


def pct(s: pd.Series) -> str:
    return ", ".join(f"p{int(q * 100)} {s.quantile(q):.3f}" for q in (0.01, 0.25, 0.5, 0.75, 0.99))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(OUT / "build_log.txt")

    days = trading_calendar()
    ccm = pd.read_parquet(CCM)
    ccm = ccm[ccm["linktype"].isin(["LU", "LC"]) & ccm["linkprim"].isin(["P", "C"])].copy()
    ccm["gvkey"] = ccm["gvkey"].astype(str)
    ccm["permno"] = ccm["permno"].astype("int64")
    ccm["linkdt"] = ns(ccm["linkdt"])
    ccm["linkenddt"] = ns(ccm["linkenddt"]).fillna(pd.Timestamp("2099-12-31"))

    print("1/2 Event file ...")
    ev = build_events(days, ccm)
    ev.to_parquet(OUT / "noa_events.parquet", index=False)
    print(f"  saved data/net_operating_assets/noa_events.parquet ({len(ev):,} rows, {ev['gvkey'].nunique():,} firms)")
    print("  how each publish date was set:")
    print(ev["timing_rule"].value_counts().to_string())
    print(f"  published_date before period_end: {(ev['published_date'] < ev['period_end']).sum()}")
    print(f"  firm-years with noa: {ev['noa'].notna().sum():,}; noa_at_cur: {ev['noa_at_cur'].notna().sum():,}")
    chk = ev.dropna(subset=["noa", "p_equity"])
    err = (chk["p_equity"] + chk["p_debt"] - chk["p_cash"] - chk["noa"]).abs().max()
    err2 = (chk["p_oa"] - chk["p_ol"] - chk["noa"]).abs().max()
    print(f"  parts add up to noa: max error {max(err, err2):.1e}")
    post = ev[(ev["period_end"].dt.year >= 2010) & ev["noa"].notna() & ev["mibn"].notna()]
    if len(post):
        close = ((post["noa_mi"] - post["noa"]) * post["at_prev"] - post["mibn"]).abs() <= 0.01 * post["at"]
        print(f"  noa_mi - noa = nonredeemable minority interest (mibn) / at_prev, fiscal 2010+: "
              f"{close.mean():.1%} of {len(post):,} (within 1% of assets)")
    pre = ev[(ev["period_end"].dt.year < 2009) & ev["noa"].notna()]
    print(f"  noa_mi = noa before fiscal 2009: {((pre['noa_mi'] - pre['noa']).abs() < 0.01).mean():.1%}")

    print("\n2/2 Monthly file ...")
    m = build_monthly(ev, ccm)
    m.to_parquet(OUT / "noa_monthly.parquet", index=False)
    print(f"  saved data/net_operating_assets/noa_monthly.parquet ({len(m):,} rows; "
          f"duplicate permno + date: {m.duplicated(['permno', 'date']).sum()})")
    print("\n  Why noa is blank (share of all panel rows):")
    print(m["status"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    ok = m[m["status"] == "ok"]
    print(f"\n  rows with noa: {len(ok):,}; exact dates {(ok['date_source'] == 'exact').mean():.1%}; "
          f"financial firms {ok['financial'].mean():.1%}")
    for c in SIGNALS:
        print(f"  {c:13s} rows {m[c].notna().sum():>9,}   {pct(m[c].dropna())}")
    print("\nDone. Reply 'done' in the chat and I'll run the Step 9 checks.")


if __name__ == "__main__":
    main()
