# Model card: upgrade propensity (SYNTHETIC)

> Trained on **synthetic** data from a fictional company. It demonstrates method, not real-world performance.

## Purpose
Rank currently-free active users by the probability that they convert to a paid plan in the **next 30 days**, so that a
limited-budget upgrade nudge can be aimed at the users most likely to respond.

## Data and target
* Grain: user x month-end snapshot (`mart_user_features`), free users who never paid before the snapshot and were active in the prior 60 days.
* Target: `converted_next_30d`, i.e. first upgrade event in (snapshot, snapshot + 30 days]. Base rate on the hold-out: 0.616%.
* Features: only days **at or before** the snapshot: assets and active days in the prior 30 days and the 30 days before that, largest single day, days since last use,
  tenure, trend (log ratio of recent to previous volume), country and acquisition source.
* **Leakage guard.** The target is never defined from a feature. A deliberately leaky variant (label = "heavy user", defined from `assets_30d`, with `assets_30d` as an
  input) scores PR-AUC 1.00 / ROC-AUC 1.00: near perfect, and meaningless.

## Split (time-based)
* Fit snapshots: 2025-03-31 to 2025-12-31 (166,050 rows).
* Validation (calibration, model selection, threshold): 2026-01-31, 2026-02-28 (47,668 rows).
* Hold-out test: 2026-03-31, 2026-04-30, 2026-05-31 (78,843 rows). Training label windows end before the first test snapshot (purged).

## Models compared
| model | valid PR-AUC | test PR-AUC | test ROC-AUC | test Brier |
|---|---|---|---|---|
| logistic_regression | 0.1083 | 0.1046 | 0.8966 | 0.0058 |
| gradient_boosting | 0.1080 | 0.1019 | 0.9050 | 0.0058 |
| gradient_boosting_calibrated | 0.1049 | 0.0863 | 0.9020 | 0.0058 |

Selected by validation PR-AUC of the uncalibrated candidates: **logistic_regression** (isotonic calibration fitted on the validation fold).
Hold-out: PR-AUC 0.105 (base rate 0.006), ROC-AUC 0.897, Brier 0.0058. Top-decile lift 6.8x.

## Decision threshold: expected profit, not accuracy
Contacting a user costs EUR 0.4, a nudge lifts conversion probability by 30% (relative), and a new paying customer is worth EUR 150
(all assumptions in `config/analysis.yaml`). Break-even precision is 0.89%. The threshold (0.0063) maximises expected profit on the validation fold;
on the hold-out it contacts 16,641 of 78,843 users and earns EUR 11,569
(contacting everyone: EUR -9,667).

## Top features (permutation importance, drop in PR-AUC)
| feature | pr_auc_drop |
|---|---|
| trend_log_ratio | 0.1087 |
| tenure_days | 0.0987 |
| assets_30d | 0.0919 |
| avg_assets_per_active_day | 0.0368 |
| max_daily_assets_30d | 0.0303 |
| assets_prev30d | 0.0209 |

## Outputs
`fact_user_scores` holds the score and decile of every scored user at the as-of snapshot (`upgrade_propensity_30d`, version `v1`); the serialized model is written to `models/` (git-ignored).

## Limitations
* Synthetic data with a built-in relationship between engagement and upgrade; real behaviour will be noisier and drift.
* Few positives per snapshot (47,668 validation rows): threshold and calibration are noisy.
* Profit numbers rest on invented assumptions; the *ordering* of policies is more reliable than the euro amounts.
* Association, not causation: the score says who is likely to convert, not who is *persuaded* by a nudge (that needs an uplift model or a randomised test).
* The model is not refit on the hold-out before scoring; a production setup would retrain on a schedule and monitor calibration drift.
