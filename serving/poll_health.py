"""Scheduled poller (zip Lambda, EventBridge every 5 min).
For each vehicle, pull recent telemetry from VehicleTelemetry, invoke the RUL inference
Lambda, and write the health score to VehicleHealth. Lightweight: no ML deps here.
Env: INFERENCE_FUNCTION (name/ARN of the container inference Lambda).
"""
import os, json, boto3
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb")
lam = boto3.client("lambda")
SENSORS = [f"s_{i}" for i in range(1, 22)]
SRC   = ddb.Table("VehicleTelemetry")
DST   = ddb.Table("VehicleHealth")
INFER = os.environ["INFERENCE_FUNCTION"]
WINDOW = 25

def _vehicle_ids():
    # Demo: fixed seeded engine-vehicles. In production, maintain a fleet registry.
    return [f"engine-{i:03d}" for i in range(1, 6)]

def handler(event, context=None):
    written = 0
    for vid in _vehicle_ids():
        r = SRC.query(KeyConditionExpression=Key("vehicle_id").eq(vid),
                      ScanIndexForward=False, Limit=WINDOW)
        items = list(reversed(r.get("Items", [])))       # oldest -> newest
        if len(items) < 5:
            continue
        try:
            cycles = [[float(it[s]) for s in SENSORS] for it in items]
        except KeyError:
            continue                                       # not a 21-sensor record
        resp = lam.invoke(FunctionName=INFER, Payload=json.dumps({"cycles": cycles}).encode())
        out = json.loads(resp["Payload"].read())
        body = json.loads(out["body"]) if "body" in out else out
        if "rul" not in body:
            continue
        DST.put_item(Item={"vehicle_id": vid,
                           "timestamp": datetime.now(timezone.utc).isoformat(),
                           "rul": str(body["rul"]), "band": body["band"]})
        written += 1
    return {"written": written}
