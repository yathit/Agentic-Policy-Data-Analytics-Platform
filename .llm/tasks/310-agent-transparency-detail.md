# Task 310 — Agent Transparency and Step Detail

## Objective
Improve plan/execution transparency so users can see:
- dataset names in `fetch_datasets` (not only IDs),
- discovery counts as returned vs total (example: `10 of 43`),
- extraction payload links to full source data.

## Problem Summary
- Current plan step `fetch_datasets` uses only dataset IDs.
- Coordinator observation says `Found 10 datasets from data.gov.sg` without clarifying whether this is capped.
- Extraction observation payload exposes row/column/status but no direct link to full source data.

## Scope
- `backend/app/api/routes/runs.py` plan step shaping for UI.
- `backend/app/agents/coordinator.py` discovery event/notes.
- `backend/app/agents/extraction.py` extraction observation payload.
- `frontend/src/components/AgentTimeline.tsx` payload rendering for links (if needed for usability).
- Tests covering changed payload/message contracts.

## Plan
1. Define updated payload contracts
- Add structured dataset entries for `fetch_datasets`, including:
  - `id`
  - `name`
  - `source`
  - `score` (if available)
- Add discovery payload fields:
  - `returned_count`
  - `total_count`
  - `is_truncated`
  - `limit`
- Add extraction payload fields:
  - `dataset_name`
  - `dataset_ref`
  - `source_uri` (provenance URL/API reference)
  - optional `portal_url` where available

2. Improve coordinator discovery visibility
- Update discovery observation message:
  - if truncated: `Found {returned_count} of {total_count} datasets from {source}`
  - else: `Found {total_count} datasets from {source}`
- Update `DiscoveryStep.notes` with the same logic.
- Include sample dataset names + IDs in payload preview.

3. Enrich `fetch_datasets` plan step
- In `_build_plan_steps_from_structured`, keep compatibility with existing `datasets` list.
- Add a new `dataset_details` array with `id/name/source/score`.
- Include optional `source_display_name` where helpful.

4. Add extraction full-data links
- Extend extraction observation payload to include provenance-derived `source_uri`.
- For `data.gov.sg`, include canonical dataset API/portal link when derivable from dataset ref.
- Keep existing fields (`dataset_id`, `row_count`, `column_count`, `status`, `completeness_score`).

5. UI payload usability (timeline)
- If payload has URL fields, render them as clickable links in details view.
- Preserve current JSON fallback for non-URL fields.

## Acceptance Criteria
1. `fetch_datasets` step contains dataset names (not IDs only).
2. Coordinator observation clearly indicates returned vs total counts when capped.
3. Extraction observation payload includes at least one link to full source data.
4. Existing run/timeline behavior remains backward compatible.
5. Automated tests assert the new fields/messages.

## Test Plan
- Backend unit tests:
  - coordinator discovery message formatting for truncated and non-truncated cases.
  - plan step builder includes `dataset_details`.
  - extraction observation payload contains link fields and existing summary fields.
- API contract tests:
  - `/runs` plan response includes enriched `fetch_datasets.inputs`.
- Frontend tests (if present):
  - timeline payload renders URL fields as links.

## Notes
- data.gov.sg discovery is currently capped in connector/service paths; this task surfaces both returned and total counts so users understand truncation.
- Keep payload additions additive to avoid breaking existing consumers.
