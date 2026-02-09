"""
Data.gov.sg V2 API connector implementation.

Uses cached collections for discovery and V2 API for data fetching.
Uses list-rows API for paginated data access.
"""

import requests
import pandas as pd
import io
import time
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from datetime import datetime

from app.connectors.base import (
    BaseConnector,
    DatasetCandidate,
    QualityReport,
    CleaningResult,
)
from app.db.repo_data_gov_sg_collection import search_collections

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DataGovV2Connector(BaseConnector):
    """
    Connector for Data.gov.sg V2 API.

    Discovery uses cached collections from database (handled by DataService).
    Fetching uses V2 public API endpoints.

    Features:
    - list-rows API for paginated data access
    - Exponential backoff retry logic
    - Rate limiting compliance (5 req/min without API key)
    """

    # V2 API endpoints
    API_BASE_V2 = "https://api-production.data.gov.sg/v2/public/api"

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_retries = config.get("max_retries", 3) if config else 3
        self.base_delay = config.get("base_delay", 2.0) if config else 2.0
        self.request_timeout = config.get("request_timeout", 30) if config else 30
        self.max_rows = config.get("max_rows", 100000) if config else 100000
        # Keep integration/demo runs fast; override via config if needed.
        self.max_pages = config.get("max_pages", 2) if config else 2
        self.api_key = config.get("api_key") if config else None

    def discover(
        self,
        intent: str,
        db: Optional["Session"] = None,
        limit: Optional[int] = None,
    ) -> List[DatasetCandidate]:
        """
        Discover datasets from cached collections in the database.

        Queries the data_gov_sg_collection table for collections matching
        the user's intent, then returns individual dataset candidates
        from each collection's child_dataset_ids.

        The search works best with single keywords, so multi-word queries
        are split into individual keywords and searched separately.

        Args:
            intent: Search keyword (e.g., "employment statistics")
            db: SQLAlchemy database session (required for discovery)
            limit: Maximum number of datasets to return (uses config default if None)

        Returns:
            List of DatasetCandidate objects with uri = dataset_id
        """
        from app.core.config import settings

        if limit is None:
            limit = settings.discovery_max_candidates
        if db is None:
            logger.warning(
                "discover() called without db session; returning empty list"
            )
            return []

        # Extract individual keywords from the intent
        keywords = self.extract_keywords(intent)

        if not keywords:
            logger.warning("No valid keywords extracted from intent: %s", intent)
            return []

        # Search with each keyword and combine results
        all_collections: Dict[str, dict] = {}

        for keyword in keywords:
            try:
                collections = search_collections(db, keyword, limit=limit)
                for collection in collections:
                    coll_id = collection.get("collection_id")
                    if coll_id and coll_id not in all_collections:
                        all_collections[coll_id] = collection
            except Exception as e:
                logger.error("Error searching data.gov.sg collections for keyword '%s': %s", keyword, e)

        candidates: List[DatasetCandidate] = []
        seen_dataset_ids: set[str] = set()

        for collection in all_collections.values():
            child_ids = collection.get("child_dataset_ids") or []
            # Take up to 2 datasets per collection to avoid flooding results
            for dataset_id in child_ids[:2]:
                if dataset_id in seen_dataset_ids:
                    continue
                seen_dataset_ids.add(dataset_id)

                candidates.append(
                    DatasetCandidate(
                        name=collection.get("name") or dataset_id,
                        description=collection.get("description") or "",
                        source_type="data.gov.sg",
                        format="api",
                        uri=dataset_id,
                        metadata={
                            "collection_id": collection.get("collection_id"),
                            "collection_name": collection.get("name"),
                            "last_updated_at": (
                                collection.get("lastUpdatedAt").isoformat()
                                if collection.get("lastUpdatedAt")
                                else None
                            ),
                        },
                    )
                )

                if len(candidates) >= limit:
                    break
            if len(candidates) >= limit:
                break

        logger.info(
            "Discovered %d datasets for intent '%s' (keywords: %s)",
            len(candidates),
            intent,
            keywords,
        )
        return candidates

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch dataset data from V2 API.

        Uses list-rows API for paginated data access.

        Args:
            dataset_ref: Dataset ID (e.g., 'd_xxxxx')

        Returns:
            Raw bytes (CSV format)
        """
        dataset_id = dataset_ref

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
        page_count = 1
        while data.get("links", {}).get("next") and page_count < self.max_pages:
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
            page_count += 1

            # Safety limit
            if len(all_rows) >= self.max_rows:
                logger.warning(
                    "Row limit (%d) reached for %s, data may be truncated",
                    self.max_rows,
                    dataset_id,
                )
                break
        if data.get("links", {}).get("next") and page_count >= self.max_pages:
            logger.info(
                "Page limit (%d) reached for %s, data may be truncated",
                self.max_pages,
                dataset_id,
            )

        if not all_rows:
            return None

        return pd.DataFrame(all_rows)

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
                parsed_series, log_entry = self._parse_datetime_column(col, cleaned_df[col])
                if parsed_series is not None and log_entry is not None:
                    cleaned_df[col] = parsed_series
                    cleaning_logs.append(log_entry)
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

    def _parse_datetime_column(
        self,
        column_name: str,
        series: pd.Series,
    ) -> tuple[Optional[pd.Series], Optional[Dict[str, Any]]]:
        """
        Parse date/time-like columns with guards for year and numeric IDs.

        Returns:
            Tuple of (parsed_series, cleaning_log_entry). If no conversion is applied,
            returns (None, None).
        """
        non_null = series.dropna()
        if non_null.empty:
            return None, None

        # Keep numeric year columns as year values (e.g., 1996), not epoch timestamps.
        if "year" in column_name.lower():
            year_numeric = pd.to_numeric(series, errors="coerce")
            non_null_year = year_numeric.dropna()
            if not non_null_year.empty:
                year_like = non_null_year[(non_null_year >= 1900) & (non_null_year <= 2100)]
                if len(year_like) / len(non_null_year) >= 0.9:
                    return year_numeric.round().astype("Int64"), {
                        "operation": "normalize_year",
                        "description": f"Normalized column '{column_name}' as year values",
                        "parameters": {"column": column_name},
                        "columns_affected": [column_name],
                    }

        # Avoid converting numeric identifier columns to datetime nanoseconds.
        if pd.api.types.is_numeric_dtype(series):
            return None, None

        parsed_dates = pd.to_datetime(series, errors="coerce")
        parse_ratio = parsed_dates.notna().sum() / len(non_null)
        if parse_ratio < 0.8:
            return None, None

        return parsed_dates, {
            "operation": "parse_dates",
            "description": f"Parsed column '{column_name}' as datetime",
            "parameters": {"column": column_name, "parse_ratio": round(parse_ratio, 3)},
            "columns_affected": [column_name],
        }

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
                headers = {"X-API-KEY": self.api_key} if self.api_key else None
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.request_timeout,
                )

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

    def estimate_rows(self, dataset_ref: str) -> int:
        """
        Estimate row count using first-page metadata from list-rows API.

        The V2 API may return a 'total' field in the first page response.

        Args:
            dataset_ref: Dataset ID

        Returns:
            Estimated row count (uses default if unavailable)
        """
        from app.core.config import settings

        try:
            url = f"{self.API_BASE_V2}/datasets/{dataset_ref}/list-rows"
            response = self._make_request_with_retry(url)

            if response and "data" in response:
                data = response["data"]
                # Check for total field in response
                total = data.get("total")
                if total is not None:
                    return int(total)
                # Fall back to counting rows in first page
                rows = data.get("rows", [])
                if rows:
                    # If there's a next link, estimate based on page size
                    if data.get("links", {}).get("next"):
                        # Assume at least 2x the page size
                        return len(rows) * 2
                    return len(rows)
        except Exception as e:
            logger.warning(f"Row estimation failed for {dataset_ref}: {e}")

        return settings.row_estimate_default
