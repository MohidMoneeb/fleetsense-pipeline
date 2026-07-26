"""Day 15 — one diagnostics agent wired to the 4 real fleet tools.
Run: python diagnostics_agent.py "Which vehicle looks least healthy right now and why?"
Each run makes a few Bedrock Haiku calls (cheap). Verify answers against the dashboard.
"""
import os, sys
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent
from tools import ALL_TOOLS

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION   = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM = ("You are a fleet diagnostics assistant. Use the tools to inspect real data before "
          "answering. Prefer get_fleet_status first, then drill in with the per-vehicle tools. "
          "For engine vehicles, predict_health gives RUL and a health band. Base every claim on "
          "tool output and cite the vehicle_id and numbers you saw.")

def build():
    model = ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0)
    return create_react_agent(model, tools=ALL_TOOLS, prompt=SYSTEM)

def ask(agent, question, show_trace=True):
    result = agent.invoke({"messages": [("user", question)]})
    if show_trace:
        for m in result["messages"]:
            k = m.__class__.__name__
            tcs = getattr(m, "tool_calls", None)
            if tcs:
                for tc in tcs: print(f"  · called {tc['name']}({tc['args']})")
            elif k == "ToolMessage":
                snippet = str(m.content)[:120]
                print(f"    ↳ {m.name}: {snippet}")
    return result["messages"][-1].content

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Which vehicle looks least healthy right now and why?"
    agent = build()
    print(f"Q: {q}\n")
    print("ANSWER:\n" + ask(agent, q))
