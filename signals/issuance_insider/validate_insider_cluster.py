"""
validate_insider_cluster.py
===========================
Step 9 (Validate) of prompts/data_acquisition.md for signals/issuance_insider,
signal 2: insider_cluster. No WRDS needed. Reads the Step 8 files and, for an
independent check, the raw SEC tables from Step 7. Changes nothing.

Checks (PASS / FAIL, or INFO = numbers to look at, no pass mark)
   1. Keys: one row per panel row, no duplicates (monthly file and event file).
   2. Coverage: share of panel rows with a value, by year; why rows are blank; ETFs.
   3. Dates: every event public on the next trading day after its filing date, filed
      0-90 days after the trade; every A > 0 value uses only filings public by the
      month-end; date_source consistent with the value.
   4. Independent recomputation: A, B, C, D rebuilt from the raw SEC rows with
      separate, plain-loop code for a random sample of ~300 firms (plus named
      firms), compared with the monthly file.
   5. Name / CIK change: Facebook -> Meta (2021, same CIK) keeps one unbroken
      history; Google Inc -> Alphabet Inc (2015, new CIK) continues under one gvkey.
   6. Split: NVIDIA (10-for-1, 2024-06) and Tesla (5-for-1 2020-08, 3-for-1 2022-08):
      reported trade prices are in the units of the trade date (close to CRSP's
      unadjusted month-end price before and after), so dollar values do not jump.
   7. Internal consistency: ranges; A > 0 always has D; A > 0 with C = 0 only when
      no purchase had a price.
   8. Link fix (adopted 2026-11-15): filings whose issuer CIK links to exactly one
      gvkey but not at the filing date are in the event file (cik_link = undated);
      INFO on filings still dropped (CIK linking to several gvkeys, none dated).
   9. Outliers (INFO): C above 10% of market value and its cause; largest clusters
      and whether they fall in the stock's first CRSP month (IPO); share of A > 0 in a
      stock's first 3 months.
  10. Three firms by hand (INFO): cluster purchases with links to the Form 4s on
      EDGAR, for you to open and compare; Apple as a firm whose insiders do not buy.

Run from the repo root, with the .venv active (about 2-4 minutes):
    python signals\\issuance_insider\\validate_insider_cluster.py
Everything printed is also saved to data/issuance_insider/validate_insider_log.txt.
"""
from __future__ import annotations

import math
import re
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "issuance_insider"
LP = REPO / "data" / "lazy_prices"
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
LOG = D / "validate_insider_log.txt"

NON_COMMON = re.compile(r"\b(?:preferred|pfd|pref|warrants?|notes?|debentures?|bonds?|rights?|options?)\b")
MAX_GAP = 90
FIRST_M = 2006 * 12 + 0          # 2006-01
SEED = 2026
N_CLUSTER, N_BUY, N_SELL = 150, 100, 50
EDGAR = "https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{acc}-index.htm"

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 34)

RESULTS: list[tuple[str, str, str]] = []


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


def record(name: str, ok: bool | None, detail: str) -> None:
    status = "INFO" if ok is None else ("PASS" if ok else "FAIL")
    RESULTS.append((name, status, detail))
    print(f"  -> {status}: {detail}")


def mi(d) -> int:
    return d.year * 12 + d.month - 1


def mi_s(s: pd.Series) -> pd.Series:
    return s.dt.year * 12 + s.dt.month - 1


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
def trading_days() -> list:
    td = pd.to_datetime(pd.read_parquet(LP / "trading_days.parquet")["date"]).sort_values().drop_duplicates()
    extra = [d for d in pd.bdate_range(td.iloc[-1] + pd.Timedelta(days=1), periods=30) if not (d.month == 1 and d.day == 1)]
    return list(td) + extra


