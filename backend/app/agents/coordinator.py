"""
Coordinator Agent - Translates user queries into structured execution plans.

Responsibilities:
- Parse user intent from natural language query
- Propose data sources and extraction steps
- Create structured analysis plan
- Emit ReAct events for transparency
- Stop at approval gate (HITL)

Task 320: Large-pool discovery with LLM ranking and row-budget selection.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

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
        self.ranking_prompt_template = self._load_ranking_prompt()
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

    def _load_ranking_prompt(self) -> str:
        """Load dataset ranking prompt template from file."""
        prompt_path = Path(__file__).parents[2] / ".llm" / "prompts" / "dataset_ranking.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            # Fallback to inline template if file not found
            logger.warning(f"Dataset ranking prompt not found at '{prompt_path}', using inline fallback")
            return """Rank these dataset candidates by relevance to the user query.

User Query: "{question}"
Entities of interest: {entities}
Metrics of interest: {metrics}

Candidates:
{candidates}

For each candidate, provide:
- id: The dataset ID (must match exactly from the list above)
- relevance_score: 0.0 to 1.0 (higher = more relevant to the query)
- reason: Brief explanation of why this is or isn't relevant (1 sentence)
- confidence: "high", "medium", or "low"

Respond with JSON:
{{"rankings": [{{"id": "...", "relevance_score": 0.85, "reason": "...", "confidence": "high"}}]}}
"""

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

        # Task 320: Use configurable discovery limit from settings
        discovery_limit = settings.discovery_max_candidates

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

                # Request limit+1 to detect if results are truncated
                request_limit = discovery_limit + 1

                # Pass db session for connectors that need it (e.g., data.gov.sg)
                if source_name == "data.gov.sg" and self.db is not None:
                    candidates = connector.discover(query, db=self.db, limit=request_limit)
                else:
                    candidates = connector.discover(query)

                # Determine if results are truncated
                is_truncated = len(candidates) > discovery_limit
                total_count = len(candidates) if not is_truncated else None
                returned_count = min(len(candidates), discovery_limit)

                # Trim to actual limit
                if is_truncated:
                    candidates = candidates[:discovery_limit]

                discovery_results[source_name] = candidates

                # Build observation message with truncation info
                if is_truncated:
                    obs_message = f"Found {returned_count}+ datasets from {source_name} (results capped at {discovery_limit})"
                    notes = f"Found {returned_count}+ candidate datasets (capped at {discovery_limit})"
                else:
                    obs_message = f"Found {returned_count} datasets from {source_name}"
                    notes = f"Found {returned_count} candidate datasets"

                # Record discovery step with truncation info
                discovery_steps.append(
                    DiscoveryStep(
                        source=source_name,
                        query=query,
                        notes=notes,
                        returned_count=returned_count,
                        total_count=total_count,
                        is_truncated=is_truncated,
                        limit=discovery_limit,
                    )
                )

                # Build dataset preview for payload
                dataset_preview = [
                    {
                        "id": c.uri,
                        "name": c.name,
                        "source": source_name,
                        "score": c.metadata.get("score"),
                    }
                    for c in candidates[:5]
                ]

                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    obs_message,
                    {
                        "source": source_name,
                        "returned_count": returned_count,
                        "total_count": total_count,
                        "is_truncated": is_truncated,
                        "limit": discovery_limit,
                        "datasets": dataset_preview,
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
        Select datasets using two-stage ranking and row-budget policy.

        Task 320: Replaces fixed top-N selection with:
        - Stage A: Deterministic pre-filter
        - Stage B: LLM ranking (with fallback)
        - Selection: Row-budget based

        Args:
            run_id: Run identifier
            intent: Parsed intent
            discovery_results: Discovery results by source
            user_constraints: Optional constraints

        Returns:
            List of DataSource with discovered datasets
        """
        # Flatten all candidates with source info
        all_candidates: List[Tuple[DatasetCandidate, str]] = []
        for source_name, candidates in discovery_results.items():
            for c in candidates:
                c.metadata["source"] = source_name
                all_candidates.append((c, source_name))

        if not all_candidates:
            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                "No candidates found for selection",
                {"candidate_count": 0},
            )
            return []

        total_candidates = len(all_candidates)

        # Stage A: Deterministic pre-filter
        scored = [(c, source, self._score_dataset(c, intent)) for c, source in all_candidates]
        scored.sort(key=lambda x: x[2], reverse=True)
        pre_filtered = scored[: settings.pre_filter_max_candidates]
        pre_filter_count = len(pre_filtered)

        self._emit_event(
            run_id,
            EventPhase.ACTION,
            f"Pre-filtered to {pre_filter_count} candidates for LLM ranking",
            {
                "candidate_pool_size": total_candidates,
                "pre_filter_count": pre_filter_count,
                "pre_filter_max": settings.pre_filter_max_candidates,
            },
        )

        # Stage B: LLM ranking
        ranking_method = "deterministic"
        llm_fallback_reason: Optional[str] = None
        llm_ranked_count = 0

        try:
            llm_ranked = self._rank_with_llm(
                run_id,
                [c for c, _, _ in pre_filtered],
                intent,
            )

            if llm_ranked is not None and len(llm_ranked) > 0:
                ranking_method = "llm"
                llm_ranked_count = len(llm_ranked)
                # Build ranked list with source info
                candidate_to_source = {c.uri: source for c, source, _ in pre_filtered}
                ranked_candidates = [
                    (c, score, reason, conf, candidate_to_source.get(c.uri, "unknown"))
                    for c, score, reason, conf in llm_ranked
                ]

                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    f"LLM ranked {llm_ranked_count} candidates",
                    {"llm_ranked_count": llm_ranked_count, "ranking_method": "llm"},
                )
            else:
                raise ValueError("LLM ranking returned empty results")

        except Exception as e:
            llm_fallback_reason = str(e)
            logger.warning(f"LLM ranking failed, using deterministic fallback: {e}")

            self._emit_event(
                run_id,
                EventPhase.OBSERVATION,
                f"LLM ranking failed, using deterministic fallback",
                {"fallback_reason": str(e), "ranking_method": "deterministic"},
            )

            # Use deterministic scores as fallback
            ranked_candidates = [
                (c, score, "", "medium", source)
                for c, source, score in pre_filtered
            ]

        # Row-budget selection
        selected: List[Tuple[DatasetCandidate, float, str, str, int, str]] = []
        total_rows = 0
        max_total = settings.selection_max_total_rows
        max_per_dataset = settings.selection_max_rows_per_dataset

        for candidate, score, reason, confidence, source_name in ranked_candidates:
            connector = self._connectors.get(source_name)

            # Get row estimate
            if connector and hasattr(connector, "estimate_rows"):
                try:
                    estimated_rows = connector.estimate_rows(candidate.uri)
                except Exception:
                    estimated_rows = settings.row_estimate_default
            else:
                estimated_rows = settings.row_estimate_default

            # Apply per-dataset cap
            estimated_rows = min(estimated_rows, max_per_dataset)

            # Check budget
            if total_rows + estimated_rows <= max_total:
                selected.append(
                    (candidate, score, reason, confidence, estimated_rows, source_name)
                )
                total_rows += estimated_rows

        self._emit_event(
            run_id,
            EventPhase.OBSERVATION,
            f"Selected {len(selected)} datasets within {total_rows} row budget",
            {
                "selected_dataset_count": len(selected),
                "selected_total_estimated_rows": total_rows,
                "selection_budget": max_total,
                "ranking_method_used": ranking_method,
                "llm_ranked_count": llm_ranked_count,
                "llm_fallback_reason": llm_fallback_reason,
            },
        )

        # Group by source
        sources_map: Dict[str, List[DiscoveredDataset]] = {}
        for candidate, score, reason, confidence, est_rows, source in selected:
            if source not in sources_map:
                sources_map[source] = []

            sources_map[source].append(
                DiscoveredDataset(
                    id=candidate.uri,
                    title=candidate.name,
                    score=round(score, 2),  # Legacy field
                    discovered_by=f"{source}_discovery",
                    # Task 320 new fields
                    relevance_score=round(score, 2),
                    reason=reason if reason else None,
                    confidence=confidence if confidence else None,
                    estimated_rows=est_rows,
                    ranking_method=ranking_method,
                )
            )

        return [
            DataSource(name=source, datasets=datasets, format="api")
            for source, datasets in sources_map.items()
        ]

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

    def _build_ranking_prompt(
        self,
        candidates: List[DatasetCandidate],
        intent: Intent,
    ) -> str:
        """
        Build LLM ranking prompt for a batch of candidates.

        Task 320: Used for Stage B LLM ranking.
        Loads prompt template from .llm/prompts/dataset_ranking.md

        Args:
            candidates: Candidates to rank
            intent: User intent for context

        Returns:
            Prompt string for LLM
        """
        candidate_json = [
            {
                "id": c.uri,
                "title": c.name,
                "description": c.description[:200] if c.description else "",
            }
            for c in candidates
        ]

        return self.ranking_prompt_template.format(
            question=intent.question,
            entities=intent.entities,
            metrics=intent.metrics,
            candidates=json.dumps(candidate_json, indent=2),
        )

    def _rank_with_llm(
        self,
        run_id: str,
        candidates: List[DatasetCandidate],
        intent: Intent,
    ) -> Optional[List[Tuple[DatasetCandidate, float, str, str]]]:
        """
        Rank candidates using LLM in parallel batches.

        Task 320: Stage B ranking with parallel batch processing.

        Args:
            run_id: Run identifier
            candidates: Pre-filtered candidates to rank
            intent: User intent for context

        Returns:
            List of (candidate, relevance_score, reason, confidence) tuples,
            or None if ranking failed (triggers deterministic fallback)
        """
        batch_size = settings.llm_ranking_batch_size
        max_parallel = settings.llm_ranking_max_parallel
        timeout_s = settings.llm_ranking_timeout_ms / 1000

        # Split candidates into batches
        batches = [
            candidates[i : i + batch_size]
            for i in range(0, len(candidates), batch_size)
        ]

        schema = {
            "type": "object",
            "properties": {
                "rankings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "relevance_score": {"type": "number"},
                            "reason": {"type": "string"},
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                        },
                        "required": ["id", "relevance_score"],
                    },
                }
            },
        }

        def rank_batch(batch: List[DatasetCandidate]) -> Optional[dict]:
            """Rank a single batch with LLM."""
            try:
                prompt = self._build_ranking_prompt(batch, intent)
                return self.llm_router.complete(
                    task_name="dataset_ranking",
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    schema=schema,
                    temperature=0.3,
                    timeout_s=int(timeout_s),
                )
            except Exception as e:
                logger.warning(f"LLM ranking batch failed: {e}")
                return None

        # Run batches in parallel with ThreadPoolExecutor
        results: List[Tuple[List[DatasetCandidate], Optional[dict]]] = []

        try:
            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                future_to_batch = {
                    executor.submit(rank_batch, batch): batch for batch in batches
                }

                for future in as_completed(future_to_batch, timeout=timeout_s * 2):
                    batch = future_to_batch[future]
                    try:
                        result = future.result(timeout=timeout_s)
                        results.append((batch, result))
                    except Exception as e:
                        logger.warning(f"LLM ranking batch exception: {e}")
                        results.append((batch, None))

        except Exception as e:
            logger.error(f"LLM ranking parallel execution failed: {e}")
            return None

        # Check if any batch failed completely
        if all(r[1] is None for r in results):
            return None

        # Merge results
        ranked: List[Tuple[DatasetCandidate, float, str, str]] = []
        for batch, result in results:
            if result is None:
                continue

            batch_map = {c.uri: c for c in batch}
            rankings = result.get("rankings", [])

            for r in rankings:
                candidate_id = r.get("id")
                if candidate_id and candidate_id in batch_map:
                    ranked.append(
                        (
                            batch_map[candidate_id],
                            float(r.get("relevance_score", 0.0)),
                            r.get("reason", ""),
                            r.get("confidence", "medium"),
                        )
                    )

        # Sort by relevance score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked if ranked else None

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
