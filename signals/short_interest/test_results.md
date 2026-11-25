# Short interest test results
Run 2026-11-24 19:27. Pre-registered in progress.md. Low-minus-high short interest (long the least shorted). Default universe (NYSE-median size, price >= $5, vol36). Design = returns to 2015-12, holdout after.

## Annual (December formation, held 12 months)

### Coverage per cohort
```
cohort       2006-12-31  2007-12-31  2008-12-31  2009-12-31  2010-12-31  2011-12-31  2012-12-31  2013-12-31  2014-12-31  2015-12-31  2016-12-31  2017-12-31  2018-12-31  2019-12-31  2020-12-31  2021-12-31  2022-12-31  2023-12-31  2024-12-31  2025-12-31
universe         824.00      811.00      689.00      766.00      790.00      755.00      783.00      805.00      811.00      813.00      842.00      834.00      791.00      796.00      864.00      866.00      808.00      889.00      864.00      849.00
with signal      806.00      793.00      676.00      755.00      780.00      744.00      776.00      798.00      804.00      807.00      836.00      827.00      786.00      794.00      861.00      863.00      807.00      888.00      862.00      848.00
cap share          0.99        0.99        0.99        0.99        0.99        0.99        0.99        0.99        0.99        0.99        0.99        0.99        1.00        1.00        1.00        1.00        1.00        1.00        1.00        1.00
```

### Mean Spearman of si_ratio with
```
                mean Spearman
pair                         
si_ratio~bm            -0.224
si_ratio~dtc            0.779
si_ratio~gprof          0.042
si_ratio~me             0.309
si_ratio~mom           -0.052
si_ratio~vol36          0.180
```

### DESIGN: p.258 screen
```
                          si_ratio
years                            9
short ZIP mean %/yr         -2.330
alpha %/yr                  -5.187
t(alpha) NW                 -8.816
t(alpha) OLS                -4.776
share of years short wins    0.333
verdict                       pass
flag                              
```

### DESIGN: si_ratio low-minus-high quintile, EW
```
                    si_ratio top-bottom q=0.20
years                                    9.000
mean %/yr                                2.330
t(mean) NW                               1.008
Sharpe                                   0.256
alpha %/yr                               5.187
t(alpha) NW                              8.816
t(alpha) OLS                             4.776
share of years > 0                       0.667
```

### DESIGN: Fama-MacBeth, si_ratio alone
```
          slope %/yr (top vs bottom rank)  t NW  t OLS  years
si_ratio                            1.072 0.452  0.314  9.000
```

### DESIGN: Fama-MacBeth with controls (avg R2 0.108)
```
          slope %/yr (top vs bottom rank)   t NW  t OLS  years
si_ratio                            1.710  0.806  0.612  9.000
vol36                               2.451  0.763  0.339  9.000
gprof                               3.472  1.044  0.997  9.000
debt_at                             0.008  0.005  0.003  9.000
ep                                  8.210  5.201  3.037  9.000
mom                                 0.292  0.058  0.043  9.000
me                                  5.604  2.535  2.581  9.000
bm                                 -6.084 -2.521 -1.991  9.000
```

### HOLDOUT: p.258 screen
```
                          si_ratio
years                           10
short ZIP mean %/yr         -5.051
alpha %/yr                   0.089
t(alpha) NW                  0.056
t(alpha) OLS                 0.036
share of years short wins    0.200
verdict                       pass
flag                              
```

### HOLDOUT: si_ratio low-minus-high quintile, EW
```
                    si_ratio top-bottom q=0.20
years                                   10.000
mean %/yr                                5.051
t(mean) NW                               1.815
Sharpe                                   0.394
alpha %/yr                              -0.089
t(alpha) NW                             -0.056
t(alpha) OLS                            -0.036
share of years > 0                       0.800
```

### HOLDOUT: Fama-MacBeth, si_ratio alone
```
          slope %/yr (top vs bottom rank)  t NW  t OLS  years
si_ratio                            4.932 1.487  1.106 10.000
```

### HOLDOUT: Fama-MacBeth with controls (avg R2 0.122)
```
          slope %/yr (top vs bottom rank)   t NW  t OLS  years
si_ratio                            6.851  2.120  2.041 10.000
vol36                              -6.791 -1.314 -1.122 10.000
gprof                               1.332  0.336  0.315 10.000
debt_at                            -1.137 -0.420 -0.315 10.000
ep                                  1.750  0.641  0.455 10.000
mom                                -0.693 -0.159 -0.121 10.000
me                                 -1.970 -0.833 -0.676 10.000
bm                                 -1.823 -0.269 -0.216 10.000
```

