"""
Tests for data source connectors.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
import io

from app.connectors import DataGovConnector, DataGovV2Connector, SingStatConnector, InternalConnector
from app.connectors.base import DatasetCandidate, QualityReport


class TestDataGovConnector:
    """Tests for Data.gov.sg connector."""

    def test_discover(self):
        """Test dataset discovery."""
        connector = DataGovConnector()

        # Mock the API response
        mock_response = {
            "success": True,
            "result": {
                "results": [
                    {
                        "name": "test-dataset",
                        "title": "Test Dataset",
                        "notes": "Test description",
                        "id": "123",
                        "organization": {"title": "Test Org"},
                        "resources": [
                            {
                                "id": "res-1",
                                "name": "Test Resource",
                                "format": "CSV",
                                "url": "https://example.com/data.csv",
                                "last_modified": "2024-01-01",
                            }
                        ],
                    }
                ]
            }
        }

        with patch.object(connector, '_make_request_with_retry', return_value=mock_response):
            candidates = connector.discover("employment")

            assert len(candidates) > 0
            assert isinstance(candidates[0], DatasetCandidate)
            assert candidates[0].source_type == "data.gov.sg"

    def test_parse_csv(self):
        """Test CSV parsing."""
        connector = DataGovConnector()

        # Create sample CSV data
        csv_data = "name,value\ntest,123\nfoo,456"
        raw_bytes = csv_data.encode('utf-8')

        df = connector.parse(raw_bytes, format_hint="csv")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "name" in df.columns
        assert "value" in df.columns

    def test_validate_quality(self):
        """Test data quality validation."""
        connector = DataGovConnector()

        # Create test DataFrame
        df = pd.DataFrame({
            "col1": [1, 2, 3, 4, 5],
            "col2": ["a", "b", "c", "d", "e"],
        })

        report = connector.validate(df)

        assert isinstance(report, QualityReport)
        assert report.status == "passed"
        assert report.completeness_score == 1.0
        assert report.duplicate_row_count == 0

    def test_validate_with_missing_values(self):
        """Test validation with missing values."""
        connector = DataGovConnector()

        # Create DataFrame with missing values
        df = pd.DataFrame({
            "col1": [1, None, 3, None, 5],
            "col2": ["a", "b", None, "d", None],
        })

        report = connector.validate(df)

        assert report.missing_value_percentage > 0
        assert report.missing_value_percentage == 40.0  # 4 missing out of 10 cells

    def test_clean_normalize_columns(self):
        """Test column name normalization."""
        connector = DataGovConnector()

        df = pd.DataFrame({
            "Test Column": [1, 2, 3],
            "Another-Column": [4, 5, 6],
        })

        result = connector.clean(df)

        assert "test_column" in result.cleaned_df.columns
        assert "another_column" in result.cleaned_df.columns
        assert len(result.cleaning_logs) > 0


class TestDataGovV2Connector:
    """Tests for Data.gov.sg V2 API connector."""

    def test_discover_returns_empty(self):
        """Test that discover returns empty list (discovery via DataService)."""
        connector = DataGovV2Connector()
        candidates = connector.discover("employment")
        assert candidates == []

    def test_parse_csv(self):
        """Test CSV parsing."""
        connector = DataGovV2Connector()

        csv_data = "year,sector,value\n2022,Tech,100\n2023,Tech,150"
        raw_bytes = csv_data.encode("utf-8")

        df = connector.parse(raw_bytes, format_hint="csv")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "year" in df.columns
        assert "sector" in df.columns

    def test_parse_json(self):
        """Test JSON parsing."""
        connector = DataGovV2Connector()

        json_data = '[{"year": 2022, "value": 100}, {"year": 2023, "value": 150}]'
        raw_bytes = json_data.encode("utf-8")

        df = connector.parse(raw_bytes, format_hint="json")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_validate_quality(self):
        """Test data quality validation."""
        connector = DataGovV2Connector()

        df = pd.DataFrame({
            "year": [2022, 2023, 2024],
            "value": [100, 150, 200],
        })

        report = connector.validate(df)

        assert isinstance(report, QualityReport)
        assert report.status == "passed"
        assert report.completeness_score == 1.0
        assert report.duplicate_row_count == 0

    def test_validate_with_duplicates(self):
        """Test validation detects duplicates."""
        connector = DataGovV2Connector()

        df = pd.DataFrame({
            "year": [2022, 2022, 2023],
            "value": [100, 100, 150],
        })

        report = connector.validate(df)

        assert report.duplicate_row_count == 1
        assert report.status == "warning"

    def test_clean_normalize_columns(self):
        """Test column name normalization."""
        connector = DataGovV2Connector()

        df = pd.DataFrame({
            "Year Of Data": [2022, 2023],
            "Sector-Name": ["Tech", "Finance"],
        })

        result = connector.clean(df)

        assert "year_of_data" in result.cleaned_df.columns
        assert "sector_name" in result.cleaned_df.columns
        assert len(result.cleaning_logs) > 0

    def test_clean_parse_dates(self):
        """Test date column parsing."""
        connector = DataGovV2Connector()

        df = pd.DataFrame({
            "year": ["2022", "2023"],
            "value": [100, 150],
        })

        result = connector.clean(df)

        # year column should be parsed as datetime
        assert any(
            log["operation"] == "parse_dates"
            for log in result.cleaning_logs
        )

    def test_get_provenance_info(self):
        """Test provenance metadata generation."""
        connector = DataGovV2Connector()

        df = pd.DataFrame({"col": [1, 2, 3]})
        provenance = connector.get_provenance_info("d_test123", df)

        assert provenance["source_name"] == "Data.gov.sg"
        assert provenance["retrieval_method"] == "api_v2"
        assert provenance["dataset_id"] == "d_test123"
        assert provenance["row_count"] == 3
        assert "license_info" in provenance

    def test_fetch_via_download_mocked(self):
        """Test download API flow with mocked responses."""
        connector = DataGovV2Connector()

        mock_init_response = {
            "data": {
                "url": "https://example.com/download.csv"
            }
        }

        mock_csv_content = b"year,value\n2022,100\n2023,150"

        with patch.object(connector, "_make_request_with_retry", return_value=mock_init_response):
            with patch("requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.content = mock_csv_content

                result = connector._fetch_via_download("d_test123")

                assert result == mock_csv_content


class TestSingStatConnector:
    """Tests for DOS SingStat connector."""

    def test_discover(self):
        """Test dataset discovery from known datasets."""
        connector = SingStatConnector()

        candidates = connector.discover("labour force")

        assert len(candidates) > 0
        assert isinstance(candidates[0], DatasetCandidate)
        assert candidates[0].source_type == "singstat"

    def test_parse_csv(self):
        """Test CSV parsing."""
        connector = SingStatConnector()

        csv_data = "year,value\n2022,100\n2023,150"
        raw_bytes = csv_data.encode('utf-8')

        df = connector.parse(raw_bytes, format_hint="csv")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_canonicalize_time_columns(self):
        """Test time column name standardization."""
        connector = SingStatConnector()

        df = pd.DataFrame({
            "Yr": [2022, 2023],
            "Qtr": ["Q1", "Q2"],
            "Value": [100, 150],
        })

        renamed = connector._canonicalize_time_columns(df)

        assert "year" in df.columns
        assert "quarter" in df.columns


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
