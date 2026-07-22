# Building a Zero-Hardware Edge-AI Driving-Behavior Detector with Edge Impulse, Wokwi, and AWS IoT Core

## The problem

Fleet operators want to know the moment a driver brakes hard or swerves. These events predict accidents, wear, and insurance risk — but they're rare, buried in a firehose of ordinary motion. The obvious move, streaming every sensor reading to the cloud, collapses at fleet scale.

An accelerometer sampling three axes at 62.5 Hz produces ~675,000 readings an hour per vehicle. Batched to one message per second, that's still ~3,600 messages an hour. Across a fleet of thousands, the bill is where the project dies in planning.

I built this to learn a range of technical skills by solving a real-world problem end to end.

## Why the edge

Four reasons push the decision onto the device, and all four apply here:

- **Latency.** A safety classification can't wait for a cloud round-trip.
- **Cost.** Streaming raw high-rate data from a fleet is expensive; sending only events is tiny.
- **Privacy.** Raw motion data is revealing; inferring locally means only labels leave the vehicle.
- **Offline.** Tunnels and dead zones must not disable a safety function.

The shift: the edge node ships conclusions, not raw data.

## The zero-hardware approach

I built and validated the entire edge pipeline without buying a single component.

- **Sensor:** a phone accelerometer streaming into Edge Impulse's mobile client at 62.5 Hz.
- **Embedded target:** a Wokwi-simulated ESP32 + MPU6050 running real Arduino/C++ firmware — I2C reads, Wi-Fi, MQTT — byte-for-byte what a physical board would run — simulator-first development, as automotive teams work.
- **Cloud:** AWS IoT Core, Lambda, DynamoDB, and SNS, all inside the free tier.

The whole pipeline is reproducible with a browser and a phone — no board, no soldering, no shipping. That's a real unlock for a proof of concept.

## Architecture

![Architecture](../../diagrams/architecture.svg)

The phone-trained model classifies four events — `idle`, `normal`, `harsh_brake`, `swerve` — from accelerometer windows. In the field, inference runs on the embedded node, which emits only detected events.

The cloud side is serverless. The Wokwi ESP32 publishes to a public MQTT broker; `bridge.py` subscribes and republishes into AWS IoT Core via per-device X.509 certificates — a standard edge-to-cloud broker pattern, not a workaround. The Rules Engine (`SELECT * FROM 'fleet/+/telemetry'`) routes to a Lambda that writes to DynamoDB and fires an SNS alert on threshold breaches. A Streamlit dashboard reads it for a live fleet view.

## The data collection story

I recorded four classes, twelve samples each, eight to ten seconds per sample, deliberately varying grip, position, and intensity so the model learned the physics rather than one memorized gesture.

The feature explorer told an honest story before training. `idle` formed a tight, isolated cluster — the absence of motion has a signature nothing else can imitate. The problem child was `swerve`, smeared across the space, overlapping `normal` and `harsh_brake`.

The reason is physics: an accelerometer measures linear acceleration plus gravity, not rotation — and a swerve is fundamentally rotational. A translated swerve looks like a harsh brake on a different axis; a rotational one looks like normal driving's gentle sway. Hence the tension: varying orientation improves generalization but erodes the cue separating these classes. The fix is sensor fusion — a gyroscope measures rotation directly.

## Results, with real numbers

The architecture (dense-20 → dense-10) reached **89.7% accuracy**, **0.90 weighted F1**, and **0.97 ROC**. Per-class F1: idle 1.00, normal 0.91, swerve 0.86, harsh_brake 0.79.

What surprised me most was how often `harsh_brake` got classified as `normal` — the opposite of the feature explorer's prediction that `swerve` would be the weak class.

The cause was label noise from windowing. Each ten-second `harsh_brake` sample held two or three jerks with calm gaps between; a two-second window sliding every second caught several of only the calm portion — indistinguishable from `normal`. The model wasn't wrong; the labels were. Fix: record events more densely, or crop to the event.

I also profiled quantization, expecting the usual "always quantize" win. The profiler estimates (ESP32 @240 MHz, EON Compiler) said otherwise:

| | int8 | float32 |
|---|---|---|
| Latency (total) | 30 ms | 32 ms |
| RAM | 2.2 K | 2.2 K |
| Flash (classifier) | 15.1 K | 14.7 K |
| Accuracy | 89.29% | 91.07% |

Quantization bought almost nothing — two milliseconds, zero RAM saved, int8 flash marginally *larger* — while costing 1.78 points of accuracy. The model is too tiny to benefit: savings scale with weight count and cancel against int8 metadata, and spectral feature extraction (~29 ms) dominates the 1–3 ms classifier anyway. The lesson: measure before optimizing.

For actionable output, `virtual_ecu.py` debounces — three consecutive windows above 0.70 confidence before emitting an event, re-arming only after the signal returns to idle — raw per-window output flickers far too much to act on.

As bandwidth: event-only reporting is ~10 messages per hour against ~3,600 for raw streaming — about **360× fewer**, plus far less storage and cost.

![Live inference demo](../../diagrams/demo.gif)

## An honest deployment finding

WebAssembly deployment worked perfectly — the model runs live in the phone's browser, no round-trip. The `.eim` Linux Python runner didn't: it loaded and reported its labels but failed at inference on macOS ARM (Python 3.9), and the documented workaround didn't help. The reportable finding: the vendor's "Linux" SDK isn't reliably cross-platform. I routed around it with a rule-based classifier on the same architecture, documenting the limitation openly.

## What I'd do next on physical silicon

- **Add a gyroscope** for sensor fusion — the one change that separates `swerve` cleanly.
- **Crop training samples to the event**, killing the windowing label noise that hurt `harsh_brake`.
- **Measure real latency and RAM on an ESP32**, replacing estimates with silicon truth.
- **Route detected events into DynamoDB and the dashboard**, closing the loop from edge conclusion to fleet insight.

Zero hardware got me a validated architecture, honest numbers, and a clear list of what silicon would change — exactly what a proof of concept is for.

*Repo: github.com/MohidMoneeb/fleetsense-pipeline*
