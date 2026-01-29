"""
Tests for data source connectors.
"""

import pandas as pd

from app.connectors import SingStatConnector, InternalConnector
from app.connectors.base import DatasetCandidate


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
