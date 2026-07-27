"""Day 16 — long-term memory: a DynamoDB FleetNotes table of past incidents.
Two tools the Ops agent uses: read past notes for a vehicle (recurrence detection)
and write a new incident summary after a run. This is PERSISTENT cross-run memory,
distinct from the graph's short-term conversation checkpointer.
"""
import os
from decimal import Decimal
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.tools import tool

REGION = os.environ.get("AWS_REGION", "us-east-1")
_ddb   = boto3.resource("dynamodb", region_name=REGION)
NOTES  = _ddb.Table("FleetNotes")

@tool
def read_fleet_notes(vehicle_id: str) -> list:
    """Read past incident notes for ONE vehicle from long-term memory (FleetNotes).
    Call this BEFORE flagging a vehicle, to see if the problem has happened before
    (e.g. a recurring voltage sag). `vehicle_id` is the exact id. Returns a list of
    {date, summary}, most recent first. Empty list means no prior incidents on record."""
    r = NOTES.query(KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
                    ScanIndexForward=False, Limit=10)
    return [{"date": str(i.get("timestamp","")), "summary": i.get("summary","")}
            for i in r.get("Items", [])]

@tool
def write_fleet_note(vehicle_id: str, summary: str) -> str:
    """Save an incident summary for ONE vehicle to long-term memory (FleetNotes).
    Call this AFTER deciding a vehicle is worth flagging, so future runs remember it.
    `vehicle_id` is the exact id; `summary` is one or two sentences describing the
    incident and severity. Returns a confirmation string."""
    ts = datetime.now(timezone.utc).isoformat()
    NOTES.put_item(Item={"vehicle_id": vehicle_id, "timestamp": ts, "summary": summary})
    return f"saved note for {vehicle_id} at {ts}"

NOTE_TOOLS = [read_fleet_notes, write_fleet_note]
