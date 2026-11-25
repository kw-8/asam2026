# EPU beta test results
Run 2026-11-24 19:49. Cohorts Dec 1988-Dec 2024, design hold years 1989-2005, holdout 2006-2025. higher_better=False (low beta = long). Default universe. Controls: lab set + mkt_beta60.

## epu_beta

### Coverage, every 4th cohort
```
cohort       1988-12-31  1992-12-31  1996-12-31  2000-12-31  2004-12-31  2008-12-31  2012-12-31  2016-12-31  2020-12-31  2024-12-31
universe         681.00      742.00     1007.00      921.00      879.00      689.00      783.00      842.00      864.00      864.00
with signal      655.00      729.00      965.00      881.00      865.00      672.00      768.00      819.00      828.00      850.00
cap share          0.98        0.99        0.99        0.98        0.99        0.99        0.99        0.98        0.98        1.00
```

### Mean Spearman of epu_beta with
```
                          mean Spearman
pair                                   
epu_beta~bm                      -0.021
epu_beta~epu_natsec_beta          0.411
epu_beta~epu_trade_beta           0.206
epu_beta~me                       0.093
epu_beta~mkt_beta60               0.096
epu_beta~mom                      0.010
epu_beta~vol36                   -0.105
```

### DESIGN: p.258 screen
```
                                                      epu_beta
years                                                       17
short ZIP mean %/yr                                      0.016
alpha %/yr                                               5.592
t(alpha) NW                                              1.479
t(alpha) OLS                                             1.311
share of years short wins                                0.588
verdict                                                   pass
flag                       short side wins most years (rule B)
```

### DESIGN: low-minus-high quintile, EW
```
                    epu_beta top-bottom q=0.20
years                                   17.000
mean %/yr                               -0.016
t(mean) NW                              -0.009
Sharpe                                  -0.002
alpha %/yr                              -5.592
t(alpha) NW                             -1.479
t(alpha) OLS                            -1.311
share of years > 0                       0.412
```

### DESIGN: FM alone
```
          slope %/yr (top vs bottom rank)  t NW  t OLS  years
epu_beta                            0.088 0.037  0.028 17.000
```

### DESIGN: FM with controls (avg R2 0.124)
```
            slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_beta                              0.107  0.054  0.048 17.000
vol36                                -8.394 -1.971 -1.610 17.000
gprof                                -1.066 -0.413 -0.240 17.000
debt_at                               3.443  2.077  1.767 17.000
ep                                   11.249  2.968  3.332 17.000
mom                                   8.136  2.078  2.041 17.000
me                                   -1.559 -0.454 -0.549 17.000
bm                                    1.950  0.546  0.647 17.000
mkt_beta60                            0.039  0.013  0.010 17.000
```

### HOLDOUT: p.258 screen
```
                                                      epu_beta
years                                                       20
short ZIP mean %/yr                                     -0.748
alpha %/yr                                              -0.158
t(alpha) NW                                             -0.107
t(alpha) OLS                                            -0.060
share of years short wins                                0.600
verdict                                                   pass
flag                       short side wins most years (rule B)
```

### HOLDOUT: low-minus-high quintile, EW
```
                    epu_beta top-bottom q=0.20
years                                   20.000
mean %/yr                                0.748
t(mean) NW                               0.330
Sharpe                                   0.070
alpha %/yr                               0.158
t(alpha) NW                              0.107
t(alpha) OLS                             0.060
share of years > 0                       0.400
```

### HOLDOUT: FM alone
```
          slope %/yr (top vs bottom rank)  t NW  t OLS  years
epu_beta                            0.756 0.291  0.271 20.000
```

