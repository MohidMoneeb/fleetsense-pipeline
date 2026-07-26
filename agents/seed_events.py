"""Seed a VehicleEvents table with a few harsh_brake/swerve events (stand-in for Module 2
edge events, which aren't yet persisted). Creates the table if missing. Run once."""
import time, boto3
from decimal import Decimal
REGION="us-east-1"
ddb=boto3.client("dynamodb",region_name=REGION); res=boto3.resource("dynamodb",region_name=REGION)
name="VehicleEvents"
existing=[t for t in ddb.list_tables()["TableNames"] if t==name]
if not existing:
    ddb.create_table(TableName=name,
        AttributeDefinitions=[{"AttributeName":"vehicle_id","AttributeType":"S"},
                              {"AttributeName":"timestamp","AttributeType":"S"}],
        KeySchema=[{"AttributeName":"vehicle_id","KeyType":"HASH"},
                   {"AttributeName":"timestamp","KeyType":"RANGE"}],
        BillingMode="PAY_PER_REQUEST")
    ddb.get_waiter("table_exists").wait(TableName=name)
    print("created", name)
t=res.Table(name)
demo=[("engine-003","2026-07-27T02:10:00","harsh_brake","0.83"),
      ("engine-003","2026-07-27T02:12:00","swerve","0.76"),
      ("engine-005","2026-07-27T02:15:00","harsh_brake","0.71")]
with t.batch_writer() as bw:
    for vid,ts,ev,conf in demo:
        bw.put_item(Item={"vehicle_id":vid,"timestamp":ts,"event_type":ev,"confidence":Decimal(conf)})
print("seeded", len(demo), "events")
