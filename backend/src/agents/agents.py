"""
Clarity Multi-Agent System.

Nine specialized AI agents for manager workforce decision support:
1. Team Gap Analysis Agent
2. Bias Signal Detection Agent
3. Fairness Policy Check Agent
4. Decision Synthesis Agent (ReAct-style)
5. Manager Reflection Agent
6. Manager Pattern Scoring Agent
7. Decision Reconsideration Agent
8. Decision Logging Agent
9. Quick Decision Check Agent
"""

import json
import logging
import uuid
from typing import Dict, List, Any
from datetime import datetime

from ..core.llm_provider import get_llm
from ..core.llm_retry import invoke_llm
from ..utils.json_utils import extract_json_from_llm_response
from ..core.models import (
    TalentDecisionState,
    AgentDecision,
    TalentDecisionType,
    TalentDecisionStatus,
    BiasRiskLevel,
    ManagerPatternTier,
    ReflectionTriggerReason,
    BIAS_RISK_THRESHOLDS,
    REFLECTION_CONFIG,
    DECISION_SYNTHESIS_CONFIG,
)
from ..memory.memory import TalentDecisionMemoryManager
from ..core.ubs_principles import UBS_CULTURE_FRAMEWORK
from ..core.product import PRODUCT_NAME

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ClarityTalentAgents:
    """Container for all Clarity workforce decision agents."""

    def __init__(self):
        logger.info("\nInitializing ClarityTalentAgents...")
        self.llm = get_llm("reasoning")
        self.fast_llm = get_llm("fast")
        self.llm_pro = self.llm
        self.llm_flash = self.fast_llm
        self.memory_manager = TalentDecisionMemoryManager()
        logger.info("ClarityTalentAgents initialization complete (OpenRouter)")

    def _parse_json_from_response(self, response) -> Dict[str, Any]:
        """Parse structured JSON from an LLM response."""
        try:
            return extract_json_from_llm_response(response)
        except (json.JSONDecodeError, ValueError):
            return {}

    def _record_decision(
        self,
        state: TalentDecisionState,
        agent_name: str,
        decision_type: TalentDecisionType,
        confidence: float,
        reasoning: str,
        flags: List[str],
        recommendations: List[str],
        extracted_data: Dict[str, Any],
        requires_review: bool,
        start_time: datetime,
    ) -> None:
        decision = AgentDecision(
            agent_name=agent_name,
            decision=decision_type,
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=reasoning,
            flags=flags,
            recommendations=recommendations,
            extracted_data=extracted_data,
            requires_human_review=requires_review,
            processing_time=(datetime.now() - start_time).total_seconds(),
        )
        state["agent_decisions"] = state.get("agent_decisions", []) + [decision]
        state["current_agent"] = agent_name
        state["requires_human_review"] = state.get("requires_human_review", False) or requires_review

    def _format_previous_decisions(self, state: TalentDecisionState) -> str:
        decisions = state.get("agent_decisions", [])
        if not decisions:
            return "No previous decisions"
        lines = []
        for dec in decisions:
            val = dec.decision.value if hasattr(dec.decision, "value") else str(dec.decision)
            lines.append(f"- {dec.agent_name}: {val} (confidence: {dec.confidence:.2%})")
        return "\n".join(lines)

    @staticmethod
    def _primary_path_from_action(action: str) -> str:
        """Map internal hire/promote/upskill to manager-facing two-path model."""
        a = (action or "").lower().replace("recommend_", "")
        if "hire" in a:
            return "hire_external"
        return "promote_internal"

    @staticmethod
    def _normalize_workforce_action(raw: str) -> str:
        """Normalize to hire|promote|upskill only."""
        a = (raw or "upskill").lower().replace("recommend_", "")
        if "hire" in a:
            return "hire"
        if "promote" in a:
            return "promote"
        if "upskill" in a:
            return "upskill"
        return "upskill"

    def team_gap_analysis_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 1: Analyze team capability gaps and parse resumes."""
        logger.info("\nAGENT 1: Team Gap Analysis Agent")
        start_time = datetime.now()
        flags, recommendations, extracted_data = [], [], {}

        try:
            prompt = f"""
You are the Team Gap Analysis Agent for Clarity.

Clarity is used by one manager responsible for one 5-person team.

Analyze this workforce decision packet.

Business goal:
{state.get('business_goal', '')}

Timeline:
{state.get('timeline_months', 'Not specified')}

Budget/headcount:
{state.get('budget_level', 'Not specified')}, {state.get('headcount_available', 'Not specified')}

Team members:
{json.dumps(state.get('team_members', []), indent=2)}

Required capabilities:
{json.dumps(state.get('required_capabilities', []), indent=2)}

Uploaded resumes, if any:
{json.dumps(state.get('uploaded_resumes', []), indent=2)}

Your tasks:
1. Identify capabilities required to meet the business goal.
2. Compare those capabilities against the current 5-person team.
3. Identify critical and moderate capability gaps.
4. If resumes are included, extract structured candidate profiles.
5. Do not make the final hire/promote/upskill decision yet.
6. ALWAYS generate a gap-based hiring role draft for resume screening (even if hire is not the final recommendation).
7. Return structured JSON only.

