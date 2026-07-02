"""
Bias-reduction hiring pipeline.

Turns resumes + job descriptions into structured, evidence-based candidate
scorecards. All LLM prompts are constrained to job-relevant, explicitly-present
information and are explicitly forbidden from inferring protected traits.

Reliability model (per user requirement):
- Pinned free models are tried in order: OPENROUTER_FREE_MODEL, then
  OPENROUTER_FALLBACK_MODEL, then OPENROUTER_FALLBACK_MODEL_2.
- Each model is attempted twice: first with a strict JSON-schema response_format,
  then (retry) with a plain prompt in case the model rejects structured output.
- Every response is parsed AND validated against a Pydantic schema.
- If nothing validates, extraction/scorecard generation returns None (the caller
  records extraction_failed / scorecard_failed). We NEVER save a placeholder
  score-0 / Reject / empty-evidence scorecard just because parsing failed.
"""

import json
import logging
import os
import random
import re
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple, Callable

from pydantic import BaseModel, ValidationError

from ..core.llm_provider import get_chat_model
from ..core.llm_retry import invoke_llm

logger = logging.getLogger(__name__)

# Recommendation vocabulary (ordered strongest -> weakest)
RECOMMENDATION_LEVELS = ["Strong interview", "Interview", "Hold", "Reject"]

# Vague / non-job-related language that should be discouraged in reasons.
VAGUE_TERMS = [
    "culture fit", "not ready", "attitude", "polish", "executive presence",
    "too quiet", "too aggressive", "gut feeling", "not a fit", "personality",
    "vibe", "likeable", "likable", "overqualified",
]

# Shared safety clause injected into every extraction/scoring prompt.
_BIAS_SAFETY_RULES = """
STRICT SAFETY RULES (must follow):
- Only use information explicitly present in the provided text.
- Do NOT infer or output protected traits: gender, ethnicity, race, age,
  religion, nationality, disability, marital status, or personality.
- Do NOT infer demographics from names, photos, schools, language, location,
  or resume style.
- Do NOT judge personality, attitude, culture fit, or "polish".
- If information is missing, use null or an empty array.
- Keep a short evidence snippet for every extracted claim so it is traceable.
- Output ONLY valid JSON. No prose, no markdown, no commentary.
"""


# ===========================================================================
# Validation schemas (application-side validation via Pydantic)
# ===========================================================================
class _EvidenceItem(BaseModel):
    value: str
    evidence_text: str = ""


class _ResumeModel(BaseModel):
    skills: List[_EvidenceItem] = []
    years_experience: Optional[float] = None
    education: List[_EvidenceItem] = []
    work_experience: List[_EvidenceItem] = []
    projects: List[_EvidenceItem] = []
    certifications: List[_EvidenceItem] = []
    leadership_experience: List[_EvidenceItem] = []
    domain_experience: List[_EvidenceItem] = []
    extraction_confidence: float = 0.0


class _CriteriaScoreModel(BaseModel):
    criterion: str
    score: float
    max_score: float = 100
    weight: float = 0
    evidence: List[str] = []
    explanation: str = ""


class _ScorecardModel(BaseModel):
    criteria_scores: List[_CriteriaScoreModel]
    missing_requirements: List[str] = []
    strengths: List[str] = []
    concerns: List[str] = []