### Annual variants: ZIP by period
```
                                              years  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe  share of years > 0
si_ratio q5 EW (primary)             DESIGN    9.00       2.95        1.26        5.89         9.03          4.71    0.33                0.67
                                     HOLDOUT  10.00       4.54        1.64        0.73         0.88          0.36    0.37                0.80
                                     FULL     19.00       3.79        2.01        5.49         3.89          3.85    0.36                0.74
si_ratio q5 VW                       DESIGN    9.00       1.35        0.37        5.13         7.29          3.90    0.09                0.56
                                     HOLDOUT  10.00       5.08        1.25       -2.07        -1.10         -0.55    0.37                0.80
                                     FULL     19.00       3.32        1.15        4.52         1.80          1.80    0.24                0.68
si_ratio terciles                    DESIGN    9.00       0.80        0.48        3.00         5.02          1.86    0.13                0.67
                                     HOLDOUT  10.00       2.92        1.37       -0.29        -0.40         -0.21    0.32                0.60
                                     FULL     19.00       1.92        1.32        2.56         3.19          2.52    0.25                0.63
dtc q5 EW                            DESIGN    9.00       0.79        0.55       -0.83        -1.26         -0.44    0.10                0.67
                                     HOLDOUT  10.00       7.72        2.72        3.28         1.40          0.95    0.94                0.80
                                     FULL     19.00       4.44        2.08        2.64         2.16          1.42    0.51                0.74
avoid top-SI quintile vs EW universe DESIGN    9.00       0.33        1.04        0.75         8.21          5.60    0.28                0.56
                                     HOLDOUT  10.00       0.62        1.18        0.04         0.27          0.10    0.30                0.60
                                     FULL     19.00       0.48        1.49        0.74         3.64          3.33    0.29                0.58
```

## Monthly (formation every month-end, held 1 month)

### Primary (si_ratio q5 EW): annual vs monthly, by period
```
                     n  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe  share > 0
annual  DESIGN    9.00       2.95        1.26        5.89         9.03          4.71    0.33       0.67
        HOLDOUT  10.00       4.54        1.64        0.73         0.88          0.36    0.37       0.80
        FULL     19.00       3.79        2.01        5.49         3.89          3.85    0.36       0.74
monthly DESIGN  112.00       4.64        1.68        4.85         3.40          2.73    0.63       0.61
        HOLDOUT 120.00       4.53        1.39        5.58         2.61          2.72    0.45       0.55
        FULL    232.00       4.58        2.13        5.86         4.18          4.04    0.52       0.58
```

### Monthly variants: ZIP by period
```
                                              months  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe  share > 0
si_ratio q5 EW (primary)             DESIGN   112.00       4.64        1.68        4.85         3.40          2.73    0.63       0.61
                                     HOLDOUT  120.00       4.53        1.39        5.58         2.61          2.72    0.45       0.55
                                     FULL     232.00       4.58        2.13        5.86         4.18          4.04    0.52       0.58
si_ratio q5 VW                       DESIGN   112.00       3.28        0.79        4.59         1.84          2.03    0.33       0.55
                                     HOLDOUT  120.00       4.46        1.20        4.67         1.54          1.69    0.41       0.53
                                     FULL     232.00       3.89        1.40        4.87         2.23          2.73    0.37       0.54
dtc q5 EW                            DESIGN   112.00       3.71        1.73        1.98         1.01          0.96    0.53       0.62
                                     HOLDOUT  120.00       6.59        3.12        5.46         2.98          3.07    1.01       0.63
                                     FULL     232.00       5.20        3.42        4.29         2.78          2.99    0.77       0.62
avoid top-SI quintile vs EW universe DESIGN   112.00       0.65        1.64        0.64         2.72          2.28    0.60       0.61
                                     HOLDOUT  120.00       0.71        1.34        0.88         2.52          2.47    0.45       0.57
                                     FULL     232.00       0.68        2.03        0.87         3.69          3.56    0.50       0.59
```

### Monthly primary, per calendar year
```
      primary monthly ZIP, compounded % per year
date                                            
2006                                        -0.7
2007                                        14.3
2008                                        14.0
2009                                        -9.6
2010                                        -7.1
2011                                        13.7
2012                                         1.8
2013                                        -0.8
2014                                         4.5
2015                                        15.2
2016                                         2.4
2017                                         7.0
2018                                        -1.6
2019                                        -4.2
2020                                       -20.2
2021                                        25.9
2022                                        25.7
2023                                        -1.7
2024                                        10.8
2025                                         5.0
```

### Decay: low-minus-high return in month k after formation (si_ratio q5 EW, monthly cohorts, FULL)
```
          mean %/yr  t NW
month 1        4.58  2.13
month 2        3.60  1.69
month 3        3.66  1.73
month 6        3.98  2.03
month 12       2.35  1.12
```

### Deflated Sharpe (FULL), n_trials = 9
Annual primary: Sharpe 0.36/yr, hurdle 0.17, DSR 0.77. Monthly primary: Sharpe 0.149/month (0.52/yr), hurdle 0.074/month, DSR 0.87.
