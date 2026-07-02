import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardContent, Chip, LinearProgress, Typography,
} from '@mui/material';
import { Psychology } from '@mui/icons-material';
import { talentAPI } from '../../services/api';

const PRIORITY_COLOR = { high: 'error', medium: 'warning', low: 'info' };

export default function ReflectionQueuePanel() {
  const navigate = useNavigate();
  const [queue, setQueue] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const q = await talentAPI.getReflectionQueue().catch(() => ({ items: [] }));
      if (!active) return;
      setQueue(q);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ my: 2 }} />;

  const items = queue?.items || [];

  return (
    <Box sx={{ mt: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Psychology color="secondary" />
        <Typography variant="h6">Manager reflection queue</Typography>
      </Box>

      {items.length === 0 ? (
        <Alert severity="success">No decisions are awaiting reflection. High-risk decisions will appear here for review.</Alert>
      ) : (
        items.map((item) => (
          <Card key={item.decision_id} variant="outlined" sx={{ mb: 1 }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                <Box>
                  <Typography variant="subtitle2">{item.business_goal || 'Workforce decision'}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    AI recommendation: {item.ai_recommendation || 'n/a'} · bias risk {Math.round((item.bias_risk_score || 0) * 100)}%
                  </Typography>
                </Box>
                <Chip size="small" label={item.priority} color={PRIORITY_COLOR[item.priority] || 'default'} />
              </Box>
              {item.bias_categories?.length > 0 && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                  {item.bias_categories.map((c) => <Chip key={c} size="small" variant="outlined" label={c} />)}
                </Box>
              )}
              {item.reflection_questions?.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  {item.reflection_questions.slice(0, 2).map((q, i) => (
                    <Typography key={i} variant="body2" color="text.secondary">• {q}</Typography>
                  ))}
                </Box>
              )}
              <Button size="small" sx={{ mt: 1 }} onClick={() => navigate('/recommendations')}>Review decision</Button>
            </CardContent>
          </Card>
        ))
      )}
    </Box>
  );
}
