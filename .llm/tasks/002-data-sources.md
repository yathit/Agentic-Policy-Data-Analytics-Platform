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
- REST API (`/api/action/datastore_search`)
- Direct CSV download (fallback)

**Typical Datasets**
- Employment by industry
- Workforce demographics
- Sectoral output indicators

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
Authoritative national statistics source demonstrating Excel/CSV handling and schema normalization.

**Access Pattern**
- Static file downloads (CSV / Excel)

**Typical Datasets**
- Labour force statistics
- Industry employment levels
- Time-series economic indicators

**Formats**
- CSV
- Excel (`.xls`, `.xlsx`)

**Handling Rules**
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

