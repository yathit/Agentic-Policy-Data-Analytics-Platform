"""
Shared utilities for data source handling.
"""

from typing import Optional


def normalize_sources(sources: Optional[list]) -> list:
    """
    Normalize source identifiers to canonical values.

    Handles various naming conventions for data sources and converts them
    to their canonical form used throughout the system.

    Args:
        sources: List of source identifiers (may include aliases)

    Returns:
        List of normalized source identifiers
    """
    if not sources:
        return ["data.gov.sg", "singstat"]

    normalized = []
    for source in sources:
        if source in ["data_gov_sg", "data.gov.sg"]:
            normalized.append("data.gov.sg")
        elif source in ["singstat"]:
            normalized.append("singstat")
        elif source in ["internal", "mock_internal"]:
            normalized.append("internal")
        else:
            normalized.append(source)
    return normalized
