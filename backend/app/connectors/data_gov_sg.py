"""
Data.gov.sg V2 API connector for collections ingestion.
"""

import requests
from typing import TypedDict


class CollectionsPageResult(TypedDict):
    pages: int
    collections: list[dict]


def fetch_collections_page(page: int, timeout: int = 30) -> CollectionsPageResult:
    """
    Fetch a single page of collections from data.gov.sg V2 API.

    Args:
        page: Page number (1-indexed)
        timeout: Request timeout in seconds

    Returns:
        Dict with 'pages' (total page count) and 'collections' (list of collection dicts)

    Raises:
        ValueError: If response structure is invalid
        requests.RequestException: If request fails
    """
    url = "https://api-production.data.gov.sg/v2/public/api/collections"
    params = {"page": page}

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()

    data = response.json()

    # Validate response structure
    if "data" not in data:
        raise ValueError("Response missing 'data' field")

    inner = data["data"]

    if "pages" not in inner:
        raise ValueError("Response missing 'data.pages' field")

    if "collections" not in inner:
        raise ValueError("Response missing 'data.collections' field")

    pages = inner["pages"]
    collections = inner["collections"]

    if not isinstance(pages, int) or pages < 0:
        raise ValueError(f"Invalid 'data.pages' value: {pages}")

    if not isinstance(collections, list):
        raise ValueError(f"'data.collections' is not a list")

    return CollectionsPageResult(pages=pages, collections=collections)
