import { useEffect, useState } from 'react';
import { Box, Grid, LinearProgress, Typography } from '@mui/material';
import { Groups } from '@mui/icons-material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { talentAPI } from '../../services/api';
import { chartRecommendations } from './dashboardMetrics';
import { PanelHeader, ChartCard, RecommendationBox } from './DashboardUI';

function utilizationColor(u) {
  if (u >= 0.9) return 'error';
  if (u >= 0.75) return 'warning';
  return 'success';
}

export default function TeamCapabilityPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const d = await talentAPI.getTeamMembers().catch(() => null);
      if (!active) return;
      setData(d);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ borderRadius: 2 }} />;

  const members = data?.members || [];
  if (members.length === 0) return null;

  const skillCounts = {};
  members.forEach((m) => (m.skills || []).forEach((s) => {
    skillCounts[s] = (skillCounts[s] || 0) + 1;
  }));
  const skillData = Object.entries(skillCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  const utils = members.map((m) => m.workload?.utilization).filter((u) => typeof u === 'number');
  const avgUtil = utils.length ? utils.reduce((a, b) => a + b, 0) / utils.length : 0;
  const tips = chartRecommendations({});

  return (
    <Box>
      <PanelHeader
        icon={<Groups color="primary" />}
        title="Team capability & coverage"
        subtitle={`${data?.team?.team_name || 'Your team'} · ${members.length} members · average workload ${Math.round(avgUtil * 100)}%`}
      />

      <Grid container spacing={2}>
        <ChartCard
          title="Skill coverage"
          description="How many team members list each skill — higher bars mean stronger bench depth."
          recommendation="Skills with low coverage that appear in critical gaps are prime candidates for hire or upskill."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={skillData} layout="vertical" margin={{ left: 16 }}>
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#1565c0" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Grid item xs={12} md={6}>
          <Box
            sx={{
              p: 2.5, height: '100%', borderRadius: 2, border: '1px solid', borderColor: 'divider',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}
          >
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>Individual workload</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Utilization above 85% for multiple people suggests capacity constraints — factor into hire vs. upskill decisions.
            </Typography>
            {members.map((m) => {
              const u = m.workload?.utilization ?? 0;
              return (
                <Box key={m.employee_id} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography variant="body2" fontWeight={500}>{m.name}</Typography>
                    <Typography variant="body2" color={`${utilizationColor(u)}.main`} fontWeight={600}>
                      {Math.round(u * 100)}%
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>{m.role}</Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(u * 100, 100)}
                    color={utilizationColor(u)}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                </Box>
              );
            })}
            <RecommendationBox text={tips.teamUtil} compact />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
