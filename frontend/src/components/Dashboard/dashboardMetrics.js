/** Plain-language metric copy + threshold-based recommendations for dashboard panels. */

export function pct(v) {
  return `${Math.round((v || 0) * 100)}%`;
}

export function statusFromRate(rate, { good = 0.1, warn = 0.25 } = {}) {
  if (rate == null || Number.isNaN(rate)) return 'neutral';
  if (rate <= good) return 'good';
  if (rate <= warn) return 'watch';
  return 'action';
}

export function statusFromScore(score, { good = 70, warn = 50 } = {}) {
  if (score == null) return 'neutral';
  if (score >= good) return 'good';
  if (score >= warn) return 'watch';
  return 'action';
}

export const STATUS = {
  good: { label: 'On track', color: 'success', bg: 'success.50' },
  watch: { label: 'Review', color: 'warning', bg: 'warning.50' },
  action: { label: 'Take action', color: 'error', bg: 'error.50' },
  neutral: { label: 'Info', color: 'info', bg: 'grey.50' },
};

/** Hiring bias metrics (BiasMetricsPanel) */
export function hiringMetricInsights(mvp, metrics) {
  const lowAdvance = metrics?.score_decision_consistency?.low_score_advancement_rate ?? 0;
  return {
    total_candidates: {
      label: 'Candidates reviewed',
      description: 'People who received a rubric scorecard in this hiring cycle.',
      value: mvp.total_candidates,
      status: mvp.total_candidates >= 8 ? 'good' : 'watch',
      recommendation: mvp.total_candidates >= 8
        ? 'Good sample size — funnel and consistency metrics are more reliable.'
        : 'Screen more candidates to strengthen trend detection and fairness checks.',
    },
    average_score: {
      label: 'Average rubric score',
      description: 'Mean score across all scorecards (0–100). Higher usually means stronger evidence vs. requirements.',
      value: mvp.average_score,
      status: statusFromScore(mvp.average_score),
      recommendation: mvp.average_score >= 65
        ? 'Pool quality looks solid — focus on consistency between score and final Hire/Reject calls.'
        : 'Scores skew lower — confirm rubric weights match role requirements and evidence is captured fairly.',
    },
    hire_rate: {
      label: 'Hire rate',
      description: 'Share of logged decisions where the manager selected Hire (vs. Reject).',
      value: pct(mvp.interview_rate),
      bar: mvp.interview_rate,
      status: 'neutral',
      recommendation: mvp.interview_rate > 0.5
        ? 'More than half of decisions are hires — spot-check that rejections still cite specific job gaps.'
        : 'Most decisions are rejections — ensure high-scoring candidates are not being rejected without evidence.',
    },
    rejection_rate: {
      label: 'Rejection rate',
      description: 'Share of decisions ending in Reject at the screening stage.',
      value: pct(mvp.rejection_rate),
      bar: mvp.rejection_rate,
      status: mvp.rejection_rate > 0.7 ? 'watch' : 'good',
      recommendation: mvp.rejection_rate > 0.7
        ? 'High rejection volume — audit a sample of reasons for specificity and job relevance.'
        : 'Rejection rate is moderate — keep tying each Reject to observable requirement gaps.',
    },
    override_rate: {
      label: 'Override rate',
      description: 'How often your Hire/Reject choice differed from the AI rubric recommendation.',
      value: pct(mvp.override_rate),
      bar: mvp.override_rate,
      status: statusFromRate(mvp.override_rate, { good: 0.15, warn: 0.3 }),
      recommendation: mvp.override_rate > 0.3
        ? 'Overrides are frequent — schedule a rubric calibration and document evidence for each override.'
        : mvp.override_rate > 0.15
          ? 'Some overrides are expected — verify each has a specific, job-related reason on file.'
          : 'Overrides are low — decisions align well with the rubric. Keep logging reasons when you do override.',
    },
    vague_reason_rate: {
      label: 'Vague reason rate',
      description: 'Rejections or overrides whose written reason uses subjective or non-job-related language.',
      value: pct(mvp.vague_reason_rate),
      bar: mvp.vague_reason_rate,
      status: statusFromRate(mvp.vague_reason_rate, { good: 0.05, warn: 0.15 }),
      recommendation: mvp.vague_reason_rate > 0.15
        ? 'Replace phrases like “culture fit” with concrete skill or experience gaps from the resume.'
        : 'Reason quality looks acceptable — continue citing resume evidence for every Reject.',
    },
    high_score_rejection: {
      label: 'High-score rejections',
      description: 'Candidates scoring ≥70 who were still Rejected — possible inconsistency signal.',
      value: pct(mvp.high_score_rejection_rate),
      bar: mvp.high_score_rejection_rate,
      status: statusFromRate(mvp.high_score_rejection_rate, { good: 0.05, warn: 0.15 }),
      recommendation: mvp.high_score_rejection_rate > 0.15
        ? 'Review high-score rejections in Recent Decisions — each should name a specific missing requirement.'
        : 'Few high-score rejections — good sign that scores and outcomes stay aligned.',
    },
    low_score_advancement: {
      label: 'Low-score hires',
      description: 'Candidates scoring <50 who received Hire — confirm documented justification exists.',
      value: pct(lowAdvance),
      bar: lowAdvance,
      status: statusFromRate(lowAdvance, { good: 0.05, warn: 0.15 }),
      recommendation: lowAdvance > 0.15
        ? 'Low-score hires need explicit written rationale tied to transferable skills or growth potential.'
        : 'Low-score hires are rare — rubric and decisions appear well calibrated.',
    },
  };
}

