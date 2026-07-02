"""
Data models for Clarity.

Manager decision-support platform for workforce talent decisions:
gap analysis, hire/promote/upskill recommendations, bias detection, and pattern learning.
"""

from enum import Enum
from dataclasses import dataclass
from typing import TypedDict, List, Optional, Dict, Any


class WorkforceDecisionCategory(str, Enum):
    """Categories of workforce decisions processed by the platform."""

    GAP_ANALYSIS = "gap_analysis"
    HIRING = "hiring"
    RESUME_SCREENING = "resume_screening"
    PROMOTION = "promotion"
    UPSKILL = "upskill"
    TEAM_DYNAMICS = "team_dynamics"
    RECONSIDERATION = "reconsideration"
    QUICK_MANAGER_NOTE = "quick_manager_note"


class TalentDecisionType(str, Enum):
    """Types of decisions agents can make."""

    APPROVE = "approve"
    FLAG = "flag"
    WARN = "warn"
    NEEDS_REFLECTION = "needs_reflection"
    RECOMMEND_HIRE = "recommend_hire"
    RECOMMEND_PROMOTE = "recommend_promote"
    RECOMMEND_UPSKILL = "recommend_upskill"
    RECOMMEND_COMBINATION = "recommend_combination"
    ESCALATE_TO_HR = "escalate_to_hr"
    AWAIT_HUMAN = "await_human"
    HUMAN_APPROVED = "human_approved"
    HUMAN_ESCALATED = "human_escalated"


class TalentDecisionStatus(str, Enum):
    """Decision status throughout the talent decision pipeline."""

    SUBMITTED = "submitted"
    TEAM_ANALYSIS = "team_analysis"
    BIAS_REVIEW = "bias_review"
    FAIRNESS_POLICY_CHECK = "fairness_policy_check"
    SYNTHESIS = "synthesis"
    PENDING_MANAGER_REFLECTION = "pending_manager_reflection"
    AWAITING_MANAGER_CHOICE = "awaiting_manager_choice"
    PATTERN_SCORING = "pattern_scoring"
    DECISION_LOGGED = "decision_logged"
    COMPLETED = "completed"
    # Legacy compat
    ANALYZING = "team_analysis"
    TOXICITY_CHECK = "bias_review"
    POLICY_CHECK = "fairness_policy_check"
    REACT_SYNTHESIS = "synthesis"
    REPUTATION_SCORING = "pattern_scoring"
    APPEAL_REVIEW = "reconsideration"
    ACTION_ENFORCEMENT = "decision_logging"
    APPROVED = "completed"
    REMOVED = "flagged"
    WARNED = "warned"
    FLAGGED = "flagged"
    UNDER_REVIEW = "pending_manager_reflection"
    PENDING_HUMAN_REVIEW = "pending_manager_reflection"
    HUMAN_REVIEW_COMPLETED = "completed"
    ESCALATED = "escalate_to_hr"


class BiasRiskLevel(str, Enum):
    """Bias risk level classifications."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"


class FairnessPolicyCategory(str, Enum):
    """Fairness policy concern categories."""

    INCONSISTENT_CRITERIA = "inconsistent_criteria"
    MISSING_EVIDENCE = "missing_evidence"
    UNSUPPORTED_OVERRIDE = "unsupported_override"
    BIASED_JOB_DESCRIPTION = "biased_job_description"
    RESUME_RUBRIC_MISMATCH = "resume_rubric_mismatch"
    PRESTIGE_OVERRELIANCE = "prestige_overreliance"
    CULTURE_FIT_AMBIGUITY = "culture_fit_ambiguity"
    UNEQUAL_UPSKILL_ACCESS = "unequal_upskill_access"
    UNJUSTIFIED_HIRING = "unjustified_hiring"
    PROMOTION_READINESS_GAP = "promotion_readiness_gap"
    NONE = "none"


class ManagerPatternTier(str, Enum):
    """Manager pattern risk tiers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    # Legacy compat
    NEW_USER = "low"
    TRUSTED = "low"
    VETERAN = "low"
    MODERATOR = "low"
    FLAGGED = "medium"
    SUSPENDED = "high"
    BANNED = "critical"


