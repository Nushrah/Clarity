import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Container,
  Grid, LinearProgress, Typography,
} from '@mui/material';
import { Psychology, Refresh, TrendingUp, Warning } from '@mui/icons-material';
import { talentAPI, hiringAPI } from '../../services/api';

const SEVERITY_COLOR = { high: 'error', medium: 'warning', info: 'info' };

function pct(v) {
  return `${Math.round((v || 0) * 100)}%`;
}

export default function GapBiasAnalytics() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [gapStats, setGapStats] = useState(null);
  const [biasStats, setBiasStats] = useState(null);
  const [patterns, setPatterns] = useState(null);
  const [hiring, setHiring] = useState(null);
  const [warnings, setWarnings] = useState([]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      const [summaryData, gapData, biasData, patternData, hiringMetrics, hiringWarnings] = await Promise.all([
        talentAPI.getAnalyticsSummary().catch(() => ({})),
        talentAPI.getGapAnalytics().catch(() => ({})),
        talentAPI.getBiasAnalytics().catch(() => ({})),
        talentAPI.getManagerPatterns().catch(() => ({})),
        hiringAPI.getMetrics().catch(() => null),
        hiringAPI.getWarnings().catch(() => ({ warnings: [] })),
      ]);
      setSummary(summaryData);
      setGapStats(gapData);
      setBiasStats(biasData);
      setPatterns(patternData);
      setHiring(hiringMetrics);
      setWarnings(hiringWarnings?.warnings || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAnalytics(); }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>Bias & Gap Dashboard</Typography>
          <Typography color="text.secondary">Workforce decision analytics for your team</Typography>
        </Box>
        <Button startIcon={<Refresh />} onClick={fetchAnalytics}>Refresh</Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12} md={3}>
          <Card><CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <TrendingUp color="primary" /><Typography variant="subtitle2">Decisions logged</Typography>
            </Box>
            <Typography variant="h4">{summary?.total_decisions ?? patterns?.decisions_logged ?? 0}</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Warning color="warning" /><Typography variant="subtitle2">Critical gaps found</Typography>
            </Box>
            <Typography variant="h4">{gapStats?.critical_gap_count ?? 0}</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Psychology color="error" /><Typography variant="subtitle2">Avg bias risk</Typography>
            </Box>
            <Typography variant="h4">
              {((biasStats?.avg_bias_risk_score ?? summary?.avg_bias_risk_score ?? 0) * 100).toFixed(0)}%
            </Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent>
            <Typography variant="subtitle2" color="text.secondary">Manager override rate</Typography>
            <Typography variant="h4">{((patterns?.override_rate ?? 0) * 100).toFixed(0)}%</Typography>
            <LinearProgress variant="determinate" value={(patterns?.override_rate ?? 0) * 100} sx={{ mt: 1 }} />
          </CardContent></Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card><CardContent>
            <Typography variant="h6" gutterBottom>Gap analysis summary</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {gapStats?.decisions_analyzed ?? 0} team decisions analyzed
            </Typography>
            <Typography variant="body2">Moderate gaps: {gapStats?.moderate_gap_count ?? 0}</Typography>
          </CardContent></Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card><CardContent>
            <Typography variant="h6" gutterBottom>Common bias categories</Typography>
            {(biasStats?.most_common_bias_categories || []).length === 0 ? (
              <Typography variant="body2" color="text.secondary">No bias patterns recorded yet</Typography>
            ) : (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {biasStats.most_common_bias_categories.map(([cat, count]) => (
                  <Chip key={cat} label={`${cat} (${count})`} color="warning" variant="outlined" />
                ))}
              </Box>
            )}
          </CardContent></Card>
        </Grid>
      </Grid>

      {/* Bias-reduction hiring metrics */}
      <Typography variant="h5" sx={{ mt: 4, mb: 2 }}>Hiring decision consistency</Typography>

      {warnings.length > 0 && (
        <Box sx={{ mb: 2 }}>
          {warnings.map((w, i) => (
            <Alert key={i} severity={SEVERITY_COLOR[w.severity] || 'warning'} sx={{ mb: 1 }} icon={<Warning />}>
              {w.message}
            </Alert>
          ))}
        </Box>
      )}

      {!hiring || (hiring.mvp?.total_decisions ?? 0) === 0 ? (
        <Alert severity="info">
          No hiring decisions logged yet. Generate scorecards in Resume Screening and record Interview / Reject / Hold decisions to populate these metrics.
        </Alert>
      ) : (
        <Grid container spacing={3}>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Candidates scored</Typography>
              <Typography variant="h4">{hiring.mvp.total_candidates}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Average score</Typography>
              <Typography variant="h4">{hiring.mvp.average_score}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Interview rate</Typography>
              <Typography variant="h4">{pct(hiring.mvp.interview_rate)}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Rejection rate</Typography>
              <Typography variant="h4">{pct(hiring.mvp.rejection_rate)}</Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Override rate</Typography>
              <Typography variant="h4">{pct(hiring.mvp.override_rate)}</Typography>
              <LinearProgress variant="determinate" value={(hiring.mvp.override_rate || 0) * 100} color="warning" sx={{ mt: 1 }} />
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Vague reason rate</Typography>
              <Typography variant="h4">{pct(hiring.mvp.vague_reason_rate)}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">High-score rejection</Typography>
              <Typography variant="h4">{pct(hiring.mvp.high_score_rejection_rate)}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card><CardContent>
              <Typography variant="subtitle2" color="text.secondary">Similar-score, different outcome</Typography>
              <Typography variant="h4">{pct(hiring.mvp.similar_score_different_outcome_rate)}</Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card><CardContent>
              <Typography variant="h6" gutterBottom>Average score by outcome</Typography>
              {Object.entries(hiring.score_decision_consistency?.average_score_by_outcome || {}).length === 0 ? (
                <Typography variant="body2" color="text.secondary">No data yet</Typography>
              ) : (
                Object.entries(hiring.score_decision_consistency.average_score_by_outcome).map(([outcome, avg]) => (
                  <Box key={outcome} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{outcome}</Typography>
                    <Typography variant="body2"><strong>{avg}</strong></Typography>
                  </Box>
                ))
              )}
            </CardContent></Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card><CardContent>
              <Typography variant="h6" gutterBottom>Override rate by manager</Typography>
              {Object.entries(hiring.override?.override_rate_by_manager || {}).length === 0 ? (
                <Typography variant="body2" color="text.secondary">No overrides recorded</Typography>
              ) : (
                Object.entries(hiring.override.override_rate_by_manager).map(([mgr, rate]) => (
                  <Box key={mgr} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{mgr}</Typography>
                    <Typography variant="body2"><strong>{pct(rate)}</strong></Typography>
                  </Box>
                ))
              )}
            </CardContent></Card>
          </Grid>
        </Grid>
      )}
    </Container>
  );
}
