"""
Internal PostgreSQL connector for IMDA mock datasets.
Queries internal database tables with high trust and low latency.
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.connectors.base import (
    BaseConnector,
    DatasetCandidate,
    QualityReport,
    CleaningResult,
)
from app.core.database import SessionLocal


class InternalConnector(BaseConnector):
    """
    Connector for internal IMDA datasets stored in PostgreSQL.

    Features:
    - Direct database queries
    - High trust weight (internal data)
    - Low latency access
    - Structured schema
    """

    # Available internal tables
    INTERNAL_TABLES = {
        "digital_sector_employment": {
            "name": "Digital Sector Employment",
            "description": "Employment statistics across digital industry sectors by quarter",
            "key_columns": ["year", "quarter", "sector", "total_employees"],
        },
        "ai_workforce_programmes": {
            "name": "AI Workforce Development Programmes",
            "description": "Government-funded AI workforce training and certification programmes",
            "key_columns": ["programme_name", "programme_type", "target_participants", "funding_sgd"],
        },
        "online_safety_incidents_summary": {
            "name": "Online Safety Incidents Summary",
            "description": "Aggregated statistics on online safety incidents by category",
            "key_columns": ["reporting_period", "incident_category", "total_reports", "verified_incidents"],
        },
        "emerging_tech_adoption_index": {
            "name": "Emerging Technology Adoption Index",
            "description": "Technology adoption metrics across industry sectors",
            "key_columns": ["assessment_year", "industry_sector", "technology_category", "adoption_score"],
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.db: Optional[Session] = None

    def _get_db_session(self) -> Session:
        """Get or create database session."""
        if self.db is None:
            self.db = SessionLocal()
        return self.db

    def close(self):
        """Close database session."""
        if self.db:
            self.db.close()
            self.db = None

    def discover(self, intent: str) -> List[DatasetCandidate]:
        """
        Discover internal datasets based on intent.

        Args:
            intent: Search query or keywords

        Returns:
            List of dataset candidates
        """
        candidates = []
        intent_lower = intent.lower()

        for table_name, info in self.INTERNAL_TABLES.items():
            # Match against table name, display name, or description
            if any(
                keyword in intent_lower
                for keyword in [
                    table_name,
                    info["name"].lower(),
                ] + info["description"].lower().split()
            ):
                candidate = DatasetCandidate(
                    name=info["name"],
                    description=info["description"],
                    source_type="internal",
                    format="database",
                    uri=f"table:{table_name}",
                    metadata={
                        "table_name": table_name,
                        "key_columns": info["key_columns"],
                        "database": "PostgreSQL",
                        "trust_level": "high",
                    },
                )
                candidates.append(candidate)

        return candidates

    def fetch(self, dataset_ref: str) -> bytes:
        """
        Fetch is not used for database queries.
        Use fetch_dataframe() directly instead.

        Args:
            dataset_ref: Table reference (e.g., "table:digital_sector_employment")

        Returns:
            Empty bytes (not applicable for database)
        """
        # For database tables, we skip the bytes step and go directly to DataFrame
        return b""

    def parse(self, raw_bytes: bytes, format_hint: Optional[str] = None) -> pd.DataFrame:
        """
        Parse is not used for database queries.
        Use fetch_dataframe() directly instead.

        Args:
            raw_bytes: Not used
            format_hint: Not used

        Returns:
            Empty DataFrame
        """
        return pd.DataFrame()

    def fetch_dataframe(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch data directly as a DataFrame from internal tables.

        Args:
            table_name: Name of the table to query
            filters: Optional filters as {column: value} pairs
            limit: Optional row limit

        Returns:
            DataFrame with query results
        """
        db = self._get_db_session()

        # Build query
        query = f"SELECT * FROM {table_name}"

        # Add filters
        where_clauses = []
        params = {}
        if filters:
            for i, (col, val) in enumerate(filters.items()):
                param_name = f"param_{i}"
                where_clauses.append(f"{col} = %({param_name})s")
                params[param_name] = val

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Add limit
        if limit:
            query += f" LIMIT {limit}"

        # Execute query
        try:
            df = pd.read_sql_query(query, db.bind, params=params)
            return df
        except Exception as e:
            raise ValueError(f"Failed to query internal table '{table_name}': {e}")

    def validate(self, df: pd.DataFrame) -> QualityReport:
        """
        Validate internal dataset quality.

        Internal datasets have high trust, so validation is lenient.

        Args:
            df: DataFrame to validate

        Returns:
            Quality report
        """
        issues = []
        warnings = []

        # Check for empty dataframe
        if df.empty:
            warnings.append({"type": "empty_dataset", "message": "Query returned no results"})

        # Check for duplicate rows (exclude array columns which are unhashable)
        duplicate_count = 0
        try:
            # Find columns with hashable types
            hashable_cols = [
                col for col in df.columns
                if not df[col].apply(lambda x: isinstance(x, (list, dict))).any()
            ]
            if hashable_cols:
                duplicate_count = df[hashable_cols].duplicated().sum()
                if duplicate_count > 0:
                    warnings.append({
                        "type": "duplicate_rows",
                        "message": f"Found {duplicate_count} duplicate rows",
                        "count": int(duplicate_count)
                    })
        except:
            # Skip duplicate detection if there's an issue
            pass

        # Check for missing values
        total_cells = df.shape[0] * df.shape[1]
        missing_cells = df.isna().sum().sum()
        missing_percentage = (missing_cells / total_cells * 100) if total_cells > 0 else 0

        # Internal data is more forgiving with missing values
        if missing_percentage > 30:
            warnings.append({
                "type": "moderate_missing_values",
                "message": f"Missing values: {missing_percentage:.2f}%",
                "percentage": missing_percentage
            })

        # Calculate completeness score
        completeness_score = 1.0 - (missing_percentage / 100)

        # Internal data rarely fails validation
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
                "source": "internal_database",
                "trust_level": "high",
            },
        )

    def clean(self, df: pd.DataFrame) -> CleaningResult:
        """
        Clean internal dataset.

        Internal datasets are already well-structured, so minimal cleaning is needed.

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame and logs
        """
        cleaning_logs = []
        cleaned_df = df.copy()

        # 1. Ensure consistent datetime parsing for timestamp columns
        datetime_cols = [col for col in cleaned_df.columns if "at" in col.lower() or col.lower() in ["created_at", "updated_at"]]

        for col in datetime_cols:
            if cleaned_df[col].dtype == "object":
                try:
                    cleaned_df[col] = pd.to_datetime(cleaned_df[col])
                    cleaning_logs.append({
                        "operation": "parse_timestamps",
                        "description": f"Parsed column '{col}' as datetime",
                        "parameters": {"column": col},
                        "columns_affected": [col],
                    })
                except:
                    pass

        # 2. Convert decimal columns to float for consistency
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                try:
                    # Check if it looks like a decimal number
                    sample = cleaned_df[col].dropna().iloc[0] if not cleaned_df[col].dropna().empty else None
                    if sample and isinstance(sample, (int, float)):
                        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors="coerce")
                        cleaning_logs.append({
                            "operation": "convert_numeric",
                            "description": f"Converted column '{col}' to numeric",
                            "parameters": {"column": col},
                            "columns_affected": [col],
                        })
                except:
                    pass

        # 3. Handle array columns (PostgreSQL arrays)
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == "object":
                # Check if it's a PostgreSQL array
                sample = cleaned_df[col].dropna().iloc[0] if not cleaned_df[col].dropna().empty else None
                if sample and isinstance(sample, list):
                    cleaning_logs.append({
                        "operation": "preserve_arrays",
                        "description": f"Preserved array column '{col}' as-is",
                        "parameters": {"column": col},
                        "columns_affected": [col],
                    })

        return CleaningResult(
            cleaned_df=cleaned_df,
            cleaning_logs=cleaning_logs,
        )

    def get_provenance_info(self, dataset_ref: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate provenance information for internal dataset.

        Args:
            dataset_ref: Table reference
            df: The DataFrame

        Returns:
            Provenance metadata
        """
        table_name = dataset_ref.replace("table:", "")

        return {
            "source_name": "IMDA Internal Database",
            "source_uri": dataset_ref,
            "retrieved_at": datetime.utcnow(),
            "retrieval_method": "database",
            "row_count": len(df),
            "column_count": len(df.columns),
            "data_owner": "IMDA",
            "license_info": "Internal Use Only",
            "update_frequency": "quarterly",
            "database_table": table_name,
            "trust_level": "high",
        }

    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an internal table.

        Args:
            table_name: Name of the table

        Returns:
            Table information or None if not found
        """
        return self.INTERNAL_TABLES.get(table_name)

    def list_tables(self) -> List[str]:
        """
        List all available internal tables.

        Returns:
            List of table names
        """
        return list(self.INTERNAL_TABLES.keys())
