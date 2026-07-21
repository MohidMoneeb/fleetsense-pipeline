"""
Virtual ECU - the 'brain' of the edge node.

Windows accelerometer data, classifies each window, applies debounce logic,
and publishes ONLY events (not raw telemetry) to AWS IoT.

NOTE ON THE CLASSIFIER: the trained Edge Impulse model is proven working
on-device via the WebAssembly deployment (running live on a phone). The .eim
Linux binary crashes on inference on macOS ARM ("Process exited with null"),
so this file uses a rule-based classifier over the same windows to exercise
the surrounding edge architecture: windowing, debounce, and event publishing.
Swapping in the ML inference call is a one-line change on a working runtime.
"""
import argparse
import json
import time
from collections import deque
from datetime import datetime, timezone

from awscrt import mqtt as aws_mqtt
from awsiot import mqtt_connection_builder

NODE_ID      = "esp32-node-01"
EVENT_TOPIC  = "fleet/" + NODE_ID + "/events"
AWS_ENDPOINT = "a2w1t5sf20bibw-ats.iot.us-east-1.amazonaws.com"
CERT = "/Users/mohiudmoneeb/fleetsense/certs/device.pem.crt"
KEY  = "/Users/mohiudmoneeb/fleetsense/certs/private.pem.key"
CA   = "/Users/mohiudmoneeb/fleetsense/certs/AmazonRootCA1.pem"

WINDOW_FEATURES = 375
DEBOUNCE_N      = 3
CONF_THRESHOLD  = 0.70
IGNORE_CLASSES  = {"idle", "normal"}


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
    with open(path) as f:
        data = json.load(f)
    payload = data["payload"]
    return payload["values"], payload.get("interval_ms", 16)


def classify_window(window):
    """Rule-based classifier over one window of [x, y, z] rows."""
    xs = [abs(r[0]) for r in window]
    ys = [abs(r[1]) for r in window]
    zs = [abs(r[2]) for r in window]

    def spread(vals):
        return max(vals) - min(vals)

    sx, sy, sz = spread(xs), spread(ys), spread(zs)
    total = sx + sy + sz

    if total < 1.5:
        return "idle", 0.95
    if total < 6.0:
        return "normal", 0.85
    # sharp event: dominant axis decides brake vs swerve
    if sx >= sy and sx >= sz:
        return "harsh_brake", min(0.99, 0.70 + total / 40.0)
    return "swerve", min(0.99, 0.70 + total / 40.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=False)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()

    values, interval_ms = load_samples(args.replay)
    axes = len(values[0])
    samples_per_window = WINDOW_FEATURES // axes
    stride = samples_per_window // 2

    print("Virtual ECU starting.")
    print("Window:", samples_per_window, "samples x", axes, "axes; stride", stride)

    aws_conn = None if args.no_publish else connect_aws()

    recent = deque(maxlen=DEBOUNCE_N)
    last_reported = None
    windows = 0
    events_sent = 0

    for start in range(0, len(values) - samples_per_window + 1, stride):
        window = values[start:start + samples_per_window]
        top, conf = classify_window(window)
        windows += 1
        print("window", windows, "->", top, round(conf, 2))

        recent.append(top if conf >= CONF_THRESHOLD else None)

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
            events_sent += 1
            last_reported = recent[0]
        elif recent and recent[-1] in IGNORE_CLASSES:
            last_reported = None

        time.sleep(0.05)

    print("")
    print("Done.", windows, "windows classified,", events_sent, "events emitted.")
    print("Bandwidth: ", windows, "raw windows ->", events_sent, "published messages.")


if __name__ == "__main__":
    main()
