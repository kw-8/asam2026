"""
measure_share_timing.py
=======================
Step 6 follow-up for signals/issuance_insider (net_issuance). No WRDS needed.

Question (approved rule, progress.md Step 6, 2026-11-14):
  CRSP dates each share count with a start date (StkShares.shrstartdt). How long
  after that date was the filing that reported it public? With a skip of k
  months, a count starting in month m is first used at month-end m + k. It is
  "early" if it became public after that month-end.
  Approved rule: if more than 5% of share changes are early with k = 1, the
  primary signal uses k = 2. If k = 2 also fails, the choice goes back to the
  user. All decided here, before any return is looked at.

What CRSP's share counts are (found 2026-11-14 on the real data)
  CRSP records most counts twice a quarter: the balance-sheet count, dated at
  the fiscal period end, and the cover-page count ("as of <date>, X shares
  outstanding"), dated a few days before the filing. Both come from the same
  10-Q/10-K, so both become public on its filing date. Some counts match
  neither (exchange data, prospectuses, ...).

How each share change is classified and dated
  - Only real changes: OBS share-history rows whose count differs from the row
    before (splits are handled by the adjustment factor).
  - permno -> gvkey: CRSP-Compustat link valid on the date (lazy_prices/ccm_links);
    gvkey -> CIK: every "Valid CIK-GVKEY Link" (lazy_prices/ciklink).
  - balance sheet: a 10-K/10-Q-family filing of the firm whose period end
    (rdate) is within 3 days of the count's date -> public when that filing was.
  - cover page: otherwise, the first filing filed on or after the date (within
    45 days) whose period ended before the date -> public when that filing was.
  - other: neither. Lower bound: treated as public on its date (never early).
    Upper bound: treated as public with the next 10-K/10-Q filed within 150 days.
  - Public date (team rule, as in lazy_prices): SEC acceptance date if accepted
    by 4:00 p.m. New York time; otherwise, with no time, or if the acceptance
    date is unusable (after the EDGAR filing date or > 4 days before it), the
    next trading day.

Sample: statistics use changes dated 2003-01-01 to 2025-08-31 (filings in the pull run
2002-2025, so later changes may not have their filing yet). Matching is also done, and
saved, for changes up to 2025-12-31; unmatched ones fall back to an assumed lag in Step 8.

Writes data/issuance_insider/timing_log.txt (everything printed) and
data/issuance_insider/share_changes_matched.parquet (one row per change).

Run from the repo root, with the .venv active (under a minute):
    python signals\\issuance_insider\\measure_share_timing.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "issuance_insider"
LP = REPO / "data" / "lazy_prices"
LOG = D / "timing_log.txt"

FIRST, LAST = "2003-01-01", "2025-08-31"   # statistics window (filings in the pull end 2025-12-31)
MATCH_END = "2025-12-31"                    # changes matched (and saved) through here, for Step 8
BS_DAYS, COVER_DAYS, NEXT_DAYS = 3, 45, 150
SKIPS = (1, 2, 3, 4, 6)
THRESHOLD = 0.05

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def show(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=False).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x:.1%}"


def trading_day_on_or_after(dates: pd.Series, days: np.ndarray, strictly_after: pd.Series) -> pd.Series:
    v = dates.values.astype("datetime64[D]")
    idx = np.where(strictly_after.values,
                   np.searchsorted(days, v, side="right"),
                   np.searchsorted(days, v, side="left"))
    ok = (~np.isnat(v)) & (idx < len(days))
    out = np.full(len(v), np.datetime64("NaT", "D"))
    out[ok] = days[idx[ok]]
    return pd.Series(out.astype("datetime64[ns]"), index=dates.index)


def public_dates(f: pd.DataFrame, days: np.ndarray) -> pd.Series:
    """Accepted by 16:00 New York time -> that trading day; otherwise the next trading day."""
    t = f["secatime"].astype("string").str.slice(0, 8)
    has_time = t.str.len().fillna(0).ge(5)
    usable = (f["secadate"].notna() & (f["secadate"] <= f["fdate"])
              & (f["secadate"] >= f["fdate"] - pd.Timedelta(days=4)))
    use_acc = usable & has_time
    base = f["secadate"].where(use_acc, f["fdate"])
    same_day = use_acc & (t <= "16:00:00").fillna(False)
    return trading_day_on_or_after(base, days, ~same_day)


def asof(left: pd.DataFrame, right: pd.DataFrame, on_right: str, direction: str, days: int) -> pd.DataFrame:
    """merge_asof by cik, returned in the row order of `left` (index preserved)."""
    r = right.sort_values(on_right)
    out = pd.merge_asof(left.rename_axis("row").reset_index().sort_values("shrstartdt"), r, left_on="shrstartdt",
                        right_on=on_right, by="cik", direction=direction, tolerance=pd.Timedelta(days=days))
    return out.set_index("row").reindex(left.index)


def main() -> None:
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            run()
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


def run() -> None:
    print(f"net_issuance timing measurement, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    sh = pd.read_parquet(D / "share_history.parquet")
    fil = pd.read_parquet(D / "filings_10kq.parquet")
    ccm = pd.read_parquet(LP / "ccm_links.parquet")
    cik = pd.read_parquet(LP / "ciklink.parquet")
    days = np.sort(pd.to_datetime(pd.read_parquet(LP / "trading_days.parquet")["date"]).values
                   .astype("datetime64[D]"))
    print(f"  share history {len(sh):,} rows; filings {len(fil):,}; trading days to {days[-1]}")

    # ---- 1. Real share changes ------------------------------------------------------
    section("1. Share changes")
    sh = sh.sort_values(["permno", "shrstartdt"]).reset_index(drop=True)
    sh["prev"] = sh.groupby("permno")["shrout"].shift()
    ch = sh[(sh["shrsource"] == "OBS") & sh["prev"].notna() & (sh["shrout"] != sh["prev"])
            & (sh["shrout"] > 0) & (sh["prev"] > 0) & sh["shrstartdt"].between(FIRST, MATCH_END)].copy()
    ch["dlog"] = np.log(ch["shrout"] / ch["prev"]).abs()
    ch["month"] = ch["shrstartdt"] + MonthEnd(0)
    print(f"  OBS rows that change the count, {FIRST[:4]} to {MATCH_END[:7]}: {len(ch):,} ({ch['permno'].nunique():,} permnos); "
          f"statistics below use those to {LAST[:7]}: {(ch['shrstartdt'] <= LAST).sum():,}")

    # ---- 2. Link to the filer (CIK) ---------------------------------------------------
    section("2. Link each change to the filer")
    ccm = ccm.assign(linkenddt=ccm["linkenddt"].fillna(pd.Timestamp("2099-12-31")))
    x = ch[["permno", "shrstartdt"]].rename_axis("cid").reset_index().merge(ccm[["permno", "gvkey", "linkdt", "linkenddt"]], on="permno")
    x = x[(x["shrstartdt"] >= x["linkdt"]) & (x["shrstartdt"] <= x["linkenddt"])].drop_duplicates(["cid", "gvkey"])
    n_gvkey = x["cid"].nunique()
    valid = cik[cik["link_desc"].astype(str).str.startswith("Valid")][["gvkey", "cik"]].drop_duplicates()
    x = x.merge(valid, on="gvkey").drop_duplicates(["cid", "cik"])
    print(f"  changes with a gvkey (CCM link valid on the date): {n_gvkey / len(ch):.1%}; "
          f"with a CIK: {x['cid'].nunique() / len(ch):.1%}")

    fil = fil.dropna(subset=["fdate"]).copy()
    fil["public"] = public_dates(fil, days)
    fil["kind10"] = np.where(fil["form"].astype(str).str.contains("K"), "10-K", "10-Q")
    f = fil[["cik", "form", "kind10", "fdate", "rdate", "public"]]

    # One candidate row per (change, CIK); keep, per change, the best match over its CIKs.
    xi = x.set_index(pd.RangeIndex(len(x)))
    a = asof(xi, f.dropna(subset=["rdate"]).rename(columns=lambda c: f"a_{c}" if c != "cik" else c),
             "a_rdate", "nearest", BS_DAYS)
    b = asof(xi, f.rename(columns=lambda c: f"b_{c}" if c != "cik" else c), "b_fdate", "forward", COVER_DAYS)
    n = asof(xi, f.rename(columns=lambda c: f"n_{c}" if c != "cik" else c), "n_fdate", "forward", NEXT_DAYS)
    cand = pd.concat([xi[["cid", "shrstartdt"]], a, b, n], axis=1)
    cand = cand.loc[:, ~cand.columns.duplicated()]
    cand["is_bs"] = cand["a_fdate"].notna()
    cand["is_cover"] = ~cand["is_bs"] & cand["b_fdate"].notna() & (cand["b_rdate"] < cand["shrstartdt"])
    cand["rank"] = np.select([cand["is_bs"], cand["is_cover"]], [0, 1], 2)
    cand = cand.sort_values(["cid", "rank", "a_public", "b_public"]).drop_duplicates("cid").set_index("cid")

    ch = ch.join(cand[["is_bs", "is_cover", "a_public", "a_kind10", "b_public", "b_kind10", "n_public"]])
    ch["source"] = np.select([ch["is_bs"].fillna(False).astype(bool), ch["is_cover"].fillna(False).astype(bool)],
                             ["balance sheet", "cover page"], "other")
    ch["public"] = ch["a_public"].where(ch["source"] == "balance sheet", ch["b_public"].where(ch["source"] == "cover page"))
    ch["form10"] = ch["a_kind10"].where(ch["source"] == "balance sheet", ch["b_kind10"].where(ch["source"] == "cover page"))
    ch["public_upper"] = ch["public"].fillna(ch["n_public"])        # other -> next 10-K/10-Q (cautious)
    ch["public_lower"] = ch["public"].fillna(ch["shrstartdt"])      # other -> public on its date

    full = ch
    ch = ch[ch["shrstartdt"] <= LAST].copy()       # statistics window
    tab = ch["source"].value_counts().rename_axis("source").reset_index(name="changes")
    tab["share"] = (tab["changes"] / len(ch)).map("{:.1%}".format)
    print("\n  Where each change comes from:")
    show(tab)
    lag = (ch["public"] - ch["shrstartdt"]).dt.days
    q = lag.groupby(ch["source"]).describe(percentiles=[.1, .5, .9]).round(0).drop(columns=["mean", "std"])
    print("\n  Days from CRSP's date to the filing being public:")
    show(q.reset_index())
    print(f"  'other' changes with a 10-K/10-Q filed within {NEXT_DAYS} days (used for the upper bound): "
          f"{ch.loc[ch['source'] == 'other', 'n_public'].notna().mean():.1%}")

    # ---- 3. Early share for each skip ----------------------------------------------
    section("3. Share of changes used before they were public, by skip (k months)")
    rows = []
    bs = ch["source"] == "balance sheet"
    for k in SKIPS:
        used = ch["month"] + MonthEnd(k)
        e_low = ch["public_lower"] > used
        e_up = ch["public_upper"] > used
        ch[f"early_low_k{k}"], ch[f"early_up_k{k}"] = e_low, e_up
        rows.append({"skip k": k,
                     "balance sheet": pct(e_low[bs].mean()),
                     "  of which 10-K": pct(e_low[bs & (ch["form10"] == "10-K")].mean()),
                     "  of which 10-Q": pct(e_low[bs & (ch["form10"] == "10-Q")].mean()),
                     "cover page": pct(e_low[ch["source"] == "cover page"].mean()),
                     "ALL, lower bound": pct(e_low.mean()),
                     "ALL, upper bound": pct(e_up.mean()),
                     "ALL, upper, size-weighted": pct(np.average(e_up, weights=ch["dlog"]))})
    show(pd.DataFrame(rows))
    yr = ch.groupby(ch["shrstartdt"].dt.year)[["early_low_k2", "early_up_k2", "early_low_k3", "early_up_k3"]].mean()
    print("\n  By year (share early; low / up = lower / upper bound):")
    show(yr.map(pct).reset_index().rename(columns={"shrstartdt": "year"}))

    # ---- 4. Decision ----------------------------------------------------------------------
    section("4. Decision")
    ok = [k for k in SKIPS if ch[f"early_up_k{k}"].mean() <= THRESHOLD and ch[f"early_low_k{k}"].mean() <= THRESHOLD]
    best = ok[0] if ok else None
    for k in (1, 2):
        print(f"  k = {k}: early {ch[f'early_low_k{k}'].mean():.1%} (lower) to {ch[f'early_up_k{k}'].mean():.1%} (upper)"
              f" -> {'within' if k in ok else 'above'} 5%")
    if 1 in ok:
        print("  RESULT: k = 1 (approved rule)")
    elif 2 in ok:
        print("  RESULT: k = 2 (approved rule)")
    else:
        print(f"  Approved rule (k = 2 if k = 1 fails) does not cover this: k = 2 also fails.")
        print(f"  Smallest skip within 5% under both bounds: k = {best}.")
    print("  User decision (2026-11-14, progress.md): primary k = 4; k = 3 and exact dates built as named checks.")

    keep = ["permno", "shrstartdt", "shrout", "prev", "dlog", "source", "form10", "public",
            "public_lower", "public_upper"]
    full[keep].reset_index(drop=True).to_parquet(D / "share_changes_matched.parquet", index=False)
    print(f"\n  saved data/issuance_insider/share_changes_matched.parquet ({len(full):,} rows, to {MATCH_END[:7]})")


if __name__ == "__main__":
    main()
