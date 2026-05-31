import time
from app.cache import ResponseCache

class LLMOptimizer:
    """Optimizes LLM API calls using intelligent caching"""
    
    def __init__(self, cache_ttl=300):
        self.cache = ResponseCache(ttl_seconds=cache_ttl)
        self.api_call_count = 0
        self.cache_hit_count = 0
    
    def get_response(self, question: str) -> tuple[str, bool]:
        """
        Get LLM response with caching
        
        Returns: (response_text, was_cached)
        """
        # Check cache first
        cached_response = self.cache.get(question)
        if cached_response is not None:
            self.cache_hit_count += 1
            return cached_response, True
        
        # Simulate LLM API call
        self.api_call_count += 1
        response = self._mock_llm_call(question)
        
        # Cache the response
        self.cache.set(question, response)
        return response, False
    
    def _mock_llm_call(self, question: str) -> str:
        """Simulates LLM API with realistic delay"""
        time.sleep(1)  # Simulate API latency
        return f"LLM Response to: {question}"
    
    def get_stats(self) -> dict:
        """Get comprehensive cache and performance stats"""
        cache_stats = self.cache.stats
        total_requests = self.api_call_count + self.cache_hit_count
        
        return {
            "total_requests": total_requests,
            "api_calls_made": self.api_call_count,
            "cache_hits": self.cache_hit_count,
            "time_saved_seconds": self.cache_hit_count * 1,  # Assuming 1s per API call
            "cost_saved_usd": self.cache_hit_count * 0.002,  # Assuming $0.002 per API call
            "cache_efficiency": f"{(self.cache_hit_count / total_requests * 100):.1f}%" if total_requests > 0 else "0%",
            **cache_stats
        }

# Simulation scenarios
def simulate_real_world_usage():
    """Simulates real-world multi-user LLM usage patterns"""
    
    optimizer = LLMOptimizer(cache_ttl=600)  # 10 minute cache
    
    print("=" * 70)
    print("Real-World LLM Cache Performance Simulation")
    print("=" * 70)
    print()
    
    # Scenario 1: Multiple users asking the same questions
    print("SCENARIO 1: Popular Questions (Same question asked multiple times)")
    print("-" * 70)
    
    popular_questions = [
        "What is Python?", "What is Python?", "What is Python?",
        "How do I learn Python?", "How do I learn Python?",
        "What is JavaScript?", "What is JavaScript?"
    ]
    
    start_time = time.time()
    for i, question in enumerate(popular_questions, 1):
        response, was_cached = optimizer.get_response(question)
        status = "[CACHED]" if was_cached else "[API CALL]"
        print(f"{i}. {status} {question}")
    
    scenario1_time = time.time() - start_time
    
    # Scenario 2: Different questions
    print()
    print("SCENARIO 2: Diverse Questions (All different)")
    print("-" * 70)
    
    diverse_questions = [
        "What is machine learning?",
        "How does a neural network work?",
        "What is the difference between AI and ML?",
        "Explain REST APIs",
        "What is Docker?"
    ]
    
    start_time = time.time()
    for i, question in enumerate(diverse_questions, 1):
        response, was_cached = optimizer.get_response(question)
        status = "[CACHED]" if was_cached else "[API CALL]"
        print(f"{i}. {status} {question}")
    
    scenario2_time = time.time() - start_time
    
    # Scenario 3: Mixed pattern
    print()
    print("SCENARIO 3: Mixed Pattern (Realistic usage)")
    print("-" * 70)
    
    mixed_questions = [
        "What is Python?",           # Will cache
        "How to code in Python?",   # New
        "What is Python?",           # Cache hit
        "Explain loops in Python",  # New
        "What is Python?",           # Cache hit
        "How to code in Python?",   # Cache hit
    ]
    
    start_time = time.time()
    for i, question in enumerate(mixed_questions, 1):
        response, was_cached = optimizer.get_response(question)
        status = "[CACHED]" if was_cached else "[API CALL]"
        print(f"{i}. {status} {question}")
    
    scenario3_time = time.time() - start_time
    
    # Results
    print()
    print("=" * 70)
    print("PERFORMANCE RESULTS")
    print("=" * 70)
    
    stats = optimizer.get_stats()
    
    print(f"\nOverall Statistics:")
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  API Calls Made: {stats['api_calls_made']}")
    print(f"  Cache Hits: {stats['cache_hits']}")
    print(f"  Cache Efficiency: {stats['cache_efficiency']}")
    
    print(f"\nCost & Time Savings:")
    print(f"  Time Saved: {stats['time_saved_seconds']:.1f} seconds")
    print(f"  Cost Saved: ${stats['cost_saved_usd']:.4f} USD")
    print(f"  Cached Entries: {stats['cached_entries']}")
    
    print(f"\nScenario Breakdown:")
    print(f"  Scenario 1 (Popular questions): {scenario1_time:.1f}s")
    print(f"  Scenario 2 (Diverse questions): {scenario2_time:.1f}s")
    print(f"  Scenario 3 (Mixed pattern): {scenario3_time:.1f}s")
    
    print(f"\nWithout Cache Analysis:")
    print(f"  Total API calls needed: {stats['total_requests']}")
    print(f"  Total time needed: {stats['total_requests'] * 1:.1f}s")
    print(f"  Total cost: ${stats['total_requests'] * 0.002:.4f}")
    
    print(f"\nWith Cache Analysis:")
    print(f"  Actual API calls: {stats['api_calls_made']}")
    print(f"  Actual time: {scenario1_time + scenario2_time + scenario3_time:.1f}s")
    print(f"  Actual cost: ${stats['api_calls_made'] * 0.002:.4f}")
    
    print(f"\nEfficiency Gains:")
    print(f"  Time reduction: {((stats['total_requests'] - stats['api_calls_made']) / stats['total_requests'] * 100):.1f}%")
    print(f"  Cost reduction: {((stats['total_requests'] - stats['api_calls_made']) / stats['total_requests'] * 100):.1f}%")

if __name__ == "__main__":
    simulate_real_world_usage()