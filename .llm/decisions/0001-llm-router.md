# ADR 0001 — LLM Router Architecture

## Status
Accepted

## Context
The system integrates with multiple LLM providers (OpenAI, Bedrock/Gemini) for agent reasoning. To maximize reliability and minimize latency variance, we need a router that:
1. Distributes load across providers
2. Falls back gracefully on failure
3. Respects token budgets and rate limits
4. Provides observability for cost and performance

## Decision
Implement a **circuit-breaker + fallback router** with:
- Primary provider: OpenAI (gpt-4-turbo)
- Fallback provider: Anthropic (claude-3-sonnet) or Bedrock (via OpenAI-compatible adapter)
- Timeout: 30 seconds per LLM call
- Retry: up to 2 attempts on rate limit or timeout
- Healthcheck: periodic provider availability probe

**Router Interface:**
```python
class LLMRouter:
  async def invoke(
    agent: str,
    prompt: str,
    model: Optional[str] = None
  ) -> Tuple[str, Metadata]:
    """
    Route request to best available provider.
    Returns (completion, metadata with provider, latency, tokens, cost).
    """
```

## Rationale
- **Circuit breaker:** Prevents cascading failures if a provider goes down
- **Fallback:** Ensures system continues working even if primary provider fails
- **Metadata logging:** Enables cost tracking and performance analysis
- **No numeric computation in LLM:** All stats/analysis done in Python; LLM only interprets and narrates

## Consequences
- Slight latency overhead (~100ms) for provider health checks
- Potential minor inconsistencies between provider outputs (mitigated by structured prompts)
- Cost slightly higher due to dual-provider setup (acceptable for governance)
- Requires async I/O throughout backend stack

## Notes
- LLM output validation happens in agent prompts (e.g., "return JSON only")
- Hallucination detection: Analytics Agent validates all claims against data
- Future: dynamic routing based on query complexity/cost budget
