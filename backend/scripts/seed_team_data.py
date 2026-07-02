"""Seed Clarity with one manager and a 5-person team."""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.database.moderation_db import TalentDecisionDatabase

TEAM_ID = "team_alpha"
MANAGER_ID = "mgr_001"

MEMBERS = [
    {
        "employee_id": "emp_001",
        "name": "Maya Chen",
        "role": "Frontend Engineer",
        "level": "L2",
        "skills": ["React", "TypeScript", "CSS", "Accessibility", "Design Systems"],
        "performance_evidence": [
            "Led dashboard UI refactor reducing load time 30%",
            "Mentored intern on component library patterns",
            "Consistent high code review quality scores",
        ],
        "career_goals": ["Staff frontend engineer", "Design systems lead"],
        "workload": {"utilization": 0.85, "active_projects": 2, "on_call": False},
    },
    {
        "employee_id": "emp_002",
        "name": "Daniel Wong",
        "role": "Backend Engineer",
        "level": "L2",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "API Design"],
        "performance_evidence": [
            "Presented architecture proposal in 3 cross-team meetings",
            "Owned payment service reliability (99.9% uptime)",
            "Visible stakeholder updates in weekly demos",
        ],
        "career_goals": ["Tech lead", "Platform engineering"],
        "workload": {"utilization": 0.90, "active_projects": 3, "on_call": True},
    },
    {
        "employee_id": "emp_003",
        "name": "Sara Ahmed",
        "role": "Full-stack Engineer",
        "level": "L3",
        "skills": ["React", "Node.js", "GraphQL", "System Design", "Mentoring"],
        "performance_evidence": [
            "Delivered end-to-end analytics feature ahead of schedule",
            "Cross-functional collaboration with data team",
            "Strong design doc and RFC contributions",
        ],
        "career_goals": ["Senior engineer", "Technical program lead"],
        "workload": {"utilization": 0.80, "active_projects": 2, "on_call": False},
    },
    {
        "employee_id": "emp_004",
        "name": "Leo Martin",
        "role": "Data Engineer",
        "level": "L2",
        "skills": ["Python", "Spark", "Airflow", "dbt", "SQL"],
        "performance_evidence": [
            "Built ETL pipeline for product analytics",
            "Reduced data freshness lag from 24h to 4h",
            "Documented data contracts for downstream teams",
        ],
        "career_goals": ["ML platform engineer", "Data architecture"],
        "workload": {"utilization": 0.75, "active_projects": 2, "on_call": False},
    },
    {
        "employee_id": "emp_005",
        "name": "Priya Nair",
        "role": "QA Automation Engineer",
        "level": "L2",
        "skills": ["Selenium", "Cypress", "Python", "CI/CD", "Test Strategy"],
        "performance_evidence": [
            "Increased automated test coverage from 45% to 72%",
            "Built regression suite for release pipeline",
            "Found 12 critical bugs pre-release in Q3",
        ],
        "career_goals": ["Quality engineering lead", "DevOps transition"],
        "workload": {"utilization": 0.70, "active_projects": 1, "on_call": False},
    },
]


def seed():
    db = TalentDecisionDatabase("databases/moderation_data.db")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO teams (team_id, manager_id, team_name, business_goal)
            VALUES (?, ?, ?, ?)
        """, (TEAM_ID, MANAGER_ID, "Product Engineering Alpha",
              "Launch AI analytics dashboard in 6 months"))

        for m in MEMBERS:
            cursor.execute("""
                INSERT OR REPLACE INTO team_members (
                    employee_id, team_id, name, role, level,
                    skills_json, performance_evidence_json, career_goals_json, workload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m["employee_id"], TEAM_ID, m["name"], m["role"], m["level"],
                json.dumps(m["skills"]),
                json.dumps(m["performance_evidence"]),
                json.dumps(m["career_goals"]),
                json.dumps(m["workload"]),
            ))

    print(f"Seeded manager {MANAGER_ID} and team {TEAM_ID} with {len(MEMBERS)} members")


if __name__ == "__main__":
    seed()
