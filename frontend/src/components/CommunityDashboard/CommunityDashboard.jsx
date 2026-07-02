import { useEffect, useState } from 'react';
import {
  Alert, Box, Card, CardContent, Chip, CircularProgress, Container,
  Grid, LinearProgress, Paper, Typography,
} from '@mui/material';
import { Groups, TrendingUp, WorkOutline } from '@mui/icons-material';
import { talentAPI } from '../../services/api';

const TEAM_ID = 'team_alpha';

function MemberCard({ member }) {
  const utilization = member.workload?.utilization ?? 0;
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6">{member.name}</Typography>
          <Chip label={member.level} size="small" color="primary" variant="outlined" />
        </Box>
        <Typography color="text.secondary" gutterBottom>{member.role}</Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          Utilization: {(utilization * 100).toFixed(0)}% · Projects: {member.workload?.active_projects ?? '—'}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
          Skills
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
          {(member.skills || []).map((skill) => (
            <Chip key={skill} label={skill} size="small" />
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
          Recent evidence
        </Typography>
        {(member.performance_evidence || []).slice(0, 2).map((item, i) => (
          <Typography key={i} variant="body2" sx={{ mb: 0.5 }}>• {item}</Typography>
        ))}
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, mb: 0.5 }}>
          Career goals
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {(member.career_goals || []).map((goal) => (
            <Chip key={goal} label={goal} size="small" variant="outlined" />
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}

export default function TeamOverview() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [team, setTeam] = useState(null);
  const [members, setMembers] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await talentAPI.getTeamMembers(TEAM_ID);
        setTeam(data.team);
        setMembers(data.members || []);
        if (!data.members?.length) {
          setError('No team members found. Run backend/scripts/seed_team_data.py to seed the team.');
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load team. Is the backend running on port 8000?');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>Team Overview</Typography>
        <Typography color="text.secondary">
          Your 5-person team — skills, workload, and performance evidence for workforce decisions.
        </Typography>
      </Box>

      {error && <Alert severity="warning" sx={{ mb: 3 }}>{error}</Alert>}

      {team && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Groups color="primary" />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Team</Typography>
                  <Typography variant="h6">{team.team_name}</Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUp color="success" />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Business goal</Typography>
                  <Typography variant="body1">{team.business_goal}</Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <WorkOutline color="info" />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Team size</Typography>
                  <Typography variant="h6">{members.length} members</Typography>
                </Box>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {members.length > 0 && (
        <>
          <Typography variant="overline" color="text.secondary">Average utilization</Typography>
          <LinearProgress
            variant="determinate"
            value={
              (members.reduce((sum, m) => sum + (m.workload?.utilization || 0), 0) / members.length) * 100
            }
            sx={{ mb: 3, height: 8, borderRadius: 4 }}
          />
          <Grid container spacing={3}>
            {members.map((member) => (
              <Grid item xs={12} md={6} lg={4} key={member.employee_id}>
                <MemberCard member={member} />
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Container>
  );
}
