"""Load-test the /predict endpoint: 50 rapid requests, report cold vs warm latency.
Usage: python3 load_test.py https://<api-id>.execute-api.us-east-1.amazonaws.com/predict
"""
import sys, json, time, statistics, urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else None
if not URL:
    print("usage: python3 load_test.py <predict-url>"); sys.exit(1)

payload = json.load(open("sample_payload.json"))
data = json.dumps(payload).encode()

lat = []
for i in range(50):
    t0 = time.time()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        body = r.read()
    ms = (time.time() - t0) * 1000
    lat.append(ms)
    if i == 0:
        print(f"request  1 (cold?): {ms:7.1f} ms  -> {body.decode()}")
    elif i < 4:
        print(f"request {i+1:2d} (warm) : {ms:7.1f} ms")

print("\n--- latency summary (ms) ---")
print(f"cold (req 1)     : {lat[0]:7.1f}")
warm = lat[1:]
print(f"warm min/mean/max: {min(warm):.1f} / {statistics.mean(warm):.1f} / {max(warm):.1f}")
print(f"warm p50 / p95   : {statistics.median(warm):.1f} / {sorted(warm)[int(len(warm)*0.95)]:.1f}")
