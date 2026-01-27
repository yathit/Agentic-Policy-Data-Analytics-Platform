"""
DOS SingStat connector implementation.
Handles CSV and Excel downloads with multi-row header normalization.
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


class SingStatConnector(BaseConnector):
    """
    Connector for Department of Statistics Singapore (SingStat).

    Features:
    - CSV and Excel file downloads
    - Multi-row header normalization
    - Time-series column canonicalization
    - Metadata preservation
    """

    BASE_URL = "https://tablebuilder.singstat.gov.sg"

    # Common SingStat datasets (can be expanded)
    KNOWN_DATASETS = {
        "labour_force": {
            "name": "Labour Force Statistics",
            "url": "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M182011",
            "format": "csv",
            "description": "Labour force participation rates and employment statistics",
        },
        "employment_by_industry": {
            "name": "Employment by Industry",
            "url": "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M182021",
            "format": "csv",
            "description": "Employment levels across different industries",
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_retries = config.get("max_retries", 3) if config else 3
        self.retry_delay = config.get("retry_delay", 1) if config else 1

    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Discover SingStat datasets based on intent.

        Note: SingStat doesn't have a public search API, so we match against
        a curated list of known datasets.

        Args:
            intent: Search query or keywords

        Returns:
            List of dataset candidates
        """
        candidates = []
        intent_lower = intent.lower()

        for key, info in self.KNOWN_DATASETS.items():
            # Simple keyword matching
            if any(
                keyword in intent_lower
                for keyword in [key, info["name"].lower()]
                + info["description"].lower().split()
            ):
                candidate = DatasetCandidate(
                    name=info["name"],
                    description=info["description"],
                    source_type="singstat",
                    format=info["format"],
                    uri=info["url"],
                    metadata={
                        "dataset_key": key,
                        "agency": "Department of Statistics Singapore",
                    },
                )
                candidates.append(candidate)

        return candidates

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch dataset from SingStat.

        Args:
            dataset_ref: URL to the dataset file

        Returns:
            Raw bytes of the dataset
        """
        try:
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(dataset_ref, timeout=30)
                    response.raise_for_status()
                    return response.content

                except requests.exceptions.RequestException as e:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        print(f"Download failed, retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise

        except Exception as e:
            raise ValueError(f"Failed to fetch dataset from SingStat: {e}")

    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse raw bytes into DataFrame.

        Handles both CSV and Excel formats with multi-row header normalization.

        Args:
            raw_bytes: Raw dataset bytes
            format_hint: Format hint ('csv', 'excel', 'xls', 'xlsx')

        Returns:
            Parsed DataFrame
        """
        try:
            if format_hint in ["excel", "xls", "xlsx"]:
                # Parse Excel file
                df = pd.read_excel(io.BytesIO(raw_bytes), engine="openpyxl")
            else:
                # Default to CSV
                df = pd.read_csv(io.BytesIO(raw_bytes))

            # Normalize multi-row headers if present
            df = self._normalize_headers(df)

            return df

        except Exception as e:
            raise ValueError(f"Failed to parse SingStat dataset: {e}")

    def validate(self, df: pd.DataFrame) -> QualityReport:
        """
        Validate SingStat dataset quality.

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

        # Check for time series continuity (if applicable)
        time_series_gaps = self._detect_time_gaps(df)

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
            time_series_gaps=time_series_gaps,
            full_report={
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            },
        )

    def clean(self, df: pd.DataFrame) -> CleaningResult:
        """
        Clean and normalize SingStat dataset.

        Special handling for:
        - Multi-row headers
        - Time columns (Year, Quarter, Month)
        - Numeric formatting

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

        # 2. Canonicalize time columns
        time_cols_renamed = self._canonicalize_time_columns(cleaned_df)
        if time_cols_renamed:
            cleaning_logs.append({
                "operation": "canonicalize_time_columns",
                "description": "Standardized time column names",
                "parameters": {"mappings": time_cols_renamed},
                "columns_affected": list(time_cols_renamed.keys()),
            })

        # 3. Convert numeric strings to numbers
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                try:
                    # Remove common formatting (commas, spaces)
                    cleaned_col = cleaned_df[col].astype(str).str.replace(",", "").str.replace(" ", "")
                    numeric_col = pd.to_numeric(cleaned_col, errors="coerce")

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

        # 4. Parse date columns
        for col in cleaned_df.columns:
            if any(keyword in col.lower() for keyword in ["date", "period"]):
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

        # 5. Remove completely empty rows and columns
        initial_rows = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(how="all")
        rows_removed = initial_rows - len(cleaned_df)

        if rows_removed > 0:
            cleaning_logs.append({
                "operation": "remove_empty_rows",
                "description": f"Removed {rows_removed} completely empty rows",
                "parameters": {},
                "rows_affected": rows_removed,
            })

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

    def _normalize_headers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize multi-row headers commonly found in SingStat files.

        Args:
            df: DataFrame with potential multi-row headers

        Returns:
            DataFrame with normalized single-row headers
        """
        # Check if first few rows might be headers
        # (common pattern: first row has category, second row has subcategory)
        if len(df) > 2:
            # If first row has many NaN values, it might be a multi-row header
            first_row_na_count = df.iloc[0].isna().sum()
            if first_row_na_count > len(df.columns) * 0.3:
                # Attempt to combine first two rows as headers
                try:
                    new_columns = []
                    for i, col in enumerate(df.columns):
                        val1 = str(df.iloc[0, i]) if not pd.isna(df.iloc[0, i]) else ""
                        val2 = str(df.iloc[1, i]) if not pd.isna(df.iloc[1, i]) else ""
                        if val1 and val2:
                            new_columns.append(f"{val1}_{val2}")
                        elif val1:
                            new_columns.append(val1)
                        elif val2:
                            new_columns.append(val2)
                        else:
                            new_columns.append(col)

                    df = df.iloc[2:].copy()
                    df.columns = new_columns
                    df = df.reset_index(drop=True)
                except:
                    pass

        return df

    def _canonicalize_time_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Standardize time column names (Year, Quarter, Month).

        Args:
            df: DataFrame to process

        Returns:
            Dictionary of {old_name: new_name} mappings
        """
        renames = {}
        time_keywords = {
            "year": ["year", "yr", "yyyy"],
            "quarter": ["quarter", "qtr", "q"],
            "month": ["month", "mon", "mm"],
            "date": ["date", "period"],
        }

        for col in df.columns:
            col_lower = col.lower()
            for standard_name, keywords in time_keywords.items():
                if any(keyword in col_lower for keyword in keywords):
                    if col != standard_name:
                        renames[col] = standard_name
                        df.rename(columns={col: standard_name}, inplace=True)
                    break

        return renames

    def _detect_time_gaps(self, df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
        """
        Detect gaps in time series data.

        Args:
            df: DataFrame to analyze

        Returns:
            List of detected gaps or None
        """
        # Look for date/time columns
        time_cols = [
            col for col in df.columns
            if any(keyword in col.lower() for keyword in ["date", "year", "quarter", "month", "period"])
        ]

        if not time_cols:
            return None

        gaps = []
        for col in time_cols:
            try:
                # Try to parse as datetime
                dates = pd.to_datetime(df[col], errors="coerce")
                dates = dates.dropna().sort_values()

                if len(dates) > 1:
                    # Check for gaps larger than expected frequency
                    diffs = dates.diff()[1:]
                    median_diff = diffs.median()

                    large_gaps = diffs[diffs > median_diff * 2]
                    if len(large_gaps) > 0:
                        gaps.append({
                            "column": col,
                            "gap_count": len(large_gaps),
                            "median_interval": str(median_diff),
                        })
            except:
                pass

        return gaps if gaps else None

    def get_provenance_info(self, dataset_ref: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate provenance information for SingStat dataset.

        Args:
            dataset_ref: Dataset URL
            df: The DataFrame

        Returns:
            Provenance metadata
        """
        return {
            "source_name": "Department of Statistics Singapore (SingStat)",
            "source_uri": dataset_ref,
            "retrieved_at": datetime.utcnow(),
            "retrieval_method": "download",
            "row_count": len(df),
            "column_count": len(df.columns),
            "data_owner": "Singapore Department of Statistics",
            "license_info": "Singapore Open Data License",
            "update_frequency": "varies",  # SingStat datasets have different update frequencies
        }
