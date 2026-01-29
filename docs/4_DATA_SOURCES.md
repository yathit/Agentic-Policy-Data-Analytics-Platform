# Data Sources

## Overview

The Agentic Policy Data Analytics Platform integrates multiple data sources to provide comprehensive policy analysis for IMDA. This document describes the implemented data sources, their access patterns, data formats, and handling rules.

## Architecture

All data sources implement a common connector interface that ensures consistent behavior:

```python
discover(intent) -> dataset_candidates
fetch(dataset_ref) -> raw_bytes
parse(raw_bytes) -> DataFrame
validate(df) -> quality_report
clean(df) -> cleaned_df, cleaning_log
```

This standardized approach ensures:
- Consistent error handling
- Transparent data transformations
- Complete provenance tracking
- Quality validation at every step

---

## Implemented Data Sources

### 1. Data.gov.sg

**Type:** External, Public
**Status:** Implemented
**Connector:** `DataGovConnector`

#### Purpose
Primary open-data source for structured government datasets. Provides access to employment statistics, workforce demographics, and sectoral indicators.

#### Access Pattern
- **Primary:** REST API (`https://data.gov.sg/api`)
- **Fallback:** Direct CSV download

#### Supported Formats
- JSON (via API)
- CSV

#### Key Features
- Dataset discovery via search API
- Exponential backoff retry logic (3 attempts)
- Automatic format detection
- Rate limiting compliance

#### Typical Datasets
- Employment by industry
- Workforce demographics
- Sectoral output indicators
- Economic statistics

#### Handling Rules
1. Prefer API endpoints when available
2. Fall back to CSV download if API fails
3. Retry with exponential backoff (1s, 2s, 4s)
4. Timeout: 30 seconds per request

#### Example Usage

```python
from app.connectors import DataGovConnector

connector = DataGovConnector()

# Discover datasets
candidates = connector.discover("employment statistics")

# Fetch and parse
df = connector.fetch_and_parse(candidates[0].uri)

# Validate
report = connector.validate(df)

# Clean
result = connector.clean(df)
```

#### Provenance Metadata
- Source name: "Data.gov.sg"
- Data owner: "Government of Singapore"
- License: "Singapore Open Data License"
- Retrieval method: "api" or "download"

#### Collections Metadata Cache

The platform maintains a local cache of data.gov.sg collection metadata in the `data_gov_sg_collection` table. This enables fast dataset discovery without hitting the API.

**Automatic Ingest:**
- **Weekly schedule:** Sundays at 02:00 SGT (configurable)
- **Startup bootstrap:** If table is empty on startup, ingest runs automatically

**Verify cached collections:**

```bash
docker exec policy-analytics-postgres psql -U user -d imda_policy -c "SELECT COUNT(*) FROM data_gov_sg_collection;"
```

**Search collections:**

```bash
docker exec policy-analytics-postgres psql -U user -d imda_policy -c "SELECT collection_id, name FROM data_gov_sg_collection_latest WHERE name ILIKE '%employment%' LIMIT 10;"
```

---

### 2. DOS SingStat

**Type:** External, Public
**Status:** Implemented
**Connector:** `SingStatConnector`

#### Purpose
Authoritative national statistics from the Department of Statistics Singapore. Demonstrates Excel/CSV handling and schema normalization for complex government datasets.

#### Access Pattern
- Static file downloads (CSV / Excel)

#### Supported Formats
- CSV
- Excel (`.xls`, `.xlsx`)

#### Key Features
- Multi-row header normalization
- Time column canonicalization (Year, Quarter, Month)
- Excel file parsing with `openpyxl`
- Original column labels preserved in metadata

#### Known Datasets
Currently configured with curated list of key datasets:
- Labour Force Statistics
- Employment by Industry
- Time-series economic indicators

#### Handling Rules
1. Normalize multi-row headers (common in SingStat files)
2. Canonicalize time columns to standard names
3. Remove numeric formatting (commas, spaces)
4. Preserve original column names in metadata
5. Detect and report time-series gaps

