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

**Access Pattern**
- Dataset listing API (exact endpoint):
  - `https://data.gov.sg/v1/public/api/datasets`


**Typical Datasets**
- Employment by industry
- Workforce demographics
- Sectoral output indicators

**Hardcoded datasetId (required for bootstrapping)**
Use these as fixed dataset seeds when discovery is not yet wired:
- `d_bccdf7ae697389c5a7e8c3f9005a852a` - Principal Statistics Of Manufacturing By Industry Cluster - Employment, Annual
- `d_623c5a2823d6ccd02c331719135108f9` - Resident Employees Aged 15 Years and Over by Industry, Nature of Employment and Sex (General Household Survey 2005)
- `d_a326c13e94827819f8f1057c15f00221` - Changes In Employment By Sector, (Compared To The Previous Period), Annual
- `d_31dec7667bc2c6b945a262cd60958eaf` - Changes In Employment By Sector, (Compared To The Previous Period), Quarterly
- `d_c2b4d1a2c9bfc5d0df58dd339d8121a0` - Total Mobile Phone Subscriptions
- `d_fcc02bc884c54a09e8665443bff2f4c2` - Individual Internet Usage
- `d_5105c8c24199312306d1dd38bbc560a8` - Total Foreign Workforce

**Formats**
- JSON (API)
- CSV

**Handling Rules**
- Prefer API endpoints when available
- Fallback to CSV download if API fails
- Retry with exponential backoff on transient errors

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



