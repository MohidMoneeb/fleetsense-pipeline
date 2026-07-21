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

# Day 5 - Virtual embedded node (Wokwi ESP32)

- Wrote real Arduino/C++ firmware: I2C read of an MPU6050 accelerometer,
  WiFi (Wokwi-GUEST), MQTT publish to a public broker every 1s.
- The firmware is identical to what a physical ESP32 would run - simulator-first
  development, which mirrors how automotive teams actually work.
- Bridge pattern: bridge.py subscribes to the public broker and republishes into
  AWS IoT Core using device certs. Edge-broker-to-cloud-broker bridging is a
  standard industrial pattern, documented as a design decision, not a workaround.
- The bridge normalizes messages (adds an ISO timestamp) so DynamoDB's sort key
  is always present.
- Zero cloud changes: the fleet/+/telemetry wildcard rule and the partition-key
  schema absorbed an entirely new device type. It appeared on the dashboard
  automatically.
- Gotcha 1: paho-mqtt 2.x requires CallbackAPIVersion.VERSION2 as the first
  Client() argument or it errors immediately.
- Gotcha 2: the IoT policy only allowed iot:Connect on client/sim-vehicle-*, so
  the bridge was rejected. AWS signals this as AWS_ERROR_MQTT_UNEXPECTED_HANGUP
  rather than an explicit access-denied - a useful debugging lesson. Fixed by
  adding client/bridge-* to the policy, keeping least privilege intact.
- Gotcha 3: the dashboard crashed on vehicles lacking certain columns. Fixed by
  rendering only fields that exist per device - heterogeneous fleets need
  schema-tolerant UIs.
- Harsh braking signature: a large, brief spike on a single accel axis
  (~0 -> +/-8 m/s2), then a return to baseline.
