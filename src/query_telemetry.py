import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("VehicleTelemetry")

# Query 1: ALL records for one vehicle
print("=== All records for CAR-001 ===")
resp = table.query(
    KeyConditionExpression=Key("vehicle_id").eq("CAR-001")
)
for item in resp["Items"]:
    print(item)

# Query 2: one vehicle within a TIME RANGE (uses the sort key)
print("\n=== CAR-001 between 10:00 and 10:07 ===")
resp = table.query(
    KeyConditionExpression=Key("vehicle_id").eq("CAR-001")
    & Key("timestamp").between("2026-07-15T10:00:00Z", "2026-07-15T10:07:00Z")
)
for item in resp["Items"]:
    print(item)
