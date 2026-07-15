# Day 2 — Lesson: access patterns drive DynamoDB design

- Query requires the partition key. It's cheap and targeted.
- Scan reads the whole table; filters only cut what's returned, not what's read.
- "All records for one vehicle" -> Query on vehicle_id (PK). Easy.
- "One vehicle in a time range" -> Query on vehicle_id + timestamp range (SK). Easy.
- "ALL vehicles in a time range" -> NOT possible efficiently with this schema,
  because no single partition key value covers all vehicles. Options:
    - Scan + filter (reads entire table — bad at scale)
    - A GSI keyed by time (e.g. PK = date bucket, SK = timestamp)
- Takeaway: model the table around the queries you need. Each new access
  pattern may require a new index.

TODO (Day 5): replace AmazonDynamoDBFullAccess on the ingest role with a
scoped policy (PutItem/Query on VehicleTelemetry only).

# Day 3 - IoT Core: the front door

- MQTT pub/sub: devices publish to topics; broker (IoT Core) routes.
- Topic fleet/<vehicle_id>/telemetry; wildcard fleet/+/telemetry catches all.
- Per-device X.509 cert auth (mutual TLS), not passwords.
- IoT policy scoped: iot:Connect on client/sim-vehicle-*, iot:Publish on
  topic/fleet/*/telemetry. Not iot:* on *. Least privilege for devices.
- Rules Engine: SELECT * FROM 'fleet/+/telemetry' -> fleetsense-ingest -> DynamoDB.
- Gotcha 1: DynamoDB rejects Python floats. Fixed with
  json.loads(json.dumps(event), parse_float=Decimal).
- Gotcha 2: IoT->Lambda needs lambda:add-permission for iot.amazonaws.com,
  scoped to the rule ARN.
- Ran 3 simulators (sim-vehicle-01/02/03), one shared cert, distinct client IDs.
  Wildcard routed all three; partition key kept them separated. This is a fleet.
