import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Box, Chip, Paper, Typography, Button } from '@mui/material';
import { useTalentWorkflowStore } from '../../store/talentWorkflowStore';
import { talentAPI } from '../../services/api';

const STEPS = [
  { key: 'gap', label: 'Gap analysis', path: '/gap-analysis' },
  { key: 'recommend', label: 'Recommendations', path: '/recommendations' },
  { key: 'screen', label: 'Resume screening', path: '/resume-screening' },
  { key: 'log', label: 'Decision logger', path: '/decision-logger' },
];

function stepIndex(pathname) {
  if (pathname.includes('gap-analysis')) return 0;
  if (pathname.includes('recommendations')) return 1;
  if (pathname.includes('resume-screening')) return 2;
  if (pathname.includes('decision-logger')) return 3;
  return -1;
}

export default function ManagerContextBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { workflowResult, businessGoal } = useTalentWorkflowStore();
  const [pendingReflect, setPendingReflect] = useState(0);
  const active = stepIndex(location.pathname);

  useEffect(() => {
    talentAPI.getReflectionQueue().then((q) => setPendingReflect(q?.pending_reflections || 0)).catch(() => {});
  }, [location.pathname]);

  if (active < 0) return null;

  const goal = businessGoal || workflowResult?.business_goal;
  const did = workflowResult?.decision_id;

  return (
    <Paper variant="outlined" sx={{ p: 1.5, mb: 2, borderRadius: 2, bgcolor: 'grey.50' }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>WORKFLOW</Typography>
        {STEPS.map((s, i) => (
          <Chip
            key={s.key}
            size="small"
            label={s.label}
            color={i === active ? 'primary' : i < active ? 'success' : 'default'}
            variant={i === active ? 'filled' : 'outlined'}
            onClick={() => navigate(s.path)}
            sx={{ cursor: 'pointer' }}
          />
        ))}
        {pendingReflect > 0 && (
          <Chip size="small" color="warning" label={`${pendingReflect} reflection(s) pending`} onClick={() => navigate('/recommendations')} />
        )}
      </Box>
      {goal && (
        <Typography variant="body2" color="text.secondary">
          Goal: <strong>{goal}</strong>
          {did && <> · Decision <Typography component="span" variant="caption">{did.slice(0, 14)}…</Typography></>}
        </Typography>
      )}
      {active === 1 && workflowResult?.primary_path && (
        <Typography variant="caption" color="info.main" display="block" sx={{ mt: 0.5 }}>
          AI leans toward: {workflowResult.primary_path === 'hire_external' ? 'Hire externally' : 'Promote internally'}
        </Typography>
      )}
      {active === 1 && (
        <Button size="small" sx={{ mt: 0.5 }} onClick={() => navigate('/decision-logger')}>View decision log</Button>
      )}
    </Paper>
  );
}
