"""Day 14 — confirm Bedrock plumbing BEFORE touching LangGraph.
1) lists the Anthropic model/profile IDs your account can use
2) makes one Converse call to confirm creds + model access work
Run: python3 bedrock_smoketest.py
"""
import os, boto3
from botocore.exceptions import ClientError

REGION   = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# --- 1) what can this account actually call? ---
print("=== Anthropic inference profiles available in", REGION, "===")
try:
    bd = boto3.client("bedrock", region_name=REGION)
    profs = bd.list_inference_profiles().get("inferenceProfileSummaries", [])
    ids = [p["inferenceProfileId"] for p in profs if "anthropic" in p["inferenceProfileId"].lower()]
    for i in ids: print("  ", i)
    if not ids:
        print("  (none listed — check Model Access in the Bedrock console)")
except ClientError as e:
    print("  could not list profiles:", e.response["Error"]["Code"])

# --- 2) one real Converse call ---
print(f"\n=== Converse test with MODEL_ID = {MODEL_ID} ===")
try:
    rt = boto3.client("bedrock-runtime", region_name=REGION)
    resp = rt.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": "Reply with exactly: plumbing works"}]}],
        inferenceConfig={"maxTokens": 20, "temperature": 0},
    )
    print("SUCCESS:", resp["output"]["message"]["content"][0]["text"])
except ClientError as e:
    code = e.response["Error"]["Code"]
    print(f"FAILED ({code}): {e.response['Error']['Message']}")
    if code in ("AccessDeniedException", "ValidationException"):
        print("→ Fix: enable model access in the Bedrock console, or set MODEL_ID to one of the IDs listed above.")
