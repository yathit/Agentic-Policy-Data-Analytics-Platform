"""
Coordinator Agent - Translates user queries into structured execution plans.

Responsibilities:
- Parse user intent from natural language query
- Propose data sources and extraction steps
- Create structured analysis plan
- Emit ReAct events for transparency
- Stop at approval gate (HITL)
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from app.llm.router import LLMRouter
from app.schemas.events import AgentEvent, EventPhase, AgentType, event_store
from app.schemas.plan import (
    Plan,
    Intent,
    TimeRange,
    DataSource,
    ExtractionStep,
    AnalysisStep,
    Guardrails,
)


class CoordinatorAgent:
    """
    Coordinator Agent for query interpretation and plan generation.

    Creates structured execution plans with bounded autonomy:
    - Proposes sources and steps
    - Does NOT execute directly
    - Waits for approval before proceeding
    """

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        """
        Initialize Coordinator Agent.

        Args:
            llm_router: LLM router for API calls (creates default if None)
        """
        self.llm_router = llm_router or LLMRouter()
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parents[3] / ".llm" / "prompts" / "coordinator.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            return "You are a Coordinator Agent for policy data analytics."

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
            agent=AgentType.COORDINATOR,
            phase=phase,
            message=message,
            payload=payload or {},
        )
        event_store.emit(event)

    def interpret_query(
        self, run_id: str, query_text: str, user_constraints: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """
        Interpret user query and generate execution plan.

        Steps:
        1. Parse intent (entities, metrics, time range)
        2. Identify candidate data sources
        3. Propose extraction steps
        4. Propose analysis steps
        5. Return plan (not approved yet)

        Args:
            run_id: Unique run identifier
            query_text: User's natural language query
            user_constraints: Optional constraints (allowed sources, time limits, etc)

        Returns:
            Proposed Plan (approved=False)
        """
        self._emit_event(
            run_id,
            EventPhase.REASON,
            f"Interpreting user query: '{query_text}'",
            {"query": query_text, "constraints": user_constraints},
        )

        # Step 1: Parse intent
        intent = self._parse_intent(run_id, query_text)

        self._emit_event(
            run_id,
            EventPhase.OBSERVATION,
            f"Identified intent: {intent.question}",
            {"intent": intent.model_dump()},
        )

        # Step 2: Propose data sources
        sources = self._propose_sources(run_id, intent, user_constraints)

        self._emit_event(
            run_id,
            EventPhase.ACTION,
            f"Proposing {len(sources)} data sources",
            {"sources": [s.model_dump() for s in sources]},
        )

        # Step 3: Create extraction steps
        extract_steps = self._create_extraction_steps(run_id, intent, sources)

        # Step 4: Create analysis steps
        analysis_steps = self._create_analysis_steps(run_id, intent)

        # Step 5: Assemble plan
        plan = Plan(
            intent=intent,
            sources=sources,
            extract_steps=extract_steps,
            analysis_steps=analysis_steps,
            guardrails=Guardrails(),
            approved=False,
        )

        self._emit_event(
            run_id,
            EventPhase.DECISION,
            "Plan created, awaiting approval",
            {"plan": plan.model_dump()},
        )

        return plan

    def _parse_intent(self, run_id: str, query_text: str) -> Intent:
        """
        Parse user query into structured intent.

        Args:
            run_id: Run identifier
            query_text: User query

        Returns:
            Structured Intent
        """
        self._emit_event(
            run_id,
            EventPhase.ACTION,
            "Calling LLM to parse intent",
            {"query": query_text},
        )

        # LLM prompt for intent parsing
        prompt = f"""
Given this user query, extract structured intent:

Query: "{query_text}"

Extract:
1. A clear, specific question
2. Time range (start year, end year)
3. Entities mentioned (countries, sectors, demographics)
4. Metrics of interest (employment, revenue, growth, etc)

