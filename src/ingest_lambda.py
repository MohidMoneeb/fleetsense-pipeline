import json
import os
from decimal import Decimal
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("VehicleTelemetry")
sns = boto3.client("sns")

ALERT_TOPIC_ARN = os.environ.get("ALERT_TOPIC_ARN", "")
COOLANT_THRESHOLD = 120  # °C

def lambda_handler(event, context):
    item = json.loads(json.dumps(event), parse_float=Decimal)
    table.put_item(Item=item)

    temp = float(item.get("coolant_temp_c", 0))
    if temp > COOLANT_THRESHOLD and ALERT_TOPIC_ARN:
        sns.publish(
            TopicArn=ALERT_TOPIC_ARN,
            Subject=f"FleetSense ALERT: {item.get('vehicle_id')} overheating",
            Message=(f"Vehicle {item.get('vehicle_id')} coolant temp "
                     f"{temp} C at {item.get('timestamp')}"),
        )
    return {"statusCode": 200, "body": "written"}
