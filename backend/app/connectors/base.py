"""
Base connector interface for all data sources.
Defines the standard contract for data discovery, fetching, parsing, validation, and cleaning.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime


@dataclass
class DatasetCandidate:
    """
    Represents a dataset that can be fetched from a source.
    """

    name: str
    description: str
    source_type: str
    format: str
    uri: str
    metadata: Dict[str, Any]


@dataclass
class QualityReport:
    """
    Data quality validation report.
    """

    status: str  # 'passed', 'warning', 'failed'
    issues: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    completeness_score: float
    missing_value_percentage: float
    duplicate_row_count: int
    time_series_gaps: Optional[List[Dict[str, Any]]]
    full_report: Dict[str, Any]


@dataclass
class CleaningResult:
    """
    Result of data cleaning operation.
    """

    cleaned_df: pd.DataFrame
    cleaning_logs: List[Dict[str, Any]]


class BaseConnector(ABC):
    """
    Abstract base class for all data source connectors.

    All connectors must implement:
    - discover(intent) -> List[DatasetCandidate]
    - fetch(dataset_ref) -> bytes
    - parse(raw_bytes) -> pd.DataFrame
    - validate(df) -> QualityReport
    - clean(df) -> CleaningResult
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize connector with optional configuration.

        Args:
            config: Connector-specific configuration (API keys, URLs, etc.)
        """
        self.config = config or {}

    @abstractmethod
    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Discover datasets matching the given intent/query.

        Args:
            intent: User's search query or intent description

        Returns:
            List of dataset candidates that match the intent
        """
        pass

    @abstractmethod
    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch raw dataset bytes from the source.

        Args:
            dataset_ref: Reference to the dataset (URL, ID, or query)

        Returns:
            Raw bytes of the dataset
        """
        pass

    @abstractmethod
    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse raw bytes into a pandas DataFrame.

        Args:
            raw_bytes: Raw dataset bytes
            format_hint: Optional format hint ('csv', 'excel', 'json')

        Returns:
            Parsed DataFrame
        """
        pass

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> QualityReport:
        """
        Validate dataset quality and structure.

        Args:
            df: DataFrame to validate

        Returns:
            Quality report with validation results
        """
        pass

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> CleaningResult:
        """
        Clean and normalize the dataset.

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame and cleaning logs
        """
        pass

    def fetch_and_parse(
        self, dataset_ref: str, format_hint: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Convenience method to fetch and parse in one call.

        Args:
            dataset_ref: Reference to the dataset
            format_hint: Optional format hint

        Returns:
            Parsed DataFrame
        """
        raw_bytes = self.fetch(dataset_ref)
        return self.parse(raw_bytes, format_hint)

    def get_provenance_info(
        self, dataset_ref: str, df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Generate provenance information for a dataset.

        Args:
            dataset_ref: Reference to the dataset
            df: The DataFrame (for statistics)

        Returns:
            Provenance metadata dictionary
        """
        return {
            "source_name": self.__class__.__name__.replace("Connector", ""),
            "source_uri": dataset_ref,
            "retrieved_at": datetime.utcnow(),
            "retrieval_method": "api",  # Override in subclasses
            "row_count": len(df),
            "column_count": len(df.columns),
        }

    def get_schema_snapshot(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate schema snapshot from DataFrame.

        Args:
            df: DataFrame to analyze

        Returns:
            Schema information dictionary
        """
        schema = {
            "columns": [],
            "dtypes": {},
            "nullable": {},
        }

        for col in df.columns:
            schema["columns"].append(col)
            schema["dtypes"][col] = str(df[col].dtype)
            schema["nullable"][col] = df[col].isna().any()

        return schema

    @staticmethod
    def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to snake_case.

        Args:
            df: DataFrame to normalize

        Returns:
            DataFrame with normalized column names
        """
        df_copy = df.copy()
        df_copy.columns = [
            col.lower().replace(" ", "_").replace("-", "_").strip()
            for col in df_copy.columns
        ]
        return df_copy