### HOLDOUT: FM with controls (avg R2 0.128)
```
            slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_beta                             -1.272 -0.506 -0.504 20.000
vol36                                 0.338  0.111  0.084 20.000
gprof                                 3.146  1.179  1.221 20.000
debt_at                              -0.251 -0.177 -0.131 20.000
ep                                    5.273  2.602  2.340 20.000
mom                                   0.902  0.369  0.275 20.000
me                                    0.528  0.236  0.304 20.000
bm                                   -2.419 -0.798 -0.609 20.000
mkt_beta60                           -2.096 -0.750 -0.499 20.000
```

## epu_trade_beta

### Coverage, every 4th cohort
```
cohort       1988-12-31  1992-12-31  1996-12-31  2000-12-31  2004-12-31  2008-12-31  2012-12-31  2016-12-31  2020-12-31  2024-12-31
universe         681.00      742.00     1007.00      921.00      879.00      689.00      783.00      842.00      864.00      864.00
with signal      655.00      729.00      965.00      881.00      865.00      672.00      768.00      819.00      828.00      850.00
cap share          0.98        0.99        0.99        0.98        0.99        0.99        0.99        0.98        0.98        1.00
```

### Mean Spearman of epu_trade_beta with
```
                                mean Spearman
pair                                         
epu_trade_beta~bm                      -0.013
epu_trade_beta~epu_beta                 0.206
epu_trade_beta~epu_natsec_beta          0.190
epu_trade_beta~me                       0.050
epu_trade_beta~mkt_beta60              -0.009
epu_trade_beta~mom                      0.015
epu_trade_beta~vol36                   -0.083
```

### DESIGN: p.258 screen
```
                                                epu_trade_beta
years                                                       17
short ZIP mean %/yr                                      3.931
alpha %/yr                                               6.173
t(alpha) NW                                              1.585
t(alpha) OLS                                             1.198
share of years short wins                                0.647
verdict                                                   pass
flag                       short side wins most years (rule B)
```

### DESIGN: low-minus-high quintile, EW
```
                    epu_trade_beta top-bottom q=0.20
years                                         17.000
mean %/yr                                     -3.931
t(mean) NW                                    -1.659
Sharpe                                        -0.390
alpha %/yr                                    -6.173
t(alpha) NW                                   -1.585
t(alpha) OLS                                  -1.198
share of years > 0                             0.353
```

### DESIGN: FM alone
```
                slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_trade_beta                           -4.172 -1.491 -1.494 17.000
```

### DESIGN: FM with controls (avg R2 0.124)
```
                slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_trade_beta                           -3.140 -1.402 -1.539 17.000
vol36                                    -7.775 -1.663 -1.377 17.000
gprof                                    -0.921 -0.353 -0.206 17.000
debt_at                                   3.151  1.913  1.598 17.000
ep                                       10.976  2.921  3.283 17.000
mom                                       8.029  2.083  2.065 17.000
me                                       -1.278 -0.376 -0.449 17.000
bm                                        2.320  0.657  0.779 17.000
mkt_beta60                               -0.019 -0.007 -0.005 17.000
```

### HOLDOUT: p.258 screen
```
                          epu_trade_beta
years                                 20
short ZIP mean %/yr               -0.114
alpha %/yr                         0.936
t(alpha) NW                        0.539
t(alpha) OLS                       0.463
share of years short wins          0.450
verdict                             pass
flag                                    
```

### HOLDOUT: low-minus-high quintile, EW
```
                    epu_trade_beta top-bottom q=0.20
years                                         20.000
mean %/yr                                      0.114
t(mean) NW                                     0.073
Sharpe                                         0.011
alpha %/yr                                    -0.936
t(alpha) NW                                   -0.539
t(alpha) OLS                                  -0.463
share of years > 0                             0.550
```

### HOLDOUT: FM alone
```
                slope %/yr (top vs bottom rank)  t NW  t OLS  years
epu_trade_beta                            0.556 0.284  0.203 20.000
```

