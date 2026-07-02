"""
LangGraph workflow for Clarity multi-agent system.

Flow:
quick_decision_router → team_gap_analysis → bias_signal_detection → fairness_policy_check
→ decision_synthesis → manager_reflection (if required) → manager_pattern_scoring
→ decision_logging → END
"""

import os
import logging
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.models import TalentDecisionState, TalentDecisionStatus
from ..agents.agents import ClarityTalentAgents
from ..database.moderation_db import TalentDecisionDatabase
from ..ml.guardrails import GuardrailManager, GuardrailConfig
from ..memory.learning_tracker import LearningTracker

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def should_use_quick_decision_check(state: TalentDecisionState) -> bool:
    """Determine if decision is eligible for Quick Decision Check."""
    enabled = os.getenv("ENABLE_QUICK_DECISION_CHECK", "true").lower() == "true"
    if not enabled:
        return False
    if state.get("force_full_pipeline", False):
        return False

    decision_type = state.get("decision_type") or state.get("content_type", "")
    eligible = os.getenv("QUICK_CHECK_DECISION_TYPES", "quick_manager_note").split(",")
    eligible = [t.strip() for t in eligible]

    if decision_type not in eligible:
        return False

    text = state.get("content_text") or state.get("manager_reasoning", "")
    max_length = int(os.getenv("QUICK_CHECK_MAX_LENGTH", "300"))
    if len(text) > max_length:
        return False

    logger.info(f"Quick Decision Check eligible: type={decision_type}, length={len(text)}")
    return True


# Legacy alias
should_use_fast_mode = should_use_quick_decision_check


def should_continue_from_team_gap_analysis(state: TalentDecisionState) -> Literal["bias_signal_detection", "END"]:
    status = state.get("status")
    if status == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
        return "END"
    return "bias_signal_detection"


def should_continue_from_bias_signal(state: TalentDecisionState) -> Literal["fairness_policy_check", "END"]:
    if state.get("status") == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
        return "END"
    return "fairness_policy_check"


def should_continue_from_fairness_policy(state: TalentDecisionState) -> Literal["decision_synthesis", "END"]:
    if state.get("status") == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
        return "END"
    return "decision_synthesis"


def should_continue_from_synthesis(state: TalentDecisionState) -> Literal["END"]:
    """Pause after synthesis — manager chooses on Recommendations page."""
    logger.info(
        "Routing from Decision Synthesis: pausing for manager choice (status=%s)",
        state.get("status"),
    )
    return "END"


def should_continue_from_reflection(state: TalentDecisionState) -> Literal["manager_pattern_scoring", "decision_logging", "END"]:
    status = state.get("status")
    human_decision = state.get("hitl_human_decision") or state.get("manager_final_decision", "")

    if status == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value and not human_decision:
        return "END"

    if human_decision in ("escalate_to_hr", "escalate") or status == TalentDecisionStatus.ESCALATED.value:
        return "END"

    return "manager_pattern_scoring"


def should_continue_from_pattern_scoring(state: TalentDecisionState) -> Literal["decision_logging", "END"]:
    if state.get("reflection_required") and not state.get("manager_reflection"):
        return "END"
    return "decision_logging"


