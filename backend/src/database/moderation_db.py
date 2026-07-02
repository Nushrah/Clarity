"""
Database module for content moderation system using SQLite.

Stores:
- Content submissions
- Moderation decisions
- User profiles
- Agent execution details
- Manual reviews
- Appeal records
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path


class TalentDecisionDatabase:
    """SQLite database for Clarity talent decisions."""

    def __init__(self, db_path: str = "databases/moderation_data.db"):
        """
        Initialize the database connection.

        Args:
            db_path: Path to SQLite database file
        """
        # Convert relative path to absolute path relative to backend directory
        if not Path(db_path).is_absolute():
            backend_dir = Path(__file__).parent.parent.parent
            self.db_path = str(backend_dir / db_path)
        else:
            self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Content submissions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT UNIQUE NOT NULL,
                    submission_id TEXT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    content_text TEXT,
                    content_type TEXT NOT NULL,
                    platform TEXT,
                    language TEXT DEFAULT 'en',
                    submission_timestamp TEXT NOT NULL,
                    current_status TEXT NOT NULL,
                    moderation_action TEXT,
                    action_reason TEXT,
                    toxicity_score REAL DEFAULT 0.0,
                    violation_severity TEXT,
                    requires_human_review INTEGER DEFAULT 0,
                    content_removed INTEGER DEFAULT 0,
                    user_notified INTEGER DEFAULT 0,
                    processed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    account_age_days INTEGER DEFAULT 0,
                    total_posts INTEGER DEFAULT 0,
                    total_violations INTEGER DEFAULT 0,
                    previous_warnings INTEGER DEFAULT 0,
                    previous_suspensions INTEGER DEFAULT 0,
                    reputation_score REAL DEFAULT 0.7,
                    reputation_tier TEXT DEFAULT 'new_user',
                    verified INTEGER DEFAULT 0,
                    follower_count INTEGER DEFAULT 0,
                    is_suspended INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    suspension_until TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Agent executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reasoning TEXT,
                    flags TEXT,
                    recommendations TEXT,
                    extracted_data TEXT,
                    requires_human_review INTEGER DEFAULT 0,
                    processing_time REAL DEFAULT 0.0,
                    execution_order INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
                )
            """)

            # Policy violations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    detected_by_agent TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
                )
            """)

            # Manual reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manual_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    review_decision TEXT NOT NULL,
                    review_notes TEXT,
                    previous_status TEXT,
                    new_status TEXT,
                    review_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
                )
            """)

            # Appeals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    appeal_reason TEXT NOT NULL,
                    original_decision TEXT NOT NULL,
                    appeal_decision TEXT,
                    appeal_reasoning TEXT,
                    appeal_timestamp TEXT NOT NULL,
                    decision_timestamp TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
                )
            """)

            # User actions table (suspensions, bans, warnings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    reason TEXT,
                    content_id TEXT,
                    duration_days INTEGER,
                    action_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)

            # Stories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    content_id TEXT,
                    moderation_status TEXT DEFAULT 'pending',
                    is_approved INTEGER DEFAULT 0,
                    is_visible INTEGER DEFAULT 0,
                    toxicity_score REAL DEFAULT 0.0,
                    view_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)

            # Story comments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS story_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id TEXT UNIQUE NOT NULL,
                    story_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    content_id TEXT,
                    moderation_status TEXT DEFAULT 'pending',
                    is_approved INTEGER DEFAULT 0,
                    is_visible INTEGER DEFAULT 0,
                    toxicity_score REAL DEFAULT 0.0,
                    parent_comment_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (story_id) REFERENCES stories(story_id),
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)

            # Clarity tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    manager_id TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    business_goal TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    employee_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    level TEXT,
                    skills_json TEXT,
                    performance_evidence_json TEXT,
                    career_goals_json TEXT,
                    workload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidate_resumes (
                    resume_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    role_id TEXT,
                    filename TEXT,
                    file_type TEXT,
                    raw_text TEXT,
                    parsed_profile_json TEXT,
                    anonymized_profile_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS talent_decision_logs (
                    decision_id TEXT PRIMARY KEY,
                    manager_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    business_goal TEXT,
                    gap_analysis_json TEXT,
                    recommended_action TEXT,
                    ai_recommendation_json TEXT,
                    manager_final_decision TEXT,
                    manager_reasoning TEXT,
                    manager_override_reason TEXT,
                    bias_risk_score REAL,
                    bias_categories_json TEXT,
                    manager_patterns_json TEXT,
                    reflection_json TEXT,
                    selected_candidate_id TEXT,
                    candidate_match_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manager_bias_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    manager_id TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_description TEXT,
                    frequency INTEGER DEFAULT 1,
                    severity TEXT,
                    last_seen_decision_id TEXT,
                    recommended_training_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_recommendations (
                    training_id TEXT PRIMARY KEY,
                    manager_id TEXT NOT NULL,
                    trigger_type TEXT,
                    module_title TEXT,
                    module_type TEXT,
                    module_payload_json TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ============================================================
            # Bias-reduction hiring pipeline tables
            # ============================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT,
                    department TEXT,
                    level TEXT,
                    location TEXT,
                    job_description_text TEXT,
                    must_have_criteria_json TEXT,
                    nice_to_have_criteria_json TEXT,
                    responsibilities_json TEXT,
                    rubric_weights_json TEXT,
                    rubric_version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    resume_id TEXT,
                    extracted_skills_json TEXT,
                    years_experience REAL,
                    education_json TEXT,
                    work_experience_json TEXT,
                    projects_json TEXT,
                    certifications_json TEXT,
                    leadership_experience_json TEXT,
                    domain_experience_json TEXT,
                    extraction_confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    application_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT,
                    current_stage TEXT DEFAULT 'applied',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scorecards (
                    scorecard_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    criteria_scores_json TEXT,
                    total_score REAL,
                    strengths_json TEXT,
                    concerns_json TEXT,
                    missing_requirements_json TEXT,
                    generated_recommendation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_events (
                    decision_id TEXT PRIMARY KEY,
                    application_id TEXT,
                    candidate_id TEXT,
                    job_id TEXT,
                    decision_type TEXT,
                    decision_stage TEXT,
                    decision_outcome TEXT,
                    decision_maker_id TEXT,
                    decision_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rubric_score_at_decision REAL,
                    generated_recommendation TEXT,
                    human_decision TEXT,
                    override_flag INTEGER DEFAULT 0,
                    decision_reason TEXT,
                    vague_reason_flag INTEGER DEFAULT 0,
                    evidence_count INTEGER DEFAULT 0,
                    stage_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Durable manager-reflection queue (survives restarts).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reflection_queue (
                    decision_id TEXT PRIMARY KEY,
                    manager_id TEXT,
                    business_goal TEXT,
                    priority TEXT DEFAULT 'medium',
                    bias_risk_score REAL,
                    bias_categories_json TEXT,
                    ai_recommendation TEXT,
                    reflection_questions_json TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            """)
            # Voluntary, self-reported candidate demographics (opt-in, consented).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidate_demographics (
                    candidate_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    self_reported_group TEXT,
                    consent INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_snapshots (
                    decision_id TEXT PRIMARY KEY,
                    manager_id TEXT,
                    state_json TEXT,
                    status TEXT DEFAULT 'awaiting_manager_choice',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_user ON content_submissions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_status ON content_submissions(current_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON user_profiles(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_content ON agent_executions(content_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_content ON policy_violations(content_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_user ON stories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_status ON stories(moderation_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_visible ON stories(is_visible)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comment_story ON story_comments(story_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comment_user ON story_comments(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_job ON applications(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_candidate ON applications(candidate_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scorecard_job ON scorecards(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scorecard_app ON scorecards(application_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_job ON decision_events(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_maker ON decision_events(decision_maker_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_stage ON decision_events(decision_stage)")

            print(f"Database initialized at {self.db_path}")

    def create_content_submission(self, content_data: Dict[str, Any]) -> str:
        """
        Create a new content submission record.

        Args:
            content_data: Dictionary with content information

        Returns:
            content_id of created submission
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO content_submissions (
                    content_id, submission_id, user_id, username, content_text,
                    content_type, platform, language, submission_timestamp,
                    current_status, toxicity_score, requires_human_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content_data.get("content_id"),
                content_data.get("submission_id"),
                content_data.get("user_id"),
                content_data.get("username"),
                content_data.get("content_text"),
                content_data.get("content_type"),
                content_data.get("platform", "generic"),
                content_data.get("language", "en"),
                content_data.get("submission_timestamp"),
                content_data.get("status", "submitted"),
                content_data.get("toxicity_score", 0.0),
                1 if content_data.get("requires_human_review", False) else 0
            ))

            return content_data.get("content_id")

    def update_content_status(
        self,
        content_id: str,
        status: str,
        moderation_action: Optional[str] = None,
        action_reason: Optional[str] = None,
        toxicity_score: Optional[float] = None
    ):
        """Update content submission status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE content_submissions
                SET current_status = ?,
                    moderation_action = COALESCE(?, moderation_action),
                    action_reason = COALESCE(?, action_reason),
                    toxicity_score = COALESCE(?, toxicity_score),
                    processed_at = ?
                WHERE content_id = ?
            """, (status, moderation_action, action_reason, toxicity_score, datetime.now().isoformat(), content_id))

    def save_agent_decision(self, content_id: str, agent_decision: Any):
        """Save an agent's decision to the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get current execution order
            cursor.execute("""
                SELECT COALESCE(MAX(execution_order), 0) + 1
                FROM agent_executions
                WHERE content_id = ?
            """, (content_id,))

            execution_order = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO agent_executions (
                    content_id, agent_name, decision, confidence, reasoning,
                    flags, recommendations, extracted_data, requires_human_review,
                    processing_time, execution_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content_id,
                agent_decision.agent_name,
                agent_decision.decision.value,
                agent_decision.confidence,
                agent_decision.reasoning,
                json.dumps(agent_decision.flags),
                json.dumps(agent_decision.recommendations),
                json.dumps(agent_decision.extracted_data),
                1 if agent_decision.requires_human_review else 0,
                agent_decision.processing_time,
                execution_order
            ))

    def save_policy_violations(self, content_id: str, violations: List[str], severity: str, agent_name: str):
        """Save policy violations for a content submission."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            for violation in violations:
                cursor.execute("""
                    INSERT INTO policy_violations (
                        content_id, violation_type, severity, detected_by_agent
                    ) VALUES (?, ?, ?, ?)
                """, (content_id, violation, severity, agent_name))

    def get_content_by_id(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve content submission by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM content_submissions WHERE content_id = ?
            """, (content_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_content(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all content submissions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM content_submissions
                ORDER BY submission_timestamp DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_content_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get content by status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM content_submissions
                WHERE current_status = ?
                ORDER BY submission_timestamp DESC
                LIMIT ?
            """, (status, limit))

            return [dict(row) for row in cursor.fetchall()]

    def get_agent_executions(self, content_id: str) -> List[Dict[str, Any]]:
        """Get all agent executions for a content submission."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM agent_executions
                WHERE content_id = ?
                ORDER BY execution_order ASC
            """, (content_id,))

            return [dict(row) for row in cursor.fetchall()]

    def get_policy_violations(self, content_id: str) -> List[Dict[str, Any]]:
        """Get all policy violations for a content submission."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM policy_violations
                WHERE content_id = ?
                ORDER BY timestamp ASC
            """, (content_id,))

            return [dict(row) for row in cursor.fetchall()]

    def create_or_update_user(self, user_data: Dict[str, Any]):
        """Create or update user profile."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO user_profiles (
                    user_id, username, account_age_days, total_posts,
                    total_violations, previous_warnings, previous_suspensions,
                    reputation_score, reputation_tier, verified, follower_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_posts = total_posts + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_data.get("user_id"),
                user_data.get("username"),
                user_data.get("account_age_days", 0),
                user_data.get("total_posts", 0),
                user_data.get("total_violations", 0),
                user_data.get("previous_warnings", 0),
                user_data.get("previous_suspensions", 0),
                user_data.get("reputation_score", 0.7),
                user_data.get("reputation_tier", "new_user"),
                1 if user_data.get("verified", False) else 0,
                user_data.get("follower_count", 0)
            ))

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM user_profiles WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_user_reputation(self, user_id: str, new_score: float, new_tier: str):
        """Update user reputation score."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE user_profiles
                SET reputation_score = ?,
                    reputation_tier = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (new_score, new_tier, user_id))

    def record_user_action(
        self,
        user_id: str,
        action_type: str,
        reason: str,
        content_id: Optional[str] = None,
        duration_days: Optional[int] = None
    ):
        """Record a user action (warning, suspension, ban)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            expires_at = None
            if duration_days:
                from datetime import timedelta
                expires_at = (datetime.now() + timedelta(days=duration_days)).isoformat()

            cursor.execute("""
                INSERT INTO user_actions (
                    user_id, action_type, reason, content_id, duration_days, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, action_type, reason, content_id, duration_days, expires_at))

            # Update user profile based on action
            if action_type == "warning":
                cursor.execute("""
                    UPDATE user_profiles
                    SET previous_warnings = previous_warnings + 1
                    WHERE user_id = ?
                """, (user_id,))
            elif action_type == "suspension":
                cursor.execute("""
                    UPDATE user_profiles
                    SET previous_suspensions = previous_suspensions + 1,
                        is_suspended = 1,
                        suspension_until = ?
                    WHERE user_id = ?
                """, (expires_at, user_id))
            elif action_type == "ban":
                cursor.execute("""
                    UPDATE user_profiles
                    SET is_banned = 1
                    WHERE user_id = ?
                """, (user_id,))

    def increment_user_violations(self, user_id: str):
        """Increment user's total violations count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE user_profiles
                SET total_violations = total_violations + 1
                WHERE user_id = ?
            """, (user_id,))

    def save_manual_review(
        self,
        content_id: str,
        reviewer_name: str,
        decision: str,
        notes: str
    ):
        """Save a manual review decision."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get current status
            cursor.execute("""
                SELECT current_status FROM content_submissions WHERE content_id = ?
            """, (content_id,))

            row = cursor.fetchone()
            previous_status = row[0] if row else "unknown"

            cursor.execute("""
                INSERT INTO manual_reviews (
                    content_id, reviewer_name, review_decision, review_notes,
                    previous_status, new_status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (content_id, reviewer_name, decision, notes, previous_status, decision))

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total content
            cursor.execute("SELECT COUNT(*) FROM content_submissions")
            stats["total_content"] = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT current_status, COUNT(*) as count
                FROM content_submissions
                GROUP BY current_status
            """)
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            # Total users
            cursor.execute("SELECT COUNT(*) FROM user_profiles")
            stats["total_users"] = cursor.fetchone()[0]

            # Total violations
            cursor.execute("SELECT COUNT(*) FROM policy_violations")
            stats["total_violations"] = cursor.fetchone()[0]

            # Total reviews
            cursor.execute("SELECT COUNT(*) FROM manual_reviews")
            stats["total_reviews"] = cursor.fetchone()[0]

            return stats

    def get_agent_decisions(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all agent decisions/executions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM agent_executions
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_all_appeals(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all appeals."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM appeals
                ORDER BY appeal_timestamp DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID (alias for get_user_profile)."""
        return self.get_user_profile(user_id)

    def update_user_status(self, user_id: str, status: str, reason: str = ""):
        """Update user status (active, suspended, banned, restricted)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if status == "suspended":
                cursor.execute("""
                    UPDATE user_profiles
                    SET is_suspended = 1,
                        is_banned = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
            elif status == "banned":
                cursor.execute("""
                    UPDATE user_profiles
                    SET is_banned = 1,
                        is_suspended = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
            elif status == "active":
                cursor.execute("""
                    UPDATE user_profiles
                    SET is_suspended = 0,
                        is_banned = 0,
                        suspension_until = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
            elif status == "restricted":
                # Just mark as suspended for now
                cursor.execute("""
                    UPDATE user_profiles
                    SET is_suspended = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))

            # Record the action
            cursor.execute("""
                INSERT INTO user_actions (
                    user_id, action_type, reason
                ) VALUES (?, ?, ?)
            """, (user_id, f"status_change_{status}", reason))

    def get_user_actions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all actions taken on a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM user_actions
                WHERE user_id = ?
                ORDER BY action_timestamp DESC
            """, (user_id,))

            return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════════════════════════
    # Story Methods
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_story(self, story_data: Dict[str, Any]) -> str:
        """Create a new story."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO stories (
                    story_id, user_id, username, title, content_text,
                    content_id, moderation_status, is_approved, is_visible,
                    toxicity_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                story_data.get("story_id"),
                story_data.get("user_id"),
                story_data.get("username"),
                story_data.get("title"),
                story_data.get("content_text"),
                story_data.get("content_id"),
                story_data.get("moderation_status", "pending"),
                1 if story_data.get("is_approved", False) else 0,
                1 if story_data.get("is_visible", False) else 0,
                story_data.get("toxicity_score", 0.0),
                story_data.get("created_at", datetime.now().isoformat())
            ))

            return story_data.get("story_id")

    def get_story_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Get a story by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stories WHERE story_id = ?
            """, (story_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_story_by_content_id(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Get a story by its moderation content_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stories WHERE content_id = ?
            """, (content_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_comment_by_content_id(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Get a comment by its moderation content_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM story_comments WHERE content_id = ?
            """, (content_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_stories(self, limit: int = 100, visible_only: bool = False) -> List[Dict[str, Any]]:
        """Get all stories, optionally only visible ones."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if visible_only:
                cursor.execute("""
                    SELECT * FROM stories
                    WHERE is_visible = 1
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM stories
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_user_stories(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get stories by a specific user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stories
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))

            return [dict(row) for row in cursor.fetchall()]

    def update_story_moderation(
        self,
        story_id: str,
        moderation_status: str,
        is_approved: bool,
        is_visible: bool,
        toxicity_score: Optional[float] = None
    ):
        """Update story moderation status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE stories
                SET moderation_status = ?,
                    is_approved = ?,
                    is_visible = ?,
                    toxicity_score = COALESCE(?, toxicity_score),
                    updated_at = ?
                WHERE story_id = ?
            """, (
                moderation_status,
                1 if is_approved else 0,
                1 if is_visible else 0,
                toxicity_score,
                datetime.now().isoformat(),
                story_id
            ))

    def increment_story_view(self, story_id: str):
        """Increment story view count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE stories
                SET view_count = view_count + 1
                WHERE story_id = ?
            """, (story_id,))

    def increment_story_comments(self, story_id: str):
        """Increment story comment count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE stories
                SET comment_count = comment_count + 1
                WHERE story_id = ?
            """, (story_id,))

    # ═══════════════════════════════════════════════════════════════════════════════
    # Story Comment Methods
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_story_comment(self, comment_data: Dict[str, Any]) -> str:
        """Create a new story comment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO story_comments (
                    comment_id, story_id, user_id, username, content_text,
                    content_id, moderation_status, is_approved, is_visible,
                    toxicity_score, parent_comment_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comment_data.get("comment_id"),
                comment_data.get("story_id"),
                comment_data.get("user_id"),
                comment_data.get("username"),
                comment_data.get("content_text"),
                comment_data.get("content_id"),
                comment_data.get("moderation_status", "pending"),
                1 if comment_data.get("is_approved", False) else 0,
                1 if comment_data.get("is_visible", False) else 0,
                comment_data.get("toxicity_score", 0.0),
                comment_data.get("parent_comment_id"),
                comment_data.get("created_at", datetime.now().isoformat())
            ))

            return comment_data.get("comment_id")

    def get_story_comments(self, story_id: str, visible_only: bool = False) -> List[Dict[str, Any]]:
        """Get all comments for a story."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if visible_only:
                cursor.execute("""
                    SELECT * FROM story_comments
                    WHERE story_id = ? AND is_visible = 1
                    ORDER BY created_at ASC
                """, (story_id,))
            else:
                cursor.execute("""
                    SELECT * FROM story_comments
                    WHERE story_id = ?
                    ORDER BY created_at ASC
                """, (story_id,))

            return [dict(row) for row in cursor.fetchall()]

    def get_comment_by_id(self, comment_id: str) -> Optional[Dict[str, Any]]:
        """Get a comment by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM story_comments WHERE comment_id = ?
            """, (comment_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_comment_moderation(
        self,
        comment_id: str,
        moderation_status: str,
        is_approved: bool,
        is_visible: bool,
        toxicity_score: Optional[float] = None
    ):
        """Update comment moderation status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE story_comments
                SET moderation_status = ?,
                    is_approved = ?,
                    is_visible = ?,
                    toxicity_score = COALESCE(?, toxicity_score)
                WHERE comment_id = ?
            """, (
                moderation_status,
                1 if is_approved else 0,
                1 if is_visible else 0,
                toxicity_score,
                comment_id
            ))

    def get_pending_stories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get stories pending moderation (including flagged stories)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stories
                WHERE moderation_status IN ('pending', 'under_review', 'flagged')
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_pending_comments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get comments pending moderation (including flagged comments)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM story_comments
                WHERE moderation_status IN ('pending', 'under_review', 'flagged')
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════════════════════════
    # Clarity Methods
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_team_members(self, team_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM team_members WHERE team_id = ? ORDER BY name", (team_id,))
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                for field in ("skills_json", "performance_evidence_json", "career_goals_json", "workload_json"):
                    if row.get(field):
                        row[field.replace("_json", "")] = json.loads(row[field])
            return rows

    def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_talent_decision_log(self, log_data: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO talent_decision_logs (
                    decision_id, manager_id, decision_type, business_goal,
                    gap_analysis_json, recommended_action, ai_recommendation_json,
                    manager_final_decision, manager_reasoning, manager_override_reason,
                    bias_risk_score, bias_categories_json, manager_patterns_json,
                    reflection_json, selected_candidate_id, candidate_match_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_data.get("decision_id"),
                log_data.get("manager_id"),
                log_data.get("decision_type"),
                log_data.get("business_goal"),
                json.dumps(log_data.get("gap_analysis", [])),
                log_data.get("recommended_action"),
                json.dumps(log_data.get("ai_recommendation", {})),
                log_data.get("manager_final_decision"),
                log_data.get("manager_reasoning"),
                log_data.get("manager_override_reason"),
                log_data.get("bias_risk_score", 0.0),
                json.dumps(log_data.get("bias_categories", [])),
                json.dumps(log_data.get("manager_patterns", [])),
                json.dumps(log_data.get("reflection", {})),
                log_data.get("selected_candidate_id"),
                json.dumps(log_data.get("candidate_match", [])),
            ))
            return log_data.get("decision_id")

    def update_talent_decision_manager(
        self,
        decision_id: str,
        manager_final_decision: str,
        manager_reasoning: str = None,
        manager_override_reason: str = None,
    ) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE talent_decision_logs
                SET manager_final_decision = ?,
                    manager_reasoning = COALESCE(?, manager_reasoning),
                    manager_override_reason = COALESCE(?, manager_override_reason)
                WHERE decision_id = ?
            """, (manager_final_decision, manager_reasoning, manager_override_reason, decision_id))
            return cursor.rowcount > 0

    def get_talent_decision_history(self, manager_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if manager_id:
                cursor.execute(
                    """
                    SELECT * FROM talent_decision_logs
                    WHERE manager_id = ? AND decision_type != 'gap_analysis'
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (manager_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM talent_decision_logs
                    WHERE decision_type != 'gap_analysis'
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def save_candidate_resume(self, resume_data: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candidate_resumes (
                    resume_id, candidate_id, role_id, filename, file_type,
                    raw_text, parsed_profile_json, anonymized_profile_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resume_data.get("resume_id"),
                resume_data.get("candidate_id"),
                resume_data.get("role_id"),
                resume_data.get("filename"),
                resume_data.get("file_type"),
                resume_data.get("raw_text"),
                json.dumps(resume_data.get("parsed_profile", {})),
                json.dumps(resume_data.get("anonymized_profile", {})),
            ))
            return resume_data.get("resume_id")

    def get_talent_analytics_summary(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM talent_decision_logs")
            total = cursor.fetchone()["cnt"]
            cursor.execute("SELECT AVG(bias_risk_score) as avg_bias FROM talent_decision_logs")
            avg_bias = cursor.fetchone()["avg_bias"] or 0.0
            cursor.execute(
                "SELECT recommended_action, COUNT(*) as cnt FROM talent_decision_logs GROUP BY recommended_action"
            )
            action_mix = {row["recommended_action"]: row["cnt"] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) as cnt FROM candidate_resumes")
            resumes = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM team_members")
            team_size = cursor.fetchone()["cnt"]
            return {
                "total_decisions": total,
                "avg_bias_risk_score": avg_bias,
                "recommended_action_mix": action_mix,
                "resumes_uploaded": resumes,
                "team_members": team_size,
            }

    # ----------------------------------------------------------------
    # Adaptive training recommendations
    # ----------------------------------------------------------------
    def save_training_recommendation(self, rec: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO training_recommendations (
                    training_id, manager_id, trigger_type, module_title,
                    module_type, module_payload_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rec.get("training_id"),
                rec.get("manager_id"),
                rec.get("trigger_type"),
                rec.get("module_title"),
                rec.get("module_type"),
                json.dumps(rec.get("module_payload", {})),
                rec.get("status", "recommended"),
            ))
            return rec.get("training_id")

    def get_training_recommendations(self, manager_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if manager_id:
                cursor.execute(
                    "SELECT * FROM training_recommendations WHERE manager_id = ? ORDER BY created_at DESC LIMIT ?",
                    (manager_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM training_recommendations ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            out = []
            for row in cursor.fetchall():
                r = dict(row)
                r["module_payload"] = self._loads(r.pop("module_payload_json", None), {})
                out.append(r)
            return out

    # ----------------------------------------------------------------
    # Durable manager-reflection queue
    # ----------------------------------------------------------------
    def save_reflection(self, item: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO reflection_queue (
                    decision_id, manager_id, business_goal, priority,
                    bias_risk_score, bias_categories_json, ai_recommendation,
                    reflection_questions_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                item.get("decision_id"),
                item.get("manager_id"),
                item.get("business_goal"),
                item.get("priority", "medium"),
                item.get("bias_risk_score", 0.0),
                json.dumps(item.get("bias_categories", [])),
                item.get("ai_recommendation"),
                json.dumps(item.get("reflection_questions", [])),
            ))
            return item.get("decision_id")

    def get_pending_reflections(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reflection_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            out = []
            for row in cursor.fetchall():
                r = dict(row)
                r["bias_categories"] = self._loads(r.pop("bias_categories_json", None), [])
                r["reflection_questions"] = self._loads(r.pop("reflection_questions_json", None), [])
                out.append(r)
            return out

    def resolve_reflection(self, decision_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reflection_queue SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE decision_id = ?",
                (decision_id,),
            )
            return cursor.rowcount > 0

    # ----------------------------------------------------------------
    # Workflow snapshots (persist gap-analysis state for manager choice)
    # ----------------------------------------------------------------
    def save_workflow_snapshot(self, decision_id: str, manager_id: str, state: Dict[str, Any], status: str = "awaiting_manager_choice") -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_snapshots (
                    decision_id, manager_id, state_json, status, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (decision_id, manager_id, json.dumps(state, default=str), status))
            return decision_id

    def get_workflow_snapshot(self, decision_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workflow_snapshots WHERE decision_id = ?", (decision_id,))
            row = cursor.fetchone()
            if not row:
                return None
            r = dict(row)
            r["state"] = self._loads(r.pop("state_json", None), {})
            return r

    def resolve_workflow_snapshot(self, decision_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE workflow_snapshots SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE decision_id = ?",
                (decision_id,),
            )
            return cursor.rowcount > 0

    def get_unified_decision_history(self, manager_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Merge workforce logs and hiring decision_events into one audit feed."""
        workforce = self.get_talent_decision_history(manager_id, limit=limit)
        events = self.get_decision_events(limit=limit * 2)
        if manager_id:
            events = [e for e in events if e.get("decision_maker_id") == manager_id]

        unified: List[Dict[str, Any]] = []

        for w in workforce:
            ai_rec = self._loads(w.get("ai_recommendation_json"), {})
            bias_cats = self._loads(w.get("bias_categories_json"), [])
            patterns = self._loads(w.get("manager_patterns_json"), [])
            reflection = self._loads(w.get("reflection_json"), {})
            post = reflection.get("post_decision_bias", {}) if isinstance(reflection, dict) else {}
            unified.append({
                "decision_id": w.get("decision_id"),
                "source": "workforce",
                "category": "workforce_planning",
                "created_at": w.get("created_at"),
                "business_goal": w.get("business_goal"),
                "manager_decision": w.get("manager_final_decision") or w.get("decision_type"),
                "ai_recommendation": w.get("recommended_action") or (ai_rec.get("primary_path") if isinstance(ai_rec, dict) else None),
                "ai_recommendation_detail": ai_rec,
                "manager_reasoning": w.get("manager_reasoning"),
                "manager_override_reason": w.get("manager_override_reason"),
                "override_flag": bool(w.get("manager_override_reason")),
                "bias_risk_score": w.get("bias_risk_score"),
                "post_decision_bias_score": post.get("score"),
                "bias_categories": bias_cats,
                "coaching_notes": post.get("coaching_notes"),
                "recurring_patterns": patterns,
                "decision_stage": None,
                "rubric_score": None,
                "candidate_label": None,
                "vague_reason_flag": False,
                "upskill_plan": reflection.get("upskill_plan") if isinstance(reflection, dict) else None,
            })

        for e in events:
            cid = e.get("candidate_id") or ""
            label = f"Candidate {cid.split('_')[-1]}" if "_" in cid else cid
            unified.append({
                "decision_id": e.get("decision_id"),
                "source": "hiring",
                "category": "resume_screen",
                "created_at": e.get("created_at") or e.get("decision_date"),
                "business_goal": e.get("job_id"),
                "manager_decision": e.get("human_decision") or e.get("decision_outcome"),
                "ai_recommendation": e.get("generated_recommendation"),
                "ai_recommendation_detail": None,
                "manager_reasoning": e.get("decision_reason"),
                "manager_override_reason": e.get("decision_reason") if e.get("override_flag") else None,
                "override_flag": e.get("override_flag", False),
                "bias_risk_score": None,
                "post_decision_bias_score": None,
                "bias_categories": [],
                "coaching_notes": None,
                "recurring_patterns": [],
                "decision_stage": e.get("decision_stage"),
                "rubric_score": e.get("rubric_score_at_decision"),
                "candidate_label": label,
                "vague_reason_flag": e.get("vague_reason_flag", False),
                "upskill_plan": None,
            })

        unified.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        return unified[:limit]


    # ================================================================
    # Bias-reduction hiring pipeline: jobs / candidates / applications
    # / scorecards / decision_events
    # ================================================================

    @staticmethod
    def _loads(value, default):
        if value is None:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def save_job(self, job: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, title, department, level, location, job_description_text,
                    must_have_criteria_json, nice_to_have_criteria_json,
                    responsibilities_json, rubric_weights_json, rubric_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                job.get("job_id"),
                job.get("title"),
                job.get("department"),
                job.get("level"),
                job.get("location"),
                job.get("job_description_text"),
                json.dumps(job.get("must_have_criteria", [])),
                json.dumps(job.get("nice_to_have_criteria", [])),
                json.dumps(job.get("responsibilities", [])),
                json.dumps(job.get("rubric_weights", {})),
                job.get("rubric_version", "v1"),
            ))
            return job.get("job_id")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            job = dict(row)
            job["must_have_criteria"] = self._loads(job.pop("must_have_criteria_json", None), [])
            job["nice_to_have_criteria"] = self._loads(job.pop("nice_to_have_criteria_json", None), [])
            job["responsibilities"] = self._loads(job.pop("responsibilities_json", None), [])
            job["rubric_weights"] = self._loads(job.pop("rubric_weights_json", None), {})
            return job

    def save_candidate(self, candidate: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candidates (
                    candidate_id, resume_id, extracted_skills_json, years_experience,
                    education_json, work_experience_json, projects_json,
                    certifications_json, leadership_experience_json, domain_experience_json,
                    extraction_confidence, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                candidate.get("candidate_id"),
                candidate.get("resume_id"),
                json.dumps(candidate.get("extracted_skills", [])),
                candidate.get("years_experience"),
                json.dumps(candidate.get("education", [])),
                json.dumps(candidate.get("work_experience", [])),
                json.dumps(candidate.get("projects", [])),
                json.dumps(candidate.get("certifications", [])),
                json.dumps(candidate.get("leadership_experience", [])),
                json.dumps(candidate.get("domain_experience", [])),
                candidate.get("extraction_confidence", 0.0),
            ))
            return candidate.get("candidate_id")

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            c = dict(row)
            c["extracted_skills"] = self._loads(c.pop("extracted_skills_json", None), [])
            c["education"] = self._loads(c.pop("education_json", None), [])
            c["work_experience"] = self._loads(c.pop("work_experience_json", None), [])
            c["projects"] = self._loads(c.pop("projects_json", None), [])
            c["certifications"] = self._loads(c.pop("certifications_json", None), [])
            c["leadership_experience"] = self._loads(c.pop("leadership_experience_json", None), [])
            c["domain_experience"] = self._loads(c.pop("domain_experience_json", None), [])
            return c

    def save_application(self, application: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO applications (
                    application_id, candidate_id, job_id, source, current_stage, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                application.get("application_id"),
                application.get("candidate_id"),
                application.get("job_id"),
                application.get("source", "upload"),
                application.get("current_stage", "resume_screen"),
                application.get("status", "active"),
            ))
            return application.get("application_id")

    def update_application_stage(self, application_id: str, stage: str, status: str = None) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE applications
                SET current_stage = ?, status = COALESCE(?, status), updated_at = CURRENT_TIMESTAMP
                WHERE application_id = ?
            """, (stage, status, application_id))
            return cursor.rowcount > 0

    def save_scorecard(self, scorecard: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scorecards (
                    scorecard_id, application_id, candidate_id, job_id,
                    criteria_scores_json, total_score, strengths_json, concerns_json,
                    missing_requirements_json, generated_recommendation, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                scorecard.get("scorecard_id"),
                scorecard.get("application_id"),
                scorecard.get("candidate_id"),
                scorecard.get("job_id"),
                json.dumps(scorecard.get("criteria_scores", [])),
                scorecard.get("total_score", 0.0),
                json.dumps(scorecard.get("strengths", [])),
                json.dumps(scorecard.get("concerns", [])),
                json.dumps(scorecard.get("missing_requirements", [])),
                scorecard.get("generated_recommendation"),
            ))
            return scorecard.get("scorecard_id")

    def _row_to_scorecard(self, row) -> Dict[str, Any]:
        s = dict(row)
        s["criteria_scores"] = self._loads(s.pop("criteria_scores_json", None), [])
        s["strengths"] = self._loads(s.pop("strengths_json", None), [])
        s["concerns"] = self._loads(s.pop("concerns_json", None), [])
        s["missing_requirements"] = self._loads(s.pop("missing_requirements_json", None), [])
        return s

    def get_scorecards_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scorecards WHERE job_id = ? ORDER BY total_score DESC", (job_id,)
            )
            return [self._row_to_scorecard(r) for r in cursor.fetchall()]

    def get_scorecard_for_application(self, application_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scorecards WHERE application_id = ? ORDER BY created_at DESC LIMIT 1",
                (application_id,),
            )
            row = cursor.fetchone()
            return self._row_to_scorecard(row) if row else None

    def save_decision_event(self, event: Dict[str, Any]) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO decision_events (
                    decision_id, application_id, candidate_id, job_id, decision_type,
                    decision_stage, decision_outcome, decision_maker_id,
                    rubric_score_at_decision, generated_recommendation, human_decision,
                    override_flag, decision_reason, vague_reason_flag, evidence_count,
                    stage_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                event.get("decision_id"),
                event.get("application_id"),
                event.get("candidate_id"),
                event.get("job_id"),
                event.get("decision_type"),
                event.get("decision_stage"),
                event.get("decision_outcome"),
                event.get("decision_maker_id"),
                event.get("rubric_score_at_decision"),
                event.get("generated_recommendation"),
                event.get("human_decision"),
                1 if event.get("override_flag") else 0,
                event.get("decision_reason"),
                1 if event.get("vague_reason_flag") else 0,
                event.get("evidence_count", 0),
            ))
            return event.get("decision_id")

    def get_decision_events(self, job_id: str = None, limit: int = 500) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if job_id:
                cursor.execute(
                    "SELECT * FROM decision_events WHERE job_id = ? ORDER BY created_at DESC LIMIT ?",
                    (job_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM decision_events ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            events = []
            for row in cursor.fetchall():
                e = dict(row)
                e["override_flag"] = bool(e.get("override_flag"))
                e["vague_reason_flag"] = bool(e.get("vague_reason_flag"))
                events.append(e)
            return events

    def list_applications(self, job_id: str = None, limit: int = 500) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if job_id:
                cursor.execute(
                    "SELECT * FROM applications WHERE job_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (job_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM applications ORDER BY updated_at DESC LIMIT ?", (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    # ----------------------------------------------------------------
    # Voluntary, self-reported candidate demographics (opt-in)
    # ----------------------------------------------------------------
    def set_candidate_demographic(self, candidate_id: str, group: str, job_id: str = None, consent: bool = True) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candidate_demographics (
                    candidate_id, job_id, self_reported_group, consent
                ) VALUES (?, ?, ?, ?)
            """, (candidate_id, job_id, group, 1 if consent else 0))
            return candidate_id

    def get_candidate_demographics(self, job_id: str = None) -> Dict[str, str]:
        """Return {candidate_id: group} for consented, voluntary records only."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if job_id:
                cursor.execute(
                    "SELECT candidate_id, self_reported_group FROM candidate_demographics WHERE consent = 1 AND (job_id = ? OR job_id IS NULL)",
                    (job_id,),
                )
            else:
                cursor.execute(
                    "SELECT candidate_id, self_reported_group FROM candidate_demographics WHERE consent = 1"
                )
            return {row["candidate_id"]: row["self_reported_group"] for row in cursor.fetchall()}


ModerationDatabase = TalentDecisionDatabase
