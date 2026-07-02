"""
Bias-reduction hiring pipeline API routes.

Flow: resume upload -> extract -> JD rubric -> scorecard -> manager decision
-> decision_events -> dashboard metrics + warning flags.
"""

import asyncio
import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..hiring.hiring_pipeline import (
    extract_candidate_profile,
    extract_job_rubric,
    generate_scorecard,
    detect_vague_language,
    is_override,
    count_evidence,
)
from ..hiring.hiring_metrics import (
    compute_metrics,
    compute_warning_flags,
    compute_demographic_fairness,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hiring", tags=["Bias-Reduction Hiring"])

_db = None


def init_hiring_routes(db):
    global _db
    _db = db


def _require_db():
    if not _db:
        raise HTTPException(status_code=503, detail="Database not initialized")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class GenerateScorecardsRequest(BaseModel):
    business_goal: str = ""
    job_description_text: str = ""
    required_capabilities: List[Any] = Field(default_factory=list)
    resume_ids: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    department: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None
    job_id: Optional[str] = None  # reuse an existing job/rubric if provided


class DecisionRequest(BaseModel):
    application_id: str
    candidate_id: str
    job_id: str
    decision_type: str = Field("resume_screen", description="resume_screen|shortlist|interview|offer|hire|reject|promotion|compensation|project_assignment")
    decision_stage: str = Field("resume_screen", description="applied|resume_screen|shortlisted|interview|finalist|offer|hired|rejected")
    human_decision: str = Field(..., description="Hire|Reject|Interview|Hold|Move to next stage|Offer")
    generated_recommendation: Optional[str] = None
    rubric_score_at_decision: Optional[float] = None
    decision_maker_id: str = "mgr_001"
    decision_reason: str = ""
    evidence_count: int = 0


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------
@router.post("/jobs/rubric")
async def build_job_rubric(request: GenerateScorecardsRequest):
    """Convert a JD + required capabilities into a structured, persisted rubric."""
    _require_db()
    job = extract_job_rubric(
        job_description_text=request.job_description_text,
        required_capabilities=request.required_capabilities,
        business_goal=request.business_goal,
        title=request.title,
        department=request.department,
        level=request.level,
        location=request.location,
    )
    _db.save_job(job)
    return job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    _require_db()
    job = _db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Resume extraction
# ---------------------------------------------------------------------------
@router.post("/resumes/{resume_id}/extract")
async def extract_resume(resume_id: str):
    """Extract a structured, bias-safe candidate profile from a stored resume."""
    _require_db()
    resume = _get_resume(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    profile = extract_candidate_profile(
        raw_text=resume.get("raw_text", ""),
        candidate_id=resume.get("candidate_id"),
        resume_id=resume_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=422,
            detail="extraction_failed: no model produced valid structured data for this resume",
        )
    _db.save_candidate(profile)
    return profile


def _get_resume(resume_id: str) -> Optional[Dict[str, Any]]:
    with _db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidate_resumes WHERE resume_id = ?", (resume_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Scorecards (one-call MVP: rubric -> extract -> score -> persist)
# ---------------------------------------------------------------------------
@router.post("/scorecards/generate")
async def generate_scorecards(request: GenerateScorecardsRequest):
    """
    MVP pipeline in one call:
    - build (or load) the job rubric
    - for each resume: extract candidate -> create application -> score
    - persist jobs, candidates, applications, scorecards
    """
    _require_db()

    if request.job_id:
        job = _db.get_job(request.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job_id not found")
    else:
        job = extract_job_rubric(
            job_description_text=request.job_description_text,
            required_capabilities=request.required_capabilities,
            business_goal=request.business_goal,
            title=request.title,
            department=request.department,
            level=request.level,
            location=request.location,
        )
        _db.save_job(job)

    if not request.resume_ids:
        raise HTTPException(status_code=400, detail="No resume_ids provided")

    total = len(request.resume_ids)
    # Resumes are processed concurrently to cut wall-clock time. Bounded by
    # HIRING_MAX_CONCURRENCY so free-tier rate limits can be respected (set to 1
    # to force sequential processing).
    max_conc = max(1, int(os.getenv("HIRING_MAX_CONCURRENCY", "4")))
    logger.info(
        "[scorecards/generate] START job_id=%s resumes=%d max_concurrency=%d "
        "(each resume = 1 extract + 1 score LLM call)",
        job["job_id"], total, max_conc,
    )
    batch_start = time.perf_counter()

    errors = []
    prepared = []
    for idx, resume_id in enumerate(request.resume_ids, start=1):
        resume = _get_resume(resume_id)
        if not resume:
            logger.warning("[scorecards/generate] resume %d/%d NOT FOUND resume_id=%s", idx, total, resume_id)
            errors.append({"resume_id": resume_id, "error": "resume not found"})
            continue
        prepared.append((idx, resume_id, resume))

    semaphore = asyncio.Semaphore(max_conc)

    async def _process(idx, resume_id, resume):
        async with semaphore:
            logger.info("[scorecards/generate] resume %d/%d START resume_id=%s", idx, total, resume_id)

            def _work():
                candidate = extract_candidate_profile(
                    raw_text=resume.get("raw_text", ""),
                    candidate_id=resume.get("candidate_id"),
                    resume_id=resume_id,
                )
                if candidate is None:
                    return {"idx": idx, "resume_id": resume_id, "status": "extraction_failed"}

                application_id = f"app_{uuid.uuid4().hex[:8]}"
                scorecard = generate_scorecard(candidate, job)
                if scorecard is None:
                    return {
                        "idx": idx, "resume_id": resume_id, "status": "scorecard_failed",
                        "candidate": candidate, "application_id": application_id,
                    }

                scorecard["application_id"] = application_id
                return {
                    "idx": idx, "resume_id": resume_id, "status": "ok",
                    "candidate": candidate, "application_id": application_id, "scorecard": scorecard,
                }

            result = await asyncio.to_thread(_work)
            logger.info(
                "[scorecards/generate] resume %d/%d DONE resume_id=%s status=%s",
                idx, total, resume_id, result.get("status"),
            )
            return result

    processed = await asyncio.gather(
        *[_process(idx, rid, res) for (idx, rid, res) in prepared],
        return_exceptions=True,
    )

    # Persist sequentially (SQLite-safe), preserving upload order.
    # Only scorecards that passed schema validation are saved/returned.
    results_by_idx = {}
    for item in processed:
        if isinstance(item, Exception):
            logger.error("[scorecards/generate] a resume raised: %s", item)
            errors.append({"error": str(item)})
            continue

        status = item.get("status")
        if status == "extraction_failed":
            errors.append({"resume_id": item["resume_id"], "error": "extraction_failed"})
            continue

        # Extraction succeeded: persist candidate + application for traceability.
        candidate = item["candidate"]
        application_id = item["application_id"]
        _db.save_candidate(candidate)
        _db.save_application({
            "application_id": application_id,
            "candidate_id": candidate["candidate_id"],
            "job_id": job["job_id"],
            "source": "upload",
            "current_stage": "resume_screen",
            "status": "active",
        })

        if status == "scorecard_failed":
            errors.append({
                "resume_id": item["resume_id"],
                "candidate_id": candidate["candidate_id"],
                "error": "scorecard_failed",
            })
            continue

        scorecard = item["scorecard"]
        _db.save_scorecard(scorecard)
        results_by_idx[item["idx"]] = _public_scorecard(scorecard, candidate, application_id, index=item["idx"])

    results = [results_by_idx[k] for k in sorted(results_by_idx)]

    logger.info(
        "[scorecards/generate] DONE job_id=%s scored=%d errors=%d total_time=%.1fs",
        job["job_id"], len(results), len(errors), time.perf_counter() - batch_start,
    )

    return {
        "job_id": job["job_id"],
        "job": job,
        "scorecards": results,
        "errors": errors,
    }


@router.get("/jobs/{job_id}/scorecards")
async def get_scorecards(job_id: str):
    _require_db()
    scorecards = _db.get_scorecards_for_job(job_id)
    enriched = []
    for i, sc in enumerate(scorecards, start=1):
        candidate = _db.get_candidate(sc.get("candidate_id")) or {}
        enriched.append(_public_scorecard(sc, candidate, sc.get("application_id"), index=i))
    return {"job_id": job_id, "scorecards": enriched, "count": len(enriched)}


def _public_scorecard(scorecard, candidate, application_id, index=None):
    """Anonymized, UI-ready scorecard payload."""
    label = f"Candidate {str(index).zfill(3)}" if index else f"Candidate {(candidate.get('candidate_id') or '')[-4:]}"
    return {
        "scorecard_id": scorecard.get("scorecard_id"),
        "application_id": application_id,
        "candidate_id": scorecard.get("candidate_id"),
        "candidate_label": label,
        "job_id": scorecard.get("job_id"),
        "total_score": scorecard.get("total_score"),
        "criteria_scores": scorecard.get("criteria_scores", []),
        "strengths": scorecard.get("strengths", []),
        "concerns": scorecard.get("concerns", []),
        "missing_requirements": scorecard.get("missing_requirements", []),
        "generated_recommendation": scorecard.get("generated_recommendation"),
        "evidence_count": count_evidence(scorecard),
        "extraction_confidence": candidate.get("extraction_confidence"),
    }


# ---------------------------------------------------------------------------
# Decision logging
# ---------------------------------------------------------------------------
@router.post("/decisions")
async def log_decision(request: DecisionRequest):
    """Log a human hiring/promotion decision as a decision_event."""
    _require_db()

    scorecard = _db.get_scorecard_for_application(request.application_id)
    generated = request.generated_recommendation or (scorecard.get("generated_recommendation") if scorecard else None)
    score = request.rubric_score_at_decision
    if score is None and scorecard:
        score = scorecard.get("total_score")
    evidence_count = request.evidence_count or (count_evidence(scorecard) if scorecard else 0)

    override_flag = is_override(generated, request.human_decision)
    vague_flag, vague_terms = detect_vague_language(request.decision_reason)

    if override_flag and not request.decision_reason.strip():
        raise HTTPException(
            status_code=400,
            detail="A job-related reason is required when overriding the recommendation.",
        )

    decision_id = f"dec_{uuid.uuid4().hex[:10]}"
    event = {
        "decision_id": decision_id,
        "application_id": request.application_id,
        "candidate_id": request.candidate_id,
        "job_id": request.job_id,
        "decision_type": request.decision_type,
        "decision_stage": request.decision_stage,
        "decision_outcome": request.human_decision,
        "decision_maker_id": request.decision_maker_id,
        "rubric_score_at_decision": score,
        "generated_recommendation": generated,
        "human_decision": request.human_decision,
        "override_flag": override_flag,
        "decision_reason": request.decision_reason,
        "vague_reason_flag": vague_flag,
        "evidence_count": evidence_count,
    }
    _db.save_decision_event(event)

    # Advance the application stage to reflect the outcome.
    stage_map = {
        "hire": "hired",
        "offer": "offer",
        "interview": "interview",
        "move to next stage": "shortlisted",
        "reject": "rejected",
        "hold": "resume_screen",
    }
    new_stage = stage_map.get(request.human_decision.strip().lower())
    if new_stage:
        status = "rejected" if new_stage == "rejected" else "active"
        _db.update_application_stage(request.application_id, new_stage, status)

    return {
        "decision_id": decision_id,
        "override_flag": override_flag,
        "vague_reason_flag": vague_flag,
        "vague_terms": vague_terms,
        "status": "logged",
    }


@router.get("/decisions")
async def get_decisions(job_id: Optional[str] = None, limit: int = 500):
    _require_db()
    return {"decisions": _db.get_decision_events(job_id, limit)}


# ---------------------------------------------------------------------------
# Dashboard metrics + warnings
# ---------------------------------------------------------------------------
@router.get("/metrics")
async def get_dashboard_metrics(job_id: Optional[str] = None):
    _require_db()
    events = _db.get_decision_events(job_id, limit=2000)
    scorecards = _db.get_scorecards_for_job(job_id) if job_id else _all_scorecards()
    return compute_metrics(events, scorecards)


@router.get("/warnings")
async def get_warning_flags(job_id: Optional[str] = None):
    _require_db()
    events = _db.get_decision_events(job_id, limit=2000)
    scorecards = _db.get_scorecards_for_job(job_id) if job_id else _all_scorecards()
    return {"warnings": compute_warning_flags(events, scorecards)}


class DemographicFairnessRequest(BaseModel):
    job_id: Optional[str] = None
    demographics: Dict[str, str] = Field(default_factory=dict, description="candidate_id -> voluntary self-reported group")


class DemographicRequest(BaseModel):
    self_reported_group: str = Field(..., description="Voluntary, self-reported group label")
    job_id: Optional[str] = None
    consent: bool = True


@router.post("/metrics/demographic-fairness")
async def demographic_fairness(request: DemographicFairnessRequest):
    """Optional. Only uses voluntary self-reported demographics; never inferred.
    Falls back to stored, consented demographics when none are supplied inline."""
    _require_db()
    events = _db.get_decision_events(request.job_id, limit=2000)
    demographics = request.demographics or _db.get_candidate_demographics(request.job_id)
    return compute_demographic_fairness(events, demographics)


@router.get("/metrics/demographic-fairness")
async def demographic_fairness_get(job_id: Optional[str] = None):
    """Read-only fairness metrics from stored voluntary demographics."""
    _require_db()
    events = _db.get_decision_events(job_id, limit=2000)
    demographics = _db.get_candidate_demographics(job_id)
    return compute_demographic_fairness(events, demographics)


@router.post("/candidates/{candidate_id}/demographics")
async def set_candidate_demographics(candidate_id: str, request: DemographicRequest):
    """Record a candidate's voluntary, consented self-reported demographic group."""
    _require_db()
    if not request.consent:
        raise HTTPException(status_code=400, detail="Consent is required to store demographic data.")
    _db.set_candidate_demographic(candidate_id, request.self_reported_group, request.job_id, request.consent)
    return {"candidate_id": candidate_id, "status": "stored"}


def _all_scorecards() -> List[Dict[str, Any]]:
    with _db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scorecards ORDER BY total_score DESC")
        return [_db._row_to_scorecard(r) for r in cursor.fetchall()]
