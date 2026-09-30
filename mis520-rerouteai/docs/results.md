# ReRouteAI - evaluation results

Delay data: **synthetic BTS-format data (stand-in)**. Regenerate with `python evaluate.py`. If the source says synthetic, these numbers only prove the pipeline works; re-run on real BTS files before presenting them as results.

## 1. Delay model (train Jan-Sep, test Oct-Dec)

Test flights: 62,741; late (>= 15 min) or cancelled: 23.7%.

| Metric | Gradient boosting | Baseline |
|---|---|---|
| PR-AUC (late >= 15 min) | 0.326 | hour-of-day lookup 0.314; no skill 0.237 |
| Brier score (lower is better) | 0.1757 | hour-of-day lookup 0.1766 |
| Log loss, 11 delay buckets | 1.4317 | climatology 1.4419 |

Calibration (deciles of predicted P(late)):

| predicted | actual |
|---|---|
| 0.146 | 0.134 |
| 0.172 | 0.160 |
| 0.194 | 0.177 |
| 0.211 | 0.197 |
| 0.227 | 0.218 |
| 0.246 | 0.244 |
| 0.270 | 0.253 |
| 0.298 | 0.287 |
| 0.333 | 0.310 |
| 0.404 | 0.393 |

## 2. Decision quality - simulated disruptions (airline cases, model is right)

Traveller cases: fares paid + value of time + connections. Airline cases: rebooking + EU261 + care + goodwill. Each strategy is replayed with delays sampled leg by leg.

| strategy | cost | delay_h | within_3h | failed | cost_vs_ReRouteAI_$ |
|---|---|---|---|---|---|
| Earliest arrival | 578.576 | 3.936 | 0.525 | 0.022 | 6.102 |
| Lowest fare | 915.066 | 5.733 | 0.000 | 0.091 | 342.592 |
| Next direct, same carrier | 981.071 | 6.304 | 0.000 | 0.027 | 408.597 |
| ReRouteAI | 572.474 | 5.438 | 0.549 | 0.025 | 0.000 |

## 2. Decision quality - simulated disruptions (traveller cases, model is right)

Traveller cases: fares paid + value of time + connections. Airline cases: rebooking + EU261 + care + goodwill. Each strategy is replayed with delays sampled leg by leg.

| strategy | cost | delay_h | within_3h | failed | cost_vs_ReRouteAI_$ |
|---|---|---|---|---|---|
| Earliest arrival | 805.760 | 4.094 | 0.511 | 0.020 | 76.802 |
| Lowest fare | 866.082 | 5.589 | 0.000 | 0.120 | 137.125 |
| Next direct, same carrier | 961.585 | 6.299 | 0.000 | 0.024 | 232.628 |
| ReRouteAI | 728.958 | 4.785 | 0.244 | 0.070 | 0.000 |

## 2. Decision quality - simulated disruptions (airline cases, delays 50% worse than model)

Traveller cases: fares paid + value of time + connections. Airline cases: rebooking + EU261 + care + goodwill. Each strategy is replayed with delays sampled leg by leg.

| strategy | cost | delay_h | within_3h | failed | cost_vs_ReRouteAI_$ |
|---|---|---|---|---|---|
| Earliest arrival | 668.352 | 4.531 | 0.388 | 0.042 | -9.808 |
| Lowest fare | 938.991 | 6.077 | 0.000 | 0.154 | 260.831 |
| Next direct, same carrier | 985.233 | 6.512 | 0.000 | 0.036 | 307.073 |
| ReRouteAI | 678.160 | 6.616 | 0.382 | 0.044 | 0.000 |

## 2. Decision quality - simulated disruptions (traveller cases, delays 50% worse than model)

Traveller cases: fares paid + value of time + connections. Airline cases: rebooking + EU261 + care + goodwill. Each strategy is replayed with delays sampled leg by leg.

| strategy | cost | delay_h | within_3h | failed | cost_vs_ReRouteAI_$ |
|---|---|---|---|---|---|
| Earliest arrival | 856.100 | 4.273 | 0.419 | 0.039 | 94.943 |
| Lowest fare | 886.955 | 5.919 | 0.000 | 0.177 | 125.797 |
| Next direct, same carrier | 952.277 | 6.499 | 0.000 | 0.037 | 191.119 |
| ReRouteAI | 761.157 | 5.148 | 0.186 | 0.131 | 0.000 |

## 3. Sensitivity - the recommendation depends on the objective

| value_of_time_$per_h | recommended | flights | p_works | traveller_pays_$ |
|---|---|---|---|---|
| 0 | ZRH → WAW | LX1348 | 0.960 | 0 |
| 10 | ZRH → WAW | LX1348 | 0.960 | 0 |
| 25 | ZRH → VIE → WAW | OS566 + OS627 | 0.650 | 0 |
| 50 | ZRH → VIE → WAW | OS566 + OS627 | 0.650 | 0 |
| 75 | ZRH → VIE → WAW | OS566 + OS627 | 0.650 | 0 |
| 100 | ZRH → VIE → WAW | OS566 + OS627 | 0.650 | 0 |
| 150 | ZRH → WAW | AJ811 | 0.970 | 260 |
| 200 | ZRH → WAW | AJ811 | 0.970 | 260 |
| 300 | ZRH → WAW | AJ811 | 0.970 | 260 |
| 400 | ZRH → WAW | AJ811 | 0.970 | 260 |
| airline view, EU261 applies | ZRH → WAW | AJ811 | 0.970 | 260 |
| airline view, EU261 exempt (weather) | ZRH → WAW | LX1350 | 0.930 | 0 |

## 4. Policy retrieval

12 labelled questions: hit@1 83%, hit@3 100%.

## 5. ROI scenario (assumptions to be validated)

- Expected airline cost saved per disrupted passenger vs. 'next direct, same carrier': $408.60
- Agent time saved per passenger: $4.50
- x 50,000 disrupted passengers/yr - $250,000 operating cost = **$20,404,850 net per year**

Simulation runtime: 56.7 s.
