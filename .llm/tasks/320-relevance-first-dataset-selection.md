# Task 320 - Large-Pool Discovery with LLM Ranking and Row-Budget Selection

## Objective
Improve dataset selection quality by searching a much larger candidate pool, ranking with LLM support, and selecting datasets by total row budget instead of a fixed dataset count.

## Problem (Observed)
In observed runs, only a small capped candidate set was considered, resulting in irrelevant dataset choices and `0 insights`.

## Product Direction
- Do not stop at first 10 candidates.
- Allow discovery to consider up to around `1000` candidates where available.
- Use LLM to rank suitability against the user query.
- Select datasets by a configurable row budget, not by "top N datasets".

## Scope
- Coordinator discovery and ranking flow.
- Connector/service candidate retrieval limits.
- Plan selection policy (row-budget based).
- Extraction preflight row estimation.
- Event payloads for ranking and selection transparency.
- Schema updates for new ranking and estimation fields.

## Configuration
All new configuration values will be stored as environment variables with defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCOVERY_MAX_CANDIDATES` | `1000` | Maximum candidates to retrieve across all sources |
| `DISCOVERY_PAGE_SIZE` | `100` | Batch size for paginated retrieval |
| `PRE_FILTER_MAX_CANDIDATES` | `200` | Max candidates to send to LLM ranking (after deterministic pre-filter) |
| `LLM_RANKING_BATCH_SIZE` | `20` | Candidates per LLM ranking call |
| `LLM_RANKING_TIMEOUT_MS` | `30000` | Timeout before falling back to deterministic ranking |
| `LLM_RANKING_MAX_PARALLEL` | `5` | Max concurrent LLM ranking requests |
| `SELECTION_MAX_TOTAL_ROWS` | `200000` | Total row budget for selected datasets |
| `SELECTION_MAX_ROWS_PER_DATASET` | `50000` | Per-dataset row cap |
| `ROW_ESTIMATE_DEFAULT` | `1000` | Conservative default when estimation unavailable |

## Plan

### 1. Expand discovery candidate pool
- Replace hard cap `10` in `coordinator.py:314` with configurable `DISCOVERY_MAX_CANDIDATES`.
- Add `DISCOVERY_PAGE_SIZE` for batched retrieval.
- Update connector-specific limits:
  - `DataGovV2Connector`: increase `max_pages` based on page size
  - `SingStatConnector`: increase `max_results` parameter
- Keep source-specific safety controls to prevent API abuse and timeouts.
- Emit discovery metrics: `retrieved_candidates`, `max_candidates`, `source_coverage`.

### 2. Build two-stage ranking pipeline

#### Stage A: Deterministic Pre-Filter (always runs first)
- Use existing lightweight lexical scoring from `_score_dataset()` method.
- Score all candidates using query terms, entities, metrics, time-related fields.
- Sort by score descending.
- Reduce pool to top `PRE_FILTER_MAX_CANDIDATES` (default 200) for LLM ranking.
- This stage is fast and runs synchronously.

#### Stage B: LLM Ranking (primary, runs on pre-filtered set)
- Send pre-filtered candidates to LLM in batches of `LLM_RANKING_BATCH_SIZE`.
- LLM prompt schema:
  ```json
  {
    "candidates": [{"id": "...", "title": "...", "description": "..."}],
    "query": "user's original query",
    "intent": {"entities": [...], "metrics": [...]}
  }
  ```
- LLM response schema:
  ```json
  {
    "rankings": [
      {"id": "...", "relevance_score": 0.85, "reason": "...", "confidence": "high"}
    ]
  }
  ```
- Run LLM batches in parallel (max `LLM_RANKING_MAX_PARALLEL` concurrent).
- Merge batch results into final ranked list.
- Fallback to Stage A scores if:
  - LLM timeout exceeds `LLM_RANKING_TIMEOUT_MS`
  - LLM returns malformed/unparseable response
  - LLM API error (rate limit, auth, etc.)

#### Ranking Artifacts
Persist in event payload:
- `rank`, `relevance_score`, `reason`, `confidence`, `ranking_method` ("llm" | "deterministic")

### 3. Replace fixed dataset-count selection with row-budget policy
- Remove existing `max_datasets_per_source = 3` logic in `coordinator.py:445-502`.
- Introduce row-budget selection:
  - `SELECTION_MAX_TOTAL_ROWS` total budget
  - `SELECTION_MAX_ROWS_PER_DATASET` per-dataset cap
- Selection algorithm:
  1. Iterate ranked list in order (best relevance first).
  2. For each candidate, check `estimated_rows`.
  3. If adding dataset stays within budget, select it.
  4. Stop when budget exhausted or no more candidates.
- Prefer diversity across sources only when relevance scores are within 0.1 of each other.
- Allow many small datasets and fewer large datasets naturally.

### 4. Add row-estimation per connector
Row counts are currently only known after full fetch. Add estimation methods:

| Connector | Estimation Strategy |
|-----------|---------------------|
| `DataGovV2Connector` | Use `total` field from first page metadata response |
| `SingStatConnector` | Use `TotalRecords` from tableinfo API if available, else default |
| Fallback | Use `ROW_ESTIMATE_DEFAULT` (1000) |

- Add `estimate_rows(dataset_id) -> int` method to base connector interface.
- Cache estimates to avoid repeated API calls.
- During extraction, if actual rows exceed estimate significantly:
  - Apply sampling or partial fetch
  - Record `truncation_strategy` in payload: "none" | "sampled" | "head" | "tail"

### 5. Update schemas

#### DiscoveredDataset (plan.py)
Add fields:
```python
relevance_score: float        # 0.0-1.0 from LLM or deterministic
reason: Optional[str]         # LLM-provided reason for relevance
confidence: Optional[str]     # "high" | "medium" | "low"
estimated_rows: int           # Pre-fetch row estimate
ranking_method: str           # "llm" | "deterministic"
```

#### DiscoveryStep (plan.py)
Add fields:
```python
pre_filter_count: int         # Candidates after deterministic filter
llm_ranked_count: int         # Candidates ranked by LLM
```

### 6. Improve transparency and controls
- Add event payload fields:
  - `candidate_pool_size`
  - `pre_filter_count`
  - `llm_ranked_count`
  - `selected_dataset_count`
  - `selected_total_estimated_rows`
  - `selection_budget`
  - `selection_rationale`
  - `ranking_method_used`
  - `llm_fallback_reason` (if applicable)
- Plan response should include both ranking summary and row-budget rationale.

## Backward Compatibility
- The new selection replaces `max_datasets_per_source` logic entirely.
- Existing `score` field in `DiscoveredDataset` maps to new `relevance_score`.
- Old event consumers should handle missing new fields gracefully.

## Acceptance Criteria
1. Discovery can evaluate large pools (target up to `1000` candidates where source supports it).
2. LLM ranking is used in selection and visible in events.
3. Selection is driven by row budget, not fixed top-N dataset count.
4. Queries like "tech employment trend" avoid obviously irrelevant education-only selections.
5. Runs produce either useful analysis or explicit diagnostics explaining budget/ranking constraints.
6. Deterministic fallback activates correctly when LLM is unavailable or times out.
7. Row estimates are within 2x of actual for connectors that support estimation.

## Test Plan

### Unit tests
- Candidate pool expansion and paging logic.
- Deterministic pre-filter scoring and reduction to `PRE_FILTER_MAX_CANDIDATES`.
- Row-budget selector edge cases:
  - Many small datasets vs few large datasets
  - Budget smaller than smallest dataset estimate
  - Budget exactly matches one dataset
  - All candidates have same relevance (diversity tiebreaker)
- LLM response parsing and malformed response handling.
- Row estimation per connector type.

### Integration tests
- **Employment trend query**: Assert ranked candidates include employment-related items, not education-only.
- Large candidate pool (500+) with LLM ranking completes within timeout.
- Assert selected total estimated rows does not exceed budget.
- Assert `ranking_method` is correctly set in events.
- Zero candidates returned from discovery: graceful error message.
- All candidates score below 0.1 relevance: explicit diagnostic in response.

### Reliability tests
- LLM ranking fallback when provider timeout occurs.
- LLM ranking fallback when API returns 429 rate limit.
- LLM ranking fallback when response is malformed JSON.
- Deterministic fallback still returns a ranked shortlist.
- Parallel LLM batches respect `LLM_RANKING_MAX_PARALLEL` limit.

### Performance benchmarks
- Discovery of 1000 candidates completes in < 30s.
- Pre-filter of 1000 candidates completes in < 1s.
- LLM ranking of 200 candidates (10 batches) completes in < 60s.
- Full pipeline (discovery + ranking + selection) completes in < 90s.
