"""
Seed realistic demo data for the bias-reduction hiring dashboard.

Creates one job + rubric, 12 candidate profiles, 12 applications, 12 scorecards,
and 20 decision_events spanning the hiring funnel. The data intentionally
contains bias-risk patterns (high-score rejections, overrides, vague reasons,
similar-score / different-outcome pairs, low-score advancement) so the manager
home dashboard is meaningful immediately.

Idempotent: existing demo rows (job_id == DEMO_JOB_ID / candidate ids prefixed
with 'cand_demo_') are deleted before re-inserting, so it is safe to run
repeatedly.

Run:
    cd backend
    python scripts/seed_bias_demo.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.database.moderation_db import TalentDecisionDatabase
from src.hiring.hiring_pipeline import (
    is_override,
    detect_vague_language,
    count_evidence,
)

DEMO_JOB_ID = "job_demo_bias"
MANAGER_ID = "mgr_001"

# --- Job rubric (must-have weights total 100) -------------------------------
RUBRIC = [
    ("Backend API development (REST design + third-party integration)", 30),
    ("Frontend engineering (React, component architecture)", 25),
    ("Cloud & DevOps (CI/CD pipelines, containers)", 20),
    ("System design & scalability", 15),
    ("Testing & code quality", 10),
]
RUBRIC_WEIGHTS = {name: weight for name, weight in RUBRIC}

JOB = {
    "job_id": DEMO_JOB_ID,
    "title": "Senior Full-Stack Engineer",
    "department": "Engineering",
    "level": "Senior",
    "location": "Remote",
    "job_description_text": (
        "Build and scale the analytics platform. Own backend APIs and their "
        "integrations, contribute to the React frontend, and help mature our "
        "CI/CD and observability. Collaborate on system design for scale."
    ),
    "must_have_criteria": [{"capability": name, "weight": w} for name, w in RUBRIC],
    "nice_to_have_criteria": [
        {"capability": "GraphQL experience"},
        {"capability": "Observability tooling (metrics, tracing)"},
    ],
    "responsibilities": [
        "Design and ship REST APIs and integrations",
        "Contribute to the React analytics dashboard",
        "Improve CI/CD reliability and deployment safety",
        "Participate in system design reviews",
    ],
    "rubric_weights": RUBRIC_WEIGHTS,
    "rubric_version": "v1",
}

# --- 12 candidates: score, recommendation, and (skills) ---------------------
# recommendation values: Strong interview | Interview | Hold | Reject
CANDIDATES = [
    dict(i=1, score=91, rec="Strong interview", skills=["Python", "FastAPI", "React", "Docker", "AWS", "PostgreSQL"], years=8),
    dict(i=2, score=88, rec="Strong interview", skills=["Node.js", "React", "TypeScript", "Kubernetes", "GCP"], years=7),
    dict(i=3, score=81, rec="Interview", skills=["Java", "Spring", "React", "CI/CD", "Terraform"], years=6),
    dict(i=4, score=76, rec="Interview", skills=["Python", "Django", "Vue", "Docker", "REST APIs"], years=5),
    dict(i=5, score=73, rec="Interview", skills=["Go", "React", "gRPC", "Kubernetes"], years=6),
    dict(i=6, score=68, rec="Hold", skills=["Python", "Flask", "React", "REST integration"], years=4),
    dict(i=7, score=64, rec="Hold", skills=["Ruby", "Rails", "JavaScript", "Heroku"], years=5),
    dict(i=8, score=59, rec="Hold", skills=["Python", "React", "Jest", "unit testing"], years=3),
    dict(i=9, score=52, rec="Reject", skills=["PHP", "Laravel", "jQuery"], years=4),
    dict(i=10, score=38, rec="Reject", skills=["HTML", "CSS", "WordPress"], years=2),
    dict(i=11, score=39, rec="Reject", skills=["C#", ".NET", "SQL Server"], years=3),
    dict(i=12, score=34, rec="Reject", skills=["Excel VBA", "Access", "basic SQL"], years=2),
]

# Primary resume-screen decisions — managers choose Hire or Reject only.
# Reasons supplied where the manager overrode the AI or rejected.
PRIMARY_DECISIONS = {
    1:  ("Hire", ""),
    2:  ("Reject", "Not a culture fit with the team."),                                     # override + vague
    3:  ("Hire", ""),
    4:  ("Reject", "Insufficient evidence on frontend depth for this senior role."),        # was Hold -> Reject
    5:  ("Reject", "Lacks required evidence of third-party API integration work."),         # override, specific
    6:  ("Hire", "Strong hands-on REST integration shown across two shipped projects."),     # override (hold->hire), specific
    7:  ("Reject", "No evidence of cloud/CI-CD experience required for this role."),          # override (hold->reject), specific
    8:  ("Reject", "Insufficient evidence of system design at the required scale."),          # override (hold->reject), specific
    9:  ("Reject", "Candidate gave off a bad vibe in the summary."),                          # vague (matching reject)
    10: ("Hire", "Willing to develop; strong learning trajectory noted."),              # override (reject->hire), low score
    11: ("Reject", "Tech stack does not overlap with required backend/cloud skills."),        # specific
    12: ("Reject", "Not ready for a senior role."),                                          # vague
}

# Post-screening funnel events (outcomes are Hire or Reject only).
LATER_EVENTS = [
    (1, "shortlisted", "shortlist", "Hire", ""),
    (1, "interview", "interview", "Hire", ""),
    (1, "finalist", "interview", "Hire", ""),
    (1, "offer", "offer", "Hire", ""),
    (1, "hired", "hire", "Hire", ""),
    (3, "shortlisted", "shortlist", "Hire", ""),
    (3, "interview", "reject", "Reject", "Technical interview revealed gaps in system design depth."),
    (6, "shortlisted", "shortlist", "Hire", ""),
]


def _build_scorecard(cand):
    """Build a display scorecard whose total_score equals the target score."""
    target = cand["score"]
    offsets = [4, -3, 2, -6, 1]
    criteria = []
    for (name, weight), off in zip(RUBRIC, offsets):
        s = max(0, min(100, target + off))
        if s >= 70:
            evidence = [
                f"Resume shows applied {name.split('(')[0].strip().lower()}.",
                "Quantified impact described in a recent role.",
            ]
        elif s >= 45:
            evidence = [f"Some exposure to {name.split('(')[0].strip().lower()} mentioned."]
        else:
            evidence = []
        criteria.append({
            "criterion": name,
            "score": s,
            "max_score": 100,
            "weight": weight,
            "evidence": evidence,
            "explanation": f"Scored {s}/100 based on resume evidence for this criterion.",
        })

    strengths = [c["criterion"] for c in criteria if c["score"] >= 75][:3]
    concerns = [c["criterion"] for c in criteria if c["score"] < 50]
    missing = [f"Weak/absent: {c['criterion']}" for c in criteria if c["score"] < 40]

    return {
        "scorecard_id": f"sc_demo_{cand['i']:03d}",
        "application_id": f"app_demo_{cand['i']:03d}",
        "candidate_id": f"cand_demo_{cand['i']:03d}",
        "job_id": DEMO_JOB_ID,
        "criteria_scores": criteria,
        "total_score": float(target),
        "strengths": strengths or ["Relevant recent experience"],
        "concerns": concerns,
        "missing_requirements": missing,
        "generated_recommendation": cand["rec"],
    }


def _clear_demo(db):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM decision_events WHERE job_id = ?", (DEMO_JOB_ID,))
        cur.execute("DELETE FROM scorecards WHERE job_id = ?", (DEMO_JOB_ID,))
        cur.execute("DELETE FROM applications WHERE job_id = ?", (DEMO_JOB_ID,))
        cur.execute("DELETE FROM candidates WHERE candidate_id LIKE 'cand_demo_%'")
        cur.execute("DELETE FROM jobs WHERE job_id = ?", (DEMO_JOB_ID,))
        cur.execute("DELETE FROM candidate_demographics WHERE candidate_id LIKE 'cand_demo_%'")
        cur.execute("DELETE FROM training_recommendations WHERE training_id LIKE 'train_demo_%'")
    print("Cleared previous demo rows.")


def seed():
    db = TalentDecisionDatabase("databases/moderation_data.db")
    _clear_demo(db)

    db.save_job(JOB)

    scorecards_by_idx = {}
    for cand in CANDIDATES:
        cid = f"cand_demo_{cand['i']:03d}"
        aid = f"app_demo_{cand['i']:03d}"
        db.save_candidate({
            "candidate_id": cid,
            "resume_id": f"res_demo_{cand['i']:03d}",
            "extracted_skills": cand["skills"],
            "years_experience": cand["years"],
            "education": [],
            "work_experience": [{"summary": "Experience described in resume."}],
            "projects": [],
            "certifications": [],
            "leadership_experience": [],
            "domain_experience": [],
            "extraction_confidence": 0.9,
        })
        db.save_application({
            "application_id": aid,
            "candidate_id": cid,
            "job_id": DEMO_JOB_ID,
            "source": "seed",
            "current_stage": "resume_screen",
            "status": "active",
        })
        sc = _build_scorecard(cand)
        db.save_scorecard(sc)
        scorecards_by_idx[cand["i"]] = sc

    # --- decision events ----------------------------------------------------
    events = []
    seq = 0

    def add_event(idx, stage, dtype, outcome, reason, rec):
        nonlocal seq
        seq += 1
        sc = scorecards_by_idx[idx]
        override = is_override(rec, outcome)
        vague, _ = detect_vague_language(reason)
        status = "rejected" if outcome.lower() in ("reject", "rejected") else "active"
        events.append({
            "decision_id": f"dec_demo_{seq:03d}",
            "application_id": f"app_demo_{idx:03d}",
            "candidate_id": f"cand_demo_{idx:03d}",
            "job_id": DEMO_JOB_ID,
            "decision_type": dtype,
            "decision_stage": stage,
            "decision_outcome": outcome,
            "decision_maker_id": MANAGER_ID,
            "rubric_score_at_decision": sc["total_score"],
            "generated_recommendation": rec,
            "human_decision": outcome,
            "override_flag": override,
            "decision_reason": reason,
            "vague_reason_flag": vague,
            "evidence_count": count_evidence(sc),
            "_final_stage": stage,
            "_status": status,
        })

    for cand in CANDIDATES:
        outcome, reason = PRIMARY_DECISIONS[cand["i"]]
        dtype = "reject" if outcome.lower() == "reject" else "hire"
        add_event(cand["i"], "resume_screen", dtype, outcome, reason, cand["rec"])

    for idx, stage, dtype, outcome, reason in LATER_EVENTS:
        add_event(idx, stage, dtype, outcome, reason, scorecards_by_idx[idx]["generated_recommendation"])

    for ev in events:
        final_stage = ev.pop("_final_stage")
        status = ev.pop("_status")
        db.save_decision_event(ev)
        db.update_application_stage(ev["application_id"], final_stage, status)

    # --- voluntary, synthetic demographics (illustrative only) --------------
    # Group A skews toward advancement, Group B toward rejection, so the
    # fairness panel demonstrates an adverse-impact signal on demo data.
    group_a = {1, 3, 4, 6, 9, 10}
    for cand in CANDIDATES:
        cid = f"cand_demo_{cand['i']:03d}"
        group = "Group A" if cand["i"] in group_a else "Group B"
        db.set_candidate_demographic(cid, group, DEMO_JOB_ID, consent=True)

    # --- sample adaptive-training recommendations --------------------------
    demo_training = [
        {
            "training_id": "train_demo_001",
            "manager_id": MANAGER_ID,
            "trigger_type": "vague_reason_pattern",
            "module_title": "Evidence-Based Rejection Reasons",
            "module_type": "hiring_fairness",
            "module_payload": {"why": "Vague rejection language detected in recent decisions."},
            "status": "recommended",
        },
        {
            "training_id": "train_demo_002",
            "manager_id": MANAGER_ID,
            "trigger_type": "high_override_pattern",
            "module_title": "Calibrating Overrides Against the Rubric",
            "module_type": "bias_awareness",
            "module_payload": {"why": "Override rate above baseline on recent decisions."},
            "status": "pending",
        },
    ]
    for t in demo_training:
        db.save_training_recommendation(t)

    overrides = sum(1 for e in events if e["override_flag"])
    vague = sum(1 for e in events if e["vague_reason_flag"])
    print(
        f"Seeded job '{JOB['title']}' ({DEMO_JOB_ID}): "
        f"{len(CANDIDATES)} candidates/scorecards, {len(events)} decision_events "
        f"({overrides} overrides, {vague} vague reasons)."
    )


if __name__ == "__main__":
    seed()
