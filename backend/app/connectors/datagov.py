"""
Data.gov.sg connector implementation.
Supports API-based search and fetching with CSV fallback.
"""

import requests
import pandas as pd
import io
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.connectors.base import (
    BaseConnector,
    DatasetCandidate,
    QualityReport,
    CleaningResult,
)


class DataGovConnector(BaseConnector):
    """
    Connector for Data.gov.sg open data portal.

    Features:
    - REST API for dataset discovery and fetching
    - CSV fallback for direct downloads
    - Exponential backoff retry logic
    - Rate limiting compliance
    """

    BASE_URL = "https://data.gov.sg/api"
    DATASET_SEARCH_URL = f"{BASE_URL}/action/package_search"
    DATASTORE_SEARCH_URL = f"{BASE_URL}/action/datastore_search"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_retries = config.get("max_retries", 3) if config else 3
        self.retry_delay = config.get("retry_delay", 1) if config else 1

    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Search Data.gov.sg for datasets matching the intent.

        Args:
            intent: Search query or keywords

        Returns:
            List of dataset candidates
        """
        candidates = []

        try:
            # Search for datasets using the package_search API
            params = {"q": intent, "rows": 10}
            response = self._make_request_with_retry(
                self.DATASET_SEARCH_URL, params=params
            )

            if response and response.get("success"):
                results = response.get("result", {}).get("results", [])

                for result in results:
                    # Extract dataset information
                    name = result.get("name", "")
                    title = result.get("title", name)
                    description = result.get("notes", "")

                    # Get resources (files/APIs)
                    resources = result.get("resources", [])

                    for resource in resources:
                        format_type = resource.get("format", "").lower()
                        url = resource.get("url", "")

                        if format_type in ["csv", "json", "api"]:
                            candidate = DatasetCandidate(
                                name=f"{title} - {resource.get('name', '')}",
                                description=description,
                                source_type="data.gov.sg",
                                format=format_type,
                                uri=url,
                                metadata={
                                    "package_id": result.get("id"),
                                    "resource_id": resource.get("id"),
                                    "last_modified": resource.get("last_modified"),
                                    "organization": result.get("organization", {}).get("title"),
                                },
                            )
                            candidates.append(candidate)

        except Exception as e:
            print(f"Error discovering datasets from Data.gov.sg: {e}")

        return candidates

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch dataset from Data.gov.sg.

        Args:
            dataset_ref: URL or resource ID

        Returns:
            Raw bytes of the dataset
        """
        try:
            # Try direct download first
            response = self._make_request_with_retry(dataset_ref, is_json=False)
            if response:
                return response.content

        except Exception as e:
            print(f"Error fetching dataset from Data.gov.sg: {e}")
            raise

        raise ValueError(f"Failed to fetch dataset from {dataset_ref}")

    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse raw bytes into DataFrame.

        Args:
            raw_bytes: Raw dataset bytes
            format_hint: Format hint ('csv', 'json')

        Returns:
            Parsed DataFrame
        """
        try:
            if format_hint == "json" or not format_hint:
                # Try JSON first
                try:
                    data = pd.read_json(io.BytesIO(raw_bytes))
                    return data
                except:
                    pass

            # Default to CSV
            data = pd.read_csv(io.BytesIO(raw_bytes))
            return data

        except Exception as e:
            raise ValueError(f"Failed to parse dataset: {e}")

    def validate(self, df: pd.DataFrame) -> QualityReport:
        """
        Validate dataset quality.

        Args:
            df: DataFrame to validate

        Returns:
            Quality report
        """
        issues = []
        warnings = []

        # Check for empty dataframe
        if df.empty:
            issues.append({"type": "empty_dataset", "message": "DataFrame is empty"})

        # Check for duplicate rows
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            warnings.append({
                "type": "duplicate_rows",
                "message": f"Found {duplicate_count} duplicate rows",
                "count": int(duplicate_count)
            })

        # Check for missing values
        total_cells = df.shape[0] * df.shape[1]
        missing_cells = df.isna().sum().sum()
        missing_percentage = (missing_cells / total_cells * 100) if total_cells > 0 else 0

        if missing_percentage > 50:
            issues.append({
                "type": "high_missing_values",
                "message": f"Missing values exceed 50% ({missing_percentage:.2f}%)",
                "percentage": missing_percentage
            })
        elif missing_percentage > 10:
            warnings.append({
                "type": "moderate_missing_values",
                "message": f"Missing values: {missing_percentage:.2f}%",
                "percentage": missing_percentage
            })

        # Calculate completeness score
        completeness_score = 1.0 - (missing_percentage / 100)

        # Determine overall status
        status = "passed"
        if issues:
            status = "failed"
        elif warnings:
            status = "warning"

        return QualityReport(
            status=status,
            issues=issues,
            warnings=warnings,
            completeness_score=completeness_score,
            missing_value_percentage=missing_percentage,
            duplicate_row_count=int(duplicate_count),
            time_series_gaps=None,  # Not applicable for general datasets
            full_report={
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            },
        )

    def clean(self, df: pd.DataFrame) -> CleaningResult:
        """
        Clean and normalize the dataset.

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame and logs
        """
        cleaning_logs = []
        cleaned_df = df.copy()

        # 1. Normalize column names
        original_columns = list(cleaned_df.columns)
        cleaned_df = self.normalize_column_names(cleaned_df)
        new_columns = list(cleaned_df.columns)

        if original_columns != new_columns:
            cleaning_logs.append({
                "operation": "normalize_columns",
                "description": "Normalized column names to snake_case",
                "parameters": {},
                "columns_affected": original_columns,
                "sample_before": {"columns": original_columns},
                "sample_after": {"columns": new_columns},
            })

        # 2. Convert numeric strings to numbers
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                try:
                    # Try to convert to numeric
                    numeric_col = pd.to_numeric(cleaned_df[col], errors="coerce")
                    if numeric_col.notna().sum() > 0:
                        original_dtype = str(cleaned_df[col].dtype)
                        cleaned_df[col] = numeric_col
                        cleaning_logs.append({
                            "operation": "convert_numeric",
                            "description": f"Converted column '{col}' from {original_dtype} to numeric",
                            "parameters": {"column": col},
                            "columns_affected": [col],
                        })
                except:
                    pass

        # 3. Parse dates (look for common date column names)
        date_columns = [col for col in cleaned_df.columns if any(
            keyword in col.lower() for keyword in ["date", "time", "year", "month", "quarter"]
        )]

        for col in date_columns:
            try:
                parsed_dates = pd.to_datetime(cleaned_df[col], errors="coerce")
                if parsed_dates.notna().sum() > 0:
                    cleaned_df[col] = parsed_dates
                    cleaning_logs.append({
                        "operation": "parse_dates",
                        "description": f"Parsed column '{col}' as datetime",
                        "parameters": {"column": col},
                        "columns_affected": [col],
                    })
            except:
                pass

        # 4. Remove completely empty columns
        empty_cols = [col for col in cleaned_df.columns if cleaned_df[col].isna().all()]
        if empty_cols:
            cleaned_df = cleaned_df.drop(columns=empty_cols)
            cleaning_logs.append({
                "operation": "remove_empty_columns",
                "description": f"Removed {len(empty_cols)} completely empty columns",
                "parameters": {},
                "columns_affected": empty_cols,
            })

        return CleaningResult(
            cleaned_df=cleaned_df,
            cleaning_logs=cleaning_logs,
        )

    def _make_request_with_retry(
        self, url: str, params: Optional[Dict] = None, is_json: bool = True
    ) -> Any:
        """
        Make HTTP request with exponential backoff retry logic.

        Args:
            url: URL to request
            params: Query parameters
            is_json: Whether to parse response as JSON

        Returns:
            Response data or response object
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()

                if is_json:
                    return response.json()
                else:
                    return response

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"Request failed, retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    print(f"Request failed after {self.max_retries} attempts: {e}")
                    raise

        return None

    def get_provenance_info(self, dataset_ref: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate provenance information for Data.gov.sg dataset.

        Args:
            dataset_ref: Dataset URL or ID
            df: The DataFrame

        Returns:
            Provenance metadata
        """
        return {
            "source_name": "Data.gov.sg",
            "source_uri": dataset_ref,
            "api_endpoint": self.BASE_URL,
            "retrieved_at": datetime.utcnow(),
            "retrieval_method": "api",
            "row_count": len(df),
            "column_count": len(df.columns),
            "data_owner": "Government of Singapore",
            "license_info": "Singapore Open Data License",
        }
