import { useEffect, useState } from 'react';
import {
  Alert, Container, Typography, Card, CardContent, Chip, LinearProgress,
} from '@mui/material';
import { School } from '@mui/icons-material';
import { talentAPI } from '../../services/api';

const STATUS_COLOR = { recommended: 'warning', pending: 'default', completed: 'success' };

export default function AdaptiveTraining() {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const res = await talentAPI.getTrainingRecommendations().catch(() => ({ recommendations: [] }));
      if (!active) return;
      setModules(res?.recommendations || []);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h4" gutterBottom>Adaptive Training</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Training modules recommended when recurring manager bias patterns are detected.
      </Typography>
      <Alert severity="info" sx={{ mb: 3 }}>
        Decision-support only — training helps managers reflect; it does not automate employment decisions.
      </Alert>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {!loading && modules.length === 0 && (
        <Alert severity="success">
          No training recommended right now. Modules appear here when recurring bias patterns are detected in your decisions.
        </Alert>
      )}

      {modules.map((m) => (
        <Card key={m.training_id} sx={{ mb: 2 }}>
          <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <School color="primary" />
            <div style={{ flex: 1 }}>
              <Typography variant="subtitle1">{m.module_title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {m.module_type}{m.trigger_type ? ` · triggered by ${m.trigger_type}` : ''}
              </Typography>
              {m.module_payload?.why && (
                <Typography variant="body2" color="text.secondary">{m.module_payload.why}</Typography>
              )}
            </div>
            <Chip label={m.status} color={STATUS_COLOR[m.status] || 'default'} size="small" />
          </CardContent>
        </Card>
      ))}
    </Container>
  );
}
