import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from app.config import get_settings
from app.models import ChatRequest, ChatResponse, HealthResponse, MetricsResponse
from app.security import InputSanitizer
from app.agent import ProductionAgent
from app.monitoring import MetricsCollector

load_dotenv()

limiter = Limiter(key_func=get_remote_address)
metrics = MetricsCollector()
sanitizer = InputSanitizer()
agent: ProductionAgent | None = None
cache: dict[str, tuple[str, str, float]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = ProductionAgent()
    yield


app = FastAPI(
    title="Production API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    s = get_settings()
    return HealthResponse(
        environment=s.app_env,
        checks={"agent": "ready" if agent else "not_initialized"},
    )


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = metrics.record_request(body.thread_id)

    is_safe, reason = sanitizer.check(body.message)
    if not is_safe:
        metrics.record_error()
        raise HTTPException(status_code=400, detail=reason)

    s = get_settings()
    now = time.time()
    cached_entry = cache.get(body.message)
    if cached_entry and (now - cached_entry[2]) < s.cache_ttl_seconds:
        metrics.record_cache_hit()
        return ChatResponse(
            response=cached_entry[0],
            thread_id=thread_id,
            model_used=cached_entry[1],
            cached=True,
            processing_time_ms=0.0,
        )

    metrics.record_cache_miss()
    start = time.perf_counter()
    try:
        result = agent.invoke(body.message)
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.record_latency(elapsed_ms / 1000)

        if result["error"]:
            metrics.record_error()
            raise HTTPException(status_code=502, detail=result["error"])

        cache[body.message] = (result["response"], result["model_used"], now)

        return ChatResponse(
            response=result["response"],
            thread_id=thread_id,
            model_used=result["model_used"],
            processing_time_ms=round(elapsed_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.record_latency(elapsed_ms / 1000)
        metrics.record_error()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    snap = metrics.snapshot()
    total = snap["requests_total"] or 1
    errors = snap["errors_total"]
    lat = snap["latency_sum"]
    hits = snap["cache_hits"]
    misses = snap["cache_misses"]
    total_cache = hits + misses or 1

    return MetricsResponse(
        total_requests=snap["requests_total"],
        total_errors=errors,
        error_rate=f"{(errors / total) * 100:.2f}%",
        avg_latency_ms=round((lat / snap["requests_total"]) * 1000, 2) if snap["requests_total"] else 0.0,
        cache_hit_rate=f"{(hits / total_cache) * 100:.2f}%",
        total_input_tokens=snap["tokens_input"],
        total_output_tokens=snap["tokens_output"],
    )


@app.post("/metrics/reset")
async def reset_metrics():
    metrics.reset()
    return {"detail": "Metrics reset"}