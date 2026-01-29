"""
Data source connectors for Policy Analytics Platform.
"""

from app.connectors.base import BaseConnector, DatasetCandidate
from app.connectors.datagov_v2 import DataGovV2Connector
from app.connectors.singstat import SingStatConnector
from app.connectors.internal import InternalConnector

__all__ = [
    "BaseConnector",
    "DatasetCandidate",
    "DataGovV2Connector",
    "SingStatConnector",
    "InternalConnector",
]
