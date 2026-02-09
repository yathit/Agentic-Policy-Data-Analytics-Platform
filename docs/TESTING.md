# Testing Guide

## Overview

This document describes how to run tests for the Agentic Policy Data Analytics Platform. The test suite includes unit tests, integration tests, and end-to-end smoke tests for validating data connectors against live APIs.

## Test Structure

```
backend/tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── test_health.py           # Health endpoint tests
├── test_connectors.py       # Unit tests for data connectors
├── test_data_service.py     # Data service tests
├── unit/
│   ├── __init__.py
│   └── test_runs_api.py     # Run API unit tests
└── integration/
    ├── __init__.py
    ├── test_datagov.py      # Data.gov.sg live API tests
    ├── test_singstat.py     # SingStat live API tests
    └── test_run_flow.py     # End-to-end run flow tests
```

---

## Quick Start

### Run All Tests (Excluding Integration)

```bash
docker-compose -f infra/docker-compose.yml exec api pytest -v
```



### Run All Tests (Including Integration)

```bash
docker-compose -f infra/docker-compose.yml exec api pytest -v -m ""
```

### Run with Coverage

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --cov=app tests/
```

---

## Test Categories

### Unit Tests

Fast, deterministic tests that do not require network access or external services.

**Run unit tests only:**
```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/ -v -m "not integration"
```

**Location:** `tests/test_*.py`, `tests/unit/`

**Examples:**
- `test_connectors.py` - Connector parsing, validation, cleaning
- `test_data_service.py` - Data service logic
- `test_runs_api.py` - API endpoint logic

### Integration Tests

Tests that make real API calls to external services. Marked with `@pytest.mark.integration`.

**Run integration tests only:**
```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/integration/ -v
```

**Skip in CI (default behavior):**
```bash
docker-compose -f infra/docker-compose.yml exec api pytest -m "not integration"
```

**Location:** `tests/integration/`

**Examples:**
- `test_datagov.py` - Data.gov.sg V2 API
- `test_singstat.py` - SingStat Table Builder API
- `test_run_flow.py` - Full pipeline execution

---

## Data Connector Tests

### SingStat Connector Tests

#### Unit Tests (`tests/test_connectors.py`)

Fast, offline tests for SingStat connector functionality:

```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/test_connectors.py::TestSingStatConnector -v
```

#### Integration Smoke Test (`tests/integration/test_singstat.py`)

End-to-end smoke test against the live SingStat Table Builder Developer API.

**Purpose:** Validate that the connector can discover, fetch, parse, validate, and clean live data from SingStat.

**Run the smoke test:**
```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/integration/test_singstat.py -v
```

**Test configuration:**
- Uses pinned resource ID `M213911` (Consumer Price Index) for stability
- Fast execution: `max_retries=1`, single retry delay
- Target execution time: < 20 seconds

**Test cases:**

| Test | Assertions |
|------|------------|
| `test_discover_returns_candidates` | Discovery returns >= 1 candidate |
| `test_fetch_returns_data` | Fetch returns non-empty payload |
| `test_parse_returns_dataframe` | Parse returns non-empty DataFrame |
| `test_value_column_exists_and_numeric` | `value` column exists and is numeric |
| `test_period_column_for_time_series` | `period` has >= 2 distinct values |
| `test_validate_not_failed` | Validation status is `passed` or `warning` |
| `test_clean_preserves_data` | Cleaning preserves rows, logs operations |
| `test_provenance_captured` | Provenance includes source, resource_id, retrieved_at, checksum |
| `test_full_pipeline_e2e` | Complete pipeline integration test |

**Error handling tests:**

| Test | Description |
|------|-------------|
| `test_fetch_invalid_resource_id` | Invalid ID raises `ValueError` |
| `test_discover_no_results_returns_empty` | No match returns empty list |

**When to run:**
- Pre-demo verification
- Debug sessions
- After connector changes
- Not required in CI (external dependency)

**Failure behavior:**
- Network timeout: Test marked as failed with network error
- Schema changes: Clear message indicating which stage failed

### Data.gov.sg Connector Tests

#### Integration Tests (`tests/integration/test_datagov.py`)

```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/integration/test_datagov.py -v
```

**Test cases:**
| Test | Description |
|------|-------------|
| `test_fetch_real_dataset` | Fetch and parse real dataset |
| `test_validate_real_dataset` | Validation on live data |
| `test_clean_real_dataset` | Cleaning operations |
| `test_discovery_via_data_service` | Discovery through DataService |
| `test_full_ingest_pipeline` | Complete ingest workflow |
| `test_fetch_invalid_dataset_id` | Error handling for invalid ID |
| `test_fetch_nonexistent_dataset` | Error handling for missing dataset |

---

## Running Specific Tests

### By File

```bash
# Single test file
docker-compose -f infra/docker-compose.yml exec api pytest tests/test_connectors.py -v

