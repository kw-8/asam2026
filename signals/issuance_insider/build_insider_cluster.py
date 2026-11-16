"""
build_insider_cluster.py
========================
Step 8 (Construct) of prompts/data_acquisition.md for signals/issuance_insider,
signal 2: insider_cluster. No WRDS needed; reads the Step 7 SEC pull
(pull_sec_insiders.py) and link files already in data/lazy_prices/.

Decisions it follows (progress.md: definitions approved 2026-11-15, Step 4b;
timing 2026-11-15, Step 6; build rules approved 2026-11-15, Step 8)
  Primary  insider_cluster       A: number of different officers/directors whose
                                 purchase was part of a tight cluster (another
                                 officer/director of the same firm bought on the same
                                 or an adjacent trading day) and became public in the
                                 last 3 months (months t-2..t). 0 = none.
  Checks   insider_buyers_1m     B: number of different officer/director buyers
                                 whose purchase became public in month t.
           insider_buy_value_3m  C: dollars bought by officers/directors, public in
                                 months t-2..t, / the firm's market value at t
                                 (sum of the panel's `me` over the firm's permnos).
           insider_npr_6m        D: (buys - sells) / (buys + sells) over months
                                 t-5..t, counting insider-days (one per insider, trade
                                 day and direction). Blank if no insider traded.
  Combination rules C1/C2 use insider_cluster only. No winsorizing, no ranking.

Rules applied
  1. Trades: purchases = code P recorded as acquired (A); sales = code S recorded as
     disposed (D); contradictory rows dropped. Original Form 4 and Form 5 only
     (4/A, 5/A dropped). Common stock only: security titles naming preferred,
     warrants, notes, debentures, bonds, rights or options are dropped (Step 4b).
  2. Insiders: the reporting owner's relationship contains "officer" or "director"
     (any spelling or combination); pure 10% holders and "other" are dropped. A
     joint filing counts as ONE insider: the first officer/director listed on it.
  3. Stale trades: filed more than 90 days after the trade dropped; filed before
     the trade date dropped.
  4. Public date: the next trading day after the filing date (Step 6: the filing time
     of day is unknown, so assume after the close). date_source = exact.
  5. Link: issuer CIK -> gvkey (data/lazy_prices/ciklink.parquet, "Valid" links whose
     dates cover the filing date; if several gvkeys qualify: one with a CRSP link at
     that date first, then source CRSP/Compustat Merged > Compustat Security >
     Compustat Company > Capital IQ, then the latest link start). If no Valid link is
     dated at the filing date but the issuer CIK links to exactly ONE gvkey, that gvkey
     is used (fix adopted 2026-11-15 in Step 9: a CIK is one company's permanent ID,
     so the link dates add nothing; e.g. Google Inc's link starts only 2007-04).
     Event file column cik_link = "dated" or "undated". -> permno (CCM link valid at
     the filing date, primary first; event file only).
  6. Insider-days: rows of one filing are summed per insider, trade day and
     direction; a filing that repeats exactly the same insider, day, direction,
     shares and dollars as an earlier filing is dropped (re-reports, e.g. on Form 5);
     then summed again across filings. An insider-day becomes public at its earliest
     filing's public date.
  7. Cluster (A): a purchase insider-day is clustered if a DIFFERENT insider of the
     same firm (gvkey) bought within one trading day (trade dates; a trade on a
     non-trading day counts as the next trading day). It counts once both are public:
     cluster_public = max(own public date, earliest partner's public date).
  8. Firm level: the signals are computed per gvkey and given to every permno of that
     gvkey (dual-class firms share one value). gvkey per panel row as for
     net_issuance: CCM link at the month-end, else the panel's.
  9. Zero vs blank: a firm-month whose gvkey has a Valid CIK link covering the
     month-end gets 0 when nothing happened; otherwise blank (we cannot see its
     filings). Blank before the window is complete: B from 2006-01, A and C from
     2006-03, D from 2006-06. ETFs: applies = "n/a (ETF)" and blank.
  Dates in the monthly file are for A: period_end = latest trade date used,
  published_date = latest cluster_public used, date_source = exact (A > 0),
  "no event" (A = 0), blank (A blank).

Outputs (data/issuance_insider/, Git ignores it)
  insider_cluster_monthly.parquet  one row per panel row:
      permno, gvkey, date, insider_cluster, period_end, published_date, date_source,
      source, applies, insider_buyers_1m, insider_buy_value_3m, insider_npr_6m
  insider_cluster_events.parquet   one row per insider-day (purchases and sales):
      permno, gvkey, period_end (trade date), published_date, date_source, source,
      version, direction, insider_cik, insider_name, relationship, title, shares,
      value_usd, n_trans, n_filings, accession_number, filing_date, issuercik,
      cik_link, clustered, cluster_size, cluster_public
  build_insider_log.txt            everything printed

Run from the repo root, with the .venv active (about 1-3 minutes):
    python signals\\issuance_insider\\build_insider_cluster.py
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
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
LOG = D / "build_insider_log.txt"

MAX_GAP_DAYS = 90
WIN_A, WIN_C, WIN_D = 3, 3, 6
FIRST_MONTH = pd.Timestamp("2006-01-31")
SOURCE = "SEC Insider Transactions Data Sets (Forms 4/5), 2006Q1-2025Q4"
NON_COMMON = r"\b(?:preferred|pfd|pref|warrants?|notes?|debentures?|bonds?|rights?|options?)\b"
SOURCE_RANK = {"CRSP/Compustat Merged": 0, "Compustat Security": 1, "Compustat Company": 2, "Capital IQ": 3}
FAR_PAST, FAR_FUTURE = pd.Timestamp("1900-01-01"), pd.Timestamp("2099-12-31")

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 40)


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


def mi(d: pd.Series) -> pd.Series:
    """Month index (year * 12 + month - 1)."""
    return d.dt.year * 12 + d.dt.month - 1


def mi_to_date(m: pd.Series) -> pd.Series:
    return pd.to_datetime(pd.DataFrame({"year": m // 12, "month": m % 12 + 1, "day": 1})) + MonthEnd(0)


# ----------------------------------------------------------------------------
# Calendar
# ----------------------------------------------------------------------------
def trading_calendar() -> np.ndarray:
    td = pd.read_parquet(LP / "trading_days.parquet")["date"]
    td = pd.to_datetime(td).sort_values().drop_duplicates()
    # filings on the last day of the data are public on the next trading day; extend a few weeks
    # past the file (business days, skipping New Year's Day)
    ext = pd.bdate_range(td.iloc[-1] + pd.Timedelta(days=1), periods=30)
    ext = ext[~((ext.month == 1) & (ext.day == 1))]
    return pd.DatetimeIndex(pd.concat([td, pd.Series(ext)])).values.astype("datetime64[ns]")


def next_trading_day(d: pd.Series, td: np.ndarray) -> pd.Series:
    """First trading day strictly after d."""
    i = np.searchsorted(td, d.values.astype("datetime64[ns]"), side="right")
    return pd.Series(td[np.minimum(i, len(td) - 1)], index=d.index)


def trading_index(d: pd.Series, td: np.ndarray) -> pd.Series:
    """Index of the first trading day on or after d."""
    return pd.Series(np.searchsorted(td, d.values.astype("datetime64[ns]"), side="left"), index=d.index)


# ----------------------------------------------------------------------------
# 1. Trades, filters, insiders
# ----------------------------------------------------------------------------
def load_trades(td: np.ndarray) -> tuple[pd.DataFrame, list]:
    tr = pd.read_parquet(D / "sec_trans.parquet", columns=[
        "accession_number", "nonderiv_trans_sk", "security_title", "trans_date", "trans_code", "trans_shares",
        "trans_pricepershare", "trans_acquired_disp_cd"])
    sub = pd.read_parquet(D / "sec_submissions.parquet", columns=[
        "accession_number", "filing_date", "document_type", "issuercik", "issuername", "issuertradingsymbol"])
    own = pd.read_parquet(D / "sec_owners.parquet", columns=[
        "accession_number", "rptownercik", "rptownername", "rptowner_relationship", "rptowner_title"])
    steps = []

    def note(label, df):
        steps.append((label, int((df["trans_code"] == "P").sum()), int((df["trans_code"] == "S").sum())))

    note("P and S rows in the pull", tr)
    ok = ((tr["trans_code"] == "P") & (tr["trans_acquired_disp_cd"] == "A")) | \
         ((tr["trans_code"] == "S") & (tr["trans_acquired_disp_cd"] == "D"))
    tr = tr[ok]
    note("code agrees with acquired/disposed", tr)
    tr = tr.merge(sub, on="accession_number", how="inner")
    tr = tr[tr["document_type"].isin(["4", "5"])]
    note("original Form 4 or 5", tr)
    tr = tr[~tr["security_title"].fillna("").str.lower().str.contains(NON_COMMON, regex=True)]
    note("common stock (no preferred, warrants, notes, ...)", tr)
    gap = (tr["filing_date"] - tr["trans_date"]).dt.days
    tr = tr[gap.between(0, MAX_GAP_DAYS)]
    note(f"filed 0-{MAX_GAP_DAYS} days after the trade", tr)

    rel = own["rptowner_relationship"].fillna("").str.lower()
    od = own[rel.str.contains("officer") | rel.str.contains("director")]
    od = od.drop_duplicates("accession_number", keep="first")      # joint filing -> first officer/director
    od = od.rename(columns={"rptownercik": "insider_cik", "rptownername": "insider_name",
                            "rptowner_relationship": "relationship", "rptowner_title": "title"})
    tr = tr.merge(od[["accession_number", "insider_cik", "insider_name", "relationship", "title"]],
                  on="accession_number", how="inner")
    note("reporting owner is an officer or director", tr)

    tr["direction"] = np.where(tr["trans_code"] == "P", "buy", "sell")
    px = tr["trans_pricepershare"].where(tr["trans_pricepershare"] > 0)
    tr["value_usd"] = tr["trans_shares"] * px
    tr["published_date"] = next_trading_day(tr["filing_date"], td)
    return tr, steps


# ----------------------------------------------------------------------------
# 2. Link issuer CIK -> gvkey (-> permno)
# ----------------------------------------------------------------------------
def cik_links(ciklink: pd.DataFrame) -> pd.DataFrame:
    v = ciklink[ciklink["link_desc"].astype(str).str.startswith("Valid")].copy()
    v["cik"] = v["cik"].astype(str).str.strip().str.lstrip("0")
    v["start"] = v["link_start_date"].fillna(FAR_PAST)
    v["end"] = v["link_end_date"].fillna(FAR_FUTURE)
    v["rank"] = v["source"].map(SOURCE_RANK).fillna(9)
    return v[["cik", "gvkey", "start", "end", "rank"]].drop_duplicates()


def ccm_ready(ccm: pd.DataFrame) -> pd.DataFrame:
    c = ccm.copy()
    c["linkenddt"] = c["linkenddt"].fillna(FAR_FUTURE)
    c["pr"] = c["linkprim"].map({"P": 0, "C": 1}).fillna(2)
    return c[["gvkey", "permno", "linkdt", "linkenddt", "pr"]]


def map_issuers(pairs: pd.DataFrame, links: pd.DataFrame, ccm: pd.DataFrame) -> pd.DataFrame:
    """pairs: issuercik, filing_date -> + gvkey, permno (at the filing date)."""
    x = pairs.merge(links, left_on="issuercik", right_on="cik", how="inner")
    x = x[(x["filing_date"] >= x["start"]) & (x["filing_date"] <= x["end"])]
    y = x[["issuercik", "filing_date", "gvkey"]].drop_duplicates().merge(ccm, on="gvkey", how="inner")
    y = y[(y["filing_date"] >= y["linkdt"]) & (y["filing_date"] <= y["linkenddt"])]
    y = y.sort_values(["issuercik", "filing_date", "gvkey", "pr"]).drop_duplicates(
        ["issuercik", "filing_date", "gvkey"])[["issuercik", "filing_date", "gvkey", "permno"]]
    x = x.merge(y, on=["issuercik", "filing_date", "gvkey"], how="left")
    x["no_permno"] = x["permno"].isna()
    x = x.sort_values(["issuercik", "filing_date", "no_permno", "rank", "start"],
                      ascending=[True, True, True, True, False])
    x = x.drop_duplicates(["issuercik", "filing_date"])[["issuercik", "filing_date", "gvkey", "permno"]]
    x["cik_link"] = "dated"
    # no dated link, but the CIK links to exactly one gvkey -> use it
    n_g = links.groupby("cik")["gvkey"].nunique()
    one = links[links["cik"].isin(n_g[n_g == 1].index)].drop_duplicates("cik").set_index("cik")["gvkey"]
    rest = pairs.merge(x[["issuercik", "filing_date"]], on=["issuercik", "filing_date"], how="left", indicator=True)
    rest = rest[(rest["_merge"] == "left_only") & rest["issuercik"].isin(one.index)].drop(columns="_merge")
    rest["gvkey"] = rest["issuercik"].map(one)
    z = rest.merge(ccm, on="gvkey", how="inner")
    z = z[(z["filing_date"] >= z["linkdt"]) & (z["filing_date"] <= z["linkenddt"])]
    z = z.sort_values(["issuercik", "filing_date", "pr"]).drop_duplicates(["issuercik", "filing_date"])
    rest = rest.merge(z[["issuercik", "filing_date", "permno"]], on=["issuercik", "filing_date"], how="left")
    rest["cik_link"] = "undated"
    return pd.concat([x, rest], ignore_index=True)


# ----------------------------------------------------------------------------
# 3. Insider-days and clusters
# ----------------------------------------------------------------------------
def insider_days(tr: pd.DataFrame, td: np.ndarray) -> tuple[pd.DataFrame, int]:
    k = ["gvkey", "insider_cik", "trans_date", "direction"]
    f = tr.groupby(["accession_number"] + k, as_index=False, dropna=False).agg(
        shares=("trans_shares", "sum"), value_usd=("value_usd", lambda s: s.sum(min_count=1)),
        n_trans=("trans_shares", "size"), filing_date=("filing_date", "first"),
        published_date=("published_date", "first"), permno=("permno", "first"), issuercik=("issuercik", "first"),
        cik_link=("cik_link", "first"),
        insider_name=("insider_name", "first"), relationship=("relationship", "first"), title=("title", "first"))
    f = f.sort_values(["filing_date", "accession_number"])
    dup = f.duplicated(k + ["shares", "value_usd"], keep="first")
    f = f[~dup]
    e = f.groupby(k, as_index=False).agg(
        shares=("shares", "sum"), value_usd=("value_usd", lambda s: s.sum(min_count=1)),
        n_trans=("n_trans", "sum"), n_filings=("accession_number", "size"),
        accession_number=("accession_number", "first"), filing_date=("filing_date", "first"),
        published_date=("published_date", "min"), permno=("permno", "first"), issuercik=("issuercik", "first"),
        cik_link=("cik_link", "first"), insider_name=("insider_name", "first"), relationship=("relationship", "first"), title=("title", "first"))
    e["tdx"] = trading_index(e["trans_date"], td)
    return e, int(dup.sum())


def mark_clusters(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    e["clustered"] = False
    e["cluster_size"] = np.nan
    e["cluster_public"] = pd.NaT
    b = e[e["direction"] == "buy"][["gvkey", "insider_cik", "tdx", "published_date"]].reset_index()
    partners = pd.concat([b.assign(tdx=b["tdx"] + d) for d in (-1, 0, 1)], ignore_index=True)
    m = b.merge(partners, on=["gvkey", "tdx"], suffixes=("", "_o"))
    m = m[m["insider_cik"] != m["insider_cik_o"]]
    g = m.groupby("index").agg(first_partner_pub=("published_date_o", "min"), n=("insider_cik_o", "nunique"))
    e.loc[g.index, "clustered"] = True
    e.loc[g.index, "cluster_size"] = g["n"] + 1
    e.loc[g.index, "cluster_public"] = np.maximum(e.loc[g.index, "published_date"].values,
                                                  g["first_partner_pub"].values)
    return e


# ----------------------------------------------------------------------------
# 4. Monthly values per gvkey
# ----------------------------------------------------------------------------
def spread(df: pd.DataFrame, month_col: str, n: int) -> pd.DataFrame:
    """Copy each row into months m, m+1, ..., m+n-1 (a trailing n-month window)."""
    return pd.concat([df.assign(m=df[month_col] + k) for k in range(n)], ignore_index=True)


def monthly_by_gvkey(e: pd.DataFrame) -> pd.DataFrame:
    buys = e[e["direction"] == "buy"].copy()
    buys["pm"] = mi(buys["published_date"])
    # A
    c = buys[buys["clustered"]].copy()
    c["pm"] = mi(c["cluster_public"])
    a = spread(c[["gvkey", "insider_cik", "pm", "trans_date", "cluster_public"]], "pm", WIN_A)
    A = a.groupby(["gvkey", "m"]).agg(insider_cluster=("insider_cik", "nunique"), period_end=("trans_date", "max"),
                                      published_date=("cluster_public", "max"))
    # B
    B = buys.groupby(["gvkey", "pm"])["insider_cik"].nunique().rename("insider_buyers_1m")
    B.index = B.index.set_names(["gvkey", "m"])
    # C (dollars; ME added later)
    cv = buys.groupby(["gvkey", "pm"], as_index=False)["value_usd"].sum()
    C = spread(cv, "pm", WIN_C).groupby(["gvkey", "m"])["value_usd"].sum().rename("buy_value_usd_3m")
    # D
    e2 = e.assign(pm=mi(e["published_date"]), nb=(e["direction"] == "buy").astype(int),
                  ns=(e["direction"] == "sell").astype(int))
    dd = e2.groupby(["gvkey", "pm"], as_index=False)[["nb", "ns"]].sum()
    Dm = spread(dd, "pm", WIN_D).groupby(["gvkey", "m"])[["nb", "ns"]].sum()
    Dm["insider_npr_6m"] = (Dm["nb"] - Dm["ns"]) / (Dm["nb"] + Dm["ns"])
    return pd.concat([A, B, C, Dm["insider_npr_6m"]], axis=1).reset_index()


# ----------------------------------------------------------------------------
# Keys and flags (as in build_net_issuance.py)
# ----------------------------------------------------------------------------
def attach_gvkey(df: pd.DataFrame, ccm: pd.DataFrame, date_col: str) -> pd.Series:
    c = ccm.assign(linkenddt=ccm["linkenddt"].fillna(pd.Timestamp("2099-12-31")))
    x = df[["permno", date_col]].reset_index().merge(c[["permno", "gvkey", "linkdt", "linkenddt", "linkprim"]],
                                                      on="permno")
    x = x[(x[date_col] >= x["linkdt"]) & (x[date_col] <= x["linkenddt"])]
    x = x.sort_values(["index", "linkprim"], key=lambda s: s.map({"P": 0, "C": 1}) if s.name == "linkprim" else s)
    return x.drop_duplicates("index").set_index("index")["gvkey"].reindex(df.index)


def etf_flag(df: pd.DataFrame, si: pd.DataFrame) -> pd.Series:
    e = si[si["securitysubtype"] == "ETF"][["permno", "secinfostartdt", "secinfoenddt"]]
    if e.empty:
        return pd.Series(False, index=df.index)
    x = df[["permno", "date"]].reset_index().merge(e, on="permno")
    x = x[(x["date"] >= x["secinfostartdt"]) & (x["date"] <= x["secinfoenddt"] + MonthEnd(0))]
    return df.index.isin(set(x["index"]))


def observable(out: pd.DataFrame, links: pd.DataFrame) -> pd.Series:
    x = out[["gvkey", "date"]].reset_index().merge(links[["gvkey", "start", "end"]].drop_duplicates(), on="gvkey")
    x = x[(x["date"] >= x["start"]) & (x["date"] <= x["end"])]
    return out.index.isin(set(x["index"]))


# ----------------------------------------------------------------------------
def main() -> None:
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            run()
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


def run() -> None:
    print(f"insider_cluster Step 8 build, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    td = trading_calendar()
    ccm_raw = pd.read_parquet(LP / "ccm_links.parquet")
    ccm_raw["permno"] = ccm_raw["permno"].astype("int64")
    ccm = ccm_ready(ccm_raw)
    links = cik_links(pd.read_parquet(LP / "ciklink.parquet"))
    si = pd.read_parquet(LP / "security_info.parquet")
    si["permno"] = si["permno"].astype("int64")

    section("1. Trades kept (rows)")
    tr, steps = load_trades(td)
    show(pd.DataFrame(steps, columns=["step", "purchases (P)", "sales (S)"]))

    section("2. Link issuer CIK -> gvkey at the filing date")
    pairs = tr[["issuercik", "filing_date"]].drop_duplicates()
    mp = map_issuers(pairs, links, ccm)
    tr = tr.merge(mp, on=["issuercik", "filing_date"], how="left")
    for d in ("buy", "sell"):
        s = tr[tr["direction"] == d]
        print(f"  {d}s: rows with a gvkey {s['gvkey'].notna().mean():.1%}; with a permno {s['permno'].notna().mean():.1%}"
              f"; issuers with a gvkey {s.groupby('issuercik')['gvkey'].apply(lambda g: g.notna().any()).mean():.1%}")
    und = tr["cik_link"] == "undated"
    print(f"  of which via a CIK linking to one gvkey outside its link dates (undated): purchases "
          f"{(und & (tr['direction'] == 'buy')).sum():,}, sales {(und & (tr['direction'] == 'sell')).sum():,}, "
          f"issuers {tr.loc[und, 'issuercik'].nunique():,}")
    tr = tr[tr["gvkey"].notna()]
    note_p, note_s = int((tr["direction"] == "buy").sum()), int((tr["direction"] == "sell").sum())
    print(f"  kept with a gvkey: {note_p:,} purchase rows, {note_s:,} sale rows")
    print(f"  purchases with no usable price (value left out of C): {tr.loc[tr['direction'] == 'buy', 'value_usd'].isna().mean():.1%}")

    section("3. Insider-days and clusters")
    e, n_dup = insider_days(tr, td)
    e = mark_clusters(e)
    nb = (e["direction"] == "buy").sum()
    print(f"  re-reported filings dropped (same insider, day, direction, shares, dollars as an earlier filing): {n_dup:,}")
    print(f"  insider-days: {nb:,} purchases, {(e['direction'] == 'sell').sum():,} sales; "
          f"{e['gvkey'].nunique():,} firms; {e['insider_cik'].nunique():,} insiders")
    cl = e[e["clustered"]]
    print(f"  clustered purchase insider-days: {len(cl):,} ({len(cl) / nb:.1%} of purchase insider-days); "
          f"firms with any cluster: {cl['gvkey'].nunique():,}")
    print("  cluster size (insiders buying within one trading day, incl. self), share of clustered insider-days:")
    cs = cl["cluster_size"].clip(upper=6).value_counts(normalize=True).sort_index()
    show(pd.DataFrame({"size": [f"{int(i)}" if i < 6 else "6+" for i in cs.index], "share": cs.map("{:.1%}".format).values}))
    wait = (cl["cluster_public"] - cl["published_date"]).dt.days
    print(f"  clustered insider-days whose partner became public later than they did: {(wait > 0).mean():.1%} "
          f"(median extra wait among those {wait[wait > 0].median():.0f} days)")
    yr = e.assign(y=e["published_date"].dt.year).groupby("y").agg(
        purchases=("direction", lambda s: (s == "buy").sum()), sales=("direction", lambda s: (s == "sell").sum()),
        clustered=("clustered", "sum"))
    yr["clustered %"] = (yr["clustered"] / yr["purchases"]).map("{:.0%}".format)
    print("\n  insider-days by year made public:")
    show(yr.reset_index().rename(columns={"y": "year"}))
    big = cl.groupby(["gvkey", "tdx"]).agg(date=("trans_date", "min"), insiders=("insider_cik", "nunique"),
                                            issuer=("issuercik", "first"), value=("value_usd", "sum")).reset_index()
    names = tr.drop_duplicates("issuercik").set_index("issuercik")[["issuername", "issuertradingsymbol"]]
    big = big.join(names, on="issuer").sort_values(["insiders", "date", "gvkey"], ascending=[False, True, True],
                                                    kind="stable").head(10)
    big["value"] = (big["value"] / 1e6).round(2)
    print("\n  largest same-day clusters (insiders buying on one trading day; value in $ millions):")
    show(big[["date", "issuername", "issuertradingsymbol", "gvkey", "insiders", "value"]])

    section("4. Monthly file on the panel's rows")
    sig = monthly_by_gvkey(e)
    panel = pd.read_parquet(PANEL, columns=["permno", "date", "gvkey", "me"])
    panel["permno"] = pd.to_numeric(panel["permno"]).astype("int64")
    panel["date"] = pd.to_datetime(panel["date"]) + MonthEnd(0)
    out = panel[["permno", "date", "me"]].copy()
    out["gvkey"] = attach_gvkey(out, ccm_raw, "date")
    pg = panel.set_index(["permno", "date"])["gvkey"]
    out["gvkey"] = out["gvkey"].fillna(pd.Series(pg.reindex(pd.MultiIndex.from_frame(out[["permno", "date"]])).values,
                                                 index=out.index))
    out["m"] = mi(out["date"])
    firm_me = out.groupby(["gvkey", "m"])["me"].sum(min_count=1).rename("firm_me").reset_index()
    out = out.merge(sig, on=["gvkey", "m"], how="left").merge(firm_me, on=["gvkey", "m"], how="left")
    obs = observable(out, links)
    is_etf = etf_flag(out, si)
    first = mi(pd.Series([FIRST_MONTH]))[0]
    in_b = obs & ~is_etf & (out["m"] >= first)
    in_a = obs & ~is_etf & (out["m"] >= first + WIN_A - 1)
    in_d = obs & ~is_etf & (out["m"] >= first + WIN_D - 1)
    out["insider_cluster"] = out["insider_cluster"].fillna(0).where(in_a)
    out["insider_buyers_1m"] = out["insider_buyers_1m"].fillna(0).where(in_b)
    me_ok = out["firm_me"] > 0
    out["insider_buy_value_3m"] = (out["buy_value_usd_3m"].fillna(0) / (out["firm_me"] * 1000)).where(in_a & me_ok)
    out["insider_npr_6m"] = out["insider_npr_6m"].where(in_d)
    pos = out["insider_cluster"] > 0
    out.loc[~pos, ["period_end", "published_date"]] = pd.NaT
    out["date_source"] = np.where(pos, "exact", np.where(out["insider_cluster"] == 0, "no event", None))
    out["source"] = SOURCE
    out["applies"] = np.where(is_etf, "n/a (ETF)", "stock")
    cols = ["permno", "gvkey", "date", "insider_cluster", "period_end", "published_date", "date_source", "source",
            "applies", "insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]
    out = out[cols].sort_values(["permno", "date"]).reset_index(drop=True)
    sigc = ["insider_cluster", "insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]
    print(f"  rows {len(out):,} (panel {len(panel):,}); duplicates (permno, date): "
          f"{out.duplicated(['permno', 'date']).sum():,}; ETF rows: {is_etf.sum():,}")
    p06 = out["date"] >= "2006-06-30"
    print(f"  from 2006-06: rows {p06.sum():,}; gvkey missing {out.loc[p06, 'gvkey'].isna().mean():.1%}; "
          f"gvkey with a Valid CIK link at the month-end (observable) {pd.Series(obs)[p06.values].mean():.1%}")
    print("  share of panel rows from 2006-06 with a value / with a non-zero value:")
    t = pd.DataFrame({"column": sigc, "with value": [out.loc[p06, c].notna().mean() for c in sigc],
                      "non-zero": [(out.loc[p06, c].fillna(0) != 0).mean() for c in sigc]})
    show(t.assign(**{k: t[k].map("{:.1%}".format) for k in ("with value", "non-zero")}))
    y = out[out["date"] >= "2006-01-31"].groupby(out["date"].dt.year).agg(
        rows=("permno", "size"), A_blank=("insider_cluster", lambda s: s.isna().mean()),
        A_pos=("insider_cluster", lambda s: (s > 0).mean()), A_ge2=("insider_cluster", lambda s: (s >= 2).mean()),
        B_ge2=("insider_buyers_1m", lambda s: (s >= 2).mean()), D_value=("insider_npr_6m", lambda s: s.notna().mean()))
    for c in y.columns[1:]:
        y[c] = y[c].map("{:.1%}".format)
    print("\n  by year (share of panel rows): A blank, A > 0, A >= 2, B >= 2, D has a value")
    show(y.reset_index().rename(columns={"date": "year"}))
    vc = out.loc[p06, "insider_cluster"].dropna().clip(upper=6).value_counts(normalize=True).sort_index()
    print("\n  insider_cluster values (from 2006-06; 6 = 6 or more): " +
          ", ".join(f"{int(k)}: {v:.2%}" for k, v in vc.items()))
    q = out.loc[p06, ["insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]].describe(
        percentiles=[.5, .9, .99, .999]).T
    print("\n  distribution of the checks (insider_buy_value_3m is a fraction of market value; 0.001 = 0.1%):")
    show(q.reset_index().rename(columns={"index": "column"}).round(4))
    nz = out.loc[p06 & (out["insider_buy_value_3m"] > 0), "insider_buy_value_3m"]
    print(f"  insider_buy_value_3m when > 0: median {nz.median():.5f}, 99th pct {nz.quantile(.99):.4f}, "
          f"max {nz.max():.3f}; rows above 0.10 (10% of market value): {(nz > 0.10).sum():,}")
    r = out.loc[p06, sigc].corr(method="spearman").round(2)
    print("\n  rank correlations between the versions (rows with both values):")
    show(r.reset_index().rename(columns={"index": ""}))
    dg = out.loc[p06 & pos]
    print(f"\n  A > 0 rows: published_date <= date in {(dg['published_date'] <= dg['date']).mean():.2%}; "
          f"period_end <= published_date in {(dg['period_end'] <= dg['published_date']).mean():.2%}; "
          f"median months from latest trade to month-end {((dg['date'] - dg['period_end']).dt.days / 30.44).median():.1f}")

    section("5. Save")
    out.to_parquet(D / "insider_cluster_monthly.parquet", index=False)
    print(f"  saved data/issuance_insider/insider_cluster_monthly.parquet ({len(out):,} rows)")
    ev = e.rename(columns={"trans_date": "period_end"})
    ev["date_source"] = "exact"
    ev["source"] = SOURCE
    ev["version"] = "original"
    ev["permno"] = ev["permno"].astype("Int64")
    evcols = ["permno", "gvkey", "period_end", "published_date", "date_source", "source", "version", "direction",
              "insider_cik", "insider_name", "relationship", "title", "shares", "value_usd", "n_trans", "n_filings",
              "accession_number", "filing_date", "issuercik", "cik_link", "clustered", "cluster_size", "cluster_public"]
    ev[evcols].sort_values(["gvkey", "period_end", "insider_cik"]).to_parquet(
        D / "insider_cluster_events.parquet", index=False)
    print(f"  saved data/issuance_insider/insider_cluster_events.parquet ({len(ev):,} rows)")


if __name__ == "__main__":
    main()