class _RubricModel(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None
    must_have_criteria: List[str] = []
    nice_to_have_criteria: List[str] = []
    responsibilities: List[str] = []
    rubric_weights: Dict[str, int] = {}


def _dump(model: BaseModel) -> Dict[str, Any]:
    """Pydantic v2/v1 compatible dict export."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ===========================================================================
# Strict JSON schemas for OpenRouter response_format
# ===========================================================================
_EVIDENCE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "string"},
        "evidence_text": {"type": "string"},
    },
    "required": ["value", "evidence_text"],
    "additionalProperties": False,
}


def _evidence_array():
    return {"type": "array", "items": _EVIDENCE_ITEM_SCHEMA}


_RESUME_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "candidate_profile",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "skills": _evidence_array(),
                "years_experience": {"type": ["number", "null"]},
                "education": _evidence_array(),
                "work_experience": _evidence_array(),
                "projects": _evidence_array(),
                "certifications": _evidence_array(),
                "leadership_experience": _evidence_array(),
                "domain_experience": _evidence_array(),
                "extraction_confidence": {"type": "number"},
            },
            "required": [
                "skills", "years_experience", "education", "work_experience",
                "projects", "certifications", "leadership_experience",
                "domain_experience", "extraction_confidence",
            ],
            "additionalProperties": False,
        },
    },
}

_SCORECARD_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "candidate_scorecard",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "criteria_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "criterion": {"type": "string"},
                            "score": {"type": "number"},
                            "max_score": {"type": "number"},
                            "weight": {"type": "number"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "explanation": {"type": "string"},
                        },
                        "required": ["criterion", "score", "max_score", "weight", "evidence", "explanation"],
                        "additionalProperties": False,
                    },
                },
                "missing_requirements": {"type": "array", "items": {"type": "string"}},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "concerns": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["criteria_scores", "missing_requirements", "strengths", "concerns"],
            "additionalProperties": False,
        },
    },
}


# ===========================================================================
# Model-fallback + structured generation
# ===========================================================================
def _model_chain() -> List[str]:
    """Ordered list of pinned free models to try."""
    chain = [
        os.getenv("OPENROUTER_FREE_MODEL"),
        os.getenv("OPENROUTER_FALLBACK_MODEL"),
        os.getenv("OPENROUTER_FALLBACK_MODEL_2"),
    ]
    seen, ordered = set(), []
    for m in chain:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered or ["openrouter/free"]


def _response_text(response) -> str:
    return response.content if hasattr(response, "content") else str(response)


def _is_rate_limited(exc: Exception) -> bool:
    """True when an exception is an upstream 429 / rate-limit error."""
    s = str(exc).lower()
    return (
        "429" in s
        or "too many requests" in s
        or "rate-limit" in s
        or "rate limited" in s
        or "temporarily rate" in s
    )


def _invoke_with_backoff(llm, prompt, label: str, model: str):
    """Invoke an LLM, retrying the SAME model on 429 with exponential backoff +
    jitter. This keeps the high-quality primary model instead of failing over to
    a weaker one just because it is momentarily rate-limited."""
    retries = int(os.getenv("LLM_RATE_LIMIT_RETRIES", "4"))
    base = float(os.getenv("LLM_RATE_LIMIT_BACKOFF", "2.5"))
    last_exc = None
    for i in range(retries + 1):
        try:
            return invoke_llm(llm, prompt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_rate_limited(exc) and i < retries:
                wait = base * (2 ** i) + random.uniform(0, base)
                logger.info(
                    "[%s] model=%s rate-limited (429); backoff %.1fs then retry (%d/%d)",
                    label, model, wait, i + 1, retries,
                )
                time.sleep(wait)
                continue
            raise
    raise last_exc


def _repair_json(raw: str) -> Optional[Dict[str, Any]]:
    """Best-effort structural recovery of malformed JSON (fences, outer braces,
    trailing commas). Never injects data."""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _try_parse(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return _repair_json(raw)


def _generate_structured(
    prompt: str,
    json_schema: Optional[Dict[str, Any]],
    validate: Callable[[Dict[str, Any]], Dict[str, Any]],
    label: str,
) -> Optional[Dict[str, Any]]:
    """Try each pinned model (strict schema, then plain retry), parse + validate.

    Returns a validated dict, or None if every model/attempt fails.
    """
    for model in _model_chain():
        # attempt 1: strict JSON schema; attempt 2 (retry): plain prompt.
        for attempt, use_schema in ((1, True), (2, False)):
            rf = json_schema if (use_schema and json_schema) else None
            t0 = time.perf_counter()
            try:
                llm = get_chat_model(model_name=model, response_format=rf)
                raw = _response_text(_invoke_with_backoff(llm, prompt, label, model))
                elapsed = time.perf_counter() - t0
                data = _try_parse(raw)
                if data is None:
                    logger.warning(
                        "[%s] model=%s attempt=%d(schema=%s) NON-JSON in %.1fs. Raw: %s",
                        label, model, attempt, use_schema, elapsed,
                        (raw or "").replace("\n", " ")[:200],
                    )
                    continue
                validated = validate(data)
                logger.info(
                    "[%s] model=%s attempt=%d(schema=%s) VALID in %.1fs",
                    label, model, attempt, use_schema, elapsed,
                )
                return validated
            except (ValidationError, ValueError) as exc:
                logger.warning(
                    "[%s] model=%s attempt=%d(schema=%s) INVALID after %.1fs: %s",
                    label, model, attempt, use_schema, time.perf_counter() - t0, str(exc)[:200],
                )
                continue
            except Exception as exc:  # noqa: BLE001  (timeout / transport / API error)
                logger.warning(
                    "[%s] model=%s attempt=%d(schema=%s) CALL FAILED after %.1fs: %s",
                    label, model, attempt, use_schema, time.perf_counter() - t0, str(exc)[:200],
                )
                continue
    logger.error("[%s] ALL models/attempts failed — no valid result", label)
    return None


# ===========================================================================
# 1. Resume extraction
# ===========================================================================
def _validate_resume(data: Dict[str, Any]) -> Dict[str, Any]:
    return _dump(_ResumeModel(**data))


def extract_candidate_profile(
    raw_text: str,
    candidate_id: str = None,
    resume_id: str = None,
) -> Optional[Dict[str, Any]]:
    """Extract a structured, bias-safe candidate profile.

    Returns None (extraction_failed) if the resume is empty or no model produces
    valid, non-empty structured data.
    """
    candidate_id = candidate_id or f"cand_{uuid.uuid4().hex[:8]}"
    text_chars = len(raw_text or "")
    logger.info("[resume-extract] START candidate=%s resume=%s text_chars=%d", candidate_id, resume_id, text_chars)

    if not (raw_text or "").strip():
        logger.warning(
            "[resume-extract] EMPTY resume text candidate=%s resume=%s (scanned/image PDF?) -> extraction_failed",
            candidate_id, resume_id,
        )
        return None

    prompt = f"""
You are a resume data extraction engine for a bias-reduction hiring system.
{_BIAS_SAFETY_RULES}

Extract structured data from the resume text below.

Resume text:
\"\"\"
{(raw_text or '')[:12000]}
\"\"\"

Return JSON only, in this exact shape:
{{
  "skills": [{{"value": "...", "evidence_text": "..."}}],
  "years_experience": 0,
  "education": [{{"value": "...", "evidence_text": "..."}}],
  "work_experience": [{{"value": "...", "evidence_text": "..."}}],
  "projects": [{{"value": "...", "evidence_text": "..."}}],
  "certifications": [{{"value": "...", "evidence_text": "..."}}],
  "leadership_experience": [{{"value": "...", "evidence_text": "..."}}],
  "domain_experience": [{{"value": "...", "evidence_text": "..."}}],
  "extraction_confidence": 0.0
}}
- years_experience: a single number if clearly stated or derivable from dates, else null.
- Every list item must include evidence_text quoting the resume.
- extraction_confidence is 0..1 reflecting how much was explicitly present.
"""
    data = _generate_structured(prompt, _RESUME_JSON_SCHEMA, _validate_resume, "resume-extract")
    if data is None:
        logger.error("[resume-extract] FAILED candidate=%s -> extraction_failed", candidate_id)
        return None

    def _clean(items):
        return [{"value": i["value"], "evidence_text": i.get("evidence_text", "")}
                for i in (items or []) if i.get("value")]

    profile = {
        "candidate_id": candidate_id,
        "resume_id": resume_id,
        "extracted_skills": _clean(data.get("skills")),
        "years_experience": data.get("years_experience"),
        "education": _clean(data.get("education")),
        "work_experience": _clean(data.get("work_experience")),
        "projects": _clean(data.get("projects")),
        "certifications": _clean(data.get("certifications")),
        "leadership_experience": _clean(data.get("leadership_experience")),
        "domain_experience": _clean(data.get("domain_experience")),
        "extraction_confidence": float(data.get("extraction_confidence") or 0.0),
    }

    has_content = any([
        profile["extracted_skills"], profile["work_experience"], profile["education"],
        profile["projects"], profile["certifications"],
        profile["leadership_experience"], profile["domain_experience"],
    ])
    # A non-trivial resume that yields nothing indicates a model failure, not an
    # empty resume — treat as extraction_failed rather than saving junk.
    if not has_content and text_chars > 200:
        logger.error(
            "[resume-extract] candidate=%s produced EMPTY extraction from %d chars -> extraction_failed",
            candidate_id, text_chars,
        )
        return None

    logger.info(
        "[resume-extract] DONE candidate=%s skills=%d work=%d education=%d projects=%d "
        "certs=%d leadership=%d domain=%d years=%s confidence=%.2f",
        candidate_id, len(profile["extracted_skills"]), len(profile["work_experience"]),
        len(profile["education"]), len(profile["projects"]), len(profile["certifications"]),
        len(profile["leadership_experience"]), len(profile["domain_experience"]),
        profile["years_experience"], profile["extraction_confidence"],
    )
    return profile


# ===========================================================================
# 2. Job description rubric extraction
# ===========================================================================
def _validate_rubric(data: Dict[str, Any]) -> Dict[str, Any]:
    return _dump(_RubricModel(**data))


def extract_job_rubric(
    job_description_text: str,
    required_capabilities: List[Any] = None,
    business_goal: str = "",
    title: str = None,
    department: str = None,
    level: str = None,
    location: str = None,
) -> Dict[str, Any]:
    """Convert a JD + required capabilities into a structured rubric.

    The rubric always returns a usable result: if all models fail, it is built
    deterministically from the (real, non-hallucinated) required capabilities.
    """
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    caps = required_capabilities or []
    caps_labels = []
    for c in caps:
        if isinstance(c, dict):
            caps_labels.append(c.get("capability") or c.get("skill") or c.get("name") or "")
        elif c:
            caps_labels.append(str(c))
    caps_labels = [c for c in caps_labels if c]

    logger.info("[jd-rubric] START title=%s capabilities=%d jd_chars=%d",
                title or "(from JD)", len(caps_labels), len(job_description_text or ""))

    prompt = f"""
You are a hiring rubric builder for a bias-reduction hiring system.
{_BIAS_SAFETY_RULES}

Convert the following into a structured, job-relevant scoring rubric.

Business goal: {business_goal}

Required capabilities (from gap analysis):
{caps_labels}

Job description text:
\"\"\"
{(job_description_text or '')[:8000]}
\"\"\"

Rules:
- Separate must_have_criteria from nice_to_have_criteria.
- Convert any vague trait (e.g. "good communicator", "culture fit") into an
  OBSERVABLE, job-relevant behavior
  (e.g. "Can clearly explain technical decisions to non-technical stakeholders").
- rubric_weights maps EACH must_have + nice_to_have criterion name to an integer weight.
- The weights MUST total exactly 100.
- Never include protected traits or "culture fit" as criteria.

Return JSON only:
{{
  "title": "...",
  "department": "...",
  "level": "...",
  "location": "...",
  "must_have_criteria": ["..."],
  "nice_to_have_criteria": ["..."],
  "responsibilities": ["..."],
  "rubric_weights": {{"criterion name": 20}}
}}
"""
    # Rubric weights use dynamic keys, which strict json_schema cannot express,
    # so we validate with Pydantic + repair rather than a response_format schema.
    data = _generate_structured(prompt, None, _validate_rubric, "jd-rubric")
    if data is None:
        logger.warning("[jd-rubric] all models failed -> deterministic rubric from required capabilities")
        data = {}

    must_have = [c for c in (data.get("must_have_criteria") or caps_labels) if c]
    nice_to_have = [c for c in (data.get("nice_to_have_criteria") or []) if c]
    weights = _normalize_weights(data.get("rubric_weights") or {}, must_have, nice_to_have)

    logger.info("[jd-rubric] DONE job_id=%s must_have=%d nice_to_have=%d weights_total=%d",
                job_id, len(must_have), len(nice_to_have), sum(weights.values()))

    return {
        "job_id": job_id,
        "title": title or data.get("title") or "Screening role",
        "department": department or data.get("department"),
        "level": level or data.get("level"),
        "location": location or data.get("location"),
        "job_description_text": job_description_text or "",
        "must_have_criteria": must_have,
        "nice_to_have_criteria": nice_to_have,
        "responsibilities": [r for r in (data.get("responsibilities") or []) if r],
        "rubric_weights": weights,
        "rubric_version": "v1",
    }


def _normalize_weights(weights: Dict[str, Any], must_have: List[str], nice_to_have: List[str]) -> Dict[str, int]:
    """Ensure every criterion has a weight and the total is exactly 100."""
    criteria = list(dict.fromkeys([*must_have, *nice_to_have]))
    if not criteria:
        return {}

    clean: Dict[str, float] = {}
    for c in criteria:
        try:
            clean[c] = max(0.0, float(weights.get(c, 0)))
        except (TypeError, ValueError):
            clean[c] = 0.0

    total = sum(clean.values())
    if total <= 0:
        base = {c: (2 if c in must_have else 1) for c in criteria}
        total = sum(base.values())
        clean = dict(base)

    scaled = {c: (v / total) * 100 for c, v in clean.items()}
    rounded = {c: int(round(v)) for c, v in scaled.items()}
    drift = 100 - sum(rounded.values())
    if drift != 0 and rounded:
        top = max(rounded, key=rounded.get)
        rounded[top] += drift
    return rounded


# ===========================================================================
# 3. Candidate-job matching scorecard
# ===========================================================================
def _make_scorecard_validator(weights: Dict[str, int]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _validate(data: Dict[str, Any]) -> Dict[str, Any]:
        model = _ScorecardModel(**data)
        dumped = _dump(model)
        # Reject empty / contentless scorecards so we never persist a placeholder.
        criteria = dumped.get("criteria_scores") or []
        if not criteria or not any((c.get("criterion") or "").strip() for c in criteria):
            raise ValueError("scorecard has no scored criteria")
        return dumped
    return _validate


def generate_scorecard(candidate: Dict[str, Any], job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Score a candidate against a job rubric.

    Returns None (scorecard_failed) if no model produces a valid, non-empty
    scorecard. Never returns a placeholder score-0 card.
    """
    scorecard_id = f"sc_{uuid.uuid4().hex[:8]}"
    weights = job.get("rubric_weights", {}) or {}
    cand_id = candidate.get("candidate_id")

    candidate_view = {
        "skills": [s.get("value") for s in candidate.get("extracted_skills", [])],
        "years_experience": candidate.get("years_experience"),
        "education": [e.get("value") for e in candidate.get("education", [])],
        "work_experience": [w.get("value") for w in candidate.get("work_experience", [])],
        "projects": [p.get("value") for p in candidate.get("projects", [])],
        "certifications": [c.get("value") for c in candidate.get("certifications", [])],
        "leadership_experience": [l.get("value") for l in candidate.get("leadership_experience", [])],
        "domain_experience": [d.get("value") for d in candidate.get("domain_experience", [])],
    }

    logger.info("[scorecard] START candidate=%s job=%s criteria=%d", cand_id, job.get("job_id"), len(weights))

    prompt = f"""
You are a candidate-job matching engine for a bias-reduction hiring system.
{_BIAS_SAFETY_RULES}

Score the candidate against each rubric criterion using ONLY the candidate's
extracted, evidence-based data. Do not make subjective claims about personality,
attitude, culture fit, or protected traits.

Rubric criteria and weights (weights total 100):
{weights}

Must-have criteria: {job.get('must_have_criteria', [])}
Nice-to-have criteria: {job.get('nice_to_have_criteria', [])}

Candidate extracted data:
{candidate_view}

Score EVERY rubric criterion above (use the exact criterion names). Give a score
0..100, evidence quoting the candidate data, and a short factual explanation.

Return JSON only:
{{
  "criteria_scores": [
    {{"criterion": "...", "score": 0, "max_score": 100, "weight": 0,
      "evidence": ["..."], "explanation": "..."}}
  ],
  "missing_requirements": ["..."],
  "strengths": ["..."],
  "concerns": ["..."]
}}
"""
    data = _generate_structured(
        prompt, _SCORECARD_JSON_SCHEMA, _make_scorecard_validator(weights), "scorecard"
    )
    if data is None:
        logger.error("[scorecard] FAILED candidate=%s -> scorecard_failed", cand_id)
        return None

    criteria_scores = _normalize_criteria_scores(data.get("criteria_scores"), weights)
    if not criteria_scores:
        logger.error("[scorecard] candidate=%s produced no usable criteria -> scorecard_failed", cand_id)
        return None

    total_score = _weighted_total(criteria_scores)
    recommendation = recommendation_from_score(total_score)
    logger.info(
        "[scorecard] DONE candidate=%s total_score=%.1f recommendation=%s criteria_scored=%d evidence=%d",
        cand_id, total_score, recommendation, len(criteria_scores),
        sum(len(c.get("evidence", [])) for c in criteria_scores),
    )

    return {
        "scorecard_id": scorecard_id,
        "candidate_id": cand_id,
        "job_id": job.get("job_id"),
        "criteria_scores": criteria_scores,
        "total_score": total_score,
        "missing_requirements": [m for m in (data.get("missing_requirements") or []) if m],
        "strengths": [s for s in (data.get("strengths") or []) if s],
        "concerns": [c for c in (data.get("concerns") or []) if c],
        "generated_recommendation": recommendation,
    }


def _normalize_criteria_scores(raw, weights: Dict[str, int]) -> List[Dict[str, Any]]:
    raw = raw or []
    weights_ci = {str(k).strip().lower(): v for k, v in (weights or {}).items()}
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        criterion = item.get("criterion", "")
        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        weight = weights.get(criterion)
        if weight is None:
            weight = weights_ci.get(str(criterion).strip().lower())
        if weight is None:
            try:
                weight = float(item.get("weight", 0))
            except (TypeError, ValueError):
                weight = 0
        evidence = item.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        out.append({
            "criterion": criterion,
            "score": round(score, 1),
            "max_score": 100,
            "weight": int(weight or 0),
            "evidence": [e for e in evidence if e],
            "explanation": item.get("explanation", ""),
        })
    return out


def _weighted_total(criteria_scores: List[Dict[str, Any]]) -> float:
    if not criteria_scores:
        return 0.0
    total_weight = sum(c.get("weight", 0) for c in criteria_scores)
    if total_weight <= 0:
        scores = [c.get("score", 0) for c in criteria_scores]
        return round(sum(scores) / len(scores), 1) if scores else 0.0
    weighted = sum((c.get("score", 0) * c.get("weight", 0)) for c in criteria_scores)
    return round(weighted / total_weight, 1)


def recommendation_from_score(total_score: float) -> str:
    """Map a 0..100 total score to a generated recommendation."""
    if total_score >= 80:
        return "Strong interview"
    if total_score >= 60:
        return "Interview"
    if total_score >= 40:
        return "Hold"
    return "Reject"


# ===========================================================================
# 4. Decision helpers: override + vague-language detection
# ===========================================================================
ADVANCING_DECISIONS = {"strong interview", "interview", "move to next stage", "shortlist", "advance", "offer", "hire"}
REJECTING_DECISIONS = {"reject", "rejected"}


def detect_vague_language(reason: str) -> Tuple[bool, List[str]]:
    """Return (is_vague, matched_terms) for a decision reason."""
    if not reason:
        return False, []
    lowered = reason.lower()
    matched = [term for term in VAGUE_TERMS if term in lowered]
    return (len(matched) > 0), matched


def is_override(generated_recommendation: str, human_decision: str) -> bool:
    """A human decision overrides when its direction differs from the recommendation."""
    if not generated_recommendation or not human_decision:
        return False
    rec = generated_recommendation.strip().lower()
    human = human_decision.strip().lower()
    rec_advances = rec in {"strong interview", "interview"}
    rec_rejects = rec == "reject"
    rec_holds = rec == "hold"
    if rec_advances and human in REJECTING_DECISIONS:
        return True
    if rec_rejects and human in ADVANCING_DECISIONS:
        return True
    # A "Hold" recommendation is overridden by a decisive hire/offer or a reject.
    if rec_holds and (human in REJECTING_DECISIONS or human in {"hire", "offer"}):
        return True
    return False


def count_evidence(scorecard: Dict[str, Any]) -> int:
    """Count evidence snippets backing a scorecard (for decision auditability)."""
    if not scorecard:
        return 0
    return sum(len(c.get("evidence", []) or []) for c in scorecard.get("criteria_scores", []))
