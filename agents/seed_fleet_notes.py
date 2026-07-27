"""Create the FleetNotes long-term-memory table and seed one PAST incident, so the first
FleetPilot run can detect a recurring problem ('same voltage sag last week'). Run once."""
import boto3
from datetime import datetime, timezone, timedelta
REGION="us-east-1"
ddb=boto3.client("dynamodb",region_name=REGION); res=boto3.resource("dynamodb",region_name=REGION)
name="FleetNotes"
if name not in ddb.list_tables()["TableNames"]:
    ddb.create_table(TableName=name,
        AttributeDefinitions=[{"AttributeName":"vehicle_id","AttributeType":"S"},
                              {"AttributeName":"timestamp","AttributeType":"S"}],
        KeySchema=[{"AttributeName":"vehicle_id","KeyType":"HASH"},
                   {"AttributeName":"timestamp","KeyType":"RANGE"}],
        BillingMode="PAY_PER_REQUEST")
    ddb.get_waiter("table_exists").wait(TableName=name)
    print("created", name)
last_week=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
res.Table(name).put_item(Item={"vehicle_id":"sim-vehicle-02","timestamp":last_week,
    "summary":"Battery voltage sag to 8.6V (LOW) flagged as yellow; advised charging-system inspection."})
print("seeded past incident for sim-vehicle-02 dated", last_week)
