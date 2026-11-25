"""
build_shareholder_yield.py
==========================
Step 8 (Construct) of prompts/data_acquisition.md for signals/shareholder_yield.

Builds two files from data already on disk (no WRDS login needed):

  data/shareholder_yield/payout_events.parquet
      One row per firm (gvkey) x fiscal year-end: the payout inputs, the dollar
      payouts, and the date the 10-K became public.
  data/shareholder_yield/shareholder_yield_monthly.parquet
      Every row of the panel (permno x month-end) with the two yields and, when
      they are blank, the reason.

Definitions agreed in Steps 1-7 (see progress.md), Boudoukh, Michaely, Richardson
& Roberts (2007), annual Compustat, $ millions:
  pref_down   = max(pstkrv[t-1] - pstkrv[t], 0); pref_up = max(pstkrv[t] - pstkrv[t-1], 0)
                (previous fiscal year-end 10-14 months earlier; a missing change counts as 0)
  gross_payout = dvc + prstkc + pref_down
  net_payout   = gross_payout - (sstk - pref_up)
  net_payout_yield  PRIMARY SIGNAL  = net_payout   / firm market value at the month-end
  payout_yield      NAMED CHECK     = gross_payout / firm market value at the month-end
  net_payout_yield_xpref  ROBUSTNESS ONLY (Step 9 decision) = (dvc + prstkc - sstk) / firm
                    market value: no preferred-stock adjustment (as JKP), because the paper's
                    adjustment counts preferred converting into common (IPOs, reorganizations)
                    as a payout. Answers "did preferred conversions matter?"; never swapped
                    in for the primary because it does better.
Missing items (Step 7 decision, OSAP's rule): blank prstkc or sstk count as 0 and are
  listed in zero_filled; a blank dvc leaves both yields blank.
Firm market value = all the firm's share classes in the panel that month (CRSP permco),
  as rd_to_market. Units: payouts in $ millions, panel me in $ thousands, so
  yield = 1000 x payout / me_firm.
Non-payers keep a yield of 0. No trimming or winsorizing. Financial firms and firms
  with ceq <= 0 stay in, flagged (financial, ceq_nonpos).

Timing (Step 6): published_date = 10-K filing date (comp.co_filedate, srctype 10K),
  UTC clock time converted to New York: before 4:00 p.m. counts that day, otherwise
  (or with no time) from the next trading day. No 10-K date: datadate + 6 months as
  month-end, date_source = assumed. Very late filing dates are trusted. Values are
  Compustat's current (restated) numbers: version = restated. Same code as
  signals/rd_to_market and signals/net_operating_assets.
Choices (Step 8, same as rd_to_market): signal on the CCM-linked (primary) share class
  only, other classes blank, so a firm is never counted twice; non-USD reporters left
  blank (their payouts are not in dollars); a 10-K is usable until 18 months after its
  fiscal year-end; financial = panel CRSP siccd 6000-6999 that month.
Splits: no adjustment needed (dollar payouts over dollar market value; nothing per share).

Run from the repo root, with the .venv active (after the Step 7 pull):
    python signals\\shareholder_yield\\build_shareholder_yield.py
Everything printed is also saved to data/shareholder_yield/build_log.txt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "shareholder_yield"

PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
FUNDA = OUT / "funda_payout.parquet"
FILEDATES = DATA / "capex_intensity" / "co_filedate.parquet"
CCM = DATA / "capex_intensity" / "ccm_links.parquet"
CRSP_IDS = DATA / "issuance_insider" / "crsp_monthly.parquet"     # permco for every panel row
TDAYS_1993 = DATA / "lazy_prices" / "trading_days.parquet"
TDAYS_PRE = DATA / "rd_to_market" / "trading_days_pre1993.parquet"

FALLBACK_MONTHS = 6          # Step 6: no 10-K date -> datadate + 6 months (month-end), assumed
MAX_AGE_MONTHS = 18          # Step 8: usable until 18 months after fiscal year-end
CLOSE_ET = 16                # 4:00 p.m. New York
PREV_DAYS = (300, 430)       # previous fiscal year-end must be 10-14 months earlier
SOURCE = "comp.funda payout items (restated); comp.co_filedate 10-K date"
SIGNALS = ["net_payout_yield", "payout_yield", "net_payout_yield_xpref"]


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
# Trading calendar and the after-close rule (same as rd_to_market / NOA)
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
# 1. Payouts on the annual file
# ----------------------------------------------------------------------------
def compute_payouts(f: pd.DataFrame) -> pd.DataFrame:
    f = f.sort_values(["gvkey", "datadate"]).reset_index(drop=True)
    g = f.groupby("gvkey", sort=False)
    gap = (f["datadate"] - g["datadate"].shift(1)).dt.days
    f["pstkrv_prev"] = g["pstkrv"].shift(1).where(gap.between(*PREV_DAYS))
    chg = f["pstkrv"] - f["pstkrv_prev"]
    f["pref_down"] = (-chg).clip(lower=0).fillna(0.0)
    f["pref_up"] = chg.clip(lower=0).fillna(0.0)

    # OSAP's rule (Step 7): blank buybacks / issuance count as 0, and are recorded
    blank_p, blank_s = f["prstkc"].isna(), f["sstk"].isna()
    f["zero_filled"] = np.select([blank_p & blank_s, blank_p, blank_s], ["prstkc+sstk", "prstkc", "sstk"], default="")
    f["gross_payout"] = f["dvc"] + f["prstkc"].fillna(0.0) + f["pref_down"]     # blank dvc -> blank
    f["issuance"] = f["sstk"].fillna(0.0) - f["pref_up"]
    f["net_payout"] = f["gross_payout"] - f["issuance"]
    # robustness only: no preferred-stock adjustment (Step 9)
    f["net_payout_xpref"] = f["dvc"] + f["prstkc"].fillna(0.0) - f["sstk"].fillna(0.0)
    usd = f["curcd"] == "USD"
    f["gross_payout_usd"] = f["gross_payout"].where(usd)
    f["net_payout_usd"] = f["net_payout"].where(usd)
    f["net_payout_xpref_usd"] = f["net_payout_xpref"].where(usd)
    f["ceq_nonpos"] = (f["ceq"] <= 0).fillna(False).astype(bool)
    return f


# ----------------------------------------------------------------------------
# 2. Event file
# ----------------------------------------------------------------------------
def build_events(days: pd.DatetimeIndex, ccm: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_parquet(FUNDA)
    f["datadate"] = ns(f["datadate"])
    f["gvkey"] = f["gvkey"].astype(str)
    f = compute_payouts(f)

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

    cols = ["permno", "gvkey", "period_end", "published_date", "date_source", "source", "version",
            "timing_rule", "filedate", "filetime_et", "fyear", "fyr", "curcd",
            "dvc", "prstkc", "sstk", "pstkrv", "pstkrv_prev", "pref_down", "pref_up", "zero_filled",
            "gross_payout", "issuance", "net_payout", "net_payout_xpref",
            "gross_payout_usd", "net_payout_usd", "net_payout_xpref_usd",
            "ceq", "ceq_nonpos"]
    return e[cols].sort_values(["gvkey", "period_end"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# 3. Monthly file
# ----------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    p = pd.read_parquet(PANEL, columns=["permno", "gvkey", "date", "me", "siccd"])
    p["permno"] = p["permno"].astype("int64")
    p["date"] = ns(p["date"])
    p["me"] = pd.to_numeric(p["me"], errors="coerce").astype("float64")
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

    # firm market value: all of the firm's share classes in the panel that month
    g = p.groupby(["permco", "date"])
    p["me_firm"] = g["me"].transform("sum").where(g["me"].transform("count") > 0)
    p["n_classes"] = g["permno"].transform("size")

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
    keep = ["gvkey", "period_end", "published_date", "date_source", "source", "version", "timing_rule",
            "curcd", "dvc", "gross_payout_usd", "net_payout_usd", "net_payout_xpref_usd", "zero_filled", "ceq_nonpos"]
    linked = p[p["gvkey"].notna()].sort_values("date")
    linked = pd.merge_asof(linked, ev[keep], left_on="date", right_on="published_date",
                           by="gvkey", direction="backward")
    p = pd.concat([linked, p[p["gvkey"].isna()]], ignore_index=True)

    stale = p["period_end"].notna() & (p["date"] > p["period_end"] + pd.offsets.MonthEnd(MAX_AGE_MONTHS))
    has_event = p["period_end"].notna() & ~stale
    good = has_event & p["net_payout_usd"].notna() & (p["me_firm"] > 0)
    p["net_payout_yield"] = np.where(good, 1000.0 * p["net_payout_usd"] / p["me_firm"], np.nan)
    p["payout_yield"] = np.where(good, 1000.0 * p["gross_payout_usd"] / p["me_firm"], np.nan)
    p["net_payout_yield_xpref"] = np.where(good, 1000.0 * p["net_payout_xpref_usd"] / p["me_firm"], np.nan)

    p["status"] = np.select(
        [good,
         has_event & p["dvc"].isna(),
         has_event & (p["curcd"] != "USD"),
         has_event,
         stale,
         p["gvkey"].notna(),
         p["gvkey"].isna() & p["firm_linked"],
         p["gvkey"].isna()],
        ["ok",
         "no dividends figure (dvc blank)",
         "not in USD (left blank)",
         "no market value",
         f"latest 10-K older than {MAX_AGE_MONTHS} months",
         "no annual report public yet",
         "secondary share class",
         "no CCM link"],
        default="?")
    # stale rows keep no accounting fields
    for c in ["period_end", "published_date", "date_source", "version", "timing_rule", "curcd",
              "zero_filled", "ceq_nonpos"]:
        p[c] = p[c].mask(stale)
    p["source"] = p["source"].fillna(SOURCE)
    p["financial"] = p["siccd"].between(6000, 6999).fillna(False).astype(bool)
    p["ceq_nonpos"] = p["ceq_nonpos"].astype("boolean")

    cols = (["permno", "gvkey", "date"] + SIGNALS
            + ["zero_filled", "financial", "ceq_nonpos", "status", "period_end", "published_date",
               "date_source", "source", "version", "timing_rule", "me_firm", "n_classes", "curcd",
               "siccd", "permco", "gvkey_panel"])
    return p[cols].sort_values(["permno", "date"]).reset_index(drop=True)


def pct(s: pd.Series) -> str:
    return ", ".join(f"p{q * 100:g} {s.quantile(q):.4f}" for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99))


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
    ev.to_parquet(OUT / "payout_events.parquet", index=False)
    print(f"  saved data/shareholder_yield/payout_events.parquet ({len(ev):,} rows, {ev['gvkey'].nunique():,} firms)")
    print("  how each publish date was set:")
    print(ev["timing_rule"].value_counts().to_string())
    print(f"  published_date before period_end: {(ev['published_date'] < ev['period_end']).sum()}")
    print(f"  firm-years with net payout: {ev['net_payout'].notna().sum():,} "
          f"(in USD: {ev['net_payout_usd'].notna().sum():,}); dvc blank: {ev['dvc'].isna().sum():,}")
    print("  zero-filled items (firm-years with a net payout): "
          + ", ".join(f"{k or 'none'} {v:,}" for k, v in
                      ev.loc[ev["net_payout"].notna(), "zero_filled"].value_counts().items()))
    chk = ev.dropna(subset=["net_payout"])
    err = (chk["dvc"] + chk["prstkc"].fillna(0) + chk["pref_down"]
           - chk["sstk"].fillna(0) + chk["pref_up"] - chk["net_payout"]).abs().max()
    print(f"  net = dvc + prstkc + pref_down - sstk + pref_up: max error {err:.1e}")

    print("\n2/2 Monthly file ...")
    m = build_monthly(ev, ccm)
    m.to_parquet(OUT / "shareholder_yield_monthly.parquet", index=False)
    print(f"  saved data/shareholder_yield/shareholder_yield_monthly.parquet ({len(m):,} rows; "
          f"duplicate permno + date: {m.duplicated(['permno', 'date']).sum()})")
    print("\n  Why the yields are blank (share of all panel rows):")
    print(m["status"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    ok = m[m["status"] == "ok"]
    print(f"\n  rows with yields: {len(ok):,}; exact dates {(ok['date_source'] == 'exact').mean():.1%}; "
          f"financial firms {ok['financial'].mean():.1%}; ceq <= 0 {ok['ceq_nonpos'].mean():.1%}; "
          f"any item zero-filled {(ok['zero_filled'] != '').mean():.1%}")
    print(f"  net_payout_yield: < 0 {(ok['net_payout_yield'] < 0).mean():.1%}, = 0 {(ok['net_payout_yield'] == 0).mean():.1%}, "
          f"> 0 {(ok['net_payout_yield'] > 0).mean():.1%};  payout_yield = 0 (non-payers) {(ok['payout_yield'] == 0).mean():.1%}")
    same = np.isclose(ok["net_payout_yield"], ok["net_payout_yield_xpref"], rtol=0, atol=1e-12)
    print(f"  net_payout_yield_xpref equals the primary (no preferred change) in {same.mean():.1%} of rows with yields")
    for c in SIGNALS:
        print(f"  {c:22s} rows {m[c].notna().sum():>9,}   {pct(m[c].dropna())}")
    print("\nDone. Reply 'done' in the chat and I'll run the Step 9 checks.")


if __name__ == "__main__":
    main()