### HOLDOUT: FM with controls (avg R2 0.123)
```
                slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_trade_beta                           -0.726 -0.497 -0.429 20.000
vol36                                     0.258  0.089  0.066 20.000
gprof                                     3.054  1.137  1.148 20.000
debt_at                                   0.037  0.026  0.020 20.000
ep                                        5.395  2.657  2.349 20.000
mom                                       0.950  0.401  0.296 20.000
me                                        0.200  0.088  0.110 20.000
bm                                       -2.747 -0.912 -0.690 20.000
mkt_beta60                               -2.212 -0.817 -0.545 20.000
```

## epu_natsec_beta

### Coverage, every 4th cohort
```
cohort       1988-12-31  1992-12-31  1996-12-31  2000-12-31  2004-12-31  2008-12-31  2012-12-31  2016-12-31  2020-12-31  2024-12-31
universe         681.00      742.00     1007.00      921.00      879.00      689.00      783.00      842.00      864.00      864.00
with signal      655.00      729.00      965.00      881.00      865.00      672.00      768.00      819.00      828.00      850.00
cap share          0.98        0.99        0.99        0.98        0.99        0.99        0.99        0.98        0.98        1.00
```

### Mean Spearman of epu_natsec_beta with
```
                                mean Spearman
pair                                         
epu_natsec_beta~bm                     -0.012
epu_natsec_beta~epu_beta                0.411
epu_natsec_beta~epu_trade_beta          0.190
epu_natsec_beta~me                      0.034
epu_natsec_beta~mkt_beta60              0.061
epu_natsec_beta~mom                    -0.004
epu_natsec_beta~vol36                  -0.032
```

### DESIGN: p.258 screen
```
                          epu_natsec_beta
years                                  17
short ZIP mean %/yr                 0.552
alpha %/yr                          1.292
t(alpha) NW                         0.294
t(alpha) OLS                        0.238
share of years short wins           0.412
verdict                              pass
flag                                     
```

### DESIGN: low-minus-high quintile, EW
```
                    epu_natsec_beta top-bottom q=0.20
years                                          17.000
mean %/yr                                      -0.552
t(mean) NW                                     -0.210
Sharpe                                         -0.035
alpha %/yr                                     -1.292
t(alpha) NW                                    -0.294
t(alpha) OLS                                   -0.238
share of years > 0                              0.588
```

### DESIGN: FM alone
```
                 slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_natsec_beta                           -0.537 -0.205 -0.137 17.000
```

### DESIGN: FM with controls (avg R2 0.124)
```
                 slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_natsec_beta                           -0.748 -0.303 -0.247 17.000
vol36                                     -7.757 -1.690 -1.393 17.000
gprof                                     -1.018 -0.406 -0.232 17.000
debt_at                                    3.217  2.026  1.712 17.000
ep                                        11.519  3.064  3.509 17.000
mom                                        7.778  1.985  2.068 17.000
me                                        -1.808 -0.514 -0.615 17.000
bm                                         2.030  0.590  0.691 17.000
mkt_beta60                                -0.817 -0.292 -0.225 17.000
```

### HOLDOUT: p.258 screen
```
                                               epu_natsec_beta
years                                                       20
short ZIP mean %/yr                                      1.611
alpha %/yr                                               0.577
t(alpha) NW                                              0.657
t(alpha) OLS                                             0.261
share of years short wins                                0.600
verdict                                                   pass
flag                       short side wins most years (rule B)
```

### HOLDOUT: low-minus-high quintile, EW
```
                    epu_natsec_beta top-bottom q=0.20
years                                          20.000
mean %/yr                                      -1.611
t(mean) NW                                     -0.733
Sharpe                                         -0.166
alpha %/yr                                     -0.577
t(alpha) NW                                    -0.657
t(alpha) OLS                                   -0.261
share of years > 0                              0.400
```

### HOLDOUT: FM alone
```
                 slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_natsec_beta                           -1.538 -0.674 -0.636 20.000
```

