import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardContent, Chip, Container, Divider,
  LinearProgress, List, ListItem, ListItemText, Paper, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography, Tooltip,
} from '@mui/material';
import {
  Upload, Description, CheckCircle, Cancel, Warning, RestartAlt,
} from '@mui/icons-material';
import { talentAPI, hiringAPI } from '../../services/api';
import { useTalentWorkflowStore } from '../../store/talentWorkflowStore';
import { getRequiredCapabilities, buildScreeningJobDescription } from '../../utils/jobDescriptionUtils';
import { findVagueTerms } from '../../utils/biasLanguage';
import ManagerContextBar from '../Shared/ManagerContextBar';
import BiasNudgeAlert from '../Shared/BiasNudgeAlert';

const MANAGER_ID = 'mgr_001';

const DECISIONS = [
  { key: 'Hire', color: 'success', icon: <CheckCircle fontSize="small" /> },
  { key: 'Reject', color: 'error', icon: <Cancel fontSize="small" /> },
];

function aiRecSummary(rec) {
  const r = (rec || '').toLowerCase();
  if (r === 'reject') return { action: 'Reject', color: 'error', hint: 'AI recommends Reject based on rubric gaps.' };
  if (r === 'hold') return { action: 'Review carefully', color: 'warning', hint: 'AI is uncertain — choose Hire only with clear evidence, or Reject with specific gaps.' };
  return { action: 'Consider Hire', color: 'success', hint: 'AI recommends advancing this candidate — Reject only if you identify specific requirement gaps.' };
}


function isOverrideDecision(rec, decision) {
  const r = (rec || '').toLowerCase();
  const d = (decision || '').toLowerCase();
  const recSuggestsHire = r === 'strong interview' || r === 'interview';
  const recSuggestsReject = r === 'reject';
  const recHold = r === 'hold';
  if (recSuggestsHire && d === 'reject') return true;
  if (recSuggestsReject && d === 'hire') return true;
  if (recHold && (d === 'hire' || d === 'reject')) return true;
  return false;
}

function scoreColor(score) {
  if (score >= 70) return 'success';
  if (score >= 40) return 'warning';
  return 'error';
}

