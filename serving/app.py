"""FleetSense RUL inference Lambda (container image).
POST /predict  body: {"cycles": [[s1..s21], ...]}  (recent raw sensor rows, oldest->newest; >=20 recommended)
returns: {"rul": float, "band": "green|yellow|red", "n_cycles": int}
"""
import json, os
import numpy as np
import xgboost as xgb

_HERE = os.path.dirname(__file__)
_META = json.load(open(os.path.join(_HERE, "feature_meta.json")))
_BOOSTER = xgb.Booster(); _BOOSTER.load_model(os.path.join(_HERE, "rul_model.json"))

CLIP        = _META["clip"]
WINDOWS     = _META["windows"]
KEPT        = _META["kept_sensors"]
FEAT_ORDER  = _META["feature_order"]
SENSORS     = _META["sensor_columns"]

# Health bands on predicted RUL (cycles). Tunable.
def band(rul):
    if rul >= 60: return "green"
    if rul >= 30: return "yellow"
    return "red"

def _features(cycles):
    """cycles: 2D list, rows = cycles (oldest->newest), cols = 21 raw sensors."""
    arr = np.asarray(cycles, dtype=float)              # (T, 21)
    col = {s: arr[:, i] for i, s in enumerate(SENSORS)}
    feat = {}
    for c in KEPT:
        x = col[c]
        diff = np.diff(x, prepend=x[0]); diff[0] = 0.0  # match training diff().fillna(0)
        feat[c] = float(x[-1])                           # raw latest value
        for w in WINDOWS:
            win = x[-w:]
            feat[f"{c}_mean{w}"]  = float(win.mean())
            feat[f"{c}_std{w}"]   = float(win.std(ddof=1)) if len(win) > 1 else 0.0
            feat[f"{c}_slope{w}"] = float(diff[-w:].mean())
    return np.array([[feat[name] for name in FEAT_ORDER]], dtype=float)

def predict_rul(cycles):
    X = _features(cycles)
    rul = float(_BOOSTER.predict(xgb.DMatrix(X, feature_names=FEAT_ORDER))[0])
    rul = max(0.0, min(rul, CLIP))
    return {"rul": round(rul, 2), "band": band(rul), "n_cycles": len(cycles)}

def handler(event, context=None):
    try:
        body = event.get("body", event)
        if isinstance(body, str):
            body = json.loads(body)
        cycles = body["cycles"]
        if not cycles or len(cycles[0]) != len(SENSORS):
            raise ValueError(f"each cycle must have {len(SENSORS)} sensor values")
        result = predict_rul(cycles)
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"},
                "body": json.dumps(result)}
    except Exception as e:
        return {"statusCode": 400, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": str(e)})}