### HOLDOUT: FM with controls (avg R2 0.123)
```
                 slope %/yr (top vs bottom rank)   t NW  t OLS  years
epu_natsec_beta                           -1.622 -0.772 -0.869 20.000
vol36                                      0.568  0.203  0.149 20.000
gprof                                      2.709  1.032  1.017 20.000
debt_at                                    0.314  0.222  0.166 20.000
ep                                         5.536  2.711  2.394 20.000
mom                                        0.936  0.381  0.286 20.000
me                                         0.376  0.172  0.212 20.000
bm                                        -2.910 -0.964 -0.723 20.000
mkt_beta60                                -2.069 -0.748 -0.494 20.000
```

### Variants: low-minus-high ZIP by period
```
                                      years  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe
epu_beta q5 EW               FULL     37.00       0.40        0.31       -0.69        -0.44         -0.34    0.04
                             DESIGN   17.00      -0.02       -0.01       -5.59        -1.48         -1.31   -0.00
                             HOLDOUT  20.00       0.75        0.33        0.16         0.11          0.06    0.07
epu_trade_beta q5 EW         FULL     37.00      -1.74       -1.13       -1.32        -0.72         -0.58   -0.17
                             DESIGN   17.00      -3.93       -1.66       -6.17        -1.59         -1.20   -0.39
                             HOLDOUT  20.00       0.11        0.07       -0.94        -0.54         -0.46    0.01
epu_natsec_beta q5 EW        FULL     37.00      -1.12       -0.67       -1.07        -0.51         -0.36   -0.09
                             DESIGN   17.00      -0.55       -0.21       -1.29        -0.29         -0.24   -0.03
                             HOLDOUT  20.00      -1.61       -0.73       -0.58        -0.66         -0.26   -0.17
epu_beta VW                  FULL     37.00       2.33        0.89        1.06         0.37          0.36    0.15
                             DESIGN   17.00       2.58        0.89       -5.72        -1.17         -1.00    0.18
                             HOLDOUT  20.00       2.12        0.47        2.84         1.41          0.74    0.12
epu_trade_beta VW            FULL     37.00      -0.32       -0.11        1.57         0.42          0.41   -0.02
                             DESIGN   17.00      -5.48       -1.40       -5.62        -0.96         -0.75   -0.35
                             HOLDOUT  20.00       4.06        1.54        2.23         0.55          0.53    0.24
epu_natsec_beta VW           FULL     37.00       0.34        0.13       -0.96        -0.30         -0.28    0.02
                             DESIGN   17.00       1.21        0.43       -6.85        -1.11         -1.00    0.08
                             HOLDOUT  20.00      -0.39       -0.10        0.35         0.17          0.09   -0.03
epu_beta terciles            FULL     37.00       0.13        0.12       -1.14        -0.88         -0.67    0.01
                             DESIGN   17.00      -0.26       -0.15       -4.02        -1.16         -0.96   -0.03
                             HOLDOUT  20.00       0.46        0.28       -0.42        -0.35         -0.20    0.06
epu_beta36 q5 EW             FULL     37.00       1.96        1.50        1.11         0.55          0.53    0.19
                             DESIGN   17.00       1.60        0.76       -3.04        -0.78         -0.69    0.15
                             HOLDOUT  20.00       2.28        1.11        2.29         1.24          0.82    0.23
mkt_beta60 q5 EW (reference) FULL     37.00      -2.21       -0.93        2.91         0.69          0.74   -0.10
                             DESIGN   17.00      -1.92       -0.37        6.80         1.32          0.83   -0.07
                             HOLDOUT  20.00      -2.46       -0.87        0.49         0.17          0.16   -0.13
```

### Deflated Sharpe (FULL)
n_trials = 8 EPU variants (mkt_beta60 is a reference, not counted). Primary epu_beta Sharpe 0.04/yr, hurdle 0.17, DSR 0.21. Best: epu_beta36 q5 EW 0.19.
