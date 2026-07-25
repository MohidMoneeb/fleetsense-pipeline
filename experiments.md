# FleetSense RUL — Experiment Log (C-MAPSS FD001)

All experiments use the **same engine-level split** (80 train / 20 validation, seed 42) so
validation RMSE is directly comparable. RUL is clipped at 125. Failures are kept in the table on
purpose — they define the bar the winner had to clear.

| # | Model | Features | n_feats | Val RMSE |
|---|-------|----------|---------|----------|
| 1 | **XGBoost (tuned)** | all | 150 | **17.02** ← winner |
| 2 | LightGBM (tuned) | all | 150 | 17.20 |
| 3 | LightGBM (default) | all | 150 | 17.44 |
| 4 | XGBoost (tuned) | mean+std | 105 | 17.55 |
| 5 | LinearRegression | all | 150 | 17.66 |
| 6 | XGBoost (default) | all | 150 | 17.77 |
| 7 | XGBoost (tuned) | mean-only | 60 | 18.00 |
| 8 | RandomForest (50) | all | 150 | 18.91 |

Tuned config (winner): `n_estimators=500, learning_rate=0.03, max_depth=5, subsample=0.8,
colsample_bytree=0.8`.

## What the table says
- Gradient boosting beats the Day-10 RandomForest baseline, but only by ~1.9 RMSE — the baseline was
  already strong, which is worth stating honestly.
- **Trimming features hurts**: dropping slope (mean+std) then std (mean-only) monotonically worsens
  RMSE, confirming the volatility and rate-of-change signals carry real degradation information.
- Tuning XGBoost mattered more than switching XGBoost↔LightGBM.

## Winner — held-out generalization
Retrained on the full 100-engine training set, evaluated on the official `test_FD001` / `RUL_FD001`:
**RMSE 16.55, NASA asymmetric score 632** (100 engines). Frozen at `rul_xgb_model.joblib`.