Respond with JSON:
{{
  "question": "Rephrased clear question",
  "time_range": {{"start": "YYYY", "end": "YYYY"}},
  "entities": ["entity1", "entity2"],
  "metrics": ["metric1", "metric2"]
}}
"""

        schema = {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"},
                    },
                },
                "entities": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}},
            },
        }

        try:
            result = self.llm_router.complete(
                task_name="intent_parse",
                prompt=prompt,
                system_prompt=self.system_prompt,
                schema=schema,
                temperature=0.3,
            )

            return Intent(
                question=result["question"],
                time_range=TimeRange(**result["time_range"]),
                entities=result.get("entities", []),
                metrics=result.get("metrics", []),
            )

        except Exception as e:
            # Fallback: basic parsing
            return Intent(
                question=query_text,
                time_range=TimeRange(start="2020", end="2023"),
                entities=[],
                metrics=[],
            )

    def _propose_sources(
        self, run_id: str, intent: Intent, user_constraints: Optional[Dict[str, Any]]
    ) -> list[DataSource]:
        """
        Propose data sources based on intent.

        Args:
            run_id: Run identifier
            intent: Parsed intent
            user_constraints: Optional constraints

        Returns:
            List of proposed data sources
        """
        # For Singapore policy data, default sources
        allowed_sources = ["data.gov.sg", "singstat", "internal"]

        if user_constraints and "allowed_sources" in user_constraints:
            allowed_sources = user_constraints["allowed_sources"]

        # Simple heuristic: propose based on entities and metrics
        sources = []

        # Singstat for employment, demographics, economic data
        if any(m in ["employment", "population", "gdp", "economic"] for m in intent.metrics):
            sources.append(
                DataSource(
                    name="singstat",
                    datasets=["employment_by_industry", "economic_indicators"],
                    format="api",
                )
            )

        # data.gov.sg for tech sector, government programs
        if any(e in ["tech", "technology", "innovation"] for e in intent.entities):
            sources.append(
                DataSource(
                    name="data.gov.sg",
                    datasets=["tech_sector_statistics", "innovation_metrics"],
                    format="api",
                )
            )

        # Default to internal mock if no matches
        if not sources:
            sources.append(
                DataSource(
                    name="internal", datasets=["table:digital_sector_employment"], format="database"
                )
            )

        return sources

    def _create_extraction_steps(
        self, run_id: str, intent: Intent, sources: list[DataSource]
    ) -> list[ExtractionStep]:
        """
        Create extraction steps from proposed sources.

        Args:
            run_id: Run identifier
            intent: Parsed intent
            sources: Proposed sources

        Returns:
            List of extraction steps
        """
        steps = []

        for source in sources:
            for dataset in source.datasets:
                steps.append(
                    ExtractionStep(
                        source=source.name,
                        dataset_ref=dataset,
                        notes=f"Extract {dataset} for {intent.question}",
                    )
                )

        return steps

    def _create_analysis_steps(self, run_id: str, intent: Intent) -> list[AnalysisStep]:
        """
        Create analysis steps based on intent.

        Args:
            run_id: Run identifier
            intent: Parsed intent

        Returns:
            List of analysis steps
        """
        steps = []

        # Default to trend analysis for time-based queries
        if intent.time_range:
            steps.append(
                AnalysisStep(
                    type="trend",
                    params={
                        "metric": intent.metrics[0] if intent.metrics else "value",
                        "group_by": "year",
                        "time_period": "annual",
                    },
                )
            )

        # Add year-over-year if multi-year
        try:
            start_year = int(intent.time_range.start)
            end_year = int(intent.time_range.end)
            if end_year - start_year > 1:
                steps.append(
                    AnalysisStep(
                        type="yoy",
                        params={
                            "metric": intent.metrics[0] if intent.metrics else "value",
                            "compare_years": [start_year, end_year],
                        },
                    )
                )
        except:
            pass

        return steps
