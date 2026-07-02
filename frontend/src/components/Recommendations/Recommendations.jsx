import { useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, Container, Divider,
  FormControl, FormControlLabel, Grid, InputLabel, LinearProgress, MenuItem, Paper, Radio, RadioGroup,
  Select, Step, StepLabel, Stepper, TextField, Typography,
} from '@mui/material';
import { CheckCircle, Warning, Psychology, Gavel, Analytics, Assignment, PersonSearch } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { talentAPI } from '../../services/api';
import { useTalentWorkflowStore } from '../../store/talentWorkflowStore';
import {
  buildTwoPathComparison, convictionColor, convictionChipColor, biasRiskLabel,
  primaryDecisionSummary, normalizeGapAnalysisForApi, normalizeBiasCategoriesForApi, formatApiError,
} from '../../utils/recommendationUtils';
import { normalizePrimaryPath, primaryPathLabel } from '../../utils/biasLanguage';
import { buildScreeningJobDescription } from '../../utils/jobDescriptionUtils';
import ManagerContextBar from '../Shared/ManagerContextBar';
import BiasNudgeAlert from '../Shared/BiasNudgeAlert';
import { RecommendationBox, SectionPaper } from '../Dashboard/DashboardUI';

const MANAGER_ID = 'mgr_001';

function ConvictionBar({ label, conviction, rationale, evidence, isPrimary }) {
  const value = Number(conviction ?? 0);
  const barColor = convictionColor(value);
  const chipColor = convictionChipColor(value);
  const safeEvidence = Array.isArray(evidence) ? evidence : [];

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: isPrimary ? 'primary.main' : undefined, borderWidth: isPrimary ? 2 : 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" fontWeight={isPrimary ? 700 : 500}>
          {label}{isPrimary && <Chip label="AI primary path" size="small" color="primary" sx={{ ml: 1 }} />}
        </Typography>
        <Chip label={`${(value * 100).toFixed(0)}% conviction`} color={chipColor} size="small" />
      </Box>
      <LinearProgress variant="determinate" value={Math.min(value * 100, 100)} color={barColor} sx={{ my: 1, height: 8, borderRadius: 4 }} />
      <Typography variant="body2" color="text.secondary">{rationale}</Typography>
      {safeEvidence.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {safeEvidence.slice(0, 4).map((e, i) => (
            <Chip key={i} label={typeof e === 'string' ? e : JSON.stringify(e)} size="small" variant="outlined" />
          ))}
        </Box>
      )}
    </Paper>
  );
}

