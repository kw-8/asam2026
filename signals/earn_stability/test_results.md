# Earnings stability test results
Run 2026-11-24 01:04. Lab default: cohorts Dec 1985-Dec 2024, design hold years 1986-2005, holdout 2006-2025. higher_better=False (low std = stable = long). Default universe.

### Coverage, every 5th cohort
```
cohort       1985-12-31  1990-12-31  1995-12-31  2000-12-31  2005-12-31  2010-12-31  2015-12-31  2020-12-31  2025-12-31
universe         760.00      621.00      963.00      921.00      849.00      790.00      813.00      864.00      849.00
with signal      627.00      551.00      858.00      846.00      812.00      750.00      765.00      812.00      825.00
cap share          0.86        0.91        0.92        0.96        0.97        0.96        0.97        0.95        0.95
```

### Mean Spearman of roa_sd5 with
```
                   mean Spearman
pair                            
roa_sd5~bm                -0.226
roa_sd5~debt_at           -0.113
roa_sd5~ep                -0.430
roa_sd5~gprof              0.204
roa_sd5~gprof_sd5          0.821
roa_sd5~me                -0.344
roa_sd5~mom               -0.149
roa_sd5~vol36              0.653
```

### DESIGN: p.258 screen
```
                          roa_sd5
years                          20
short ZIP mean %/yr        -2.716
alpha %/yr                  4.125
t(alpha) NW                 1.147
t(alpha) OLS                0.625
share of years short wins   0.400
verdict                      pass
flag                             
```

### DESIGN: roa_sd5 low-minus-high quintile, EW
```
                    roa_sd5 top-bottom q=0.20
years                                  20.000
mean %/yr                               2.716
t(mean) NW                              0.777
Sharpe                                  0.114
alpha %/yr                             -4.125
t(alpha) NW                            -1.147
t(alpha) OLS                           -0.625
share of years > 0                      0.600
```

### DESIGN: FM roa_sd5 alone
```
         slope %/yr (top vs bottom rank)  t NW  t OLS  years
roa_sd5                            2.346 0.590  0.401 20.000
```

### DESIGN: FM with controls incl. vol36 (avg R2 0.118)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
roa_sd5                            1.811  0.611  0.513 20.000
vol36                             -6.403 -1.334 -1.114 20.000
gprof                              2.498  0.844  0.646 20.000
debt_at                            2.004  1.074  0.973 20.000
ep                                 8.763  2.117  2.641 20.000
mom                                7.509  2.590  2.330 20.000
me                                -1.516 -0.489 -0.578 20.000
bm                                 4.422  1.516  1.682 20.000
```

### DESIGN: FM vol36 + roa_sd5 only
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
vol36                             -3.117 -0.619 -0.527 20.000
roa_sd5                            3.483  1.176  0.903 20.000
```

### HOLDOUT: p.258 screen
```
                          roa_sd5
years                          20
short ZIP mean %/yr         1.874
alpha %/yr                  2.020
t(alpha) NW                 0.877
t(alpha) OLS                0.717
share of years short wins   0.400
verdict                      pass
flag                             
```

### HOLDOUT: roa_sd5 low-minus-high quintile, EW
```
                    roa_sd5 top-bottom q=0.20
years                                  20.000
mean %/yr                              -1.874
t(mean) NW                             -0.905
Sharpe                                 -0.132
alpha %/yr                             -2.020
t(alpha) NW                            -0.877
t(alpha) OLS                           -0.717
share of years > 0                      0.600
```

### HOLDOUT: FM roa_sd5 alone
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
roa_sd5                           -2.416 -0.989 -0.650 20.000
```

### HOLDOUT: FM with controls incl. vol36 (avg R2 0.110)
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
roa_sd5                           -0.679 -0.314 -0.318 20.000
vol36                             -0.122 -0.037 -0.029 20.000
gprof                              2.774  1.066  1.071 20.000
debt_at                            0.190  0.132  0.099 20.000
ep                                 5.733  2.513  2.220 20.000
mom                               -0.943 -0.308 -0.229 20.000
me                                 0.290  0.121  0.154 20.000
bm                                -3.318 -0.972 -0.761 20.000
```

### HOLDOUT: FM vol36 + roa_sd5 only
```
         slope %/yr (top vs bottom rank)   t NW  t OLS  years
vol36                             -0.615 -0.199 -0.143 20.000
roa_sd5                           -2.142 -1.018 -0.840 20.000
```

### Variants: low-minus-high ZIP by period
```
                                 years  mean %/yr  t(mean) NW  alpha %/yr  t(alpha) NW  t(alpha) OLS  Sharpe
roa_sd5 q5 EW           FULL     40.00       0.42        0.24       -2.61        -1.08         -0.83    0.02
                        DESIGN   20.00       2.72        0.78       -4.12        -1.15         -0.63    0.11
                        HOLDOUT  20.00      -1.87       -0.91       -2.02        -0.88         -0.72   -0.13
roa_sd5 VW              FULL     40.00      -2.47       -1.07       -6.78        -3.10         -2.76   -0.13
                        DESIGN   20.00       1.96        0.70       -6.84        -2.86         -1.45    0.10
                        HOLDOUT  20.00      -6.90       -2.25       -6.17        -2.13         -1.96   -0.40
roa_sd5 terciles        FULL     40.00      -0.08       -0.06       -1.81        -0.92         -0.74   -0.01
                        DESIGN   20.00       1.41        0.52       -2.65        -0.75         -0.51    0.08
                        HOLDOUT  20.00      -1.56       -1.01       -1.57        -0.84         -0.74   -0.14
gprof_sd5 q5 EW (check) FULL     40.00       0.19        0.12       -3.67        -2.02         -1.56    0.01
                        DESIGN   20.00       1.71        0.58       -6.12        -2.29         -1.22    0.09
                        HOLDOUT  20.00      -1.32       -0.58       -2.13        -1.28         -1.11   -0.09
vol36 q5 EW (reference) FULL     40.00      -1.87       -0.80        2.84         0.81          0.76   -0.07
                        DESIGN   20.00      -1.48       -0.30        2.71         0.59          0.38   -0.05
                        HOLDOUT  20.00      -2.26       -0.84        1.78         0.56          0.48   -0.12
```

### Deflated Sharpe (FULL)
n_trials = 4 stability variants (vol36 is a reference, not counted). Primary Sharpe 0.02/yr, hurdle 0.07, DSR 0.37.