class ReflectionTriggerReason(str, Enum):
    """Reasons for triggering manager reflection."""

    LOW_CONFIDENCE = "low_confidence"
    HIGH_BIAS_RISK = "high_bias_risk"
    HIGH_SEVERITY = "high_severity"
    RECONSIDERATION_REQUEST = "reconsideration_request"
    CONFLICTING_DECISIONS = "conflicting_decisions"
    EDGE_CASE = "edge_case"
    INCONSISTENT_CRITERIA = "inconsistent_criteria"
    MANAGER_OVERRIDE = "manager_override"
    POTENTIAL_FALSE_POSITIVE = "potential_false_positive"
    REPEATED_PATTERN = "repeated_pattern"
  # Legacy HITL alias values
    USER_APPEAL = "reconsideration_request"
    SENSITIVE_CONTENT = "edge_case"
    HIGH_PROFILE_USER = "edge_case"
    FIRST_OFFENSE_SEVERE = "high_severity"
    LEGAL_CONCERN = "high_severity"


# Backward compatibility aliases
ContentType = WorkforceDecisionCategory
ContentStatus = TalentDecisionStatus
DecisionType = TalentDecisionType
ToxicityLevel = BiasRiskLevel
PolicyCategory = FairnessPolicyCategory
ReputationTier = ManagerPatternTier
HITLTriggerReason = ReflectionTriggerReason


@dataclass
class TeamMemberProfile:
    """Team member profile information."""

    employee_id: str
    name: str
    role: str
    level: str = "L2"
    skills: List[str] = None
    performance_evidence: List[str] = None
    career_goals: List[str] = None
    workload: Dict[str, Any] = None


@dataclass
class ManagerProfile:
    """Manager profile information."""

    manager_id: str
    name: str
    role: str = "Manager"
    team_id: str = ""
    manager_pattern_score: float = 0.0
    manager_pattern_tier: str = "low"


@dataclass
class ContentMetadata:
    """Legacy content metadata (retained for API compatibility)."""

    content_id: str
    content_type: str
    platform: str
    created_at: str
    language: str
    parent_id: Optional[str] = None
    thread_id: Optional[str] = None
    media_urls: List[str] = None
    hashtags: List[str] = None
    mentions: List[str] = None


@dataclass
class UserProfile:
    """Legacy user profile (maps to manager in TalentOS context)."""

    user_id: str
    username: str
    account_age_days: int = 30
    total_posts: int = 0
    total_violations: int = 0
    previous_warnings: int = 0
    previous_suspensions: int = 0
    reputation_score: float = 0.7
    reputation_tier: str = "low"
    verified: bool = False
    follower_count: int = 0
    following_count: int = 0


@dataclass
class AgentDecision:
    """Represents a decision made by an agent."""

    agent_name: str
    decision: TalentDecisionType
    confidence: float
    reasoning: str
    flags: List[str]
    recommendations: List[str]
    extracted_data: Dict[str, Any]
    requires_human_review: bool = False
    processing_time: float = 0.0


