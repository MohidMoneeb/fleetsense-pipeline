"""Day 15 — read-only diagnostic tools wrapping FleetSense infrastructure.
Each tool is small, single-purpose, typed, with a docstring written FOR the model.
No tool writes data. Env: AWS_REGION, PREDICT_URL.
"""
import os, json, urllib.request
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.tools import tool

REGION      = os.environ.get("AWS_REGION", "us-east-1")
PREDICT_URL = os.environ.get("PREDICT_URL", "https://8148a8gs1e.execute-api.us-east-1.amazonaws.com/predict")
SENSORS     = [f"s_{i}" for i in range(1, 22)]

from aws_helper import boto3_kwargs
_ddb   = boto3.resource("dynamodb", **boto3_kwargs())
TELEM  = _ddb.Table("VehicleTelemetry")
HEALTH = _ddb.Table("VehicleHealth")
EVENTS = _ddb.Table("VehicleEvents")

def _clean(item):
    """Convert DynamoDB Decimals to plain numbers for JSON-friendly output."""
    out = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = int(v) if v % 1 == 0 else float(v)
        else:
            out[k] = v
    return out

@tool
def get_fleet_status() -> list:
    """Get the latest telemetry reading for EVERY vehicle in the fleet, one record per vehicle.
    Use this first to see the whole fleet at a glance before drilling into one vehicle.
    Returns a list of dicts, each with vehicle_id, timestamp, and whatever sensor fields that
    vehicle reports (e.g. speed, coolant temperature, battery voltage)."""
    items = TELEM.scan().get("Items", [])
    latest = {}
    for it in items:
        v = it["vehicle_id"]
        if v not in latest or str(it["timestamp"]) > str(latest[v]["timestamp"]):
            latest[v] = it
    return [_clean(latest[v]) for v in sorted(latest)]

@tool
def get_vehicle_history(vehicle_id: str, hours: int = 24) -> list:
    """Get recent time-series telemetry for ONE vehicle, most recent readings first.
    Use this to inspect trends for a specific vehicle. `vehicle_id` is the exact id
    (e.g. 'engine-003'). `hours` is a hint for how far back to look; the tool returns up
    to 50 of the most recent readings. Returns a list of telemetry dicts."""
    r = TELEM.query(KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
                    ScanIndexForward=False, Limit=50)
    return [_clean(it) for it in r.get("Items", [])]

@tool
def get_recent_events(vehicle_id: str) -> list:
    """Get recent driving-behavior events (e.g. harsh_brake, swerve) for ONE vehicle.
    Use this to check whether a vehicle has had risky driving events. `vehicle_id` is the
    exact id. Returns a list of {timestamp, event_type, confidence}, most recent first.
    An empty list means no recorded events."""
    try:
        r = EVENTS.query(KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
                         ScanIndexForward=False, Limit=25)
        return [_clean(it) for it in r.get("Items", [])]
    except Exception:
        return []

@tool
def predict_health(vehicle_id: str) -> dict:
    """Predict Remaining Useful Life (RUL) and a health band for ONE engine vehicle by calling
    the deployed model API. Use this to assess how close a vehicle is to needing service.
    `vehicle_id` must be an engine-type vehicle that reports the 21 sensors (id like 'engine-003').
    Returns {rul, band} where band is green/yellow/red, or {error: ...} if the vehicle has no
    21-sensor data (the RUL model only applies to engine vehicles)."""
    r = TELEM.query(KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
                    ScanIndexForward=False, Limit=25)
    items = list(reversed(r.get("Items", [])))
    if not items or any(s not in items[0] for s in SENSORS):
        return {"error": f"{vehicle_id} has no 21-sensor data; RUL model applies to engine vehicles only"}
    cycles = [[float(it[s]) for s in SENSORS] for it in items]
    req = urllib.request.Request(PREDICT_URL, data=json.dumps({"cycles": cycles}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

ALL_TOOLS = [get_fleet_status, get_vehicle_history, get_recent_events, predict_health]