export default function Recommendations() {
  const navigate = useNavigate();
  const { workflowResult, members, managerDecision, setManagerDecision, businessGoal } = useTalentWorkflowStore();
  const [selectedPath, setSelectedPath] = useState(managerDecision?.action || '');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(managerDecision?.targetEmployeeId || '');
  const [upskillPlan, setUpskillPlan] = useState(managerDecision?.upskillPlan || '');
  const [notes, setNotes] = useState(managerDecision?.notes || '');
  const [overrideReason, setOverrideReason] = useState(managerDecision?.overrideReason || '');
  const [submitting, setSubmitting] = useState(false);
  const [postSubmit, setPostSubmit] = useState(null);
  const [error, setError] = useState(null);

  const result = workflowResult;
  const memberList = Array.isArray(members) ? members : [];

  if (!result || typeof result !== 'object') {
    return (
      <Container maxWidth="md" sx={{ py: 3 }}>
        <ManagerContextBar />
        <Typography variant="h4" gutterBottom>Recommendations</Typography>
        <Alert severity="info" sx={{ mb: 2 }}>
          Run a gap analysis first to generate workforce recommendations for your team.
        </Alert>
        <Button variant="contained" onClick={() => navigate('/gap-analysis')}>
          Go to Gap Analysis
        </Button>
      </Container>
    );
  }

  const paths = buildTwoPathComparison(result, memberList);
  const aiPrimaryPath = normalizePrimaryPath(result);
  const promotePath = paths.find((p) => p.key === 'promote_internal');
  const defaultUpskill = promotePath?.upskillPlan || '';
  const biasScore = Number(result.bias_risk_score ?? 0);
  const biasCategories = Array.isArray(result.bias_categories) ? result.bias_categories : [];
  const fairnessConcerns = Array.isArray(result.fairness_concerns)
    ? result.fairness_concerns
    : Array.isArray(result.fairness_flags) ? result.fairness_flags : [];
  const policyViolations = Array.isArray(result.policy_violations) ? result.policy_violations : [];

  const steps = [
    {
      label: 'Team gap analysis',
      icon: <Analytics />,
      detail: `${(result.critical_gaps || []).length} critical, ${(result.moderate_gaps || []).length} moderate gaps identified`,
    },
    {
      label: 'Bias signal detection',
      icon: <Psychology />,
      detail: `Risk score ${(biasScore * 100).toFixed(0)}% (${result.bias_risk_level || biasRiskLabel(biasScore)})`,
    },
    {
      label: 'UBS fairness policy check',
      icon: <Gavel />,
      detail: policyViolations.length
        ? `${policyViolations.length} UBS principle violation(s) — ${result.violation_severity || 'unknown'}`
        : 'Aligned with UBS Pillars, Principles, and Behaviors',
    },
    {
      label: 'Decision synthesis',
      icon: <CheckCircle />,
      detail: `Primary: ${primaryDecisionSummary(result, memberList)} (${((result.decision_synthesis_confidence ?? 0) * 100).toFixed(0)}% confidence)`,
    },
  ];

  const isOverride = selectedPath && selectedPath !== aiPrimaryPath;
  const reasoningText = [notes, overrideReason].filter(Boolean).join(' ');

  const handlePathChange = (path) => {
    setSelectedPath(path);
    if (path === 'promote_internal' && !upskillPlan && defaultUpskill) {
      setUpskillPlan(defaultUpskill);
    }
    if (path === 'promote_internal' && !selectedEmployeeId && promotePath?.employeeId) {
      setSelectedEmployeeId(promotePath.employeeId);
    }
  };

  const handleSubmit = async () => {
    if (!selectedPath) {
      setError('Select hire externally or promote internally before submitting.');
      return;
    }
    if (!notes.trim()) {
      setError('Document your reasoning for the audit trail.');
      return;
    }
    if (isOverride && !overrideReason.trim()) {
      setError('Provide an override reason when your choice differs from the AI primary path.');
      return;
    }
    if (selectedPath === 'promote_internal') {
      const empId = selectedEmployeeId || promotePath?.employeeId;
      if (!empId) {
        setError('Select which team member to promote.');
        return;
      }
      if (!(upskillPlan || defaultUpskill).trim()) {
        setError('Provide an upskill plan for the internal promotion path.');
        return;
      }
    }

    if (!result.decision_id) {
      setError('Missing decision ID — re-run Gap Analysis.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const employeeId = selectedEmployeeId || promotePath?.employeeId;
      const employeeName = memberList.find((m) => m.employee_id === employeeId)?.name;

      const payload = {
        manager_id: MANAGER_ID,
        manager_choice: selectedPath,
        manager_reasoning: notes,
        manager_override_reason: isOverride ? overrideReason : null,
        target_employee_id: selectedPath === 'promote_internal' ? employeeId : null,
        target_employee_name: selectedPath === 'promote_internal' ? employeeName : null,
        upskill_plan: selectedPath === 'promote_internal' ? (upskillPlan || defaultUpskill) : null,
        business_goal: result.business_goal || businessGoal,
        recommended_action: result.recommended_action,
        bias_risk_score: result.bias_risk_score,
        bias_categories: normalizeBiasCategoriesForApi(result.bias_categories),
        ai_recommendation: {
          ...(typeof result.final_recommendation === 'object' && result.final_recommendation ? result.final_recommendation : {}),
          primary_path: aiPrimaryPath,
          path_comparison: result.path_comparison,
        },
        gap_analysis: normalizeGapAnalysisForApi(result.gap_analysis || result.critical_gaps),
      };

      const response = await talentAPI.submitManagerChoice(result.decision_id, payload);

      const storePayload = {
        action: selectedPath,
        targetEmployeeId: employeeId,
        targetEmployeeName: employeeName,
        upskillPlan: payload.upskill_plan,
        notes,
        overrideReason: isOverride ? overrideReason : null,
        submittedAt: new Date().toISOString(),
      };
      setManagerDecision(storePayload);
      setPostSubmit(response);
    } catch (err) {
      setError(formatApiError(err, 'Failed to submit decision.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <ManagerContextBar />
      <Typography variant="h4" gutterBottom>Recommendations</Typography>
      <Typography color="text.secondary" sx={{ mb: 1 }}>
        Structured decision process for: {businessGoal || result.business_goal}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 3 }}>
        Decision ID: {result.decision_id}
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      {/* AI guidance banner — not a submit option */}
      <Alert severity="info" sx={{ mb: 2 }} icon={<Psychology />}>
        <strong>AI guidance:</strong> {primaryPathLabel(aiPrimaryPath)} is the primary path based on gap analysis and synthesis.
        You must choose either <strong>Hire externally</strong> or <strong>Promote internally</strong> — there is no “accept AI” shortcut.
      </Alert>

      {postSubmit && (
        <SectionPaper sx={{ mb: 3, p: 2 }}>
          <Typography variant="h6" gutterBottom>Decision recorded</Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Your choice: <strong>{primaryPathLabel(postSubmit.manager_choice)}</strong>
            {postSubmit.override_vs_ai && <Chip size="small" color="warning" label="Override vs AI" sx={{ ml: 1 }} />}
          </Typography>
          {postSubmit.post_decision_bias_score != null && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Post-decision bias review: {Math.round(postSubmit.post_decision_bias_score * 100)}% risk
            </Typography>
          )}
          {postSubmit.coaching_notes && <RecommendationBox text={postSubmit.coaching_notes} compact />}
          <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button variant="contained" startIcon={<Assignment />} onClick={() => navigate('/decision-logger')}>
              View in Decision Logger
            </Button>
            {postSubmit.manager_choice === 'hire_external' && (
              <Button variant="outlined" startIcon={<PersonSearch />} onClick={() => navigate('/resume-screening')}>
                Continue to Resume Screening
              </Button>
            )}
          </Box>
        </SectionPaper>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Decision process</Typography>
          <Stepper activeStep={steps.length} alternativeLabel sx={{ mb: 3 }}>
            {steps.map((s) => (
              <Step key={s.label} completed>
                <StepLabel>{s.label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          <Grid container spacing={2}>
            {steps.map((s) => (
              <Grid item xs={12} sm={6} md={3} key={s.label}>
                <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    {s.icon}
                    <Typography variant="subtitle2">{s.label}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">{s.detail}</Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Bias risk assessment</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Typography variant="h4" color={biasScore >= 0.65 ? 'error.main' : 'text.primary'}>
              {(biasScore * 100).toFixed(0)}%
            </Typography>
            <Chip label={result.bias_risk_level || biasRiskLabel(biasScore)} color={biasScore >= 0.65 ? 'error' : 'default'} />
            {result.reflection_required && <Chip icon={<Warning />} label="Reflection suggested" color="warning" />}
          </Box>
          {biasCategories.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {biasCategories.map((c, i) => (
                <Chip key={i} label={typeof c === 'string' ? c : JSON.stringify(c)} size="small" color="warning" variant="outlined" />
              ))}
            </Box>
          )}
          {fairnessConcerns.length > 0 && fairnessConcerns.map((f, i) => (
            <Typography key={i} variant="body2">• {typeof f === 'string' ? f : JSON.stringify(f)}</Typography>
          ))}
        </CardContent>
      </Card>

      {(() => {
        const screening = buildScreeningJobDescription(result, businessGoal);
        if (!screening.bullets.length) return null;
        return (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Resume screening rubric</Typography>
              {screening.bullets.map((b) => (
                <Typography key={b} variant="body1" sx={{ mb: 0.5 }}>• {b}</Typography>
              ))}
              <Button size="small" variant="outlined" sx={{ mt: 1 }} onClick={() => navigate('/resume-screening')}>
                Use in Resume Screening
              </Button>
            </CardContent>
          </Card>
        );
      })()}

      <Typography variant="h6" gutterBottom>AI path comparison</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Compare external hire vs internal promote+upskill. Higher conviction = stronger AI evidence for that path.
      </Typography>
      {paths.map((p) => (
        <ConvictionBar key={p.key} {...p} isPrimary={p.key === aiPrimaryPath} />
      ))}

      {result.decision_synthesis_reasoning && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
          <Typography variant="subtitle2" gutterBottom>Decision synthesis reasoning</Typography>
          <Typography variant="body2">{result.decision_synthesis_reasoning}</Typography>
        </Paper>
      )}

      <Divider sx={{ my: 3 }} />

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Your decision</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Choose exactly one path. If you differ from the AI primary path, document why.
          </Typography>

          <FormControl component="fieldset" sx={{ mb: 2, width: '100%' }}>
            <RadioGroup value={selectedPath} onChange={(e) => handlePathChange(e.target.value)}>
              {paths.map((p) => (
                <FormControlLabel
                  key={p.key}
                  value={p.key}
                  control={<Radio />}
                  label={`${p.label} (${(p.conviction * 100).toFixed(0)}% AI conviction)`}
                />
              ))}
            </RadioGroup>
          </FormControl>

          {selectedPath === 'promote_internal' && (
            <>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Team member to promote</InputLabel>
                <Select
                  value={selectedEmployeeId || promotePath?.employeeId || ''}
                  label="Team member to promote"
                  onChange={(e) => setSelectedEmployeeId(e.target.value)}
                >
                  {memberList.map((m) => (
                    <MenuItem key={m.employee_id} value={m.employee_id}>
                      {m.name} — {m.role} ({m.level})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                fullWidth multiline rows={3} label="Upskill plan (required)"
                value={upskillPlan || defaultUpskill}
                onChange={(e) => setUpskillPlan(e.target.value)}
                sx={{ mb: 2 }}
                placeholder="Learning path, milestones, and practice projects..."
              />
            </>
          )}

          {isOverride && (
            <TextField
              fullWidth multiline rows={2} label="Override reason (required)"
              value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
              sx={{ mb: 2 }}
              placeholder="What evidence supports choosing differently from the AI primary path?"
            />
          )}

          <TextField
            fullWidth multiline rows={3} label="Manager reasoning (required)"
            value={notes} onChange={(e) => setNotes(e.target.value)}
            sx={{ mb: 1 }}
            placeholder="Document specific, job-related evidence for audit and pattern learning..."
          />
          <BiasNudgeAlert text={reasoningText} sx={{ mb: 2 }} />

          <Button variant="contained" onClick={handleSubmit} disabled={submitting || !!postSubmit}>
            {submitting ? 'Running post-decision review…' : 'Submit manager decision'}
          </Button>

          {managerDecision && !postSubmit && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Last submitted: <strong>{primaryPathLabel(managerDecision.action)}</strong> at {new Date(managerDecision.submittedAt).toLocaleString()}
            </Alert>
          )}
        </CardContent>
      </Card>
    </Container>
  );
}
