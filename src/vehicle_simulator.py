import argparse
import json
import time
import random
from datetime import datetime, timezone

from awscrt import mqtt
from awsiot import mqtt_connection_builder


class VehicleSimulator:
    """Generates plausible vehicle telemetry, with occasional anomalies."""

    def __init__(self, vehicle_id):
        self.vehicle_id = vehicle_id
        self.speed = 0.0
        self.rpm = 800.0
        self.coolant_temp = 80.0
        self.battery_voltage = 12.6
        self.lat = 36.0014   # start near Durham, NC
        self.lon = -78.9382
        self.tick = 0

    def next_reading(self):
        self.tick += 1

        # normal driving dynamics
        self.speed = max(0.0, min(120.0, self.speed + random.uniform(-8, 8)))
        self.rpm = 800 + self.speed * 45 + random.uniform(-100, 100)
        self.coolant_temp += random.uniform(-0.5, 0.5)
        self.battery_voltage += random.uniform(-0.05, 0.05)
        self.lat += random.uniform(-0.0005, 0.0005)   # GPS drifts along a route
        self.lon += random.uniform(-0.0005, 0.0005)

        # occasional injected anomalies
        if self.tick % 30 == 0:
            self.coolant_temp += 15      # temperature creep
        if self.tick % 45 == 0:
            self.battery_voltage -= 1.5  # voltage sag

        return {
            "vehicle_id": self.vehicle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "speed_kmh": round(self.speed, 1),
            "rpm": round(self.rpm, 0),
            "coolant_temp_c": round(self.coolant_temp, 1),
            "battery_voltage": round(self.battery_voltage, 2),
            "lat": round(self.lat, 5),
            "lon": round(self.lon, 5),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicle-id", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--ca", required=True)
    args = parser.parse_args()

    topic = f"fleet/{args.vehicle_id}/telemetry"

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=args.endpoint,
        cert_filepath=args.cert,
        pri_key_filepath=args.key,
        ca_filepath=args.ca,
        client_id=args.vehicle_id,
        clean_session=False,
        keep_alive_secs=30,
    )

    print(f"Connecting as {args.vehicle_id} ...")
    mqtt_connection.connect().result()
    print("Connected. Publishing to", topic)

    sim = VehicleSimulator(args.vehicle_id)
    try:
        while True:
            reading = sim.next_reading()
            mqtt_connection.publish(
                topic=topic,
                payload=json.dumps(reading),
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )
            print("published:", reading)
            time.sleep(2)
    except KeyboardInterrupt:
        print("Stopping...")
        mqtt_connection.disconnect().result()


if __name__ == "__main__":
    main()
