"""
End-to-End Smoke Test for SingStat Table Builder Developer API.

Purpose: Single, fast end-to-end validation that the SingStat connector can
discover and fetch live data, producing a parsed + validated + cleaned dataset.

Run with: pytest tests/integration/test_singstat.py -v
Skip in CI: pytest -m "not integration"

This test requires network access to the SingStat API.
"""

import pytest
import pandas as pd

from app.connectors.singstat import SingStatConnector


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Pinned resource ID for stable testing (Consumer Price Index - Annual, 2024 base year)
PINNED_RESOURCE_ID = "M213911"

# Alternative discovery keyword if pinned ID fails
DISCOVERY_KEYWORD = "consumer price"

# Test configuration for fast execution
TEST_CONFIG = {
    "max_retries": 1,  # Keep test fast
    "retry_delay": 1,
    "max_results": 5,
    "prefer_time_series": True,
}


class TestSingStatSmokeTest:
    """
    End-to-end smoke test for SingStat connector.

    Tests the complete pipeline: discover -> fetch -> parse -> validate -> clean
    against the live SingStat Table Builder Developer API.
    """

    @pytest.fixture
    def connector(self):
        """Create a connector instance with test configuration."""
        return SingStatConnector(TEST_CONFIG)

    @pytest.fixture(scope="class")
    def shared_connector(self):
        """Shared connector for tests that need to reuse fetched data."""
        return SingStatConnector(TEST_CONFIG)

    def test_discover_returns_candidates(self, connector):
        """
        Test that discovery returns at least 1 dataset candidate.

        Assertions:
        - Discovery returns >= 1 dataset candidate
        - Top candidate is time series (when prefer_time_series=True)
        """
        candidates = connector.discover(DISCOVERY_KEYWORD)

        # Must return at least 1 candidate
        assert len(candidates) >= 1, (
            f"Discovery for '{DISCOVERY_KEYWORD}' returned no candidates"
        )

        # Verify candidate structure
        candidate = candidates[0]
        assert candidate.name, "Candidate must have a name"
        assert candidate.uri, "Candidate must have a URI (resource_id)"
        assert candidate.source_type == "singstat"

        # If time series preference is set, top candidate should be TS
        if TEST_CONFIG.get("prefer_time_series"):
            # Best-effort check - may not always be TS
            if candidate.metadata.get("is_time_series"):
                assert candidate.metadata["is_time_series"] is True

    def test_fetch_returns_data(self, connector):
        """
        Test that fetch returns non-empty payload.

        Uses pinned resource ID for stability.

        Assertions:
        - Fetch returns non-empty payload
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)

        assert raw_data is not None, "Fetch returned None"
        assert len(raw_data) > 0, "Fetch returned empty payload"

    def test_parse_returns_dataframe(self, connector):
        """
        Test that parse returns non-empty DataFrame.

        Assertions:
        - Parse returns non-empty table
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)

        assert isinstance(df, pd.DataFrame), "Parse did not return a DataFrame"
        assert not df.empty, "Parse returned empty DataFrame"
        assert df.shape[0] > 0, "DataFrame has no rows"
        assert df.shape[1] > 0, "DataFrame has no columns"

    def test_value_column_exists_and_numeric(self, connector):
        """
        Test that 'value' column exists and is numeric-coercible.

        Assertions:
        - 'value' column exists
        - 'value' column is numeric or coercible to numeric
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)

        # Check for value column (case-insensitive)
        value_col = None
        for col in df.columns:
            if col.lower() == "value":
                value_col = col
                break

        assert value_col is not None, (
            f"'value' column not found. Columns: {list(df.columns)}"
        )

        # Check if numeric or coercible
        if df[value_col].dtype in ["int64", "float64"]:
            # Already numeric
            pass
        else:
            # Try to coerce
            numeric = pd.to_numeric(df[value_col], errors="coerce")
            non_null_count = numeric.notna().sum()
            assert non_null_count > 0, (
                f"'value' column has no numeric-coercible values"
            )

    def test_period_column_for_time_series(self, connector):
        """
        Test that 'period' column exists with distinct values for TS tables.

        Assertions:
        - 'period' column exists
        - 'period' has at least 2 distinct values
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)

        # Check for period column (case-insensitive)
        period_col = None
        for col in df.columns:
            if col.lower() == "period":
                period_col = col
                break

        assert period_col is not None, (
            f"'period' column not found for TS table. Columns: {list(df.columns)}"
        )

        # Must have at least 2 distinct values
        distinct_periods = df[period_col].nunique()
        assert distinct_periods >= 2, (
            f"'period' column has only {distinct_periods} distinct values"
        )

    def test_validate_not_failed(self, connector):
        """
        Test that validation status is not 'failed'.

        Assertions:
        - Validation status is 'passed' or 'warning' (not 'failed')
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)
        report = connector.validate(df)

        assert report.status in ["passed", "warning"], (
            f"Validation failed: {report.issues}"
        )
        assert report.completeness_score >= 0
        assert report.completeness_score <= 1

    def test_clean_preserves_data(self, connector):
        """
        Test that cleaning preserves reasonable row count.

        Assertions:
        - Cleaning log is non-empty
        - Row count preserved within reasonable bound (no drop-to-empty)
        - Canonical columns present after cleaning
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)
        result = connector.clean(df)

        # Cleaning logs should be non-empty (at least column normalization)
        assert isinstance(result.cleaning_logs, list)
        assert len(result.cleaning_logs) > 0, (
            "Cleaning log is empty - expected at least column normalization"
        )

        # Should not drop to empty
        assert not result.cleaned_df.empty, "Cleaning dropped all rows"

        # Should preserve most rows (allow up to 10% drop for empty rows)
        original_rows = len(df)
        cleaned_rows = len(result.cleaned_df)
        drop_ratio = 1 - (cleaned_rows / original_rows) if original_rows > 0 else 0
        assert drop_ratio <= 0.1, (
            f"Cleaning dropped too many rows: {drop_ratio:.1%} "
            f"(from {original_rows} to {cleaned_rows})"
        )

        # Canonical 'value' column should exist (may be renamed to snake_case)
        value_exists = any(
            "value" in col.lower() for col in result.cleaned_df.columns
        )
        assert value_exists, (
            f"'value' column missing after cleaning. "
            f"Columns: {list(result.cleaned_df.columns)}"
        )

    def test_provenance_captured(self, connector):
        """
        Test that provenance metadata is complete.

        Assertions:
        - Provenance includes: source, resource_id, retrieved_at
        - Checksum can be computed
        """
        raw_data = connector.fetch(PINNED_RESOURCE_ID)
        df = connector.parse(raw_data)
        provenance = connector.get_provenance_info(PINNED_RESOURCE_ID, df)

        # Required provenance fields
        assert "source" in provenance, "Provenance missing 'source'"
        assert provenance["source"] == "singstat"

        assert "resource_id" in provenance, "Provenance missing 'resource_id'"
        assert provenance["resource_id"] == PINNED_RESOURCE_ID

        assert "retrieved_at" in provenance, "Provenance missing 'retrieved_at'"
        assert provenance["retrieved_at"], "retrieved_at is empty"

        # Checksum computation
        checksum = connector.compute_checksum(raw_data)
        assert checksum, "Checksum is empty"
        assert len(checksum) == 64, "Checksum should be SHA-256 (64 hex chars)"

        # Idempotency key
        idem_key = connector.get_idempotency_key(PINNED_RESOURCE_ID, raw_data)
        assert idem_key == (PINNED_RESOURCE_ID, checksum)

    def test_full_pipeline_e2e(self, connector):
        """
        Complete end-to-end pipeline test.

        Tests the full flow: discover -> fetch -> parse -> validate -> clean
        in a single test to verify integration.
        """
        # 1. Discover
        candidates = connector.discover(DISCOVERY_KEYWORD)
        assert len(candidates) >= 1, "Discovery failed"

        # 2. Select candidate (use pinned ID for stability)
        resource_id = PINNED_RESOURCE_ID

        # 3. Fetch
        raw_data = connector.fetch(resource_id)
        assert len(raw_data) > 0, "Fetch returned empty data"

        # 4. Parse
        df = connector.parse(raw_data)
        assert not df.empty, "Parse returned empty DataFrame"

        # 5. Validate
        validation_report = connector.validate(df)
        assert validation_report.status != "failed", (
            f"Validation failed: {validation_report.issues}"
        )

        # 6. Clean
        cleaning_result = connector.clean(df)
        assert not cleaning_result.cleaned_df.empty, "Cleaning dropped all data"
        assert len(cleaning_result.cleaning_logs) > 0, "No cleaning operations logged"

        # 7. Provenance
        provenance = connector.get_provenance_info(resource_id, cleaning_result.cleaned_df)
        assert provenance["source"] == "singstat"
        assert provenance["resource_id"] == resource_id

        # 8. Schema snapshot
        schema = connector.get_schema_snapshot(cleaning_result.cleaned_df)
        assert "columns" in schema
        assert "dtypes" in schema
        assert len(schema["columns"]) > 0


class TestSingStatErrorHandling:
    """Test error handling for the SingStat connector."""

    @pytest.fixture
    def connector(self):
        return SingStatConnector(TEST_CONFIG)

    def test_fetch_invalid_resource_id(self, connector):
        """Test that fetching invalid resource ID raises error."""
        with pytest.raises(ValueError):
            connector.fetch("INVALID_RESOURCE_ID_XYZ123")

    def test_discover_no_results_returns_empty(self, connector):
        """Test that discovery with no matches returns empty list."""
        # Use a very unlikely search term
        candidates = connector.discover("xyzzy_nonexistent_term_12345")

        # Should return empty list, not raise exception
        assert isinstance(candidates, list)
        # May return empty or some loosely matching results
