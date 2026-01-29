"""
Tests for data source connectors.
"""

import pandas as pd

from app.connectors import SingStatConnector, InternalConnector
from app.connectors.base import DatasetCandidate


class TestSingStatConnector:
    """Tests for DOS SingStat connector."""

    def test_parse_csv(self):
        """Test CSV parsing."""
        connector = SingStatConnector()

        csv_data = "year,value\n2022,100\n2023,150"
        raw_bytes = csv_data.encode('utf-8')

        df = connector.parse(raw_bytes, format_hint="csv")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_parse_json(self):
        """Test JSON parsing into tidy format."""
        connector = SingStatConnector()

        json_data = '{"Data": {"row": [{"rowKey": "Total", "columns": [{"key": "2022", "value": 100}, {"key": "2023", "value": 150}]}]}}'
        raw_bytes = json_data.encode('utf-8')

        df = connector.parse(raw_bytes, format_hint="json")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "period" in df.columns
        assert "value" in df.columns

    def test_standardize_time_columns(self):
        """Test time column name standardization."""
        connector = SingStatConnector()

        df = pd.DataFrame({
            "yr": [2022, 2023],
            "qtr": ["Q1", "Q2"],
            "value": [100, 150],
        })

        renamed = connector._standardize_time_columns(df)

        assert "year" in df.columns
        assert "quarter" in df.columns

    def test_validate_empty_dataset(self):
        """Test validation fails for empty dataset."""
        connector = SingStatConnector()

        df = pd.DataFrame()
        report = connector.validate(df)

        assert report.status == "failed"
        assert any(i["type"] == "empty_dataset" for i in report.issues)

    def test_validate_valid_dataset(self):
        """Test validation passes for valid dataset."""
        connector = SingStatConnector()

        df = pd.DataFrame({
            "period": ["2022", "2023"],
            "value": [100, 150],
        })
        report = connector.validate(df)

        assert report.status in ["passed", "warning"]
        assert report.completeness_score == 1.0

    def test_clean_normalizes_columns(self):
        """Test cleaning normalizes column names."""
        connector = SingStatConnector()

        df = pd.DataFrame({
            "Period Value": ["2022", "2023"],
            "Total Amount": [100, 150],
        })
        result = connector.clean(df)

        assert "period_value" in result.cleaned_df.columns
        assert "total_amount" in result.cleaned_df.columns
        assert len(result.cleaning_logs) > 0

    def test_compute_checksum(self):
        """Test checksum computation."""
        connector = SingStatConnector()

        data = b"test data for checksum"
        checksum = connector.compute_checksum(data)

        assert len(checksum) == 64  # SHA-256 hex string
        # Same data should produce same checksum
        assert connector.compute_checksum(data) == checksum

    def test_get_idempotency_key(self):
        """Test idempotency key generation."""
        connector = SingStatConnector()

        data = b"test data"
        key = connector.get_idempotency_key("M123456", data)

        assert key[0] == "M123456"
        assert len(key[1]) == 64  # checksum

    def test_extract_resource_id_from_url(self):
        """Test resource ID extraction from URLs."""
        connector = SingStatConnector()

        # Full URL
        url = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212881"
        assert connector._extract_resource_id(url) == "M212881"

        # Plain ID
        assert connector._extract_resource_id("M212881") == "M212881"

        # With query params
        url_with_params = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M182011?format=csv"
        assert connector._extract_resource_id(url_with_params) == "M182011"


class TestInternalConnector:
    """Tests for internal PostgreSQL connector."""

    def test_discover(self):
        """Test internal dataset discovery."""
        connector = InternalConnector()

        candidates = connector.discover("employment")

        assert len(candidates) > 0
        assert all(c.source_type == "internal" for c in candidates)
        assert all(c.format == "database" for c in candidates)

    def test_list_tables(self):
        """Test listing available tables."""
        connector = InternalConnector()

        tables = connector.list_tables()

        assert "digital_sector_employment" in tables
        assert "ai_workforce_programmes" in tables
        assert "online_safety_incidents_summary" in tables
        assert "emerging_tech_adoption_index" in tables

    def test_get_table_info(self):
        """Test getting table metadata."""
        connector = InternalConnector()

        info = connector.get_table_info("digital_sector_employment")

        assert info is not None
        assert "name" in info
        assert "description" in info
        assert "key_columns" in info

    def test_validate_internal_data(self):
        """Test validation for internal data (more lenient)."""
        connector = InternalConnector()

        df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [100, 200, 300],
        })

        report = connector.validate(df)

        # Internal data should have high trust
        assert report.full_report["trust_level"] == "high"
