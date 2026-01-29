"""
Plan schema for coordinator agent output and approval gate.
The plan is the contract between user intent and agent execution.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    """Time range for analysis."""

    start: str = Field(..., description="Start year (YYYY format)")
    end: str = Field(..., description="End year (YYYY format)")


class Intent(BaseModel):
    """
    Structured representation of user intent.
    Parsed from user query by Coordinator agent.
    """

    question: str = Field(..., description="Clear statement of the question")
    time_range: TimeRange = Field(..., description="Time period of interest")
    entities: List[str] = Field(
        default_factory=list, description="Entities (countries, sectors, demographics)"
    )
    metrics: List[str] = Field(
        default_factory=list, description="Metrics to analyze"
    )


class DiscoveredDataset(BaseModel):
    """A dataset discovered through connector discovery."""

    id: str = Field(..., description="Dataset ID or reference URI")
    title: str = Field(..., description="Human-readable dataset title")
    score: float = Field(default=0.0, description="Relevance score (0-1)")
    discovered_by: str = Field(..., description="Discovery method or connector name")


class DataSource(BaseModel):
    """Data source specification."""

    name: str = Field(
        ..., description="Source name: data.gov.sg, singstat, internal"
    )
    datasets: List[DiscoveredDataset] = Field(
        default_factory=list, description="Discovered datasets with metadata"
    )
    format: str = Field(..., description="Data format: api, csv, excel, json")


class DiscoveryStep(BaseModel):
    """A discovery step showing how datasets were found."""

    source: str = Field(..., description="Source name: data.gov.sg, singstat")
    query: str = Field(..., description="Search query used for discovery")
    notes: str = Field(default="", description="Additional notes about the discovery")


class ExtractionStep(BaseModel):
    """Single extraction step in the plan."""

    source: str = Field(..., description="Source name")
    dataset_ref: str = Field(..., description="Specific dataset reference (URI, ID, etc)")
    notes: str = Field(..., description="Why this dataset is needed")


class AnalysisStepType(str):
    """Types of analysis steps."""

    TREND = "trend"
    YOY = "yoy"
    BREAKDOWN = "breakdown"
    CORRELATION = "correlation"


class AnalysisStep(BaseModel):
    """Single analysis step in the plan."""

    type: str = Field(
        ..., description="Analysis type: trend, yoy, breakdown, correlation"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Analysis parameters (metric, group_by, etc)"
    )


class Guardrails(BaseModel):
    """Execution guardrails and constraints."""

    approved_sources_only: bool = Field(
        default=True, description="Only use approved data sources"
    )
    no_llm_math: bool = Field(
        default=True, description="LLMs cannot perform mathematical computations"
    )
    citation_required: bool = Field(
        default=True, description="All claims must be cited with dataset IDs"
    )


class Plan(BaseModel):
    """
    Complete execution plan for user query.

    Created by Coordinator agent, approved by user (HITL gate),
    executed by Extraction and Analytics agents.
    """

    intent: Intent = Field(..., description="Structured user intent")
    sources: List[DataSource] = Field(..., description="Data sources to use")
    discovery_steps: List[DiscoveryStep] = Field(
        default_factory=list, description="Discovery steps showing how datasets were found"
    )
    extract_steps: List[ExtractionStep] = Field(..., description="Extraction steps")
    analysis_steps: List[AnalysisStep] = Field(..., description="Analysis steps")
    guardrails: Guardrails = Field(
        default_factory=Guardrails, description="Execution guardrails"
    )
    approved: bool = Field(default=False, description="Whether plan is approved")

    class Config:
        json_schema_extra = {
            "example": {
                "intent": {
                    "question": "What has been the trend in Singapore's tech sector employment from 2018 to 2023?",
                    "time_range": {"start": "2018", "end": "2023"},
                    "entities": ["Singapore", "tech sector"],
                    "metrics": ["employment"],
                },
                "sources": [
                    {
                        "name": "singstat",
                        "datasets": [
                            {
                                "id": "M182931",
                                "title": "Employed Residents By Industry",
                                "score": 0.85,
                                "discovered_by": "singstat_discovery",
                            }
                        ],
                        "format": "api",
                    }
                ],
                "discovery_steps": [
                    {
                        "source": "singstat",
                        "query": "employment industry tech",
                        "notes": "Searching for employment statistics by industry sector",
                    }
                ],
                "extract_steps": [
                    {
                        "source": "singstat",
                        "dataset_ref": "M182931",
                        "notes": "Primary employment data for tech sector",
                    }
                ],
                "analysis_steps": [
                    {
                        "type": "trend",
                        "params": {
                            "metric": "employment_count",
                            "group_by": "year",
                            "sector_filter": "technology",
                        },
                    }
                ],
                "guardrails": {
                    "approved_sources_only": True,
                    "no_llm_math": True,
                    "citation_required": True,
                },
                "approved": False,
            }
        }


class PlanApprovalRequest(BaseModel):
    """Request to approve or reject a plan."""

    run_id: str = Field(..., description="Run identifier")
    approved: bool = Field(..., description="Whether to approve the plan")
    feedback: Optional[str] = Field(
        None, description="Optional feedback if plan is rejected"
    )
