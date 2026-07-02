"""Seed example manager workforce decisions for Decision Logger (two-path model)."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.database.moderation_db import TalentDecisionDatabase

MANAGER_ID = "mgr_001"
GOAL = "Launch AI analytics dashboard in 6 months"

EXAMPLE_DECISIONS = [
    {
        "decision_id": "dec_seed_promote_001",
        "manager_id": MANAGER_ID,
        "decision_type": "promote_internal",
        "business_goal": GOAL,
        "gap_analysis": [
            {"capability": "Technical leadership", "severity": "moderate"},
            {"capability": "Cross-team program delivery", "severity": "moderate"},
        ],
        "recommended_action": "promote",
        "ai_recommendation": {
            "primary_path": "promote_internal",
            "action": "promote",
            "target_employee_id": "emp_003",
            "target_employee_name": "Sara Ahmed",
            "summary": "Promote Sara to lead analytics dashboard delivery",
        },
        "manager_final_decision": "promote_internal",
        "manager_reasoning": "Promote Sara Ahmed — delivered end-to-end analytics ahead of schedule; strongest readiness evidence on the team.",
        "manager_override_reason": None,
        "bias_risk_score": 0.18,
        "bias_categories": [],
        "reflection": {"upskill_plan": "90-day tech lead onboarding: stakeholder management + architecture reviews."},
    },
    {
        "decision_id": "dec_seed_upskill_001",
        "manager_id": MANAGER_ID,
        "decision_type": "promote_internal",
        "business_goal": GOAL,
        "gap_analysis": [
            {"capability": "ML model monitoring", "severity": "critical"},
            {"capability": "Production ML ops", "severity": "critical"},
        ],
        "recommended_action": "upskill",
        "ai_recommendation": {
            "primary_path": "promote_internal",
            "action": "upskill",
            "target_employee_id": "emp_004",
            "target_employee_name": "Leo Martin",
        },
        "manager_final_decision": "promote_internal",
        "manager_reasoning": "Develop Leo Martin internally with structured ML monitoring upskilling before considering external hire.",
        "manager_override_reason": None,
        "bias_risk_score": 0.24,
        "bias_categories": ["visibility_bias"],
        "reflection": {"upskill_plan": "8-week ML monitoring path: Kubeflow basics, alert design, on-call shadowing."},
    },
    {
        "decision_id": "dec_seed_hire_001",
        "manager_id": MANAGER_ID,
        "decision_type": "hire_external",
        "business_goal": GOAL,
        "gap_analysis": [
            {"capability": "ML model monitoring", "severity": "critical"},
            {"capability": "Real-time inference at scale", "severity": "critical"},
        ],
        "recommended_action": "hire",
        "ai_recommendation": {"primary_path": "hire_external", "action": "hire", "summary": "Hire ML platform engineer"},
        "manager_final_decision": "hire_external",
        "manager_reasoning": "External hire needed — upskilling timeline exceeds 6-month launch window for inference at scale.",
        "manager_override_reason": None,
        "bias_risk_score": 0.31,
        "bias_categories": [],
        "reflection": {},
    },
    {
        "decision_id": "dec_seed_upskill_002",
        "manager_id": MANAGER_ID,
        "decision_type": "promote_internal",
        "business_goal": GOAL,
        "gap_analysis": [
            {"capability": "Advanced React performance", "severity": "moderate"},
        ],
        "recommended_action": "hire",
        "ai_recommendation": {"primary_path": "hire_external", "action": "hire"},
        "manager_final_decision": "promote_internal",
        "manager_reasoning": "Promote Maya Chen with upskill on analytics UI — she already owns dashboard UI refactor.",
        "manager_override_reason": "Existing dashboard context lowers delivery risk vs external hire for UI layer.",
        "bias_risk_score": 0.42,
        "bias_categories": ["affinity_bias"],
        "reflection": {"upskill_plan": "React performance + data-viz patterns; 6-week mentorship with design systems lead."},
    },
    {
        "decision_id": "dec_seed_promote_002",
        "manager_id": MANAGER_ID,
        "decision_type": "promote_internal",
        "business_goal": GOAL,
        "gap_analysis": [{"capability": "Backend platform ownership", "severity": "moderate"}],
        "recommended_action": "upskill",
        "ai_recommendation": {"primary_path": "promote_internal", "target_employee_name": "Daniel Wong"},
        "manager_final_decision": "promote_internal",
        "manager_reasoning": "Promote Daniel Wong to tech lead for API platform with documented readiness evidence.",
        "manager_override_reason": "Readiness evidence supports promotion over extended upskill path.",
        "bias_risk_score": 0.55,
        "bias_categories": ["visibility_bias", "recency_bias"],
        "reflection": {"upskill_plan": "Platform ownership bootcamp + lead one cross-team API migration."},
    },
]


def seed():
    db = TalentDecisionDatabase("databases/moderation_data.db")
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM talent_decision_logs WHERE decision_id LIKE 'dec_seed_%'")
        cur.execute("DELETE FROM talent_decision_logs WHERE decision_type = 'gap_analysis'")
    for d in EXAMPLE_DECISIONS:
        db.save_talent_decision_log(d)
    print(f"Seeded {len(EXAMPLE_DECISIONS)} workforce decisions ({MANAGER_ID})")


if __name__ == "__main__":
    seed()
