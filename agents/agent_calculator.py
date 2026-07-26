"""Day 14 — minimal LangGraph ReAct agent on Amazon Bedrock with ONE tool (calculator).
Run:  python3 agent_calculator.py
Requires: Bedrock model access enabled + AWS creds configured (aws configure).
Set MODEL_ID to an inference-profile ID your account can access (see bedrock_smoketest.py).
"""
import os
from langchain_core.tools import tool
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

# US cross-region inference profile for Claude Haiku 4.5 (cheap iteration).
# VERIFY this string with bedrock_smoketest.py and replace if your account shows a different one.
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION   = os.environ.get("AWS_REGION", "us-east-1")

@tool
def calculator(a: float, b: float, op: str) -> float:
    """Do arithmetic on two numbers. op is one of: add, subtract, multiply, divide.
    Returns the numeric result."""
    if op == "add":      return a + b
    if op == "subtract": return a - b
    if op == "multiply": return a * b
    if op == "divide":   return a / b
    raise ValueError(f"unknown op: {op}")

def build_agent():
    model = ChatBedrockConverse(model=MODEL_ID, region_name=REGION, temperature=0)
    return create_react_agent(model, tools=[calculator])

def print_trace(result):
    """Print every message in the agent's run so nothing is mysterious."""
    for i, m in enumerate(result["messages"]):
        kind = m.__class__.__name__
        tool_calls = getattr(m, "tool_calls", None)
        print(f"\n[{i}] {kind}")
        if getattr(m, "content", None):
            print(f"    content: {m.content}")
        if tool_calls:
            for tc in tool_calls:
                print(f"    -> tool_call: {tc['name']}({tc['args']})")
        if kind == "ToolMessage":
            print(f"    <- tool_result: {m.content}")

if __name__ == "__main__":
    agent = build_agent()
    q = "What is 128 times 7, and then add 46 to that?"
    print(f"USER: {q}")
    result = agent.invoke({"messages": [("user", q)]})
    print_trace(result)
    print("\nFINAL:", result["messages"][-1].content)
