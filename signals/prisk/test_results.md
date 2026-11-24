# PRisk test results
Run 2026-11-24 01:03. Cohorts Dec 2002-Dec 2020; design hold years 2003-2012, holdout 2013-2021. Annual top-minus-bottom ZIPs; alpha on mktrf/smb/hml/umd, NW t. Default universe (NYSE median size, price >= $5, vol36). Ranks among stocks with the signal.

### Coverage per cohort (universe stocks, with prisk4, their cap share)
```
cohort       2002-12-31  2003-12-31  2004-12-31  2005-12-31  2006-12-31  2007-12-31  2008-12-31  2009-12-31  2010-12-31  2011-12-31  2012-12-31  2013-12-31  2014-12-31  2015-12-31  2016-12-31  2017-12-31  2018-12-31  2019-12-31  2020-12-31  2021-12-31  2022-12-31  2023-12-31  2024-12-31  2025-12-31
universe         823.00      884.00      879.00      849.00      824.00      811.00      689.00      766.00      790.00      755.00      783.00      805.00      811.00      813.00      842.00      834.00      791.00      796.00      864.00      866.00      808.00      889.00      864.00      849.00
with signal      415.00      685.00      699.00      698.00      704.00      704.00      619.00      682.00      708.00      685.00      717.00      738.00      743.00      756.00      788.00      785.00      747.00      750.00      811.00        0.00        0.00        0.00        0.00        0.00
cap share          0.71        0.83        0.85        0.88        0.89        0.91        0.93        0.93        0.93        0.94        0.94        0.94        0.92        0.94        0.94        0.94        0.93        0.94        0.95        0.00        0.00        0.00        0.00        0.00
```

### Mean Spearman of prisk4 with
```
                mean Spearman
pair                         
prisk4~bm               0.052
prisk4~gprof           -0.194
prisk4~me               0.043
prisk4~mom             -0.026
prisk4~nprisk4          0.425
prisk4~risk4            0.708
prisk4~roa_sd5         -0.032
prisk4~vol36           -0.044
```

### DESIGN: p.258 screen (short ZIP = bottom minus top)
```
                                                        prisk4
years                                                       10
short ZIP mean %/yr                                      3.404
alpha %/yr                                               2.400
t(alpha) NW                                              5.267
t(alpha) OLS                                             1.499
share of years short wins                                0.700
verdict                                                   FAIL
flag                       short side wins most years (rule B)
```

### DESIGN: prisk4 top-minus-bottom quintile, EW
```
                    prisk4 top-bottom q=0.20
years                                 10.000
mean %/yr                             -3.404
t(mean) NW                            -1.402
Sharpe                                -0.425
alpha %/yr                            -2.400
t(alpha) NW                           -5.267
t(alpha) OLS                          -1.499
share of years > 0                     0.300
```

### DESIGN: Fama-MacBeth, prisk4 alone
```
        slope %/yr (top vs bottom rank)   t NW  t OLS  years
prisk4                           -3.161 -1.064 -0.980 10.000
```

### DESIGN: Fama-MacBeth with controls (avg R2 0.121)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
prisk4                            -0.944 -0.470 -0.392 10.000
vol36                             -5.394 -1.017 -0.720 10.000
gprof                              3.339  0.976  0.990 10.000
debt_at                           -0.416 -0.260 -0.197 10.000
ep                                11.403  5.440  4.107 10.000
mom                               -1.924 -0.498 -0.308 10.000
me                                 4.664  2.281  2.174 10.000
bm                                -0.524 -0.139 -0.147 10.000
```

### HOLDOUT: p.258 screen (short ZIP = bottom minus top)
```
                          prisk4
years                          9
short ZIP mean %/yr       -0.711
alpha %/yr                 0.501
t(alpha) NW                1.136
t(alpha) OLS               0.282
share of years short wins  0.333
verdict                     pass
flag                            
```

### HOLDOUT: prisk4 top-minus-bottom quintile, EW
```
                    prisk4 top-bottom q=0.20
years                                  9.000
mean %/yr                              0.711
t(mean) NW                             0.465
Sharpe                                 0.114
alpha %/yr                            -0.501
t(alpha) NW                           -1.136
t(alpha) OLS                          -0.282
share of years > 0                     0.667
```

### HOLDOUT: Fama-MacBeth, prisk4 alone
```
        slope %/yr (top vs bottom rank)  t NW  t OLS  years
prisk4                            0.988 0.579  0.436  9.000
```

### HOLDOUT: Fama-MacBeth with controls (avg R2 0.100)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
prisk4                             1.600  2.041  1.330  9.000
vol36                             -0.809 -0.123 -0.130  9.000
gprof                              3.430  2.379  1.336  9.000
debt_at                            3.348  2.025  1.117  9.000
ep                                 2.905  0.950  0.685  9.000
mom                                0.294  0.105  0.074  9.000
me                                -1.231 -0.446 -0.458  9.000
bm                                -6.604 -1.096 -0.791  9.000
```

