import json
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"

def chat(msg: str, tid: str):
    r = httpx.post(f"{BASE_URL}/chat", json={"message": msg, "thread_id": tid}, timeout=30)
    return r.json()

def metrics():
    r = httpx.get(f"{BASE_URL}/metrics", timeout=10)
    return r.json()

def reset():
    httpx.post(f"{BASE_URL}/metrics/reset", timeout=10)

print("Resetting metrics...")
reset()

print("\n--- Request 1 (LLM hit): 'Say hello' ---")
r1 = chat("Say hello", "thread-001")
print(json.dumps(r1, indent=2))
print(f"  cached={r1['cached']}  latency={r1['processing_time_ms']}ms")

print("\n--- Request 2 (LLM hit): 'What is 2+2? One word.' ---")
r2 = chat("What is 2+2? One word.", "thread-002")
print(json.dumps(r2, indent=2))
print(f"  cached={r2['cached']}  latency={r2['processing_time_ms']}ms")

print("\n--- Request 3 (CACHE hit): 'Say hello' (same as request 1) ---")
r3 = chat("Say hello", "thread-003")
print(json.dumps(r3, indent=2))
print(f"  cached={r3['cached']}  latency={r3['processing_time_ms']}ms")

print("\n=== Final Metrics ===")
m = metrics()
print(json.dumps(m, indent=2))

print(f"""
Summary:
  Total requests:  {m['total_requests']}
  Cache hits:      {m['cache_hit_rate']}  (request 3 matched request 1)
  Cache misses:    2  (requests 1 & 2 went to LLM)
  Avg latency:     {m['avg_latency_ms']}ms  (only LLM calls counted)
""")
