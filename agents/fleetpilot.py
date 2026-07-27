"""Day 16 — FleetPilot: a three-role supervisor multi-agent graph with long-term memory.
Roles: Diagnostics (read-only telemetry) -> Fleet Ops (prioritize + write/read FleetNotes)
-> Report Writer (Markdown report, no tools). A supervisor routes between them.
Short-term memory: InMemorySaver checkpointer (conversation state per thread).
Long-term memory: DynamoDB FleetNotes (persists across runs).

Run: python fleetpilot.py            (uses default scenario)
Each run makes several Bedrock calls (supervisor + agents). Keep runs minimal.
"""
import os, sys
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_supervisor import create_supervisor

from tools import get_fleet_status, get_vehicle_history, get_recent_events, predict_health
from fleet_notes import read_fleet_notes, write_fleet_note

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION   = os.environ.get("AWS_REGION", "us-east-1")

def _model():
    return ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0)

DIAG_PROMPT = (
 "You are the Diagnostics Agent. You have READ-ONLY telemetry tools. Inspect the fleet, "
 "find vehicles with anomalies (red/yellow health bands, low RUL, recent harsh events), and "
 "explain each anomaly with the specific vehicle_id and numbers. Do not prioritize or write "
 "reports — just report what you found, then hand back to the supervisor.")

OPS_PROMPT = (
 "You are the Fleet Ops Agent. Given the diagnostics findings, PRIORITIZE across vehicles. "
 "Severity heuristic: red band = urgent (high cost of failure), yellow = monitor, green = ignore; "
 "a recorded harsh-driving event raises priority one level. For each vehicle you care about, FIRST "
 "call read_fleet_notes to check if this is recurring (say so explicitly if it is). Decide what is "
 "worth flagging. Then call write_fleet_note to save a one-line incident summary for each flagged "
 "vehicle so future runs remember it. Hand your prioritized list back to the supervisor.")

REPORT_PROMPT = (
 "You are the Report Writer. You have NO tools. Turn the ops findings into a clean Markdown "
 "maintenance report with: a one-line summary, a table (vehicle | severity | issue | action), "
 "and a short 'recurring issues' note if any vehicle was flagged as repeat. Be concise and consistent.")

SUPERVISOR_PROMPT = (
 "You manage three agents. Route in order: diagnostics_agent (find anomalies) -> ops_agent "
 "(prioritize + record notes) -> report_writer (final Markdown report). Call each once, in that "
 "order, then return the report_writer's report as the final answer.")

def build():
    m = _model()
    diagnostics = create_react_agent(m, tools=[get_fleet_status, get_vehicle_history,
                                     get_recent_events, predict_health],
                                     name="diagnostics_agent", prompt=DIAG_PROMPT)
    ops = create_react_agent(m, tools=[read_fleet_notes, write_fleet_note, predict_health],
                             name="ops_agent", prompt=OPS_PROMPT)
    report = create_react_agent(m, tools=[], name="report_writer", prompt=REPORT_PROMPT)
    supervisor = create_supervisor([diagnostics, ops, report], model=m, prompt=SUPERVISOR_PROMPT)
    return supervisor.compile(checkpointer=InMemorySaver())

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Do a full fleet health check and give me a maintenance report."
    app = build()
    cfg = {"configurable": {"thread_id": "fleet-run-1"}}
    result = app.invoke({"messages": [("user", q)]}, cfg)
    print("=== FINAL REPORT ===\n")
    print(result["messages"][-1].content)
