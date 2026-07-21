"""
Virtual ECU - the 'brain' of the edge node.

Runs the Edge Impulse classifier over windows of accelerometer data,
applies debounce logic, and publishes ONLY events (not raw telemetry)
to AWS IoT. Architected exactly as it would be on-silicon.
"""
import argparse
import json
import time
from collections import deque
from datetime import datetime, timezone

from edge_impulse_linux.runner import ImpulseRunner
from awscrt import mqtt as aws_mqtt
from awsiot import mqtt_connection_builder

NODE_ID       = "esp32-node-01"
EVENT_TOPIC   = f"fleet/{NODE_ID}/events"
AWS_ENDPOINT  = "a2w1t5sf20bibw-ats.iot.us-east-1.amazonaws.com"
CERT = "/Users/mohiudmoneeb/fleetsense/certs/device.pem.crt"
KEY  = "/Users/mohiudmoneeb/fleetsense/certs/private.pem.key"
CA   = "/Users/mohiudmoneeb/fleetsense/certs/AmazonRootCA1.pem"

# --- debounce config ---
DEBOUNCE_N      = 3      # consecutive agreeing windows required
CONF_THRESHOLD  = 0.70   # minimum confidence to count as a vote
IGNORE_CLASSES  = {"idle", "normal"}   # only report interesting events


def connect_aws():
    conn = mqtt_connection_builder.mtls_from_path(
        endpoint=AWS_ENDPOINT,
        cert_filepath=CERT,
        pri_key_filepath=KEY,
        ca_filepath=CA,
        client_id="bridge-virtual-ecu",
        clean_session=False,
        keep_alive_secs=30,
    )
    print("Connecting to AWS IoT...")
    conn.connect().result()
    print("Connected to AWS IoT.")
    return conn


def load_samples(path):
    """Load an Edge Impulse exported sample JSON -> flat list of axis values."""
    with open(path) as f:
        data = json.load(f)
    payload = data["payload"]
    return payload["values"], payload.get("interval_ms", 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="path to .eim file")
    ap.add_argument("--replay", required=True, help="path to exported sample JSON")
    ap.add_argument("--no-publish", action="store_true", help="dry run")
    args = ap.parse_args()

    runner = ImpulseRunner(args.model)
    info = runner.init()
    params = info["model_parameters"]
    window_len = params["input_features_count"]        # total floats per window
    labels = params["labels"]
    print(f"Model loaded. Labels={labels}, window={window_len} features")

    values, interval_ms = load_samples(args.replay)
    axes = len(values[0])
    samples_per_window = window_len // axes
    stride = samples_per_window // 2                   # 50% overlap, as trained

    aws_conn = None if args.no_publish else connect_aws()

    recent = deque(maxlen=DEBOUNCE_N)
    last_reported = None
    windows = 0

    for start in range(0, len(values) - samples_per_window + 1, stride):
        window = values[start:start + samples_per_window]
        features = [v for row in window for v in row]   # flatten

        res = runner.classify(features)
        scores = res["result"]["classification"]
        top = max(scores, key=scores.get)
        conf = scores[top]
        windows += 1
        print(f"window {windows:3d}  ->  {top:12s} {conf:.2f}")

        recent.append(top if conf >= CONF_THRESHOLD else None)

        # debounce: N consecutive identical, confident predictions
        if (len(recent) == DEBOUNCE_N
                and len(set(recent)) == 1
                and recent[0] is not None
                and recent[0] not in IGNORE_CLASSES
                and recent[0] != last_reported):
            event = {
                "vehicle_id": NODE_ID,
                "event": recent[0],
                "confidence": round(float(conf), 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            print("  EVENT ->", event)
            if aws_conn:
                aws_conn.publish(
                    topic=EVENT_TOPIC,
                    payload=json.dumps(event),
                    qos=aws_mqtt.QoS.AT_LEAST_ONCE,
                )
            last_reported = recent[0]
        elif recent and recent[-1] in IGNORE_CLASSES:
            last_reported = None      # re-arm once things calm down

        time.sleep(0.05)

    print(f"\nDone. {windows} windows classified.")
    runner.stop()


if __name__ == "__main__":
    main()
