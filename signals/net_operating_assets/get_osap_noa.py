"""
get_osap_noa.py
===============
Optional helper for Step 9, check 9 (signals/net_operating_assets). Same pattern as
signals/rd_to_market/get_osap_rd.py.

Downloads Open Source Asset Pricing's firm-level NOA and dNoa (net operating assets
and their change, Hirshleifer, Hou, Teoh & Zhang 2004; Chen & Zimmermann) so
validate_net_operating_assets.py can compare them with our noa and dnoa.
No WRDS login needed.

One-time install (inside the .venv; already there if you ran get_osap_rd.py):
    pip install openassetpricing
Run from the repo root:
    python signals\\net_operating_assets\\get_osap_noa.py

Saves data/net_operating_assets/osap_NOA.parquet (permno, yyyymm, NOA, dNoa).
Firm-level OSAP data stays in data/ and on the shared drive, not on GitHub
(reference/wrds_guide.md). Cite: Chen & Zimmermann (2022), Open Source
Cross-Sectional Asset Pricing, Critical Finance Review.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "net_operating_assets" / "osap_NOA.parquet"
SIGNALS = ["NOA", "dNoa"]


def main() -> None:
    try:
        import openassetpricing as oap
    except ImportError:
        raise SystemExit("openassetpricing is not installed: run  pip install openassetpricing  (inside the .venv).")
    print(f"Downloading {', '.join(SIGNALS)} from Open Source Asset Pricing ...")
    df = pd.DataFrame(oap.OpenAP().dl_signal("pandas", SIGNALS))
    df.columns = [str(c) for c in df.columns]
    need = {"permno", "yyyymm", *SIGNALS}
    if not need <= set(df.columns):
        raise SystemExit(f"Unexpected columns {list(df.columns)}; show this message to Claude.")
    df = df[["permno", "yyyymm"] + SIGNALS].dropna(how="all", subset=SIGNALS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Saved {OUT.relative_to(REPO)}: {len(df):,} rows, {df['permno'].nunique():,} permnos, "
          f"{int(df['yyyymm'].min())} to {int(df['yyyymm'].max())}")
    print("Next: python signals\\net_operating_assets\\validate_net_operating_assets.py")


if __name__ == "__main__":
    main()
