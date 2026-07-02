export const VAGUE_TERMS = [
  'culture fit', 'not ready', 'attitude', 'polish', 'executive presence',
  'too quiet', 'too aggressive', 'gut feeling', 'not a fit', 'personality',
  'vibe', 'likeable', 'likable', 'overqualified', 'bad vibe',
];

export function findVagueTerms(reason) {
  const lowered = (reason || '').toLowerCase();
  return VAGUE_TERMS.filter((t) => lowered.includes(t));
}

export function primaryPathLabel(path) {
  if (path === 'hire_external') return 'Hire externally';
  if (path === 'promote_internal') return 'Promote internally';
  return path || '—';
}

export function normalizePrimaryPath(result) {
  if (result?.primary_path) return result.primary_path;
  const action = (result?.recommended_action || result?.final_recommendation?.action || '').toLowerCase();
  if (action.includes('hire')) return 'hire_external';
  return 'promote_internal';
}
