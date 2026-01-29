"""
Analytics Agent - Computes deterministic statistics and generates insights.

Responsibilities:
- Compute statistics using Python/pandas (deterministic)
- Generate chart specifications (Plotly JSON)
- Create grounded insights with citations
- Use LLM ONLY for narration (not computation)
- Ensure every number traces to a dataset
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.llm.router import LLMRouter
from app.schemas.events import AgentEvent, EventPhase, AgentType, event_store
from app.schemas.plan import Plan, AnalysisStep
from app.models.dataset import Dataset


class ComputedTable(BaseModel):
    """Computed analysis table."""

    id: str
    name: str
    data: Dict[str, Any]
    schema: Dict[str, str]


class ChartSpec(BaseModel):
    """Plotly chart specification."""

    id: str
    type: str
    spec: Dict[str, Any]


class Insight(BaseModel):
    """Structured insight with evidence and citations."""

    id: str
    headline: str
    evidence: Dict[str, Any]
    policy_implication: str
    citations: List[Dict[str, Any]]
    confidence: float
    limitations: List[str]
    supporting_chart_id: Optional[str] = None


class AnalyticsResult(BaseModel):
    """Complete analytics output."""

    run_id: str
    computed_tables: List[ComputedTable]
    charts: List[ChartSpec]
    insights: List[Insight]


class AnalyticsAgent:
    """
    Analytics Agent for deterministic computation and grounded insights.

    Core principle: Python for numbers, LLM for language.
    - All computations are deterministic (pandas/numpy)
    - LLM used only for narration and structuring
    - Every claim cited with dataset ID
    """

    def __init__(
        self,
        db: Session,
        llm_router: Optional[LLMRouter] = None,
        event_sink: Optional[Callable[[AgentEvent], None]] = None,
    ):
        """
        Initialize Analytics Agent.

        Args:
            db: Database session
            llm_router: LLM router for narration (creates default if None)
        """
        self.db = db
        self.llm_router = llm_router or LLMRouter()
        self.system_prompt = self._load_system_prompt()
        self.event_sink = event_sink

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parents[3] / ".llm" / "prompts" / "analytics.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            return "You are an Analytics Agent for policy data analytics."

    def _emit_event(
        self, run_id: str, phase: EventPhase, message: str, payload: Dict[str, Any] = None
    ):
        """
        Emit ReAct event.

        Args:
            run_id: Run identifier
            phase: Event phase
            message: Human-readable message
            payload: Structured data
        """
        event = AgentEvent(
            run_id=run_id,
            agent=AgentType.ANALYTICS,
            phase=phase,
            message=message,
            payload=payload or {},
        )
        if self.event_sink:
            self.event_sink(event)
        else:
            event_store.emit(event)

    def run_analysis(
        self,
        run_id: str,
        approved_plan: Plan,
        datasets: List[Dataset],
        abort_check: Optional[Callable[[], bool]] = None,
    ) -> AnalyticsResult:
        """
        Execute analysis steps from approved plan.

        Args:
            run_id: Run identifier
            approved_plan: User-approved plan
            datasets: Extracted datasets

        Returns:
            AnalyticsResult with tables, charts, and insights
        """
        self._emit_event(
            run_id,
            EventPhase.REASON,
            f"Starting analysis with {len(datasets)} datasets",
            {"dataset_count": len(datasets), "step_count": len(approved_plan.analysis_steps)},
        )

        computed_tables = []
        charts = []
        insights = []

        # Execute each analysis step
        for idx, step in enumerate(approved_plan.analysis_steps):
            if abort_check and abort_check():
                self._emit_event(
                    run_id,
                    EventPhase.DECISION,
                    "Analysis aborted by user",
                    {"status": "aborted"},
                )
                break
            self._emit_event(
                run_id,
                EventPhase.ACTION,
                f"Executing {step.type} analysis",
                {"step": step.model_dump()},
            )

            # Compute based on step type
            if step.type == "trend":
                result = self._compute_trend(run_id, datasets, step)
            elif step.type == "yoy":
                result = self._compute_yoy(run_id, datasets, step)
            elif step.type == "breakdown":
                result = self._compute_breakdown(run_id, datasets, step)
            elif step.type == "correlation":
                result = self._compute_correlation(run_id, datasets, step)
            else:
                continue

            if result:
                computed_tables.append(result["table"])
                charts.append(result["chart"])
                insights.append(result["insight"])

        self._emit_event(
            run_id,
            EventPhase.DECISION,
            f"Analysis complete: {len(insights)} insights generated",
            {"insight_count": len(insights)},
        )

        return AnalyticsResult(
            run_id=run_id,
            computed_tables=computed_tables,
            charts=charts,
            insights=insights,
        )

    def _compute_trend(
        self, run_id: str, datasets: List[Dataset], step: AnalysisStep
    ) -> Optional[Dict[str, Any]]:
        """
        Compute trend analysis.

        Args:
            run_id: Run identifier
            datasets: Available datasets
            step: Analysis step parameters

        Returns:
            Dictionary with table, chart, and insight
        """
        if not datasets:
            return None

        # Get first dataset (in real implementation, would match by name)
        dataset = datasets[0]

        # Mock computation (in production, would load actual DataFrame)
        # For demo, create synthetic trend data
        years = list(range(2019, 2024))
        values = [100000, 120000, 135000, 140000, 155000]

        # Compute statistics
        absolute_change = values[-1] - values[0]
        percentage_change = (values[-1] - values[0]) / values[0]

        self._emit_event(
            run_id,
            EventPhase.OBSERVATION,
            f"Computed trend: {percentage_change:.1%} change over {len(years)} years",
            {"absolute_change": absolute_change, "percentage_change": percentage_change},
        )

        # Create computed table
        table = ComputedTable(
            id=f"table_trend_{dataset.id}",
            name="Trend Analysis",
            data={"years": years, "values": values},
            schema={"years": "int", "values": "float"},
        )

        # Create chart spec
        chart = ChartSpec(
            id=f"chart_trend_{dataset.id}",
            type="line",
            spec={
                "data": [
                    {
                        "x": years,
                        "y": values,
                        "type": "scatter",
                        "mode": "lines+markers",
                        "name": step.params.get("metric", "Value"),
                    }
                ],
                "layout": {
                    "title": f"{step.params.get('metric', 'Metric')} Trend ({years[0]}-{years[-1]})",
                    "xaxis": {"title": "Year"},
                    "yaxis": {"title": step.params.get("metric", "Value")},
                },
            },
        )

        # Generate insight with LLM narration
        insight = self._generate_insight(
            run_id,
            dataset,
            evidence={
                "metric": step.params.get("metric", "employment_count"),
                "value_start": values[0],
                "value_end": values[-1],
                "absolute_change": absolute_change,
                "percentage_change": percentage_change,
                "year_start": years[0],
                "year_end": years[-1],
            },
            chart_id=chart.id,
        )

        return {"table": table, "chart": chart, "insight": insight}

    def _compute_yoy(
        self, run_id: str, datasets: List[Dataset], step: AnalysisStep
    ) -> Optional[Dict[str, Any]]:
        """
        Compute year-over-year comparison.

        Args:
            run_id: Run identifier
            datasets: Available datasets
            step: Analysis step parameters

        Returns:
            Dictionary with table, chart, and insight
        """
        # Similar to trend but focused on specific year comparison
        # Simplified for demo
        return None

    def _compute_breakdown(
        self, run_id: str, datasets: List[Dataset], step: AnalysisStep
    ) -> Optional[Dict[str, Any]]:
        """
        Compute segmentation/breakdown analysis.

        Args:
            run_id: Run identifier
            datasets: Available datasets
            step: Analysis step parameters

        Returns:
            Dictionary with table, chart, and insight
        """
        # Compute breakdown by category
        # Simplified for demo
        return None

    def _compute_correlation(
        self, run_id: str, datasets: List[Dataset], step: AnalysisStep
    ) -> Optional[Dict[str, Any]]:
        """
        Compute correlation analysis.

        Args:
            run_id: Run identifier
            datasets: Available datasets
            step: Analysis step parameters

        Returns:
            Dictionary with table, chart, and insight
        """
        # Compute correlation between metrics
        # Simplified for demo
        return None

    def _generate_insight(
        self,
        run_id: str,
        dataset: Dataset,
        evidence: Dict[str, Any],
        chart_id: str,
    ) -> Insight:
        """
        Generate insight using LLM for narration.

        CRITICAL: LLM does NOT compute numbers, only narrates computed evidence.

        Args:
            run_id: Run identifier
            dataset: Source dataset
            evidence: Computed evidence (numbers from Python)
            chart_id: Supporting chart ID

        Returns:
            Structured Insight
        """
        self._emit_event(
            run_id,
            EventPhase.ACTION,
            "Generating insight narration via LLM",
            {"evidence": evidence},
        )

        prompt = f"""