#### Special Handling

**Multi-row Headers:**
SingStat files often have category headers spanning multiple rows. The connector automatically detects and combines these into single-row headers.

**Time Column Canonicalization:**
- `Yr`, `Year`, `yyyy` → `year`
- `Qtr`, `Quarter`, `Q` → `quarter`
- `Mon`, `Month`, `mm` → `month`

#### Example Usage

```python
from app.connectors import SingStatConnector

connector = SingStatConnector()

# Discover from known datasets
candidates = connector.discover("labour force")

# Fetch and parse Excel file
raw_bytes = connector.fetch(candidates[0].uri)
df = connector.parse(raw_bytes, format_hint="excel")

# Validate (includes time-series gap detection)
report = connector.validate(df)

# Clean (normalize headers and time columns)
result = connector.clean(df)
```

#### Provenance Metadata
- Source name: "Department of Statistics Singapore (SingStat)"
- Data owner: "Singapore Department of Statistics"
- License: "Singapore Open Data License"
- Retrieval method: "download"
- Update frequency: "varies" (dataset-specific)

---

### 3. IMDA Internal Datasets (Mock)

**Type:** Internal, Synthetic
**Status:** Implemented
**Connector:** `InternalConnector`

#### Purpose
Simulates internal IMDA and inter-agency datasets that are not publicly accessible. Demonstrates enterprise-style database integration with high trust and low latency.

#### Storage
PostgreSQL database (seeded via `/infra/scripts/seed_db.sh`)

#### Available Tables

##### 3.1 Digital Sector Employment
**Table:** `digital_sector_employment`

Tracks employment across digital industry sectors by quarter.

**Schema:**
- `year` (INTEGER) - Year of reporting
- `quarter` (VARCHAR) - Quarter (Q1, Q2, Q3, Q4)
- `sector` (VARCHAR) - Industry sector
- `total_employees` (INTEGER)
- `local_employees` (INTEGER)
- `foreign_employees` (INTEGER)
- `professional_roles` (INTEGER)
- `technical_roles` (INTEGER)
- `average_salary_sgd` (DECIMAL)

**Coverage:** 2022-2024, quarterly data
**Sectors:** Software Development, Cybersecurity, AI and Data Analytics, Digital Marketing

##### 3.2 AI Workforce Programmes
**Table:** `ai_workforce_programmes`

Government-funded AI workforce development initiatives.

**Schema:**
- `programme_name` (VARCHAR)
- `programme_type` (VARCHAR) - Training, Certification, Internship, Attachment
- `start_date` (DATE)
- `end_date` (DATE)
- `target_participants` (INTEGER)
- `actual_participants` (INTEGER)
- `completion_rate` (DECIMAL) - Percentage
- `employment_rate_6months` (DECIMAL) - Employment rate within 6 months
- `funding_sgd` (DECIMAL)
- `partner_organizations` (TEXT[])

**Coverage:** 2022-2024
**Programme Types:** AI Apprenticeships, Data Science Bootcamps, ML Certifications, Ethics Workshops

##### 3.3 Online Safety Incidents Summary
**Table:** `online_safety_incidents_summary`

Aggregated statistics on online safety incidents (privacy-preserving).

**Schema:**
- `reporting_period` (DATE) - First day of month
- `incident_category` (VARCHAR)
- `total_reports` (INTEGER)
- `verified_incidents` (INTEGER)
- `severity_high/medium/low` (INTEGER)
- `age_group_child/adult` (INTEGER)
- `resolution_rate` (DECIMAL) - Percentage
- `avg_resolution_days` (DECIMAL)

**Coverage:** 2022-2024, monthly aggregates
**Categories:** Cyberbullying, Privacy Violation, Misinformation, Online Harassment, Deepfake Content, AI-Generated Scams

##### 3.4 Emerging Tech Adoption Index
**Table:** `emerging_tech_adoption_index`

Technology adoption metrics across industry sectors.