class TalentDecisionState(TypedDict, total=False):
    """
    Central state object passed between all agents in the LangGraph workflow.
    """

    # Identification
    decision_id: str
    submission_id: str
    submission_timestamp: str
    content_id: str  # legacy alias for decision_id

    # Manager and team
    manager_id: str
    manager_name: str
    team_id: str
    team_name: str
    team_members: List[Dict[str, Any]]
    user_id: str  # legacy alias for manager_id
    username: str  # legacy alias for manager_name
    user_profile: ManagerProfile  # legacy

    # Decision packet
    decision_type: str
    business_goal: str
    timeline_months: Optional[int]
    budget_level: Optional[str]
    headcount_available: Optional[int]
    content_text: Optional[str]  # legacy: manager note or decision text
    content_type: str  # legacy alias for decision_type
    manager_reasoning: Optional[str]

    # Team gap analysis
    required_capabilities: List[Dict[str, Any]]
    team_capability_map: List[Dict[str, Any]]
    gap_analysis: List[Dict[str, Any]]
    critical_gaps: List[Dict[str, Any]]
    moderate_gaps: List[Dict[str, Any]]
    evidence_quality_score: float

    # Hiring role generation
    recommended_action: str
    hiring_role: Optional[Dict[str, Any]]
    generated_job_description: Optional[str]
    hiring_goals: List[str]
    interview_rubric: Dict[str, Any]

    # Resume intake and candidate matching
    uploaded_resumes: List[Dict[str, Any]]
    parsed_candidates: List[Dict[str, Any]]
    anonymized_candidates: List[Dict[str, Any]]
    candidate_match_results: List[Dict[str, Any]]
    shortlist: List[Dict[str, Any]]
    selected_candidate_id: Optional[str]

    # Promotion and upskilling
    promotion_recommendation: Optional[Dict[str, Any]]
    upskill_recommendation: Optional[Dict[str, Any]]

    # Bias and fairness
    bias_risk_score: float
    bias_risk_level: str
    bias_categories: List[str]
    fairness_flags: List[str]
    policy_violations: List[str]
    violation_severity: str
    toxicity_score: Optional[float]  # legacy alias for bias_risk_score
    toxicity_level: Optional[str]  # legacy alias for bias_risk_level
    toxicity_categories: List[str]  # legacy alias for bias_categories
    policy_flags: List[str]  # legacy alias for fairness_flags

    # Manager decision
    final_recommendation: Optional[Dict[str, Any]]
    decision_synthesis_confidence: float
    decision_synthesis_reasoning: str
    manager_final_decision: Optional[str]
    manager_override_reason: Optional[str]
    react_act_decision: Optional[str]  # legacy
    react_confidence: Optional[float]  # legacy
    react_reasoning: Optional[str]  # legacy
    react_think_output: Optional[str]  # legacy
    react_observe_result: Optional[str]  # legacy

    # Manager reflection
    reflection_required: bool
    reflection_questions: List[str]
    manager_reflection: Optional[str]
    hitl_required: bool  # legacy alias
    hitl_trigger_reasons: List[str]  # legacy
    hitl_checkpoint: Optional[str]  # legacy
    hitl_priority: Optional[str]  # legacy
    hitl_human_decision: Optional[str]  # legacy
    hitl_human_notes: Optional[str]  # legacy
    hitl_resolution_timestamp: Optional[str]  # legacy
    hitl_human_confidence_override: Optional[float]  # legacy
    hitl_waiting_since: Optional[str]  # legacy
    hitl_review_prompt: Optional[str]  # legacy

    # Manager pattern memory
    manager_pattern_score: float
    manager_pattern_tier: str
    manager_patterns: List[Dict[str, Any]]
    recommended_training: Optional[Dict[str, Any]]
    user_reputation_score: Optional[float]  # legacy
    user_reputation_tier: Optional[str]  # legacy
    user_risk_score: Optional[float]  # legacy
    user_history_flags: List[str]  # legacy

    # Reconsideration
    is_appeal: bool  # legacy alias for is_reconsideration
    is_reconsideration: bool
    reconsideration_reason: Optional[str]
    appeal_reason: Optional[str]  # legacy
    original_decision: Optional[str]

    # Decision logging
    moderation_action: Optional[str]  # legacy
    action_reason: str
    action_timestamp: Optional[str]
    decision_log_id: Optional[str]

    # Workflow tracking
    agent_decisions: List[AgentDecision]
    current_agent: str
    status: str
    requires_human_review: bool
    overall_confidence: float
    force_full_pipeline: bool
    created_at: str
    processed_at: Optional[str]

    # Memory/learning
    similar_content: Optional[List[Dict[str, Any]]]
    historical_patterns: Optional[List[Dict[str, Any]]]

    # Guardrails
    _guardrail_iteration: Optional[int]
    _guardrail_checks: Optional[List[Dict[str, Any]]]
    guardrail_violations: Optional[List[str]]
    guardrail_warnings: Optional[List[str]]


