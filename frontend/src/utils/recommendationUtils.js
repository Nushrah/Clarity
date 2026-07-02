const ACTION_LABELS = {
  hire: 'Hire externally',
  promote: 'Promote',
  upskill: 'Upskill',
};

/** Coerce gap/critical-gap items to objects the manager-choice API accepts. */
export function normalizeGapAnalysisForApi(gaps) {
  const list = Array.isArray(gaps) ? gaps : [];
  return list.map((g) => {
    if (typeof g === 'string') return { capability: g };
    if (g && typeof g === 'object') return g;
    return { capability: String(g) };
  });
}

/** Coerce bias category items to plain strings for API validation. */
export function normalizeBiasCategoriesForApi(categories) {
  const list = Array.isArray(categories) ? categories : [];
  return list.map((c) => {
    if (typeof c === 'string') return c;
    if (c && typeof c === 'object') {
      return c.pattern || c.category || c.name || JSON.stringify(c);
    }
    return String(c);
  });
}

/** Turn axios/FastAPI errors into a safe string for React alerts. */
export function formatApiError(err, fallback = 'Request failed.') {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message || fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(' ');
  }
  if (typeof detail === 'object') return detail.msg || JSON.stringify(detail);
  return fallback;
}

export function normalizeAction(action) {
  if (!action) return 'upskill';
  const a = String(action).toLowerCase().replace('recommend_', '');
  if (a.includes('hire')) return 'hire';
  if (a.includes('promote')) return 'promote';
  if (a.includes('upskill')) return 'upskill';
  return 'upskill';
}

export function memberName(members, employeeId) {
  if (!employeeId) return null;
  return (members || []).find((m) => m.employee_id === employeeId)?.name || null;
}

export function formatDecisionLabel(key, result, members = []) {
  if (key === 'hire') return 'Hire externally (gap-based role)';
  if (key === 'promote') {
    const name =
      result?.promotion_recommendation?.recommended_employee_name ||
      result?.final_recommendation?.target_employee_name ||
      memberName(members, result?.promotion_recommendation?.recommended_employee_id) ||
      memberName(members, result?.final_recommendation?.target_employee_id);
    return name ? `Promote ${name}` : 'Promote (team member)';
  }
  if (key === 'upskill') {
    const name =
      result?.upskill_recommendation?.recommended_employee_name ||
      result?.final_recommendation?.target_employee_name ||
      memberName(members, result?.upskill_recommendation?.recommended_employee_id) ||
      memberName(members, result?.final_recommendation?.target_employee_id);
    return name ? `Upskill ${name}` : 'Upskill (team member)';
  }
  return ACTION_LABELS[key] || key;
}

export function buildActionConvictions(result, members = []) {
  const primary = normalizeAction(
    result?.final_recommendation?.type ||
    result?.final_recommendation?.action ||
    result?.recommended_action ||
    result?.react_act_decision
  );
  const synthConfidence = result?.decision_synthesis_confidence ?? 0.5;
  const policyConfidence = result?.fairness_confidence ?? synthConfidence * 0.9;

  const promoteName =
    result?.promotion_recommendation?.recommended_employee_name ||
    memberName(members, result?.promotion_recommendation?.recommended_employee_id);
  const upskillName =
    result?.upskill_recommendation?.recommended_employee_name ||
    memberName(members, result?.upskill_recommendation?.recommended_employee_id);

  const actions = [
    {
      key: 'hire',
      label: formatDecisionLabel('hire', result, members),
      conviction: primary === 'hire' ? synthConfidence : result?.hiring_role?.job_description ? policyConfidence * 0.55 : 0.12,
      rationale: result?.hiring_role?.role_title
        ? `${result.hiring_role.role_title}: ${(result.hiring_role.job_description || '').slice(0, 160)}`
        : 'External hire to cover capability gaps identified in team analysis.',
      evidence: result?.hiring_role?.required_skills || result?.hiring_role?.gap_capabilities_addressed || [],
      target: result?.hiring_role?.role_title || 'New hire',
      employeeId: null,
    },
    {
      key: 'promote',
      label: formatDecisionLabel('promote', result, members),
      conviction: primary === 'promote' ? synthConfidence : promoteName ? policyConfidence * 0.6 : 0.1,
      rationale: result?.promotion_recommendation?.rationale ||
        (promoteName ? `Promote ${promoteName} based on readiness evidence.` : 'Internal promotion when readiness evidence supports expanded scope.'),
      evidence: result?.promotion_recommendation?.evidence || [],
      target: promoteName,
      employeeId: result?.promotion_recommendation?.recommended_employee_id,
    },
    {
      key: 'upskill',
      label: formatDecisionLabel('upskill', result, members),
      conviction: primary === 'upskill' ? synthConfidence : upskillName ? policyConfidence * 0.58 : 0.15,
      rationale: result?.upskill_recommendation?.skill_gap
        ? `Upskill ${upskillName || 'team member'}: ${result.upskill_recommendation.skill_gap}`
        : upskillName
          ? `Develop ${upskillName}'s skills to close internal gaps.`
          : 'Develop existing team capacity before external hiring.',
      evidence: result?.upskill_recommendation?.learning_path || [],
      target: upskillName,
      employeeId: result?.upskill_recommendation?.recommended_employee_id,
    },
  ];

  return actions.sort((a, b) => b.conviction - a.conviction);
}

