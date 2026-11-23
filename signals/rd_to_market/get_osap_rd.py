"""
get_osap_rd.py
==============
Optional helper for Step 9, check 9 (signals/rd_to_market). Same pattern as
signals/issuance_insider/get_osap_shareiss.py.

Downloads Open Source Asset Pricing's firm-level RD (R&D over market cap,
Chan, Lakonishok & Sougiannis 2001; Chen & Zimmermann) so
validate_rd_to_market.py can compare it with our rdm. No WRDS login needed.

One-time install (inside the .venv):
    pip install openassetpricing
Run from the repo root:
    python signals\\rd_to_market\\get_osap_rd.py

Saves data/rd_to_market/osap_RD.parquet (permno, yyyymm, RD).
Firm-level OSAP data stays in data/ and on the shared drive, not on GitHub
(reference/wrds_guide.md). Cite: Chen & Zimmermann (2022), Open Source
Cross-Sectional Asset Pricing, Critical Finance Review.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "rd_to_market" / "osap_RD.parquet"


def main() -> None:
    try:
        import openassetpricing as oap
    except ImportError:
        raise SystemExit("openassetpricing is not installed: run  pip install openassetpricing  (inside the .venv).")
    print("Downloading RD from Open Source Asset Pricing ...")
    df = pd.DataFrame(oap.OpenAP().dl_signal("pandas", ["RD"]))
    df.columns = [str(c) for c in df.columns]
    need = {"permno", "yyyymm", "RD"}
    if not need <= set(df.columns):
        raise SystemExit(f"Unexpected columns {list(df.columns)}; show this message to Claude.")
    df = df[["permno", "yyyymm", "RD"]].dropna()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Saved {OUT.relative_to(REPO)}: {len(df):,} rows, {df['permno'].nunique():,} permnos, "
          f"{int(df['yyyymm'].min())} to {int(df['yyyymm'].max())}")
    print("Next: python signals\\rd_to_market\\validate_rd_to_market.py")


if __name__ == "__main__":
    main()
