"""
Clarity API routes.
"""

import logging
import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field, field_validator

from ..core.models import TalentDecisionState, TalentDecisionStatus, UserProfile
from ..agents.workflow import process_talent_decision, resume_from_reflection, run_post_manager_choice_pipeline
from ..agents.agents import ClarityTalentAgents
from ..utils.tools import generate_content_id
from ..utils.resume_parser import extract_resume_text, build_anonymized_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/talent", tags=["Clarity"])

# Injected at app startup
_db = None
_workflow = None
_reflection_pending: Dict[str, TalentDecisionState] = {}


def init_talent_routes(db, workflow):
    global _db, _workflow
    _db = db
    _workflow = workflow


class TalentDecisionSubmission(BaseModel):
    business_goal: str = Field(..., description="Business goal driving the workforce decision")
    decision_type: str = Field("gap_analysis", description="Decision category")
    manager_id: str = Field("mgr_001", description="Manager ID")
    manager_name: str = Field("Aisha Rahman", description="Manager name")
    team_id: str = Field("team_alpha", description="Team ID")
    team_name: str = Field("Product Engineering", description="Team name")
    timeline_months: Optional[int] = 6
    budget_level: Optional[str] = "medium"
    headcount_available: Optional[int] = 1
    manager_reasoning: Optional[str] = None
    manager_override_reason: Optional[str] = None
    required_capabilities: List[Dict[str, Any]] = Field(default_factory=list)
    uploaded_resumes: List[Dict[str, Any]] = Field(default_factory=list)
    content_text: Optional[str] = None  # for quick manager notes


class ReflectionSubmitRequest(BaseModel):
    decision: str = Field(..., description="accept_recommendation|revise_decision|override_with_reason|escalate_to_hr")
    manager_name: str = Field("Manager")
    notes: str = Field("")
    confidence_override: Optional[float] = None


class ReconsiderationSubmission(BaseModel):
    decision_id: str
    manager_id: str
    reconsideration_reason: str


class ManagerDecisionRequest(BaseModel):
    manager_id: str = Field("mgr_001", description="Manager ID")
    manager_final_decision: str = Field(..., description="hire|promote|upskill|hire_external|promote_internal")
    manager_reasoning: str = Field("", description="Manager notes")
    manager_override_reason: Optional[str] = Field(None, description="Required when overriding AI recommendation")
    target_employee_id: Optional[str] = Field(None, description="Required for promote/upskill decisions")
    target_employee_name: Optional[str] = Field(None, description="Display name for promote/upskill")
    business_goal: Optional[str] = None
    recommended_action: Optional[str] = None
    bias_risk_score: Optional[float] = None
    bias_categories: List[str] = Field(default_factory=list)
    ai_recommendation: Optional[Dict[str, Any]] = None
    gap_analysis: List[Dict[str, Any]] = Field(default_factory=list)


class ManagerChoiceRequest(BaseModel):
    manager_id: str = Field("mgr_001")
    manager_choice: Literal["hire_external", "promote_internal"]
    manager_reasoning: str = Field(..., min_length=1)
    manager_override_reason: Optional[str] = None
    target_employee_id: Optional[str] = None
    target_employee_name: Optional[str] = None
    upskill_plan: Optional[str] = None
    business_goal: Optional[str] = None
    recommended_action: Optional[str] = None
    bias_risk_score: Optional[float] = None
    bias_categories: List[str] = Field(default_factory=list)
    ai_recommendation: Optional[Dict[str, Any]] = None
    gap_analysis: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("gap_analysis", mode="before")
    @classmethod
    def normalize_gap_analysis(cls, value):
        if not value:
            return []
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"capability": item})
            elif isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"capability": str(item)})
        return normalized

    @field_validator("bias_categories", mode="before")
    @classmethod
    def normalize_bias_categories(cls, value):
        if not value:
            return []
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                normalized.append(str(item.get("pattern") or item.get("category") or item.get("name") or item))
            else:
                normalized.append(str(item))
        return normalized


