import { useEffect, useState } from 'react';
import { Box, Chip, Grid, LinearProgress, Typography } from '@mui/material';
import {
  Assignment, Warning, Psychology, SwapHoriz,
} from '@mui/icons-material';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { talentAPI } from '../../services/api';
import { talentMetricInsights } from './dashboardMetrics';
import { PanelHeader, MetricCard, ChartCard, RecommendationBox, SectionPaper } from './DashboardUI';

const PIE_COLORS = ['#1565c0', '#6a1b9a', '#2e7d32', '#ed6c02', '#0288d1', '#d32f2f'];

export default function TalentAnalyticsPanel() {
  const [gap, setGap] = useState(null);
  const [bias, setBias] = useState(null);
  const [patterns, setPatterns] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const [g, b, p, s] = await Promise.all([
        talentAPI.getGapAnalytics().catch(() => ({})),
        talentAPI.getBiasAnalytics().catch(() => ({})),
        talentAPI.getManagerPatterns().catch(() => ({})),
        talentAPI.getAnalyticsSummary().catch(() => ({})),
      ]);
      if (!active) return;
      setGap(g); setBias(b); setPatterns(p); setSummary(s);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ borderRadius: 2 }} />;

  const insights = talentMetricInsights(summary, gap, bias, patterns);
  const biasData = (bias?.most_common_bias_categories || []).map(([name, value]) => ({ name, value }));
  const actionMix = Object.entries(summary?.recommended_action_mix || {})
    .filter(([k]) => k && k !== 'null')
    .map(([name, value]) => ({ name, value }));
  const recurring = Object.entries(patterns?.recurring_patterns || {});

  return (
    <Box>
      <PanelHeader
        icon={<Psychology color="secondary" />}
        title="Workforce decision analytics"
        subtitle="Tracks gap analysis, bias risk, and AI recommendation patterns for hire / promote / upskill decisions."
      />

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <MetricCard icon={<Assignment fontSize="small" color="primary" />} insight={insights.decisions} />
        <MetricCard icon={<Warning fontSize="small" color="error" />} insight={insights.critical_gaps} />
        <MetricCard icon={<Psychology fontSize="small" color="secondary" />} insight={insights.avg_bias} />
        <MetricCard icon={<SwapHoriz fontSize="small" color="warning" />} insight={insights.override} />
      </Grid>

      <Grid container spacing={2}>
        <ChartCard
          title="Common bias categories"
          description="Which bias types appear most often in logged workforce decisions."
          recommendation={
            biasData.length > 0
              ? `Most frequent: "${biasData[0]?.name}". Review recent decisions tagged with this category in the Reflection queue.`
              : 'No bias categories recorded yet — run Gap Analysis to generate your first assessment.'
          }
        >
          {biasData.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ pt: 6, textAlign: 'center' }}>No patterns yet</Typography>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={biasData} layout="vertical" margin={{ left: 16 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#6a1b9a" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Recommended action mix"
          description="How often the AI suggested hire vs. promote vs. upskill for your team."
          recommendation="A heavy skew toward one action may mean capability gaps are being addressed the same way repeatedly — diversify if appropriate."
        >
          {actionMix.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ pt: 6, textAlign: 'center' }}>No decisions yet</Typography>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={actionMix} dataKey="value" nameKey="name" outerRadius={88} innerRadius={48} paddingAngle={3} label>
                  {actionMix.map((entry, i) => <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {recurring.length > 0 && (
          <Grid item xs={12}>
            <SectionPaper>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>Recurring manager patterns</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Behaviours detected across multiple decisions — use for self-reflection, not evaluation.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
                {recurring.map(([name, count]) => (
                  <Chip key={name} label={`${name.replace(/_/g, ' ')} (${count}×)`} color="warning" variant="outlined" />
                ))}
              </Box>
              <RecommendationBox text="Open Adaptive Training for modules matched to these patterns, or complete a pending reflection." />
            </SectionPaper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