export function convictionColor(score) {
  if (score >= 0.7) return 'success';
  if (score >= 0.45) return 'warning';
  return 'primary';
}

export function convictionChipColor(score) {
  if (score >= 0.7) return 'success';
  if (score >= 0.45) return 'warning';
  return 'default';
}

export function biasRiskLabel(score) {
  if (score >= 0.8) return 'severe';
  if (score >= 0.65) return 'high';
  if (score >= 0.4) return 'medium';
  if (score > 0) return 'low';
  return 'none';
}

export function primaryDecisionSummary(result, members = []) {
  const path = result?.primary_path || normalizeAction(
    result?.final_recommendation?.type || result?.recommended_action
  );
  if (path === 'hire_external' || path === 'hire') return 'Hire externally';
  const name =
    result?.promotion_recommendation?.recommended_employee_name ||
    result?.final_recommendation?.target_employee_name ||
    memberName(members, result?.promotion_recommendation?.recommended_employee_id);
  return name ? `Promote internally (${name} + upskill)` : 'Promote internally (+ upskill)';
}

/** Two-path AI comparison for Recommendations (hire_external vs promote_internal). */
export function buildTwoPathComparison(result, members = []) {
  const synth = result?.decision_synthesis_confidence ?? 0.5;
  const primary = result?.primary_path
    || (normalizeAction(result?.recommended_action) === 'hire' ? 'hire_external' : 'promote_internal');
  const pc = result?.path_comparison || {};

  const promoteName =
    result?.promotion_recommendation?.recommended_employee_name ||
    memberName(members, result?.promotion_recommendation?.recommended_employee_id);
  const upskill = result?.upskill_recommendation || {};
  const upskillPlan = upskill.learning_path?.join('; ')
    || upskill.skill_gap
    || upskill.practice_project
    || 'Structured upskilling aligned to critical gaps.';

  const hireConv = pc?.hire_external?.conviction ?? (primary === 'hire_external' ? synth : synth * 0.45);
  const promoteConv = pc?.promote_internal?.conviction ?? (primary === 'promote_internal' ? synth : synth * 0.5);

  return [
    {
      key: 'hire_external',
      label: 'Hire externally',
      conviction: hireConv,
      rationale: pc?.hire_external?.summary || result?.hiring_role?.role_title
        ? `External hire: ${result.hiring_role?.role_title || 'new role'} to cover critical gaps.`
        : 'Bring in external talent when internal capacity cannot close gaps in time.',
      evidence: result?.hiring_role?.required_skills || result?.critical_gaps || [],
      isPrimary: primary === 'hire_external',
      upskillPlan: null,
    },
    {
      key: 'promote_internal',
      label: promoteName ? `Promote internally (${promoteName})` : 'Promote internally',
      conviction: promoteConv,
      rationale: pc?.promote_internal?.summary || upskill.skill_gap
        ? `Develop ${promoteName || 'a team member'}: ${upskill.skill_gap || 'close gaps via promotion + upskill'}.`
        : 'Grow existing team capacity with promotion and targeted upskilling.',
      evidence: result?.promotion_recommendation?.evidence || upskill.learning_path || [],
      isPrimary: primary === 'promote_internal',
      upskillPlan: pc?.promote_internal?.upskill_plan || upskillPlan,
      employeeId: result?.promotion_recommendation?.recommended_employee_id
        || result?.upskill_recommendation?.recommended_employee_id,
    },
  ].sort((a, b) => b.conviction - a.conviction);
}