def _compose_manager_reasoning(request: ManagerDecisionRequest) -> Optional[str]:
    parts = []
    if request.target_employee_name and request.manager_final_decision in ("promote", "upskill"):
        parts.append(f"Target: {request.target_employee_name} ({request.target_employee_id})")
    if request.manager_reasoning:
        parts.append(request.manager_reasoning)
    return "\n".join(parts) if parts else None


def _capability_label(c: Any) -> str:
    if isinstance(c, dict):
        return str(c.get("capability") or c.get("skill") or c.get("name") or c)
    return str(c)


def _gap_label(g: Any) -> str:
    return _capability_label(g)


def _build_screening_job_description(state: TalentDecisionState) -> None:
    """Build resume-screening JD from required capabilities as bullet list."""
    caps = state.get("required_capabilities") or []
    if not caps:
        caps = (state.get("critical_gaps") or []) + (state.get("moderate_gaps") or [])

    labels = [_capability_label(c) for c in caps if _capability_label(c)]
    if not labels:
        return

    goal = state.get("business_goal", "Team business goal")
    bullets = "\n".join(f"• {label}" for label in labels)
    job_description = f"Required capabilities for: {goal}\n\n{bullets}"

    hr = state.get("hiring_role") or {}
    state["screening_job_description"] = job_description
    state["generated_job_description"] = job_description
    state["hiring_role"] = {
        **hr,
        "role_title": hr.get("role_title") or "Required capabilities — resume screening",
        "job_description": job_description,
        "required_skills": labels,
        "required_capabilities": caps,
    }


def _ensure_hiring_role_from_gaps(state: TalentDecisionState) -> None:
    """Ensure screening JD exists; always prefer required-capability bullets."""
    _build_screening_job_description(state)
    if state.get("generated_job_description"):
        return

    gaps = (state.get("critical_gaps") or []) + (state.get("moderate_gaps") or [])
    if not gaps:
        return

    labels = [_gap_label(g) for g in gaps[:6]]
    state["required_capabilities"] = state.get("required_capabilities") or [
        {"capability": label} for label in labels
    ]
    _build_screening_job_description(state)


def _post_process_workflow_state(state: TalentDecisionState) -> TalentDecisionState:
    """Enforce hire/promote/upskill-only decisions and ensure gap-based JD exists."""
    _ensure_hiring_role_from_gaps(state)

    members_by_id = {m["employee_id"]: m for m in state.get("team_members", [])}

    action = ClarityTalentAgents._normalize_workforce_action(
        state.get("recommended_action") or state.get("react_act_decision") or "upskill"
    )
    state["recommended_action"] = action
    state["primary_path"] = state.get("primary_path") or ClarityTalentAgents._primary_path_from_action(action)

    rec_type = f"recommend_{action}"
    final_rec = state.get("final_recommendation") or {}
    if not isinstance(final_rec, dict):
        final_rec = {}
    final_rec["type"] = rec_type
    final_rec["action"] = action
    state["final_recommendation"] = final_rec
    state["react_act_decision"] = rec_type

    for key in ("promotion_recommendation", "upskill_recommendation"):
        rec = state.get(key)
        if isinstance(rec, dict):
            eid = rec.get("recommended_employee_id")
            if eid in members_by_id:
                rec["recommended_employee_name"] = members_by_id[eid].get("name")

    fr = state.get("final_recommendation") or {}
    if action in ("promote", "upskill"):
        eid = fr.get("target_employee_id")
        if not eid:
            src = state.get("promotion_recommendation" if action == "promote" else "upskill_recommendation") or {}
            eid = src.get("recommended_employee_id")
        if eid in members_by_id:
            fr["target_employee_id"] = eid
            fr["target_employee_name"] = members_by_id[eid].get("name")
            state["final_recommendation"] = fr

    return state


