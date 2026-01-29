# Task — DOS SingStat Data Connector (Developer API, On-Demand)

## Objective
Integrate DOS SingStat as an external government data source using the **SingStat Table Builder Developer API**, enabling **on-demand discovery and retrieval** of statistical tables based on query intent, without pre-ingesting the full SingStat catalog.

This task focuses strictly on **data acquisition, validation, and provenance**, consistent with the shared connector interface.

---

## Scope

### In Scope
- Keyword-based discovery of SingStat tables via Developer API
- Retrieval of selected tables via API (JSON/CSV)
- Parsing, validation, and cleaning into a canonical tabular form
- Metadata and provenance capture
- Idempotent storage of retrieved data
- Lightweight integration tests (fast, deterministic)

### Out of Scope
- Full catalog ingestion of all SingStat tables
- Statistical analysis or aggregation
- UI or visualization logic
- Authentication, access control, or rate-limit escalation

---

## Access Pattern

### Discovery
- Use SingStat Table Builder **search API** to locate tables by keyword.
- Search scope includes:
  - Table title
  - Variable names
  - Description text (where available)
- Prefer **Time Series (TS)** tables by default.
- Return a bounded list of candidate tables for downstream selection.

### Data Retrieval
- Fetch table data using the Table Builder **Data API**.
- Prefer **JSON** format; fallback to **CSV** where JSON is unavailable.
- Retrieve only the explicitly selected table(s).

---

## Connector Responsibilities (Interface Alignment)

The SingStat connector must implement the standard data-source interface:

- `discover(intent)`
- `fetch(dataset_ref)`
- `parse(raw_data)`
- `validate(parsed_data)`
- `clean(parsed_data)`

Each step must emit structured metadata suitable for persistence and audit.

---

## Dataset Reference Model

- Each SingStat table is treated as a **dataset**.
- Dataset reference uniquely identifies:
  - SingStat resource / table ID
  - Requested format (JSON or CSV)
  - Optional query parameters (e.g. time range)

The dataset reference must be stable and reproducible.

---

## Parsing Strategy

- Normalize all tables into a **tidy format**:
  - One observation per row
  - Canonical columns:
    - `period`
    - `value`
    - Dimension attributes (captured as structured fields or JSON)
- Handle common SingStat characteristics:
  - Multi-row headers
  - Embedded footnotes
  - Mixed numeric/string values
  - Suppressed or missing values

Parsing must be resilient and table-agnostic.

---

## Validation Rules (Minimum)

Each retrieved dataset must be validated for:

- Non-empty dataset
- Presence of a numeric measure column
- Parseable time/period column (if applicable)
- Missing value percentage
- Duplicate row detection
- Basic time-series continuity checks (best-effort)

Validation outcomes:
- `passed`
- `warning`
- `failed`

All validation results must be persisted.

---

## Cleaning Rules

Cleaning steps must be **explicit, deterministic, and logged**:

- Normalize column names
- Coerce numeric values
- Standardize period representations (Year / Quarter / Month)
- Trim whitespace and normalize categorical values
- Drop fully empty rows or columns

No table-specific heuristics or hard-coded assumptions.

---

## Metadata & Provenance

For each retrieved SingStat dataset, persist:

- Source: `singstat`
- Table / resource ID
- Human-readable title
- Retrieval timestamp
- Request parameters
- Raw payload checksum
- Parsed schema snapshot
- Validation report
- Cleaning log

This metadata is required for downstream citation and auditability.

---

## Idempotency & Updates

- Use `(resource_id, payload_checksum)` as the idempotency key.
- If the same table content is retrieved again:
  - Do not re-ingest
  - Reuse existing stored version
- Store newer versions separately when content changes.

---

## Failure Handling

- Discovery failure:
  - Return empty candidate set with structured error metadata
- Fetch failure:
  - Retry with backoff
  - Fallback format (JSON → CSV)
- Parse or validation failure:
  - Mark dataset as failed
  - Do not block unrelated pipeline steps

Failures must be observable and non-silent.

---
## End-to-End Smoke Test (Live SingStat Developer API)

### Purpose
Provide a **single, fast** end-to-end validation that the SingStat connector can **discover and fetch live data** from the SingStat Table Builder Developer API, producing a parsed + validated + cleaned dataset.

### When to run
- **Debug / pre-demo** verification 
- Not required in CI by default (external dependency + network variability).

### Test Inputs
- Use **one stable keyword query** (e.g., a broad term like “labour force” or “consumer price index”) and/or a **pinned known resource/table ID** (preferred for stability).
- Prefer a **Time Series (TS)** table for consistent output.

### Flow (Single Test)
1) `discover(intent)` against live API
   - Expect at least 1 candidate returned
   - If configured `prefer_ts=true`, expect the top candidate to be TS (best-effort)

2) Select candidate (deterministic)
   - Prefer:
     - pinned `resource_id` if configured
     - else the top-ranked candidate from discovery

3) `fetch(dataset_ref)` live
   - Prefer JSON; fallback to CSV only if JSON is unavailable
   - Enforce strict timeouts (see below)

4) `parse(raw)` → DataFrame
   - Must produce a non-empty dataset

5) `validate(df)`
   - Must return `passed` or `warning` (not `failed`)

6) `clean(df)`
   - Must preserve row count within a reasonable bound (no accidental drop-to-empty)
   - Must output canonical columns (`value` required; `period` expected for TS tables)

### Assertions (Minimal, Fast)
- Discovery returns ≥ 1 dataset candidate
- Fetch returns non-empty payload
- Parse returns non-empty table
- `value` column exists and is numeric-coercible
- For TS: `period` exists and has at least 2 distinct values
- Validation status is not `failed`
- Cleaning log is non-empty (at least column normalization + value coercion recorded)
- Provenance captured: `source`, `resource_id`, `retrieved_at`, `checksum`

### Time Budget / Limits
- Hard timeout per HTTP request: 10–15s
- Max retries: 1 (keep test fast)
- Limit downloaded payload size where API supports it (or limit parsing to first N rows if necessary)
- Overall test budget target: < 20s under normal connectivity

### Failure Behavior
- If the live API is unreachable / times out:
  - mark as skipped if clearly network-related (recommended), otherwise fail with a concise error.
- If schema changes cause parse failure:
  - fail with a clear message indicating which stage failed (discover/fetch/parse/validate/clean).

### Deliverable
- One end-to-end smoke test case documented and executable via environment flags, intended for **quick pre-submission verification**.

