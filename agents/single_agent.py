"""Day 16 EXERCISE baseline — ONE mega-prompt agent with all tools and all jobs at once.
Compare its output to fleetpilot.py on the same scenario: the single agent tends to bury the
diagnosis, mix priorities, and produce an inconsistent report format.
Run: python single_agent.py
"""
import os, sys
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent
from tools import get_fleet_status, get_vehicle_history, get_recent_events, predict_health
from fleet_notes import read_fleet_notes, write_fleet_note

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION   = os.environ.get("AWS_REGION", "us-east-1")

MEGA_PROMPT = (
 "You are a one-stop fleet assistant. Inspect telemetry, find anomalies, prioritize them using "
 "severity and cost, check and update incident history, AND write a clean Markdown maintenance "
 "report — all yourself. Use the tools as needed.")

def build():
    m = ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0)
    return create_react_agent(m, tools=[get_fleet_status, get_vehicle_history, get_recent_events,
                              predict_health, read_fleet_notes, write_fleet_note], prompt=MEGA_PROMPT)

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Do a full fleet health check and give me a maintenance report."
    result = build().invoke({"messages": [("user", q)]})
    print("=== SINGLE-AGENT OUTPUT ===\n")
    print(result["messages"][-1].content)
