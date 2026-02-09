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

## Plan
1. Expand discovery candidate pool
- Replace hard cap `10` with configurable values:
  - `DISCOVERY_MAX_CANDIDATES` default `1000`
  - `DISCOVERY_PAGE_SIZE` for batched retrieval
- Keep source-specific safety controls to prevent API abuse and timeouts.
- Emit discovery metrics: `retrieved_candidates`, `max_candidates`, `source_coverage`.

2. Build two-stage ranking pipeline
- Stage B (LLM ranking, default):
  - send reduced candidate set to LLM in batches,
  - ask for relevance ranking with reason and confidence,
  - merge batch results into a final ranked list.
- Stage A (deterministic fallback):
  - use lightweight lexical scoring (query terms, entities, metrics, time-related fields),
  - activate when LLM is unavailable, times out, or returns invalid ranking output.
- Parallelization:
  - run LLM ranking batches in parallel to reduce latency.
- Persist ranking artifacts in event payload:
  - `rank`, `relevance_score`, `reason`, `confidence`.

3. Replace fixed dataset-count selection with row-budget policy
- Introduce configurable row budget:
  - `SELECTION_MAX_TOTAL_ROWS` (for example `200000`)
  - per-dataset cap `SELECTION_MAX_ROWS_PER_DATASET=1000`
- Select from ranked list until row budget is reached.
- Prefer diversity across sources/coverage only when relevance is similar.
- Allow many small datasets and fewer large datasets naturally.

4. Add row-estimation and adaptive truncation
- Estimate row count before full ingest (metadata/probe call when possible).
- If row count unknown, apply conservative default and adjust after fetch.
- During extraction, if dataset exceeds budget:
  - sample or partial fetch,
  - record truncation strategy in payload.

5. Improve transparency and controls
- Add event payload fields:
  - `candidate_pool_size`
  - `llm_ranked_count`
  - `selected_dataset_count`
  - `selected_total_estimated_rows`
  - `selection_budget`
  - `selection_rationale`
- Plan response should include both ranking summary and row-budget rationale.

## Acceptance Criteria
1. Discovery can evaluate large pools (target up to `1000` candidates where source supports it).
2. LLM ranking is used in selection and visible in events.
3. Selection is driven by row budget, not fixed top-N dataset count.
4. Queries like tech employment trend avoid obviously irrelevant education-only selections.
5. Runs produce either useful analysis or explicit diagnostics explaining budget/ranking constraints.

## Test Plan
- Unit tests:
  - candidate pool expansion and paging logic,
  - deterministic pre-filter behavior,
  - row-budget selector edge cases (many small vs few large datasets).
- Integration tests:
  - employment trend query with large candidate pool,
  - assert ranked candidates include domain-relevant items before extraction,
  - assert selected total estimated rows does not exceed budget.
- Reliability tests:
  - LLM ranking fallback when provider timeout/error occurs,
  - deterministic fallback still returns a ranked shortlist.
