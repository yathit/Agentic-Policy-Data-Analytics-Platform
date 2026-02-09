"""Unit tests for analytics trend time-range fallback behavior."""

from unittest.mock import MagicMock, patch

import pandas as pd

from app.agents.analytics import AnalyticsAgent
from app.core.config import settings
from app.schemas.plan import AnalysisStep, Intent, Plan, TimeRange


def test_trend_uses_unfiltered_data_when_time_filter_returns_no_rows(monkeypatch):
    """Trend analysis should fall back to unfiltered data when filter yields no rows."""
    events_captured = []

    def capture_event(event):
        events_captured.append(event)

    plan = Plan(
        intent=Intent(
            question="Test question",
            time_range=TimeRange(start="2022", end="2023"),
            entities=[],
            metrics=["value"],
        ),
        sources=[],
        extract_steps=[],
        analysis_steps=[AnalysisStep(type="trend", params={"metric": "value"})],
    )

    step = AnalysisStep(type="trend", params={"metric": "value"})
    dataset = MagicMock()
    dataset.id = 1
    dataset.source_type = "data.gov.sg"
    dataset.name = "data.gov.sg_demo"
    dataset.provenance = None

    with patch.object(AnalyticsAgent, "__init__", lambda self, db, llm_router=None, event_sink=None: None):
        agent = AnalyticsAgent.__new__(AnalyticsAgent)
        agent.db = MagicMock()
        agent.event_sink = capture_event
        agent.llm_router = MagicMock()
        agent.system_prompt = ""
        agent.connectors = {}
        agent._select_dataset_for_step = MagicMock(return_value=dataset)
        agent._load_dataset_dataframe = MagicMock(
            return_value=pd.DataFrame({"year": [2018, 2019, 2020], "value": [10, 20, 30]})
        )
        agent._generate_insight = MagicMock(return_value=MagicMock())

        monkeypatch.setattr(settings, "analytics_bypass_time_filter", False)

        result = agent._compute_trend(
            run_id="test-run-id",
            datasets=[dataset],
            step=step,
            approved_plan=plan,
        )

    assert result is not None
    assert result["table"].data["years"] == [2018, 2019, 2020]
    assert any(
        "using unfiltered data for demo" in event.message.lower()
        for event in events_captured
    )
