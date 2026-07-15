# FleetSense Pipeline

A connected-vehicle intelligence platform built on AWS. Telemetry flows from
simulated vehicles through IoT ingestion into a queryable time-series store,
with analytics and AI layers to follow.

## Architecture

![Architecture](diagrams/architecture.svg)

Pipeline (device to storage):
- **Devices:** Python vehicle simulators (`sim-vehicle-01/02/03`) publish
  plausible telemetry (speed, RPM, coolant temp, battery voltage, GPS) every
  2 seconds over MQTT, with injected anomalies.
- **Ingestion:** AWS IoT Core authenticates each device with an X.509
  certificate and routes messages via a Rules Engine rule
  (`SELECT * FROM 'fleet/+/telemetry'`).
- **Processing:** `fleetsense-ingest` Lambda receives each message and writes
  it to DynamoDB (converting floats to Decimal).
- **Storage:** DynamoDB table `VehicleTelemetry`
  (PK `vehicle_id`, SK `timestamp`), which partitions each vehicle cleanly.

## Security notes
- IoT policy is least-privilege: `iot:Connect` scoped to `client/sim-vehicle-*`
  and `iot:Publish` scoped to `topic/fleet/*/telemetry` (no wildcards on `*`).
- Device certificates and keys live outside the repo and are gitignored.

## Repo layout
- `/src` — application, simulator, and Lambda code
- `/docs` — design notes and lessons learned
- `/diagrams` — architecture diagrams

## Status
Day 3 of 20 — IoT ingestion pipeline live; three-vehicle fleet flowing into DynamoDB.
