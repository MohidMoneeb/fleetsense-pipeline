"""Day 15 — verify the 4 tools against REAL AWS data. NO Bedrock, NO model, $0 credits.
Run this first to confirm the infrastructure wiring before spending any agent calls.
Run: python check_tools.py
"""
from tools import get_fleet_status, get_vehicle_history, get_recent_events, predict_health

print("=== get_fleet_status() ===")
fleet = get_fleet_status.invoke({})
for r in fleet:
    print(" ", r.get("vehicle_id"), "| fields:", [k for k in r if k not in ("vehicle_id","timestamp")][:6])
ids = [r["vehicle_id"] for r in fleet]
engine_ids = [v for v in ids if v.startswith("engine")]

if engine_ids:
    v = engine_ids[0]
    print(f"\n=== get_vehicle_history('{v}') ===")
    print("  rows:", len(get_vehicle_history.invoke({"vehicle_id": v})))
    print(f"\n=== get_recent_events('{v}') ===")
    print(" ", get_recent_events.invoke({"vehicle_id": v}))
    print(f"\n=== predict_health for each engine vehicle ===")
    for v in engine_ids:
        print(" ", v, "->", predict_health.invoke({"vehicle_id": v}))
print("\nAll tools returned. Cross-check these against your dashboard.")
