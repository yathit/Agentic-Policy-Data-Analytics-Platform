"""
Database models for dataset management, provenance, and quality tracking.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

from app.core.database import Base


class Dataset(Base):
    """
    Core dataset metadata table.
    Tracks every dataset ingested into the system with its schema and statistics.
    """

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    source_type = Column(String(100), nullable=False)  # 'data.gov.sg', 'singstat', 'internal'
    format = Column(String(50), nullable=False)  # 'csv', 'excel', 'json', 'database'

    # Schema and statistics
    schema_snapshot = Column(JSON, nullable=False)  # Column names, types, nullable info
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)

    # File information
    file_size_bytes = Column(Integer, nullable=True)
    file_checksum = Column(String(64), nullable=True)  # SHA256 hash

    # Status
    status = Column(
        String(50),
        nullable=False,
        default="pending"
    )  # 'pending', 'validated', 'cleaned', 'failed'

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    provenance = relationship(
        "DatasetProvenance",
        back_populates="dataset",
        uselist=False,
        cascade="all, delete-orphan"
    )
    validation_reports = relationship(
        "ValidationReport",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )
    cleaning_logs = relationship(
        "CleaningLog",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dataset(id={self.id}, name='{self.name}', source='{self.source_type}')>"


class DatasetProvenance(Base):
    """
    Provenance tracking for dataset retrieval and source information.
    Ensures every dataset can be traced back to its origin.
    """

    __tablename__ = "dataset_provenance"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Source information
    source_name = Column(String(255), nullable=False)  # 'Data.gov.sg', 'SingStat', 'IMDA Internal'
    source_uri = Column(Text, nullable=False)  # Full URL or database query
    api_endpoint = Column(Text, nullable=True)  # API endpoint if applicable

    # Retrieval information
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    retrieval_method = Column(String(50), nullable=False)  # 'api', 'download', 'database'

    # Additional metadata
    dataset_version = Column(String(100), nullable=True)
    license_info = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=True)

    # Contact/ownership
    data_owner = Column(String(255), nullable=True)
    update_frequency = Column(String(100), nullable=True)  # 'daily', 'monthly', 'quarterly', 'annual'

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    dataset = relationship("Dataset", back_populates="provenance")

    def __repr__(self):
        return f"<DatasetProvenance(dataset_id={self.dataset_id}, source='{self.source_name}')>"


class ValidationReport(Base):
    """
    Validation results for dataset quality checks.
    Tracks issues and warnings detected during validation.
    """

    __tablename__ = "validation_reports"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Validation metadata
    validation_type = Column(String(100), nullable=False)  # 'schema', 'quality', 'completeness'
    status = Column(String(50), nullable=False)  # 'passed', 'warning', 'failed'

    # Validation results
    issues = Column(JSON, nullable=False, default=list)  # List of issues found
    warnings = Column(JSON, nullable=False, default=list)  # List of warnings

    # Quality metrics
    completeness_score = Column(Float, nullable=True)  # 0.0 to 1.0
    missing_value_percentage = Column(Float, nullable=True)
    duplicate_row_count = Column(Integer, nullable=True)

    # Time series validation (if applicable)
    time_series_gaps = Column(JSON, nullable=True)  # List of detected gaps

    # Detailed report
    full_report = Column(JSON, nullable=False)  # Complete validation details

    # Timestamps
    validated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    dataset = relationship("Dataset", back_populates="validation_reports")

    def __repr__(self):
        return f"<ValidationReport(id={self.id}, dataset_id={self.dataset_id}, status='{self.status}')>"


class CleaningLog(Base):
    """
    Transparent log of all data cleaning operations applied to a dataset.
    No silent mutations - every transformation is recorded.
    """

    __tablename__ = "cleaning_logs"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Cleaning operation details
    operation = Column(String(100), nullable=False)  # 'normalize_columns', 'parse_dates', 'handle_missing'
    description = Column(Text, nullable=False)  # Human-readable description

    # Operation parameters
    parameters = Column(JSON, nullable=False)  # Parameters used for operation

    # Operation results
    rows_affected = Column(Integer, nullable=True)
    columns_affected = Column(JSON, nullable=True)  # List of column names

    # Before/after samples (for audit)
    sample_before = Column(JSON, nullable=True)  # Sample rows before cleaning
    sample_after = Column(JSON, nullable=True)  # Sample rows after cleaning

    # Timestamps
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    dataset = relationship("Dataset", back_populates="cleaning_logs")

    def __repr__(self):
        return f"<CleaningLog(id={self.id}, dataset_id={self.dataset_id}, operation='{self.operation}')>"