def load():
    out = pd.read_parquet(D / "insider_cluster_monthly.parquet")
    ev = pd.read_parquet(D / "insider_cluster_events.parquet")
    panel = pd.read_parquet(PANEL, columns=["permno", "date", "gvkey", "me"])
    panel["permno"] = pd.to_numeric(panel["permno"]).astype("int64")
    panel["date"] = pd.to_datetime(panel["date"]) + MonthEnd(0)
    out["permno"] = out["permno"].astype("int64")
    tr = pd.read_parquet(D / "sec_trans.parquet", columns=[
        "accession_number", "security_title", "trans_date", "trans_code", "trans_shares", "trans_pricepershare",
        "trans_acquired_disp_cd"])
    sub = pd.read_parquet(D / "sec_submissions.parquet", columns=[
        "accession_number", "filing_date", "document_type", "issuercik", "issuername", "issuertradingsymbol"])
    own = pd.read_parquet(D / "sec_owners.parquet", columns=[
        "accession_number", "rptownercik", "rptowner_relationship"])
    cik = pd.read_parquet(LP / "ciklink.parquet")
    cik = cik[cik["link_desc"].astype(str).str.startswith("Valid")].copy()
    cik["cik"] = cik["cik"].astype(str).str.strip().str.lstrip("0")
    cik["s"] = cik["link_start_date"].fillna(pd.Timestamp("1900-01-01"))
    cik["e"] = cik["link_end_date"].fillna(pd.Timestamp("2099-12-31"))
    cm = pd.read_parquet(D / "crsp_monthly.parquet", columns=["permno", "mthcaldt", "mthprc"])
    cm["permno"] = cm["permno"].astype("int64")
    cm["date"] = pd.to_datetime(cm["mthcaldt"]) + MonthEnd(0)
    return out, ev, panel, tr, sub, own, cik, cm


# ----------------------------------------------------------------------------
# Plain-loop recomputation (independent of the build's code)
# ----------------------------------------------------------------------------
def first_od_owner(own: pd.DataFrame, accs: set) -> dict:
    first = {}
    o = own[own["accession_number"].isin(accs)]
    for acc, ocik, rel in zip(o["accession_number"], o["rptownercik"], o["rptowner_relationship"]):
        if acc in first:
            continue
        r = (rel or "").lower()
        if "officer" in r or "director" in r:
            first[acc] = ocik
    return first


def recompute_firm(rows: pd.DataFrame, first: dict, ivals: dict, td: list, single: set) -> list:
    """rows: raw rows of the firm's CIKs (in file order). Returns insider-days as dicts."""
    acc_lvl = {}
    order = []
    for r in rows.itertuples(index=False):
        if not ((r.trans_code == "P" and r.trans_acquired_disp_cd == "A") or
                (r.trans_code == "S" and r.trans_acquired_disp_cd == "D")):
            continue
        if r.document_type not in ("4", "5"):
            continue
        if NON_COMMON.search((r.security_title or "").lower()):
            continue
        if pd.isna(r.trans_date) or pd.isna(r.filing_date):
            continue
        gap = (r.filing_date - r.trans_date).days
        if gap < 0 or gap > MAX_GAP:
            continue
        ins = first.get(r.accession_number)
        if ins is None:
            continue
        dated = any(s <= r.filing_date <= e for s, e in ivals.get(r.issuercik, []))
        if not dated and r.issuercik not in single:      # undated link allowed only for a CIK of one gvkey
            continue
        sh = 0.0 if pd.isna(r.trans_shares) else float(r.trans_shares)
        px = r.trans_pricepershare
        val = None if (pd.isna(px) or px <= 0 or pd.isna(r.trans_shares)) else float(r.trans_shares) * float(px)
        direction = "buy" if r.trans_code == "P" else "sell"
        k = (r.accession_number, ins, r.trans_date, direction)
        if k not in acc_lvl:
            acc_lvl[k] = {"sh": [], "val": [], "filing": r.filing_date}
            order.append(k)
        acc_lvl[k]["sh"].append(sh)
        if val is not None:
            acc_lvl[k]["val"].append(val)
    items = []
    for k in order:
        a = acc_lvl[k]
        items.append((a["filing"], k[0], k[1], k[2], k[3], math.fsum(a["sh"]),
                      math.fsum(a["val"]) if a["val"] else None))
    items.sort(key=lambda x: (x[0], x[1]))
    seen, days = set(), {}
    for filing, acc, ins, d, direction, sh, val in items:
        key = (ins, d, direction, sh, val)
        if key in seen:
            continue
        seen.add(key)
        pub = td[bisect_right(td, filing)]
        k = (ins, d, direction)
        if k not in days:
            days[k] = {"ins": ins, "date": d, "dir": direction, "vals": [], "pub": pub}
        if val is not None:
            days[k]["vals"].append(val)
        days[k]["pub"] = min(days[k]["pub"], pub)
    res = list(days.values())
    for x in res:
        x["val"] = math.fsum(x["vals"]) if x["vals"] else None
        x["tdx"] = bisect_left(td, x["date"])
        x["cpub"] = None
    buys = [x for x in res if x["dir"] == "buy"]
    for x in buys:
        partner_pubs = [y["pub"] for y in buys if y["ins"] != x["ins"] and abs(y["tdx"] - x["tdx"]) <= 1]
        if partner_pubs:
            x["cpub"] = max(x["pub"], min(partner_pubs))
    return res


