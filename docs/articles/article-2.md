# A Multi-Agent Fleet Copilot on Amazon Bedrock with LangGraph

## The problem

A fleet dashboard tells you *what* every vehicle is doing. It doesn't tell you *what to do about it* — which vehicle to service first, whether a warning is new or a repeat, or how to write that up for a maintenance team. That's judgment work, and it's where a language-model agent earns its place: not to replace the dashboard, but to reason over it.

I built **FleetPilot**, a multi-agent copilot on top of an existing serverless fleet platform (AWS IoT Core → Lambda → DynamoDB, with a deployed predictive-maintenance model). It answers questions like "which vehicle looks least healthy right now, and why?" by calling the same infrastructure the dashboard uses — then prioritizing, remembering, and reporting.

I built it mostly to learn how real agent systems are structured end to end — tools, orchestration, memory, and guardrails — by solving a problem I already had infrastructure for.

## Why multiple agents, not one big prompt

The honest answer isn't "because multi-agent is trendy." It's separation of concerns. FleetPilot is three specialists coordinated by a supervisor:

- **Diagnostics Agent** — read-only telemetry tools; finds and explains anomalies.
- **Fleet Ops Agent** — takes the diagnosis, prioritizes by severity and cost, checks incident history, and decides what's worth flagging.
- **Report Writer** — *no tools*; turns findings into a clean, consistently formatted Markdown report.

A **supervisor** routes between them: diagnostics → ops → report.

Three benefits fall out that a single mega-prompt agent doesn't get for free. **Focused prompts:** each agent has one job, so the diagnosis stays distinct from the prioritization and the formatting — a single agent juggling all three tends to bury the diagnosis and mix priorities into the prose. **Per-role permissions:** the Diagnostics Agent is read-only, only Ops can write notes, the Report Writer can't touch data. **Consistent output:** the writer only sees clean findings, so the format doesn't drift.

Multi-agent isn't free — more model calls means more tokens and latency. It's right when separation of concerns and per-role permissions matter, wrong for a trivial one-shot task.

## Architecture

FleetPilot uses **LangGraph** and `langgraph-supervisor`, on **Amazon Bedrock** with Claude Haiku 4.5 (via a US cross-region inference profile). Each agent is a LangGraph ReAct agent; the supervisor is a graph whose nodes are the agents.

*(Insert your exported graph image here.)*

The tools wrap real infrastructure, not mocks: latest telemetry per vehicle and per-vehicle history from DynamoDB, recent driving events, and a `predict_health` tool that calls the deployed Remaining-Useful-Life model and returns an RUL plus a green/yellow/red band.

## Memory design — the part that makes it feel intelligent

Two kinds of memory, deliberately separated. **Short-term** is conversation state: a LangGraph checkpointer keyed by a per-session thread id, so follow-ups keep context. **Long-term** is a DynamoDB **FleetNotes** table of past incidents that persists across runs. Before flagging a vehicle, the Ops Agent reads its notes; after deciding, it writes a one-line summary. So a later run can say *"sim-vehicle-02 showed this same voltage sag last week"* — recurrence detection out of persistent memory, not a single conversation's context. That split — ephemeral conversation state vs. durable cross-run knowledge — maps onto the checkpointer-vs-store distinction.

## Guardrails

Agents that touch production infrastructure need rails, and the load-bearing one is not a prompt. **Least-privilege IAM:** FleetPilot's identity is read-only on all telemetry tables and can write only to FleetNotes, with an explicit **Deny** on telemetry writes — verified, a telemetry write returns AccessDenied. Even a fully compromised agent cannot corrupt fleet data. Plus an **iteration cap**, a **per-call output cap**, a **per-session token budget**, and a **scope + injection-resistance prompt** that refuses out-of-scope questions and treats all tool output as data, never instructions.

## Evaluation — grading against known answers

FleetPilot has a 15-case eval set with expected answers defined from verified ground truth, including out-of-scope and injection cases. Current pass rate: **13/15**, kept honest — both misses are grading artifacts (a "harsh brake" vs "harsh_brake" formatting mismatch, and an ambiguous "past incidents" question answered from the events table instead of notes), not wrong answers. A suspicious 15/15 would be less credible than a documented 13/15.

Separately, three prompt-injection attacks — direct, **indirect** via a poisoned FleetNotes record, and a jailbreak — were all resisted. The indirect case is the interesting one: the malicious text arrived *inside legitimate tool output*, and the agent flagged it as a suspected injection and refused. Indirect injection through retrieved data is the realistic threat for tool-using agents.

What surprised me most was how well a small, cheap model handled that indirect injection — it named the poisoned note as suspicious rather than obeying it, which I hadn't expected from Haiku.

## Honest limitations

**Cost:** multi-agent runs are token-heavy; on a free-tier Bedrock quota I hit the daily token cap more than once. Defensible, not cheap. **Stand-in data:** the RUL model is trained on NASA's C-MAPSS turbofan dataset, and the "engine" vehicles are seeded C-MAPSS trajectories — the plumbing is real, the domain transfer is future work. **Coarse evals:** keyword matching is blunt and produced two false failures; an LLM-as-judge grader is the next step. **Prompt defenses are necessary, not sufficient:** they can be bypassed by novel phrasing, which is exactly why the read-only IAM boundary — not the prompt — is what actually protects the data.

## What I'd do next

Swap keyword grading for an LLM judge; run the agent under its restricted IAM identity in a deployed service rather than locally; and, the real unlock, retrain the RUL model on genuine vehicle telemetry so the predictive-maintenance answers are about cars, not turbofans.

*Repo: github.com/MohidMoneeb/fleetsense-pipeline*
