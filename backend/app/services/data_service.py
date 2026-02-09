"""
Data service for managing dataset ingestion, validation, cleaning, and provenance.
Provides high-level interface for working with data connectors.
"""

import hashlib
import uuid as uuid_module
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.connectors.base import BaseConnector, QualityReport, CleaningResult
from app.connectors import DataGovV2Connector, SingStatConnector, InternalConnector
from app.core.config import settings
from app.db.repo_data_gov_sg_collection import search_collections
from app.models.dataset import Dataset, DatasetProvenance, ValidationReport, CleaningLog
from app.models.run import RunDatasetSnapshot

logger = logging.getLogger(__name__)
RUN_DATASET_SNAPSHOT_MAX_ROWS = 2000


class DataService:
    """
    Service for managing dataset lifecycle:
    - Discovery
    - Fetching
    - Parsing
    - Validation
    - Cleaning
    - Provenance tracking
    - Metadata persistence
    """

    def __init__(self, db: Session):
        """
        Initialize data service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.connectors: Dict[str, BaseConnector] = {
            "data.gov.sg": DataGovV2Connector(
                config={"api_key": settings.data_gov_sg_api_key}
            ),
            "singstat": SingStatConnector(),
            "internal": InternalConnector(),
        }

    def discover_datasets(self, intent: str, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Discover datasets across configured sources based on user intent.

        Args:
            intent: Search query or intent description
            sources: Optional list of source types to search (default: all)

        Returns:
            List of dataset candidates with metadata
        """
        if sources is None:
            sources = list(self.connectors.keys())

        all_candidates = []

        for source_type in sources:
            if source_type == "data.gov.sg":
                try:
                    collections = search_collections(self.db, intent, limit=10)
                except Exception as e:
                    print(f"Error searching data.gov.sg cache: {e}")
                    collections = []

                if collections:
                    seen_dataset_ids: set[str] = set()
                    max_datasets = 10
                    for collection in collections:
                        child_ids = collection.get("child_dataset_ids") or []
                        for dataset_id in child_ids[:2]:
                            if dataset_id in seen_dataset_ids:
                                continue
                            seen_dataset_ids.add(dataset_id)
                            all_candidates.append({
                                "name": collection.get("name") or dataset_id,
                                "description": collection.get("description") or "",
                                "source_type": "data.gov.sg",
                                "format": "api",
                                "uri": dataset_id,
                                "metadata": {
                                    "collection_id": collection.get("collection_id"),
                                    "collection_name": collection.get("name"),
                                    "last_updated_at": (
                                        collection.get("lastUpdatedAt").isoformat()
                                        if collection.get("lastUpdatedAt")
                                        else None
                                    ),
                                },
                            })
                            if len(seen_dataset_ids) >= max_datasets:
                                break
                        if len(seen_dataset_ids) >= max_datasets:
                            break

                    continue

            connector = self.connectors.get(source_type)
            if connector:
                try:
                    candidates = connector.discover(intent)
                    for candidate in candidates:
                        all_candidates.append({
                            "name": candidate.name,
                            "description": candidate.description,
                            "source_type": candidate.source_type,
                            "format": candidate.format,
                            "uri": candidate.uri,
                            "metadata": candidate.metadata,
                        })
                except Exception as e:
                    print(f"Error discovering from {source_type}: {e}")

        return all_candidates

    def ingest_dataset(
        self,
        source_type: str,
        dataset_ref: str,
        name: str,
        format_hint: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dataset:
        """
        Ingest a dataset through the full pipeline:
        fetch -> parse -> validate -> clean -> persist

        Args:
            source_type: Type of data source ('data.gov.sg', 'singstat', 'internal')
            dataset_ref: Reference to the dataset (URL, table name, etc.)
            name: Display name for the dataset
            format_hint: Optional format hint

        Returns:
            Persisted Dataset object with all metadata
        """
        connector = self.connectors.get(source_type)
        if not connector:
            raise ValueError(f"Unknown source type: {source_type}")

        # Special handling for internal database queries
        if source_type == "internal":
            table_name = dataset_ref.replace("table:", "")
            df = connector.fetch_dataframe(table_name)
            raw_bytes = b""
        else:
            # 1. Fetch raw data
            raw_bytes = connector.fetch(dataset_ref)

            # 2. Parse to DataFrame
            df = connector.parse(raw_bytes, format_hint)

        # 3. Validate
        validation_report = connector.validate(df)

        # 4. Clean
        cleaning_result = connector.clean(df)

        # 5. Generate provenance info
        provenance_info = connector.get_provenance_info(dataset_ref, cleaning_result.cleaned_df)

        # 6. Persist to database
        dataset = self._persist_dataset(
            name=name,
            source_type=source_type,
            format=format_hint or "unknown",
            df=cleaning_result.cleaned_df,
            raw_bytes=raw_bytes,
            validation_report=validation_report,
            cleaning_result=cleaning_result,
            provenance_info=provenance_info,
            run_id=run_id,
        )

        return dataset

    def _persist_dataset(
        self,
        name: str,
        source_type: str,
        format: str,
        df: pd.DataFrame,
        raw_bytes: bytes,
        validation_report: QualityReport,
        cleaning_result: CleaningResult,
        provenance_info: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> Dataset:
        """
        Persist dataset and all associated metadata to database.

        Args:
            name: Dataset name
            source_type: Source type
            format: Data format
            df: Cleaned DataFrame
            raw_bytes: Original raw bytes
            validation_report: Validation results
            cleaning_result: Cleaning results
            provenance_info: Provenance metadata

        Returns:
            Persisted Dataset object
        """
        # Calculate file checksum (if raw bytes available)
        file_checksum = None
        if raw_bytes:
            file_checksum = hashlib.sha256(raw_bytes).hexdigest()

        # Generate schema snapshot
        schema_snapshot = {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "nullable": {col: bool(df[col].isna().any()) for col in df.columns},
        }

        # Determine status based on validation
        status = "validated" if validation_report.status == "passed" else "warning"

        # Create Dataset
        dataset = Dataset(
            name=name,
            source_type=source_type,
            format=format,
            schema_snapshot=schema_snapshot,
            row_count=len(df),
            column_count=len(df.columns),
            file_size_bytes=len(raw_bytes) if raw_bytes else None,
            file_checksum=file_checksum,
            status=status,
        )

        self.db.add(dataset)
        self.db.flush()  # Get dataset ID

        # Create DatasetProvenance
        provenance = DatasetProvenance(
            dataset_id=dataset.id,
            source_name=provenance_info.get("source_name", source_type),
            source_uri=provenance_info.get("source_uri", ""),
            api_endpoint=provenance_info.get("api_endpoint"),
            retrieved_at=provenance_info.get("retrieved_at", datetime.utcnow()),
            retrieval_method=provenance_info.get("retrieval_method", "unknown"),
            dataset_version=provenance_info.get("dataset_version"),
            license_info=provenance_info.get("license_info"),
            original_filename=provenance_info.get("original_filename"),
            data_owner=provenance_info.get("data_owner"),
            update_frequency=provenance_info.get("update_frequency"),
        )

        self.db.add(provenance)

        # Create ValidationReport
        validation = ValidationReport(
            dataset_id=dataset.id,
            validation_type="quality",
            status=validation_report.status,
            issues=validation_report.issues,
            warnings=validation_report.warnings,
            completeness_score=validation_report.completeness_score,
            missing_value_percentage=validation_report.missing_value_percentage,
            duplicate_row_count=validation_report.duplicate_row_count,
            time_series_gaps=validation_report.time_series_gaps,
            full_report=validation_report.full_report,
        )

        self.db.add(validation)

        # Create CleaningLogs
        for log_entry in cleaning_result.cleaning_logs:
            cleaning_log = CleaningLog(
                dataset_id=dataset.id,
                operation=log_entry.get("operation", "unknown"),
                description=log_entry.get("description", ""),
                parameters=log_entry.get("parameters", {}),
                rows_affected=log_entry.get("rows_affected"),
                columns_affected=log_entry.get("columns_affected"),
                sample_before=log_entry.get("sample_before"),
                sample_after=log_entry.get("sample_after"),
            )

            self.db.add(cleaning_log)

        # Persist run-scoped snapshot so the UI can view the exact data used in this run.
        if run_id:
            try:
                self._upsert_run_dataset_snapshot(run_id=run_id, dataset_id=dataset.id, df=df)
            except Exception as e:
                logger.warning(
                    "Failed to persist run dataset snapshot for run_id=%s dataset_id=%s: %s",
                    run_id,
                    dataset.id,
                    e,
                )

        # Commit all changes
        self.db.commit()
        self.db.refresh(dataset)

        return dataset

    def _upsert_run_dataset_snapshot(self, run_id: str, dataset_id: int, df: pd.DataFrame) -> None:
        """Persist a run-specific dataset snapshot used during this execution."""
        run_uuid = uuid_module.UUID(str(run_id))
        total_row_count = int(len(df))
        is_truncated = total_row_count > RUN_DATASET_SNAPSHOT_MAX_ROWS
        snapshot_df = df.head(RUN_DATASET_SNAPSHOT_MAX_ROWS).copy() if is_truncated else df.copy()

        columns = [str(col) for col in snapshot_df.columns.tolist()]
        rows = [
            [self._json_safe_value(value) for value in row]
            for row in snapshot_df.itertuples(index=False, name=None)
        ]

        existing = (
            self.db.query(RunDatasetSnapshot)
            .filter(
                RunDatasetSnapshot.run_id == run_uuid,
                RunDatasetSnapshot.dataset_id == dataset_id,
            )
            .first()
        )
        if existing:
            existing.columns = columns
            existing.rows = rows
            existing.total_row_count = total_row_count
            existing.is_truncated = is_truncated
        else:
            self.db.add(
                RunDatasetSnapshot(
                    run_id=run_uuid,
                    dataset_id=dataset_id,
                    columns=columns,
                    rows=rows,
                    total_row_count=total_row_count,
                    is_truncated=is_truncated,
                )
            )

    def _json_safe_value(self, value: Any) -> Any:
        """Convert pandas/numpy values to JSON-safe primitives."""
        if value is None:
            return None
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.bool_, bool)):
            return bool(value)
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (list, dict, str, int, float)):
            return value
        if pd.isna(value):
            return None
        return str(value)

    def get_dataset(self, dataset_id: int) -> Optional[Dataset]:
        """
        Retrieve dataset by ID with all relationships loaded.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dataset object or None
        """
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

    def get_dataset_with_metadata(self, dataset_id: int) -> Optional[Dict[str, Any]]:
        """
        Get dataset with all metadata (provenance, validation, cleaning logs).

        Args:
            dataset_id: Dataset ID

        Returns:
            Dictionary with dataset and all metadata
        """
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None

        return {
            "dataset": {
                "id": dataset.id,
                "name": dataset.name,
                "source_type": dataset.source_type,
                "format": dataset.format,
                "row_count": dataset.row_count,
                "column_count": dataset.column_count,
                "status": dataset.status,
                "created_at": dataset.created_at.isoformat(),
            },
            "provenance": {
                "source_name": dataset.provenance.source_name,
                "source_uri": dataset.provenance.source_uri,
                "retrieved_at": dataset.provenance.retrieved_at.isoformat(),
                "data_owner": dataset.provenance.data_owner,
                "license_info": dataset.provenance.license_info,
            } if dataset.provenance else None,
            "validation": [
                {
                    "status": v.status,
                    "issues": v.issues,
                    "warnings": v.warnings,
                    "completeness_score": v.completeness_score,
                }
                for v in dataset.validation_reports
            ],
            "cleaning_logs": [
                {
                    "operation": c.operation,
                    "description": c.description,
                    "columns_affected": c.columns_affected,
                }
                for c in dataset.cleaning_logs
            ],
        }

    def list_datasets(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dataset]:
        """
        List datasets with optional filters.

        Args:
            source_type: Filter by source type
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of datasets
        """
        query = self.db.query(Dataset)

        if source_type:
            query = query.filter(Dataset.source_type == source_type)

        if status:
            query = query.filter(Dataset.status == status)

        return query.order_by(Dataset.created_at.desc()).limit(limit).all()
