# Model Card — FleetSense RUL Regressor (C-MAPSS FD001)

**Artifact:** `notebooks/rul_xgb_model.joblib` · **Owner:** Mohid Moneeb ·
**Project:** [FleetSense](https://github.com/MohidMoneeb/fleetsense-pipeline)

## Intended use
Predict the **Remaining Useful Life (RUL)**, in operating cycles, of a turbofan engine from rolling
statistics of its sensor stream. Built as the predictive-maintenance core of FleetSense and as a
transferable template for **vehicle** predictive maintenance (engine→vehicle, cycle→trip,
sensors→OBD/CAN channels). Intended for **fleet triage and maintenance scheduling**, not for
real-time flight-safety decisions.

## Model
Tuned **XGBoost** regressor (`n_estimators=500, learning_rate=0.03, max_depth=5, subsample=0.8,
colsample_bytree=0.8`). Selected from 8 experiments (see `experiments.md`).

## Training data
NASA C-MAPSS **FD001**: 100 run-to-failure engine trajectories, single operating condition, single
fault mode (**HPC degradation**). Features: rolling mean / std / slope over 5/10/20-cycle windows of
the 15 non-flat sensors (6 zero-variance sensors dropped). Target: RUL clipped at 125 cycles.

## Metrics
| Metric | Value |
|---|---|
| Validation RMSE (engine split) | 17.02 |
| **Official test RMSE** (`test_FD001`) | **16.55** |
| NASA asymmetric score | 632 (100 engines) |

Top drivers (summed importance): `s_4` T50 LPT-outlet temp (~0.40), `s_15` BPR (~0.14),
`s_11` Ps30 HPC-outlet static pressure (~0.14) — consistent with the HPC-degradation fault mode.

## Known failure modes
- **Early-life underdetermination.** Least accurate at high RUL, when the engine still looks healthy
  and sensors carry little degradation signal. Acceptable for maintenance (decisions only matter near
  the service threshold), but the model should not be read as precise far from failure.
- **Single-condition scope.** Trained only on FD001's one operating condition; it will **not**
  generalize to multi-condition subsets (FD002/FD004) or to real engines/vehicles without retraining
  and recalibration.
- **Clip ceiling.** Cannot distinguish RUL values above 125 by design.

## What NOT to trust it for
- Absolute RUL for a healthy unit (treat high predictions as "healthy," not as an exact countdown).
- Any engine type, operating condition, or sensor suite different from FD001 without retraining.
- Safety-critical or flight-critical decisions, or use without human maintenance-engineer oversight.
- Real vehicle telemetry as-is — the mapping is structural; production use requires vehicle data,
  re-derived features, and revalidation.