# Multiple files
docker-compose -f infra/docker-compose.yml exec api pytest tests/test_connectors.py tests/test_health.py -v
```

### By Class

```bash
docker-compose -f infra/docker-compose.yml exec api pytest tests/test_connectors.py::TestSingStatConnector -v
```

### By Test Name

```bash
# Exact match
docker-compose -f infra/docker-compose.yml exec api pytest tests/test_connectors.py::TestSingStatConnector::test_parse_json -v

# Pattern match
docker-compose -f infra/docker-compose.yml exec api pytest -k "parse" -v
docker-compose -f infra/docker-compose.yml exec api pytest -k "singstat" -v
docker-compose -f infra/docker-compose.yml exec api pytest -k "validate and not empty" -v
```

### By Marker

```bash
# Only integration tests
docker-compose -f infra/docker-compose.yml exec api pytest -m integration -v

# Exclude integration tests
docker-compose -f infra/docker-compose.yml exec api pytest -m "not integration" -v
```

---

## Test Fixtures

Common fixtures defined in `tests/conftest.py`:

### `test_db`

Fresh in-memory SQLite database for each test.

```python
def test_something(test_db):
    # test_db is a SQLAlchemy session
    pass
```

### `client`

FastAPI TestClient with database override.

```python
def test_api_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
```

---

## Coverage Reports

### Generate Coverage Report

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --cov=app --cov-report=term-missing tests/
```

### HTML Coverage Report

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --cov=app --cov-report=html tests/
```

Report saved to `htmlcov/index.html`.

### Coverage Thresholds

Current target: **80% line coverage**

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --cov=app --cov-fail-under=80 tests/
```

---

## Debugging Tests

### Verbose Output

```bash
docker-compose -f infra/docker-compose.yml exec api pytest -vvv tests/
```

### Show Print Statements

```bash
docker-compose -f infra/docker-compose.yml exec api pytest -s tests/
```

### Stop on First Failure

```bash
docker-compose -f infra/docker-compose.yml exec api pytest -x tests/
```

### Enter Debugger on Failure

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --pdb tests/
```

### Run Last Failed Tests

```bash
docker-compose -f infra/docker-compose.yml exec api pytest --lf tests/
```

---

## Local Development (Without Docker)

If running tests locally without Docker:

### Setup

```bash
cd backend
poetry install
```

### Run Tests

```bash
cd backend
poetry run pytest -v
```

### Environment Variables

Ensure database connection is configured:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/imda_policy"
poetry run pytest -v
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: user
          POSTGRES_PASSWORD: pass
          POSTGRES_DB: imda_policy
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install poetry
          poetry install

      - name: Run unit tests
        run: |
          cd backend
          poetry run pytest -m "not integration" --cov=app --cov-fail-under=80
```

### Skipping Integration Tests in CI

Integration tests are skipped by default in CI:

```bash
pytest -m "not integration"
```

To explicitly run integration tests (e.g., nightly builds):

```bash
pytest -m ""  # Run all tests including integration
```

---

## Test Data

### Mock Data

Unit tests use mock data defined inline:

```python
def test_parse_json(self):
    connector = SingStatConnector()
    json_data = '{"Data": {"row": [{"rowKey": "Total", "columns": [{"key": "2022", "value": 100}]}]}}'
    df = connector.parse(json_data.encode(), format_hint="json")
    assert not df.empty
```

### Pinned Resource IDs

Integration tests use stable, pinned resource IDs:

| Connector | Resource ID | Description |
|-----------|-------------|-------------|
| SingStat | `M213911` | Consumer Price Index (stable TS table) |
| Data.gov.sg | `d_c1295bd1935f06ac0646a10efbf07dbf` | Known stable dataset |

---

## Troubleshooting

### Tests Hang or Timeout

**Network issues with integration tests:**
```bash
# Skip integration tests
pytest -m "not integration" -v
```

**Database connection issues:**
```bash
# Check PostgreSQL is running
docker-compose -f infra/docker-compose.yml ps postgres
```

### Import Errors

**Missing dependencies:**
```bash
docker-compose -f infra/docker-compose.yml exec api poetry install
```

### Database State Issues

**Reset test database:**
```bash
docker-compose -f infra/docker-compose.yml down -v
docker-compose -f infra/docker-compose.yml up -d
```

### Stale Test Cache

**Clear pytest cache:**
```bash
docker-compose -f infra/docker-compose.yml exec api rm -rf .pytest_cache
```

---

## Adding New Tests

### Unit Test Template

```python
# tests/test_my_feature.py
import pytest
from app.my_module import MyClass


class TestMyClass:
    """Tests for MyClass."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        obj = MyClass()
        result = obj.do_something()
        assert result == expected_value

    def test_edge_case(self):
        """Test edge case handling."""
        obj = MyClass()
        with pytest.raises(ValueError):
            obj.do_something_invalid()
```

### Integration Test Template

```python
# tests/integration/test_my_integration.py
import pytest

pytestmark = pytest.mark.integration


class TestMyIntegration:
    """Integration tests for external service."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        return MyClient()

    def test_live_api_call(self, client):
        """Test against live API."""
        result = client.fetch_data()
        assert result is not None
```

---

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-29
**Task:** 220-singstat
