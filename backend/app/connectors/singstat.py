"""
DOS SingStat connector implementation using Table Builder Developer API.
Enables on-demand discovery and retrieval of statistical tables.
"""

import hashlib
import io
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from app.connectors.base import (
    BaseConnector,
    CleaningResult,
    DatasetCandidate,
    QualityReport,
)

logger = logging.getLogger(__name__)


class SingStatConnector(BaseConnector):
    """
    Connector for Department of Statistics Singapore (SingStat) Table Builder API.

    Features:
    - Keyword-based discovery via Table Builder search API
    - On-demand retrieval via Table Builder Data API
    - JSON preferred with CSV fallback
    - Tidy format normalization
    - Idempotency via (resource_id, payload_checksum)
    """

    BASE_URL = "https://tablebuilder.singstat.gov.sg/api/table"
    SEARCH_URL = f"{BASE_URL}/resourceid"
    DATA_URL = f"{BASE_URL}/tabledata"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; IMDA-Policy-Analytics/1.0)",
        "Accept": "application/json, text/csv;q=0.9, */*;q=0.8",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SingStat connector.

        Args:
            config: Optional configuration with keys:
                - max_retries: Number of retry attempts (default: 3)
                - retry_delay: Base delay between retries in seconds (default: 1)
                - max_results: Maximum discovery results to return (default: 20)
                - prefer_time_series: Prefer TS tables in discovery (default: True)
        """
        super().__init__(config)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 1)
        self.max_results = self.config.get("max_results", 20)
        self.prefer_time_series = self.config.get("prefer_time_series", True)
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Discover SingStat tables by keyword search.

        Uses the Table Builder search API to locate tables matching the intent.
        Search scope includes table title, variable names, and descriptions.

        The SingStat API works best with single keywords, so multi-word queries
        are split into individual keywords and searched separately.

        Args:
            intent: Search query or keywords

        Returns:
            List of dataset candidates matching the intent
        """
        try:
            # Extract individual keywords from the intent
            keywords = self.extract_keywords(intent)

            if not keywords:
                logger.warning("No valid keywords extracted from intent: %s", intent)
                return []

            # Search with each keyword and combine results
            all_candidates: Dict[str, DatasetCandidate] = {}

            for keyword in keywords:
                candidates = self._search_tables(keyword)
                for candidate in candidates:
                    # Use URI as unique key to deduplicate
                    if candidate.uri not in all_candidates:
                        all_candidates[candidate.uri] = candidate

            candidates_list = list(all_candidates.values())

            if self.prefer_time_series:
                candidates_list = self._prioritize_time_series(candidates_list)

            from app.core.config import settings
            max_results = settings.discovery_max_candidates
            return candidates_list[:max_results]

        except Exception as e:
            logger.error("Discovery failed for intent '%s': %s", intent, e)
            return []

    def _search_tables(self, keyword: str) -> List[DatasetCandidate]:
        """
        Search for tables using the Table Builder API.

        Args:
            keyword: Search keyword

        Returns:
            List of DatasetCandidate objects
        """
        candidates = []

        try:
            params = {"keyword": keyword}
            response = self._make_request(self.SEARCH_URL, params=params)

            if response is None:
                return candidates

            data = response.json()

            records = data.get("Data", {}).get("records", [])
            if not records:
                records = data.get("records", [])

            for record in records:
                resource_id = record.get("id") or record.get("resourceId")
                if not resource_id:
                    continue

                title = record.get("title", "")
                description = record.get("description", "")
                variables = record.get("variables", [])

                if isinstance(variables, list):
                    var_text = ", ".join(str(v) for v in variables[:5])
                else:
                    var_text = str(variables) if variables else ""

                full_description = description
                if var_text:
                    full_description = f"{description} Variables: {var_text}"

                data_type = record.get("type", "").upper()
                is_time_series = data_type == "TS" or "time" in title.lower()

                candidate = DatasetCandidate(
                    name=title or f"Table {resource_id}",
                    description=full_description.strip() or "SingStat statistical table",
                    source_type="singstat",
                    format="json",
                    uri=resource_id,
                    metadata={
                        "resource_id": resource_id,
                        "agency": "Department of Statistics Singapore",
                        "data_type": data_type,
                        "is_time_series": is_time_series,
                        "variables": variables if isinstance(variables, list) else [],
                        "frequency": record.get("frequency", ""),
                        "generated_on": record.get("generatedOn", ""),
                    },
                )
                candidates.append(candidate)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse search response: %s", e)
        except Exception as e:
            logger.error("Search failed for keyword '%s': %s", keyword, e)

        return candidates

    def _prioritize_time_series(
        self, candidates: List[DatasetCandidate]
    ) -> List[DatasetCandidate]:
        """
        Sort candidates to prioritize time series tables.

        Args:
            candidates: List of candidates to sort

        Returns:
            Sorted list with time series tables first
        """
        ts_candidates = []
        other_candidates = []

        for c in candidates:
            if c.metadata.get("is_time_series"):
                ts_candidates.append(c)
            else:
                other_candidates.append(c)

        return ts_candidates + other_candidates

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch table data from SingStat Table Builder API.

        Prefers JSON format with CSV fallback.

        Args:
            dataset_ref: Resource ID or full URL

        Returns:
            Raw bytes of the table data
        """
        resource_id = self._extract_resource_id(dataset_ref)
        url = f"{self.DATA_URL}/{resource_id}"

        formats_to_try = [("json", "application/json"), ("csv", "text/csv")]

        last_error: Optional[Exception] = None

        for fmt, accept in formats_to_try:
            try:
                headers = {"Accept": accept}
                response = self._make_request(url, headers=headers)

                if response is not None:
                    return response.content

            except Exception as e:
                last_error = e
                logger.warning(
                    "Fetch failed for %s (format=%s): %s", resource_id, fmt, e
                )

        error_msg = f"Failed to fetch table {resource_id}"
        if last_error:
            error_msg = f"{error_msg}: {last_error}"

        raise ValueError(error_msg)

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers

        Returns:
            Response object or None on failure
        """
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url, params=params, headers=request_headers, timeout=30
                )
                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else None

                if status == 429:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning("Rate limited, waiting %ss...", delay)
                    time.sleep(delay)
                    continue

                if status and 400 <= status < 500:
                    logger.warning("Client error %s for %s", status, url)
                    return None

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning("Request failed, retrying in %ss...", delay)
                    time.sleep(delay)
                else:
                    raise

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning("Request error, retrying in %ss: %s", delay, e)
                    time.sleep(delay)
                else:
                    raise

        return None

    def _extract_resource_id(self, dataset_ref: str) -> str:
        """
        Extract resource ID from various reference formats.

        Args:
            dataset_ref: Resource ID, URL, or table reference

        Returns:
            Normalized resource ID
        """
        if dataset_ref.startswith("http"):
            match = re.search(r"/tabledata/([A-Z0-9]+)", dataset_ref, re.IGNORECASE)
            if match:
                return match.group(1)
            match = re.search(r"resourceId=([A-Z0-9]+)", dataset_ref, re.IGNORECASE)
            if match:
                return match.group(1)

        return dataset_ref.strip()

    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse raw bytes into tidy format DataFrame.

        Normalizes data into one observation per row with:
        - period: Time dimension
        - value: Numeric measure
        - Additional dimension columns

        Args:
            raw_bytes: Raw table data bytes
            format_hint: Format hint ('json' or 'csv')

        Returns:
            Parsed DataFrame in tidy format
        """
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")

        if format_hint == "csv" or (
            format_hint is None and not content.strip().startswith(("{", "["))
        ):
            return self._parse_csv(content)

        return self._parse_json(content)

    def _parse_json(self, content: str) -> pd.DataFrame:
        """
        Parse JSON response into tidy DataFrame.

        Args:
            content: JSON string

        Returns:
            Tidy DataFrame
        """
        data = json.loads(content)

        records_data = data.get("Data", {})
        if isinstance(records_data, dict):
            rows = records_data.get("row", [])
            if not rows:
                rows = records_data.get("rows", [])
        else:
            rows = data.get("row", []) or data.get("rows", [])

        if not rows:
            if "records" in data:
                rows = data["records"]
            elif "Data" in data and isinstance(data["Data"], list):
                rows = data["Data"]

        if not rows:
            raise ValueError("No data rows found in JSON response")

        tidy_rows = []

        for row in rows:
            if isinstance(row, dict):
                row_key = row.get("rowKey", row.get("key", ""))
                columns = row.get("columns", [])

                for col in columns:
                    if isinstance(col, dict):
                        tidy_row = self._extract_tidy_row(row_key, col)
                        if tidy_row:
                            tidy_rows.append(tidy_row)
                    else:
                        tidy_rows.append({"row_key": row_key, "value": col})

                if not columns:
                    value = row.get("value") or row.get("Value")
                    period = row.get("period") or row.get("year") or row.get("date")
                    if value is not None:
                        tidy_rows.append(
                            {
                                "period": period,
                                "value": value,
                                **{
                                    k: v
                                    for k, v in row.items()
                                    if k not in ("value", "Value", "period", "year", "date")
                                },
                            }
                        )
            elif isinstance(row, list):
                if len(row) >= 2:
                    tidy_rows.append({"period": row[0], "value": row[1]})

        if not tidy_rows:
            raise ValueError("Could not extract any data rows from JSON")

        return pd.DataFrame(tidy_rows)

    def _extract_tidy_row(
        self, row_key: str, col_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a single tidy row from column data.

        Args:
            row_key: Row identifier (often contains dimension info)
            col_data: Column data dictionary

        Returns:
            Tidy row dictionary or None
        """
        value = col_data.get("value") or col_data.get("Value")
        if value is None:
            return None

        period = col_data.get("key") or col_data.get("period") or col_data.get("year")

        row = {"period": period, "value": value}

        if row_key:
            row["dimension"] = row_key

        for key in ["unit", "footnote", "status", "uom"]:
            if key in col_data:
                row[key] = col_data[key]

        return row

    def _parse_csv(self, content: str) -> pd.DataFrame:
        """
        Parse CSV content into tidy DataFrame.

        Handles multi-row headers and footnotes common in SingStat CSV files.

        Args:
            content: CSV string

        Returns:
            Tidy DataFrame
        """
        df = pd.read_csv(io.StringIO(content))

        df = self._handle_multirow_headers(df)

        df = self._normalize_to_tidy(df)

        return df

    def _handle_multirow_headers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle multi-row headers in SingStat files.

        Args:
            df: DataFrame with potential multi-row headers

        Returns:
            DataFrame with normalized headers
        """
        if len(df) < 3:
            return df

        first_row_na_ratio = df.iloc[0].isna().sum() / len(df.columns)

        if first_row_na_ratio > 0.3:
            try:
                new_columns = []
                for i, col in enumerate(df.columns):
                    val1 = "" if pd.isna(df.iloc[0, i]) else str(df.iloc[0, i])
                    val2 = "" if pd.isna(df.iloc[1, i]) else str(df.iloc[1, i])

                    if val1 and val2:
                        new_columns.append(f"{val1}_{val2}")
                    elif val1:
                        new_columns.append(val1)
                    elif val2:
                        new_columns.append(val2)
                    else:
                        new_columns.append(str(col))

                df = df.iloc[2:].copy()
                df.columns = new_columns
                df = df.reset_index(drop=True)
            except Exception as e:
                logger.warning("Failed to normalize multi-row headers: %s", e)

        return df

    def _normalize_to_tidy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame to tidy format if needed.

        Args:
            df: DataFrame to normalize

        Returns:
            Tidy DataFrame
        """
        if "period" in df.columns and "value" in df.columns:
            return df

        time_cols = self._identify_time_columns(df)
        value_cols = self._identify_value_columns(df)

        if not time_cols and not value_cols:
            return df

        if len(time_cols) == 1 and len(value_cols) >= 1:
            return df

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_cols) > 2:
            id_cols = [c for c in df.columns if c not in numeric_cols]
            if id_cols:
                try:
                    melted = pd.melt(
                        df,
                        id_vars=id_cols,
                        value_vars=numeric_cols,
                        var_name="period",
                        value_name="value",
                    )
                    return melted
                except Exception as e:
                    logger.warning("Failed to melt DataFrame: %s", e)

        return df

    def _identify_time_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Identify columns that represent time/period.

        Args:
            df: DataFrame to analyze

        Returns:
            List of time column names
        """
        time_keywords = ["year", "quarter", "month", "date", "period", "time"]
        time_cols = []

        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in time_keywords):
                time_cols.append(col)

        return time_cols

    def _identify_value_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Identify columns that represent numeric values.

        Args:
            df: DataFrame to analyze

        Returns:
            List of value column names
        """
        value_keywords = ["value", "amount", "count", "total", "rate", "number"]
        value_cols = []

        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in value_keywords):
                value_cols.append(col)

        return value_cols

    def validate(self, df: pd.DataFrame) -> QualityReport:
        """
        Validate SingStat dataset against quality rules.

        Validation checks:
        - Non-empty dataset
        - Presence of numeric measure column
        - Parseable time/period column
        - Missing value percentage
        - Duplicate row detection
        - Time-series continuity

        Args:
            df: DataFrame to validate

        Returns:
            Quality report with validation results
        """
        issues = []
        warnings = []

        if df.empty:
            issues.append({"type": "empty_dataset", "message": "Dataset is empty"})
            return QualityReport(
                status="failed",
                issues=issues,
                warnings=warnings,
                completeness_score=0.0,
                missing_value_percentage=100.0,
                duplicate_row_count=0,
                time_series_gaps=None,
                full_report={"total_rows": 0, "total_columns": 0},
            )

        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) == 0:
            potential_numeric = self._find_coercible_numeric_columns(df)
            if not potential_numeric:
                issues.append(
                    {
                        "type": "no_numeric_column",
                        "message": "No numeric measure column found",
                    }
                )

        time_cols = self._identify_time_columns(df)
        if not time_cols:
            warnings.append(
                {
                    "type": "no_time_column",
                    "message": "No parseable time/period column found",
                }
            )

        total_cells = df.shape[0] * df.shape[1]
        missing_cells = df.isna().sum().sum()
        missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 0

        if missing_pct > 50:
            issues.append(
                {
                    "type": "high_missing_values",
                    "message": f"Missing values exceed 50% ({missing_pct:.2f}%)",
                    "percentage": missing_pct,
                }
            )
        elif missing_pct > 10:
            warnings.append(
                {
                    "type": "moderate_missing_values",
                    "message": f"Missing values: {missing_pct:.2f}%",
                    "percentage": missing_pct,
                }
            )

        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            warnings.append(
                {
                    "type": "duplicate_rows",
                    "message": f"Found {duplicate_count} duplicate rows",
                    "count": int(duplicate_count),
                }
            )

        time_series_gaps = self._detect_time_gaps(df)
        if time_series_gaps:
            warnings.append(
                {
                    "type": "time_series_gaps",
                    "message": "Gaps detected in time series",
                    "gaps": time_series_gaps,
                }
            )

        completeness_score = 1.0 - (missing_pct / 100)

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
            missing_value_percentage=missing_pct,
            duplicate_row_count=int(duplicate_count),
            time_series_gaps=time_series_gaps,
            full_report={
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "numeric_columns": list(numeric_cols),
                "time_columns": time_cols,
            },
        )

    def _find_coercible_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Find columns that can be coerced to numeric.

        Args:
            df: DataFrame to analyze

        Returns:
            List of column names that can be numeric
        """
        coercible = []
        for col in df.columns:
            if df[col].dtype == "object":
                try:
                    cleaned = df[col].astype(str).str.replace(",", "").str.strip()
                    numeric = pd.to_numeric(cleaned, errors="coerce")
                    if numeric.notna().sum() > len(df) * 0.5:
                        coercible.append(col)
                except Exception:
                    pass
        return coercible

    def _detect_time_gaps(self, df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
        """
        Detect gaps in time series data.

        Args:
            df: DataFrame to analyze

        Returns:
            List of detected gaps or None
        """
        time_cols = self._identify_time_columns(df)
        if not time_cols:
            return None

        gaps = []
        for col in time_cols:
            try:
                dates = pd.to_datetime(df[col], errors="coerce")
                dates = dates.dropna().sort_values()

                if len(dates) > 1:
                    diffs = dates.diff()[1:]
                    median_diff = diffs.median()

                    if pd.notna(median_diff):
                        large_gaps = diffs[diffs > median_diff * 2]
                        if len(large_gaps) > 0:
                            gaps.append(
                                {
                                    "column": col,
                                    "gap_count": len(large_gaps),
                                    "median_interval": str(median_diff),
                                }
                            )
            except Exception:
                pass

        return gaps if gaps else None

    def clean(self, df: pd.DataFrame) -> CleaningResult:
        """
        Clean and normalize SingStat dataset.

        Cleaning operations:
        - Normalize column names to snake_case
        - Coerce numeric values
        - Standardize period representations
        - Trim whitespace and normalize categoricals
        - Drop fully empty rows/columns

        All operations are logged for auditability.

        Args:
            df: DataFrame to clean

        Returns:
            CleaningResult with cleaned DataFrame and logs
        """
        cleaning_logs = []
        cleaned_df = df.copy()

        original_columns = list(cleaned_df.columns)
        cleaned_df = self.normalize_column_names(cleaned_df)
        new_columns = list(cleaned_df.columns)

        if original_columns != new_columns:
            cleaning_logs.append(
                {
                    "operation": "normalize_columns",
                    "description": "Normalized column names to snake_case",
                    "columns_affected": original_columns,
                    "mapping": dict(zip(original_columns, new_columns)),
                }
            )

        time_renames = self._standardize_time_columns(cleaned_df)
        if time_renames:
            cleaning_logs.append(
                {
                    "operation": "standardize_time_columns",
                    "description": "Standardized time column names",
                    "mapping": time_renames,
                }
            )

        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                original_values = cleaned_df[col].copy()

                cleaned_col = (
                    cleaned_df[col]
                    .astype(str)
                    .str.replace(",", "", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.strip()
                )

                numeric_col = pd.to_numeric(cleaned_col, errors="coerce")
                non_null_numeric = numeric_col.notna().sum()
                non_null_original = cleaned_df[col].notna().sum()

                if non_null_numeric > 0 and non_null_numeric >= non_null_original * 0.5:
                    cleaned_df[col] = numeric_col
                    cleaning_logs.append(
                        {
                            "operation": "coerce_numeric",
                            "description": f"Converted '{col}' to numeric",
                            "column": col,
                            "values_converted": int(non_null_numeric),
                        }
                    )

        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                original_values = cleaned_df[col].copy()
                cleaned_df[col] = cleaned_df[col].astype(str).str.strip()

                if not original_values.equals(cleaned_df[col]):
                    cleaning_logs.append(
                        {
                            "operation": "trim_whitespace",
                            "description": f"Trimmed whitespace in '{col}'",
                            "column": col,
                        }
                    )

        for col in cleaned_df.columns:
            if any(kw in col for kw in ["period", "year", "quarter", "month"]):
                standardized = self._standardize_period_values(cleaned_df[col])
                if standardized is not None:
                    cleaned_df[col] = standardized
                    cleaning_logs.append(
                        {
                            "operation": "standardize_period",
                            "description": f"Standardized period values in '{col}'",
                            "column": col,
                        }
                    )

        initial_rows = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(how="all")
        rows_removed = initial_rows - len(cleaned_df)

        if rows_removed > 0:
            cleaning_logs.append(
                {
                    "operation": "remove_empty_rows",
                    "description": f"Removed {rows_removed} empty rows",
                    "rows_removed": rows_removed,
                }
            )

        empty_cols = [col for col in cleaned_df.columns if cleaned_df[col].isna().all()]
        if empty_cols:
            cleaned_df = cleaned_df.drop(columns=empty_cols)
            cleaning_logs.append(
                {
                    "operation": "remove_empty_columns",
                    "description": f"Removed {len(empty_cols)} empty columns",
                    "columns_removed": empty_cols,
                }
            )

        return CleaningResult(cleaned_df=cleaned_df, cleaning_logs=cleaning_logs)

    def _standardize_time_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Standardize time column names.

        Args:
            df: DataFrame to modify in place

        Returns:
            Dictionary of {old_name: new_name} mappings
        """
        renames = {}
        time_mappings = {
            "period": ["period", "time_period", "ref_period"],
            "year": ["year", "yr", "yyyy", "annual"],
            "quarter": ["quarter", "qtr", "q"],
            "month": ["month", "mon", "mm", "mth"],
        }

        for col in list(df.columns):
            col_lower = col.lower()
            for standard_name, keywords in time_mappings.items():
                if any(kw == col_lower or col_lower.endswith(f"_{kw}") for kw in keywords):
                    if col != standard_name and standard_name not in df.columns:
                        df.rename(columns={col: standard_name}, inplace=True)
                        renames[col] = standard_name
                    break

        return renames

    def _standardize_period_values(self, series: pd.Series) -> Optional[pd.Series]:
        """
        Standardize period value formats.

        Handles Year, Quarter (YYYY-Q#), Month (YYYY-MM) formats.

        Args:
            series: Series with period values

        Returns:
            Standardized series or None if no changes needed
        """
        try:
            sample = series.dropna().head(10).astype(str)
            if len(sample) == 0:
                return None

            quarter_pattern = re.compile(r"(\d{4})\s*[Qq](\d)")
            month_pattern = re.compile(r"(\d{4})\s*[Mm](\d{1,2})")

            standardized = series.astype(str)
            changed = False

            if sample.str.match(quarter_pattern).any():
                standardized = standardized.str.replace(
                    quarter_pattern, r"\1-Q\2", regex=True
                )
                changed = True

            if sample.str.match(month_pattern).any():
                standardized = standardized.apply(
                    lambda x: month_pattern.sub(
                        lambda m: f"{m.group(1)}-{int(m.group(2)):02d}", str(x)
                    )
                )
                changed = True

            return standardized if changed else None

        except Exception:
            return None

    def get_provenance_info(self, dataset_ref: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate complete provenance information for SingStat dataset.

        Args:
            dataset_ref: Dataset reference (resource ID or URL)
            df: The DataFrame

        Returns:
            Provenance metadata dictionary
        """
        resource_id = self._extract_resource_id(dataset_ref)

        return {
            "source": "singstat",
            "source_name": "Department of Statistics Singapore (SingStat)",
            "resource_id": resource_id,
            "source_uri": f"{self.DATA_URL}/{resource_id}",
            "retrieved_at": datetime.utcnow().isoformat(),
            "retrieval_method": "Table Builder Developer API",
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "data_owner": "Singapore Department of Statistics",
            "license_info": "Singapore Open Data License",
            "api_version": "v1",
        }

    def compute_checksum(self, raw_bytes: bytes) -> str:
        """
        Compute checksum for raw payload.

        Used for idempotency checks.

        Args:
            raw_bytes: Raw data bytes

        Returns:
            SHA-256 checksum string
        """
        return hashlib.sha256(raw_bytes).hexdigest()

    def get_idempotency_key(self, resource_id: str, raw_bytes: bytes) -> Tuple[str, str]:
        """
        Generate idempotency key for dataset.

        Args:
            resource_id: SingStat resource ID
            raw_bytes: Raw data bytes

        Returns:
            Tuple of (resource_id, checksum)
        """
        checksum = self.compute_checksum(raw_bytes)
        return (resource_id, checksum)

    def get_schema_snapshot(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate detailed schema snapshot.

        Args:
            df: DataFrame to analyze

        Returns:
            Schema information dictionary
        """
        schema = {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "nullable": {col: bool(df[col].isna().any()) for col in df.columns},
            "unique_counts": {col: int(df[col].nunique()) for col in df.columns},
            "sample_values": {},
        }

        for col in df.columns:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                schema["sample_values"][col] = [
                    str(v) for v in non_null.head(3).tolist()
                ]

        return schema

    def estimate_rows(self, dataset_ref: str) -> int:
        """
        Estimate row count for a SingStat dataset.

        Attempts to get row count from tableinfo API if available.

        Args:
            dataset_ref: Resource ID or URL

        Returns:
            Estimated row count (uses default if unavailable)
        """
        from app.core.config import settings

        try:
            resource_id = self._extract_resource_id(dataset_ref)

            # Try tableinfo endpoint for metadata
            tableinfo_url = f"{self.BASE_URL}/tableinfo/{resource_id}"
            response = self._make_request(tableinfo_url)

            if response is not None:
                data = response.json()
                # Check for TotalRecords in response
                total_records = data.get("Data", {}).get("TotalRecords")
                if total_records is not None:
                    return int(total_records)

                # Check for rowCount or similar fields
                row_count = data.get("Data", {}).get("rowCount")
                if row_count is not None:
                    return int(row_count)

                # Try to estimate from variable combinations
                variables = data.get("Data", {}).get("variables", [])
                if variables:
                    # Rough estimate: product of unique values per variable
                    # This is a heuristic and may not be accurate
                    estimated = 1
                    for var in variables[:3]:  # Limit to first 3 variables
                        levels = var.get("levels", [])
                        if levels:
                            estimated *= len(levels)
                    if estimated > 1:
                        return min(estimated, 10000)  # Cap at 10000

        except Exception as e:
            logger.warning(f"Row estimation failed for {dataset_ref}: {e}")

        return settings.row_estimate_default
