"""
Coordinator Agent - Translates user queries into structured execution plans.

Responsibilities:
- Parse user intent from natural language query
- Propose data sources and extraction steps
- Create structured analysis plan
- Emit ReAct events for transparency
- Stop at approval gate (HITL)
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable

from sqlalchemy.orm import Session

from app.llm.router import LLMRouter
from app.schemas.events import AgentEvent, EventPhase, AgentType, event_store
from app.schemas.plan import (
    Plan,
    Intent,
    TimeRange,
    DataSource,
    DiscoveredDataset,
    DiscoveryStep,
    ExtractionStep,
    AnalysisStep,
    Guardrails,
)
from app.connectors.singstat import SingStatConnector
from app.connectors.datagov import DataGovV2Connector
from app.connectors.base import DatasetCandidate


class CoordinatorAgent:
    """
    Coordinator Agent for query interpretation and plan generation.

    Creates structured execution plans with bounded autonomy:
    - Proposes sources and steps
    - Does NOT execute directly
    - Waits for approval before proceeding
    """

    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        db: Optional[Session] = None,
        event_sink: Optional[Callable[[AgentEvent], None]] = None,
    ):
        """
        Initialize Coordinator Agent.

        Args:
            llm_router: LLM router for API calls (creates default if None)
            db: Database session for discovery queries
            event_sink: Optional callback for event persistence (uses in-memory store if None)
        """
        self.llm_router = llm_router or LLMRouter()
        self.db = db
        self.event_sink = event_sink
        self.system_prompt = self._load_system_prompt()
        self._connectors = {
            "singstat": SingStatConnector(),
            "data.gov.sg": DataGovV2Connector(),
        }

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parents[2] / ".llm" / "prompts" / "coordinator.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            raise FileNotFoundError(
                f"Coordinator prompt file not found at '{prompt_path}'. "
                f"This file is required to define the agent's behavior and capabilities. "
                f"Please create the prompt file at '.llm/prompts/coordinator.md'."
            )

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
        if self.event_sink:
            self.event_sink(event)
        else:
            event_store.emit(event)

    def interpret_query(
        self,
        run_id: str,
        query_text: str,
        user_constraints: Optional[Dict[str, Any]] = None,
        discovery_hints: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """
        Interpret user query and generate execution plan.

        Steps:
        1. Parse intent (entities, metrics, time range)
        2. Run dataset discovery on connectors
        3. Select best-fit datasets based on relevance
        4. Propose extraction steps using discovered dataset IDs
        5. Propose analysis steps
        6. Return plan (not approved yet)

        Args:
            run_id: Unique run identifier
            query_text: User's natural language query
            user_constraints: Optional constraints (allowed sources, time limits, etc)
            discovery_hints: Optional hints for discovery (keywords, entities, metrics)

        Returns:
            Proposed Plan (approved=False)
        """
        self._emit_event(
            run_id,
            EventPhase.REASON,
            f"Interpreting user query: '{query_text}'",
            {"query": query_text, "constraints": user_constraints, "hints": discovery_hints},
        )

        # Step 1: Parse intent
        intent = self._parse_intent(run_id, query_text)

        self._emit_event(
            run_id,
            EventPhase.OBSERVATION,
            f"Identified intent: {intent.question}",
            {"intent": intent.model_dump()},
        )

        # Step 2: Run dataset discovery
        discovery_results, discovery_steps = self._run_discovery(
            run_id, intent, user_constraints, discovery_hints
        )

        self._emit_event(
            run_id,
            EventPhase.OBSERVATION,
            f"Discovery completed: found {sum(len(ds) for ds in discovery_results.values())} datasets",
            {"discovery_results": {k: len(v) for k, v in discovery_results.items()}},
        )

        # Step 3: Select best-fit datasets and create sources
        sources = self._select_datasets(run_id, intent, discovery_results, user_constraints)

        self._emit_event(
            run_id,
            EventPhase.ACTION,
            f"Selected {len(sources)} data sources with discovered datasets",
            {"sources": [s.model_dump() for s in sources]},
        )

        # Step 4: Create extraction steps from discovered datasets
        extract_steps = self._create_extraction_steps(run_id, intent, sources)

        # Step 5: Create analysis steps
        analysis_steps = self._create_analysis_steps(run_id, intent, sources, extract_steps)

        # Step 6: Assemble plan
        plan = Plan(
            intent=intent,
            sources=sources,
            discovery_steps=discovery_steps,
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

    def _build_discovery_query(
        self, intent: Intent, discovery_hints: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build discovery query from intent and hints.

        Args:
            intent: Parsed intent
            discovery_hints: Optional discovery hints

        Returns:
            Search query string
        """
        query_parts = []

        # Add entities from intent
        if intent.entities:
            query_parts.extend(intent.entities[:3])

        # Add metrics from intent
        if intent.metrics:
            query_parts.extend(intent.metrics[:2])

        # Add hints if provided
        if discovery_hints:
            if "keywords" in discovery_hints:
                query_parts.extend(discovery_hints["keywords"][:3])
            if "entities" in discovery_hints:
                query_parts.extend(discovery_hints["entities"][:2])

        # Fallback: extract key terms from question
        if not query_parts:
            words = intent.question.lower().split()
            stop_words = {"what", "how", "the", "is", "are", "has", "have", "been", "in", "of", "to", "from", "a", "an"}
            query_parts = [w for w in words if w not in stop_words and len(w) > 2][:4]

        return " ".join(query_parts)

    def _run_discovery(
        self,
        run_id: str,
        intent: Intent,
        user_constraints: Optional[Dict[str, Any]] = None,
        discovery_hints: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, list[DatasetCandidate]], list[DiscoveryStep]]:
        """
        Run dataset discovery on configured connectors.

        Args:
            run_id: Run identifier
            intent: Parsed intent
            user_constraints: Optional constraints
            discovery_hints: Optional discovery hints

        Returns:
            Tuple of (discovery_results by source, discovery_steps)
        """
        discovery_results: Dict[str, list[DatasetCandidate]] = {}
        discovery_steps: list[DiscoveryStep] = []

        # Determine which sources to query
        allowed_sources = ["singstat", "data.gov.sg"]
        if user_constraints and "allowed_sources" in user_constraints:
            allowed_sources = user_constraints["allowed_sources"]

        # Build discovery query
        query = self._build_discovery_query(intent, discovery_hints)

        self._emit_event(
            run_id,
            EventPhase.ACTION,
            f"Running dataset discovery with query: '{query}'",
            {"query": query, "sources": allowed_sources},
        )

        # Run discovery on each connector
        for source_name in allowed_sources:
            connector = self._connectors.get(source_name)
            if not connector:
                continue

            try:
                self._emit_event(
                    run_id,
                    EventPhase.ACTION,
                    f"Discovering datasets from {source_name}",
                    {"source": source_name, "query": query},
                )

                # Pass db session for connectors that need it (e.g., data.gov.sg)
                if source_name == "data.gov.sg" and self.db is not None:
                    candidates = connector.discover(query, db=self.db)
                else:
                    candidates = connector.discover(query)
                discovery_results[source_name] = candidates

                # Record discovery step
                discovery_steps.append(
                    DiscoveryStep(
                        source=source_name,
                        query=query,
                        notes=f"Found {len(candidates)} candidate datasets",
                    )
                )

                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    f"Found {len(candidates)} datasets from {source_name}",
                    {
                        "source": source_name,
                        "count": len(candidates),
                        "datasets": [
                            {"id": c.uri, "name": c.name} for c in candidates[:5]
                        ],
                    },
                )

            except Exception as e:
                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    f"Discovery failed for {source_name}: {str(e)}",
                    {"source": source_name, "error": str(e)},
                )
                discovery_results[source_name] = []

        return discovery_results, discovery_steps

    def _select_datasets(
        self,
        run_id: str,
        intent: Intent,
        discovery_results: Dict[str, list[DatasetCandidate]],
        user_constraints: Optional[Dict[str, Any]] = None,
    ) -> list[DataSource]:
        """
        Select best-fit datasets from discovery results.

        Args:
            run_id: Run identifier
            intent: Parsed intent
            discovery_results: Discovery results by source
            user_constraints: Optional constraints

        Returns:
            List of DataSource with discovered datasets
        """
        sources = []
        max_datasets_per_source = 3

        for source_name, candidates in discovery_results.items():
            if not candidates:
                continue

            # Score and select top candidates
            scored_datasets = []
            for candidate in candidates:
                score = self._score_dataset(candidate, intent)
                scored_datasets.append((candidate, score))

            # Sort by score descending
            scored_datasets.sort(key=lambda x: x[1], reverse=True)

            # Select top datasets
            selected = scored_datasets[:max_datasets_per_source]

            datasets = [
                DiscoveredDataset(
                    id=candidate.uri,
                    title=candidate.name,
                    score=round(score, 2),
                    discovered_by=f"{source_name}_discovery",
                )
                for candidate, score in selected
            ]

            if datasets:
                sources.append(
                    DataSource(
                        name=source_name,
                        datasets=datasets,
                        format="api",
                    )
                )

        return sources

    def _score_dataset(self, candidate: DatasetCandidate, intent: Intent) -> float:
        """
        Score a dataset candidate based on relevance to intent.

        Args:
            candidate: Dataset candidate
            intent: Parsed intent

        Returns:
            Relevance score (0-1)
        """
        score = 0.0
        name_lower = candidate.name.lower()
        desc_lower = candidate.description.lower()

        # Check entity matches
        for entity in intent.entities:
            entity_lower = entity.lower()
            if entity_lower in name_lower:
                score += 0.3
            elif entity_lower in desc_lower:
                score += 0.15

        # Check metric matches
        for metric in intent.metrics:
            metric_lower = metric.lower()
            if metric_lower in name_lower:
                score += 0.25
            elif metric_lower in desc_lower:
                score += 0.1

        # Bonus for time series data
        if candidate.metadata.get("is_time_series"):
            score += 0.1

        # Cap at 1.0
        return min(score, 1.0)

    def _create_extraction_steps(
        self, run_id: str, intent: Intent, sources: list[DataSource]
    ) -> list[ExtractionStep]:
        """
        Create extraction steps from discovered datasets.

        Args:
            run_id: Run identifier
            intent: Parsed intent
            sources: Data sources with discovered datasets

        Returns:
            List of extraction steps
        """
        steps = []

        for source in sources:
            for dataset in source.datasets:
                steps.append(
                    ExtractionStep(
                        source=source.name,
                        dataset_ref=dataset.id,
                        notes=f"Extract '{dataset.title}' (score: {dataset.score}) for: {intent.question[:50]}",
                    )
                )

        return steps

    def _create_analysis_steps(
        self,
        run_id: str,
        intent: Intent,
        sources: list[DataSource],
        extract_steps: list[ExtractionStep],
    ) -> list[AnalysisStep]:
        """
        Create analysis steps based on intent.

        Args:
            run_id: Run identifier
            intent: Parsed intent

        Returns:
            List of analysis steps
        """
        steps = []

        dataset_ref = None
        dataset_source = None
        if extract_steps:
            dataset_ref = extract_steps[0].dataset_ref
            dataset_source = extract_steps[0].source
        elif sources and sources[0].datasets:
            dataset_ref = sources[0].datasets[0].id
            dataset_source = sources[0].name

        # Default to trend analysis for time-based queries
        if intent.time_range:
            steps.append(
                AnalysisStep(
                    type="trend",
                    dataset_ref=dataset_ref,
                    source=dataset_source,
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
                        dataset_ref=dataset_ref,
                        source=dataset_source,
                        params={
                            "metric": intent.metrics[0] if intent.metrics else "value",
                            "compare_years": [start_year, end_year],
                        },
                    )
                )
        except:
            pass

        return steps
