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
import re
from urllib.parse import urlparse
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
from app.connectors import DataGovV2Connector, SingStatConnector, InternalConnector
from app.core.config import settings


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
    llm_response: Optional[Dict[str, Any]] = None


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
        self.connectors = {
            "data.gov.sg": DataGovV2Connector(config={"api_key": settings.data_gov_sg_api_key}),
            "singstat": SingStatConnector(),
            "internal": InternalConnector(),
        }

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parents[2] / ".llm" / "prompts" / "analytics.md"
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
                result = self._compute_trend(run_id, datasets, step, approved_plan)
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
        self,
        run_id: str,
        datasets: List[Dataset],
        step: AnalysisStep,
        approved_plan: Plan,
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

        dataset = self._select_dataset_for_step(run_id, datasets, step)
        if not dataset:
            return None

        df = self._load_dataset_dataframe(run_id, dataset)
        if df is None or df.empty:
            return None

        time_col = self._select_time_column(df)
        if not time_col:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No time column found for trend analysis",
                {"columns": list(df.columns)},
            )
            return None

        metric_param = step.params.get("metric") if step.params else None
        value_col = self._select_value_column(df, metric_param, time_col)
        if not value_col:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No numeric value column found for trend analysis",
                {"columns": list(df.columns)},
            )
            return None

        series_df = df[[time_col, value_col]].copy()
        series_df[time_col] = self._normalize_time_to_year(series_df[time_col])
        series_df[value_col] = pd.to_numeric(series_df[value_col], errors="coerce")
        series_df = series_df.dropna(subset=[time_col, value_col])
        series_df = series_df.groupby(time_col, dropna=True)[value_col].mean().sort_index()

        if series_df.empty:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No usable time series data after normalization",
                {"time_col": time_col, "value_col": value_col},
            )
            return None

        time_range = approved_plan.intent.time_range if approved_plan and approved_plan.intent else None
        if time_range:
            try:
                start_year = int(time_range.start)
                end_year = int(time_range.end)
                series_df = series_df.loc[
                    (series_df.index >= start_year) & (series_df.index <= end_year)
                ]
                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    "Applied time range filter for trend analysis",
                    {
                        "time_range": {
                            "start": start_year,
                            "end": end_year,
                        }
                    },
                )
            except (TypeError, ValueError):
                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    "Invalid time range; skipping filter",
                    {
                        "time_range": {
                            "start": time_range.start,
                            "end": time_range.end,
                        }
                    },
                )

        if series_df.empty:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No data available after applying time range filter",
                {"time_range": {"start": time_range.start, "end": time_range.end}}
                if time_range
                else {},
            )
            return None

        years = series_df.index.astype(int).tolist()
        values = series_df.values.tolist()

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
        requested_range = (
            {"start": time_range.start, "end": time_range.end} if time_range else None
        )
        used_range = {"start": years[0], "end": years[-1]}

        insight = self._generate_insight(
            run_id,
            dataset,
            evidence={
                "metric": metric_param or value_col,
                "value_start": values[0],
                "value_end": values[-1],
                "absolute_change": absolute_change,
                "percentage_change": percentage_change,
                "year_start": years[0],
                "year_end": years[-1],
                "dataset_id": dataset.id,
                "dataset_ref": self._extract_dataset_ref(dataset),
                "dataset_source": dataset.source_type,
                "time_range": used_range,
                "requested_time_range": requested_range,
            },
            chart_id=chart.id,
        )

        return {"table": table, "chart": chart, "insight": insight}

    def _select_dataset_for_step(
        self,
        run_id: str,
        datasets: List[Dataset],
        step: AnalysisStep,
    ) -> Optional[Dataset]:
        """
        Select the most appropriate dataset for a given analysis step.

        Uses dataset_ref/source if provided, otherwise falls back to the first dataset.
        """
        if not datasets:
            return None

        target_ref = (step.dataset_ref or "").strip() if hasattr(step, "dataset_ref") else ""
        target_source = (step.source or "").strip() if hasattr(step, "source") else ""

        if target_ref or target_source:
            for dataset in datasets:
                if target_source and dataset.source_type != target_source:
                    continue

                if target_ref:
                    extracted = self._extract_dataset_ref(dataset)
                    if extracted == target_ref:
                        return dataset
                    if dataset.name == target_ref:
                        return dataset
                    if dataset.provenance and dataset.provenance.source_uri:
                        if target_ref in dataset.provenance.source_uri:
                            return dataset
                else:
                    return dataset

            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No dataset matched analysis step reference; falling back to first dataset",
                {"dataset_ref": target_ref, "source": target_source},
            )

        return datasets[0]

    def _load_dataset_dataframe(self, run_id: str, dataset: Dataset) -> Optional[pd.DataFrame]:
        """
        Load a dataset into a DataFrame for analysis.

        Uses connectors to refetch the source data based on provenance.
        """
        connector = self.connectors.get(dataset.source_type)
        if not connector:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                f"No connector available for source type '{dataset.source_type}'",
                {"source_type": dataset.source_type},
            )
            return None

        dataset_ref = self._extract_dataset_ref(dataset)
        if not dataset_ref:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "Unable to determine dataset reference for analysis",
                {"dataset_id": dataset.id, "source_type": dataset.source_type},
            )
            return None

        try:
            if dataset.source_type == "internal":
                df = connector.fetch_dataframe(dataset_ref.replace("table:", ""))
            else:
                raw_bytes = connector.fetch(dataset_ref)
                format_hint = dataset.format
                if format_hint in {"unknown", "api", ""}:
                    format_hint = None
                df = connector.parse(raw_bytes, format_hint)

            cleaned = connector.clean(df).cleaned_df

            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                f"Loaded dataset {dataset.id} for analysis",
                {"rows": len(cleaned), "columns": len(cleaned.columns)},
            )

            return cleaned
        except Exception as e:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                f"Failed to load dataset for analysis: {e}",
                {"dataset_id": dataset.id, "source_type": dataset.source_type},
            )
            return None

    def _extract_dataset_ref(self, dataset: Dataset) -> Optional[str]:
        """Extract a dataset reference from stored metadata."""
        if dataset.provenance and dataset.provenance.source_uri:
            source_uri = dataset.provenance.source_uri
            if dataset.source_type == "data.gov.sg":
                match = re.search(r"/datasets/([^/]+)", source_uri)
                if match:
                    return match.group(1)
            if dataset.source_type == "singstat":
                return urlparse(source_uri).path.rstrip("/").split("/")[-1]
            return source_uri

        name_prefix = f"{dataset.source_type}_"
        if dataset.name and dataset.name.startswith(name_prefix):
            return dataset.name[len(name_prefix):]

        return None

    def _select_time_column(self, df: pd.DataFrame) -> Optional[str]:
        """Pick a reasonable time column for trend analysis."""
        preferred = ["year", "period", "date", "time", "month", "quarter"]
        lower_map = {c.lower(): c for c in df.columns}
        for key in preferred:
            if key in lower_map:
                return lower_map[key]

        for col in df.columns:
            col_lower = col.lower()
            if any(k in col_lower for k in preferred):
                return col

        return None

    def _select_value_column(
        self, df: pd.DataFrame, metric: Optional[str], time_col: str
    ) -> Optional[str]:
        """Pick a numeric value column based on metric or heuristics."""
        if metric:
            metric_lower = metric.lower()
            for col in df.columns:
                if col.lower() == metric_lower:
                    return col

        for key in ["value", "count", "total", "amount"]:
            for col in df.columns:
                if col.lower() == key:
                    return col

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if time_col in numeric_cols:
            numeric_cols = [c for c in numeric_cols if c != time_col]

        return numeric_cols[0] if numeric_cols else None

    def _normalize_time_to_year(self, series: pd.Series) -> pd.Series:
        """Normalize a time-like series to year integers."""
        if pd.api.types.is_datetime64_any_dtype(series):
            return series.dt.year

        if pd.api.types.is_numeric_dtype(series):
            return series.astype("Int64")

        return pd.to_datetime(series, errors="coerce").dt.year

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
            {
                "evidence": evidence,
                "dataset_id": dataset.id,
                "dataset_ref": self._extract_dataset_ref(dataset),
                "dataset_source": dataset.source_type,
                "time_range": evidence.get("time_range"),
                "requested_time_range": evidence.get("requested_time_range"),
            },
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
                return_metadata=True,
            )

            parsed = result.get("parsed") if isinstance(result, dict) else None
            if not parsed:
                raise ValueError("LLM response missing parsed content")

            headline = parsed.get("headline", "")
            policy_implication = parsed.get("policy_implication", "")

            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "Received insight narration from LLM",
                {"llm_response": result},
            )

        except Exception as e:
            # Template fallback
            headline = f"{evidence['metric']} changed {evidence['percentage_change']:.1%} from {evidence['year_start']} to {evidence['year_end']}"
            policy_implication = "Further analysis required to determine policy implications."
            result = {"error": str(e)}
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "LLM narration failed; using fallback template",
                {"error": str(e)},
            )

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
            llm_response=result if isinstance(result, dict) else None,
        )