Return:
{{
  "business_goal_summary": "...",
  "required_capabilities": [
    {{
      "capability": "...",
      "required_level": 1,
      "business_criticality": 0.0,
      "urgency": 0.0
    }}
  ],
  "team_capability_map": [
    {{
      "employee_id": "...",
      "current_strengths": [],
      "development_gaps": [],
      "promotion_readiness_evidence": []
    }}
  ],
  "critical_gaps": [],
  "moderate_gaps": [],
  "gap_based_hiring_role": {{
    "role_title": "...",
    "job_description": "Full bias-safe job description derived from critical/moderate gaps",
    "responsibilities": [],
    "required_skills": [],
    "nice_to_have_skills": [],
    "gap_capabilities_addressed": [],
    "interview_rubric": {{}}
  }},
  "parsed_candidates": [
    {{
      "candidate_id": "...",
      "skills": [],
      "experience": [],
      "projects": [],
      "education": [],
      "certifications": [],
      "role_relevant_evidence": []
    }}
  ],
  "evidence_quality_score": 0.0
}}
"""
            response = invoke_llm(self.fast_llm, prompt)
            result = self._parse_json_from_response(response)

            state["required_capabilities"] = result.get("required_capabilities", state.get("required_capabilities", []))
            state["team_capability_map"] = result.get("team_capability_map", [])
            state["critical_gaps"] = result.get("critical_gaps", [])
            state["moderate_gaps"] = result.get("moderate_gaps", [])
            state["gap_analysis"] = result.get("critical_gaps", []) + result.get("moderate_gaps", [])
            state["parsed_candidates"] = result.get("parsed_candidates", [])
            state["evidence_quality_score"] = float(result.get("evidence_quality_score", 0.5))

            gap_hiring = result.get("gap_based_hiring_role")
            if gap_hiring and gap_hiring.get("job_description"):
                state["hiring_role"] = gap_hiring
                state["generated_job_description"] = gap_hiring.get("job_description", "")

            state["status"] = TalentDecisionStatus.BIAS_REVIEW.value

            extracted_data = result
            confidence = state["evidence_quality_score"]

            self._record_decision(
                state, "Team Gap Analysis Agent", TalentDecisionType.APPROVE,
                confidence, response.content[:500], flags, recommendations,
                extracted_data, False, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Team Gap Analysis Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            state["requires_human_review"] = True
            self._record_decision(
                state, "Team Gap Analysis Agent", TalentDecisionType.NEEDS_REFLECTION,
                0.0, str(e), ["processing_error"], ["Manual review required"],
                {}, True, start_time,
            )
        return state

    def bias_signal_detection_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 2: Detect bias signals in workforce decisions."""
        logger.info("\nAGENT 2: Bias Signal Detection Agent")
        start_time = datetime.now()
        flags, recommendations, extracted_data = [], [], {}

        try:
            prompt = f"""
You are the Bias Signal Detection Agent for Clarity.

Review this workforce decision for potential unconscious bias signals.

Decision type:
{state.get('decision_type', '')}

Business goal:
{state.get('business_goal', '')}

Gap analysis:
{json.dumps(state.get('gap_analysis', []), indent=2)}

Generated job description:
{state.get('generated_job_description', 'Not yet generated')}

Candidate resume matches:
{json.dumps(state.get('candidate_match_results', []), indent=2)}

Promotion recommendation:
{json.dumps(state.get('promotion_recommendation', {}), indent=2)}

Upskill recommendation:
{json.dumps(state.get('upskill_recommendation', {}), indent=2)}

Manager reasoning:
{state.get('manager_reasoning', '')}

Check for:
1. Affinity bias
2. Visibility bias
3. Recency bias
4. Halo or horn effect
5. Prestige bias in resume screening
6. Vague culture-fit reasoning
7. Gendered or personality-coded language
8. Unsupported subjective claims
9. Inconsistent criteria across candidates or employees
10. Overusing external hiring when internal upskilling is feasible
11. Unequal access to development opportunities

Return JSON only:
{{
  "bias_risk_score": 0.0,
  "bias_risk_level": "none/low/medium/high/severe",
  "bias_categories": [],
  "flagged_phrases": [],
  "fairness_concerns": [],
  "recommended_reframes": [],
  "requires_reflection": true
}}
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            bias_score = float(result.get("bias_risk_score", 0.0))
            state["bias_risk_score"] = bias_score
            state["toxicity_score"] = bias_score  # legacy compat
            state["bias_risk_level"] = result.get("bias_risk_level", "none")
            state["toxicity_level"] = state["bias_risk_level"]
            state["bias_categories"] = result.get("bias_categories", [])
            state["toxicity_categories"] = state["bias_categories"]
            state["fairness_flags"] = result.get("fairness_concerns", [])
            state["policy_flags"] = state["fairness_flags"]
            state["reflection_required"] = result.get("requires_reflection", bias_score >= 0.65)
            state["hitl_required"] = state["reflection_required"]
            state["status"] = TalentDecisionStatus.FAIRNESS_POLICY_CHECK.value

            extracted_data = result
            self._record_decision(
                state, "Bias Signal Detection Agent",
                TalentDecisionType.FLAG if bias_score >= 0.4 else TalentDecisionType.APPROVE,
                1.0 - bias_score if bias_score < 0.5 else 0.5,
                response.content[:500], flags, recommendations, extracted_data,
                state["reflection_required"], start_time,
            )
        except Exception as e:
            logger.error(f"Error in Bias Signal Detection Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            self._record_decision(
                state, "Bias Signal Detection Agent", TalentDecisionType.NEEDS_REFLECTION,
                0.0, str(e), ["processing_error"], [], {}, True, start_time,
            )
        return state

    def fairness_policy_check_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 3: Check fairness policy and generate hire/promote/upskill recommendations."""
        logger.info("\nAGENT 3: Fairness Policy Check Agent")
        start_time = datetime.now()
        flags, recommendations, extracted_data = [], [], {}

        try:
            prompt = f"""
You are the Fairness Policy Check Agent for {PRODUCT_NAME}.

Review the workforce recommendation against UBS culture standards and fair decision-making rules.

{UBS_CULTURE_FRAMEWORK}

Business goal:
{state.get('business_goal', '')}

Gap analysis:
{json.dumps(state.get('gap_analysis', []), indent=2)}

Current recommended action:
{state.get('recommended_action', 'Not yet determined')}

Hiring role:
{json.dumps(state.get('hiring_role', {}), indent=2)}

Generated job description:
{state.get('generated_job_description', 'Not yet generated')}

Interview rubric:
{json.dumps(state.get('interview_rubric', {}), indent=2)}

Candidate match results:
{json.dumps(state.get('candidate_match_results', []), indent=2)}

Parsed candidates:
{json.dumps(state.get('parsed_candidates', []), indent=2)}

Promotion recommendation:
{json.dumps(state.get('promotion_recommendation', {}), indent=2)}

Upskill recommendation:
{json.dumps(state.get('upskill_recommendation', {}), indent=2)}

Manager reasoning:
{state.get('manager_reasoning', '')}

Check against UBS Pillars, Principles, and Behaviors AND fair workforce practice:
1. Is the recommendation tied to a real team gap? (Client centricity, Accountability with integrity)
2. Are all candidates or team members evaluated using the same criteria? (Collaboration, inclusive environment)
3. Is the recommendation evidence-based? (Accountability with integrity, Risk management)
4. Is the job description job-relevant, bias-safe, and client-focused? (Client centricity, Simplification)
5. Is resume screening based on the structured rubric? (Risk management, Accountability)
6. Is promotion based on readiness evidence across all 5 team members? (Collaboration, equitable environment)
7. Is upskilling recommended fairly rather than repeatedly favoring the same person? (Sustainable impact, Collaboration)
8. If the manager overrode the recommendation, is the override evidence-based? (Accountability with integrity)
9. Does the path support long-term talent sustainability vs short-term convenience? (Sustainable impact, Innovation)

For each violation, cite the relevant UBS Pillar, Principle, or Behavior by name.

IMPORTANT: recommended_action MUST be exactly one of: hire, promote, upskill (no combination, no_action, or escalate).
- For promote: promotion_recommendation MUST include recommended_employee_id from the team and recommended_employee_name.
- For upskill: upskill_recommendation MUST include recommended_employee_id from the team and recommended_employee_name.
- ALWAYS populate hiring_role with a full gap-based job description for resume screening, derived from critical/moderate gaps.

Team members (use these employee_id values):
{json.dumps(state.get('team_members', []), indent=2)}

Return JSON only:
{{
  "policy_passed": true,
  "violations": [],
  "ubs_principle_violations": [],
  "violation_severity": "none/low/medium/high/critical",
  "recommended_action": "hire|promote|upskill",
  "hiring_role": {{
    "role_title": "...",
    "job_description": "Full job description addressing identified gaps",
    "responsibilities": [],
    "required_skills": [],
    "nice_to_have_skills": [],
    "gap_capabilities_addressed": [],
    "hiring_goals_90_days": [],
    "interview_rubric": {{}}
  }},
  "promotion_recommendation": {{
    "recommended_employee_id": "...",
    "recommended_employee_name": "...",
    "rationale": "...",
    "evidence": [],
    "readiness_gaps": [],
    "first_90_day_goals": []
  }},
  "upskill_recommendation": {{
    "recommended_employee_id": "...",
    "recommended_employee_name": "...",
    "skill_gap": "...",
    "learning_path": [],
    "practice_project": "...",
    "timeline_weeks": 0,
    "success_metrics": []
  }},
  "candidate_match_results": [],
  "fairness_notes": [],
  "ubs_alignment_notes": [],
  "confidence": 0.0,
  "primary_path": "hire_external|promote_internal",
  "path_comparison": {{
    "hire_external": {{"pros": [], "cons": [], "conviction": 0.0}},
    "promote_internal": {{"pros": [], "cons": [], "conviction": 0.0, "promote_target": "...", "upskill_summary": "..."}}
  }}
}}
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            state["policy_violations"] = result.get("violations", []) + result.get("ubs_principle_violations", [])
            state["violation_severity"] = result.get("violation_severity", "none")
            state["recommended_action"] = self._normalize_workforce_action(
                result.get("recommended_action", "upskill")
            )
            state["primary_path"] = result.get("primary_path") or self._primary_path_from_action(
                state["recommended_action"]
            )
            state["path_comparison"] = result.get("path_comparison", {})

            members_by_id = {m["employee_id"]: m for m in state.get("team_members", [])}

            hiring_role = result.get("hiring_role")
            if hiring_role:
                state["hiring_role"] = hiring_role
                state["generated_job_description"] = hiring_role.get("job_description", "")
                state["hiring_goals"] = hiring_role.get("hiring_goals_90_days", [])
                state["interview_rubric"] = hiring_role.get("interview_rubric", {})

            if result.get("promotion_recommendation"):
                pr = result["promotion_recommendation"]
                eid = pr.get("recommended_employee_id")
                if eid in members_by_id:
                    pr["recommended_employee_name"] = members_by_id[eid].get("name")
                state["promotion_recommendation"] = pr
            if result.get("upskill_recommendation"):
                ur = result["upskill_recommendation"]
                eid = ur.get("recommended_employee_id")
                if eid in members_by_id:
                    ur["recommended_employee_name"] = members_by_id[eid].get("name")
                state["upskill_recommendation"] = ur
            if result.get("candidate_match_results"):
                state["candidate_match_results"] = result["candidate_match_results"]
                state["shortlist"] = [
                    c for c in result["candidate_match_results"]
                    if c.get("recommendation") in ("advance", "shortlist")
                ]

            state["status"] = TalentDecisionStatus.SYNTHESIS.value
            extracted_data = result
            confidence = float(result.get("confidence", 0.75))

            self._record_decision(
                state, "Fairness Policy Check Agent",
                TalentDecisionType.APPROVE if result.get("policy_passed", True) else TalentDecisionType.FLAG,
                confidence, response.content[:500], flags, recommendations, extracted_data,
                len(state["policy_violations"]) > 0, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Fairness Policy Check Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            self._record_decision(
                state, "Fairness Policy Check Agent", TalentDecisionType.NEEDS_REFLECTION,
                0.0, str(e), ["processing_error"], [], {}, True, start_time,
            )
        return state

    def decision_synthesis_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 4: ReAct-style decision synthesis."""
        logger.info("\nAGENT 4: Decision Synthesis Agent (Think → Act → Observe)")
        start_time = datetime.now()
        flags, recommendations, extracted_data = [], [], {}

        try:
            prompt = f"""
You are the Decision Synthesis Agent for Clarity.

You must synthesize previous agent outputs and produce the final workforce recommendation.

Business goal:
{state.get('business_goal', '')}

Team gap analysis:
{json.dumps(state.get('gap_analysis', []), indent=2)}

Bias risk:
{state.get('bias_risk_score', 0.0)}
{json.dumps(state.get('bias_categories', []))}

Fairness policy check:
{json.dumps(state.get('policy_violations', []))}
Severity: {state.get('violation_severity', 'none')}

Hiring role:
{json.dumps(state.get('hiring_role', {}), indent=2)}

Candidate match results:
{json.dumps(state.get('candidate_match_results', []), indent=2)}

Promotion recommendation:
{json.dumps(state.get('promotion_recommendation', {}), indent=2)}

Upskill recommendation:
{json.dumps(state.get('upskill_recommendation', {}), indent=2)}

Manager reasoning:
{state.get('manager_reasoning', '')}

Think:
1. What is the actual team gap?
2. Can the gap be solved internally?
3. Is hiring justified?
4. Is promotion justified?
5. Is upskilling more appropriate?
6. Does the decision have bias risk?
7. Should manager reflection be required?

Act - Choose exactly ONE of:
- recommend_hire
- recommend_promote
- recommend_upskill

Do NOT use combination, no_action, or escalate unless bias risk is severe and reflection is mandatory.

Observe: Explain the recommended next step, evidence, risks, and confidence.
For promote/upskill, name the specific team member in final_recommendation.

Return JSON only:
{{
  "final_recommendation_type": "recommend_hire|recommend_promote|recommend_upskill",
  "final_recommendation": {{
    "action": "hire|promote|upskill",
    "target_employee_id": "emp_xxx or null for hire",
    "target_employee_name": "Name or null for hire",
    "summary": "..."
  }},
  "confidence": 0.0,
  "reasoning": "...",
  "reflection_required": true,
  "reflection_triggers": [],
  "next_steps": [],
  "primary_path": "hire_external|promote_internal",
  "path_comparison": {{
    "hire_external": {{"summary": "...", "conviction": 0.0}},
    "promote_internal": {{"summary": "...", "conviction": 0.0, "promote_target": "...", "upskill_plan": "..."}}
  }}
}}
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            rec_type = self._normalize_workforce_action(
                result.get("final_recommendation_type", result.get("final_recommendation", {}).get("action", "upskill"))
            )
            if not str(rec_type).startswith("recommend_"):
                rec_type = f"recommend_{rec_type}"
            confidence = float(result.get("confidence", 0.5))
            reflection_required = result.get("reflection_required", False)

            # Auto-trigger reflection based on thresholds
            if state.get("bias_risk_score", 0) >= REFLECTION_CONFIG["bias_risk_threshold"]:
                reflection_required = True
                flags.append("high_bias_risk")
            if state.get("violation_severity", "none") in ["medium", "high", "critical"]:
                reflection_required = True
            if confidence < REFLECTION_CONFIG["confidence_threshold"]:
                reflection_required = True
            if "inconsistent_criteria" in state.get("bias_categories", []):
                reflection_required = True
            if state.get("manager_override_reason"):
                reflection_required = True

            state["final_recommendation"] = {
                "type": rec_type,
                **(result.get("final_recommendation") or {}),
            }
            state["decision_synthesis_confidence"] = confidence
            state["decision_synthesis_reasoning"] = result.get("reasoning", "")
            state["react_act_decision"] = rec_type
            state["react_confidence"] = confidence
            state["react_reasoning"] = result.get("reasoning", "")
            state["reflection_required"] = reflection_required
            state["hitl_required"] = reflection_required
            state["reflection_questions"] = REFLECTION_CONFIG["reflection_questions"] if reflection_required else []
            state["hitl_trigger_reasons"] = result.get("reflection_triggers", [])
            state["primary_path"] = result.get("primary_path") or self._primary_path_from_action(rec_type)
            state["path_comparison"] = result.get("path_comparison", {})
            state["status"] = TalentDecisionStatus.AWAITING_MANAGER_CHOICE.value

            decision_map = {
                "recommend_hire": TalentDecisionType.RECOMMEND_HIRE,
                "recommend_promote": TalentDecisionType.RECOMMEND_PROMOTE,
                "recommend_upskill": TalentDecisionType.RECOMMEND_UPSKILL,
                "hire": TalentDecisionType.RECOMMEND_HIRE,
                "promote": TalentDecisionType.RECOMMEND_PROMOTE,
                "upskill": TalentDecisionType.RECOMMEND_UPSKILL,
            }
            decision_type = decision_map.get(rec_type, TalentDecisionType.RECOMMEND_UPSKILL)

            self._record_decision(
                state, "Decision Synthesis Agent", decision_type, confidence,
                result.get("reasoning", ""), flags, result.get("next_steps", []),
                result, reflection_required, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Decision Synthesis Agent: {e}")
            state["reflection_required"] = True
            state["hitl_required"] = True
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            self._record_decision(
                state, "Decision Synthesis Agent", TalentDecisionType.NEEDS_REFLECTION,
                0.0, str(e), ["processing_error"], [], {}, True, start_time,
            )
        return state

    def manager_decision_bias_review_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Review manager's final hire_external / promote_internal choice and reasoning."""
        logger.info("\nAGENT: Manager Decision Bias Review")
        start_time = datetime.now()

        try:
            prompt = f"""
You are the Manager Decision Bias Review Agent for Clarity.

The manager has submitted their workforce decision. Review it for bias risk and evidence quality.

Business goal:
{state.get('business_goal', '')}

Gap analysis:
{json.dumps(state.get('gap_analysis', []), indent=2)}

AI primary path (guidance only):
{state.get('primary_path', state.get('recommended_action', ''))}

AI path comparison:
{json.dumps(state.get('path_comparison', {}), indent=2)}

Manager choice:
{state.get('manager_final_decision', '')}

Manager reasoning:
{state.get('manager_reasoning', '')}

Manager override reason:
{state.get('manager_override_reason', '')}

Target employee (if promote_internal):
{state.get('final_recommendation', {}).get('target_employee_name', '')}

Upskill plan:
{state.get('upskill_plan', '')}

Pre-decision bias score: {state.get('bias_risk_score', 0)}
Pre-decision categories: {json.dumps(state.get('bias_categories', []))}

Check for: vague language, culture-fit terms, prestige bias, inconsistent criteria vs gap evidence,
override without job-related evidence, favoritism in promote_internal choice.

Return JSON only:
{{
  "post_decision_bias_score": 0.0,
  "post_decision_bias_categories": [],
  "coaching_notes": "...",
  "override_vs_ai": true,
  "reason_quality": "specific|mixed|vague",
  "flags": []
}}
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            post_score = float(result.get("post_decision_bias_score", state.get("bias_risk_score", 0)))
            post_cats = result.get("post_decision_bias_categories", [])
            state["post_decision_bias"] = {
                "score": post_score,
                "categories": post_cats,
                "coaching_notes": result.get("coaching_notes", ""),
                "override_vs_ai": result.get("override_vs_ai", False),
                "reason_quality": result.get("reason_quality", "mixed"),
            }
            state["bias_risk_score"] = max(state.get("bias_risk_score", 0), post_score)
            merged = list(set((state.get("bias_categories") or []) + post_cats))
            state["bias_categories"] = merged

            self._record_decision(
                state, "Manager Decision Bias Review Agent", TalentDecisionType.APPROVE,
                1.0 - post_score, result.get("coaching_notes", ""),
                result.get("flags", []), [], result, False, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Manager Decision Bias Review Agent: {e}")
            state["post_decision_bias"] = {
                "score": state.get("bias_risk_score", 0),
                "categories": [],
                "coaching_notes": "Post-decision review unavailable.",
                "override_vs_ai": False,
                "reason_quality": "mixed",
            }
        return state

    def manager_reflection_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 5: Manager reflection checkpoint (formerly HITL)."""
        logger.info("\nAGENT 5: Manager Reflection Agent")
        start_time = datetime.now()

        try:
            if state.get("hitl_human_decision") or state.get("manager_final_decision"):
                return self._process_manager_decision(state)

            state["reflection_required"] = True
            state["hitl_required"] = True
            state["reflection_questions"] = REFLECTION_CONFIG["reflection_questions"]
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            state["hitl_waiting_since"] = datetime.now().isoformat()
            state["hitl_checkpoint"] = "post_synthesis"

            priority = self._calculate_reflection_priority(state)
            state["hitl_priority"] = priority

            summary = self._prepare_reflection_summary(state)
            state["hitl_review_prompt"] = summary

            self._record_decision(
                state, "Manager Reflection Agent", TalentDecisionType.AWAIT_HUMAN,
                1.0, f"Manager reflection required. Priority: {priority}",
                [f"reflection_{priority}"], state["reflection_questions"],
                {"summary": summary}, True, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Manager Reflection Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value

        return state

    def _process_manager_decision(self, state: TalentDecisionState) -> TalentDecisionState:
        """Process manager reflection decision."""
        human_decision = (
            state.get("hitl_human_decision")
            or state.get("manager_final_decision", "")
        ).lower()
        notes = state.get("hitl_human_notes") or state.get("manager_reflection", "")

        decision_map = {
            "accept_recommendation": (TalentDecisionType.HUMAN_APPROVED, TalentDecisionStatus.PATTERN_SCORING),
            "approve": (TalentDecisionType.HUMAN_APPROVED, TalentDecisionStatus.PATTERN_SCORING),
            "revise_decision": (TalentDecisionType.FLAG, TalentDecisionStatus.PATTERN_SCORING),
            "override_with_reason": (TalentDecisionType.FLAG, TalentDecisionStatus.PATTERN_SCORING),
            "escalate_to_hr": (TalentDecisionType.ESCALATE_TO_HR, TalentDecisionStatus.ESCALATED),
            "escalate": (TalentDecisionType.ESCALATE_TO_HR, TalentDecisionStatus.ESCALATED),
        }

        decision_type, new_status = decision_map.get(
            human_decision,
            (TalentDecisionType.NEEDS_REFLECTION, TalentDecisionStatus.PENDING_MANAGER_REFLECTION),
        )

        state["status"] = new_status.value
        state["manager_reflection"] = notes
        state["hitl_resolution_timestamp"] = datetime.now().isoformat()
        state["reflection_required"] = False
        state["hitl_required"] = False

        decision = AgentDecision(
            agent_name="Manager Reflection",
            decision=decision_type,
            confidence=state.get("hitl_human_confidence_override", 1.0),
            reasoning=f"Manager decision: {human_decision}. Notes: {notes}",
            flags=["manager_reviewed"],
            recommendations=[f"Proceed with {human_decision}"],
            extracted_data={"manager_decision": human_decision, "notes": notes},
            requires_human_review=False,
            processing_time=0.0,
        )
        state["agent_decisions"] = state.get("agent_decisions", []) + [decision]
        state["current_agent"] = "Manager Reflection"
        return state

    def manager_pattern_scoring_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 6: Analyze recurring manager bias patterns."""
        logger.info("\nAGENT 6: Manager Pattern Scoring Agent")
        start_time = datetime.now()

        try:
            manager_id = state.get("manager_id") or state.get("user_id", "unknown")
            manager_history = self.memory_manager.get_manager_decision_history(manager_id, limit=20)

            prompt = f"""
You are the Manager Pattern Scoring Agent for Clarity.

Analyze whether this manager shows recurring bias patterns across workforce decisions.

Manager ID:
{manager_id}

Current decision:
{json.dumps(state.get('final_recommendation', {}), indent=2)}

Manager reasoning:
{state.get('manager_reasoning', '')}

Bias categories in current decision:
{json.dumps(state.get('bias_categories', []))}

Previous manager decision history:
{json.dumps(manager_history[:10], indent=2)}

Check for recurring patterns:
1. Repeatedly choosing external hiring when upskilling is feasible.
2. Repeatedly favoring prestigious schools or companies in resumes.
3. Repeatedly using vague culture-fit language.
4. Repeatedly promoting the most visible person.
5. Repeatedly relying on recent events.
6. Repeatedly overriding recommendations without evidence.
7. Repeatedly assigning stretch opportunities to the same people.
8. Repeatedly overlooking internal growth options.

Return JSON only:
{{
  "manager_pattern_score": 0.0,
  "manager_pattern_tier": "low/medium/high/critical",
  "recurring_patterns": [],
  "pattern_evidence": [],
  "recommended_training": {{}},
  "requires_reflection": true
}}
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            pattern_score = float(result.get("manager_pattern_score", 0.0))
            state["manager_pattern_score"] = pattern_score
            state["user_reputation_score"] = pattern_score  # legacy
            state["manager_pattern_tier"] = result.get("manager_pattern_tier", "low")
            state["user_reputation_tier"] = state["manager_pattern_tier"]
            state["manager_patterns"] = [
                {"pattern": p, "evidence": result.get("pattern_evidence", [])}
                for p in result.get("recurring_patterns", [])
            ]
            state["recommended_training"] = result.get("recommended_training", {})

            if pattern_score >= REFLECTION_CONFIG.get("manager_pattern_threshold", 0.70):
                state["reflection_required"] = True
                state["hitl_required"] = True

            state["status"] = TalentDecisionStatus.DECISION_LOGGED.value

            self._record_decision(
                state, "Manager Pattern Scoring Agent", TalentDecisionType.APPROVE,
                1.0 - pattern_score, response.content[:500], result.get("recurring_patterns", []),
                [], result, result.get("requires_reflection", False), start_time,
            )
        except Exception as e:
            logger.error(f"Error in Manager Pattern Scoring Agent: {e}")
            state["manager_pattern_score"] = 0.0
            state["manager_pattern_tier"] = "low"
            state["status"] = TalentDecisionStatus.DECISION_LOGGED.value

        return state

    def decision_reconsideration_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 7: Handle reconsideration requests."""
        logger.info("\nAGENT 7: Decision Reconsideration Agent")
        start_time = datetime.now()

        try:
            evidence = (
                state.get("candidate_match_results")
                or state.get("promotion_recommendation")
                or state.get("upskill_recommendation")
            )
            prompt = f"""
You are the Decision Reconsideration Agent for Clarity.

Review this reconsideration request.

Original decision:
{state.get('manager_final_decision', state.get('original_decision', ''))}

Original recommendation:
{json.dumps(state.get('final_recommendation', {}), indent=2)}

Gap analysis:
{json.dumps(state.get('gap_analysis', []), indent=2)}

Candidate / employee evidence:
{json.dumps(evidence, indent=2)}

Bias concerns:
{json.dumps(state.get('bias_categories', []))}
{json.dumps(state.get('policy_violations', []))}

Reconsideration reason:
{state.get('reconsideration_reason', state.get('appeal_reason', ''))}

Decide: uphold_decision, revise_decision, overturn_decision, or escalate_to_hr

Return JSON with decision, reasoning, and confidence.
"""
            response = invoke_llm(self.llm, prompt)
            result = self._parse_json_from_response(response)

            decision_str = result.get("decision", "uphold_decision")
            decision_map = {
                "uphold_decision": TalentDecisionType.APPROVE,
                "revise_decision": TalentDecisionType.FLAG,
                "overturn_decision": TalentDecisionType.HUMAN_APPROVED,
                "escalate_to_hr": TalentDecisionType.ESCALATE_TO_HR,
            }

            self._record_decision(
                state, "Decision Reconsideration Agent",
                decision_map.get(decision_str, TalentDecisionType.FLAG),
                float(result.get("confidence", 0.75)),
                result.get("reasoning", response.content[:500]),
                [], [], result, False, start_time,
            )
            state["status"] = TalentDecisionStatus.DECISION_LOGGED.value
        except Exception as e:
            logger.error(f"Error in Decision Reconsideration Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value

        return state

    def decision_logging_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 8: Log final workforce decision to SQLite + ChromaDB."""
        logger.info("\nAGENT 8: Decision Logging Agent")
        start_time = datetime.now()

        try:
            decision_id = state.get("decision_id") or state.get("content_id", str(uuid.uuid4()))
            state["decision_log_id"] = f"log_{decision_id}"
            state["action_timestamp"] = datetime.now().isoformat()
            state["processed_at"] = state["action_timestamp"]

            final_rec = state.get("final_recommendation", {})
            rec_type = final_rec.get("type", state.get("react_act_decision", "no_action"))
            state["moderation_action"] = rec_type
            state["action_reason"] = state.get("decision_synthesis_reasoning", "Decision logged")

            self.memory_manager.store_talent_decision(
                decision_id=decision_id,
                decision_text=state.get("business_goal", "") or state.get("content_text", ""),
                manager_id=state.get("manager_id") or state.get("user_id", "unknown"),
                action=rec_type,
                violations=state.get("policy_violations", []),
                bias_risk_score=state.get("bias_risk_score", 0.0),
                agent_decisions=state.get("agent_decisions", []),
                primary_agent="Decision Logging Agent",
                decision_context=f"decision_{state.get('decision_type', 'unknown')}",
                confidence=state.get("decision_synthesis_confidence", 0.0),
                gap_analysis=state.get("gap_analysis", []),
                manager_reasoning=state.get("manager_reasoning", ""),
                manager_override_reason=state.get("manager_override_reason", ""),
                bias_categories=state.get("bias_categories", []),
                manager_pattern_score=state.get("manager_pattern_score", 0.0),
                final_decision=state.get("manager_final_decision", rec_type),
            )

            state["status"] = TalentDecisionStatus.COMPLETED.value

            self._record_decision(
                state, "Decision Logging Agent", TalentDecisionType.APPROVE,
                1.0, f"Decision logged: {state['decision_log_id']}",
                [], ["Decision recorded for audit and pattern learning"],
                {"decision_log_id": state["decision_log_id"]}, False, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Decision Logging Agent: {e}")
            state["status"] = TalentDecisionStatus.COMPLETED.value

        return state

    def quick_decision_check_agent(self, state: TalentDecisionState) -> TalentDecisionState:
        """Agent 9: Fast single-pass review for short manager notes."""
        logger.info("\nAGENT 9: Quick Decision Check Agent")
        start_time = datetime.now()

        decision_text = state.get("content_text") or state.get("manager_reasoning", "")

        try:
            prompt = f"""
You are the Quick Decision Check Agent for Clarity.

Analyze this short manager decision note:

{decision_text}

Return JSON only:
{{
  "decision_type": "hiring/promotion/upskill/team_dynamics/unknown",
  "bias_risk_score": 0.0,
  "bias_categories": [],
  "quick_recommendation": "log/run_full_workflow/request_reflection",
  "reasoning": "..."
}}
"""
            response = invoke_llm(self.fast_llm, prompt)
            result = self._parse_json_from_response(response)

            bias_score = float(result.get("bias_risk_score", 0.0))
            state["bias_risk_score"] = bias_score
            state["toxicity_score"] = bias_score
            state["bias_categories"] = result.get("bias_categories", [])
            state["decision_type"] = result.get("decision_type", "quick_manager_note")
            state["action_reason"] = result.get("reasoning", "")

            quick_rec = result.get("quick_recommendation", "log")
            if quick_rec == "request_reflection" or bias_score >= 0.5:
                state["reflection_required"] = True
                state["hitl_required"] = True
                state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            elif quick_rec == "run_full_workflow":
                state["force_full_pipeline"] = True
                state["status"] = TalentDecisionStatus.SUBMITTED.value
            else:
                state["status"] = TalentDecisionStatus.COMPLETED.value

            self._record_decision(
                state, "Quick Decision Check Agent",
                TalentDecisionType.FLAG if bias_score >= 0.4 else TalentDecisionType.APPROVE,
                1.0 - bias_score, result.get("reasoning", ""),
                result.get("bias_categories", []),
                [f"Quick recommendation: {quick_rec}"], result, bias_score >= 0.5, start_time,
            )
        except Exception as e:
            logger.error(f"Error in Quick Decision Check Agent: {e}")
            state["status"] = TalentDecisionStatus.PENDING_MANAGER_REFLECTION.value
            state["reflection_required"] = True

        return state

    def _calculate_reflection_priority(self, state: TalentDecisionState) -> str:
        score = 0
        weights = REFLECTION_CONFIG["priority_weights"]
        if state.get("bias_risk_score", 0) >= 0.8:
            score += 80
        elif state.get("bias_risk_score", 0) >= 0.65:
            score += 60
        if state.get("violation_severity") in ["high", "critical"]:
            score += 70
        if state.get("decision_synthesis_confidence", 1) < 0.7:
            score += 40
        if state.get("manager_override_reason"):
            score += 50

        if score >= weights["critical"]:
            return "critical"
        if score >= weights["high"]:
            return "high"
        if score >= weights["medium"]:
            return "medium"
        return "low"

    def _prepare_reflection_summary(self, state: TalentDecisionState) -> str:
        lines = [
            "=== Clarity — Manager Reflection Required ===",
            f"Business Goal: {state.get('business_goal', 'N/A')}",
            f"Recommended Action: {state.get('react_act_decision', state.get('recommended_action', 'N/A'))}",
            f"Bias Risk Score: {state.get('bias_risk_score', 0):.2%}",
            f"Bias Categories: {', '.join(state.get('bias_categories', [])) or 'None'}",
            f"Fairness Violations: {', '.join(state.get('policy_violations', [])) or 'None'}",
            f"Synthesis Confidence: {state.get('decision_synthesis_confidence', 0):.2%}",
            "",
            "Reflection Questions:",
        ]
        for i, q in enumerate(state.get("reflection_questions", REFLECTION_CONFIG["reflection_questions"]), 1):
            lines.append(f"  {i}. {q}")
        lines.extend([
            "",
            "Options: accept_recommendation | revise_decision | override_with_reason | escalate_to_hr",
        ])
        return "\n".join(lines)


# Backward compatibility alias
# Backward compatibility aliases
BiasLensTalentAgents = ClarityTalentAgents
ContentModerationAgents = ClarityTalentAgents