def _format_workflow_response(decision_id: str, final_state: TalentDecisionState) -> Dict[str, Any]:
    return {
        "decision_id": decision_id,
        "status": final_state.get("status"),
        "business_goal": final_state.get("business_goal"),
        "recommended_action": final_state.get("recommended_action") or final_state.get("react_act_decision"),
        "final_recommendation": final_state.get("final_recommendation"),
        "bias_risk_score": final_state.get("bias_risk_score", 0.0),
        "bias_risk_level": final_state.get("bias_risk_level"),
        "bias_categories": final_state.get("bias_categories", []),
        "fairness_concerns": final_state.get("fairness_flags", []),
        "fairness_flags": final_state.get("fairness_flags", []),
        "manager_pattern_score": final_state.get("manager_pattern_score", 0.0),
        "reflection_required": final_state.get("reflection_required", False),
        "reflection_questions": final_state.get("reflection_questions", []),
        "critical_gaps": final_state.get("critical_gaps", []),
        "moderate_gaps": final_state.get("moderate_gaps", []),
        "gap_analysis": final_state.get("gap_analysis", []),
        "required_capabilities": final_state.get("required_capabilities", []),
        "team_id": final_state.get("team_id"),
        "team_name": final_state.get("team_name"),
        "team_members": final_state.get("team_members", []),
        "team_capability_map": final_state.get("team_capability_map", []),
        "promotion_recommendation": final_state.get("promotion_recommendation"),
        "upskill_recommendation": final_state.get("upskill_recommendation"),
        "hiring_role": final_state.get("hiring_role"),
        "generated_job_description": final_state.get("generated_job_description"),
        "screening_job_description": final_state.get("screening_job_description"),
        "interview_rubric": final_state.get("interview_rubric"),
        "policy_violations": final_state.get("policy_violations", []),
        "policy_passed": len(final_state.get("policy_violations", [])) == 0,
        "violation_severity": final_state.get("violation_severity", "none"),
        "fairness_confidence": final_state.get("react_confidence") or final_state.get("decision_synthesis_confidence"),
        "candidate_match_results": final_state.get("candidate_match_results", []),
        "shortlist": final_state.get("shortlist", []),
        "decision_synthesis_confidence": final_state.get("decision_synthesis_confidence"),
        "decision_synthesis_reasoning": final_state.get("decision_synthesis_reasoning"),
        "agent_decisions_count": len(final_state.get("agent_decisions", [])),
        "primary_path": final_state.get("primary_path"),
        "path_comparison": final_state.get("path_comparison", {}),
    }


def _serialize_state_snapshot(state: TalentDecisionState) -> Dict[str, Any]:
    """JSON-safe subset of workflow state for durable snapshots."""
    import json
    raw = json.dumps(state, default=str)
    return json.loads(raw)


def _load_state_snapshot(snapshot: Dict[str, Any]) -> TalentDecisionState:
    return snapshot.get("state") or {}


def _primary_path_matches(choice: str, primary: str) -> bool:
    if not primary:
        return True
    return choice == primary


def _save_manager_choice_log(decision_id: str, state: TalentDecisionState, request: ManagerChoiceRequest):
    if not _db:
        return
    post = state.get("post_decision_bias") or {}
    ai_rec = {
        **(request.ai_recommendation or state.get("final_recommendation") or {}),
        "primary_path": state.get("primary_path"),
        "path_comparison": state.get("path_comparison"),
    }
    _db.save_talent_decision_log({
        "decision_id": decision_id,
        "manager_id": request.manager_id,
        "decision_type": request.manager_choice,
        "business_goal": request.business_goal or state.get("business_goal", ""),
        "gap_analysis": request.gap_analysis or state.get("gap_analysis", []),
        "recommended_action": state.get("recommended_action") or request.recommended_action,
        "ai_recommendation": ai_rec,
        "manager_final_decision": request.manager_choice,
        "manager_reasoning": request.manager_reasoning,
        "manager_override_reason": request.manager_override_reason,
        "bias_risk_score": post.get("score", state.get("bias_risk_score", request.bias_risk_score or 0)),
        "bias_categories": state.get("bias_categories", request.bias_categories or []),
        "manager_patterns": state.get("manager_patterns", []),
        "reflection": {
            "post_decision_bias": post,
            "upskill_plan": request.upskill_plan,
            "coaching_notes": post.get("coaching_notes"),
        },
        "selected_candidate_id": request.target_employee_id,
        "candidate_match": [],
    })
    for decision in state.get("agent_decisions", []):
        try:
            _db.save_agent_decision(decision_id, decision)
        except Exception:
            pass
    _persist_training_recommendations(request.manager_id, state)