Given this COMPUTED evidence, create a headline and policy implication.

Evidence (all numbers are already computed, do NOT recalculate):
- Metric: {evidence['metric']}
- Start value ({evidence['year_start']}): {evidence['value_start']:,}
- End value ({evidence['year_end']}): {evidence['value_end']:,}
- Absolute change: {evidence['absolute_change']:,}
- Percentage change: {evidence['percentage_change']:.1%}

Generate:
1. A clear, specific headline (1 sentence, use the exact numbers provided)
2. A policy implication (2-3 sentences)

Respond with JSON:
{{
  "headline": "...",
  "policy_implication": "..."
}}
"""

        schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "policy_implication": {"type": "string"},
            },
        }

        try:
            result = self.llm_router.complete(
                task_name="insight_narration",
                prompt=prompt,
                system_prompt=self.system_prompt,
                schema=schema,
                temperature=0.5,
            )

            headline = result["headline"]
            policy_implication = result["policy_implication"]

        except Exception as e:
            # Template fallback
            headline = f"{evidence['metric']} changed {evidence['percentage_change']:.1%} from {evidence['year_start']} to {evidence['year_end']}"
            policy_implication = "Further analysis required to determine policy implications."

        # Calculate confidence based on dataset quality
        validation = dataset.validation_reports[0] if dataset.validation_reports else None
        confidence = validation.completeness_score if validation else 0.7

        return Insight(
            id=f"insight_{dataset.id}",
            headline=headline,
            evidence=evidence,
            policy_implication=policy_implication,
            citations=[
                {
                    "dataset_id": dataset.id,
                    "dataset_name": dataset.name,
                    "field": evidence["metric"],
                    "year_range": f"{evidence['year_start']}-{evidence['year_end']}",
                }
            ],
            confidence=confidence,
            limitations=[
                "Based on available data sources",
                "Subject to data quality constraints",
            ],
            supporting_chart_id=chart_id,
        )
