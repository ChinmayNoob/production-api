import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import json
from dotenv import load_dotenv

load_dotenv()

from app.monitoring import MetricsCollector
from langchain_openai import ChatOpenAI

metrics = MetricsCollector()
llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=20)

cache: dict[str, str] = {}


def call_with_metrics(prompt: str, thread_id: str):
    if prompt in cache:
        metrics.record_request(thread_id)
        metrics.record_cache_hit()
        metrics.record_latency(0.0)
        print(f"[CACHE HIT] thread={thread_id} -> {cache[prompt]}")
        return

    metrics.record_request(thread_id)
    metrics.record_cache_miss()

    start = time.perf_counter()
    try:
        resp = llm.invoke(prompt)
        elapsed = time.perf_counter() - start
        metrics.record_latency(elapsed)
        usage = resp.response_metadata.get("token_usage", {})
        metrics.record_tokens_input(usage.get("prompt_tokens", 0))
        metrics.record_tokens_output(usage.get("completion_tokens", 0))
        cache[prompt] = resp.content
        print(f"[LLM CALL] thread={thread_id} latency={elapsed:.3f}s -> {resp.content}")
    except Exception as e:
        metrics.record_error()
        metrics.record_latency(time.perf_counter() - start)
        print(f"[ERROR] thread={thread_id} -> {e}")


def test_metrics_with_llm():
    call_with_metrics("Say hello in one word", "thread-001")
    call_with_metrics("What is 2+2? One word answer", "thread-002")
    call_with_metrics("Say hello in one word", "thread-003")

    print("\n=== Metrics Snapshot ===")
    print(json.dumps(metrics.snapshot(), indent=2))

    snap = metrics.snapshot()
    assert snap["requests_total"] == 3
    assert snap["cache_hits"] == 1
    assert snap["cache_misses"] == 2
    assert snap["errors_total"] == 0
    assert snap["tokens_input"] > 0
    assert snap["tokens_output"] > 0
    assert len(snap["request_log"]) == 3
