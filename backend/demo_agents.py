"""
Demo script to test multi-agent system.

Run this script to execute a sample query through the full agent workflow:
1. Coordinator generates plan
2. Wait for approval (auto-approved in demo)
3. Extraction fetches data
4. Analytics computes insights
5. Returns final results

Usage:
    python demo_agents.py
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.agents.graph import AgentOrchestrator
from app.schemas.events import event_store


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def print_events(run_id: str):
    """Print all events for a run."""
    events = event_store.get_events(run_id)

    for event in events:
        print(f"[{event.agent.value.upper()}] {event.phase.value}: {event.message}")
        if event.payload:
            payload_str = json.dumps(event.payload, indent=2, default=str)
            if len(payload_str) > 500:
                payload_str = payload_str[:500] + "... (truncated)"
            print(f"  Payload: {payload_str}")
        print()


def demo_basic_query():
    """Run demo with basic query."""
    print_section("MULTI-AGENT SYSTEM DEMO")

    # Initialize database session
    db = SessionLocal()

    try:
        # Create orchestrator
        orchestrator = AgentOrchestrator(db)

        # Demo query
        query = "What has been the trend in Singapore's tech sector employment from 2019 to 2023?"

        print(f"Query: {query}\n")

        # Step 1: Execute until approval gate
        print_section("STEP 1: COORDINATOR - Generate Plan")

        result = orchestrator.execute(query)

        print("Run ID:", result["run_id"])
        print("\nGenerated Plan:")
        if result["plan"]:
            plan_json = json.dumps(result["plan"].model_dump(), indent=2)
            print(plan_json)

        # Print coordinator events
        print("\nCoordinator Events:")
        print_events(result["run_id"])

        # Step 2: Approval gate (auto-approve in demo)
        print_section("STEP 2: APPROVAL GATE (HITL)")

        print("In production, this would wait for user approval via UI/API.")
        print("For demo, auto-approving plan...\n")

        orchestrator.approve_plan(result["run_id"], approved=True)
        print("✓ Plan approved")

        # Step 3: Continue execution
        print_section("STEP 3: EXTRACTION & ANALYTICS - Execute Plan")

        final_output = orchestrator.continue_after_approval(result["run_id"])

        print("Extraction Summary:")
        if final_output.get("extraction_summary"):
            for idx, summary in enumerate(final_output["extraction_summary"], 1):
                print(f"\n  Dataset {idx}:")
                print(f"    ID: {summary.get('dataset_id')}")
                print(f"    Name: {summary.get('name')}")
                print(f"    Rows: {summary.get('row_count')}")
                print(f"    Columns: {summary.get('column_count')}")
                print(f"    Status: {summary.get('status')}")
                print(f"    Quality Score: {summary.get('quality_score')}")

        print("\nAnalytics Results:")
        if final_output.get("analytics"):
            analytics = final_output["analytics"]

            print(f"\n  Computed Tables: {len(analytics.get('computed_tables', []))}")
            print(f"  Charts: {len(analytics.get('charts', []))}")
            print(f"  Insights: {len(analytics.get('insights', []))}")

            # Print insights
            for insight in analytics.get("insights", []):
                print(f"\n  Insight: {insight['headline']}")
                print(f"    Confidence: {insight['confidence']:.2f}")
                print(f"    Policy Implication: {insight['policy_implication']}")
                print(f"    Citations: {len(insight['citations'])}")

        # Step 4: Full event trace
        print_section("STEP 4: FULL EVENT TRACE (ReAct)")

        print_events(result["run_id"])

        # Summary
        print_section("DEMO COMPLETE")

        print("✓ Coordinator generated plan")
        print("✓ Plan approved by user (HITL gate)")
        print("✓ Extraction fetched and validated datasets")
        print("✓ Analytics computed insights with citations")
        print("✓ All events traced for replay and observability")

        print(f"\nRun ID: {result['run_id']}")
        print("All events persisted in event store for audit trail.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


def demo_with_constraints():
    """Run demo with user constraints."""
    print_section("DEMO WITH USER CONSTRAINTS")

    db = SessionLocal()

    try:
        orchestrator = AgentOrchestrator(db)

        query = "Analyze digital transformation metrics"
        constraints = {
            "allowed_sources": ["singstat", "mock_internal"],
            "time_limit": 30,  # seconds
        }

        print(f"Query: {query}")
        print(f"Constraints: {json.dumps(constraints, indent=2)}\n")

        result = orchestrator.execute(query, user_constraints=constraints)

        print("Generated Plan:")
        if result["plan"]:
            print(json.dumps(result["plan"].model_dump(), indent=2))

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-agent system demo")
    parser.add_argument(
        "--mode",
        choices=["basic", "constraints"],
        default="basic",
        help="Demo mode to run",
    )

    args = parser.parse_args()

    if args.mode == "basic":
        demo_basic_query()
    elif args.mode == "constraints":
        demo_with_constraints()
