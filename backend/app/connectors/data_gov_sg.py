"""
Data.gov.sg V2 API connector for collections ingestion.
"""

import time
import requests
from typing import TypedDict


class CollectionsPageResult(TypedDict):
    pages: int
    collections: list[dict]


# Transient HTTP status codes that warrant retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_collections_page(
    page: int,
    timeout: int = 30,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> CollectionsPageResult:
    """
    Fetch a single page of collections from data.gov.sg V2 API.

    Implements exponential backoff retry for transient failures.

    Args:
        page: Page number (1-indexed)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Dict with 'pages' (total page count) and 'collections' (list of collection dicts)

    Raises:
        ValueError: If response structure is invalid (hard fail - no retry)
        requests.RequestException: If request fails after all retries
    """
    url = "https://api-production.data.gov.sg/v2/public/api/collections"
    params = {"page": page}

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)

            # Check for retryable status codes
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                # Last attempt failed with retryable status
                response.raise_for_status()

            response.raise_for_status()

            data = response.json()

            # Validate response structure - hard fail on shape drift
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
                raise ValueError("'data.collections' is not a list")

            return CollectionsPageResult(pages=pages, collections=collections)

        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            raise

        except requests.exceptions.RequestException as e:
            # Non-timeout request exceptions - check if retryable
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in RETRYABLE_STATUS_CODES:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
            raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in fetch_collections_page")
