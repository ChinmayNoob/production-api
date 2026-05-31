from pydantic import BaseModel,Field
from datetime import datetime


class ChatRequest(BaseModel):
    """Incoming chat request"""

    message:str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message to the agent"
    )
    thread_id:str = Field(
        default = "default",
        description="The thread ID for conversation context. Defaults to 'default'."
    )

class ChatResponse(BaseModel):
    """Response from the agent"""
    response:str
    thread_id:str
    model_used:str
    cached:bool = False
    processing_time_ms: float
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")     

class HealthResponse(BaseModel):
    """Health check response"""
    status:str = "healthy"
    environment:str
    version:str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    checks:dict = {}

class MetricsResponse(BaseModel):
    """Metrics endpoint response"""
    total_requests:int
    total_errors:int
    error_rate:str
    avg_latency_ms:float
    cache_hit_rate:str
    total_input_tokens:int
    total_output_tokens:int