# LLM Configuration Guide

## Overview
This document covers Claude and LLM provider setup for the Agentic Policy Analytics Platform.

## Environment Setup

### 1. API Keys
Create a `.env` file in the project root with:

```env
# OpenAI (Primary provider)
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...  # Optional

# Anthropic (Fallback provider)
ANTHROPIC_API_KEY=sk-ant-...

# Bedrock (Optional alternative)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# LLM Configuration
LLM_PRIMARY_PROVIDER=openai
LLM_PRIMARY_MODEL=gpt-4-turbo-preview
LLM_FALLBACK_PROVIDER=anthropic
LLM_FALLBACK_MODEL=claude-3-sonnet-20240229
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

### 2. Model Selection

#### Primary: OpenAI GPT-4 Turbo
- **Use for:** Complex reasoning, multi-step planning
- **Cost:** ~$0.01 per 1K prompt tokens, $0.03 per 1K completion tokens
- **Latency:** ~2-5s typical
- **Benefits:** Excellent instruction-following, broad knowledge cutoff

#### Fallback: Anthropic Claude 3 Sonnet
- **Use for:** Backup reasoning, structured output
- **Cost:** ~$0.003 per 1K prompt tokens, $0.015 per 1K completion tokens
- **Latency:** ~2-4s typical
- **Benefits:** Strong constitution/safety, good value

#### Optional: Bedrock (AWS)
- **Use for:** On-premise/private cloud deployments
- **Models:** Claude via Bedrock, other options
- **Setup:** Configure AWS credentials, region

## Agent Configuration

### Coordinator Agent
- **Model:** `gpt-4-turbo-preview` (primary)
- **Temperature:** 0.2 (low randomness for planning consistency)
- **Max tokens:** 2000
- **Prompt:** `.llm/prompts/coordinator.md`

### Extraction Agent
- **Model:** `gpt-4-turbo-preview` (primary)
- **Temperature:** 0.0 (deterministic API call generation)
- **Max tokens:** 1500
- **Prompt:** `.llm/prompts/extraction.md`

### Analytics Agent
- **Model:** `gpt-4-turbo-preview` (primary)
- **Temperature:** 0.3 (slightly more creative for insight narration)
- **Max tokens:** 2000
- **Prompt:** `.llm/prompts/analytics.md`

### Report Generator
- **Model:** `gpt-3.5-turbo` (efficient for text generation)
- **Temperature:** 0.5 (balanced for readable prose)
- **Max tokens:** 4000
- **Prompt:** `.llm/prompts/report.md`

## Router Configuration

The `LLMRouter` automatically handles:
- **Timeouts:** 30 seconds; falls back on timeout
- **Rate limits:** Automatic retry with exponential backoff
- **Circuit breaker:** Marks provider down after 3 consecutive failures; retries every 60 seconds
- **Cost tracking:** Logs token usage and estimated cost per call

### Router Example Usage

```python
from backend.app.core.llm_router import LLMRouter

router = LLMRouter()

# Simple invocation
completion, metadata = await router.invoke(
    agent="coordinator",
    prompt="Analyze employment trends...",
)

# With custom model override
completion, metadata = await router.invoke(
    agent="analytics",
    prompt="...",
    model="gpt-3.5-turbo"  # Override default for cost
)

# metadata contains:
# - provider: "openai" | "anthropic"
# - model: "gpt-4-turbo-preview"
# - latency_ms: 2543
# - prompt_tokens: 512
# - completion_tokens: 256
# - estimated_cost_usd: 0.0087
```

## Prompt Engineering Guidelines

1. **Structured Output:** Always request JSON when data is needed:
   ```
   Return a JSON object with keys: sources, metrics, time_range
   ```

2. **Separation of Concerns:**
   - Coordinator: "What should we do?"
   - Extraction: "How do we get the data?"
   - Analytics: "What does it mean?"
   - Report: "How do we communicate it?"

3. **Grounding:** Always cite data in responses:
   ```
   Finding: Employment increased 5% YoY (row_ids: [123, 456])
   ```

4. **Constraints:** Explicitly bound agent autonomy:
   ```
   You may access: Data.gov.sg, DOS SingStat (read-only)
   You may NOT: Modify data, access external APIs beyond [list]
   ```

5. **Fallback:** Provide graceful degradation:
   ```
   If source A unavailable, use source B instead.
   If both unavailable, report partial results with caveats.
   ```

## Cost Management

### Monitoring
- All LLM calls logged to `llm_calls` table
- Check cost: `SELECT SUM(total_cost) FROM llm_calls WHERE created_at > now() - interval '1 day';`

### Budget Controls
- Set daily budget limit in config
- Coordinator agent checks remaining budget before planning large runs
- Graceful degradation: use cheaper models for fallback

### Cost Estimation per Query Type
- Simple query (e.g., "single metric trend"): ~$0.05
- Complex query (e.g., "multi-source analysis"): ~$0.20
- Large dataset analysis: ~$0.50

## Testing & Validation

### Unit Tests
```bash
pytest backend/tests/test_llm_router.py
pytest backend/tests/test_agents/
```

### Integration Tests
```bash
pytest backend/tests/integration/test_full_pipeline.py
```

### Prompt Validation
- Agents must return valid JSON when required
- No hallucinated citations (verify against dataset)
- Confidence scores must be in [0, 1]

## Troubleshooting

### Issue: LLM Provider Timeout
- **Check:** Network connectivity, API key validity
- **Fix:** Increase timeout (default 30s), verify provider status page

### Issue: Hallucinated Data
- **Check:** Prompt clarity, context length
- **Fix:** Add validation step in Analytics Agent before emitting insights

### Issue: High Cost
- **Check:** Token usage in `llm_calls` table
- **Fix:** Use cheaper fallback model, optimize prompts for brevity, batch queries

## Next Steps
1. Set environment variables in `.env`
2. Run `pytest backend/tests/test_llm_router.py` to verify connectivity
3. Test agents individually with sample data
4. Monitor cost dashboard in week 1 of deployment
