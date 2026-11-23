"""
build_rd_to_market.py
=====================
Step 8 (Construct) of prompts/data_acquisition.md for signals/rd_to_market.

Builds two files from data already on disk (no WRDS login needed):

  data/rd_to_market/rd_events.parquet
      One row per firm (gvkey) x fiscal year-end: the R&D figure and the date it
      became public.
  data/rd_to_market/rd_to_market_monthly.parquet
      Every row of the panel (permno x month-end) with the signal and, when it
      is blank, the reason.

Definitions agreed in Steps 1-8 (see progress.md):
  rdm      = R&D (latest annual xrd whose 10-K was public by the month-end)
             / the firm's market value at that month-end (all its share
             classes in the panel, by CRSP permco)        [Definition A]
           = 1000 x xrd ($ millions) / me_firm ($ thousands)
  has_rd   = 1 if that xrd > 0; 0 if it is 0 or missing (rdm blank).
  rdm_hxz  = Hou-Xue-Zhang "Rdm" check [Definition B]: xrd for the fiscal year
             ending in calendar y-1 / firm market value at December y-1, held
             fixed from July y to June y+1. Positive R&D only.
Timing (Step 6): published_date = 10-K filing date (comp.co_filedate, srctype
  10K). The time of day is stored in UTC; converted to New York time, a filing
  before 4:00 p.m. counts that day, otherwise (or with no time) from the next
  trading day. No 10-K date: datadate + 6 months as month-end, date_source =
  assumed. Very late filing dates are trusted. Values are Compustat's current
  (restated) numbers: version = restated.
Choices (Step 8): the signal sits on the CCM-linked (primary) share class only,
  other classes are blank; Canadian-dollar R&D is left blank; an R&D figure is
  usable until 18 months after its fiscal year-end.
Splits: no adjustment needed. R&D is in dollars and market value (price x
  shares) does not change at a split. Step 9 shows one split.

Run from the repo root, with the .venv active (after pull_compustat_rd.py):
    python signals\\rd_to_market\\build_rd_to_market.py
Everything printed is also saved to data/rd_to_market/build_log.txt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "rd_to_market"

PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
FUNDA = OUT / "funda_rd.parquet"
FILEDATES = DATA / "capex_intensity" / "co_filedate.parquet"
CCM = DATA / "capex_intensity" / "ccm_links.parquet"
CRSP_IDS = DATA / "issuance_insider" / "crsp_monthly.parquet"     # permco for every panel row
TDAYS_1993 = DATA / "lazy_prices" / "trading_days.parquet"
TDAYS_PRE = OUT / "trading_days_pre1993.parquet"

FALLBACK_MONTHS = 6          # Step 6: no 10-K date -> datadate + 6 months (month-end), assumed
MAX_AGE_MONTHS = 18          # Step 8: usable until 18 months after fiscal year-end
CLOSE_ET = 16                # 4:00 p.m. New York
SOURCE = "comp.funda xrd (restated); comp.co_filedate 10-K date; CRSP market value"


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
# Trading calendar and the after-close rule
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
# 1. Event file
# ----------------------------------------------------------------------------
def build_events(days: pd.DatetimeIndex, ccm: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_parquet(FUNDA)
    f["datadate"] = ns(f["datadate"])
    f["gvkey"] = f["gvkey"].astype(str)

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

    e["xrd_usd"] = e["xrd"].where(e["curcd"] == "USD")
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
            "xrd", "xrd_usd", "curcd", "fyear", "fyr", "sale", "filedate", "filetime_et", "timing_rule"]
    return e[cols].sort_values(["gvkey", "period_end"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# 2. Monthly file
# ----------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    p = pd.read_parquet(PANEL, columns=["permno", "gvkey", "date", "me"])
    p["permno"] = p["permno"].astype("int64")
    p["date"] = ns(p["date"])
    p["me"] = pd.to_numeric(p["me"], errors="coerce").astype("float64")
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
    firm_linked = p["gvkey"].notna().groupby([p["permco"], p["date"]]).transform("any")
    p["firm_linked"] = firm_linked

    # latest event public by the month-end; an event that is older than one already
    # public (a late refiling of an earlier year) never replaces the newer one
    ev = events.sort_values(["gvkey", "published_date", "period_end"]).copy()
    ev["newest_so_far"] = ev.groupby("gvkey")["period_end"].cummax()
    ev = ev[ev["period_end"] >= ev["newest_so_far"]]
    ev = ev.sort_values("published_date")
    keep = ["gvkey", "period_end", "published_date", "date_source", "source", "version",
            "xrd", "xrd_usd", "curcd", "timing_rule"]
    linked = p[p["gvkey"].notna()].sort_values("date")
    linked = pd.merge_asof(linked, ev[keep], left_on="date", right_on="published_date",
                           by="gvkey", direction="backward")
    p = pd.concat([linked, p[p["gvkey"].isna()]], ignore_index=True)

    stale = p["period_end"].notna() & (p["date"] > p["period_end"] + pd.offsets.MonthEnd(MAX_AGE_MONTHS))
    has_event = p["period_end"].notna() & ~stale
    p["has_rd"] = pd.Series(pd.NA, index=p.index, dtype="Int64")
    p.loc[has_event, "has_rd"] = (p.loc[has_event, "xrd"] > 0).astype("int64")
    good = has_event & (p["xrd"] > 0) & p["xrd_usd"].notna() & (p["me_firm"] > 0)
    p["rdm"] = np.where(good, 1000.0 * p["xrd_usd"] / p["me_firm"], np.nan)

    p["status"] = np.select(
        [good,
         has_event & (p["xrd"] > 0) & p["xrd_usd"].isna(),
         has_event & (p["xrd"] > 0),
         has_event,
         stale,
         p["gvkey"].notna(),
         p["gvkey"].isna() & p["firm_linked"],
         p["gvkey"].isna()],
        ["ok",
         "R&D not in USD (left blank)",
         "no market value",
         "no R&D reported (has_rd = 0)",
         f"latest 10-K older than {MAX_AGE_MONTHS} months",
         "no annual report public yet",
         "secondary share class",
         "no CCM link"],
        default="?")
    # stale rows keep no accounting fields
    for c in ["period_end", "published_date", "date_source", "version", "xrd", "xrd_usd",
              "curcd", "timing_rule"]:
        p[c] = p[c].mask(stale)
    p["source"] = p["source"].fillna(SOURCE)

    # Definition B (Hou-Xue-Zhang Rdm): fixed each June, check only
    p["hxz_year"] = np.where(p["date"].dt.month >= 7, p["date"].dt.year, p["date"].dt.year - 1)
    ann = events[events["xrd_usd"] > 0].copy()
    ann["cal_year"] = ann["period_end"].dt.year
    ann = ann.sort_values("period_end").drop_duplicates(["gvkey", "cal_year"], keep="last")
    dec = p[(p["date"].dt.month == 12) & p["gvkey"].notna()][["gvkey", "date", "me_firm"]].copy()
    dec["cal_year"] = dec["date"].dt.year
    b = ann[["gvkey", "cal_year", "xrd_usd"]].merge(dec[["gvkey", "cal_year", "me_firm"]], on=["gvkey", "cal_year"])
    b["rdm_hxz"] = 1000.0 * b["xrd_usd"] / b["me_firm"]
    b["hxz_year"] = b["cal_year"] + 1
    p = p.merge(b[["gvkey", "hxz_year", "rdm_hxz"]], on=["gvkey", "hxz_year"], how="left")

    cols = ["permno", "gvkey", "date", "rdm", "has_rd", "status", "period_end", "published_date",
            "date_source", "source", "version", "xrd", "xrd_usd", "curcd", "me", "me_firm", "permco",
            "n_classes", "gvkey_panel", "timing_rule", "rdm_hxz"]
    return p[cols].sort_values(["permno", "date"]).reset_index(drop=True)


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
    ev.to_parquet(OUT / "rd_events.parquet", index=False)
    print(f"  saved data/rd_to_market/rd_events.parquet ({len(ev):,} rows, {ev['gvkey'].nunique():,} firms)")
    print("  how each publish date was set:")
    print(ev["timing_rule"].value_counts().to_string())
    print(f"  published_date before period_end: {(ev['published_date'] < ev['period_end']).sum()}")

    print("\n2/2 Monthly file ...")
    m = build_monthly(ev, ccm)
    m.to_parquet(OUT / "rd_to_market_monthly.parquet", index=False)
    print(f"  saved data/rd_to_market/rd_to_market_monthly.parquet ({len(m):,} rows)")
    print("\n  Why rows are blank (share of all panel rows):")
    print(m["status"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    ok = m[m["status"] == "ok"]
    print(f"\n  rows with a signal: {len(ok):,}; exact dates {(ok['date_source'] == 'exact').mean():.1%}")
    print(f"  rdm percentiles (R&D / market value): "
          + ", ".join(f"p{int(q*100)} {ok['rdm'].quantile(q):.3f}" for q in (0.01, 0.25, 0.5, 0.75, 0.99)))
    print(f"  rows with the Hou-Xue-Zhang check value (rdm_hxz): {m['rdm_hxz'].notna().sum():,}")
    print("\nDone. Reply 'done' in the chat and I'll run the Step 9 checks.")


if __name__ == "__main__":
    main()
