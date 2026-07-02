import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Button, Chip, Collapse, Container, IconButton, LinearProgress,
  Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import { Refresh, KeyboardArrowDown, KeyboardArrowUp, School } from '@mui/icons-material';
import { talentAPI } from '../../services/api';
import ManagerContextBar from '../Shared/ManagerContextBar';
import { SectionPaper, RecommendationBox } from '../Dashboard/DashboardUI';
import { primaryPathLabel } from '../../utils/biasLanguage';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'workforce', label: 'Workforce' },
  { key: 'hiring', label: 'Resume screening' },
];

function sourceLabel(d) {
  return d.source === 'hiring' ? 'Resume screening' : 'Workforce';
}

function decisionLabel(d) {
  const m = d.manager_decision || '—';
  if (m === 'hire_external') return 'Hire externally';
  if (m === 'promote_internal') return 'Promote internally';
  return m;
}

function Row({ row, onTraining }) {
  const [open, setOpen] = useState(false);
  const patterns = row.recurring_patterns || [];
  const hasPatterns = patterns.length > 0;

  return (
    <>
      <TableRow hover sx={{ '& > *': { borderBottom: open ? 'none' : undefined } }}>
        <TableCell>
          <IconButton size="small" onClick={() => setOpen(!open)}>
            {open ? <KeyboardArrowUp /> : <KeyboardArrowDown />}
          </IconButton>
        </TableCell>
        <TableCell>{String(row.created_at || '').slice(0, 10)}</TableCell>
        <TableCell><Chip size="small" label={sourceLabel(row)} variant="outlined" /></TableCell>
        <TableCell>
          <Chip
            size="small"
            label={decisionLabel(row)}
            color={String(row.manager_decision).toLowerCase().includes('reject') ? 'error' : 'success'}
          />
        </TableCell>
        <TableCell>{row.ai_recommendation || primaryPathLabel(row.ai_recommendation_detail?.primary_path) || '—'}</TableCell>
        <TableCell align="right">{row.rubric_score != null ? Math.round(row.rubric_score) : '—'}</TableCell>
        <TableCell>
          {row.bias_risk_score != null ? `${Math.round(row.bias_risk_score * 100)}%` : '—'}
          {row.post_decision_bias_score != null && (
            <Typography variant="caption" display="block" color="text.secondary">
              post: {Math.round(row.post_decision_bias_score * 100)}%
            </Typography>
          )}
        </TableCell>
        <TableCell>
          {row.override_flag && <Chip size="small" color="warning" label="Override" sx={{ mr: 0.5 }} />}
          {row.vague_reason_flag && <Chip size="small" color="error" variant="outlined" label="Vague" sx={{ mr: 0.5 }} />}
          {hasPatterns && <Chip size="small" color="secondary" variant="outlined" label="Pattern" />}
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={8} sx={{ py: 0 }}>
          <Collapse in={open}>
            <Box sx={{ py: 2, px: 1 }}>
              {row.candidate_label && (
                <Typography variant="body2"><strong>Candidate:</strong> {row.candidate_label} · stage {row.decision_stage}</Typography>
              )}
              {row.business_goal && (
                <Typography variant="body2" sx={{ mt: 0.5 }}><strong>Context:</strong> {row.business_goal}</Typography>
              )}
              {row.manager_reasoning && (
                <Typography variant="body2" sx={{ mt: 0.5 }}><strong>Reasoning:</strong> {row.manager_reasoning}</Typography>
              )}
              {row.upskill_plan && (
                <Typography variant="body2" sx={{ mt: 0.5 }}><strong>Upskill plan:</strong> {row.upskill_plan}</Typography>
              )}
              {row.coaching_notes && (
                <Box sx={{ mt: 1 }}>
                  <RecommendationBox text={row.coaching_notes} compact />
                </Box>
              )}
              {hasPatterns && (
                <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                  {patterns.map((p, i) => (
                    <Chip key={i} size="small" label={typeof p === 'object' ? p.pattern : p} color="warning" variant="outlined" />
                  ))}
                  <Button size="small" startIcon={<School />} onClick={onTraining}>Adaptive training</Button>
                </Box>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export default function DecisionLogger() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [decisions, setDecisions] = useState([]);
  const [filter, setFilter] = useState('all');

  const fetchDecisions = useCallback(() => {
    setLoading(true);
    talentAPI.getUnifiedDecisionHistory('mgr_001', 100)
      .then((data) => setDecisions(data.decisions || []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchDecisions(); }, [location.pathname, fetchDecisions]);

  const filtered = decisions.filter((d) => {
    if (filter === 'workforce') return d.source === 'workforce';
    if (filter === 'hiring') return d.source === 'hiring';
    return true;
  });

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <ManagerContextBar />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>Decision Logger</Typography>
          <Typography color="text.secondary">
            Unified audit trail — workforce planning (hire / promote) and resume screening (Hire / Reject).
          </Typography>
        </Box>
        <Button startIcon={<Refresh />} onClick={fetchDecisions} disabled={loading}>Refresh</Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        {FILTERS.map((f) => (
          <Chip
            key={f.key}
            label={`${f.label}${f.key === 'all' ? ` (${decisions.length})` : ''}`}
            color={filter === f.key ? 'primary' : 'default'}
            onClick={() => setFilter(f.key)}
            variant={filter === f.key ? 'filled' : 'outlined'}
          />
        ))}
      </Box>

      {loading && <LinearProgress sx={{ mb: 2, borderRadius: 2 }} />}

      <SectionPaper sx={{ p: 0, overflow: 'hidden' }}>
        <Table size="small">
          <TableHead sx={{ bgcolor: 'grey.50' }}>
            <TableRow>
              <TableCell width={48} />
              <TableCell><strong>Date</strong></TableCell>
              <TableCell><strong>Source</strong></TableCell>
              <TableCell><strong>Decision</strong></TableCell>
              <TableCell><strong>AI guidance</strong></TableCell>
              <TableCell align="right"><strong>Score</strong></TableCell>
              <TableCell><strong>Bias risk</strong></TableCell>
              <TableCell><strong>Flags</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {!loading && filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ py: 4 }}>
                  No decisions yet. Run Gap Analysis → Recommendations, or Resume Screening.
                  <RecommendationBox text="Run: python scripts/seed_all_demo.py to populate demo workforce + hiring decisions." compact />
                </TableCell>
              </TableRow>
            ) : filtered.map((d) => (
              <Row key={d.decision_id} row={d} onTraining={() => navigate('/adaptive-training')} />
            ))}
          </TableBody>
        </Table>
      </SectionPaper>
    </Container>
  );
}
