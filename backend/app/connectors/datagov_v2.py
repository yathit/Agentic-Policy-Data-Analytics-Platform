"""
Data.gov.sg V2 API connector implementation.

Uses cached collections for discovery and V2 API for data fetching.
Supports list-rows API for smaller datasets and async download for larger ones.
"""

import requests
import pandas as pd
import io
import time
import logging
from typing import List, Dict, Any, Optional

from datetime import datetime

from app.connectors.base import (
    BaseConnector,
    DatasetCandidate,
    QualityReport,
    CleaningResult,
)

logger = logging.getLogger(__name__)


class DataGovV2Connector(BaseConnector):
    """
    Connector for Data.gov.sg V2 API.

    Discovery uses cached collections from database (handled by DataService).
    Fetching uses V2 public API endpoints.

    Features:
    - list-rows API for paginated data access
    - Async download API for large datasets
    - Exponential backoff retry logic
    - Rate limiting compliance (5 req/min without API key)
    """

    # V2 API endpoints
    API_BASE_V2 = "https://api-production.data.gov.sg/v2/public/api"
    API_BASE_OPEN = "https://api-open.data.gov.sg/v1/public/api"

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_retries = config.get("max_retries", 3) if config else 3
        self.base_delay = config.get("base_delay", 2.0) if config else 2.0
        self.request_timeout = config.get("request_timeout", 30) if config else 30
        self.max_rows = config.get("max_rows", 100000) if config else 100000

    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Discover datasets from cached collections.

        NOTE: Discovery is handled by DataService which queries the
        data_gov_sg_collection table directly. This method returns
        empty list for interface compliance.

        Args:
            intent: Search keyword (unused)

        Returns:
            Empty list - discovery handled externally
        """
        return []

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch dataset data from V2 API.

        Tries list-rows API first (preferred for smaller datasets),
        falls back to async download API for larger datasets.

        Args:
            dataset_ref: Dataset ID (e.g., 'd_xxxxx')

        Returns:
            Raw bytes (CSV format)
        """
        dataset_id = dataset_ref

        # Use download API by default (more efficient for larger datasets)
        # list-rows API has rate limits (5 req/min) and returns only 10 rows per page
        try:
            return self._fetch_via_download(dataset_id)
        except Exception as e:
            logger.warning(
                "Download API failed for %s, trying list-rows: %s",
                dataset_id,
                e,
            )

        # Fallback to list-rows API
        df = self._fetch_via_list_rows(dataset_id)
        if df is not None and not df.empty:
            logger.info(
                "Fetched %d rows via list-rows API for %s",
                len(df),
                dataset_id,
            )
            return df.to_csv(index=False).encode("utf-8")

        raise ValueError(f"Failed to fetch dataset {dataset_id}")

    def _fetch_via_list_rows(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Fetch all rows using paginated list-rows API.

        Args:
            dataset_id: Dataset ID

        Returns:
            DataFrame with all rows, or None if failed
        """
        base_url = f"{self.API_BASE_V2}/datasets/{dataset_id}/list-rows"
        all_rows = []

        # Fetch first page
        response = self._make_request_with_retry(base_url)
        if not response or "data" not in response:
            return None

        data = response["data"]
        rows = data.get("rows", [])
        all_rows.extend(rows)

        # Handle pagination
        while data.get("links", {}).get("next"):
            next_link = data["links"]["next"]
            # Handle relative URLs - append to base URL
            if not next_link.startswith("http"):
                next_url = f"{base_url}?{next_link}"
            else:
                next_url = next_link
            response = self._make_request_with_retry(next_url)
            if not response or "data" not in response:
                break
            data = response["data"]
            all_rows.extend(data.get("rows", []))

            # Safety limit
            if len(all_rows) >= self.max_rows:
                logger.warning(
                    "Row limit (%d) reached for %s, data may be truncated",
                    self.max_rows,
                    dataset_id,
                )
                break

        if not all_rows:
            return None

        return pd.DataFrame(all_rows)

    def _fetch_via_download(self, dataset_id: str) -> bytes:
        """
        Fetch dataset via initiate-download/poll-download API.

        Args:
            dataset_id: Dataset ID

        Returns:
            Raw bytes of downloaded file
        """
        # Step 1: Initiate download
        initiate_url = f"{self.API_BASE_OPEN}/datasets/{dataset_id}/initiate-download"
        init_response = self._make_request_with_retry(initiate_url)

        if not init_response:
            raise ValueError(f"Failed to initiate download for {dataset_id}")

        # Check if URL is immediately available
        if "data" in init_response and init_response["data"].get("url"):
            download_url = init_response["data"]["url"]
        else:
            # Step 2: Poll for download URL
            poll_url = f"{self.API_BASE_OPEN}/datasets/{dataset_id}/poll-download"
            download_url = None

            for attempt in range(10):
                time.sleep(2)
                poll_response = self._make_request_with_retry(poll_url)

                if poll_response and "data" in poll_response:
                    status = poll_response["data"].get("status", "")
                    if status == "COMPLETED" or poll_response["data"].get("url"):
                        download_url = poll_response["data"].get("url")
                        break
                    elif status == "FAILED":
                        raise ValueError(f"Download preparation failed for {dataset_id}")

            if not download_url:
                raise ValueError(f"Download URL not available after polling for {dataset_id}")

        # Step 3: Download the file
        logger.info("Downloading dataset %s from %s", dataset_id, download_url)
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        return response.content

    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse raw bytes into DataFrame.

        Args:
            raw_bytes: Raw data bytes
            format_hint: Format hint ('csv', 'json', 'geojson')

        Returns:
            Parsed DataFrame
        """
        try:
            if format_hint and format_hint.lower() == "json":
                return pd.read_json(io.BytesIO(raw_bytes))
            elif format_hint and format_hint.lower() == "geojson":
                import json

                geojson = json.loads(raw_bytes)
                features = geojson.get("features", [])
                rows = [f.get("properties", {}) for f in features]
                return pd.DataFrame(rows)
            else:
                # Default to CSV
                return pd.read_csv(io.BytesIO(raw_bytes))
        except Exception as e:
            raise ValueError(f"Failed to parse data: {e}")

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
                "count": int(duplicate_count),
            })

        # Check for missing values
        total_cells = df.shape[0] * df.shape[1]
        missing_cells = df.isna().sum().sum()
        missing_percentage = (missing_cells / total_cells * 100) if total_cells > 0 else 0

        if missing_percentage > 50:
            issues.append({
                "type": "high_missing_values",
                "message": f"Missing values exceed 50% ({missing_percentage:.2f}%)",
                "percentage": missing_percentage,
            })
        elif missing_percentage > 10:
            warnings.append({
                "type": "moderate_missing_values",
                "message": f"Missing values: {missing_percentage:.2f}%",
                "percentage": missing_percentage,
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
            time_series_gaps=None,
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
                except Exception:
                    pass

        # 3. Parse dates
        date_columns = [
            col
            for col in cleaned_df.columns
            if any(
                keyword in col.lower()
                for keyword in ["date", "time", "year", "month", "quarter"]
            )
        ]

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
            except Exception:
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
        self,
        url: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Make HTTP request with exponential backoff retry.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            JSON response or None
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=self.request_timeout)

                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2**attempt)
                        logger.warning(
                            "Request to %s returned %d, retrying in %.1fs...",
                            url,
                            response.status_code,
                            delay,
                        )
                        time.sleep(delay)
                        continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning("Request timeout, retrying in %.1fs...", delay)
                    time.sleep(delay)
                    continue
                raise

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning("Request failed: %s, retrying in %.1fs...", e, delay)
                    time.sleep(delay)
                    continue
                raise

        return None

    def get_provenance_info(self, dataset_ref: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate provenance information for Data.gov.sg dataset.

        Args:
            dataset_ref: Dataset ID
            df: The DataFrame

        Returns:
            Provenance metadata
        """
        return {
            "source_name": "Data.gov.sg",
            "source_uri": f"https://data.gov.sg/datasets/{dataset_ref}/view",
            "api_endpoint": self.API_BASE_V2,
            "retrieved_at": datetime.utcnow(),
            "retrieval_method": "api_v2",
            "row_count": len(df),
            "column_count": len(df.columns),
            "data_owner": "Government of Singapore",
            "license_info": "Singapore Open Data License",
            "dataset_id": dataset_ref,
        }
