"""
Unit tests for agent transparency features (Task 310).

Tests:
- Discovery step truncation info
- Plan step builder includes dataset_details
- Extraction observation payload includes source links
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.plan import (
    DiscoveryStep,
    DiscoveredDataset,
    DataSource,
    Intent,
    TimeRange,
    Plan,
    ExtractionStep,
    AnalysisStep,
    Guardrails,
)
from app.connectors.base import DatasetCandidate


class TestDiscoveryStepSchema:
    """Tests for DiscoveryStep schema with truncation fields."""

    def test_discovery_step_with_truncation_info(self):
        """Test DiscoveryStep includes truncation fields."""
        step = DiscoveryStep(
            source="data.gov.sg",
            query="employment",
            notes="Found 10+ candidate datasets (capped at 10)",
            returned_count=10,
            total_count=None,
            is_truncated=True,
            limit=10,
        )

        assert step.source == "data.gov.sg"
        assert step.returned_count == 10
        assert step.total_count is None
        assert step.is_truncated is True
        assert step.limit == 10

    def test_discovery_step_without_truncation(self):
        """Test DiscoveryStep when results are not truncated."""
        step = DiscoveryStep(
            source="singstat",
            query="gdp",
            notes="Found 5 candidate datasets",
            returned_count=5,
            total_count=5,
            is_truncated=False,
            limit=10,
        )

        assert step.returned_count == 5
        assert step.total_count == 5
        assert step.is_truncated is False

    def test_discovery_step_defaults(self):
        """Test DiscoveryStep default values for backward compatibility."""
        step = DiscoveryStep(
            source="data.gov.sg",
            query="test",
        )

        assert step.notes == ""
        assert step.returned_count is None
        assert step.total_count is None
        assert step.is_truncated is False
        assert step.limit is None


class TestPlanStepBuilder:
    """Tests for _build_plan_steps_from_structured including dataset_details."""

    def test_build_plan_steps_includes_dataset_details(self):
        """Test that plan steps include dataset_details with names and scores."""
        from app.api.routes.runs import _build_plan_steps_from_structured

        # Create a mock structured plan
        plan = Plan(
            intent=Intent(
                question="What are employment trends?",
                time_range=TimeRange(start="2020", end="2023"),
                entities=["Singapore"],
                metrics=["employment"],
            ),
            sources=[
                DataSource(
                    name="data.gov.sg",
                    datasets=[
                        DiscoveredDataset(
                            id="d_123456",
                            title="Employment Statistics",
                            score=0.85,
                            discovered_by="data.gov.sg_discovery",
                        ),
                        DiscoveredDataset(
                            id="d_789012",
                            title="Labour Force Survey",
                            score=0.72,
                            discovered_by="data.gov.sg_discovery",
                        ),
                    ],
                    format="api",
                ),
            ],
            extract_steps=[],
            analysis_steps=[],
            guardrails=Guardrails(),
            approved=False,
        )

        steps = _build_plan_steps_from_structured(plan)

        # Find the fetch_datasets step
        fetch_step = next(s for s in steps if s["action"] == "fetch_datasets")

        # Check that dataset_details is included
        assert "dataset_details" in fetch_step["inputs"]
        dataset_details = fetch_step["inputs"]["dataset_details"]

        assert len(dataset_details) == 2

        # Check first dataset details
        assert dataset_details[0]["id"] == "d_123456"
        assert dataset_details[0]["name"] == "Employment Statistics"
        assert dataset_details[0]["source"] == "data.gov.sg"
        assert dataset_details[0]["score"] == 0.85

        # Check second dataset details
        assert dataset_details[1]["id"] == "d_789012"
        assert dataset_details[1]["name"] == "Labour Force Survey"
        assert dataset_details[1]["source"] == "data.gov.sg"
        assert dataset_details[1]["score"] == 0.72

    def test_build_plan_steps_backward_compatible(self):
        """Test that datasets list is still included for backward compatibility."""
        from app.api.routes.runs import _build_plan_steps_from_structured

        plan = Plan(
            intent=Intent(
                question="Test query",
                time_range=TimeRange(start="2020", end="2023"),
            ),
            sources=[
                DataSource(
                    name="singstat",
                    datasets=[
                        DiscoveredDataset(
                            id="M123",
                            title="Test Dataset",
                            score=0.9,
                            discovered_by="singstat_discovery",
                        ),
                    ],
                    format="api",
                ),
            ],
            extract_steps=[],
            analysis_steps=[],
        )

        steps = _build_plan_steps_from_structured(plan)
        fetch_step = next(s for s in steps if s["action"] == "fetch_datasets")

        # Both datasets (old) and dataset_details (new) should be present
        assert "datasets" in fetch_step["inputs"]
        assert "dataset_details" in fetch_step["inputs"]
        assert fetch_step["inputs"]["datasets"] == ["M123"]


class TestExtractionPayload:
    """Tests for extraction observation payload with source links."""

    def test_extraction_payload_includes_source_uri(self):
        """Test that extraction events include source_uri and portal_url."""
        from app.agents.extraction import ExtractionAgent
        from app.schemas.plan import Plan, ExtractionStep

        # We'll test the payload structure by checking what gets emitted
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        # Create mocks
        mock_db = MagicMock()
        mock_data_service = MagicMock()

        # Mock dataset with provenance
        mock_provenance = MagicMock()
        mock_provenance.source_uri = "https://data.gov.sg/datasets/d_test/view"

        mock_dataset = MagicMock()
        mock_dataset.id = 1
        mock_dataset.name = "Test Dataset"
        mock_dataset.row_count = 100
        mock_dataset.column_count = 5
        mock_dataset.status = "validated"
        mock_dataset.validation_reports = []
        mock_dataset.provenance = mock_provenance

        mock_data_service.ingest_dataset.return_value = mock_dataset

        with patch.object(ExtractionAgent, "__init__", lambda self, db, event_sink=None: None):
            agent = ExtractionAgent.__new__(ExtractionAgent)
            agent.db = mock_db
            agent.data_service = mock_data_service
            agent.event_sink = capture_event
            agent.connectors = {
                "data.gov.sg": MagicMock(),
            }

            # Create a test extraction step
            step = ExtractionStep(
                source="data.gov.sg",
                dataset_ref="d_test123",
                notes="Test extraction",
            )

            # Execute extraction
            result = agent._execute_extraction_step("test-run-id", step)

        # Find the observation event
        obs_events = [e for e in events_captured if e.phase.value == "observation"]
        assert len(obs_events) >= 1

        # Check that the observation payload includes links
        obs_payload = obs_events[-1].payload
        assert "source_uri" in obs_payload
        assert "portal_url" in obs_payload
        assert obs_payload["portal_url"] == "https://data.gov.sg/datasets/d_test123/view"
        assert "dataset_name" in obs_payload
        assert "dataset_ref" in obs_payload

    def test_portal_url_for_singstat(self):
        """Test correct portal URL generation for SingStat source."""
        from app.agents.extraction import ExtractionAgent
        from app.schemas.plan import ExtractionStep

        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        mock_db = MagicMock()
        mock_data_service = MagicMock()

        mock_dataset = MagicMock()
        mock_dataset.id = 2
        mock_dataset.name = "SingStat Dataset"
        mock_dataset.row_count = 50
        mock_dataset.column_count = 3
        mock_dataset.status = "validated"
        mock_dataset.validation_reports = []
        mock_dataset.provenance = None

        mock_data_service.ingest_dataset.return_value = mock_dataset

        with patch.object(ExtractionAgent, "__init__", lambda self, db, event_sink=None: None):
            agent = ExtractionAgent.__new__(ExtractionAgent)
            agent.db = mock_db
            agent.data_service = mock_data_service
            agent.event_sink = capture_event
            agent.connectors = {
                "singstat": MagicMock(),
            }

            step = ExtractionStep(
                source="singstat",
                dataset_ref="M182931",
                notes="Test SingStat extraction",
            )

            result = agent._execute_extraction_step("test-run-id", step)

        obs_events = [e for e in events_captured if e.phase.value == "observation"]
        obs_payload = obs_events[-1].payload

        assert obs_payload["portal_url"] == "https://tablebuilder.singstat.gov.sg/table/M182931"


class TestCoordinatorDiscoveryMessages:
    """Tests for coordinator discovery message formatting."""

    def test_truncated_discovery_message(self):
        """Test discovery message when results are truncated."""
        from app.agents.coordinator import CoordinatorAgent
        from app.schemas.plan import Intent, TimeRange

        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        # Create mock connector that returns more than limit
        mock_connector = MagicMock()
        mock_connector.discover.return_value = [
            DatasetCandidate(
                name=f"Dataset {i}",
                description=f"Description {i}",
                source_type="data.gov.sg",
                format="api",
                uri=f"d_{i}",
                metadata={},
            )
            for i in range(11)  # 11 results to trigger truncation
        ]

        with patch.object(CoordinatorAgent, "__init__", lambda self, llm_router=None, db=None, event_sink=None: None):
            agent = CoordinatorAgent.__new__(CoordinatorAgent)
            agent.db = MagicMock()
            agent.event_sink = capture_event
            agent._connectors = {"data.gov.sg": mock_connector}

            intent = Intent(
                question="What are employment trends?",
                time_range=TimeRange(start="2020", end="2023"),
                entities=["employment"],
                metrics=["count"],
            )

            discovery_results, discovery_steps = agent._run_discovery(
                run_id="test-run",
                intent=intent,
                user_constraints={"allowed_sources": ["data.gov.sg"]},
            )

        # Check the discovery step has truncation info
        assert len(discovery_steps) == 1
        step = discovery_steps[0]
        assert step.is_truncated is True
        assert step.returned_count == 10
        assert "capped" in step.notes.lower()

        # Check the observation event message
        obs_events = [e for e in events_captured if e.phase.value == "observation" and "Found" in e.message]
        assert len(obs_events) >= 1
        assert "10+" in obs_events[-1].message or "capped" in obs_events[-1].message.lower()

    def test_non_truncated_discovery_message(self):
        """Test discovery message when results are not truncated."""
        from app.agents.coordinator import CoordinatorAgent
        from app.schemas.plan import Intent, TimeRange

        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        # Create mock connector that returns fewer than limit
        mock_connector = MagicMock()
        mock_connector.discover.return_value = [
            DatasetCandidate(
                name=f"Dataset {i}",
                description=f"Description {i}",
                source_type="data.gov.sg",
                format="api",
                uri=f"d_{i}",
                metadata={},
            )
            for i in range(5)  # Only 5 results
        ]

        with patch.object(CoordinatorAgent, "__init__", lambda self, llm_router=None, db=None, event_sink=None: None):
            agent = CoordinatorAgent.__new__(CoordinatorAgent)
            agent.db = MagicMock()
            agent.event_sink = capture_event
            agent._connectors = {"data.gov.sg": mock_connector}

            intent = Intent(
                question="What are GDP trends?",
                time_range=TimeRange(start="2020", end="2023"),
                entities=["gdp"],
                metrics=["value"],
            )

            discovery_results, discovery_steps = agent._run_discovery(
                run_id="test-run",
                intent=intent,
                user_constraints={"allowed_sources": ["data.gov.sg"]},
            )

        # Check the discovery step does NOT have truncation
        step = discovery_steps[0]
        assert step.is_truncated is False
        assert step.returned_count == 5
        assert step.total_count == 5
        assert "capped" not in step.notes.lower()

        # Check the observation event
        obs_events = [e for e in events_captured if e.phase.value == "observation" and "Found" in e.message]
        obs_payload = obs_events[-1].payload
        assert obs_payload["is_truncated"] is False
        assert obs_payload["returned_count"] == 5


class TestCoordinatorRowEstimationOptimization:
    """Tests for reduced planning-time row estimation API calls."""

    def test_select_datasets_caps_row_estimation_api_calls(self, monkeypatch):
        """Coordinator should cap expensive estimate_rows API calls."""
        from app.agents.coordinator import CoordinatorAgent
        from app.schemas.plan import Intent, TimeRange
        from app.core.config import settings

        mock_connector = MagicMock()
        mock_connector.estimate_rows.return_value = 500

        candidates = [
            DatasetCandidate(
                name=f"Dataset {i}",
                description="Employment dataset",
                source_type="data.gov.sg",
                format="api",
                uri=f"d_{i}",
                metadata={},
            )
            for i in range(6)
        ]

        with patch.object(CoordinatorAgent, "__init__", lambda self, llm_router=None, db=None, event_sink=None: None):
            agent = CoordinatorAgent.__new__(CoordinatorAgent)
            agent.db = MagicMock()
            agent.event_sink = lambda *_: None
            agent._connectors = {"data.gov.sg": mock_connector}
            agent._emit_event = lambda *args, **kwargs: None

            # Force deterministic ranking path for stable test behavior
            agent._rank_with_llm = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("skip llm"))

            monkeypatch.setattr(settings, "selection_row_estimate_max_api_calls", 2)
            monkeypatch.setattr(settings, "selection_max_total_rows", 100000)
            monkeypatch.setattr(settings, "selection_max_rows_per_dataset", 50000)
            monkeypatch.setattr(settings, "pre_filter_max_candidates", 200)
            monkeypatch.setattr(settings, "row_estimate_default", 1000)

            intent = Intent(
                question="What are employment trends?",
                time_range=TimeRange(start="2020", end="2024"),
                entities=["employment"],
                metrics=["count"],
            )

            sources = agent._select_datasets(
                run_id="test-run",
                intent=intent,
                discovery_results={"data.gov.sg": candidates},
            )

        assert mock_connector.estimate_rows.call_count == 2
        assert len(sources) == 1
        assert len(sources[0].datasets) > 0

    def test_select_datasets_uses_metadata_row_estimate_before_api(self, monkeypatch):
        """Coordinator should prefer metadata estimate and avoid API call."""
        from app.agents.coordinator import CoordinatorAgent
        from app.schemas.plan import Intent, TimeRange
        from app.core.config import settings

        mock_connector = MagicMock()
        mock_connector.estimate_rows.return_value = 9999

        candidate = DatasetCandidate(
            name="Employment by Sector",
            description="Employment dataset",
            source_type="data.gov.sg",
            format="api",
            uri="d_meta_1",
            metadata={"estimated_rows": 3210},
        )

        with patch.object(CoordinatorAgent, "__init__", lambda self, llm_router=None, db=None, event_sink=None: None):
            agent = CoordinatorAgent.__new__(CoordinatorAgent)
            agent.db = MagicMock()
            agent.event_sink = lambda *_: None
            agent._connectors = {"data.gov.sg": mock_connector}
            agent._emit_event = lambda *args, **kwargs: None
            agent._rank_with_llm = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("skip llm"))

            monkeypatch.setattr(settings, "selection_row_estimate_max_api_calls", 0)
            monkeypatch.setattr(settings, "selection_max_total_rows", 100000)
            monkeypatch.setattr(settings, "selection_max_rows_per_dataset", 50000)
            monkeypatch.setattr(settings, "pre_filter_max_candidates", 200)

            intent = Intent(
                question="Employment trend",
                time_range=TimeRange(start="2020", end="2024"),
                entities=["employment"],
                metrics=["count"],
            )

            sources = agent._select_datasets(
                run_id="test-run",
                intent=intent,
                discovery_results={"data.gov.sg": [candidate]},
            )

        assert mock_connector.estimate_rows.call_count == 0
        assert len(sources) == 1
        assert len(sources[0].datasets) == 1
        assert sources[0].datasets[0].estimated_rows == 3210
