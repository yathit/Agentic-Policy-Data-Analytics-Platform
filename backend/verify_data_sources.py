#!/usr/bin/env python3
"""
Quick verification script to test data source connectors.
Run: docker compose -f infra/docker-compose.yml exec api python verify_data_sources.py
"""

import sys
sys.path.insert(0, '/app')

from app.connectors import InternalConnector
from app.core.database import SessionLocal

def main():
    print("=" * 60)
    print("Data Sources Verification")
    print("=" * 60)
    print()

    # Test 1: Internal Connector Discovery
    print("1. Testing Internal Connector Discovery")
    print("-" * 60)
    connector = InternalConnector()

    candidates = connector.discover("employment")
    print(f"   Found {len(candidates)} datasets matching 'employment':")
    for candidate in candidates:
        print(f"   - {candidate.name}")
    print()

    # Test 2: List All Internal Tables
    print("2. Listing All Internal Tables")
    print("-" * 60)
    tables = connector.list_tables()
    print(f"   Available tables: {len(tables)}")
    for table in tables:
        info = connector.get_table_info(table)
        print(f"   - {table}: {info['name']}")
    print()

    # Test 3: Fetch Data from Internal Table
    print("3. Fetching Sample Data")
    print("-" * 60)
    try:
        df = connector.fetch_dataframe(
            "digital_sector_employment",
            filters={"year": 2024, "sector": "AI and Data Analytics"}
        )
        print(f"   Fetched {len(df)} rows from digital_sector_employment")
        print(f"   Columns: {list(df.columns)}")
        if not df.empty:
            print(f"   Sample data:")
            print(f"   - Sector: {df.iloc[0]['sector']}")
            print(f"   - Year: {df.iloc[0]['year']}")
            print(f"   - Quarter: {df.iloc[0]['quarter']}")
            print(f"   - Total Employees: {df.iloc[0]['total_employees']}")
    except Exception as e:
        print(f"   Error fetching data: {e}")
    print()

    # Test 4: Validate Data
    print("4. Validating Data Quality")
    print("-" * 60)
    try:
        df = connector.fetch_dataframe("ai_workforce_programmes")
        report = connector.validate(df)
        print(f"   Validation Status: {report.status}")
        print(f"   Completeness Score: {report.completeness_score:.2%}")
        print(f"   Missing Values: {report.missing_value_percentage:.2f}%")
        print(f"   Duplicate Rows: {report.duplicate_row_count}")
    except Exception as e:
        print(f"   Error validating: {e}")
    print()

    # Test 5: Clean Data
    print("5. Testing Data Cleaning")
    print("-" * 60)
    try:
        df = connector.fetch_dataframe("emerging_tech_adoption_index", limit=5)
        result = connector.clean(df)
        print(f"   Original rows: {len(df)}")
        print(f"   Cleaned rows: {len(result.cleaned_df)}")
        print(f"   Cleaning operations: {len(result.cleaning_logs)}")
        for log in result.cleaning_logs:
            print(f"   - {log['operation']}: {log['description']}")
    except Exception as e:
        print(f"   Error cleaning: {e}")
    print()

    # Test 6: Database Models
    print("6. Testing Database Models")
    print("-" * 60)
    try:
        from app.models import Dataset
        db = SessionLocal()
        dataset_count = db.query(Dataset).count()
        print(f"   Datasets in database: {dataset_count}")
        db.close()
    except Exception as e:
        print(f"   Error querying database: {e}")
    print()

    connector.close()

    print("=" * 60)
    print("✓ Verification Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
