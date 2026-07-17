# FleetSense Pipeline

A connected-vehicle intelligence platform on AWS. Telemetry flows from simulated
vehicles through IoT ingestion into a queryable store, with real-time alerting
and a live dashboard.

![Dashboard](diagrams/demo.gif)

## Architecture

![Architecture](diagrams/architecture.svg)

Pipeline (device to insight):
- **Devices:** Python vehicle simulators (`sim-vehicle-01/02/03`) publish
  telemetry (speed, RPM, coolant temp, battery voltage, GPS) every 2s over MQTT,
  with injected anomalies.
- **Ingestion:** AWS IoT Core authenticates each device with an X.509 certificate
  and routes messages via a Rules Engine rule (`SELECT * FROM 'fleet/+/telemetry'`).
- **Processing:** `fleetsense-ingest` Lambda writes each reading to DynamoDB and
  fires an SNS email alert when coolant temp exceeds a threshold.
- **Storage:** DynamoDB table `VehicleTelemetry` (PK `vehicle_id`, SK `timestamp`).
- **Visualization:** a Streamlit dashboard reads DynamoDB for a live fleet
  overview, per-vehicle charts, and an anomaly banner.

## Setup

Prerequisites: an AWS account, AWS CLI configured (`aws configure`), Python 3.9+,
and a device certificate/key from AWS IoT Core (see below).

1. Install dependencies:
2. Register an IoT Thing in AWS IoT Core, download its certificate, private key,
   and the Amazon Root CA, and place them in `~/fleetsense/certs/`.
3. Get your IoT endpoint:
4. Run a simulator (replace the endpoint with yours):
5. Launch the dashboard:
## Design decisions

- **MQTT over HTTP for ingestion.** Vehicles are intermittently connected and
  send small, frequent messages. MQTT's persistent pub/sub connections and QoS
  delivery fit this far better than HTTP's per-request overhead.
- **DynamoDB over a relational database.** The workload is high-volume,
  append-heavy time-series with a simple access pattern (by vehicle, by time).
  DynamoDB gives predictable low-latency writes and scales without server
  management; JOINs and rigid schemas aren't needed.
- **Serverless (Lambda + IoT Rules).** Telemetry is bursty, so scaling to zero
  when idle and up automatically under load avoids paying for idle servers.
- **Least-privilege policies.** Devices can only connect as `sim-vehicle-*` and
  publish to `fleet/*/telemetry` — nothing more.

## Repo layout
- `/src` — simulator, ingest Lambda, dashboard
- `/docs` — design notes and lessons learned
- `/diagrams` — architecture diagram and dashboard demo

## Status
Day 4 of 20 — Module 1 shipped: ingest, store, alert, and visualize.
