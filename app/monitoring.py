import logging
import json
import time
import uuid
import threading

from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Any

class JSONFormatter(logging.Formatter):

    def format(self,record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data"):
            log_obj["extra"] = record.extra_data

        return json.dumps(log_obj)

class MetricsCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._latency_sum = 0.0
        self._tokens_input = 0
        self._tokens_output = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._request_log: list[dict] = []

    @property
    def requests_total(self) -> int:
        return self._requests_total

    @property
    def errors_total(self) -> int:
        return self._errors_total

    @property
    def latency_sum(self) -> float:
        return self._latency_sum

    @property
    def tokens_input(self) -> int:
        return self._tokens_input

    @property
    def tokens_output(self) -> int:
        return self._tokens_output

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    @property
    def cache_misses(self) -> int:
        return self._cache_misses

    def record_request(self, thread_id: str | None = None) -> str:
        with self._lock:
            self._requests_total += 1
            tid = thread_id or str(uuid.uuid4())
            self._request_log.append({
                "thread_id": tid,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            })
            return tid

    def record_error(self) -> None:
        with self._lock:
            self._errors_total += 1

    def record_latency(self, seconds: float) -> None:
        with self._lock:
            self._latency_sum += seconds

    def record_tokens_input(self, count: int) -> None:
        with self._lock:
            self._tokens_input += count

    def record_tokens_output(self, count: int) -> None:
        with self._lock:
            self._tokens_output += count

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def snapshot(self) -> dict:
        return {
            "requests_total": self._requests_total,
            "errors_total": self._errors_total,
            "latency_sum": self._latency_sum,
            "tokens_input": self._tokens_input,
            "tokens_output": self._tokens_output,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "request_log": self._request_log,
        }

    def reset(self) -> None:
        with self._lock:
            self._requests_total = 0
            self._errors_total = 0
            self._latency_sum = 0.0
            self._tokens_input = 0
            self._tokens_output = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._request_log.clear()
    
    def get_logger(name:str = "production_api")-> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        return logger