import { useEffect, useState } from 'react';
import {
  Alert, Box, Chip, LinearProgress, Typography,
} from '@mui/material';
import { Diversity3 } from '@mui/icons-material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { hiringAPI } from '../../services/api';
import { chartRecommendations } from './dashboardMetrics';
import { PanelHeader, RecommendationBox } from './DashboardUI';

export default function DemographicFairnessPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const d = await hiringAPI.getDemographicFairness().catch(() => ({ available: false }));
      if (!active) return;
      setData(d);
      setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <LinearProgress sx={{ borderRadius: 2 }} />;

  const tips = chartRecommendations({});

  return (
    <Box>
      <PanelHeader
        icon={<Diversity3 color="info" />}
        title="Demographic fairness (voluntary)"
        subtitle="Uses only voluntary, self-reported data — never inferred. Small groups are hidden to protect individuals."
      />

      {!data?.available ? (
        <Alert severity="info" sx={{ borderRadius: 2 }}>
          {data?.reason || 'No voluntary demographic data yet. Candidates can opt in during application; this section stays empty until then.'}
          <RecommendationBox text="When data is available, compare selection rates across groups and investigate any group below the 80% rule with structured, evidence-based review — not individual profiling." compact />
        </Alert>
      ) : (
        <FairnessContent data={data} tip={tips.demographic} />
      )}
    </Box>
  );
}

function FairnessContent({ data, tip }) {
  const rows = Object.entries(data.selection_rate_by_group || {});
  const chartData = rows
    .filter(([, v]) => typeof v === 'number')
    .map(([name, value]) => ({ name, value: Math.round(value * 100) }));
  const suppressed = rows.filter(([, v]) => typeof v !== 'number').map(([name]) => name);
  const adverse = data.adverse_impact_by_group || {};

  return (
    <Box
      sx={{
        p: 2.5, borderRadius: 2, border: '1px solid', borderColor: 'divider',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      <Typography variant="subtitle1" fontWeight={600} gutterBottom>Selection rate by group</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Share of candidates in each voluntary group who received a Hire (or advanced). Green = within fairness guidelines; red = below 80% rule.
      </Typography>

      {chartData.length === 0 ? (
        <Typography variant="body2" color="text.secondary">Not enough data in any group to report.</Typography>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={chartData}>
            <XAxis dataKey="name" />
            <YAxis unit="%" domain={[0, 100]} />
            <Tooltip formatter={(v) => `${v}% selected`} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={adverse[entry.name]?.adverse_impact ? '#d32f2f' : '#2e7d32'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      <Box sx={{ mt: 2 }}>
        {Object.entries(adverse).map(([group, info]) => (
          <Box key={group} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 1 }}>
            <Typography variant="body2">
              <strong>{group}</strong> — selection is {Math.round(info.ratio * 100)}% of the highest group&apos;s rate
            </Typography>
            {info.adverse_impact
              ? <Chip size="small" color="error" label="Below 80% — structured review recommended" />
              : <Chip size="small" color="success" variant="outlined" label="Within 80% rule" />}
          </Box>
        ))}
      </Box>

      {suppressed.length > 0 && (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          Hidden for privacy (group too small): {suppressed.join(', ')}
        </Typography>
      )}

      <Box sx={{ mt: 2 }}>
        <RecommendationBox
          text={
            Object.values(adverse).some((a) => a.adverse_impact)
              ? `${tip} One or more groups show adverse impact — review screening criteria and reason quality, not individual candidates.`
              : `${tip} All reported groups are within the 80% guideline on current data.`
          }
        />
      </Box>
    </Box>
  );
}
