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

# Day 6 - TinyML concepts and data collection (Edge Impulse)

Why edge inference (the four standard reasons):
- Latency: a safety decision cannot wait for a cloud round-trip.
- Cost: streaming raw high-rate sensor data from a whole fleet is expensive;
  sending only detected events is tiny.
- Privacy: raw motion data is revealing; inferring locally sends only labels.
- Offline: tunnels and dead zones must not disable safety functions.

Architectural contrast: FleetSense today ships RAW telemetry to the cloud.
Edge inference would ship CONCLUSIONS. Same pipeline, far less bandwidth.

TinyML workflow: collect -> window -> extract features -> train -> quantize
-> deploy.

Dataset: 4 classes (idle, normal, harsh_brake, swerve), 12 samples each,
~8-10s per sample, phone accelerometer at 62.5 Hz via the Edge Impulse mobile
client. Grip, resting position, and intensity were varied deliberately so the
model learns the physics rather than one memorized gesture.

Impulse: 2000 ms window, 1000 ms stride (50% overlap), spectral analysis
processing block, classification learning block.

FEATURE EXPLORER OBSERVATION:
idle separates cleanly into a tight, isolated cluster - unsurprising, since
the absence of motion has a signature no other class can imitate. normal and
harsh_brake each form reasonably coherent regions. The problem class is
swerve, which is smeared across the space and overlaps BOTH normal and
harsh_brake rather than occupying its own region. The physical reason is that
an accelerometer measures linear acceleration plus gravity - it does not
directly measure rotation, and a swerve is fundamentally a rotational event.
So a swerve registers only indirectly, and in two different ways depending on
execution: a laterally-translated swerve produces a sharp linear transient
that is nearly indistinguishable from harsh_brake apart from which axis
carries the energy, while a mostly-rotational swerve appears as a slow
redistribution of the gravity vector across axes, which resembles the gentle
swaying of normal. Hence red points appear in both neighbourhoods. The most
confusable pair is therefore swerve and harsh_brake: both are high-magnitude
transients whose only real discriminator is axis of action, and any variation
in grip or phone orientation smears that axis information across samples.
This is the central tension of the dataset - varying orientation improves
generalization but erodes the very cue that separates these two classes.
The correct engineering fix is sensor fusion: adding a gyroscope would
measure rotation directly and separate swerve cleanly.

A handful of stray idle windows sit near the centre of the plot - these are
almost certainly captured while repositioning the phone between samples.

Gotchas: phone auto-lock and app-switching kill a recording mid-sample;
iOS requires an explicit motion-sensor permission prompt; samples recorded
slightly shorter (8s) than the 10000 ms requested, which is fine as long as
it is consistent.

# Day 7 - Train, quantize, deploy

Training (Edge Impulse suggested architecture: dense 20 -> dense 10):
  accuracy 89.7%, loss 0.76, ROC 0.97, weighted F1 0.90
  Per-class F1: idle 1.00, normal 0.91, swerve 0.86, harsh_brake 0.79
  Confusion: swerve->harsh_brake 16.7%; harsh_brake->normal 14.3%

Finding: harsh_brake was the WEAKEST class, not swerve as predicted from the
feature explorer. Cause is label noise from windowing: each 10s harsh_brake
sample contained 2-3 jerks with calm gaps between them, and with a 2s window
sliding every 1s, several windows contain only the calm portion. Those windows
are physically indistinguishable from normal, so the model is not wrong - the
labels are. Fixes: record events more densely, or crop samples to the event.

QUANTIZATION TRADE-OFF (Edge Impulse profiler ESTIMATES for Espressif ESP-EYE
ESP32 @240MHz with EON Compiler - NOT measured on physical silicon):
                    int8        float32
  latency (total)   30 ms       32 ms
  RAM               2.2K        2.2K
  flash (classifier) 15.1K      14.7K
  accuracy          89.29%      91.07%

Interpretation: quantization bought almost nothing here - 2 ms latency, zero
RAM saving, and int8 flash was marginally LARGER - while costing 1.78
percentage points of accuracy. Two reasons: (1) the model is tiny (two dense
layers), and quantization savings scale with weight count, so the int8
scale/zero-point metadata roughly cancels the weight savings; (2) spectral
feature extraction dominates total latency at 29 ms vs 1-3 ms for the
classifier, so the neural network was never the bottleneck. The EON Compiler
(same accuracy, 54% less RAM, 61% less ROM) is doing far more work than
quantization on this workload. Lesson: measure before optimizing - the
standard "always quantize" advice does not pay off at this model scale.

Deployment 1 (SUCCESS): WASM "Launch in browser" - the model runs locally on
the phone with no network round-trip. Recorded as a demo video.

Deployment 2 (BLOCKED): .eim binary + edge_impulse_linux Python runner.
The model loads and reports its labels correctly, but classify() fails with
"No data or corrupted data received" from the SDK's socket read. This is a
known limitation of the Linux Python SDK on macOS / Python 3.9 - the documented
workaround (patching the recv buffer in runner.py) did not resolve it. Real
portability finding: the vendor's "Linux" SDK is not reliably cross-platform.

DEBOUNCE DESIGN (implemented in virtual_ecu.py):
Require N=3 consecutive windows agreeing above 0.70 confidence before emitting
an event, and re-arm only after the signal returns to idle/normal. Trades a
small amount of detection latency for a large reduction in false positives.
Every production embedded system debounces; raw per-window output flickers far
too much to act on.

BANDWIDTH MATH (the business case for edge AI):
  Raw streaming: 62.5 Hz x 3 axes = ~225,000 samples/hour/vehicle;
    batched to 1 message/sec = 3,600 messages/hour.
  Event-only:    ~10 messages/hour (harsh brakes and swerves are rare).
  Reduction:     ~360x fewer messages, and far less storage and ingest cost.
  At fleet scale this is the difference between a viable architecture and an
  unaffordable one. It is also why the edge node should ship CONCLUSIONS
  rather than RAW DATA.

Gotcha: the IoT policy allowed publishing only to topic/fleet/*/telemetry, so
publishing to .../events required adding topic/fleet/*/events. Same class of
failure as the Day 5 bridge connect issue.
