import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, Chip, LinearProgress, Table, TableBody, TableCell, TableHead, TableRow,
  Tooltip, Typography,
} from '@mui/material';
import { History } from '@mui/icons-material';
import { hiringAPI } from '../../services/api';
import { PanelHeader, RecommendationBox } from './DashboardUI';

function labelFor(candidateId, idx) {
  if (candidateId && /_(\d{3})$/.test(candidateId)) {
    return `Candidate ${candidateId.match(/_(\d{3})$/)[1]}`;
  }
  return `Candidate ${String(idx + 1).padStart(3, '0')}`;
}

function normalizeDecision(d) {
  const raw = (d.human_decision || d.decision_outcome || '').toLowerCase();
  if (raw === 'reject' || raw === 'rejected') return 'Reject';
  if (['hire', 'offer', 'interview', 'move to next stage', 'strong interview'].includes(raw)) return 'Hire';
  return d.human_decision || d.decision_outcome || '—';
}

function aiRecHint(rec) {
  const r = (rec || '').toLowerCase();
  if (r === 'reject') return 'AI suggested Reject';
  if (r === 'hold') return 'AI suggested review (Hold)';
  return 'AI suggested advance (consider Hire)';
}

export default function RecentDecisionsPanel() {
  const navigate = useNavigate();
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const res = await hiringAPI.getDecisions().catch(() => ({ decisions: [] }));
      if (!active) return;
      setDecisions((res?.decisions || []).slice(0, 12));
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ borderRadius: 2 }} />;
  if (decisions.length === 0) return null;

  const overrideCount = decisions.filter((d) => d.override_flag).length;
  const vagueCount = decisions.filter((d) => d.vague_reason_flag).length;

  return (
    <Box>
      <PanelHeader
        icon={<History color="action" />}
        title="Recent hiring decisions"
        subtitle="Latest Hire / Reject choices with rubric scores and quality flags. At screening, managers choose only Hire or Reject."
        action={<Button size="small" onClick={() => navigate('/decision-logger')}>View all decisions</Button>}
      />

      <Box sx={{ overflowX: 'auto', borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Table size="small">
          <TableHead sx={{ bgcolor: 'grey.50' }}>
            <TableRow>
              <TableCell><strong>Candidate</strong></TableCell>
              <TableCell><strong>Stage</strong></TableCell>
              <TableCell align="right"><strong>Score</strong></TableCell>
              <TableCell><strong>AI guidance</strong></TableCell>
              <TableCell><strong>Your decision</strong></TableCell>
              <TableCell><strong>Flags</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {decisions.map((d, idx) => {
              const decision = normalizeDecision(d);
              return (
                <TableRow key={d.decision_id} hover>
                  <TableCell>{labelFor(d.candidate_id, idx)}</TableCell>
                  <TableCell><Typography variant="caption">{d.decision_stage?.replace(/_/g, ' ')}</Typography></TableCell>
                  <TableCell align="right">
                    <Typography fontWeight={600}>{d.rubric_score_at_decision != null ? Math.round(d.rubric_score_at_decision) : '—'}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">{aiRecHint(d.generated_recommendation)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={decision} color={decision === 'Hire' ? 'success' : decision === 'Reject' ? 'error' : 'default'} />
                  </TableCell>
                  <TableCell>
                    {d.override_flag && <Chip size="small" color="warning" label="Override" sx={{ mr: 0.5 }} />}
                    {d.vague_reason_flag && (
                      <Tooltip title={d.decision_reason || 'Vague reason'}>
                        <Chip size="small" color="error" variant="outlined" label="Vague reason" />
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>

      <Box sx={{ mt: 2 }}>
        <RecommendationBox
          text={
            vagueCount > 0
              ? `${vagueCount} decision(s) used vague language — edit future Reject reasons to cite specific resume evidence.`
              : overrideCount > 0
                ? `${overrideCount} override(s) logged — ensure each documents why the rubric recommendation was set aside.`
                : 'Decisions look consistent. Keep choosing Hire or Reject with job-specific reasons for every Reject.'
          }
        />
      </Box>
    </Box>
  );
}