# Legacy alias
ContentState = TalentDecisionState


@dataclass
class BiasRiskAnalysis:
    """Bias risk detection analysis results."""

    bias_risk_score: float
    bias_risk_level: str
    categories: List[str]
    fairness_concerns: List[str]
    confidence: float


@dataclass
class FairnessPolicyAnalysis:
    """Fairness policy check analysis results."""

    violations: List[str]
    severity: str
    confidence: float
    flags: List[str]
    recommended_action: str
    reasoning: str


@dataclass
class ManagerPatternAnalysis:
    """Manager pattern scoring analysis results."""

    manager_pattern_score: float
    manager_pattern_tier: str
    recurring_patterns: List[str]
    recommended_training: Dict[str, Any]


@dataclass
class TalentDecisionLog:
    """Logged talent decision details."""

    action: str
    reason: str
    confidence: float
    bias_risk_score: float
    manager_pattern_score: float
    reflection_completed: bool
    timestamp: str


# Legacy aliases
ToxicityAnalysis = BiasRiskAnalysis
PolicyAnalysis = FairnessPolicyAnalysis
ReputationAnalysis = ManagerPatternAnalysis
ModerationAction = TalentDecisionLog


BIAS_RISK_THRESHOLDS = {
    "none": 0.2,
    "low": 0.4,
    "medium": 0.6,
    "high": 0.8,
    "severe": 0.9,
}
TOXICITY_THRESHOLDS = BIAS_RISK_THRESHOLDS

VIOLATION_SEVERITY = {
    "low": ["missing_evidence", "culture_fit_ambiguity"],
    "medium": ["inconsistent_criteria", "resume_rubric_mismatch"],
    "high": ["prestige_overreliance", "unsupported_override"],
    "critical": ["unjustified_hiring", "unequal_upskill_access"],
}

MANAGER_PATTERN_RANGES = {
    "low": (0.0, 0.4),
    "medium": (0.4, 0.6),
    "high": (0.6, 0.8),
    "critical": (0.8, 1.0),
}
REPUTATION_RANGES = MANAGER_PATTERN_RANGES

REFLECTION_CONFIG = {
    "confidence_threshold": 0.70,
    "bias_risk_threshold": 0.65,
    "agent_agreement_threshold": 0.60,
    "always_review_severities": ["critical", "high"],
    "manager_pattern_threshold": 0.70,
    "priority_weights": {
        "critical": 100,
        "high": 75,
        "medium": 50,
        "low": 25,
    },
    "checkpoints": {
        "post_analysis": True,
        "post_synthesis": True,
        "pre_logging": True,
        "post_pattern_scoring": True,
    },
    "reflection_questions": [
        "What business gap are you trying to close?",
        "Why is hire, promote, or upskill the best option?",
        "Did you compare all relevant people using the same criteria?",
        "Are you relying on visibility, similarity, school/company prestige, or recent events?",
        "If overriding the system recommendation, what evidence supports the override?",
        "What evidence would change your decision?",
    ],
}
HITL_CONFIG = REFLECTION_CONFIG

DECISION_SYNTHESIS_CONFIG = {
    "agent_weights": {
        "Team Gap Analysis Agent": 0.25,
        "Bias Signal Detection Agent": 0.30,
        "Fairness Policy Check Agent": 0.45,
    },
    "consensus_threshold": 0.67,
    "strong_consensus_threshold": 1.0,
    "decision_priority": {
        "escalate_to_hr": 7,
        "request_manager_reflection": 6,
        "recommend_hire": 5,
        "recommend_promote": 4,
        "recommend_upskill": 3,
        "recommend_combination": 3,
        "no_action": 1,
    },
}
REACT_CONFIG = DECISION_SYNTHESIS_CONFIG
