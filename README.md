# FleetSense Pipeline

A connected-vehicle intelligence platform built on AWS.
Telemetry flows from a simulator to Lambda ingestion to DynamoDB to analytics/AI layers.

## Architecture
Diagram coming (see /diagrams). Current state:
- Ingestion: fleetsense-ingest Lambda writes JSON telemetry to DynamoDB.
- Storage: DynamoDB table VehicleTelemetry (PK vehicle_id, SK timestamp).

## Repo layout
- /src - application and Lambda code
- /docs - design notes and lessons learned
- /diagrams - architecture diagrams

## Status
Day 2 of 20 - serverless core stood up.