### Variants: top-minus-bottom ZIP by period
```
                              DESIGN                                                                        FULL                                                                      HOLDOUT                                                                     
                              Sharpe alpha %/yr mean %/yr share of years > 0 t(alpha) NW t(mean) NW years Sharpe alpha %/yr mean %/yr share of years > 0 t(alpha) NW t(mean) NW years  Sharpe alpha %/yr mean %/yr share of years > 0 t(alpha) NW t(mean) NW years
primary prisk4 q5 EW           -0.43      -2.40     -3.40               0.30       -5.27      -1.40 10.00  -0.20      -1.18     -1.45               0.47       -1.89      -0.88 19.00    0.11      -0.50      0.71               0.67       -1.14       0.47  9.00
VW legs                        -0.21      -0.24     -0.88               0.40       -0.32      -1.08 10.00  -0.12      -0.59     -1.03               0.47       -0.38      -0.74 19.00   -0.10      -4.51     -1.19               0.56       -1.53      -0.44  9.00
no size screen                 -0.36      -1.80     -3.25               0.40       -4.39      -1.33 10.00  -0.05      -0.01     -0.35               0.58       -0.01      -0.19 19.00    0.61       1.48      2.87               0.78        1.60       2.54  9.00
terciles                       -0.28      -0.99     -1.89               0.40       -2.57      -0.91 10.00  -0.09      -0.66     -0.53               0.58       -1.17      -0.40 19.00    0.21      -0.87      0.97               0.78       -3.23       0.81  9.00
raw prisk (last call)          -0.03      -0.97     -0.18               0.70       -4.19      -0.12 10.00   0.08       0.08      0.38               0.58        0.13       0.39 19.00    0.22       0.98      1.00               0.44        1.57       0.95  9.00
prisk_dm4 (vs own past)         0.42       1.08      1.20               0.56        3.45       1.41  9.00   0.55       0.61      1.23               0.67        1.14       2.31 18.00    0.79       1.00      1.26               0.78        1.56       2.02  9.00
prisk_dm (last call vs past)    0.89       1.82      2.49               0.67        4.98       3.40  9.00   0.32       0.97      1.12               0.61        1.47       1.38 18.00   -0.07      -0.13     -0.25               0.56       -0.09      -0.33  9.00
FF12-neutral rank              -0.27       0.46     -1.47               0.50        0.98      -0.85 10.00  -0.22      -0.54     -1.08               0.47       -0.57      -1.04 19.00   -0.15      -3.15     -0.65               0.44       -2.34      -0.63  9.00
orth to NPRisk                 -0.15      -0.55     -1.42               0.50       -0.70      -0.59 10.00  -0.10      -0.34     -0.76               0.47       -0.44      -0.57 19.00   -0.01      -1.58     -0.03               0.44       -1.51      -0.04  9.00
orth to Risk (all risk words)   0.10       1.15      0.75               0.70        1.21       0.35 10.00   0.17       1.79      1.08               0.68        2.04       0.89 19.00    0.29       1.60      1.44               0.67        1.28       1.67  9.00
```

### Primary ZIP by subperiod (hold years)
```
                    years  mean %/yr  t(mean) NW  Sharpe  alpha %/yr         t(alpha) NW  t(alpha) OLS  share of years > 0
all                 19.00      -1.45       -0.88   -0.20       -1.18               -1.89         -0.92                0.47
excl 2008-09        17.00      -0.60       -0.51   -0.10       -1.02               -1.28         -0.74                0.47
excl 2020           18.00      -0.76       -0.43   -0.11       -1.19               -1.91         -0.89                0.50
excl 2008-09, 2020  16.00       0.23        0.20    0.05       -0.89               -1.10         -0.62                0.50
2003-2007            5.00      -0.55       -0.45   -0.16       -1.43 -421490199870198.69         -0.00                0.40
2010-2019           10.00      -0.06       -0.04   -0.01       -1.87               -1.42         -0.94                0.50
```

### Primary ZIP per hold year (%)
```
      prisk4 ZIP %
2003          -5.9
2004          -0.0
2005           3.5
2006           1.0
2007          -1.3
2008           4.1
2009         -21.6
2010         -12.6
2011          -0.3
2012          -0.9
2013           1.9
2014           6.0
2015          -0.6
2016           0.5
2017           5.5
2018          -0.2
2019           0.1
2020         -13.9
2021           7.1
```

### Deflated Sharpe (FULL, annual)
n_trials = 10 PRisk variants. Primary Sharpe -0.20/yr, hurdle SR0 0.39, DSR 0.00 (p.247: with many tries one t of 2 is expected by chance).

### Joint FM 2003-2021 hold years: PRisk+NPRisk+vol36+roa_sd5 (avg R2 0.050)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
prisk4                            -1.451 -0.842 -0.733 19.000
nprisk4                            0.690  0.675  0.487 19.000
vol36                             -2.086 -0.562 -0.442 19.000
roa_sd5                           -2.106 -0.943 -0.834 19.000
```

### Joint FM 2003-2021 hold years: + controls (avg R2 0.117)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
prisk4                            -0.529 -0.449 -0.341 19.000
nprisk4                            0.539  0.485  0.452 19.000
vol36                             -2.479 -0.585 -0.557 19.000
roa_sd5                           -0.213 -0.093 -0.100 19.000
gprof                              4.234  2.088  1.819 19.000
debt_at                            1.494  1.069  0.812 19.000
ep                                 7.670  2.721  2.861 19.000
mom                               -1.488 -0.587 -0.405 19.000
me                                 2.010  0.931  1.102 19.000
bm                                -3.093 -0.844 -0.725 19.000
```

### Joint FM 2003-2021 hold years: vol36 + roa_sd5 only (avg R2 0.042)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
vol36                             -1.857 -0.497 -0.394 19.000
roa_sd5                           -1.781 -0.751 -0.693 19.000
```

### Joint FM 2003-2021 hold years: roa_sd5 alone (avg R2 0.017)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
roa_sd5                           -2.727 -0.996 -0.719 19.000
```

### Joint FM 2003-2021 hold years: vol36 alone (avg R2 0.036)
```
       slope %/yr (top vs bottom rank)   t NW  t OLS  years
vol36                           -2.993 -0.765 -0.571 19.000
```

### prisk4 quintile mean annual return % (Q5 = highest PRisk)
```
port      Q1   Q2   Q3   Q4   Q5
DESIGN  14.2 12.3 13.4 12.4 10.8
HOLDOUT 16.4 16.6 15.4 16.8 17.1
```
