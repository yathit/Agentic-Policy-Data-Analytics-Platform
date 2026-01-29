# Task 002 — Data Sources Integration

## Objective
Implement and document the initial government and internal data sources used by the Agentic Policy Data Analytics Platform, ensuring realistic formats, provenance tracking, and data quality validation suitable for an IMDA policy analytics use case.

This task focuses on **data acquisition and validation only**. No analytics or UI work is included here.

---

## Scope

### In Scope
- Integrate **at least two** government data sources
- Support **multiple data formats** (CSV, Excel, JSON/API)
- Implement dataset metadata capture and validation
- Provide a realistic **mock internal dataset**
- Produce clear documentation for `DATA_SOURCES.md`

### Out of Scope
- Statistical analysis
- LLM reasoning or insight generation
- UI visualisation
- Authentication / access control

---

## Data Sources (v1)

### 1. Data.gov.sg (External, Public)

**Purpose**
Primary open-data source for structured datasets suitable for demos and automated extraction.

**Typical Datasets**
- Employment by industry
- Workforce demographics
- Sectoral output indicators

**Formats**
- JSON (API)
- CSV

#### Architecture

**Two-phase approach:**
1. **Discovery** — Query cached `data_gov_sg_collection` table (not API)
2. **Fetching** — Use V2 API to retrieve actual dataset data

**Connector:** `DataGovV2Connector` (new, replaces legacy CKAN connector)

#### V2 API Endpoints

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Metadata | `GET /v2/public/api/datasets/{id}/metadata` | Schema info |
| List Rows | `GET /v2/public/api/datasets/{id}/list-rows` | Paginated data |
| Initiate Download | `GET /v1/public/api/datasets/{id}/initiate-download` | Async download |
| Poll Download | `GET /v1/public/api/datasets/{id}/poll-download` | Get download URL |

Base URLs:
- `https://api-production.data.gov.sg` (v2)
- `https://api-open.data.gov.sg` (v1 download)

#### Discovery Flow

1. User provides intent (e.g., "employment statistics")
2. `DataService.discover_datasets()` calls `search_collections(db, intent)`
3. Returns dataset candidates with `uri` = dataset_id (e.g., `d_abc123`)
4. Each candidate includes collection metadata (name, description, last_updated)

#### Data Fetching Flow

1. `DataService.ingest_dataset()` receives selected dataset_id
2. `DataGovV2Connector.fetch(dataset_id)` tries:
   - **Primary:** `list-rows` API (paginated, for smaller datasets)
   - **Fallback:** `initiate-download` → `poll-download` (async, for large datasets)
3. Parse response to DataFrame (CSV/JSON)
4. Validate and clean per standard pipeline

#### Files

| File | Purpose |
|------|---------|
| `connectors/datagov_v2.py` | V2 connector implementation |
| `connectors/__init__.py` | Export new connector |
| `services/data_service.py` | Register V2 connector for `data.gov.sg` |

#### Handling Rules

- Retry with exponential backoff on 429, 5xx errors (base delay: 2s)
- Max 3 retries per request
- Poll download status up to 10 times (2s intervals)
- Hard-fail on invalid response shape

---

### 2. DOS SingStat (External, Public)

**Purpose**
Authoritative national statistics source; use SingStat Table Builder for time-series and cross-sectional tables.

**Access Pattern**
- Discover tables via SingStat Table Builder (free access to ~2,400 datasets / ~150,000 data series from 70 agencies). citeturn1view0
- Prefer SingStat Table Builder APIs for commonly accessed tables (JSON/CSV). citeturn10view0
- Use developer APIs for parameterized/custom queries when standard APIs are insufficient. citeturn10view0
- Export customised tables in different formats; supports downloading multiple tables at once. citeturn10view0

**Typical Datasets**
- Labour force statistics
- Industry employment levels
- Time-series economic indicators

**Formats**
- JSON / CSV (API) 
- CSV / Excel (`.xls`, `.xlsx`) via table export

**Handling Rules**
- Prefer API responses (JSON/CSV) when available for reliability and repeatability. 
- Fallback to exported CSV/Excel for tables without API coverage. citeturn10view0
- Normalize multi-row headers
- Canonicalize time columns (Year / Quarter / Month)
- Preserve original column labels in metadata

---

### 3. Mock Internal Dataset (IMDA-Realistic)

**Purpose**
Simulate internal IMDA or inter-agency datasets that are not publicly accessible, demonstrating enterprise-style integration.

**Storage**
- PostgreSQL (seeded via `/infra/scripts/seed_db.sh`)

**Example Tables**
- `digital_sector_employment`
- `ai_workforce_programmes`
- `online_safety_incidents_summary`
- `emerging_tech_adoption_index`

**Characteristics**
- Stable schema
- Lower latency
- Higher trust weight during planning
- Used as fallback when external APIs fail

**Note**
Data is **synthetic but policy-plausible**, derived from publicly observable IMDA focus areas.

---

## Connector Interface

Each data source implements a common interface:

```

discover(intent) -> dataset_candidates
fetch(dataset_ref) -> raw_bytes
parse(raw_bytes) -> DataFrame
validate(df) -> quality_report
clean(df) -> cleaned_df, cleaning_log

```

This ensures all sources behave consistently within the agent workflow.

---

## Data Validation Rules (Minimum)

Each dataset must pass or emit warnings for:

- Required columns present
- Datatypes coercible (date / numeric / categorical)
- Missing value thresholds
- Duplicate row detection (where applicable)
- Time-series continuity (gap detection)

Validation results are stored as structured JSON and surfaced to agents and UI.

---

## Data Cleaning Rules

Cleaning steps are **transparent and logged**:

- Normalize column names (snake_case)
- Parse dates to ISO format
- Convert numeric strings to floats/ints
- Handle missing values (drop, forward-fill, or interpolate)
- Flag outliers (do not delete by default)

No silent mutations are allowed.

---

## Provenance & Metadata

Every dataset ingested must persist:

- Source name
- URI / endpoint
- Retrieval timestamp
- File checksum
- Row count
- Schema snapshot
- Validation report
- Cleaning log

This metadata is required for citation and auditability.

---

## Deliverables

By completion of this task:

- Data connectors for:
  - Data.gov.sg
  - DOS SingStat
  - Mock internal PostgreSQL dataset
- Seed script for internal dataset
- Validation and cleaning pipeline
- Documentation ready for `DATA_SOURCES.md`

---

## Acceptance Criteria

- At least **two external government sources** integrated
- At least **two file formats** supported
- Internal dataset seeded and queryable
- Validation warnings are emitted and persisted
- Provenance metadata stored for every dataset
- No analytics or UI logic introduced

---

## Verification

Manual:
- Run seed script and verify internal tables
- Trigger extraction for one dataset per source

Automated:
- Unit tests for each connector
- Validation test for missing/invalid columns

---

## Notes

This task establishes the **trust boundary** of the system.  
All downstream analytics and LLM narration depend on the correctness and transparency of these data sources.



