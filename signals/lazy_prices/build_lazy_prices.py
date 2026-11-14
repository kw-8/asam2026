"""
build_lazy_prices.py
====================
Step 8 (Construct) of prompts/data_acquisition.md for signals/lazy_prices.
Reads only files already in data/ (no WRDS, no password).

Inputs
  data/lazy_prices/bow_cossim_10k.parquet   pull_bow_cossim.py (version 2)
  data/lazy_prices/ciklink.parquet          pull_bow_cossim.py
  data/lazy_prices/ccm_links.parquet        pull_bow_cossim.py
  data/lazy_prices/trading_days.parquet     pull_bow_cossim.py
  data/lazy_prices/security_info.parquet    pull_security_info.py
  data/crsp_monthly_ratios_clean.parquet    the team panel

Rules (progress.md, Step 8, approved 2026-11-13)
  1. Filings: every original 10-K-family filing, compared with its most recent
     ORIGINAL 10-K among lookback 1-4, only if that one was filed 9-15 months
     earlier (months = days / 30.44, rounded); otherwise no value.
  2. Signal: filing_sim = that similarity (low = "changer"). Not ranked or
     winsorized here. Which measure (rule 10, approved 2026-11-14):
       `cosine_eng` (English words only) if, in each of 2010, 2011 and 2012,
       at most 30% of that year's bottom fifth are the largest fifth of firms;
       otherwise `cosine`, with values from filings published in 2010-2014
       flagged (2014 added 2026-11-14 after Step 9). Override: --measure.
  3. published_date: first trading day on or after the SEC acceptance date if
     accepted at or before 4:00 p.m. New York time; otherwise, or with no time
     (before 2003), the first trading day after it. If WRDS's acceptance date is
     after the EDGAR filing date or more than 4 days before it (a later
     re-processing date, mostly 1994-2002 filings), the EDGAR filing date is used
     with no time (added in Step 9, 2026-11-14). period_end = rdate.
     date_source = exact, version = original, source = wrdssec.bow_cossim.
  4. CIK -> gvkey: "Valid CIK-GVKEY Link" rows only. If the CIK has one gvkey,
     use it. If it has several, use the links whose dates contain the filing
     date, preferring CRSP/Compustat Merged, Compustat Security, Compustat
     Company, Capital IQ; if still more than one gvkey, drop the filing.
  5. gvkey -> permno: CCM (LU/LC, P/C), link window containing published_date;
     prefer linkprim P over C; if still more than one permno, drop.
  6. Event file: permno, gvkey, period_end, published_date, date_source,
     source, version + inputs.
  7. Monthly file on the panel's (permno, month-end) rows: latest event with
     published_date <= month-end and at most 15 months old (by calendar month).
     applies = "stock" or "n/a (ETF)".
  8. ETFs from CRSP securitysubtype = 'ETF' over the security's date ranges.
  9. Splits: nothing to adjust; filing_sim is computed from text only.

Outputs (data/lazy_prices/, which Git ignores)
  lazy_prices_events.parquet, lazy_prices_monthly.parquet, build_log.txt

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\build_lazy_prices.py
    python signals\\lazy_prices\\build_lazy_prices.py --measure cosine   (override the rule)
Takes about 1-3 minutes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
LP = DATA / "lazy_prices"
LOG = LP / "build_log.txt"

MIN_MONTHS, MAX_MONTHS = 9, 15          # rule 1
CLOSE = "16:00:00"                      # rule 3 (New York time)
MAX_AGE_MONTHS = 15                     # rule 7
MAX_ACCEPT_GAP = 4                      # rule 3: acceptance at most 4 days before the EDGAR filing date
MEASURES = ("cosine", "cosine_eng")     # rule 10
TILT_YEARS = (2010, 2011, 2012)         # rule 10: years checked
TILT_MAX = 0.30                         # rule 10: largest-fifth share of the bottom fifth allowed
FLAG_YEARS = (2010, 2014)               # rule 10: flagged if cosine is kept (2014 added in Step 9)
FLAG_COL = f"format_change_{FLAG_YEARS[0]}_{str(FLAG_YEARS[1])[2:]}"   # format_change_2010_14
SOURCE = "wrdssec.bow_cossim"
LINK_PRIORITY = ["CRSP/Compustat Merged", "Compustat Security", "Compustat Company", "Capital IQ"]
NS = "datetime64[ns]"

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


class Tee:
    """Print to the terminal and to the log file at the same time."""

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


def need(path: Path, made_by: str) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(REPO)}. Run {made_by} first.")
    return path


def gvkey_text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.zfill(6)


# ----------------------------------------------------------------------------
# Rule 1-2: which filings, compared with what
# ----------------------------------------------------------------------------
def pick_comparisons(raw: pd.DataFrame, funnel: list) -> pd.DataFrame:
    n_all = raw[["cik", "accession"]].drop_duplicates().shape[0]
    funnel.append(("10-K-family filings pulled", n_all))
    original = raw["form_prev"].notna() & ~raw["form_prev"].str.contains("/A", regex=False, na=False)
    c = (raw[original].sort_values(["cik", "accession", "lookback"])
                      .drop_duplicates(["cik", "accession"], keep="first").copy())
    funnel.append(("... with an original 10-K among lookback 1-4", len(c)))
    c["months_apart"] = ((c["fdate"] - c["fdate_prev"]).dt.days / 30.44).round()
    c = c[c["months_apart"].between(MIN_MONTHS, MAX_MONTHS)].copy()
    funnel.append((f"... filed {MIN_MONTHS}-{MAX_MONTHS} months earlier (kept)", len(c)))
    return c.rename(columns={"accession2": "accession_prev",
                             "lookback": "lookback_used", "rdate": "period_end"})


# ----------------------------------------------------------------------------
# Rule 3: published_date
# ----------------------------------------------------------------------------
def add_published_date(c: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    td = np.sort(days["date"].astype(NS).to_numpy())
    # The SEC acceptance date can only be on or up to a few days before the EDGAR filing
    # date. WRDS has a later (re-processing) date for many 1994-2002 filings: then the
    # acceptance date and time are not trusted and the filing date is used with no time.
    gap = (c["fdate"] - c["secadate"]).dt.days
    trusted = (c["secadate"].notna() & gap.between(0, MAX_ACCEPT_GAP)).to_numpy(dtype=bool)
    accepted = np.where(trusted, c["secadate"].astype(NS).to_numpy(), c["fdate"].astype(NS).to_numpy())
    t = c["secatime"].astype("string")
    has_time = t.str.match(r"^\d{2}:\d{2}").fillna(False).to_numpy(dtype=bool) & trusted
    by_close = has_time & (t.str[:8] <= CLOSE).fillna(False).to_numpy(dtype=bool)
    i_on_or_after = np.searchsorted(td, accepted, side="left")
    i_after = np.searchsorted(td, accepted, side="right")
    i = np.where(by_close, i_on_or_after, i_after)
    ok = i < len(td)
    pub = np.full(len(c), np.datetime64("NaT", "ns"), dtype=NS)
    pub[ok] = td[i[ok]]
    return c.assign(published_date=pub, has_time=has_time, by_close=by_close, accept_trusted=trusted)


# ----------------------------------------------------------------------------
# Rule 4: CIK -> gvkey
# ----------------------------------------------------------------------------
def link_gvkey(c: pd.DataFrame, ciklink: pd.DataFrame, funnel: list) -> pd.DataFrame:
    lk = ciklink[ciklink["link_desc"].astype("string").str.startswith("Valid", na=False)].copy()
    lk["gvkey"] = gvkey_text(lk["gvkey"])
    lk = lk[["cik", "gvkey", "source", "link_start_date", "link_end_date"]].drop_duplicates()
    n_gv = lk.groupby("cik")["gvkey"].nunique()

    one = lk[lk["cik"].isin(n_gv[n_gv == 1].index)].drop_duplicates("cik")[["cik", "gvkey"]]
    a = c.merge(one, on="cik", how="inner").assign(gvkey_rule="only gvkey for this CIK")

    multi = c[c["cik"].isin(n_gv[n_gv > 1].index)]
    m = multi[["cik", "accession", "fdate"]].merge(lk, on="cik", how="inner")
    inside = (m["link_start_date"].notna() & m["link_end_date"].notna()
              & (m["link_start_date"] <= m["fdate"]) & (m["fdate"] <= m["link_end_date"]))
    m = m[inside].copy()
    m["prio"] = m["source"].map({s: k for k, s in enumerate(LINK_PRIORITY)}).fillna(len(LINK_PRIORITY))
    m = m[m["prio"] == m.groupby(["cik", "accession"])["prio"].transform("min")]
    n_cand = m.groupby(["cik", "accession"])["gvkey"].nunique()
    ok = n_cand[n_cand == 1].index
    picked = (m.set_index(["cik", "accession"]).loc[ok].reset_index()
                .drop_duplicates(["cik", "accession"])[["cik", "accession", "gvkey"]])
    b = multi.merge(picked, on=["cik", "accession"], how="inner").assign(gvkey_rule="dated link, by source")

    no_valid = (~c["cik"].isin(lk["cik"])).sum()
    ambiguous = (n_cand > 1).sum()
    no_date = len(multi) - len(b) - ambiguous
    funnel.append(("    dropped: no 'Valid CIK-GVKEY Link'", -int(no_valid)))
    funnel.append(("    dropped: several gvkeys, none of their links dated around the filing", -int(no_date)))
    funnel.append(("    dropped: several gvkeys still possible", -int(ambiguous)))
    out = pd.concat([a, b], ignore_index=True)
    funnel.append(("... linked to a gvkey", len(out)))
    return out


# ----------------------------------------------------------------------------
# Rule 5: gvkey -> permno
# ----------------------------------------------------------------------------
def link_permno(c: pd.DataFrame, ccm: pd.DataFrame, funnel: list) -> pd.DataFrame:
    cc = ccm.copy()
    cc["gvkey"] = gvkey_text(cc["gvkey"])
    cc["linkenddt"] = cc["linkenddt"].fillna(pd.Timestamp.today().normalize())
    x = c.merge(cc[["gvkey", "permno", "linkprim", "linkdt", "linkenddt"]], on="gvkey", how="inner")
    x = x[(x["linkdt"] <= x["published_date"]) & (x["published_date"] <= x["linkenddt"])].copy()
    x["prim_rank"] = x["linkprim"].map({"P": 0, "C": 1}).fillna(2)
    x = x[x["prim_rank"] == x.groupby(["cik", "accession"])["prim_rank"].transform("min")]
    n_p = x.groupby(["cik", "accession"])["permno"].nunique()
    x = x[x.set_index(["cik", "accession"]).index.isin(n_p[n_p == 1].index)]
    x = x.drop_duplicates(["cik", "accession"])
    lost = c[~c.set_index(["cik", "accession"]).index.isin(n_p.index)]
    never = (~lost["gvkey"].isin(set(cc["gvkey"]))).sum()
    funnel.append(("    dropped: gvkey has no CCM link at all (not a CRSP stock)", -int(never)))
    funnel.append(("    dropped: CCM link exists, but not on the published date", -int(len(lost) - never)))
    funnel.append(("    dropped: several permnos still possible", -int((n_p > 1).sum())))
    funnel.append(("... linked to a permno", len(x)))
    return x.drop(columns=["prim_rank", "linkprim", "linkdt", "linkenddt"])


# ----------------------------------------------------------------------------
# Rule 6: event file
# ----------------------------------------------------------------------------
def make_events(x: pd.DataFrame, funnel: list) -> pd.DataFrame:
    no_day = x["published_date"].isna()
    if no_day.any():
        funnel.append(("    dropped: no trading day on file after the acceptance date", -int(no_day.sum())))
        x = x[~no_day]
    bad_pe = x["period_end"].notna() & (x["period_end"] > x["published_date"])
    if bad_pe.any():
        x = x.copy()
        x.loc[bad_pe, "period_end"] = pd.NaT
        funnel.append((f"    note: period_end (rdate) after the filing in {int(bad_pe.sum())} rows -> set to missing", None))
    x = x.sort_values(["permno", "published_date", "fdate", "accession"])
    dup = x.duplicated(["permno", "published_date"], keep="last")
    funnel.append(("    dropped: 2nd filing, same permno and published date (kept the later)", -int(dup.sum())))
    x = x[~dup]
    ev = pd.DataFrame({
        "permno": x["permno"].astype("int64"),
        "gvkey": x["gvkey"].astype("string"),
        "period_end": x["period_end"].astype(NS),
        "published_date": x["published_date"].astype(NS),
        "date_source": "exact",
        "source": SOURCE,
        "version": "original",
        # inputs
        "cik": x["cik"].astype("string"),
        "accession": x["accession"].astype("string"),
        "form": x["form"].astype("string"),
        "filing_sim": x["cosine"].astype("float64"),      # replaced by the chosen measure
        "cosine": x["cosine"].astype("float64"),
        "cosine_eng": (x["cosine_eng"] if "cosine_eng" in x else pd.Series(np.nan, index=x.index)).astype("float64"),
        "engwcnt": (x["engwcnt"] if "engwcnt" in x else pd.Series(np.nan, index=x.index)).astype("float64"),
        "accession_prev": x["accession_prev"].astype("string"),
        "form_prev": x["form_prev"].astype("string"),
        "fdate_prev": x["fdate_prev"].astype(NS),
        "months_apart": x["months_apart"].astype("int64"),
        "lookback_used": x["lookback_used"].astype("int64"),
        "fdate": x["fdate"].astype(NS),
        "secadate": x["secadate"].astype(NS),
        "secatime": x["secatime"].astype("string"),
        "published_basis": pd.Series(np.select(
            [x["by_close"].to_numpy(dtype=bool), x["has_time"].to_numpy(dtype=bool),
             x["accept_trusted"].to_numpy(dtype=bool)],
            ["acceptance at/before 4 p.m.: same day", "acceptance after 4 p.m.: next trading day",
             "acceptance date, no time: next trading day"],
            "EDGAR filing date (acceptance date not usable): next trading day"), index=x.index).astype("string"),
        "wcnt": x["wcnt"].astype("float64"),
        "gvkey_rule": x["gvkey_rule"].astype("string"),
    }).reset_index(drop=True)
    funnel.append(("Events saved", len(ev)))
    return ev


# ----------------------------------------------------------------------------
# Rule 7-8: monthly file on the panel grid, ETFs marked n/a
# ----------------------------------------------------------------------------
def etf_rows(panel: pd.DataFrame, info: pd.DataFrame) -> np.ndarray:
    """True for panel rows whose permno is an ETF in that month."""
    e = info.loc[info["securitysubtype"].astype("string") == "ETF",
                 ["permno", "secinfostartdt", "secinfoenddt"]].copy()
    e["permno"] = e["permno"].astype("int64")
    e["m0"] = e["secinfostartdt"].dt.to_period("M")
    e["m1"] = e["secinfoenddt"].fillna(pd.Timestamp("2099-12-31")).dt.to_period("M")
    p = panel.loc[panel["permno"].isin(set(e["permno"])), ["permno", "date"]].reset_index()
    p["m"] = p["date"].dt.to_period("M")
    j = p.merge(e[["permno", "m0", "m1"]], on="permno")
    hit = j.loc[(j["m0"] <= j["m"]) & (j["m"] <= j["m1"]), "index"].unique()
    flag = np.zeros(len(panel), dtype=bool)
    flag[panel.index.get_indexer(hit)] = True
    return flag


def size_tilt(ev: pd.DataFrame, panel: pd.DataFrame, col: str) -> pd.Series:
    """By published year: share of the bottom fifth (lowest `col`) that are the largest
    fifth of firms by market value at the month-end before publication (20% = no tilt)."""
    e = ev[["permno", "published_date", col]].dropna().copy()
    e["date"] = (e["published_date"] - pd.offsets.MonthEnd(1)).astype(NS)
    e = e.merge(panel[["permno", "date", "me"]], on=["permno", "date"], how="inner").dropna(subset=["me"])
    e["year"] = e["published_date"].dt.year
    e["largest"] = e.groupby("year")["me"].rank(pct=True) > 0.8
    e["bottom"] = e.groupby("year")[col].rank(pct=True, method="first") <= 0.2
    return e[e["bottom"]].groupby("year")["largest"].mean()


def choose_measure(ev: pd.DataFrame, panel: pd.DataFrame, requested: str):
    """Rule 10. Returns (measure, reason, tilt table)."""
    have = [m for m in MEASURES if ev[m].notna().any()]
    tilts = pd.DataFrame({m: size_tilt(ev, panel, m) for m in have})
    if requested != "auto":
        if requested not in have:
            raise SystemExit(f"--measure {requested}: that column is empty. Run pull_bow_cossim.py (version 3).")
        return requested, f"set by --measure {requested}", tilts
    if "cosine_eng" not in have:
        return "cosine", ("cosine_eng is not in bow_cossim_10k.parquet (run pull_bow_cossim.py version 3); "
                          f"kept cosine and flagged {FLAG_YEARS[0]}-{FLAG_YEARS[1]}"), tilts
    t = tilts["cosine_eng"].reindex(TILT_YEARS)
    if t.notna().all() and (t <= TILT_MAX).all():
        return "cosine_eng", (f"cosine_eng: largest-fifth share of the bottom fifth is at most {TILT_MAX:.0%} "
                              f"in each of {TILT_YEARS[0]}-{TILT_YEARS[-1]} (max {t.max():.0%})"), tilts
    return "cosine", (f"cosine_eng still tilted (max {t.max():.0%} in {TILT_YEARS[0]}-{TILT_YEARS[-1]}, "
                      f"limit {TILT_MAX:.0%}); kept cosine and flagged {FLAG_YEARS[0]}-{FLAG_YEARS[1]}"), tilts


def make_monthly(panel: pd.DataFrame, ev: pd.DataFrame, info: pd.DataFrame, flag: bool) -> pd.DataFrame:
    left = panel.reset_index(drop=True)
    left["is_etf"] = etf_rows(left, info)
    right = ev[["permno", "published_date", "gvkey", "filing_sim", "period_end",
                "date_source", "source"]].rename(columns={"gvkey": "gvkey_ev"})
    m = pd.merge_asof(left.sort_values("date"), right.sort_values("published_date"),
                      left_on="date", right_on="published_date", by="permno",
                      direction="backward", allow_exact_matches=True)
    age = ((m["date"].dt.year - m["published_date"].dt.year) * 12
           + (m["date"].dt.month - m["published_date"].dt.month))
    stale = m["published_date"].notna() & (age > MAX_AGE_MONTHS)
    drop_val = stale | m["is_etf"]
    for col in ("filing_sim", "period_end", "published_date", "date_source", "source", "gvkey_ev"):
        m.loc[drop_val, col] = pd.NA if m[col].dtype.kind not in "Mf" else np.nan
    m["gvkey"] = m["gvkey_ev"].astype("string").fillna(m["gvkey"].astype("string"))
    m["applies"] = np.where(m["is_etf"], "n/a (ETF)", "stock")
    out = m[["permno", "gvkey", "date", "filing_sim", "period_end", "published_date",
             "date_source", "source", "applies"]].sort_values(["permno", "date"]).reset_index(drop=True)
    out["date_source"] = out["date_source"].astype("string")
    out["source"] = out["source"].astype("string")
    out["applies"] = out["applies"].astype("string")
    if flag:   # rule 10: cosine kept -> mark values from filings published in the format-change years
        y = out["published_date"].dt.year
        out[FLAG_COL] = y.between(*FLAG_YEARS).fillna(False).astype(bool)
    return out


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Step 8 build for lazy_prices.")
    ap.add_argument("--measure", choices=("auto",) + MEASURES, default="auto",
                    help="similarity measure for filing_sim (default: rule 10 decides)")
    a = ap.parse_args()
    paths = {
        "raw": need(LP / "bow_cossim_10k.parquet", "pull_bow_cossim.py"),
        "ciklink": need(LP / "ciklink.parquet", "pull_bow_cossim.py"),
        "ccm": need(LP / "ccm_links.parquet", "pull_bow_cossim.py"),
        "days": need(LP / "trading_days.parquet", "pull_bow_cossim.py"),
        "info": need(LP / "security_info.parquet", "pull_security_info.py"),
        "panel": need(DATA / "crsp_monthly_ratios_clean.parquet", "the team panel setup (SETUP.md)"),
    }
    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices Step 8 build, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            raw = pd.read_parquet(paths["raw"])
            if "form_prev" not in raw.columns or "lookback" not in raw.columns:
                raise SystemExit("bow_cossim_10k.parquet is from version 1 of the pull. "
                                 "Run pull_bow_cossim.py (version 2) first.")
            for col in ("fdate", "rdate", "secadate", "fdate_prev"):
                raw[col] = raw[col].astype(NS)
            ciklink = pd.read_parquet(paths["ciklink"])
            for col in ("link_start_date", "link_end_date"):
                ciklink[col] = ciklink[col].astype(NS)
            ccm = pd.read_parquet(paths["ccm"])
            for col in ("linkdt", "linkenddt"):
                ccm[col] = ccm[col].astype(NS)
            ccm["permno"] = ccm["permno"].astype("int64")
            days = pd.read_parquet(paths["days"])
            info = pd.read_parquet(paths["info"])
            for col in ("secinfostartdt", "secinfoenddt"):
                info[col] = info[col].astype(NS)
            panel = pd.read_parquet(paths["panel"], columns=["permno", "date", "gvkey", "me"])
            panel["me"] = pd.to_numeric(panel["me"], errors="coerce").astype("float64")
            panel["permno"] = panel["permno"].astype("int64")
            panel["date"] = panel["date"].astype(NS)

            section("1. From filings to events")
            funnel: list = []
            c = pick_comparisons(raw, funnel)
            c = add_published_date(c, days)
            c = link_gvkey(c, ciklink, funnel)
            x = link_permno(c, ccm, funnel)
            ev = make_events(x, funnel)
            measure, reason, tilts = choose_measure(ev, panel, a.measure)
            ev["filing_sim"] = ev[measure]
            ev["measure"] = measure
            for step_name, n in funnel:
                print(f"  {step_name:<86s}{n:>10,}" if n is not None else f"  {step_name}")

            section("2. Event checks")
            print(f"  events: {len(ev):,}; permnos: {ev['permno'].nunique():,}; "
                  f"published {ev['published_date'].min():%Y-%m-%d} to {ev['published_date'].max():%Y-%m-%d}")
            print(f"  duplicate (permno, published_date): {ev.duplicated(['permno', 'published_date']).sum()} (should be 0)")
            bad = (ev["published_date"] < ev["period_end"]).sum()
            print(f"  published_date before period_end: {bad} (should be 0); "
                  f"missing period_end (WRDS rdate missing or impossible): {ev['period_end'].isna().sum()}; "
                  f"date_source assumed: {(ev['date_source'] == 'assumed').mean():.0%}")
            lag = (ev["published_date"] - ev["period_end"]).dt.days
            print(f"  days from period_end to published_date: median {lag.median():.0f}, "
                  f"10th pct {lag.quantile(.1):.0f}, 90th pct {lag.quantile(.9):.0f}")
            sel = x.set_index(["cik", "accession"]).loc[
                list(zip(ev["cik"], ev["accession"]))]
            print(f"  accepted after 4 p.m. or no time -> moved to the next trading day: "
                  f"{(~sel['by_close']).mean():.1%} of events "
                  f"(with a time: {(sel['has_time'] & ~sel['by_close']).sum() / max(sel['has_time'].sum(), 1):.1%})")
            print("  basis of published_date: " + "; ".join(
                f"{k}: {v:,}" for k, v in ev["published_basis"].value_counts().items()))
            print("  how the gvkey was found: " + ", ".join(
                f"{k}: {v:,}" for k, v in ev["gvkey_rule"].value_counts().items()))

            section("3. Measure (rule 10)")
            print("  share of each published year's bottom fifth that are the largest fifth of firms "
                  "(20% = no tilt):")
            tt = tilts.loc[(tilts.index >= 2006) & (tilts.index <= 2016)]
            show(tt.apply(lambda c: c.map("{:.0%}".format)).rename_axis("year").reset_index())
            print(f"  -> filing_sim = {measure}: {reason}")

            section("4. Monthly file")
            mo = make_monthly(panel, ev, info, flag=(measure == "cosine"))
            if FLAG_COL in mo:
                print(f"  monthly rows flagged {FLAG_COL}: {mo[FLAG_COL].sum():,}")
            print(f"  rows: {len(mo):,} (panel rows: {len(panel):,}); "
                  f"duplicate (permno, date): {mo.duplicated(['permno', 'date']).sum()} (should be 0)")
            etf = mo["applies"] == "n/a (ETF)"
            print(f"  rows marked n/a (ETF): {etf.sum():,} ({mo.loc[etf, 'permno'].nunique():,} permnos)")
            st = mo[~etf]
            print(f"  stock rows with a value: {st['filing_sim'].notna().mean():.1%} overall")
            yr = pd.DataFrame({
                "events": ev.groupby(ev["published_date"].dt.year).size(),
                "sim_p10": ev.groupby(ev["published_date"].dt.year)["filing_sim"].quantile(0.10),
                "sim_median": ev.groupby(ev["published_date"].dt.year)["filing_sim"].median(),
                "stock_rows": st.groupby(st["date"].dt.year).size(),
                "with_value": st.groupby(st["date"].dt.year)["filing_sim"].apply(lambda s: s.notna().mean()),
            })
            yr = yr.loc[yr.index >= 1995].rename_axis("year").reset_index()
            yr["events"] = yr["events"].fillna(0).astype("int64")
            yr[["sim_p10", "sim_median"]] = yr[["sim_p10", "sim_median"]].round(3)
            yr["with_value"] = yr["with_value"].map("{:.0%}".format)
            print("  by year (events and similarity by published year; coverage of the panel's stock rows):")
            show(yr)
            age = ((st["date"].dt.year - st["published_date"].dt.year) * 12
                   + (st["date"].dt.month - st["published_date"].dt.month))
            print(f"  age of the value used (months): median {age.median():.0f}, max {age.max():.0f} (cap {MAX_AGE_MONTHS})")
            print("  splits: nothing to adjust; filing_sim is computed from text only "
                  "(Step 9 shows one split with no jump).")

            ev.to_parquet(LP / "lazy_prices_events.parquet", index=False)
            mo.to_parquet(LP / "lazy_prices_monthly.parquet", index=False)
            print(f"\n  saved data/lazy_prices/lazy_prices_events.parquet ({len(ev):,} rows)")
            print(f"  saved data/lazy_prices/lazy_prices_monthly.parquet ({len(mo):,} rows)")
            print("\nDone. Reply 'done' in the chat; Claude will read data/lazy_prices/build_log.txt.")
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
