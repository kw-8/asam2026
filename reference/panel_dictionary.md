# Panel data dictionary

Generated from `crsp_monthly_ratios_clean.parquet` by `scripts/make_panel_dictionary.py`. Metadata only.

- Rows: 2,796,065 | permnos: 23,480 | dates: 1980-01 to 2025-12
- Firms per month: 3,568 to 7,466
- Keys: `permno` + `date` (month-end). `shrout` in thousands; `me` = prc x shrout (thousands of $).
- Accounting ratios: assumed on time (change ~2 months after quarter end).

| column | dtype | null % | min | median | max |
|---|---|---|---|---|---|
| permno | Int64 | 0.0 | 1e+04 | 6.486e+04 | 9.344e+04 |
| gvkey | string | 11.5 |  | 20,004 unique |  |
| date | datetime64[ns] | 0.0 | 1980-01-31 |  | 2025-12-31 |
| mthcaldt | datetime64[ns] | 0.0 | 1980-01-31 |  | 2025-12-31 |
| primaryexch | string | 0.0 |  | 3 unique |  |
| siccd | Int64 | 0.0 | 0 | 4841 | 9999 |
| mthret | Float64 | 0.2 | -1 | 0 | 26.58 |
| mthretx | Float64 | 0.2 | -1 | 0 | 26.58 |
| prc | Float64 | 0.1 | 0.0062 | 12.52 | 8.005e+05 |
| shrout | Int64 | 0.0 | 9 | 1.378e+04 | 2.921e+07 |
| me | Float64 | 0.1 | 10.56 | 1.309e+05 | 4.922e+09 |
| me_lag | Float64 | 1.0 | 17.19 | 1.317e+05 | 4.922e+09 |
| mthvol | Float64 | 3.4 | 0 | 9.571e+05 | 2.28e+10 |
| vol_adj | Float64 | 3.4 | 0 | 7.233e+05 | 2.28e+10 |
| dvol | Float64 | 3.4 | 0 | 6.902e+06 | 1.09e+12 |
| turnover | float64 | 3.4 | 5.817e-06 | 0.05014 | 24.96 |
| bm | float32 | 16.1 | 0.01283 | 0.5769 | 9.959 |
| pe_exi | float32 | 17.7 | -2.311e+04 | 10.78 | 1061 |
| ptb | float32 | 16.1 | 0.04739 | 1.712 | 107.6 |
| ps | float32 | 15.7 | 0.009625 | 1.122 | 2040 |
| pcf | float32 | 15.0 | -836 | 6.215 | 609.6 |
| evm | float32 | 14.4 | -3.088e+18 | 7.967 | 2.522e+18 |
| divyield | float32 | 15.0 | 0 | 0 | 0.1548 |
| roe | float32 | 18.0 | -10.32 | 0.07767 | 89.43 |
| roa | float32 | 15.2 | -2.614 | 0.08922 | 0.5427 |
| gpm | float32 | 15.9 | -155.4 | 0.3474 | 1.01 |
| npm | float32 | 15.7 | -460.3 | 0.03575 | 0.6784 |
| opmbd | float32 | 15.7 | -430.4 | 0.1115 | 0.739 |
| gprof | float32 | 14.1 | -1.202 | 0.2587 | 1.372 |
| de_ratio | float32 | 13.8 | -33.68 | 1.116 | 44.64 |
| debt_at | float32 | 14.1 | 0 | 0.1843 | 1.564 |
| intcov | float32 | 32.5 | -9613 | 2.339 | 2694 |
| curr_ratio | float32 | 27.6 | 0.1275 | 2.05 | 43.15 |
| quick_ratio | float32 | 27.6 | 0.08468 | 1.407 | 43.15 |
| cash_ratio | float32 | 27.3 | 0 | 0.4261 | 37.97 |
| at_turn | float32 | 16.7 | 0.001288 | 0.8598 | 5.58 |
| accrual | float32 | 14.9 | -1.372 | -0.03766 | 0.5232 |
| rect_turn | float32 | 18.6 | 0.02839 | 5.979 | 256.4 |
| ep | float32 | 17.7 | -38.46 | 0.03762 | 2.142 |
| cfp | float32 | 15.0 | -8.053 | 0.06328 | 5.866 |
| ebitda_ev | float32 | 14.5 | -2.609 | 0.08528 | 1.523 |
| sp | float32 | 15.7 | 0.0005584 | 0.8912 | 81.06 |
