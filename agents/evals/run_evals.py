"""Grade the diagnostics agent against the eval set (keyword match; grading is free).
Each CASE costs a few Bedrock Haiku calls. Run: python evals/run_evals.py
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from diagnostics_agent import build, ask

cases = json.load(open(os.path.join(os.path.dirname(__file__), "eval_set.json")))["cases"]
agent = build()
passed = 0
for c in cases:
    ans = ask(agent, c["question"], show_trace=False).lower()
    ok = all(k.lower() in ans for k in c["must_include"])
    passed += ok
    print(f"[{'PASS' if ok else 'FAIL'}] {c['id']}: expects {c['must_include']}")
    if not ok:
        print("        got:", ans[:160].replace(chr(10), ' '))
print(f"\nSCORE: {passed}/{len(cases)}")