def monthly_from_days(days: list, months: list[int]) -> dict:
    vals = {}
    for t in months:
        a = {x["ins"] for x in days if x["cpub"] is not None and t - 2 <= mi(x["cpub"]) <= t}
        b = {x["ins"] for x in days if x["dir"] == "buy" and mi(x["pub"]) == t}
        c = math.fsum(x["val"] for x in days if x["dir"] == "buy" and x["val"] is not None and t - 2 <= mi(x["pub"]) <= t)
        nb = sum(1 for x in days if x["dir"] == "buy" and t - 5 <= mi(x["pub"]) <= t)
        ns = sum(1 for x in days if x["dir"] == "sell" and t - 5 <= mi(x["pub"]) <= t)
        vals[t] = (len(a), len(b), c, (nb - ns) / (nb + ns) if nb + ns else None)
    return vals


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
    print(f"insider_cluster Step 9 validation, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    out, ev, panel, tr, sub, own, cik, cm = load()
    td = trading_days()
    p06 = out["date"] >= "2006-06-30"
    sig = ["insider_cluster", "insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]

    # ------------------------------------------------------------------ 1
    section("1. Keys and duplicates")
    same = len(out) == len(panel) and out[["permno", "date"]].merge(panel[["permno", "date"]], how="inner").shape[0] == len(panel)
    d1 = out.duplicated(["permno", "date"]).sum()
    d2 = ev.duplicated(["gvkey", "insider_cik", "period_end", "direction"]).sum()
    print(f"  monthly rows {len(out):,}, panel rows {len(panel):,}; duplicate (permno, date): {d1}; "
          f"duplicate events (firm, insider, trade day, direction): {d2}")
    record("1 keys", same and d1 == 0 and d2 == 0, "monthly file = panel rows, no duplicates in either file")

    # ------------------------------------------------------------------ 2
    section("2. Coverage")
    has = out.loc[p06, "insider_cluster"].notna().mean()
    yr = out[out["date"] >= "2006-01-31"].groupby(out["date"].dt.year)["insider_cluster"].apply(lambda s: s.notna().mean())
    print("  share of panel rows with a value (A), by year: " + ", ".join(f"{y} {v:.0%}" for y, v in yr.items()))
    blank = out[p06 & out["insider_cluster"].isna()]
    gv_links = set(cik["gvkey"])
    print(f"  blank rows from 2006-06: {len(blank):,} ({len(blank) / p06.sum():.1%}): gvkey missing "
          f"{blank['gvkey'].isna().sum():,}; gvkey without any Valid CIK link {(~blank['gvkey'].isin(gv_links) & blank['gvkey'].notna()).sum():,}; "
          f"link not dated at the month-end {(blank['gvkey'].isin(gv_links)).sum():,}")
    print(f"  ETF rows (n/a): {(out['applies'] != 'stock').sum():,}")
    record("2 coverage", has >= 0.90, f"{has:.1%} of panel rows from 2006-06 have a value (threshold 90%)")

    # ------------------------------------------------------------------ 3
    section("3. Dates and timing")
    nxt = pd.Series([td[bisect_right(td, f)] for f in ev["filing_date"]], index=ev.index)
    ok_pub = (ev["published_date"] == nxt).mean()
    gap = (ev["filing_date"] - ev["period_end"]).dt.days
    ok_gap = gap.between(0, MAX_GAP).mean()
    ok_src = (ev["date_source"] == "exact").mean()
    pos = out["insider_cluster"] > 0
    a = out[pos]
    ok_m = ((a["period_end"] <= a["published_date"]) & (a["published_date"] <= a["date"])).mean()
    ds = out["date_source"].fillna("blank")
    ok_ds = ((ds == "exact") == pos).all() and ((ds == "no event") == (out["insider_cluster"] == 0)).all() and \
            ((ds == "blank") == out["insider_cluster"].isna()).all()
    print(f"  events: public date = next trading day after filing {ok_pub:.2%}; filed 0-{MAX_GAP} days after the trade "
          f"{ok_gap:.2%}; date_source exact {ok_src:.2%}")
    print(f"  monthly A > 0 rows ({len(a):,}): period_end <= published_date <= month-end {ok_m:.2%}; "
          f"date_source matches the value: {ok_ds}")
    record("3 dates", min(ok_pub, ok_gap, ok_src, ok_m) == 1 and ok_ds,
           "every value uses only filings public by its month-end; all dates exact")

    # ------------------------------------------------------------------ 4
    section("4. Independent recomputation (plain loops, raw SEC rows)")
    cg = cik.groupby("cik")["gvkey"].nunique()
    single_cik = set(cg[cg == 1].index)
    g_ciks = cik[cik["cik"].isin(single_cik)].groupby("gvkey")["cik"].apply(set)
    g_all = cik.groupby("gvkey")["cik"].apply(set)
    simple = {g for g, s in g_ciks.items() if s == g_all.get(g)}          # every CIK of the firm links only to it
    fe = ev[ev["gvkey"].isin(simple)]
    rng = np.random.default_rng(SEED)
    pick = lambda pool, n: list(rng.choice(sorted(pool), size=min(n, len(pool)), replace=False))
    has_cl = set(fe.loc[fe["clustered"], "gvkey"])
    has_buy = set(fe.loc[fe["direction"] == "buy", "gvkey"]) - has_cl
    only_sell = set(fe["gvkey"]) - has_cl - has_buy
    named = {"170617", "160329", "117768", "184996", "001690"} & simple     # Meta, Alphabet, NVIDIA, Tesla, Apple
    sample = set(pick(has_cl, N_CLUSTER)) | set(pick(has_buy, N_BUY)) | set(pick(only_sell, N_SELL)) | named
    hand = choose_hand_firms(out, ev, simple, cm)
    sample |= {h["gvkey"] for h in hand}
    print(f"  firms whose CIKs link only to them: {len(simple):,}; sample: {len(sample)} firms "
          f"({N_CLUSTER} with clusters, {N_BUY} with buys only, {N_SELL} with sales only, + named and hand-check firms)")
    ciks_of = {g: g_all[g] for g in sample}
    allc = set().union(*ciks_of.values())
    ivals = defaultdict(list)
    for c, s, e in cik.loc[cik["cik"].isin(allc), ["cik", "s", "e"]].itertuples(index=False):
        ivals[c].append((s, e))
    s_sub = sub[sub["issuercik"].isin(allc)]
    rows = tr.merge(s_sub, on="accession_number", how="inner")
    first = first_od_owner(own, set(s_sub["accession_number"]))
    me_firm = out[["gvkey", "date", "permno"]].merge(panel[["permno", "date", "me"]], on=["permno", "date"]) \
        .groupby(["gvkey", "date"])["me"].sum(min_count=1)
    mism, compared = [], 0
    for g in sorted(sample):
        r = rows[rows["issuercik"].isin(ciks_of[g])]
        days = recompute_firm(r, first, ivals, td, single_cik)
        fg = out[(out["gvkey"] == g) & out[sig].notna().any(axis=1)]
        if fg.empty:
            continue
        months = sorted(set(mi_s(fg["date"])))
        rc = monthly_from_days(days, months)
        for row in fg.itertuples(index=False):
            t = mi(row.date)
            A, B, Cd, Dv = rc[t]
            me = me_firm.get((g, row.date))
            C = Cd / (me * 1000) if (me is not None and not pd.isna(me) and me > 0) else None
            checks = [("A", row.insider_cluster, A, 0), ("B", row.insider_buyers_1m, B, 0),
                      ("C", row.insider_buy_value_3m, C, 1e-9), ("D", row.insider_npr_6m, Dv, 1e-12)]
            for name, fv, rv, tol in checks:
                if pd.isna(fv):
                    continue
                compared += 1
                if rv is None or abs(fv - rv) > tol * max(1.0, abs(rv)):
                    mism.append((g, row.permno, row.date.date(), name, fv, rv))
    print(f"  values compared: {compared:,}; mismatches: {len(mism):,}")
    if mism:
        show(pd.DataFrame(mism[:15], columns=["gvkey", "permno", "date", "column", "file", "recomputed"]))
    record("4 recompute", compared > 0 and not mism, f"{compared:,} values in {len(sample)} firms recomputed independently")

    # ------------------------------------------------------------------ 5
    section("5. Name and CIK changes")
    meta = ev[ev["gvkey"] == "170617"]
    mrow = out[(out["permno"] == 13407) & (out["date"] >= "2012-06-30")]
    m_ok = (meta["issuercik"].nunique() == 1 and (meta["period_end"] < "2021-10-28").any()
            and (meta["period_end"] >= "2021-10-28").any() and mrow["insider_cluster"].notna().all()
            and mrow["gvkey"].nunique() == 1)
    print(f"  Meta (permno 13407, gvkey 170617, CIK 1326801; renamed 2021-10-28): events {len(meta):,} from "
          f"{meta['issuercik'].nunique()} CIK, before rename {(meta['period_end'] < '2021-10-28').sum():,}, after "
          f"{(meta['period_end'] >= '2021-10-28').sum():,}; panel months 2012-06+ {len(mrow)}, blank {mrow['insider_cluster'].isna().sum()}, "
          f"gvkeys {mrow['gvkey'].nunique()}")
    goog = ev[ev["gvkey"] == "160329"]
    old, new = goog[goog["issuercik"] == "1288776"], goog[goog["issuercik"] == "1652044"]
    gap_days = (new["filing_date"].min() - old["filing_date"].max()).days if len(old) and len(new) else None
    grow = out[(out["permno"] == 90319) & (out["date"].between("2015-01-31", "2016-12-31"))]
    g_ok = (len(old) > 0 and len(new) > 0 and gap_days is not None and gap_days <= 31 and grow["insider_cluster"].notna().all()
            and old["filing_date"].min() < pd.Timestamp("2006-02-01"))
    print(f"  Alphabet (permno 90319, gvkey 160329): Google Inc CIK 1288776 events {len(old):,} "
          f"({old['filing_date'].min():%Y-%m-%d} to {old['filing_date'].max():%Y-%m-%d}); Alphabet CIK 1652044 events "
          f"{len(new):,} (from {new['filing_date'].min():%Y-%m-%d}); days between {gap_days}; 2015-16 months blank "
          f"{grow['insider_cluster'].isna().sum()}")
    print(f"    Google Inc events before its CIK link's start date (2007-04-14), recovered by the link fix: "
          f"{(old['filing_date'] < '2007-04-14').sum():,} (first {old['filing_date'].min():%Y-%m-%d})")
    record("5 name/CIK change", m_ok and g_ok, "Meta one history across the rename; Google 2006 -> Alphabet 2025 under one gvkey")

    # ------------------------------------------------------------------ 6
    section("6. Splits: reported prices are in trade-date units")
    split_ok = True
    for name, g, permno, splits in [("NVIDIA", "117768", 86580, ["2024-06-10"]),
                                    ("Tesla", "184996", 93436, ["2020-08-31", "2022-08-25"])]:
        e = ev[(ev["gvkey"] == g) & (ev["shares"] > 0) & ev["value_usd"].notna()].copy()
        e["px"] = e["value_usd"] / e["shares"]
        e["m"] = e["period_end"] + MonthEnd(0)
        e = e.merge(cm[cm["permno"] == permno][["date", "mthprc"]], left_on="m", right_on="date", how="left")
        for sd in splits:
            sd = pd.Timestamp(sd)
            sm = sd + MonthEnd(0)
            for label, w in [("12 months before", (e["m"] < sm) & (e["m"] >= sm - MonthEnd(12))),
                             ("12 months after", (e["m"] > sm) & (e["m"] <= sm + MonthEnd(12)))]:
                x = e[w & e["mthprc"].notna()]
                ratio = x["px"] / x["mthprc"].abs()
                share = ratio.between(1 / 1.5, 1.5).mean() if len(x) else float("nan")
                print(f"  {name} split {sd:%Y-%m-%d}, {label}: insider-days {len(x)}, median price / CRSP month-end "
                      f"price {ratio.median():.2f}, within 1.5x {share:.0%}")
                split_ok &= bool(len(x) >= 5 and share >= 0.9)
    record("6 splits", split_ok, "prices match CRSP's unadjusted price on both sides of each split (>= 90% within 1.5x)")

    # ------------------------------------------------------------------ 7
    section("7. Internal consistency")
    A, B, C, Dv = (out[c] for c in sig)
    r1 = ((A.dropna() >= 0) & (A.dropna() % 1 == 0)).all() and ((B.dropna() >= 0) & (B.dropna() % 1 == 0)).all()
    r2 = (C.dropna() >= 0).all() and Dv.dropna().between(-1, 1).all()
    r3 = Dv[(A > 0) & (out["date"] >= "2006-06-30")].notna().all()      # D starts 2006-06 (6-month window)
    zc = out[(A > 0) & (C == 0)]
    print(f"  A and B whole numbers >= 0: {r1}; C >= 0 and D in [-1, 1]: {r2}; every A > 0 row from 2006-06 has D: {r3}")
    print(f"  A = 1 (a cluster partner made public outside the 3-month window): {(A == 1).sum():,} rows "
          f"({(A == 1).sum() / (A > 0).sum():.2%} of A > 0)")
    print(f"  A > 0 but C = 0 (no purchase in the window had a usable price): {len(zc):,} rows "
          f"({len(zc) / (A > 0).sum():.2%} of A > 0)")
    record("7 consistency", r1 and r2 and r3, "value ranges and A/C/D relations hold")

    # ------------------------------------------------------------------ 8
    section("8. Link fix: filings outside the CIK link's dates")
    link_gaps(tr, sub, own, cik, single_cik, ev)

    # ------------------------------------------------------------------ 9
    section("9. Outliers")
    outliers(out, ev, cm, panel)

    # ------------------------------------------------------------------ 10
    section("10. Three firms to check by hand on EDGAR")
    for h in hand:
        show_hand(h, out, ev)
    ap = out[(out["permno"] == 14593) & (out["date"] >= "2006-03-31")]
    print(f"\n  Apple (permno 14593): months with A > 0: {(ap['insider_cluster'] > 0).sum()} of {len(ap)}; "
          f"with any insider buyer (B > 0): {(ap['insider_buyers_1m'] > 0).sum()}; median D {ap['insider_npr_6m'].median():.2f} "
          f"(-1 = only sales)")
    record("10 hand check", None, "open the EDGAR links above and compare names, dates, shares and prices")

    section("Summary")
    show(pd.DataFrame(RESULTS, columns=["check", "result", "what"]))
    print(f"\n  {sum(r[1] == 'PASS' for r in RESULTS)} PASS, {sum(r[1] == 'FAIL' for r in RESULTS)} FAIL, "
          f"{sum(r[1] == 'INFO' for r in RESULTS)} INFO")
    print("\nDone. Reply 'done' in the chat; Claude will read data/issuance_insider/validate_insider_log.txt.")


# ----------------------------------------------------------------------------
def link_gaps(tr, sub, own, cik, single_cik, ev) -> None:
    x = tr[((tr["trans_code"] == "P") & (tr["trans_acquired_disp_cd"] == "A")) |
           ((tr["trans_code"] == "S") & (tr["trans_acquired_disp_cd"] == "D"))]
    x = x.merge(sub, on="accession_number")
    x = x[x["document_type"].isin(["4", "5"])]
    x = x[~x["security_title"].fillna("").str.lower().str.contains(NON_COMMON)]
    g = (x["filing_date"] - x["trans_date"]).dt.days
    x = x[g.between(0, MAX_GAP)]
    rel = own["rptowner_relationship"].fillna("").str.lower()
    odf = own[rel.str.contains("officer") | rel.str.contains("director")].drop_duplicates("accession_number")
    x = x.merge(odf[["accession_number", "rptownercik"]], on="accession_number")      # first officer/director
    pairs = x[["issuercik", "filing_date"]].drop_duplicates()
    c = pairs.merge(cik[["cik", "gvkey", "s", "e"]], left_on="issuercik", right_on="cik")
    covered = c[(c["filing_date"] >= c["s"]) & (c["filing_date"] <= c["e"])][["issuercik", "filing_date"]].drop_duplicates()
    covered["cov"] = True
    x = x.merge(covered, on=["issuercik", "filing_date"], how="left")
    linked = set(cik["cik"])
    out_dates = x[x["cov"].isna() & x["issuercik"].isin(linked)]
    rec = out_dates[out_dates["issuercik"].isin(single_cik)]
    still = out_dates[~out_dates["issuercik"].isin(single_cik)]
    nolink = x[~x["issuercik"].isin(linked)]
    one = cik[cik["cik"].isin(single_cik)].drop_duplicates("cik").set_index("cik")["gvkey"]
    rk = pd.DataFrame({"gvkey": rec["issuercik"].map(one), "insider_cik": rec["rptownercik"],
                       "period_end": rec["trans_date"],
                       "direction": np.where(rec["trans_code"] == "P", "buy", "sell")}).drop_duplicates()
    have = set(zip(ev["gvkey"], ev["insider_cik"], ev["period_end"], ev["direction"]))
    found = np.mean([k in have for k in rk.itertuples(index=False, name=None)]) if len(rk) else 1.0
    und = ev[ev["cik_link"] == "undated"]
    print(f"  rows outside every dated link, CIK linking to exactly one gvkey (recovered by the fix): {len(rec):,} "
          f"({(rec['trans_code'] == 'P').sum():,} purchases), {rec['issuercik'].nunique():,} issuers")
    print(f"  ... their insider-days (firm, insider, trade day, direction) found in the event file: {found:.2%} "
          f"of {len(rk):,}")
    print(f"  events with cik_link = undated: {len(und):,} ({(und['direction'] == 'buy').sum():,} purchases, "
          f"{und['clustered'].sum():,} clustered)")
    print(f"  still dropped - outside every dated link, CIK linking to several gvkeys (ambiguous): {len(still):,} rows "
          f"({(still['trans_code'] == 'P').sum():,} purchases), {still['issuercik'].nunique():,} issuers")
    print(f"  not linkable - issuer CIK without any Valid link: {len(nolink):,} rows "
          f"({(nolink['trans_code'] == 'P').sum():,} purchases), {nolink['issuercik'].nunique():,} issuers "
          f"(mostly firms outside CRSP/Compustat)")
    t = und.groupby("issuercik").agg(events=("direction", "size"), purchases=("direction", lambda s: (s == "buy").sum()),
                                     first=("filing_date", "min"), last=("filing_date", "max"))
    names = sub.drop_duplicates("issuercik").set_index("issuercik")["issuername"]
    t = t.join(names).sort_values("events", ascending=False).head(6).reset_index()
    print("  most undated-link events by issuer:")
    show(t[["issuername", "issuercik", "events", "purchases", "first", "last"]])
    record("8 link fix", found == 1.0, f"all {len(rk):,} recovered insider-days are in the event file" if found == 1.0
           else f"only {found:.2%} of {len(rk):,} recovered insider-days are in the event file")


def outliers(out, ev, cm, panel) -> None:
    big = out[out["insider_buy_value_3m"] > 0.10].sort_values("insider_buy_value_3m", ascending=False)
    print(f"  C above 10% of market value: {len(big):,} firm-months ({big['gvkey'].nunique():,} firms); above 100%: "
          f"{(big['insider_buy_value_3m'] > 1).sum():,}")
    buys = ev[(ev["direction"] == "buy") & ev["value_usd"].notna() & (ev["shares"] > 0)].copy()
    buys["px"] = buys["value_usd"] / buys["shares"]
    buys["m"] = buys["period_end"] + MonthEnd(0)
    rows = []
    for r in big.drop_duplicates("gvkey").head(10).itertuples(index=False):
        t0 = r.date - MonthEnd(3)
        b = buys[(buys["gvkey"] == r.gvkey) & (buys["published_date"] > t0) & (buys["published_date"] <= r.date)]
        if b.empty:
            continue
        top = b.loc[b["value_usd"].idxmax()]
        p = cm[(cm["permno"] == r.permno) & (cm["date"] == top["m"])]["mthprc"]
        crsp = abs(p.iloc[0]) if len(p) and pd.notna(p.iloc[0]) else np.nan
        rows.append((r.date.date(), r.permno, round(r.insider_buy_value_3m, 2), top["insider_name"],
                     top["period_end"].date(), f"{top['shares']:,.0f}", round(top["px"], 2), round(crsp, 2),
                     round(top["px"] / crsp, 1) if crsp == crsp else np.nan))
    print("  largest C per firm (top 10) and the purchase behind it:")
    show(pd.DataFrame(rows, columns=["month", "permno", "C", "insider", "trade", "shares", "price", "CRSP price",
                                     "price/CRSP"]))
    first = cm.groupby("permno")["date"].min()
    pfirst = out[["permno"]].drop_duplicates().assign(first=lambda d: d["permno"].map(first))
    cl = ev[ev["clustered"] & (ev["direction"] == "buy")]
    top = cl.groupby(["gvkey", "period_end"]).agg(insiders=("insider_cik", "nunique"), permno=("permno", "first"),
                                                  cik=("issuercik", "first")).reset_index()
    top = top.sort_values(["insiders", "period_end", "gvkey"], ascending=[False, True, True], kind="stable").head(10)
    top["first CRSP month"] = top["permno"].map(first)
    top["IPO month"] = top["period_end"] <= top["first CRSP month"]
    print("\n  largest same-day clusters and whether the trade is in the stock's first CRSP month:")
    show(top[["period_end", "gvkey", "permno", "insiders", "first CRSP month", "IPO month"]])
    o = out.merge(pfirst, on="permno", how="left")
    young = (o["first"] >= "2006-03-31") & (o["date"] <= o["first"] + MonthEnd(2))
    pos = o["insider_cluster"] > 0
    print(f"\n  A > 0 rows in a stock's first 3 CRSP months (stocks listed from 2006-03): {(pos & young).sum():,} "
          f"of {pos.sum():,} A > 0 rows ({(pos & young).sum() / pos.sum():.1%}); A > 0 in "
          f"{pos[young].mean():.1%} of such young-stock months vs {pos[~young & (o['date'] >= '2006-03-31')].mean():.1%} of others")
    record("9 outliers", None, f"{len(big):,} firm-months with C > 10% of market value; IPO-month share of A > 0 shown")


def choose_hand_firms(out, ev, simple, cm) -> list[dict]:
    first = cm.groupby("permno")["date"].min()
    o = out[(out["insider_cluster"] > 0) & out["gvkey"].isin(simple)].copy()
    o["first"] = o["permno"].map(first)
    o = o[o["date"] > o["first"] + MonthEnd(3)]
    me = pd.read_parquet(PANEL, columns=["permno", "date", "me"])
    me["date"] = pd.to_datetime(me["date"]) + MonthEnd(0)
    me["permno"] = pd.to_numeric(me["permno"]).astype("int64")
    o = o.merge(me, on=["permno", "date"], how="left")
    picks = []
    for label, lo, hi, how in [("large firm, financial crisis", "2008-10-31", "2009-03-31", "max"),
                               ("mid-size firm, 2016", "2016-01-31", "2016-12-31", "median"),
                               ("large firm, 2025", "2025-01-31", "2025-12-31", "max")]:
        x = o[o["date"].between(lo, hi) & ~o["gvkey"].isin([p["gvkey"] for p in picks])].dropna(subset=["me"])
        if x.empty:
            continue
        x = x.sort_values(["date", "permno"])
        r = x.loc[x["me"].idxmax()] if how == "max" else x.iloc[(x["me"] - x["me"].median()).abs().argsort().iloc[0]]
        picks.append({"label": label, "gvkey": r["gvkey"], "permno": int(r["permno"]), "date": r["date"]})
    return picks


def show_hand(h, out, ev) -> None:
    t = mi(h["date"])
    e = ev[(ev["gvkey"] == h["gvkey"]) & ev["clustered"]].copy()
    e = e[mi_s(e["cluster_public"]).between(t - 2, t)].sort_values(["period_end", "insider_name"])
    rows = out[(out["permno"] == h["permno"]) & (out["date"] >= h["date"] - MonthEnd(1)) &
               (out["date"] <= h["date"] + MonthEnd(3))]
    print(f"\n  {h['label']}: gvkey {h['gvkey']}, permno {h['permno']}, month {h['date']:%Y-%m}")
    print(f"  cluster purchases counted in A at {h['date']:%Y-%m} ({e['insider_cik'].nunique()} insiders):")
    e["price"] = (e["value_usd"] / e["shares"]).round(2)
    e["link"] = [EDGAR.format(cik=c, nodash=a.replace("-", ""), acc=a) for c, a in zip(e["issuercik"], e["accession_number"])]
    show(e[["insider_name", "relationship", "period_end", "shares", "price", "filing_date", "published_date"]].head(12))
    print("  Form 4 links (open in a browser):")
    for n, l in e[["insider_name", "link"]].drop_duplicates("link").head(12).itertuples(index=False):
        print(f"    {n}: {l}")
    print("  monthly values:")
    v = rows[["date", "insider_cluster", "insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]].copy()
    v["date"] = v["date"].dt.strftime("%Y-%m")
    show(v.round({"insider_buy_value_3m": 5, "insider_npr_6m": 3}))


if __name__ == "__main__":
    main()
