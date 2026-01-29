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

## Deliverables

- SingStat data connector specification implemented and registered
- Structured documentation suitable for inclusion in `DATA_SOURCES.md`
- Unit-testable behavior for:
  - Discovery
  - Retrieval
  - Parsing
  - Validation
  - Cleaning

---

## Acceptance Criteria

- SingStat tables can be discovered by keyword
- Selected tables can be retrieved via API
- Parsed data conforms to canonical structure
- Validation and cleaning reports are persisted
- Provenance metadata is complete and reproducible
- Connector integrates cleanly with existing data-source framework

---

## Notes

This connector intentionally treats SingStat as a **query-driven statistical system**, not a dataset catalog.  
The design prioritizes correctness, transparency, and operational simplicity over exhaustive coverage.