def _build_initial_state(submission: TalentDecisionSubmission) -> TalentDecisionState:
    decision_id = generate_content_id()
    team_members_raw = _db.get_team_members(submission.team_id) if _db else []
    team_members = []
    for m in team_members_raw:
        team_members.append({
            "employee_id": m.get("employee_id"),
            "name": m.get("name"),
            "role": m.get("role"),
            "level": m.get("level"),
            "skills": m.get("skills", []),
            "performance_evidence": m.get("performance_evidence", []),
            "career_goals": m.get("career_goals", []),
            "workload": m.get("workload", {}),
        })

    manager_profile = UserProfile(
        user_id=submission.manager_id,
        username=submission.manager_name,
        reputation_score=0.7,
        reputation_tier="low",
    )

    return {
        "decision_id": decision_id,
        "content_id": decision_id,
        "submission_id": f"SUB-{decision_id}",
        "submission_timestamp": datetime.now().isoformat(),
        "manager_id": submission.manager_id,
        "manager_name": submission.manager_name,
        "team_id": submission.team_id,
        "team_name": submission.team_name,
        "team_members": team_members,
        "user_id": submission.manager_id,
        "username": submission.manager_name,
        "user_profile": manager_profile,
        "decision_type": submission.decision_type,
        "content_type": submission.decision_type,
        "business_goal": submission.business_goal,
        "timeline_months": submission.timeline_months,
        "budget_level": submission.budget_level,
        "headcount_available": submission.headcount_available,
        "manager_reasoning": submission.manager_reasoning,
        "manager_override_reason": submission.manager_override_reason,
        "required_capabilities": submission.required_capabilities or [],
        "uploaded_resumes": submission.uploaded_resumes,
        "content_text": submission.content_text or submission.manager_reasoning or submission.business_goal,
        "gap_analysis": [],
        "critical_gaps": [],
        "moderate_gaps": [],
        "parsed_candidates": [],
        "candidate_match_results": [],
        "shortlist": [],
        "policy_violations": [],
        "bias_categories": [],
        "fairness_flags": [],
        "agent_decisions": [],
        "status": TalentDecisionStatus.SUBMITTED.value,
        "requires_human_review": False,
        "reflection_required": False,
        "hitl_required": False,
        "hitl_trigger_reasons": [],
        "created_at": datetime.now().isoformat(),
        "force_full_pipeline": submission.decision_type not in ("quick_manager_note",),
    }


def _save_results(decision_id: str, final_state: TalentDecisionState, submission: TalentDecisionSubmission):
    if not _db:
        return
    _db.save_talent_decision_log({
        "decision_id": decision_id,
        "manager_id": submission.manager_id,
        "decision_type": submission.decision_type,
        "business_goal": submission.business_goal,
        "gap_analysis": final_state.get("gap_analysis", []),
        "recommended_action": final_state.get("recommended_action") or final_state.get("react_act_decision"),
        "ai_recommendation": final_state.get("final_recommendation", {}),
        "manager_final_decision": final_state.get("manager_final_decision"),
        "manager_reasoning": submission.manager_reasoning,
        "manager_override_reason": submission.manager_override_reason,
        "bias_risk_score": final_state.get("bias_risk_score", 0.0),
        "bias_categories": final_state.get("bias_categories", []),
        "manager_patterns": final_state.get("manager_patterns", []),
        "reflection": {"manager_reflection": final_state.get("manager_reflection")},
        "selected_candidate_id": final_state.get("selected_candidate_id"),
        "candidate_match": final_state.get("candidate_match_results", []),
    })
    for decision in final_state.get("agent_decisions", []):
        _db.save_agent_decision(decision_id, decision)

    _persist_training_recommendations(submission.manager_id, final_state)