def create_talent_decision_workflow(
    db: TalentDecisionDatabase,
    use_checkpointer: bool = True,
    enable_guardrails: bool = True,
    enable_learning: bool = True,
    enable_quick_check: bool = True,
) -> StateGraph:
    """Create the LangGraph StateGraph for Clarity."""
    logger.info("\nBuilding Clarity Workflow...")
    logger.info("=" * 40)

    learning_tracker = None
    if enable_learning:
        try:
            learning_tracker = LearningTracker()
        except Exception:
            learning_tracker = None

    guardrail_manager = None
    if enable_guardrails:
        try:
            guardrail_config = GuardrailConfig(
                max_reasoning_iterations=10,
                max_agent_calls=20,
                max_cost_usd=1.0,
                max_execution_time_seconds=300,
                hallucination_check_enabled=True,
                consistency_check_enabled=True,
            )
            guardrail_manager = GuardrailManager(config=guardrail_config)
        except Exception as gr_error:
            logger.error(f"Failed to initialize guardrails: {gr_error}")
            guardrail_manager = None

    agents = ClarityTalentAgents()
    workflow = StateGraph(TalentDecisionState)

    def create_agent_wrapper(agent_func, agent_name: str):
        def wrapped_agent(state: TalentDecisionState) -> TalentDecisionState:
            if guardrail_manager:
                iteration = state.get("_guardrail_iteration") or 0
                state["_guardrail_iteration"] = iteration + 1
                guardrail_result = guardrail_manager.check_all_guardrails(
                    state, current_iteration=iteration, operation_cost=0.001
                )
                if not state.get("_guardrail_checks"):
                    state["_guardrail_checks"] = []
                state["_guardrail_checks"].append({
                    "agent": agent_name, "iteration": iteration, "result": guardrail_result,
                })
                if not guardrail_result["passed"]:
                    violations = state.get("guardrail_violations") or []
                    state["guardrail_violations"] = violations + guardrail_result["violations"]

            result_state = agent_func(state)

            if learning_tracker and agent_name in ["bias_signal_detection", "fairness_policy_check", "decision_synthesis"]:
                decisions = result_state.get("agent_decisions", [])
                if decisions:
                    last = decisions[-1]
                    try:
                        learning_tracker.record_decision(
                            agent_name=last.agent_name,
                            content_text=result_state.get("business_goal", "") or result_state.get("content_text", ""),
                            toxicity_score=result_state.get("bias_risk_score", 0.0),
                            policy_violations=result_state.get("policy_violations", []),
                            decision=last.decision.value,
                            confidence=last.confidence,
                            outcome=result_state.get("status", "unknown"),
                            context=f"bias_{result_state.get('bias_risk_score', 0):.1f}",
                            metadata={"agent": agent_name},
                        )
                    except Exception as learn_err:
                        logger.error(f"Learning error: {learn_err}")

            return result_state
        return wrapped_agent

    node_agents = [
        ("team_gap_analysis", agents.team_gap_analysis_agent),
        ("bias_signal_detection", agents.bias_signal_detection_agent),
        ("fairness_policy_check", agents.fairness_policy_check_agent),
        ("decision_synthesis", agents.decision_synthesis_agent),
        ("manager_reflection", agents.manager_reflection_agent),
        ("manager_pattern_scoring", agents.manager_pattern_scoring_agent),
        ("decision_reconsideration", agents.decision_reconsideration_agent),
        ("decision_logging", agents.decision_logging_agent),
    ]

    if guardrail_manager or learning_tracker:
        for name, func in node_agents:
            workflow.add_node(name, create_agent_wrapper(func, name))
    else:
        for name, func in node_agents:
            workflow.add_node(name, func)

    if enable_quick_check:
        if guardrail_manager or learning_tracker:
            workflow.add_node("quick_decision_check", create_agent_wrapper(agents.quick_decision_check_agent, "quick_decision_check"))
        else:
            workflow.add_node("quick_decision_check", agents.quick_decision_check_agent)

    def entry_router(state: TalentDecisionState) -> TalentDecisionState:
        return state

    def route_entry(state: TalentDecisionState) -> Literal["decision_reconsideration", "manager_reflection", "team_gap_analysis", "quick_decision_check"]:
        if state.get("is_reconsideration") or state.get("is_appeal", False):
            return "decision_reconsideration"
        if (state.get("hitl_human_decision") or state.get("manager_final_decision")) and \
                state.get("status") == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
            return "manager_reflection"
        if enable_quick_check and should_use_quick_decision_check(state):
            return "quick_decision_check"
        return "team_gap_analysis"

    workflow.add_node("entry_router", entry_router)
    workflow.set_entry_point("entry_router")

    edge_targets = {
        "decision_reconsideration": "decision_reconsideration",
        "manager_reflection": "manager_reflection",
        "team_gap_analysis": "team_gap_analysis",
    }
    if enable_quick_check:
        edge_targets["quick_decision_check"] = "quick_decision_check"

    workflow.add_conditional_edges("entry_router", route_entry, edge_targets)

    workflow.add_conditional_edges(
        "team_gap_analysis", should_continue_from_team_gap_analysis,
        {"bias_signal_detection": "bias_signal_detection", "END": END},
    )
    workflow.add_conditional_edges(
        "bias_signal_detection", should_continue_from_bias_signal,
        {"fairness_policy_check": "fairness_policy_check", "END": END},
    )
    workflow.add_conditional_edges(
        "fairness_policy_check", should_continue_from_fairness_policy,
        {"decision_synthesis": "decision_synthesis", "END": END},
    )
    workflow.add_conditional_edges(
        "decision_synthesis", should_continue_from_synthesis,
        {"END": END},
    )
    workflow.add_conditional_edges(
        "manager_reflection", should_continue_from_reflection,
        {
            "manager_pattern_scoring": "manager_pattern_scoring",
            "decision_logging": "decision_logging",
            "END": END,
        },
    )
    workflow.add_conditional_edges(
        "manager_pattern_scoring", should_continue_from_pattern_scoring,
        {"decision_logging": "decision_logging", "END": END},
    )

    workflow.add_edge("decision_reconsideration", "decision_logging")
    workflow.add_edge("decision_logging", END)

    if enable_quick_check:
        workflow.add_edge("quick_decision_check", END)

    if use_checkpointer:
        checkpointer = MemorySaver()
        compiled_graph = workflow.compile(checkpointer=checkpointer)
    else:
        compiled_graph = workflow.compile()

    return compiled_graph


