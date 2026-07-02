import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Container,
  Grid, LinearProgress, Paper, TextField, Typography,
} from '@mui/material';
import { ArrowForward } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { talentAPI } from '../../services/api';
import { getRequiredCapabilities } from '../../utils/jobDescriptionUtils';
import { useTalentWorkflowStore } from '../../store/talentWorkflowStore';
import ManagerContextBar from '../Shared/ManagerContextBar';

const TEAM_ID = 'team_alpha';
const MANAGER_ID = 'mgr_001';
const MANAGER_NAME = 'Aisha Rahman';

function TeamRoster({ members }) {
  if (!members?.length) return null;
  return (
    <Grid container spacing={1}>
      {members.map((m) => (
        <Grid item xs={12} sm={6} md={4} key={m.employee_id}>
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="subtitle2">{m.name}</Typography>
            <Typography variant="caption" color="text.secondary">{m.role} · {m.level}</Typography>
          </Paper>
        </Grid>
      ))}
    </Grid>
  );
}

export default function GapAnalysis() {
  const navigate = useNavigate();
  const {
    businessGoal, team, members, workflowResult,
    setTeamContext, setBusinessGoal, setWorkflowResult,
  } = useTalentWorkflowStore();

  const [teamLoading, setTeamLoading] = useState(!members.length);
  const [goal, setGoal] = useState(businessGoal || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const result = workflowResult;
  const requiredCapabilities = getRequiredCapabilities(result);

  useEffect(() => {
    if (members.length && team) {
      setTeamLoading(false);
      if (!goal) setGoal(businessGoal || team.business_goal || '');
      return;
    }
    (async () => {
      try {
        setTeamLoading(true);
        const data = await talentAPI.getTeamMembers(TEAM_ID);
        const loadedGoal = businessGoal || data.team?.business_goal || 'Launch AI analytics dashboard in 6 months.';
        setTeamContext({ team: data.team, members: data.members || [], businessGoal: loadedGoal });
        setGoal(loadedGoal);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load team data.');
      } finally {
        setTeamLoading(false);
      }
    })();
  }, []);

  const handleGoalChange = (value) => {
    setGoal(value);
    setBusinessGoal(value);
  };

  const runAnalysis = async () => {
    if (!members.length) {
      setError('No team members loaded. Seed team data first.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await talentAPI.runGapAnalysis({
        business_goal: goal,
        decision_type: 'gap_analysis',
        team_id: TEAM_ID,
        team_name: team?.team_name || 'Product Engineering Alpha',
        manager_id: MANAGER_ID,
        manager_name: MANAGER_NAME,
        timeline_months: 6,
        budget_level: 'medium',
        headcount_available: 1,
      });
      setWorkflowResult(data);
      setBusinessGoal(goal);
    } catch (err) {
      setError(err.response?.data?.detail || 'Gap analysis failed. Check OpenRouter configuration.');
    } finally {
      setLoading(false);
    }
  };

  if (teamLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <ManagerContextBar />
      <Typography variant="h4" gutterBottom>Gap Analysis</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Compare {team?.team_name || 'your team'} ({members.length} members) against your business goal.
        Results persist when you navigate away.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Current team</Typography>
          <TeamRoster members={members} />
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <TextField
            fullWidth multiline rows={3} label="Business Goal"
            value={goal} onChange={(e) => handleGoalChange(e.target.value)} sx={{ mb: 2 }}
          />
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button variant="contained" onClick={runAnalysis} disabled={loading || !members.length}>
              Run Gap Analysis
            </Button>
            {result && (
              <Button variant="outlined" endIcon={<ArrowForward />} onClick={() => navigate('/recommendations')}>
                View Recommendations
              </Button>
            )}
          </Box>
        </CardContent>
      </Card>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {result && (
        <Box>
          <Alert severity="success" sx={{ mb: 2 }}>
            Analysis complete for decision <strong>{result.decision_id?.slice(0, 12)}…</strong>.
            Go to <strong>Recommendations</strong> for conviction ratings and your decision.
          </Alert>

          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6">Critical Gaps</Typography>
              {(result.critical_gaps || []).length === 0 && (
                <Typography variant="body2" color="text.secondary">None identified</Typography>
              )}
              {(result.critical_gaps || []).map((g, i) => (
                <Chip key={i} label={typeof g === 'string' ? g : g.capability || JSON.stringify(g)} sx={{ m: 0.5 }} color="error" />
              ))}
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="h6">Moderate Gaps</Typography>
              {(result.moderate_gaps || []).length === 0 && (
                <Typography variant="body2" color="text.secondary">None identified</Typography>
              )}
              {(result.moderate_gaps || []).map((g, i) => (
                <Chip key={i} label={typeof g === 'string' ? g : g.capability || JSON.stringify(g)} sx={{ m: 0.5 }} color="warning" />
              ))}
            </Grid>
          </Grid>

          {result.team_capability_map?.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Team capability map</Typography>
                {result.team_capability_map.map((entry, i) => {
                  const member = members.find((m) => m.employee_id === entry.employee_id);
                  return (
                    <Paper key={i} variant="outlined" sx={{ p: 2, mb: 1 }}>
                      <Typography variant="subtitle1">{member?.name || entry.employee_id}</Typography>
                      {entry.current_strengths?.length > 0 && (
                        <Typography variant="body2">Strengths: {entry.current_strengths.join(', ')}</Typography>
                      )}
                      {entry.development_gaps?.length > 0 && (
                        <Typography variant="body2" color="warning.main">
                          Gaps: {entry.development_gaps.join(', ')}
                        </Typography>
                      )}
                    </Paper>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {requiredCapabilities.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Required capabilities</Typography>
                {requiredCapabilities.map((cap, i) => (
                  <Typography key={`${cap}-${i}`} variant="body2" sx={{ mb: 0.5 }}>
                    • {cap}
                  </Typography>
                ))}
              </CardContent>
            </Card>
          )}
        </Box>
      )}
    </Container>
  );
}
