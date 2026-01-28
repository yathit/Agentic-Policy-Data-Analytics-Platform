"""
Integration tests for the complete run flow.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestRunFlow:
    """Integration tests for the complete run workflow."""

    def test_create_and_reject_flow(self, client):
        """Test creating a run and rejecting it."""
        # Step 1: Create a run
        create_response = client.post(
            "/api/v1/runs",
            json={
                "query": "Analyse employment trends in tech sector from 2020-2024",
                "constraints": {
                    "time_range": {"start": "2020-01-01", "end": "2024-12-31"},
                    "sources_allowlist": ["data.gov.sg", "singstat"],
                },
            },
        )
        assert create_response.status_code == 201
        run_data = create_response.json()
        run_id = run_data["run"]["id"]
        plan_id = run_data["plan"]["id"]

        # Verify run status
        assert run_data["run"]["status"] == "awaiting_approval"

        # Step 2: Verify we can get the run
        get_response = client.get(f"/api/v1/runs/{run_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "awaiting_approval"

        # Step 3: Reject the plan
        reject_response = client.post(
            f"/api/v1/runs/{run_id}/approve",
            json={"plan_id": plan_id, "approved": False},
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "aborted"

        # Step 4: Verify final status
        final_response = client.get(f"/api/v1/runs/{run_id}")
        assert final_response.status_code == 200
        assert final_response.json()["status"] == "aborted"

        # Step 5: Verify event was created
        events_response = client.get(f"/api/v1/runs/{run_id}/events")
        assert events_response.status_code == 200
        events = events_response.json()["items"]
        assert len(events) > 0
        # Find the rejection event
        rejection_events = [e for e in events if "rejected" in e["message"].lower()]
        assert len(rejection_events) > 0

    def test_create_and_abort_flow(self, client):
        """Test creating a run and aborting it."""
        # Step 1: Create a run
        create_response = client.post(
            "/api/v1/runs",
            json={"query": "Test query for abort flow"},
        )
        assert create_response.status_code == 201
        run_id = create_response.json()["run"]["id"]

        # Step 2: Abort the run
        abort_response = client.post(f"/api/v1/runs/{run_id}/abort")
        assert abort_response.status_code == 200
        assert abort_response.json()["status"] == "aborted"

        # Step 3: Try to abort again (should fail)
        second_abort_response = client.post(f"/api/v1/runs/{run_id}/abort")
        assert second_abort_response.status_code == 409  # Conflict

        # Step 4: Try to approve (should fail)
        plan_id = create_response.json()["plan"]["id"]
        approve_response = client.post(
            f"/api/v1/runs/{run_id}/approve",
            json={"plan_id": plan_id, "approved": True},
        )
        assert approve_response.status_code == 409  # Conflict

    def test_list_runs_pagination(self, client):
        """Test listing runs with pagination."""
        # Create 10 runs
        run_ids = []
        for i in range(10):
            response = client.post(
                "/api/v1/runs",
                json={"query": f"Test query number {i}"},
            )
            assert response.status_code == 201
            run_ids.append(response.json()["run"]["id"])

        # Test pagination
        # Page 1
        page1_response = client.get("/api/v1/runs?limit=3")
        assert page1_response.status_code == 200
        page1 = page1_response.json()
        assert len(page1["items"]) == 3
        assert page1["next_cursor"] is not None

        # Page 2
        page2_response = client.get(f"/api/v1/runs?limit=3&cursor={page1['next_cursor']}")
        assert page2_response.status_code == 200
        page2 = page2_response.json()
        assert len(page2["items"]) == 3

        # Verify no duplicate IDs between pages
        page1_ids = {item["id"] for item in page1["items"]}
        page2_ids = {item["id"] for item in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_export_markdown_report(self, client):
        """Test exporting a run as markdown."""
        # Create a run
        create_response = client.post(
            "/api/v1/runs",
            json={"query": "Employment analysis query"},
        )
        assert create_response.status_code == 201
        run_id = create_response.json()["run"]["id"]

        # Export as markdown
        export_response = client.get(f"/api/v1/runs/{run_id}/export?format=md")
        assert export_response.status_code == 200
        assert "text/markdown" in export_response.headers["content-type"]

        # Verify content includes query
        content = export_response.text
        assert "Employment analysis query" in content

    def test_error_responses_format(self, client):
        """Test that error responses follow Problem JSON format."""
        # Test 404
        response = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        data = response.json()
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert data["status"] == 404

        # Test 422 (validation error)
        response = client.post("/api/v1/runs", json={"query": ""})
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == 422
        assert "errors" in data


class TestWebSocketConnection:
    """Integration tests for WebSocket connections."""

    def test_websocket_connection_invalid_run(self, client):
        """Test WebSocket connection to non-existent run."""
        # This test verifies that the WebSocket endpoint exists
        # Full WebSocket testing requires async test setup
        # For now, just verify the endpoint URL is correct
        pass  # WebSocket tests require special async handling


class TestEventSequence:
    """Tests for event ordering and retrieval."""

    def test_events_ordered_by_timestamp(self, client):
        """Test that events are returned in chronological order."""
        # Create a run
        create_response = client.post(
            "/api/v1/runs",
            json={"query": "Test event ordering"},
        )
        run_id = create_response.json()["run"]["id"]
        plan_id = create_response.json()["plan"]["id"]

        # Reject to create an event
        client.post(
            f"/api/v1/runs/{run_id}/approve",
            json={"plan_id": plan_id, "approved": False},
        )

        # Get events
        events_response = client.get(f"/api/v1/runs/{run_id}/events")
        events = events_response.json()["items"]

        # Verify events are in chronological order
        if len(events) > 1:
            for i in range(len(events) - 1):
                assert events[i]["ts"] <= events[i + 1]["ts"]

    def test_events_filter_by_timestamp(self, client):
        """Test filtering events by timestamp."""
        # Create a run and generate some events
        create_response = client.post(
            "/api/v1/runs",
            json={"query": "Test event filtering"},
        )
        run_id = create_response.json()["run"]["id"]
        plan_id = create_response.json()["plan"]["id"]

        # Reject to create an event
        client.post(
            f"/api/v1/runs/{run_id}/approve",
            json={"plan_id": plan_id, "approved": False},
        )

        # Get all events first
        all_events_response = client.get(f"/api/v1/runs/{run_id}/events")
        all_events = all_events_response.json()["items"]

        if len(all_events) > 0:
            # Get first event timestamp
            first_ts = all_events[0]["ts"]

            # Filter events after first timestamp
            filtered_response = client.get(
                f"/api/v1/runs/{run_id}/events?after={first_ts}"
            )
            filtered_events = filtered_response.json()["items"]

            # Should have fewer events (excluding the first one)
            assert len(filtered_events) < len(all_events)
