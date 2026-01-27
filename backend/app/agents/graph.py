"""
LangGraph orchestration for multi-agent workflow.

Workflow:
1. Coordinator: Interpret query → Propose plan
2. WAIT: Plan approval gate (HITL)
3. Extraction: Run approved extraction steps
4. Analytics: Compute tables, charts, insights
5. Finalize: Return results

Implements bounded autonomy with human-in-the-loop approval.
"""

import uuid
from typing import Dict, Any, Optional, TypedDict, Annotated
from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.coordinator import CoordinatorAgent
from app.agents.extraction import ExtractionAgent
from app.agents.analytics import AnalyticsAgent
from app.llm.router import LLMRouter
from app.schemas.plan import Plan, PlanApprovalRequest
from app.schemas.events import event_store, EventPhase, AgentType, AgentEvent


class AgentState(TypedDict):
    """State passed between agent nodes."""

    run_id: str
    query: str
    user_constraints: Optional[Dict[str, Any]]
    plan: Optional[Plan]
    plan_approved: bool
    extraction_results: Optional[list]
    analytics_results: Optional[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
    error: Optional[str]


class AgentOrchestrator:
    """
    LangGraph-based orchestrator for multi-agent workflow.

    Features:
    - Directed workflow with approval gate
    - Graceful failure handling
    - Event tracing across all agents
    - Stateful execution with checkpoints
    """

    def __init__(self, db: Session):
        """
        Initialize orchestrator.

        Args:
            db: Database session
        """
        self.db = db
        self.llm_router = LLMRouter()

        # Initialize agents
        self.coordinator = CoordinatorAgent(self.llm_router)
        self.extraction = ExtractionAgent(db)
        self.analytics = AnalyticsAgent(db, self.llm_router)

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow.

        Returns:
            Compiled StateGraph
        """
        # Create workflow
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("interpret_query", self._interpret_query_node)
        workflow.add_node("wait_approval", self._wait_approval_node)
        workflow.add_node("run_extraction", self._run_extraction_node)
        workflow.add_node("run_analytics", self._run_analytics_node)
        workflow.add_node("finalize", self._finalize_node)

        # Define edges
        workflow.set_entry_point("interpret_query")

        workflow.add_edge("interpret_query", "wait_approval")

        # Conditional edge: wait for approval
        # Note: "waiting" goes to END to pause execution at the approval gate.
        # Use continue_after_approval() to resume after user approves the plan.
        workflow.add_conditional_edges(
            "wait_approval",
            self._check_approval,
            {
                "approved": "run_extraction",
                "waiting": END,  # Pause here - resume via continue_after_approval()
                "rejected": END,
            },
        )

        workflow.add_edge("run_extraction", "run_analytics")
        workflow.add_edge("run_analytics", "finalize")
        workflow.add_edge("finalize", END)

        # Compile with memory saver for checkpoints
        return workflow.compile(checkpointer=MemorySaver())

    def _interpret_query_node(self, state: AgentState) -> AgentState:
        """
        Coordinator: Interpret query and propose plan.

        Args:
            state: Current state

        Returns:
            Updated state with plan
        """
        try:
            plan = self.coordinator.interpret_query(
                run_id=state["run_id"],
                query_text=state["query"],
                user_constraints=state.get("user_constraints"),
            )
            state["plan"] = plan
            state["plan_approved"] = False

        except Exception as e:
            state["error"] = f"Coordinator error: {str(e)}"

        return state

    def _wait_approval_node(self, state: AgentState) -> AgentState:
        """
        HITL approval gate: Wait for user to approve/reject plan.

        This is a blocking node that requires external input.
        In production, this would integrate with UI or API.

        Args:
            state: Current state

        Returns:
            State (unchanged, waiting for approval)
        """
        # Emit event indicating waiting state
        event = AgentEvent(
            run_id=state["run_id"],
            agent=AgentType.COORDINATOR,
            phase=EventPhase.DECISION,
            message="Plan ready, awaiting user approval",
            payload={"plan": state["plan"].model_dump() if state["plan"] else None},
        )
        event_store.emit(event)

        return state

    def _check_approval(self, state: AgentState) -> str:
        """
        Check if plan is approved.

        Args:
            state: Current state

        Returns:
            Edge name: "approved", "waiting", or "rejected"
        """
        if not state.get("plan"):
            return "rejected"

        if state["plan"].approved:
            return "approved"
        else:
            return "waiting"

    def _run_extraction_node(self, state: AgentState) -> AgentState:
        """
        Extraction: Fetch and clean datasets.

        Args:
            state: Current state

        Returns:
            Updated state with extraction results
        """
        try:
            results = self.extraction.run_extraction(
                run_id=state["run_id"], approved_plan=state["plan"]
            )
            state["extraction_results"] = results

        except Exception as e:
            state["error"] = f"Extraction error: {str(e)}"

        return state

    def _run_analytics_node(self, state: AgentState) -> AgentState:
        """
        Analytics: Compute tables, charts, insights.

        Args:
            state: Current state

        Returns:
            Updated state with analytics results
        """
        try:
            # Get successful datasets
            datasets = [
                r.dataset
                for r in state.get("extraction_results", [])
                if r.success and r.dataset
            ]

            if datasets:
                analytics_result = self.analytics.run_analysis(
                    run_id=state["run_id"],
                    approved_plan=state["plan"],
                    datasets=datasets,
                )
                state["analytics_results"] = analytics_result.model_dump()
            else:
                state["error"] = "No datasets available for analysis"

        except Exception as e:
            state["error"] = f"Analytics error: {str(e)}"

        return state

    def _finalize_node(self, state: AgentState) -> AgentState:
        """
        Finalize: Assemble final output.

        Args:
            state: Current state

        Returns:
            Updated state with final output
        """
        # Assemble final output
        extraction_summary = []
        if state.get("extraction_results"):
            for result in state["extraction_results"]:
                if result.success:
                    extraction_summary.append(
                        self.extraction.get_dataset_summary(result.dataset)
                    )
                else:
                    extraction_summary.append({"success": False, "error": result.error})

        state["final_output"] = {
            "run_id": state["run_id"],
            "query": state["query"],
            "plan": state["plan"].model_dump() if state["plan"] else None,
            "extraction_summary": extraction_summary,
            "analytics": state.get("analytics_results"),
            "events": [
                e.model_dump() for e in event_store.get_events(state["run_id"])
            ],
            "error": state.get("error"),
        }

        return state

    def execute(
        self,
        query: str,
        user_constraints: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute multi-agent workflow for a query.

        This initiates the workflow up to the approval gate.
        Use approve_and_continue() to proceed after user approval.

        Args:
            query: User query
            user_constraints: Optional constraints
            run_id: Optional run ID (generates if None)

        Returns:
            State with plan awaiting approval
        """
        if not run_id:
            run_id = str(uuid.uuid4())

        initial_state: AgentState = {
            "run_id": run_id,
            "query": query,
            "user_constraints": user_constraints,
            "plan": None,
            "plan_approved": False,
            "extraction_results": None,
            "analytics_results": None,
            "final_output": None,
            "error": None,
        }

        # Execute workflow (will stop at approval gate)
        config = {"configurable": {"thread_id": run_id}}
        result = self.graph.invoke(initial_state, config)

        return result

    def approve_plan(self, run_id: str, approved: bool = True) -> None:
        """
        Approve or reject plan.

        Args:
            run_id: Run identifier
            approved: Whether to approve the plan
        """
        # Get events to find plan
        events = event_store.get_events(run_id, agent=AgentType.COORDINATOR)

        for event in reversed(events):
            if event.phase == EventPhase.DECISION and "plan" in event.payload:
                plan_dict = event.payload["plan"]
                plan = Plan(**plan_dict)
                plan.approved = approved

                # Update event payload
                event.payload["plan"] = plan.model_dump()

                # Re-emit approval event
                approval_event = AgentEvent(
                    run_id=run_id,
                    agent=AgentType.COORDINATOR,
                    phase=EventPhase.DECISION,
                    message=f"Plan {'approved' if approved else 'rejected'} by user",
                    payload={"approved": approved, "plan": plan.model_dump()},
                )
                event_store.emit(approval_event)
                break

    def continue_after_approval(self, run_id: str) -> Dict[str, Any]:
        """
        Continue workflow after plan approval.

        Args:
            run_id: Run identifier

        Returns:
            Final output
        """
        # Get current state from events
        events = event_store.get_events(run_id, agent=AgentType.COORDINATOR)

        plan = None
        for event in reversed(events):
            if "plan" in event.payload and event.payload.get("approved"):
                plan = Plan(**event.payload["plan"])
                break

        if not plan or not plan.approved:
            raise ValueError("Plan not approved")

        # Create state for continuation
        state: AgentState = {
            "run_id": run_id,
            "query": plan.intent.question,
            "user_constraints": None,
            "plan": plan,
            "plan_approved": True,
            "extraction_results": None,
            "analytics_results": None,
            "final_output": None,
            "error": None,
        }

        # Continue from extraction node
        state = self._run_extraction_node(state)
        state = self._run_analytics_node(state)
        state = self._finalize_node(state)

        return state["final_output"]