**Schema:**
- `assessment_year` (INTEGER)
- `assessment_quarter` (VARCHAR)
- `industry_sector` (VARCHAR)
- `technology_category` (VARCHAR)
- `adoption_score` (DECIMAL) - 0-100 scale
- `implementation_maturity` (VARCHAR) - Exploring, Piloting, Scaling, Mature
- `investment_level` (VARCHAR) - Low, Medium, High, Very High
- `workforce_readiness` (DECIMAL) - 0-100 scale
- `regulatory_clarity` (DECIMAL) - 0-100 scale
- `num_companies_surveyed` (INTEGER)

**Coverage:** 2022-2024, quarterly assessments
**Sectors:** Financial Services, Healthcare, Manufacturing, Retail, Education, Public Sector
**Technologies:** Generative AI, Blockchain, IoT, Computer Vision, Adaptive Learning

#### Characteristics
- Stable, well-defined schema
- Low latency (local database)
- High trust weight (internal provenance)
- Used as fallback when external APIs fail
- Policy-plausible synthetic data

#### Seeding

Database is seeded on initialization:

```bash
cd infra
./scripts/seed_db.sh
```

Or via Docker:

```bash
docker compose exec api bash -c "cd /app && ../infra/scripts/seed_db.sh"
```

#### Example Usage

```python
from app.connectors import InternalConnector

connector = InternalConnector()

# List available tables
tables = connector.list_tables()

# Get table info
info = connector.get_table_info("digital_sector_employment")

# Fetch data
df = connector.fetch_dataframe(
    "digital_sector_employment",
    filters={"year": 2024, "sector": "AI and Data Analytics"}
)

# Validate (lenient for internal data)
report = connector.validate(df)

# Clean (minimal cleaning needed)
result = connector.clean(df)
```

#### Provenance Metadata
- Source name: "IMDA Internal Database"
- Data owner: "IMDA"
- License: "Internal Use Only"
- Retrieval method: "database"
- Trust level: "high"
- Update frequency: "quarterly"

---

## Data Validation

Every dataset passes through standardized validation that checks:

### Required Checks
1. **Schema validation** - Required columns present
2. **Data type validation** - Datatypes coercible (date / numeric / categorical)
3. **Completeness** - Missing value thresholds
4. **Duplicate detection** - Duplicate row identification
5. **Time-series continuity** - Gap detection (when applicable)

### Validation Levels

**Passed:** No issues, warnings acceptable
**Warning:** Non-critical issues detected
**Failed:** Critical issues prevent usage

### Quality Metrics

All validation reports include:
- `completeness_score` (0.0 - 1.0)
- `missing_value_percentage`
- `duplicate_row_count`
- `time_series_gaps` (if applicable)
- Detailed issue and warning lists

### Example Validation Report

```json
{
  "status": "warning",
  "completeness_score": 0.92,
  "missing_value_percentage": 8.0,
  "duplicate_row_count": 3,
  "issues": [],
  "warnings": [
    {
      "type": "moderate_missing_values",
      "message": "Missing values: 8.00%",
      "percentage": 8.0
    }
  ],
  "full_report": {
    "total_rows": 1000,
    "total_columns": 15,
    "columns": ["year", "sector", "value", ...]
  }
}
```

---

## Data Cleaning

All cleaning operations are **transparent and logged**. No silent mutations are allowed.

### Standard Cleaning Operations

1. **Column name normalization**
   - Convert to snake_case
   - Remove special characters
   - Preserve original names in metadata

2. **Date parsing**
   - Parse to ISO format
   - Handle multiple date formats
   - Preserve original format in logs

3. **Numeric conversion**
   - Remove formatting (commas, currency symbols)
   - Convert strings to float/int
   - Handle missing values appropriately

4. **Missing value handling**
   - Drop completely empty rows/columns
   - Forward-fill for time series (when appropriate)
   - Interpolate for continuous data (when appropriate)
   - **Never** drop missing values silently

