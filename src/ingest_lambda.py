import json
from decimal import Decimal
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("VehicleTelemetry")

def lambda_handler(event, context):
    item = json.loads(json.dumps(event), parse_float=Decimal)
    table.put_item(Item=item)
    print("Wrote item:", json.dumps(event))
    return {"statusCode": 200, "body": "written"}
