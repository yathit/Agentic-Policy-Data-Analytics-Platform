"""
Repository for data_gov_sg_collection table operations.
"""

from datetime import datetime
from typing import TypedDict
from sqlalchemy import text
from sqlalchemy.orm import Session


class CollectionRow(TypedDict):
    collection_id: str
    lastUpdatedAt: datetime
    name: str | None
    description: str | None
    child_dataset_ids: list[str]
    payload: dict


def insert_many_ignore_conflicts(db: Session, rows: list[CollectionRow]) -> int:
    """
    Insert collection rows, ignoring conflicts on (collection_id, lastUpdatedAt).

    Args:
        db: SQLAlchemy session
        rows: List of collection row dicts

    Returns:
        Number of rows actually inserted (excludes conflicts)
    """
    if not rows:
        return 0

    sql = text("""
        INSERT INTO data_gov_sg_collection
            (collection_id, lastUpdatedAt, name, description, child_dataset_ids, payload)
        VALUES
            (:collection_id, :lastUpdatedAt, :name, :description, :child_dataset_ids, :payload)
        ON CONFLICT (collection_id, lastUpdatedAt) DO NOTHING
    """)

    inserted = 0
    for row in rows:
        result = db.execute(sql, {
            "collection_id": row["collection_id"],
            "lastUpdatedAt": row["lastUpdatedAt"],
            "name": row["name"],
            "description": row["description"],
            "child_dataset_ids": row["child_dataset_ids"],
            "payload": row["payload"],
        })
        # For INSERT ... ON CONFLICT DO NOTHING, rowcount is 1 if inserted, 0 if skipped
        inserted += result.rowcount

    db.commit()
    return inserted
