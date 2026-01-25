"""
Tests for data service.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch

from app.services.data_service import DataService
from app.models.dataset import Dataset


class TestDataService:
    """Tests for DataService."""

    def test_discover_datasets(self, test_db):
        """Test dataset discovery across sources."""
        service = DataService(test_db)

        # Mock connector responses
        with patch.object(service.connectors['data.gov.sg'], 'discover', return_value=[]):
            with patch.object(service.connectors['singstat'], 'discover', return_value=[]):
                with patch.object(service.connectors['internal'], 'discover', return_value=[]):
                    results = service.discover_datasets("employment")

                    # Should call all connectors
                    assert isinstance(results, list)

    def test_ingest_dataset_internal(self, test_db):
        """Test ingesting an internal dataset."""
        service = DataService(test_db)

        # Create mock DataFrame
        mock_df = pd.DataFrame({
            "id": [1, 2, 3],
            "sector": ["tech", "finance", "healthcare"],
            "value": [100, 200, 300],
        })

        # Mock the internal connector
        with patch.object(
            service.connectors['internal'],
            'fetch_dataframe',
            return_value=mock_df
        ):
            dataset = service.ingest_dataset(
                source_type="internal",
                dataset_ref="table:digital_sector_employment",
                name="Test Internal Dataset",
            )

            assert dataset.id is not None
            assert dataset.name == "Test Internal Dataset"
            assert dataset.source_type == "internal"
            assert dataset.row_count == 3
            assert dataset.column_count == 3
            assert dataset.status in ["validated", "warning"]

    def test_get_dataset_with_metadata(self, test_db):
        """Test retrieving dataset with full metadata."""
        service = DataService(test_db)

        # Create mock DataFrame
        mock_df = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"],
        })

        # Ingest dataset
        with patch.object(
            service.connectors['internal'],
            'fetch_dataframe',
            return_value=mock_df
        ):
            dataset = service.ingest_dataset(
                source_type="internal",
                dataset_ref="table:test_table",
                name="Test Dataset",
            )

            # Retrieve with metadata
            metadata = service.get_dataset_with_metadata(dataset.id)

            assert metadata is not None
            assert "dataset" in metadata
            assert "provenance" in metadata
            assert "validation" in metadata
            assert "cleaning_logs" in metadata

            assert metadata["dataset"]["id"] == dataset.id
            assert metadata["dataset"]["name"] == "Test Dataset"

    def test_list_datasets(self, test_db):
        """Test listing datasets with filters."""
        service = DataService(test_db)

        # Create test datasets
        dataset1 = Dataset(
            name="Dataset 1",
            source_type="internal",
            format="database",
            schema_snapshot={"columns": []},
            row_count=10,
            column_count=2,
            status="validated",
        )

        dataset2 = Dataset(
            name="Dataset 2",
            source_type="data.gov.sg",
            format="csv",
            schema_snapshot={"columns": []},
            row_count=20,
            column_count=3,
            status="validated",
        )

        test_db.add(dataset1)
        test_db.add(dataset2)
        test_db.commit()

        # List all datasets
        all_datasets = service.list_datasets()
        assert len(all_datasets) == 2

        # Filter by source type
        internal_datasets = service.list_datasets(source_type="internal")
        assert len(internal_datasets) == 1
        assert internal_datasets[0].name == "Dataset 1"

        # Filter by status
        validated_datasets = service.list_datasets(status="validated")
        assert len(validated_datasets) == 2

    def test_persist_dataset(self, test_db):
        """Test persisting dataset with all metadata."""
        service = DataService(test_db)

        # Create test data
        df = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"],
        })

        from app.connectors.base import QualityReport, CleaningResult

        validation_report = QualityReport(
            status="passed",
            issues=[],
            warnings=[],
            completeness_score=1.0,
            missing_value_percentage=0.0,
            duplicate_row_count=0,
            time_series_gaps=None,
            full_report={},
        )

        cleaning_result = CleaningResult(
            cleaned_df=df,
            cleaning_logs=[
                {
                    "operation": "test_op",
                    "description": "Test operation",
                    "parameters": {},
                }
            ],
        )

        provenance_info = {
            "source_name": "Test Source",
            "source_uri": "test://uri",
            "retrieved_at": pd.Timestamp.now(),
            "retrieval_method": "test",
        }

        # Persist
        dataset = service._persist_dataset(
            name="Test Dataset",
            source_type="test",
            format="csv",
            df=df,
            raw_bytes=b"test data",
            validation_report=validation_report,
            cleaning_result=cleaning_result,
            provenance_info=provenance_info,
        )

        # Verify
        assert dataset.id is not None
        assert dataset.provenance is not None
        assert len(dataset.validation_reports) == 1
        assert len(dataset.cleaning_logs) == 1