export default function ResumeScreening() {
  const navigate = useNavigate();
  const {
    workflowResult, businessGoal, hiringJobId, setHiringJobId,
    hiringResumes: resumes, setHiringResumes,
    hiringScorecards: scorecards, setHiringScorecards,
    hiringDecisionState: decisionState, setHiringDecisionState,
    clearHiring,
  } = useTalentWorkflowStore();

  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  // per-scorecard decision state persists in the store:
  // { [scorecardId]: { decision, reason, vagueTerms, submitting, done } }

  const requiredCapabilities = getRequiredCapabilities(workflowResult);
  const screening = buildScreeningJobDescription(workflowResult, businessGoal);
  const hasCapabilities = requiredCapabilities.length > 0;

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await talentAPI.uploadResume(file, null, screening.title);
      const current = useTalentWorkflowStore.getState().hiringResumes || [];
      setHiringResumes([...current, result]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const generateScorecards = async () => {
    if (!resumes.length) {
      setError('Upload at least one resume first.');
      return;
    }
    setGenerating(true);
    setError(null);
    setInfo(null);
    try {
      const data = await hiringAPI.generateScorecards({
        business_goal: businessGoal || workflowResult?.business_goal || '',
        job_description_text: screening.description || '',
        required_capabilities:
          workflowResult?.required_capabilities?.length
            ? workflowResult.required_capabilities
            : requiredCapabilities.map((c) => ({ capability: c })),
        resume_ids: resumes.map((r) => r.resume_id),
        title: screening.title,
      });
      setHiringJobId(data.job_id);
      const cards = data.scorecards || [];
      const errs = data.errors || [];
      setHiringScorecards(cards);
      if (errs.length) {
        const detail = errs
          .map((e) => `${e.candidate_id || e.resume_id || 'unknown'}: ${e.error}`)
          .join('; ');
        setError(`${errs.length} resume(s) failed and were not saved (${detail}). Model returned invalid data — try again; it will retry across fallback models.`);
      }
      if (cards.length) {
        setInfo(`Generated ${cards.length} validated scorecard(s).`);
      } else if (!errs.length) {
        setInfo('No scorecards generated.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Scorecard generation failed. Check OpenRouter configuration.');
    } finally {
      setGenerating(false);
    }
  };

  const updateDecision = (scId, patch) => {
    const current = useTalentWorkflowStore.getState().hiringDecisionState || {};
    setHiringDecisionState({ ...current, [scId]: { ...current[scId], ...patch } });
  };

  const chooseDecision = (sc, decision) => {
    const vagueTerms = findVagueTerms(decisionState[sc.scorecard_id]?.reason || '');
    updateDecision(sc.scorecard_id, { decision, vagueTerms });
  };

  const onReasonChange = (scId, reason) => {
    updateDecision(scId, { reason, vagueTerms: findVagueTerms(reason) });
  };

  const submitDecision = async (sc) => {
    const state = decisionState[sc.scorecard_id] || {};
    const decision = state.decision;
    if (!decision) {
      updateDecision(sc.scorecard_id, { localError: 'Select a decision first.' });
      return;
    }
    const override = isOverrideDecision(sc.generated_recommendation, decision);
    const needsReason = override || decision === 'Reject';
    if (needsReason && !(state.reason || '').trim()) {
      updateDecision(sc.scorecard_id, { localError: 'Please provide a job-related reason for this decision.' });
      return;
    }
    updateDecision(sc.scorecard_id, { submitting: true, localError: null });
    try {
      const res = await hiringAPI.logDecision({
        application_id: sc.application_id,
        candidate_id: sc.candidate_id,
        job_id: sc.job_id || hiringJobId,
        decision_type: decision === 'Reject' ? 'reject' : 'hire',
        decision_stage: 'resume_screen',
        human_decision: decision,
        generated_recommendation: sc.generated_recommendation,
        rubric_score_at_decision: sc.total_score,
        decision_maker_id: MANAGER_ID,
        decision_reason: state.reason || '',
        evidence_count: sc.evidence_count || 0,
      });
      updateDecision(sc.scorecard_id, {
        submitting: false,
        done: true,
        result: res,
      });
    } catch (err) {
      updateDecision(sc.scorecard_id, {
        submitting: false,
        localError: err.response?.data?.detail || 'Failed to log decision.',
      });
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <ManagerContextBar />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
        <Box>
          <Typography variant="h4" gutterBottom>Resume Screening</Typography>
          <Typography color="text.secondary" sx={{ mb: 1 }}>
            Evidence-based scorecards against your required capabilities. For each candidate, choose <strong>Hire</strong> or <strong>Reject</strong> only.
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Decisions are logged for fairness analysis. Rejections and overrides require a job-related reason.
          </Typography>
        </Box>
        {(resumes.length > 0 || scorecards.length > 0) && (
          <Button size="small" color="inherit" startIcon={<RestartAlt />} onClick={clearHiring}>
            Start over
          </Button>
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {info && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setInfo(null)}>{info}</Alert>}

      {/* Required capabilities — copied exactly from Gap Analysis */}
      {!hasCapabilities ? (
        <Alert
          severity="info"
          sx={{ mb: 3 }}
          action={<Button color="inherit" size="small" onClick={() => navigate('/gap-analysis')}>Run Gap Analysis</Button>}
        >
          No required capabilities yet. Run gap analysis to build the screening rubric.
        </Alert>
      ) : (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Description color="primary" />
              <Typography variant="h6">Required capabilities</Typography>
            </Box>
            <List dense disablePadding>
              {requiredCapabilities.map((cap, i) => (
                <ListItem key={`${cap}-${i}`} disableGutters sx={{ py: 0.25 }}>
                  <ListItemText primary={`• ${cap}`} primaryTypographyProps={{ variant: 'body1' }} />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {(uploading || generating) && <LinearProgress sx={{ mb: 2 }} />}

      {/* Upload + generate */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Button variant="contained" component="label" startIcon={<Upload />} disabled={!hasCapabilities}>
            Upload Resume
            <input type="file" hidden accept=".pdf,.docx,.txt" onChange={handleUpload} />
          </Button>
          {resumes.length > 0 && (
            <Button sx={{ ml: 2 }} variant="outlined" onClick={generateScorecards} disabled={generating}>
              Generate scorecards ({resumes.length})
            </Button>
          )}
          {resumes.length > 0 && (
            <Table sx={{ mt: 2 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Resume</TableCell>
                  <TableCell>File</TableCell>
                  <TableCell>Parsed</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {resumes.map((r) => (
                  <TableRow key={r.resume_id}>
                    <TableCell>{r.resume_id.slice(0, 12)}…</TableCell>
                    <TableCell>{r.filename}</TableCell>
                    <TableCell>{r.text_length} chars</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Scorecards */}
      {scorecards.map((sc) => {
        const state = decisionState[sc.scorecard_id] || {};
        const override = state.decision && isOverrideDecision(sc.generated_recommendation, state.decision);
        const needsReason = override || state.decision === 'Reject';
        const ai = aiRecSummary(sc.generated_recommendation);
        return (
          <Card key={sc.scorecard_id} sx={{ mb: 3, borderRadius: 2, border: override ? '2px solid' : '1px solid', borderColor: override ? 'warning.main' : 'divider', boxShadow: override ? 2 : 1 }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
                <Box>
                  <Typography variant="h6">{sc.candidate_label}</Typography>
                  <Typography variant="caption" color="text.secondary">{screening.title}</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Chip
                    label={`Score ${Math.round(sc.total_score)} / 100`}
                    color={scoreColor(sc.total_score)}
                    sx={{ fontWeight: 600 }}
                  />
                  <Box sx={{ mt: 1 }}>
                    <Chip size="small" label={sc.generated_recommendation} variant="outlined" sx={{ mr: 0.5 }} />
                    <Chip size="small" label={ai.action} color={ai.color} />
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5, maxWidth: 220 }}>
                    {ai.hint}
                  </Typography>
                </Box>
              </Box>

              {/* Criteria scores */}
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Criteria</Typography>
                {sc.criteria_scores.map((c) => (
                  <Box key={c.criterion} sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Tooltip title={c.explanation || ''}>
                        <Typography variant="body2">{c.criterion} (weight {c.weight})</Typography>
                      </Tooltip>
                      <Typography variant="body2" color={`${scoreColor(c.score)}.main`}>{Math.round(c.score)}/100</Typography>
                    </Box>
                    <LinearProgress variant="determinate" value={Math.min(c.score, 100)} color={scoreColor(c.score)} sx={{ height: 6, borderRadius: 3 }} />
                    {c.evidence?.length > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        Evidence: {c.evidence.slice(0, 2).join('; ')}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Box>

              {sc.strengths?.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="subtitle2">Strengths</Typography>
                  {sc.strengths.map((s, i) => <Typography key={i} variant="body2">• {s}</Typography>)}
                </Box>
              )}
              {sc.missing_requirements?.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="subtitle2" color="warning.main">Missing / weak requirements</Typography>
                  {sc.missing_requirements.map((m, i) => <Typography key={i} variant="body2">• {m}</Typography>)}
                </Box>
              )}

              <Divider sx={{ my: 2 }} />

              {/* Decision */}
              {state.done ? (
                <Alert severity={state.result?.override_flag ? 'warning' : 'success'}>
                  Logged: <strong>{state.decision}</strong>
                  {state.result?.override_flag && ' (override of AI recommendation)'}
                  {state.result?.vague_reason_flag && ' — reason flagged as vague'}
                </Alert>
              ) : (
                <>
                  <Typography variant="subtitle2" gutterBottom>Your decision — Hire or Reject</Typography>
                  <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 1 }}>
                    {DECISIONS.map((d) => (
                      <Button
                        key={d.key}
                        size="medium"
                        variant={state.decision === d.key ? 'contained' : 'outlined'}
                        color={d.color}
                        startIcon={d.icon}
                        onClick={() => chooseDecision(sc, d.key)}
                        sx={{ minWidth: 120, borderRadius: 2 }}
                      >
                        {d.key}
                      </Button>
                    ))}
                  </Box>

                  {override && (
                    <Alert severity="warning" sx={{ mb: 1 }}>
                      This differs from the AI recommendation (<strong>{sc.generated_recommendation}</strong>). A job-related reason is required.
                    </Alert>
                  )}

                  {needsReason && (
                    <TextField
                      fullWidth multiline rows={2}
                      label="Please provide a job-related reason for this decision"
                      value={state.reason || ''}
                      onChange={(e) => onReasonChange(sc.scorecard_id, e.target.value)}
                      sx={{ mb: 1 }}
                    />
                  )}

                  {state.vagueTerms?.length > 0 && (
                    <BiasNudgeAlert text={state.reason || ''} sx={{ mb: 1 }} />
                  )}

                  {state.localError && <Alert severity="error" sx={{ mb: 1 }}>{state.localError}</Alert>}

                  <Button variant="contained" onClick={() => submitDecision(sc)} disabled={state.submitting}>
                    {state.submitting ? 'Logging…' : 'Log decision'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        );
      })}

      {scorecards.length > 0 && (
        <Paper sx={{ p: 2, mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Decisions appear in the unified Decision Logger.{' '}
            <Button size="small" onClick={() => navigate('/decision-logger')}>View decision log</Button>
            {' · '}
            <Button size="small" onClick={() => navigate('/bias-dashboard')}>Bias dashboard deep dive</Button>
          </Typography>
        </Paper>
      )}
    </Container>
  );
}
