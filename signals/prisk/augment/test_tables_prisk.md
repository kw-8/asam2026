# PRisk augmentation tables (prisk)
Run 2026-11-24 22:33. Q5-Q1 EW annual, Dec formation, lab universe. Design hold years 2003-2012. Holdout only for finalists.

### DESIGN (2003-2012): candidates, Q5-Q1 EW; FM with lab controls
```
               years  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe  share of years > 0  FM ctrl slope  FM ctrl t
A1 dm4_ind      9.00       2.15        2.53        2.13         3.76          1.36    0.47                0.67           0.77       0.77
A2 dm4_o_sent   9.00       1.07        1.41        0.80         1.90          1.13    0.42                0.67           1.31       1.13
A3 sys_dm4      9.00       0.55        0.47        0.18         0.28          0.11    0.15                0.67           0.24       0.16
A4 dm4_o_np     9.00       1.12        1.13        0.67         1.61          0.77    0.33                0.56           1.38       1.30
A5 dm4_z        9.00       1.94        1.66        1.53         3.04          0.78    0.44                0.67           1.97       1.48
ref dm4 dm4     9.00       1.20        1.41        1.08         3.45          1.08    0.42                0.56           1.17       0.99
```

### Design Sharpe of all 15 trials
```
                      design Sharpe
A1                             0.47
A2                             0.42
A3                             0.15
A4                             0.33
A5                             0.44
primary prisk4 q5 EW          -0.43
VW legs                       -0.21
no size screen                -0.36
terciles                      -0.28
raw prisk                     -0.03
prisk_dm4                      0.42
prisk_dm                       0.89
FF12-neutral                  -0.27
orth NPRisk                   -0.15
orth Risk                      0.10
```

Finalists: ['A1', 'A5']. Reference dm4 design Sharpe 0.42.

### Finalists and dm4 reference by period (DSR vs all trials)
```
                     years  mean %/yr  t(mean) NW  Sharpe  alpha %/yr  t(alpha) NW  t(alpha) OLS  share of years > 0  DSR  hurdle
A1 dm4_ind  DESIGN    9.00       2.15        2.53    0.47        2.13         3.76          1.36                0.67 0.28    0.68
            HOLDOUT   9.00      -0.50       -0.54   -0.18       -1.28        -1.92         -0.60                0.33 0.01    0.68
            FULL     18.00       0.83        0.99    0.21        0.83         0.95          0.71                0.50 0.02    0.68
A5 dm4_z    DESIGN    9.00       1.94        1.66    0.44        1.53         3.04          0.78                0.67 0.28    0.68
            HOLDOUT   9.00       1.67        2.18    0.57        2.91         5.16          1.77                0.78 0.38    0.68
            FULL     18.00       1.81        2.61    0.50        1.85         3.46          1.57                0.72 0.25    0.68
ref dm4 dm4 DESIGN    9.00       1.20        1.41    0.42        1.08         3.45          1.08                0.56  NaN     NaN
            HOLDOUT   9.00       1.26        2.02    0.79        1.00         1.56          0.82                0.78  NaN     NaN
            FULL     18.00       1.23        2.31    0.55        0.61         1.14          0.82                0.67  NaN     NaN
```

### FM slope %/yr, NW t: lab controls, and + beta60
```
                     ctrl slope  ctrl t  ctrl+beta slope  ctrl+beta t
A1 dm4_ind  DESIGN         0.77    0.77             1.41         1.69
            HOLDOUT       -0.27   -0.32            -0.26        -0.23
            FULL           0.25    0.37             0.57         0.74
A5 dm4_z    DESIGN         1.97    1.48             2.34         1.89
            HOLDOUT        0.03    0.04            -0.16        -0.17
            FULL           1.00    1.12             1.09         1.16
ref dm4 dm4 DESIGN         1.17    0.99             1.95         1.94
            HOLDOUT        0.05    0.06            -0.11        -0.09
            FULL           0.61    0.77             0.92         1.04
```

### Mean monthly Spearman with vol36, me, beta60, dm4
```
pair         beta60  dm4    me  vol36
A1 dm4_ind     0.00 0.97 -0.01  -0.00
A5 dm4_z       0.00 0.91 -0.00  -0.00
ref dm4 dm4    0.01  NaN -0.00  -0.00
```
