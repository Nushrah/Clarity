import { useEffect, useState } from 'react';
import {
  Alert, Box, Grid, LinearProgress, Typography,
} from '@mui/material';
import {
  People, Score, ThumbUp, ThumbDown, SwapHoriz, Chat, TrendingDown, TrendingUp, Warning,
} from '@mui/icons-material';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { hiringAPI } from '../../services/api';
import { hiringMetricInsights, chartRecommendations, pct } from './dashboardMetrics';
import { PanelHeader, MetricCard, ChartCard, RateInsightCard, RecommendationBox } from './DashboardUI';

const SEVERITY_COLOR = { high: 'error', medium: 'warning', info: 'info' };
const PIE_COLORS = ['#ed6c02', '#2e7d32', '#d32f2f', '#0288d1'];
const CHART = { primary: '#1565c0', purple: '#6a1b9a', green: '#2e7d32', orange: '#ed6c02' };

const WARNING_META = {
  high_override: { title: 'Elevated override rate', action: 'Review recent overrides and confirm each has specific, job-related evidence.' },
  high_override_manager: { title: 'Override rate above baseline', action: 'Schedule a brief calibration session on rubric-aligned Hire/Reject decisions.' },
  vague_reason: { title: 'Vague rejection language', action: 'Replace subjective phrases with concrete skill or experience gaps from the resume.' },
  similar_score_different_outcome: { title: 'Similar scores, different outcomes', action: 'Compare candidates in the same score band — decisions should follow consistent rules.' },
  high_score_rejection: { title: 'High-score candidates rejected', action: 'Open Recent Decisions and verify each Reject cites a specific missing requirement.' },
  low_score_advancement: { title: 'Low-score candidates hired', action: 'Ensure every low-score Hire has written justification tied to transferable skills.' },
  funnel_bottleneck: { title: 'Funnel drop-off detected', action: 'Inspect the stage with the largest drop — criteria may be applied inconsistently.' },
  small_sample: { title: 'Limited data', action: 'Log more Hire/Reject decisions before drawing strong conclusions.' },
};

const FUNNEL_STAGES = [
  ['applied', 'Applied'],
  ['resume_screen', 'Screened'],
  ['shortlisted', 'Shortlisted'],
  ['interview', 'Interviewed'],
  ['finalist', 'Finalist'],
  ['offer', 'Offer'],
  ['hired', 'Hired'],
  ['rejected', 'Rejected'],
];

