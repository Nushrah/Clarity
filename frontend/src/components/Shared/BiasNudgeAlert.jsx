import { Alert } from '@mui/material';
import { Warning } from '@mui/icons-material';
import { findVagueTerms } from '../../utils/biasLanguage';

export default function BiasNudgeAlert({ text, sx }) {
  const terms = findVagueTerms(text);
  if (!terms.length) return null;
  return (
    <Alert severity="warning" icon={<Warning />} sx={{ ...sx, borderRadius: 2 }}>
      This reasoning may be too vague ({terms.join(', ')}). Add specific, job-related evidence from the rubric or resume.
    </Alert>
  );
}
