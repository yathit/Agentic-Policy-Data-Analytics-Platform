"""
Extraction Agent - Fetches, parses, validates, and cleans datasets.

Responsibilities:
- Fetch data from approved sources only
- Parse raw data into DataFrames
- Validate quality and completeness
- Clean and normalize data
- Track full provenance
- Emit quality reports
"""

import time
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from sqlalchemy.orm import Session

from app.schemas.events import AgentEvent, EventPhase, AgentType, event_store
from app.schemas.plan import Plan, ExtractionStep
from app.connectors.base import BaseConnector, QualityReport
from app.connectors import DataGovV2Connector, SingStatConnector, InternalConnector
from app.services.data_service import DataService
from app.models.dataset import Dataset


class ExtractionResult:
    """Result of extraction process."""

    def __init__(
        self,
        dataset: Optional[Dataset] = None,
        success: bool = False,
        error: Optional[str] = None,
    ):
        self.dataset = dataset
        self.success = success
        self.error = error


class ExtractionAgent:
    """
    Extraction Agent for deterministic data fetching and cleaning.

    Features:
    - Bounded authority (only approved sources)
    - Quality validation and reporting
    - Automatic retry with backoff
    - Full provenance tracking
    - No LLM usage (deterministic pipeline)
    """

    def __init__(self, db: Session, event_sink: Optional[Callable[[AgentEvent], None]] = None):
        """
        Initialize Extraction Agent.

        Args:
            db: Database session for persistence
        """
        self.db = db
        self.data_service = DataService(db)
        self.system_prompt = self._load_system_prompt()
        self.event_sink = event_sink

        # Initialize connectors
        self.connectors: Dict[str, BaseConnector] = {
            "data.gov.sg": DataGovV2Connector(),
            "singstat": SingStatConnector(),
            "internal": InternalConnector(),
        }

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parents[2].joinpath(".llm", "prompts", "extraction.md")
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            return "You are an Extraction Agent for policy data analytics."

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
            agent=AgentType.EXTRACTION,
            phase=phase,
            message=message,
            payload=payload or {},
        )
        if self.event_sink:
            self.event_sink(event)
        else:
            event_store.emit(event)

    def run_extraction(
        self,
        run_id: str,
        approved_plan: Plan,
        abort_check: Optional[Callable[[], bool]] = None,
    ) -> List[ExtractionResult]:
        """
        Execute all extraction steps from approved plan.

        Args:
            run_id: Run identifier
            approved_plan: User-approved plan

        Returns:
            List of extraction results (datasets or errors)
        """
        if not approved_plan.approved:
            raise ValueError("Cannot execute unapproved plan")

        self._emit_event(
            run_id,
            EventPhase.REASON,
            f"Starting extraction of {len(approved_plan.extract_steps)} datasets",
            {"step_count": len(approved_plan.extract_steps)},
        )

        results = []

        for step in approved_plan.extract_steps:
            if abort_check and abort_check():
                self._emit_event(
                    run_id,
                    EventPhase.DECISION,
                    "Extraction aborted by user",
                    {"status": "aborted"},
                )
                break
            result = self._execute_extraction_step(run_id, step)
            results.append(result)

        # Summary
        success_count = sum(1 for r in results if r.success)
        self._emit_event(
            run_id,
            EventPhase.DECISION,
            f"Extraction complete: {success_count}/{len(results)} successful",
            {"success_count": success_count, "total_count": len(results)},
        )

        return results

    def _execute_extraction_step(
        self, run_id: str, step: ExtractionStep
    ) -> ExtractionResult:
        """
        Execute single extraction step with retry logic.

        Args:
            run_id: Run identifier
            step: Extraction step from plan

        Returns:
            ExtractionResult with dataset or error
        """
        self._emit_event(
            run_id,
            EventPhase.REASON,
            f"Fetching dataset '{step.dataset_ref}' from '{step.source}'",
            {"source": step.source, "dataset_ref": step.dataset_ref},
        )

        # Verify source is approved
        connector = self.connectors.get(step.source)
        if not connector:
            error = f"Source '{step.source}' not in approved connectors"
            self._emit_event(
                run_id, EventPhase.OBSERVATION, error, {"error": error}
            )
            return ExtractionResult(success=False, error=error)

        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._emit_event(
                    run_id,
                    EventPhase.ACTION,
                    f"Attempt {attempt + 1}/{max_retries}: Calling {step.source} connector",
                    {"attempt": attempt + 1, "max_retries": max_retries},
                )

                # Use DataService for full ingestion pipeline
                dataset = self.data_service.ingest_dataset(
                    source_type=step.source,
                    dataset_ref=step.dataset_ref,
                    name=f"{step.source}_{step.dataset_ref}",
                )

                # Get validation report
                validation = (
                    dataset.validation_reports[0]
                    if dataset.validation_reports
                    else None
                )

                # Build provenance links for transparency
                provenance = dataset.provenance
                source_uri = provenance.source_uri if provenance else None
                portal_url = None

                # Generate portal URL for known sources
                if step.source == "data.gov.sg":
                    portal_url = f"https://data.gov.sg/datasets/{step.dataset_ref}/view"
                elif step.source == "singstat":
                    portal_url = f"https://tablebuilder.singstat.gov.sg/table/{step.dataset_ref}"

                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    f"Retrieved {dataset.row_count} rows, {dataset.column_count} columns. Status: {dataset.status}",
                    {
                        "dataset_id": dataset.id,
                        "dataset_name": dataset.name,
                        "dataset_ref": step.dataset_ref,
                        "row_count": dataset.row_count,
                        "column_count": dataset.column_count,
                        "status": dataset.status,
                        "completeness_score": (
                            validation.completeness_score if validation else None
                        ),
                        "source_uri": source_uri,
                        "portal_url": portal_url,
                    },
                )

                self._emit_event(
                    run_id,
                    EventPhase.DECISION,
                    f"Dataset {dataset.id} successfully extracted and validated",
                    {"dataset_id": dataset.id},
                )

                return ExtractionResult(dataset=dataset, success=True)

            except Exception as e:
                error_msg = str(e)
                self._emit_event(
                    run_id,
                    EventPhase.OBSERVATION,
                    f"Attempt {attempt + 1} failed: {error_msg}",
                    {"attempt": attempt + 1, "error": error_msg},
                )

                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    self._emit_event(
                        run_id,
                        EventPhase.ACTION,
                        f"Retrying after {wait_time}s backoff",
                        {"wait_time": wait_time},
                    )
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    self._emit_event(
                        run_id,
                        EventPhase.DECISION,
                        f"Extraction failed after {max_retries} attempts",
                        {"error": error_msg},
                    )
                    return ExtractionResult(success=False, error=error_msg)

        return ExtractionResult(success=False, error="Unknown error")

    def get_dataset_summary(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Generate summary of extracted dataset.

        Args:
            dataset: Dataset object

        Returns:
            Summary dictionary
        """
        validation = dataset.validation_reports[0] if dataset.validation_reports else None
        provenance = dataset.provenance

        return {
            "dataset_id": dataset.id,
            "name": dataset.name,
            "source_type": dataset.source_type,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "status": dataset.status,
            "quality_score": validation.completeness_score if validation else None,
            "warnings": validation.warnings if validation else [],
            "provenance": {
                "source_uri": provenance.source_uri if provenance else None,
                "retrieved_at": (
                    provenance.retrieved_at.isoformat() if provenance else None
                ),
            },
        }
