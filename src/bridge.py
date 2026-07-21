import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from awscrt import mqtt as aws_mqtt
from awsiot import mqtt_connection_builder

# --- config ---
NODE_ID       = "esp32-node-01"
PUBLIC_TOPIC  = f"fleet/{NODE_ID}/telemetry"
AWS_TOPIC     = f"fleet/{NODE_ID}/telemetry"
PUBLIC_BROKER = "test.mosquitto.org"
PUBLIC_PORT   = 1883

AWS_ENDPOINT = "a2w1t5sf20bibw-ats.iot.us-east-1.amazonaws.com"
CERT = "/Users/mohiudmoneeb/fleetsense/certs/device.pem.crt"
KEY  = "/Users/mohiudmoneeb/fleetsense/certs/private.pem.key"
CA   = "/Users/mohiudmoneeb/fleetsense/certs/AmazonRootCA1.pem"

# --- connect to AWS IoT (mutual TLS with your device certs) ---
aws_conn = mqtt_connection_builder.mtls_from_path(
    endpoint=AWS_ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=CA,
    client_id="bridge-esp32-node-01",
    clean_session=False,
    keep_alive_secs=30,
)
print("Connecting to AWS IoT...")
aws_conn.connect().result()
print("Connected to AWS IoT.")

# --- public broker callbacks (paho-mqtt v2 API) ---
def on_connect(client, userdata, flags, reason_code, properties):
    print("Public broker connected:", reason_code)
    client.subscribe(PUBLIC_TOPIC)
    print("Subscribed to", PUBLIC_TOPIC)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("bad payload:", e)
        return
    # Normalize for DynamoDB keys: guarantee vehicle_id + timestamp
    data.setdefault("vehicle_id", NODE_ID)
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    aws_conn.publish(
        topic=AWS_TOPIC,
        payload=json.dumps(data),
        qos=aws_mqtt.QoS.AT_LEAST_ONCE,
    )
    print("bridged ->", data)

# NOTE: paho-mqtt 2.x requires CallbackAPIVersion as the first argument.
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bridge-sub-esp32")
client.on_connect = on_connect
client.on_message = on_message
client.connect(PUBLIC_BROKER, PUBLIC_PORT, 60)
client.loop_forever()