export default function BiasMetricsPanel() {
  const [metrics, setMetrics] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const [m, w] = await Promise.all([
        hiringAPI.getMetrics().catch(() => null),
        hiringAPI.getWarnings().catch(() => ({ warnings: [] })),
      ]);
      if (!active) return;
      setMetrics(m);
      setWarnings(w?.warnings || []);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ my: 2, borderRadius: 2 }} />;

  const mvp = metrics?.mvp;
  if (!mvp || (mvp.total_decisions ?? 0) === 0) {
    return (
      <Alert severity="info" sx={{ borderRadius: 2 }}>
        No hiring decisions logged yet. In Resume Screening, choose <strong>Hire</strong> or <strong>Reject</strong> for each
        candidate — or run the demo seed — to populate these indicators.
      </Alert>
    );
  }

  const insights = hiringMetricInsights(mvp, metrics);
  const tips = chartRecommendations(metrics);

  const funnelCounts = metrics.funnel?.counts_by_stage || {};
  const funnelData = FUNNEL_STAGES
    .map(([key, label]) => ({ name: label, value: funnelCounts[key] || 0 }))
    .filter((d) => d.value > 0);

  const bandData = Object.entries(metrics.score_bands || {}).map(([name, value]) => ({ name, value }));
  const avgOutcomeData = Object.entries(metrics.score_decision_consistency?.average_score_by_outcome || {})
    .map(([name, value]) => ({ name: name === 'hire' ? 'Hire' : name === 'reject' ? 'Reject' : name, value }));
  const timeseries = metrics.timeseries || [];
  const reasonData = Object.entries(metrics.override?.override_reason_categories || {}).map(([name, value]) => ({ name, value }));
  const vl = metrics.vague_language || {};
  const vagueData = [
    { name: 'Vague rejections', value: Math.round((vl.vague_rejection_reason_rate || 0) * 100) },
    { name: 'Vague overrides', value: Math.round((vl.vague_override_reason_rate || 0) * 100) },
    { name: 'Personality terms', value: Math.round((vl.personality_language_rate || 0) * 100) },
    { name: 'Actionable reasons', value: Math.round((vl.actionable_reason_rate || 0) * 100) },
  ];
  const funnelRates = {
    'Resume screen pass': metrics.funnel?.resume_screen_pass_rate,
    Shortlist: metrics.funnel?.shortlist_rate,
    Interview: metrics.funnel?.interview_rate,
    Offer: metrics.funnel?.offer_rate,
    Hired: metrics.funnel?.hire_rate,
  };
  const stalled = metrics.timing?.candidates_stalled_by_stage || {};

  return (
    <Box>
      <PanelHeader
        icon={<Warning color="warning" />}
        title="Hiring fairness & consistency"
        subtitle={`${mvp.total_decisions} decisions across ${mvp.total_candidates} candidates. Each card explains what the number means and what to do next. Indicators support review — they are not judgments about individuals.`}
      />

      {warnings.length > 0 && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {warnings.map((w, i) => {
            const meta = WARNING_META[w.flag] || { title: w.flag, action: w.message };
            return (
              <Grid item xs={12} md={6} key={i}>
                <Alert severity={SEVERITY_COLOR[w.severity] || 'warning'} icon={<Warning />} sx={{ borderRadius: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600}>{meta.title}</Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>{w.message}</Typography>
                  <RecommendationBox text={meta.action} compact />
                </Alert>
              </Grid>
            );
          })}
        </Grid>
      )}

      <Typography variant="overline" color="text.secondary" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
        Key metrics
      </Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <MetricCard icon={<People fontSize="small" color="primary" />} insight={insights.total_candidates} />
        <MetricCard icon={<Score fontSize="small" color="primary" />} insight={insights.average_score} />
        <MetricCard icon={<ThumbUp fontSize="small" color="success" />} insight={insights.hire_rate} />
        <MetricCard icon={<ThumbDown fontSize="small" color="error" />} insight={insights.rejection_rate} />
        <MetricCard icon={<SwapHoriz fontSize="small" color="warning" />} insight={insights.override_rate} />
        <MetricCard icon={<Chat fontSize="small" color="warning" />} insight={insights.vague_reason_rate} />
        <MetricCard icon={<TrendingDown fontSize="small" color="error" />} insight={insights.high_score_rejection} />
        <MetricCard icon={<TrendingUp fontSize="small" color="error" />} insight={insights.low_score_advancement} />
      </Grid>

      <Typography variant="overline" color="text.secondary" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
        Visual breakdowns
      </Typography>
      <Grid container spacing={2}>
        <ChartCard
          title="Hiring funnel"
          description="How many candidates reached each stage. Large gaps between bars may signal inconsistent screening."
          recommendation={tips.funnel}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnelData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={56} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" fill={CHART.primary} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Score distribution"
          description="How candidate rubric scores are spread. Helps spot whether the pool skews too weak or too strong."
          recommendation={tips.scoreBands}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bandData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" fill={CHART.purple} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Average score by outcome"
          description="Typical score for candidates you Hired vs. Rejected. Hired should generally score higher."
          recommendation={tips.avgOutcome}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={avgOutcomeData} layout="vertical" margin={{ left: 8 }}>
              <XAxis type="number" domain={[0, 100]} />
              <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill={CHART.green} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Decisions over time"
          description="Daily volume of decisions, overrides, and rejections — useful for spotting sudden pattern shifts."
          recommendation={tips.timeseries}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeseries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="decisions" name="Decisions" stroke={CHART.primary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="overrides" name="Overrides" stroke={CHART.orange} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="rejects" name="Rejects" stroke="#d32f2f" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Override reason quality"
          description="When you override the AI, how specific are your written reasons?"
          recommendation={tips.overrideReasons}
        >
          {reasonData.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ pt: 4, textAlign: 'center' }}>No overrides yet</Typography>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={reasonData} dataKey="value" nameKey="name" outerRadius={88} innerRadius={44} paddingAngle={2}>
                  {reasonData.map((entry, i) => <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Reason language quality"
          description="Percentage of rejection/override reasons that are vague vs. actionable and evidence-based."
          recommendation={tips.reasonLanguage}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={vagueData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={48} />
              <YAxis unit="%" domain={[0, 100]} />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="value" fill={CHART.primary} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <RateInsightCard
          title="Funnel pass rates"
          description="Percent of candidates who advance past each stage."
          entries={funnelRates}
          recommendation="If pass rates vary wildly between similar roles, standardize rubric weights before the next cycle."
        />
        <RateInsightCard
          title="Override rate by stage"
          description="Where managers most often disagree with the AI recommendation."
          entries={metrics.override?.override_rate_by_stage}
          recommendation="Stages with high override rates benefit from a quick rubric refresher with the hiring panel."
        />
        <RateInsightCard
          title="Rejection rate by stage"
          description="Where candidates are most often Rejected in the pipeline."
          entries={metrics.funnel?.rejection_rate_by_stage}
          recommendation={
            Object.keys(stalled).length > 0
              ? `Stalled candidates: ${Object.entries(stalled).map(([k, v]) => `${k} (${v})`).join(', ')}. Follow up or close out inactive applications.`
              : 'Rejections concentrated at one stage may mean criteria there need clearer documentation.'
          }
        />
        <RateInsightCard
          title="Override rate by manager"
          description="Per-reviewer override frequency — for calibration, not blame."
          entries={metrics.override?.override_rate_by_manager}
          recommendation="Pair reviewers with high override rates with a structured calibration on two recent scorecards."
        />
        <RateInsightCard
          title="Override rate by job"
          description="Which requisitions see the most rubric overrides."
          entries={metrics.override?.override_rate_by_job}
          recommendation="Jobs with high overrides may need rubric tuning or clearer must-have vs. nice-to-have criteria."
        />
      </Grid>
    </Box>
  );
}
