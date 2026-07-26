# FleetSense — Resume Bullets (Modules 1–3)

Project one-liner (for a header):
**FleetSense — Connected-vehicle telemetry + predictive-maintenance platform on AWS** (personal project). github.com/MohidMoneeb/fleetsense-pipeline

Pick 3–4 of the bullets below. Each is action verb → what → tech → result. Trim to fit.

### Module 1 — Ingestion & dashboard
- Built a serverless connected-vehicle telemetry pipeline on AWS (IoT Core, Rules Engine, Lambda, DynamoDB, SNS) ingesting MQTT sensor data from simulated fleets and a virtual ESP32 node, with per-device X.509 auth and least-privilege policies.
- Shipped a live Streamlit fleet dashboard with per-vehicle charts, threshold-based SNS email alerts, and a schema-tolerant design that renders heterogeneous device types without code changes.

### Edge AI (Module 1.5)
- Trained and deployed a TinyML driving-event classifier (Edge Impulse; idle/normal/harsh_brake/swerve) at 89.7% accuracy, running on-device in-browser via WebAssembly; profiled int8 vs float32 tradeoffs and quantified a ~360× bandwidth reduction from shipping edge conclusions instead of raw telemetry.

### Module 2 — Predictive-maintenance model
- Built a Remaining-Useful-Life regression model on NASA C-MAPSS turbofan data (XGBoost) achieving 16.55 RMSE on the held-out test set, using rolling-window features and leakage-safe entity-level splits; ran 8 tracked experiments and shipped an experiment log + model card.
- Tied model feature importances back to physical sensors (turbine-outlet temperature, HPC outlet pressure), confirming the model recovered the true HPC-degradation failure signature rather than spurious correlations.

### Module 3 — Deployment & monitoring
- Deployed the model as a container-image AWS Lambda behind API Gateway (POST /predict → RUL + health band), solving multi-arch image/OpenMP packaging issues; achieved ~1.0 s warm inference latency.
- Wired an EventBridge-scheduled poller that scores fleet telemetry into a DynamoDB health table surfaced on the dashboard, with CloudWatch alarms on errors and p95 latency; documented a Lambda-vs-SageMaker cost analysis justifying serverless for spiky, low-volume scoring.

### Tightest 4-bullet version (if space is tight)
- Built a serverless AWS telemetry pipeline (IoT Core → Lambda → DynamoDB → SNS) with a live Streamlit fleet dashboard.
- Deployed a TinyML driving-event classifier (89.7% acc) running on-device via WebAssembly; ~360× bandwidth reduction vs raw streaming.
- Trained an XGBoost Remaining-Useful-Life model on NASA C-MAPSS (16.55 test RMSE) with leakage-safe splits, an experiment log, and a model card.
- Deployed it as a container-image Lambda behind API Gateway with EventBridge-scheduled scoring and CloudWatch alarming (~1.0 s warm latency); documented Lambda-vs-SageMaker cost tradeoffs.
