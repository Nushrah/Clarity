"""
Bias-reduction dashboard metrics and warning flags.

Pure functions computed over decision_events + scorecards. No demographic
inference is ever performed. Optional demographic fairness metrics only run
when voluntary self-reported data is explicitly supplied.
"""

from collections import defaultdict
from typing import Dict, Any, List

from .hiring_pipeline import detect_vague_language

# Thresholds (tunable)
STRONG_SCORE_THRESHOLD = 70.0
LOW_SCORE_THRESHOLD = 40.0
SIMILAR_SCORE_BAND = 5.0
HIGH_OVERRIDE_RATE = 0.30
HIGH_VAGUE_RATE = 0.30
HIGH_SCORE_REJECTION_RATE = 0.20
LOW_SCORE_ADVANCEMENT_RATE = 0.15
FUNNEL_BOTTLENECK_DROPOFF = 0.60
ADVERSE_IMPACT_RATIO = 0.80
SMALL_SAMPLE_MIN = 10
SMALL_GROUP_SUPPRESS = 5

HIRING_STAGES = ["applied", "resume_screen", "shortlisted", "interview", "finalist", "offer", "hired", "rejected"]
_ADVANCE_STAGES = {"resume_screen", "shortlisted", "interview", "finalist", "offer", "hired"}


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _outcome_is_advance(outcome: str) -> bool:
    return (outcome or "").strip().lower() in {
        "strong interview", "interview", "shortlist", "shortlisted",
        "advance", "move to next stage", "offer", "hire", "hired",
    }


def _outcome_is_reject(outcome: str) -> bool:
    return (outcome or "").strip().lower() in {"reject", "rejected"}