# Legacy aliases
create_moderation_workflow = create_talent_decision_workflow


def process_talent_decision(
    graph: StateGraph,
    initial_state: TalentDecisionState,
    config: Dict[str, Any] = None,
) -> TalentDecisionState:
    """Process a workforce decision through the multi-agent workflow."""
    logger.info("\n" + "=" * 40)
    logger.info("STARTING CLARITY TALENT DECISION WORKFLOW")
    logger.info("=" * 40)

    if config is None:
        thread_id = initial_state.get("decision_id") or initial_state.get("content_id", "default")
        config = {"configurable": {"thread_id": thread_id}}

    final_state = None
    try:
        for state in graph.stream(initial_state, config):
            final_state = state
    except Exception as stream_error:
        logger.error(f"Workflow error: {stream_error}")
        raise

    if final_state:
        final_state = list(final_state.values())[0]

    if final_state.get("status") == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
        logger.info("Workflow paused — awaiting manager reflection")
        return final_state

    logger.info("CLARITY TALENT DECISION COMPLETE")
    logger.info(f"Status: {final_state.get('status')}")
    logger.info(f"Recommendation: {final_state.get('react_act_decision', 'N/A')}")
    logger.info(f"Bias Risk: {final_state.get('bias_risk_score', 0):.2%}")
    return final_state


process_content = process_talent_decision


def resume_from_reflection(
    graph: StateGraph,
    decision_id: str,
    manager_decision: str,
    manager_notes: str = "",
    reviewer_name: str = "Manager",
    confidence_override: float = None,
    existing_state: TalentDecisionState = None,
) -> TalentDecisionState:
    """Resume a paused workflow with manager reflection decision."""
    if existing_state is None:
        raise ValueError(f"No existing state for decision_id: {decision_id}")

    existing_state["hitl_human_decision"] = manager_decision
    existing_state["manager_final_decision"] = manager_decision
    existing_state["hitl_human_notes"] = manager_notes
    existing_state["manager_reflection"] = manager_notes
    existing_state["reviewer_name"] = reviewer_name

    if confidence_override is not None:
        existing_state["hitl_human_confidence_override"] = confidence_override

    config = {"configurable": {"thread_id": decision_id}}
    return process_talent_decision(graph, existing_state, config)


resume_from_hitl = resume_from_reflection


def run_post_manager_choice_pipeline(state: TalentDecisionState) -> TalentDecisionState:
    """Run bias review → pattern scoring → logging after manager submits hire/promote choice."""
    agents = ClarityTalentAgents()
    state = agents.manager_decision_bias_review_agent(state)
    state = agents.manager_pattern_scoring_agent(state)
    state = agents.decision_logging_agent(state)
    return state


def create_reconsideration_workflow(db: TalentDecisionDatabase) -> StateGraph:
    """Simplified workflow for reconsideration requests."""
    agents = ClarityTalentAgents()
    workflow = StateGraph(TalentDecisionState)
    workflow.add_node("decision_reconsideration", agents.decision_reconsideration_agent)
    workflow.add_node("decision_logging", agents.decision_logging_agent)
    workflow.set_entry_point("decision_reconsideration")
    workflow.add_edge("decision_reconsideration", "decision_logging")
    workflow.add_edge("decision_logging", END)
    return workflow.compile()


create_appeal_workflow = create_reconsideration_workflow