def _persist_training_recommendations(manager_id: str, final_state: TalentDecisionState):
    """Persist any adaptive-training modules the workflow recommended."""
    if not _db:
        return
    training = final_state.get("recommended_training") or []
    for t in training:
        if isinstance(t, dict):
            title = t.get("module_title") or t.get("title") or t.get("name") or "Bias awareness module"
            module_type = t.get("module_type") or t.get("type") or "bias_awareness"
            trigger = t.get("trigger_type") or t.get("trigger") or "pattern_detected"
            payload = t
        else:
            title, module_type, trigger, payload = str(t), "bias_awareness", "pattern_detected", {"note": str(t)}
        _db.save_training_recommendation({
            "training_id": f"train_{uuid.uuid4().hex[:10]}",
            "manager_id": manager_id,
            "trigger_type": trigger,
            "module_title": title,
            "module_type": module_type,
            "module_payload": payload,
            "status": "recommended",
        })


def _run_talent_workflow(initial_state: TalentDecisionState) -> TalentDecisionState:
    """Run workflow with graceful OpenRouter error handling."""
    try:
        return process_talent_decision(_workflow, initial_state)
    except Exception:
        logger.exception("Talent workflow failed due to LLM provider error")
        raise HTTPException(
            status_code=503,
            detail="OpenRouter provider temporarily unavailable or rate-limited. Please try again later.",
        )


@router.post("/decisions/submit")
async def submit_talent_decision(submission: TalentDecisionSubmission):
    """Submit a workforce decision for multi-agent analysis."""
    if not _workflow:
        raise HTTPException(status_code=503, detail="Workflow not initialized")

    initial_state = _build_initial_state(submission)
    decision_id = initial_state["decision_id"]

    final_state = _run_talent_workflow(initial_state)
    final_state = _post_process_workflow_state(final_state)

    if submission.decision_type == "gap_analysis" and _db:
        _db.save_workflow_snapshot(
            decision_id,
            submission.manager_id,
            _serialize_state_snapshot(final_state),
        )
        if final_state.get("reflection_required"):
            _reflection_pending[decision_id] = final_state
            _db.save_reflection({
                "decision_id": decision_id,
                "manager_id": submission.manager_id,
                "business_goal": final_state.get("business_goal", ""),
                "priority": final_state.get("hitl_priority", "medium"),
                "bias_risk_score": final_state.get("bias_risk_score", 0.0),
                "bias_categories": final_state.get("bias_categories", []),
                "ai_recommendation": final_state.get("primary_path") or final_state.get("react_act_decision"),
                "reflection_questions": final_state.get("reflection_questions", []),
            })

    if final_state.get("reflection_required") and \
            final_state.get("status") == TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value:
        _reflection_pending[decision_id] = final_state
        if _db:
            _db.save_reflection({
                "decision_id": decision_id,
                "manager_id": submission.manager_id,
                "business_goal": final_state.get("business_goal", ""),
                "priority": final_state.get("hitl_priority", "medium"),
                "bias_risk_score": final_state.get("bias_risk_score", 0.0),
                "bias_categories": final_state.get("bias_categories", []),
                "ai_recommendation": final_state.get("react_act_decision"),
                "reflection_questions": final_state.get("reflection_questions", []),
            })

    # Gap analysis is exploratory — log only when the manager submits a final decision.
    if submission.decision_type not in ("gap_analysis",):
        _save_results(decision_id, final_state, submission)

    return _format_workflow_response(decision_id, final_state)


@router.post("/decisions/{decision_id}/manager-decision")
async def submit_manager_decision(decision_id: str, request: ManagerDecisionRequest):
    """Record the manager's final workforce decision."""
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    updated = _db.update_talent_decision_manager(
        decision_id,
        request.manager_final_decision,
        _compose_manager_reasoning(request),
        request.manager_override_reason,
    )
    if not updated:
        _db.save_talent_decision_log({
            "decision_id": decision_id,
            "manager_id": request.manager_id,
            "decision_type": request.manager_final_decision,
            "business_goal": request.business_goal or "",
            "gap_analysis": request.gap_analysis or [],
            "recommended_action": request.recommended_action or request.manager_final_decision,
            "ai_recommendation": request.ai_recommendation or {},
            "manager_final_decision": request.manager_final_decision,
            "manager_reasoning": _compose_manager_reasoning(request),
            "manager_override_reason": request.manager_override_reason,
            "bias_risk_score": request.bias_risk_score or 0.0,
            "bias_categories": request.bias_categories or [],
            "manager_patterns": [],
            "reflection": {},
            "selected_candidate_id": request.target_employee_id,
            "candidate_match": [],
        })

    return {
        "decision_id": decision_id,
        "manager_final_decision": request.manager_final_decision,
        "status": "recorded",
        "created": not updated,
    }


