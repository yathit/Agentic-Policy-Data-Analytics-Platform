"""
Integration tests for Data.gov.sg V2 connector.

These tests make real API calls to data.gov.sg.
Run with: pytest tests/integration/test_datagov_v2.py -v

To skip in CI, use: pytest -m "not integration"
"""

import pytest
from app.connectors.datagov_v2 import DataGovV2Connector
from app.core.database import SessionLocal
from app.services.data_service import DataService


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestDataGovV2Integration:
    """Integration tests for Data.gov.sg V2 API."""

    @pytest.fixture
    def connector(self):
        """Create a connector instance."""
        return DataGovV2Connector()

    @pytest.fixture
    def db_session(self):
        """Create a database session."""
        db = SessionLocal()
        yield db
        db.close()

    def test_fetch_real_dataset(self, connector):
        """Test fetching a real dataset from data.gov.sg."""
        # Use a known dataset ID
        dataset_id = "d_c1295bd1935f06ac0646a10efbf07dbf"

        raw_data = connector.fetch(dataset_id)

        assert raw_data is not None
        assert len(raw_data) > 0

        # Parse and verify
        df = connector.parse(raw_data)
        assert not df.empty
        assert df.shape[0] > 0

    def test_validate_real_dataset(self, connector):
        """Test validation on a real dataset."""
        dataset_id = "d_c1295bd1935f06ac0646a10efbf07dbf"

        raw_data = connector.fetch(dataset_id)
        df = connector.parse(raw_data)
        report = connector.validate(df)

        assert report.status in ["passed", "warning"]
        assert report.completeness_score >= 0
        assert report.completeness_score <= 1

    def test_clean_real_dataset(self, connector):
        """Test cleaning on a real dataset."""
        dataset_id = "d_c1295bd1935f06ac0646a10efbf07dbf"

        raw_data = connector.fetch(dataset_id)
        df = connector.parse(raw_data)
        result = connector.clean(df)

        assert result.cleaned_df is not None
        assert not result.cleaned_df.empty
        # Cleaning logs should be recorded
        assert isinstance(result.cleaning_logs, list)

    def test_discovery_via_data_service(self, db_session):
        """Test dataset discovery through DataService."""
        svc = DataService(db_session)

        candidates = svc.discover_datasets("employment", ["data.gov.sg"])

        assert len(candidates) > 0
        # Verify candidate structure
        for c in candidates:
            assert "uri" in c
            assert "name" in c
            assert c["source_type"] == "data.gov.sg"
            # URI should be a dataset ID
            assert c["uri"].startswith("d_")

    def test_full_ingest_pipeline(self, db_session):
        """Test the complete ingest pipeline."""
        svc = DataService(db_session)

        # Discover
        candidates = svc.discover_datasets("employment", ["data.gov.sg"])
        assert len(candidates) > 0

        # Pick first candidate
        candidate = candidates[0]

        # Ingest
        dataset = svc.ingest_dataset(
            source_type="data.gov.sg",
            dataset_ref=candidate["uri"],
            name=candidate["name"][:100],
            format_hint="csv",
        )

        # Verify
        assert dataset is not None
        assert dataset.id is not None
        assert dataset.row_count > 0
        assert dataset.column_count > 0
        assert dataset.status in ["validated", "warning"]
        assert dataset.source_type == "data.gov.sg"

        # Check provenance was created
        assert dataset.provenance is not None
        assert dataset.provenance.source_name == "Data.gov.sg"
        assert dataset.provenance.retrieval_method == "api_v2"

        # Check validation report exists
        assert len(dataset.validation_reports) > 0

    def test_download_api_directly(self, connector):
        """Test the download API path directly."""
        dataset_id = "d_c1295bd1935f06ac0646a10efbf07dbf"

        raw_data = connector._fetch_via_download(dataset_id)

        assert raw_data is not None
        assert len(raw_data) > 0

        # Should be valid CSV
        df = connector.parse(raw_data)
        assert not df.empty


class TestDataGovV2ErrorHandling:
    """Test error handling for the V2 connector."""

    @pytest.fixture
    def connector(self):
        return DataGovV2Connector()

    def test_fetch_invalid_dataset_id(self, connector):
        """Test fetching with invalid dataset ID raises error."""
        with pytest.raises(Exception):
            connector.fetch("invalid_dataset_id_12345")

    def test_fetch_nonexistent_dataset(self, connector):
        """Test fetching non-existent dataset raises error."""
        with pytest.raises(Exception):
            connector.fetch("d_nonexistent_dataset_xyz")
