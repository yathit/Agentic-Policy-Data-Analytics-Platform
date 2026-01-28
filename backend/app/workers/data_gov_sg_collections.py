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
    skipped: int
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


def map_collection_to_row(collection: dict, errors: list[str]) -> CollectionRow | None:
    """
    Map a collection dict from the API to a database row.

    Skips records missing required fields (collectionId, lastUpdatedAt).

    Args:
        collection: Collection dict from API response
        errors: List to append error messages for skipped records

    Returns:
        CollectionRow dict ready for insertion, or None if record is invalid
    """
    # Validate required fields
    if "collectionId" not in collection:
        errors.append(f"Skipped record: missing 'collectionId' - {collection.get('name', 'unknown')}")
        return None

    if "lastUpdatedAt" not in collection:
        errors.append(f"Skipped record: missing 'lastUpdatedAt' - collectionId={collection['collectionId']}")
        return None

    try:
        last_updated = parse_ts(collection["lastUpdatedAt"])
    except (ValueError, TypeError) as e:
        errors.append(f"Skipped record: invalid 'lastUpdatedAt' - collectionId={collection['collectionId']}: {e}")
        return None

    return CollectionRow(
        collection_id=collection["collectionId"],
        lastUpdatedAt=last_updated,
        name=collection.get("name"),
        description=collection.get("description"),
        child_dataset_ids=collection.get("childDatasets") or [],
        payload=collection,
    )


def _process_page(collections: list[dict], db, errors: list[str]) -> tuple[int, int, int]:
    """
    Process a page of collections.

    Args:
        collections: List of collection dicts
        db: Database session
        errors: List to append error messages

    Returns:
        Tuple of (collections_seen, rows_inserted, skipped)
    """
    rows: list[CollectionRow] = []
    skipped = 0

    for c in collections:
        row = map_collection_to_row(c, errors)
        if row is not None:
            rows.append(row)
        else:
            skipped += 1

    inserted = insert_many_ignore_conflicts(db, rows) if rows else 0
    return len(collections), inserted, skipped


def run_data_gov_sg_collections_ingest() -> IngestResult:
    """
    Ingest all collections from data.gov.sg into Postgres.

    Fetches all pages of collections and inserts them with idempotency
    (same version re-run is ignored, updated collection creates new row).

    Error handling:
    - Retries transient failures (timeouts, 429, 5xx) with exponential backoff
    - Hard-fails on response shape drift (missing data.pages/data.collections)
    - Skips records missing collectionId or lastUpdatedAt (tracked in errors)

    Returns:
        IngestResult with pages_fetched, collections_seen, rows_inserted, skipped, and optional errors
    """
    db = SessionLocal()
    errors: list[str] = []
    pages_fetched = 0
    collections_seen = 0
    rows_inserted = 0
    skipped = 0

    try:
        # Fetch first page to get total page count
        result = fetch_collections_page(page=1)
        total_pages = result["pages"]
        pages_fetched = 1

        # Process first page
        seen, inserted, page_skipped = _process_page(result["collections"], db, errors)
        collections_seen += seen
        rows_inserted += inserted
        skipped += page_skipped

        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            try:
                result = fetch_collections_page(page=page)
                pages_fetched += 1

                seen, inserted, page_skipped = _process_page(result["collections"], db, errors)
                collections_seen += seen
                rows_inserted += inserted
                skipped += page_skipped

            except ValueError as e:
                # Hard fail on response shape drift - re-raise
                raise
            except Exception as e:
                errors.append(f"Page {page}: {str(e)}")

    except ValueError as e:
        # Hard fail on response shape drift
        errors.append(f"Fatal: {str(e)}")
        raise

    except Exception as e:
        errors.append(f"Initial fetch: {str(e)}")

    finally:
        db.close()

    return IngestResult(
        pages_fetched=pages_fetched,
        collections_seen=collections_seen,
        rows_inserted=rows_inserted,
        skipped=skipped,
        errors=errors if errors else None,
    )
