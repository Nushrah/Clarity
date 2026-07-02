import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Container, Grid, LinearProgress, Typography, alpha,
} from '@mui/material';
import {
  Groups, TrendingUp, Warning, Psychology, School, Assignment,
  Refresh, Upload, RateReview, Description, Insights,
} from '@mui/icons-material';
import { talentAPI } from '../../services/api';
import BiasMetricsPanel from './BiasMetricsPanel';
import TalentAnalyticsPanel from './TalentAnalyticsPanel';
import TeamCapabilityPanel from './TeamCapabilityPanel';
import ReflectionQueuePanel from './ReflectionQueuePanel';
import RecentDecisionsPanel from './RecentDecisionsPanel';
import DemographicFairnessPanel from './DemographicFairnessPanel';
import { SectionPaper, RecommendationBox } from './DashboardUI';

function KpiCard({ icon, label, value, sub, tip }) {
  return (
    <Grid item xs={6} sm={4} md={2}>
      <SectionPaper sx={{ p: 2, height: '100%', bgcolor: (t) => alpha(t.palette.primary.main, 0.02) }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {icon}
          <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase">
            {label}
          </Typography>
        </Box>
        <Typography variant="h4" fontWeight={700} lineHeight={1.2}>{value}</Typography>
        {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
        {tip && (
          <Typography variant="caption" color="info.main" display="block" sx={{ mt: 1, lineHeight: 1.35 }}>
            {tip}
          </Typography>
        )}
      </SectionPaper>
    </Grid>
  );
}

export default function ManagerDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [team, setTeam] = useState(null);
  const [latest, setLatest] = useState(null);
  const [reflections, setReflections] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [analytics, teamData, latestRec, reflectionQueue] = await Promise.all([
        talentAPI.getAnalyticsSummary().catch(() => ({})),
        talentAPI.getTeamMembers().catch(() => ({ members: [] })),
        talentAPI.getLatestRecommendation().catch(() => null),
        talentAPI.getReflectionQueue().catch(() => ({ items: [] })),
      ]);
      setSummary(analytics);
      setTeam(teamData);
      setLatest(latestRec);
      setReflections(reflectionQueue);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const refreshAll = () => { fetchData(); setRefreshKey((k) => k + 1); };

  if (loading) return <LinearProgress sx={{ borderRadius: 0 }} />;

  const avgBias = summary?.avg_bias_risk_score ?? latest?.bias_risk_score ?? 0;
  const pendingReflect = reflections?.pending_reflections ?? 0;

  return (
    <Box sx={{ bgcolor: (t) => alpha(t.palette.grey[100], 0.5), minHeight: '100vh', pb: 4 }}>
      <Box
        sx={{
          background: (t) => `linear-gradient(135deg, ${t.palette.primary.main} 0%, ${t.palette.primary.dark} 55%, #1a237e 100%)`,
          color: 'primary.contrastText',
          py: { xs: 3, md: 4 },
          px: 2,
          mb: 3,
        }}
      >
        <Container maxWidth="xl">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
            <Box>
              <Typography variant="h4" fontWeight={700} gutterBottom>Clarity Manager Home</Typography>
              <Typography sx={{ opacity: 0.9, maxWidth: 560 }}>
                One place to review hiring fairness, team gaps, and workforce decisions — with clear recommendations for every metric.
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="inherit"
              startIcon={<Refresh />}
              onClick={refreshAll}
              sx={{ color: 'primary.dark', bgcolor: 'rgba(255,255,255,0.95)', '&:hover': { bgcolor: '#fff' } }}
            >
              Refresh data
            </Button>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="xl">
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <KpiCard
            icon={<Groups fontSize="small" />}
            label="Team"
            value={team?.count ?? 0}
            sub={team?.team?.team_name || '—'}
            tip="Run Gap Analysis to map skills vs. business goals."
          />
          <KpiCard
            icon={<Assignment fontSize="small" />}
            label="Decisions"
            value={summary?.total_decisions ?? 0}
            tip="More logged decisions improve pattern detection."
          />
          <KpiCard
            icon={<Warning fontSize="small" />}
            label="Bias risk"
            value={`${(avgBias * 100).toFixed(0)}%`}
            tip={avgBias > 0.4 ? 'Complete reflections to reduce risk.' : 'Keep using evidence-based criteria.'}
          />
          <KpiCard
            icon={<Description fontSize="small" />}
            label="Resumes"
            value={summary?.resumes_uploaded ?? 0}
            tip="Upload in Resume Screening; choose Hire or Reject per candidate."
          />
          <KpiCard
            icon={<Psychology fontSize="small" />}
            label="Reflections"
            value={pendingReflect}
            tip={pendingReflect > 0 ? 'High-risk decisions need your review.' : 'No pending reflections.'}
          />
          <KpiCard
            icon={<TrendingUp fontSize="small" />}
            label="Latest AI action"
            value={latest?.recommended_action || '—'}
            tip="From your most recent workforce analysis."
          />
        </Grid>

        <SectionPaper sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>Quick actions</Typography>
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            <Button variant="contained" onClick={() => navigate('/gap-analysis')}>Gap Analysis</Button>
            <Button variant="outlined" startIcon={<Upload />} onClick={() => navigate('/resume-screening')}>Resume Screening</Button>
            <Button variant="outlined" startIcon={<Assignment />} onClick={() => navigate('/decision-logger')}>Decision Logger</Button>
            <Button variant="outlined" startIcon={<RateReview />} onClick={() => navigate('/recommendations')}>Recommendations</Button>
            <Button variant="outlined" startIcon={<School />} onClick={() => navigate('/adaptive-training')}>Adaptive Training</Button>
            <Button variant="outlined" startIcon={<Insights />} onClick={() => navigate('/bias-dashboard')}>Full bias dashboard</Button>
          </Box>
        </SectionPaper>

        {latest?.critical_gaps?.length > 0 && (
          <Alert severity="warning" icon={<Warning />} sx={{ mb: 3, borderRadius: 2 }}>
            <Typography variant="subtitle2" fontWeight={600}>Critical capability gaps</Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              These skills are missing from your team and may require hiring or upskilling.
            </Typography>
            {latest.critical_gaps.map((g, i) => (
              <Chip key={i} label={typeof g === 'string' ? g : g.capability || JSON.stringify(g)} sx={{ mr: 0.5, mb: 0.5 }} size="small" />
            ))}
            <RecommendationBox text="Prioritize the top 1–2 gaps before opening new reqs — run Resume Screening against updated capabilities." compact />
          </Alert>
        )}

        <SectionPaper sx={{ mb: 3 }} key={`talent-${refreshKey}`}><TalentAnalyticsPanel /></SectionPaper>
        <SectionPaper sx={{ mb: 3 }} key={`team-${refreshKey}`}><TeamCapabilityPanel /></SectionPaper>
        <SectionPaper sx={{ mb: 3 }} key={`bias-${refreshKey}`}><BiasMetricsPanel /></SectionPaper>
        <SectionPaper sx={{ mb: 3 }} key={`decisions-${refreshKey}`}><RecentDecisionsPanel /></SectionPaper>
        <SectionPaper sx={{ mb: 3 }} key={`fairness-${refreshKey}`}><DemographicFairnessPanel /></SectionPaper>
        <SectionPaper key={`reflect-${refreshKey}`}><ReflectionQueuePanel /></SectionPaper>
      </Container>
    </Box>
  );
}
