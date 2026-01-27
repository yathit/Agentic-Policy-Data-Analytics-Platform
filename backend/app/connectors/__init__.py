"""
Data source connectors for Policy Analytics Platform.
"""

from app.connectors.base import BaseConnector, DatasetCandidate
from app.connectors.datagov import DataGovConnector
from app.connectors.singstat import SingStatConnector
from app.connectors.internal import InternalConnector

__all__ = [
    "BaseConnector",
    "DatasetCandidate",
    "DataGovConnector",
    "SingStatConnector",
    "InternalConnector",
]