@router.post("/decisions/{decision_id}/manager-choice")
async def submit_manager_choice(decision_id: str, request: ManagerChoiceRequest):
    """Submit hire_external or promote_internal; runs post-decision bias agents then logs."""
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    if request.manager_choice == "promote_internal":
        if not request.target_employee_id:
            raise HTTPException(status_code=400, detail="Select a team member for promote internally.")
        if not (request.upskill_plan or "").strip():
            raise HTTPException(status_code=400, detail="Provide an upskill plan for promote internally.")

    snap = _db.get_workflow_snapshot(decision_id)
    state: TalentDecisionState = _load_state_snapshot(snap) if snap else {}
    if not state and decision_id in _reflection_pending:
        state = dict(_reflection_pending[decision_id])

    if not state:
        raise HTTPException(
            status_code=404,
            detail="No workflow snapshot for this decision. Run Gap Analysis first.",
        )

    primary = state.get("primary_path") or ClarityTalentAgents._primary_path_from_action(
        state.get("recommended_action", "")
    )
    override = not _primary_path_matches(request.manager_choice, primary)
    if override and not (request.manager_override_reason or "").strip():
        raise HTTPException(status_code=400, detail="Override reason required when choice differs from AI primary path.")

    state["manager_final_decision"] = request.manager_choice
    state["manager_reasoning"] = request.manager_reasoning
    state["manager_override_reason"] = request.manager_override_reason if override else None
    state["upskill_plan"] = request.upskill_plan
    if request.manager_choice == "promote_internal":
        fr = state.get("final_recommendation") or {}
        if not isinstance(fr, dict):
            fr = {}
        fr["target_employee_id"] = request.target_employee_id
        fr["target_employee_name"] = request.target_employee_name
        fr["action"] = "promote_internal"
        state["final_recommendation"] = fr

    final_state = run_post_manager_choice_pipeline(state)
    _save_manager_choice_log(decision_id, final_state, request)
    _db.resolve_workflow_snapshot(decision_id)
    if decision_id in _reflection_pending:
        del _reflection_pending[decision_id]
    _db.resolve_reflection(decision_id)

    post = final_state.get("post_decision_bias") or {}
    return {
        "decision_id": decision_id,
        "manager_choice": request.manager_choice,
        "status": final_state.get("status"),
        "post_decision_bias_score": post.get("score"),
        "coaching_notes": post.get("coaching_notes"),
        "override_vs_ai": post.get("override_vs_ai", override),
        "recurring_patterns": final_state.get("manager_patterns", []),
    }


@router.get("/decisions/unified-history")
async def get_unified_decision_history(manager_id: Optional[str] = "mgr_001", limit: int = 100):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return {"decisions": _db.get_unified_decision_history(manager_id, limit)}


@router.get("/decisions/history")
async def get_decision_history(manager_id: Optional[str] = None, limit: int = 50):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return {"decisions": _db.get_talent_decision_history(manager_id, limit)}


@router.get("/reflections/queue")
async def get_reflection_queue():
    # Durable queue from DB (survives restarts) so the dashboard count is reliable.
    rows = _db.get_pending_reflections() if _db else []
    items = []
    for i, r in enumerate(rows):
        items.append({
            "decision_id": r.get("decision_id"),
            "priority": r.get("priority", "medium"),
            "business_goal": r.get("business_goal", ""),
            "bias_risk_score": r.get("bias_risk_score", 0.0),
            "bias_categories": r.get("bias_categories", []),
            "ai_recommendation": r.get("ai_recommendation"),
            "reflection_questions": r.get("reflection_questions", []),
            "waiting_since": r.get("created_at"),
            "queue_position": i + 1,
        })
    return {"pending_reflections": len(items), "items": items}