/** Workforce / talent analytics */
export function talentMetricInsights(summary, gap, bias, patterns) {
  const overrideRate = patterns?.override_rate ?? 0;
  const avgBias = bias?.avg_bias_risk_score ?? 0;
  return {
    decisions: {
      label: 'Workforce decisions',
      description: 'Logged hire / promote / upskill analyses (excluding exploratory gap runs).',
      value: summary?.total_decisions ?? 0,
      status: (summary?.total_decisions ?? 0) > 0 ? 'good' : 'watch',
      recommendation: (summary?.total_decisions ?? 0) > 0
        ? 'Decision history is building — patterns become clearer with each logged choice.'
        : 'Submit a workforce decision in Gap Analysis or Decision Logger to start tracking bias risk.',
    },
    critical_gaps: {
      label: 'Critical skill gaps',
      description: 'Capabilities marked critical across recent gap analyses — hiring may be warranted.',
      value: gap?.critical_gap_count ?? 0,
      status: (gap?.critical_gap_count ?? 0) > 2 ? 'action' : (gap?.critical_gap_count ?? 0) > 0 ? 'watch' : 'good',
      recommendation: (gap?.critical_gap_count ?? 0) > 0
        ? 'Prioritize filling critical gaps via hire or targeted upskilling before lower-priority needs.'
        : 'No critical gaps flagged — team coverage looks stable for current goals.',
    },
    avg_bias: {
      label: 'Average bias risk',
      description: 'AI-assessed risk that recent workforce decisions may reflect unconscious bias (0–100%).',
      value: `${Math.round(avgBias * 100)}%`,
      bar: avgBias,
      status: statusFromRate(avgBias, { good: 0.25, warn: 0.45 }),
      recommendation: avgBias > 0.45
        ? 'Complete pending reflections and use Adaptive Training modules flagged for your profile.'
        : avgBias > 0.25
          ? 'Review bias categories below — small process tweaks often reduce risk quickly.'
          : 'Bias risk is low — maintain evidence-based criteria in promotions and hiring.',
    },
    override: {
      label: 'Workforce override rate',
      description: 'How often managers chose differently from the AI workforce recommendation.',
      value: pct(overrideRate),
      bar: overrideRate,
      status: statusFromRate(overrideRate, { good: 0.15, warn: 0.35 }),
      recommendation: overrideRate > 0.35
        ? 'Document override reasons and compare against team capability data before next cycle.'
        : 'Override rate is manageable — keep noting why when you diverge from AI guidance.',
    },
  };
}

/** Chart-level recommendations */
export function chartRecommendations(metrics) {
  const vl = metrics?.vague_language || {};
  const actionable = vl.actionable_reason_rate ?? 0;
  return {
    funnel: 'Look for sharp drop-offs between stages — large gaps may indicate inconsistent screening criteria.',
    scoreBands: 'A healthy pool often clusters in 50–84. Many scores below 50 may mean rubric weights need tuning.',
    avgOutcome: 'Hired candidates should average higher than rejected ones. Large overlap suggests inconsistent decisions.',
    timeseries: 'Sudden spikes in overrides or rejects may follow policy changes — investigate those dates.',
    overrideReasons: 'Most override reasons should be “specific” or “evidence-based”. High “vague” share needs coaching.',
    reasonLanguage: actionable < 0.5
      ? 'Increase actionable, evidence-based rejection reasons — aim for >50% citing concrete resume facts.'
      : 'Reason language quality is solid — maintain job-specific evidence in every Reject.',
    demographic: 'Compare selection rates across groups. Groups below 80% of the highest rate warrant a structured review.',
    teamUtil: 'Sustained utilization above 85% increases burnout risk — consider hire vs. upskill trade-offs.',
  };
}