5. **Outlier detection**
   - Flag outliers
   - **Do not** delete by default
   - Log detection parameters

### Cleaning Logs

Every cleaning operation creates a log entry:

```json
{
  "operation": "normalize_columns",
  "description": "Normalized column names to snake_case",
  "parameters": {},
  "columns_affected": ["Test Column", "Another-Column"],
  "sample_before": {"columns": ["Test Column", "Another-Column"]},
  "sample_after": {"columns": ["test_column", "another_column"]}
}
```

---

## Provenance Tracking

Every dataset ingested persists complete metadata:

### Required Metadata

- **Source information**
  - Source name
  - URI / endpoint
  - Data owner
  - License information

- **Retrieval information**
  - Retrieval timestamp
  - Retrieval method (API, download, database)
  - File checksum (SHA256)

- **Dataset statistics**
  - Row count
  - Column count
  - File size (bytes)

- **Schema snapshot**
  - Column names
  - Data types
  - Nullable fields

- **Quality assurance**
  - Validation report
  - Cleaning log
  - Completeness score

### Database Schema

All provenance is stored in PostgreSQL:

- `datasets` - Core dataset metadata
- `dataset_provenance` - Source and retrieval info
- `validation_reports` - Quality validation results
- `cleaning_logs` - Transparent cleaning operations

### Citation

Every dataset can be traced back to its source for citation:

```python
from app.services import DataService

service = DataService(db)
metadata = service.get_dataset_with_metadata(dataset_id)

print(f"Source: {metadata['provenance']['source_name']}")
print(f"Retrieved: {metadata['provenance']['retrieved_at']}")
print(f"License: {metadata['provenance']['license_info']}")
```

---

## Integration with Agent Workflow

Data sources are used by agents in the following workflow:

1. **Discovery** - Agent searches for relevant datasets using intent
2. **Selection** - Agent evaluates candidates and selects best match
3. **Ingestion** - Dataset fetched, validated, and cleaned
4. **Analysis** - Agent performs statistical analysis on cleaned data
5. **Interpretation** - LLM generates insights with citations

### Multi-Source Strategy

Agents can query multiple sources simultaneously:
- **Primary:** External government sources (freshest data)
- **Fallback:** Internal database (high trust, always available)
- **Validation:** Cross-reference between sources

---

## Testing

Comprehensive test suite covers:

- Connector interface compliance
- Data parsing for all formats
- Validation logic
- Cleaning operations
- Provenance persistence

Run tests:

```bash
docker compose exec api pytest -v tests/
```

With coverage:

```bash
docker compose exec api pytest --cov=app tests/
```

---

## Future Extensions

Planned enhancements (not in current scope):

1. **Additional Sources**
   - MAS (Monetary Authority of Singapore)
   - MOE (Ministry of Education)
   - IMDA public datasets

2. **Advanced Features**
   - Incremental updates
   - Change detection
   - Data versioning
   - Automated refresh schedules

3. **Performance**
   - Caching layer
   - Parallel fetching
   - Streaming for large datasets

---

## Troubleshooting

### Common Issues

**Data.gov.sg API timeout:**
- Check network connectivity
- Verify API endpoint is accessible
- Review rate limiting

**SingStat parsing errors:**
- Verify Excel file format
- Check for unexpected header structure
- Review column mapping

**Internal database connection:**
- Ensure PostgreSQL is running
- Verify database is seeded
- Check connection parameters

### Debug Mode

Enable debug logging in settings:

```python
# app/core/config.py
environment = "development"
```

This will log:
- SQL queries
- HTTP requests
- Validation details
- Cleaning operations

---

## References

- [Data.gov.sg API Documentation](https://data.gov.sg/developer)
- [SingStat TableBuilder](https://tablebuilder.singstat.gov.sg/)
- [Singapore Open Data License](https://data.gov.sg/open-data-licence)

---

**Document Version:** 1.0
**Last Updated:** 2024-01-25
**Task:** 002-data-sources