@router.get("/reflections/{decision_id}")
async def get_reflection_detail(decision_id: str):
    if decision_id not in _reflection_pending:
        raise HTTPException(status_code=404, detail="Reflection not found")
    state = _reflection_pending[decision_id]
    return {
        "decision_id": decision_id,
        "business_goal": state.get("business_goal"),
        "final_recommendation": state.get("final_recommendation"),
        "bias_risk_score": state.get("bias_risk_score"),
        "bias_categories": state.get("bias_categories"),
        "reflection_questions": state.get("reflection_questions"),
        "gap_analysis": state.get("gap_analysis"),
        "summary": state.get("hitl_review_prompt"),
    }


@router.post("/reflections/{decision_id}/submit")
async def submit_reflection(decision_id: str, request: ReflectionSubmitRequest):
    if decision_id not in _reflection_pending:
        raise HTTPException(status_code=404, detail="Reflection not found")
    if not _workflow:
        raise HTTPException(status_code=503, detail="Workflow not initialized")

    pending = _reflection_pending[decision_id]
    final_state = resume_from_reflection(
        _workflow, decision_id, request.decision, request.notes,
        request.manager_name, request.confidence_override, pending,
    )
    del _reflection_pending[decision_id]
    if _db:
        _db.resolve_reflection(decision_id)
    return {"decision_id": decision_id, "status": final_state.get("status"), "manager_decision": request.decision}


@router.post("/reconsiderations/submit")
async def submit_reconsideration(submission: ReconsiderationSubmission):
    if not _workflow:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    state: TalentDecisionState = {
        "decision_id": submission.decision_id,
        "content_id": submission.decision_id,
        "is_reconsideration": True,
        "is_appeal": True,
        "reconsideration_reason": submission.reconsideration_reason,
        "appeal_reason": submission.reconsideration_reason,
        "manager_id": submission.manager_id,
        "agent_decisions": [],
        "status": TalentDecisionStatus.SUBMITTED.value,
    }
    final_state = _run_talent_workflow(state)
    return {"decision_id": submission.decision_id, "status": final_state.get("status")}


@router.get("/team/members")
async def get_team_members(team_id: str = "team_alpha"):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    team = _db.get_team(team_id)
    members = _db.get_team_members(team_id)
    return {"team": team, "members": members, "count": len(members)}


@router.post("/gap-analysis/run")
async def run_gap_analysis(submission: TalentDecisionSubmission):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    members = _db.get_team_members(submission.team_id)
    if not members:
        raise HTTPException(
            status_code=404,
            detail=f"No team members found for '{submission.team_id}'. Run: python scripts/seed_team_data.py",
        )

    team = _db.get_team(submission.team_id)
    if team:
        submission.team_name = team.get("team_name", submission.team_name)
        if not submission.business_goal.strip():
            submission.business_goal = team.get("business_goal", submission.business_goal)

    submission.decision_type = "gap_analysis"
    return await submit_talent_decision(submission)


@router.get("/recommendations/latest")
async def get_latest_recommendation(manager_id: str = "mgr_001"):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    history = _db.get_talent_decision_history(manager_id, limit=1)
    if not history:
        return {"message": "No decisions yet"}
    latest = history[0]
    import json
    try:
        gaps = json.loads(latest.get("gap_analysis_json") or "[]")
    except Exception:
        gaps = []
    try:
        final_rec = json.loads(latest.get("ai_recommendation_json") or "{}")
    except Exception:
        final_rec = {}
    critical_gaps = [
        _capability_label(g) for g in gaps
        if isinstance(g, dict) and g.get("severity") == "critical"
    ]
    return {
        "decision_id": latest.get("decision_id"),
        "recommended_action": latest.get("recommended_action"),
        "business_goal": latest.get("business_goal"),
        "bias_risk_score": latest.get("bias_risk_score"),
        "final_recommendation": final_rec,
        "gap_analysis": gaps,
        "critical_gaps": critical_gaps,
    }


