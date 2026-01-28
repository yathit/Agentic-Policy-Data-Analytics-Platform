"""
Worker for ingesting data.gov.sg collections into Postgres.
"""

from datetime import datetime
from typing import TypedDict

from app.core.database import SessionLocal
from app.connectors.data_gov_sg import fetch_collections_page
from app.db.repo_data_gov_sg_collection import insert_many_ignore_conflicts, CollectionRow


class IngestResult(TypedDict):
    pages_fetched: int
    collections_seen: int
    rows_inserted: int
    errors: list[str] | None


def parse_ts(ts_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string to datetime.

    Args:
        ts_str: Timestamp string (e.g., "2024-01-15T10:30:00.000Z")

    Returns:
        Parsed datetime object (timezone-aware)
    """
    # Handle various ISO formats
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def map_collection_to_row(collection: dict) -> CollectionRow:
    """
    Map a collection dict from the API to a database row.

    Args:
        collection: Collection dict from API response

    Returns:
        CollectionRow dict ready for insertion
    """
    return CollectionRow(
        collection_id=collection["collectionId"],
        lastUpdatedAt=parse_ts(collection["lastUpdatedAt"]),
        name=collection.get("name"),
        description=collection.get("description"),
        child_dataset_ids=collection.get("childDatasets") or [],
        payload=collection,
    )


def run_data_gov_sg_collections_ingest() -> IngestResult:
    """
    Ingest all collections from data.gov.sg into Postgres.

    Fetches all pages of collections and inserts them with idempotency
    (same version re-run is ignored, updated collection creates new row).

    Returns:
        IngestResult with pages_fetched, collections_seen, rows_inserted, and optional errors
    """
    db = SessionLocal()
    errors: list[str] = []
    pages_fetched = 0
    collections_seen = 0
    rows_inserted = 0

    try:
        # Fetch first page to get total page count
        result = fetch_collections_page(page=1)
        total_pages = result["pages"]
        pages_fetched = 1

        # Process first page
        rows = [map_collection_to_row(c) for c in result["collections"]]
        collections_seen += len(result["collections"])
        rows_inserted += insert_many_ignore_conflicts(db, rows)

        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            try:
                result = fetch_collections_page(page=page)
                pages_fetched += 1

                rows = [map_collection_to_row(c) for c in result["collections"]]
                collections_seen += len(result["collections"])
                rows_inserted += insert_many_ignore_conflicts(db, rows)

            except Exception as e:
                errors.append(f"Page {page}: {str(e)}")

    except Exception as e:
        errors.append(f"Initial fetch: {str(e)}")

    finally:
        db.close()

    return IngestResult(
        pages_fetched=pages_fetched,
        collections_seen=collections_seen,
        rows_inserted=rows_inserted,
        errors=errors if errors else None,
    )
