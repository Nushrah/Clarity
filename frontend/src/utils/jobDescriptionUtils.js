export function capabilityLabel(cap) {
  if (!cap) return '';
  if (typeof cap === 'string') return cap;
  return cap.capability || cap.skill || cap.name || JSON.stringify(cap);
}

/**
 * Single source of truth for the required-capabilities list.
 * Both Gap Analysis and Resume Screening render this exact list.
 */
export function getRequiredCapabilities(workflowResult) {
  if (!workflowResult) return [];
  const source =
    (workflowResult.gap_analysis && workflowResult.gap_analysis.length
      ? workflowResult.gap_analysis
      : workflowResult.required_capabilities) || [];
  return source.map(capabilityLabel).filter(Boolean);
}

/** Job description for resume screening: bulleted required capabilities. */
export function buildScreeningJobDescription(workflowResult, businessGoal = '') {
  if (!workflowResult) return { title: '', description: '', bullets: [] };

  const caps =
    workflowResult.required_capabilities?.length
      ? workflowResult.required_capabilities
      : [
          ...(workflowResult.critical_gaps || []),
          ...(workflowResult.moderate_gaps || []),
        ];

  const bullets = caps.map(capabilityLabel).filter(Boolean);
  const goal = businessGoal || workflowResult.business_goal || 'Team business goal';
  const title =
    workflowResult.hiring_role?.role_title ||
    'Required capabilities — resume screening rubric';

  if (!bullets.length) {
    const fallback =
      workflowResult.hiring_role?.job_description ||
      workflowResult.generated_job_description ||
      '';
    return { title, description: fallback, bullets: [] };
  }

  const description = `Required capabilities for: ${goal}\n\n${bullets.map((b) => `• ${b}`).join('\n')}`;
  return { title, description, bullets };
}