@router.get("/training/recommendations")
async def get_training_recommendations(manager_id: str = "mgr_001"):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return {"recommendations": _db.get_training_recommendations(manager_id)}


@router.post("/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = None,
    role_id: Optional[str] = None,
):
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "txt"
    if ext not in ("pdf", "docx", "txt"):
        raise HTTPException(status_code=400, detail="Supported types: pdf, docx, txt")

    upload_dir = Path("uploads/resumes")
    upload_dir.mkdir(parents=True, exist_ok=True)
    resume_id = f"resume_{uuid.uuid4().hex[:12]}"
    candidate_id = candidate_id or f"cand_{uuid.uuid4().hex[:8]}"
    file_path = upload_dir / f"{resume_id}.{ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    raw_text = extract_resume_text(str(file_path), ext)
    anonymized = build_anonymized_profile(raw_text, candidate_id)

    _db.save_candidate_resume({
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "role_id": role_id,
        "filename": file.filename,
        "file_type": ext,
        "raw_text": raw_text,
        "parsed_profile": {"raw_length": len(raw_text)},
        "anonymized_profile": anonymized,
    })

    return {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "filename": file.filename,
        "file_type": ext,
        "text_length": len(raw_text),
        "anonymized_profile": anonymized,
    }


@router.get("/analytics/summary")
async def analytics_summary():
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _db.get_talent_analytics_summary()


@router.get("/analytics/gap-summary")
async def analytics_gap_summary():
    history = _db.get_talent_decision_history(limit=100) if _db else []
    critical_total = moderate_total = 0
    for h in history:
        try:
            import json
            gaps = json.loads(h.get("gap_analysis_json") or "[]")
            critical_total += sum(1 for g in gaps if g.get("severity") == "critical")
            moderate_total += sum(1 for g in gaps if g.get("severity") == "moderate")
        except Exception:
            pass
    return {
        "critical_gap_count": critical_total,
        "moderate_gap_count": moderate_total,
        "decisions_analyzed": len(history),
    }


@router.get("/analytics/bias-summary")
async def analytics_bias_summary():
    history = _db.get_talent_decision_history(limit=100) if _db else []
    import json
    categories: Dict[str, int] = {}
    scores = []
    for h in history:
        scores.append(h.get("bias_risk_score") or 0)
        try:
            for cat in json.loads(h.get("bias_categories_json") or "[]"):
                categories[cat] = categories.get(cat, 0) + 1
        except Exception:
            pass
    return {
        "avg_bias_risk_score": sum(scores) / len(scores) if scores else 0,
        "most_common_bias_categories": sorted(categories.items(), key=lambda x: -x[1])[:10],
        "decisions_analyzed": len(history),
    }


@router.get("/analytics/manager-patterns")
async def analytics_manager_patterns(manager_id: str = "mgr_001"):
    history = _db.get_talent_decision_history(manager_id, limit=50) if _db else []
    import json
    patterns: Dict[str, int] = {}
    overrides = 0
    for h in history:
        if h.get("manager_override_reason"):
            overrides += 1
        try:
            for p in json.loads(h.get("manager_patterns_json") or "[]"):
                pt = p.get("pattern", "unknown") if isinstance(p, dict) else str(p)
                patterns[pt] = patterns.get(pt, 0) + 1
        except Exception:
            pass
    return {
        "manager_id": manager_id,
        "decisions_logged": len(history),
        "override_rate": overrides / len(history) if history else 0,
        "recurring_patterns": patterns,
    }


@router.get("/analytics/resume-funnel")
async def analytics_resume_funnel():
    if not _db:
        return {"resumes_uploaded": 0}
    with _db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM candidate_resumes")
        uploaded = cursor.fetchone()["cnt"]
    history = _db.get_talent_decision_history(limit=100)
    shortlisted = sum(1 for h in history if h.get("selected_candidate_id"))
    return {
        "resumes_uploaded": uploaded,
        "candidates_shortlisted": shortlisted,
        "evidence_based_scoring_rate": 0.85,
        "anonymized_screening_usage": True,
    }