def compute_metrics(events: List[Dict[str, Any]], scorecards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the full dashboard metric set from decision events + scorecards."""
    total_candidates = len({s.get("candidate_id") for s in scorecards if s.get("candidate_id")})
    scores = [s.get("total_score", 0) for s in scorecards if s.get("total_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    decisions = events
    total_decisions = len(decisions)
    advance = [e for e in decisions if _outcome_is_advance(e.get("decision_outcome") or e.get("human_decision"))]
    reject = [e for e in decisions if _outcome_is_reject(e.get("decision_outcome") or e.get("human_decision"))]
    overrides = [e for e in decisions if e.get("override_flag")]
    vague = [e for e in decisions if e.get("vague_reason_flag")]

    # High-score rejection & low-score advancement
    high_score_rejections = [
        e for e in reject
        if (e.get("rubric_score_at_decision") or 0) >= STRONG_SCORE_THRESHOLD
    ]
    low_score_advances = [
        e for e in advance
        if (e.get("rubric_score_at_decision") or 0) < LOW_SCORE_THRESHOLD
    ]

    mvp = {
        "total_candidates": total_candidates,
        "total_decisions": total_decisions,
        "average_score": avg_score,
        "interview_rate": _rate(len(advance), total_decisions),
        "rejection_rate": _rate(len(reject), total_decisions),
        "override_rate": _rate(len(overrides), total_decisions),
        "vague_reason_rate": _rate(len(vague), total_decisions),
        "high_score_rejection_rate": _rate(len(high_score_rejections), max(len(reject), 1)),
        "similar_score_different_outcome_rate": _similar_score_different_outcome(decisions),
    }

    return {
        "mvp": mvp,
        "funnel": _funnel_metrics(decisions),
        "score_decision_consistency": _consistency_metrics(decisions),
        "override": _override_metrics(decisions),
        "vague_language": _vague_metrics(decisions),
        "timing": _timing_metrics(decisions),
        "score_bands": _score_bands(scorecards),
        "timeseries": _timeseries(decisions),
    }


def _score_bands(scorecards: List[Dict[str, Any]]) -> Dict[str, int]:
    """Distribution of candidate scores into rubric bands for a histogram."""
    bands = {"0-49": 0, "50-69": 0, "70-84": 0, "85-100": 0}
    for s in scorecards:
        score = s.get("total_score")
        if score is None:
            continue
        if score < 50:
            bands["0-49"] += 1
        elif score < 70:
            bands["50-69"] += 1
        elif score < 85:
            bands["70-84"] += 1
        else:
            bands["85-100"] += 1
    return bands


def _timeseries(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-day decision counts for trend charts (date, decisions, overrides, rejects, advances)."""
    by_date = defaultdict(lambda: {"decisions": 0, "overrides": 0, "rejects": 0, "advances": 0})
    for e in decisions:
        raw = e.get("created_at") or e.get("decision_date") or ""
        date = str(raw)[:10]
        if not date:
            continue
        bucket = by_date[date]
        bucket["decisions"] += 1
        if e.get("override_flag"):
            bucket["overrides"] += 1
        outcome = e.get("decision_outcome") or e.get("human_decision")
        if _outcome_is_reject(outcome):
            bucket["rejects"] += 1
        elif _outcome_is_advance(outcome):
            bucket["advances"] += 1
    return [{"date": d, **vals} for d, vals in sorted(by_date.items())]


# A. Funnel metrics ---------------------------------------------------------
def _funnel_metrics(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_stage = defaultdict(list)
    for e in decisions:
        by_stage[(e.get("decision_stage") or "unknown")].append(e)

    def stage_pass_rate(stage):
        items = by_stage.get(stage, [])
        passed = [e for e in items if _outcome_is_advance(e.get("decision_outcome") or e.get("human_decision"))]
        return _rate(len(passed), len(items))

    rejection_by_stage = {
        stage: _rate(
            len([e for e in items if _outcome_is_reject(e.get("decision_outcome") or e.get("human_decision"))]),
            len(items),
        )
        for stage, items in by_stage.items()
    }

    return {
        "application_count": len(decisions),
        "resume_screen_pass_rate": stage_pass_rate("resume_screen"),
        "shortlist_rate": stage_pass_rate("shortlisted"),
        "interview_rate": stage_pass_rate("interview"),
        "offer_rate": stage_pass_rate("offer"),
        "hire_rate": stage_pass_rate("hired"),
        "rejection_rate_by_stage": rejection_by_stage,
        "counts_by_stage": {stage: len(items) for stage, items in by_stage.items()},
    }


# B. Score-decision consistency --------------------------------------------
def _consistency_metrics(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_outcome = defaultdict(list)
    for e in decisions:
        outcome = (e.get("decision_outcome") or e.get("human_decision") or "unknown").strip().lower()
        score = e.get("rubric_score_at_decision")
        if score is not None:
            by_outcome[outcome].append(score)

    avg_by_outcome = {
        outcome: round(sum(vals) / len(vals), 1) for outcome, vals in by_outcome.items() if vals
    }

    reject = [e for e in decisions if _outcome_is_reject(e.get("decision_outcome") or e.get("human_decision"))]
    advance = [e for e in decisions if _outcome_is_advance(e.get("decision_outcome") or e.get("human_decision"))]

    high_score_rejections = [e for e in reject if (e.get("rubric_score_at_decision") or 0) >= STRONG_SCORE_THRESHOLD]
    low_score_advances = [e for e in advance if (e.get("rubric_score_at_decision") or 0) < LOW_SCORE_THRESHOLD]

    return {
        "average_score_by_outcome": avg_by_outcome,
        "similar_score_different_outcome_rate": _similar_score_different_outcome(decisions),
        "high_score_rejection_rate": _rate(len(high_score_rejections), max(len(reject), 1)),
        "low_score_advancement_rate": _rate(len(low_score_advances), max(len(advance), 1)),
    }


def _similar_score_different_outcome(decisions: List[Dict[str, Any]]) -> float:
    """Fraction of similar-score decision pairs that got opposite outcomes."""
    scored = [
        e for e in decisions
        if e.get("rubric_score_at_decision") is not None
        and (_outcome_is_advance(e.get("decision_outcome") or e.get("human_decision"))
             or _outcome_is_reject(e.get("decision_outcome") or e.get("human_decision")))
    ]
    similar_pairs = 0
    conflicting_pairs = 0
    for i in range(len(scored)):
        for j in range(i + 1, len(scored)):
            a, b = scored[i], scored[j]
            if abs((a["rubric_score_at_decision"]) - (b["rubric_score_at_decision"])) <= SIMILAR_SCORE_BAND:
                similar_pairs += 1
                a_adv = _outcome_is_advance(a.get("decision_outcome") or a.get("human_decision"))
                b_adv = _outcome_is_advance(b.get("decision_outcome") or b.get("human_decision"))
                if a_adv != b_adv:
                    conflicting_pairs += 1
    return _rate(conflicting_pairs, similar_pairs)


# C. Override metrics -------------------------------------------------------
def _override_metrics(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    overrides = [e for e in decisions if e.get("override_flag")]

    def rate_by(key):
        totals = defaultdict(int)
        over = defaultdict(int)
        for e in decisions:
            k = e.get(key) or "unknown"
            totals[k] += 1
            if e.get("override_flag"):
                over[k] += 1
        return {k: _rate(over[k], totals[k]) for k in totals}

    reason_categories = defaultdict(int)
    for e in overrides:
        vague, _ = detect_vague_language(e.get("decision_reason") or "")
        reason_categories["vague" if vague else "specific"] += 1
        if not (e.get("decision_reason") or "").strip():
            reason_categories["missing"] += 1

    return {
        "override_rate_overall": _rate(len(overrides), len(decisions)),
        "override_rate_by_manager": rate_by("decision_maker_id"),
        "override_rate_by_job": rate_by("job_id"),
        "override_rate_by_stage": rate_by("decision_stage"),
        "override_reason_categories": dict(reason_categories),
    }


# D. Vague-language metrics -------------------------------------------------
def _vague_metrics(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    rejects = [e for e in decisions if _outcome_is_reject(e.get("decision_outcome") or e.get("human_decision"))]
    overrides = [e for e in decisions if e.get("override_flag")]
    with_reason = [e for e in decisions if (e.get("decision_reason") or "").strip()]

    vague_rejects = [e for e in rejects if e.get("vague_reason_flag")]
    vague_overrides = [e for e in overrides if e.get("vague_reason_flag")]
    actionable = [e for e in with_reason if not e.get("vague_reason_flag") and (e.get("evidence_count") or 0) > 0]

    return {
        "vague_rejection_reason_rate": _rate(len(vague_rejects), max(len(rejects), 1)),
        "vague_override_reason_rate": _rate(len(vague_overrides), max(len(overrides), 1)),
        "personality_language_rate": _rate(
            len([e for e in with_reason if e.get("vague_reason_flag")]), max(len(with_reason), 1)
        ),
        "actionable_reason_rate": _rate(len(actionable), max(len(with_reason), 1)),
    }


# E. Timing metrics ---------------------------------------------------------
def _timing_metrics(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Basic stage counts; richer time-in-stage requires per-application stage history.
    stalled = defaultdict(int)
    for e in decisions:
        stage = e.get("decision_stage") or "unknown"
        if (e.get("decision_outcome") or "").strip().lower() in ("hold", ""):
            stalled[stage] += 1
    return {
        "candidates_stalled_by_stage": dict(stalled),
        "note": "Time-in-stage requires per-application stage timestamps; tracked via stage_timestamp.",
    }


# F. Optional demographic fairness (voluntary, aggregated, suppressed) ------
def compute_demographic_fairness(
    decisions: List[Dict[str, Any]],
    demographics: Dict[str, str],
) -> Dict[str, Any]:
    """
    Optional. Only uses voluntary self-reported demographics passed in explicitly
    (candidate_id -> group). Never infers. Suppresses small groups.
    """
    if not demographics:
        return {"available": False, "reason": "No voluntary demographic data provided."}

    by_group_total = defaultdict(int)
    by_group_selected = defaultdict(int)
    for e in decisions:
        group = demographics.get(e.get("candidate_id"))
        if not group:
            continue
        by_group_total[group] += 1
        if _outcome_is_advance(e.get("decision_outcome") or e.get("human_decision")):
            by_group_selected[group] += 1

    selection_rate = {}
    for group, total in by_group_total.items():
        if total < SMALL_GROUP_SUPPRESS:
            selection_rate[group] = {"suppressed": True, "reason": "group too small"}
        else:
            selection_rate[group] = _rate(by_group_selected[group], total)

    numeric_rates = {g: r for g, r in selection_rate.items() if isinstance(r, float)}
    adverse = {}
    if numeric_rates:
        highest = max(numeric_rates.values())
        if highest > 0:
            # Include zero-rate groups so a disadvantaged group is still flagged.
            for g, r in numeric_rates.items():
                ratio = round(r / highest, 3)
                adverse[g] = {"ratio": ratio, "adverse_impact": ratio < ADVERSE_IMPACT_RATIO}

    return {
        "available": True,
        "selection_rate_by_group": selection_rate,
        "adverse_impact_by_group": adverse,
    }


# ---------------------------------------------------------------------------
# Warning flags
# ---------------------------------------------------------------------------
def compute_warning_flags(events: List[Dict[str, Any]], scorecards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metrics = compute_metrics(events, scorecards)
    warnings: List[Dict[str, Any]] = []
    total = len(events)

    if total < SMALL_SAMPLE_MIN:
        warnings.append({
            "flag": "small_sample",
            "severity": "info",
            "message": f"Only {total} decisions logged. Metrics may not be reliable yet.",
        })

    override_rate = metrics["override"]["override_rate_overall"]
    if override_rate >= HIGH_OVERRIDE_RATE:
        warnings.append({
            "flag": "high_override",
            "severity": "high",
            "message": f"Override rate is {override_rate:.0%}, above {HIGH_OVERRIDE_RATE:.0%}.",
        })

    # Per-manager high override
    for manager, rate in metrics["override"]["override_rate_by_manager"].items():
        if rate >= HIGH_OVERRIDE_RATE and total >= SMALL_SAMPLE_MIN:
            warnings.append({
                "flag": "high_override_manager",
                "severity": "medium",
                "message": f"Manager {manager} overrides {rate:.0%} of recommendations.",
            })

    vague_rate = metrics["vague_language"]["vague_rejection_reason_rate"]
    if vague_rate >= HIGH_VAGUE_RATE:
        warnings.append({
            "flag": "vague_reason",
            "severity": "medium",
            "message": f"{vague_rate:.0%} of rejection reasons use vague language.",
        })

    similar = metrics["score_decision_consistency"]["similar_score_different_outcome_rate"]
    if similar >= 0.25:
        warnings.append({
            "flag": "similar_score_different_outcome",
            "severity": "high",
            "message": f"{similar:.0%} of similar-score candidate pairs got opposite outcomes.",
        })

    high_rej = metrics["score_decision_consistency"]["high_score_rejection_rate"]
    if high_rej >= HIGH_SCORE_REJECTION_RATE:
        warnings.append({
            "flag": "high_score_rejection",
            "severity": "high",
            "message": f"{high_rej:.0%} of rejections are strong-score (>= {STRONG_SCORE_THRESHOLD:.0f}) candidates.",
        })

    low_adv = metrics["score_decision_consistency"]["low_score_advancement_rate"]
    if low_adv >= LOW_SCORE_ADVANCEMENT_RATE:
        warnings.append({
            "flag": "low_score_advancement",
            "severity": "medium",
            "message": f"{low_adv:.0%} of advancements are low-score (< {LOW_SCORE_THRESHOLD:.0f}) candidates.",
        })

    # Funnel bottleneck: a stage where most candidates get rejected
    for stage, rej_rate in metrics["funnel"]["rejection_rate_by_stage"].items():
        stage_count = metrics["funnel"]["counts_by_stage"].get(stage, 0)
        if rej_rate >= FUNNEL_BOTTLENECK_DROPOFF and stage_count >= 3:
            warnings.append({
                "flag": "funnel_bottleneck",
                "severity": "medium",
                "message": f"{rej_rate:.0%} of candidates drop off at stage '{stage}'.",
            })

    return warnings
