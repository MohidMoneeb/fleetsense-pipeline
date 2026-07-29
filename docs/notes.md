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

# Day 8 - Technical writing + repo polish

- Shipped Builder Center article #1: "Building a Zero-Hardware Edge-AI
  Driving-Behavior Detector with Edge Impulse, Wokwi, and AWS IoT Core".
- Repo polish: Wokwi diagram screenshot, demo GIF (WASM browser inference),
  README rewrite (fixed stale Day 4 status, added ESP32/bridge/vECU/events,
  profiler table, 360x bandwidth math).
- Editing exercise: cut the draft ~20% (1233 -> ~985 words). Adverbs, hedges,
  and throat-clearing lead-ins were the easy 250 to lose.
- The novel angle that carried the piece: zero hardware. Phone as sensor,
  Wokwi as the embedded target, AWS free tier as the cloud - fully reproducible.
- No AWS/IoT policy changes needed today.

Published: https://builder.aws.com/content/3GqGnUj7Qexb9HPpRK10fNs5Eei/building-a-zero-hardware-edge-ai-driving-behavior-detector-with-edge-impulse-wokwi-and-aws-iot-core

# Day 9 - Predictive maintenance EDA: NASA C-MAPSS (FD001)

- Loaded FD001: 100 engines run to failure, 21 sensors + 3 settings per cycle,
  20,631 rows, no missing values. Lifetimes range ~128-362 cycles.
- Sensor triage by variance: s_1, s_5, s_10, s_16, s_18, s_19 are flat
  (zero variance under FD001's single operating condition) and get dropped;
  s_6 is near-constant. The rest (s_2, s_3, s_4, s_7, s_11, s_12, s_15, s_17,
  s_20, s_21, ...) carry a clear degradation trend - noisy but directional.
- RUL label = max_cycle(engine) - current_cycle. Clipped at 125: early life is
  "healthy" and sensors look identical whether RUL is 250 or 200, so an unclipped
  target forces the model to fit noise. Clip encodes piecewise-linear degradation.
  Standard C-MAPSS convention.
- Three problem framings: RUL regression (used here), anomaly detection,
  health-zone classification.
- Product-thinking translation for FleetSense: engine -> vehicle, cycle -> trip,
  21 sensors -> OBD-II/CAN channels, run-to-failure -> telemetry to fault,
  RUL -> trips/miles to service. C-MAPSS (unit, cycle) maps onto FleetSense's
  (vehicle_id, timestamp) directly.
- Artifact: notebooks/01_cmapss_eda_FD001.ipynb (executed, plots embedded).
  Data gitignored; notebooks/fetch_data.sh reproduces it.
- Gotcha pre-empted: computed the flat-sensor list rather than trusting a
  hardcoded one - s_6 is near-constant but not zero-variance, easy to miscount.

# Day 10 - Feature engineering + honest baseline (FD001)

- Features: dropped 6 flat sensors, added rolling mean/std/slope over 5/10/20
  cycle windows, computed per-engine so no info crosses engine boundaries.
- Split by UNIT (80 train / 20 test), never by row. Baselines on clipped RUL:
  LinearRegression 17.66 RMSE, RandomForest 18.91 RMSE.
- Model fails most at high RUL (early, healthy life). Acceptable for a
  maintenance product: decisions only matter near the service threshold, where
  the model is accurate. The clip at 125 encodes exactly this.
- LEAKAGE EXPERIMENT: same features/model split by row instead of engine gave
  RMSE 10.55 - looks 1.8x better and is a lie. Why it lied (two sentences):
  Because rolling features summarize an engine's own recent history, a row split
  puts different cycles of the same engine on both sides, so the model is quietly
  tested on engines it trained on and its features encode those engines'
  trajectories. That RMSE measures memorization of known engines, not prediction
  on unseen ones, so it collapses the moment a genuinely new engine arrives.
- Artifact: notebooks/02_feature_baseline_FD001.ipynb (executed, plots embedded).

# Day 11 - Better models + experiment discipline (FD001)

- Ran 8 experiments on one fixed engine-level split (comparable RMSE, failures kept).
  Winner: tuned XGBoost, val RMSE 17.02 (vs RandomForest 18.91, LinReg 17.66,
  LightGBM tuned 17.20). Feature-trimming hurt -> std/slope carry real signal.
- Froze winner (retrained on all 100 engines) with joblib: notebooks/rul_xgb_model.joblib.
  Official test_FD001: RMSE 16.55, NASA asymmetric score 632.
- Feature importance -> physics: top sensors are s_4 (T50, LPT outlet temp, ~40%),
  s_15 (BPR, bypass ratio), s_11 (Ps30, HPC outlet static pressure). FD001's fault
  mode is HPC degradation, so a model leaning on gas-path temperature and HPC outlet
  pressure is physically correct - it recovered the failure signature, not noise.
- Artifacts: experiments.md (honest table), model_card.md (intended use, metrics,
  failure modes, what NOT to trust), notebooks/03_models_experiments_FD001.ipynb.

# Day 13 - Module 3 ship-day

- Added inference-flow architecture diagram (diagrams/inference_architecture.svg):
  real-time API path, scheduled scoring, monitoring.
- Notebooks are restart-run-all clean (produced by fresh top-to-bottom execution).
  Local nbconvert re-verify skipped: newest jupyter stack needs Python 3.10+.
- README carries metrics (test RMSE 16.55), Lambda-vs-SageMaker cost analysis,
  and the inference diagram.
- Drafted resume bullets for Modules 1-3 (docs/resume_bullets_modules_1-3.md).
- Health panel verified: engine-critical scored RUL 2.24 -> red alongside 5 healthy engines.

# Day 14 - AI agents: LangGraph + Bedrock

- Confirmed Bedrock Converse from boto3 (bedrock_smoketest.py). Model auto-enabled
  on first invoke after submitting Anthropic use-case details. Working profile id:
  us.anthropic.claude-haiku-4-5-20251001-v1:0 (US cross-region inference profile,
  NOT the bare model id).
- Built a minimal LangGraph ReAct agent, one calculator tool (agent_calculator.py).
  Trace: Human -> AI(tool_call multiply) -> Tool(896) -> AI(tool_call add 896+46)
  -> Tool(942) -> AI(final 942). Model chained the first result into the second
  call itself - that reason/act/observe loop is what makes it an agent.
- EXERCISE (agent_lying_tool.py): tool docstring says "add", code multiplies;
  agent trusts the docstring and returns 42 for 6+7. Lesson: tool descriptions
  ARE prompts; agents are only as good as their tool interfaces.
- Env: agent stack on a Python 3.12 venv (agent-venv, gitignored), retiring the
  system-3.9 problem.

# Day 15 - Real tools: the agent meets the fleet

- Built 4 read-only, typed, single-purpose tools wrapping existing infra
  (agents/tools.py): get_fleet_status, get_vehicle_history, get_recent_events,
  predict_health (calls the Module 3 /predict API).
- Verified every tool against real data with check_tools.py at ZERO model cost;
  output matched the dashboard exactly (engine-critical 2.24 red, engine-003
  50.57 yellow, rest green; heterogeneous schemas handled).
- Wired all 4 into one diagnostics agent (agents/diagnostics_agent.py).
- First eval set: 5 questions with known answers (agents/evals/eval_set.json),
  graded by run_evals.py (keyword match). least_healthy expected = engine-critical.
  Full grading run deferred (Bedrock credit ceiling); verifying tools first is the
  cheap, correct order.
- Design note: tools read-only, single-purpose, docstrings written FOR the model.

# Day 16 - Multi-agent supervisor + long-term memory

- FleetPilot: supervisor routes Diagnostics (read-only telemetry) -> Fleet Ops
  (prioritize by severity+cost heuristic; reads/writes FleetNotes) -> Report Writer
  (Markdown, no tools). agents/fleetpilot.py. Graph nodes: supervisor,
  diagnostics_agent, ops_agent, report_writer.
- Short-term memory: InMemorySaver checkpointer keyed by thread_id (conversation
  state). Long-term memory: DynamoDB FleetNotes table (agents/fleet_notes.py) -
  persists incidents across runs. Seeded a past sim-vehicle-02 voltage sag so the
  ops agent detects recurrence ("same sag last week") on the first run.
- Why multi-agent beats one mega-prompt here (defensible, not hype):
  * Separation of concerns: each agent has ONE job and a focused prompt, so the
    diagnosis stays distinct from prioritization stays distinct from formatting.
  * Different tools/permissions per role: Diagnostics is read-only; only Ops can
    write FleetNotes; Report Writer has no tools at all (can't touch data).
  * Consistent report format: the writer sees only clean findings, so formatting
    doesn't drift the way a single agent's does when juggling all jobs at once.
  * Single mega-agent failure modes observed: buries the diagnosis, mixes
    priorities into the report, inconsistent formatting run to run.
- Cost note: multi-agent uses more tokens (more model calls) - justified when
  separation of concerns and per-role permissions matter, not for trivial tasks.

# Day 17 - Guardrails, evaluation, chat UI

- Hardened FleetPilot: read-only chat tools, recursion_limit=12, max_tokens=1024,
  per-session token budget (60k), scope + injection-resistance prompt (chat_agent.py).
- Least-privilege IAM: fleetpilot-agent user, read-only on telemetry tables, write
  only FleetNotes, explicit Deny on telemetry writes. Verified: telemetry PutItem
  -> AccessDenied; FleetNotes PutItem -> OK. (agents/iam/fleetpilot-agent-policy.json)
- Streamlit "Ask FleetPilot" chat view added to the dashboard (venv), conversation
  memory per session, live token-budget bar (chat_ui.py).
- Expanded eval set to 15 cases incl. out-of-scope + injection (evals/eval_set.json).
  Pass rate: 13/15 (both misses were grading artifacts: harsh_brake vs "harsh brake"
  formatting; and "past incidents" read events not FleetNotes). Injection + out-of-scope
  cases all passed.
- Injection exercise: 3 attacks (direct, indirect via poisoned FleetNotes, jailbreak) -
  all resisted; indirect injection was explicitly flagged as suspicious. Documented in
  docs/security-notes.md.
