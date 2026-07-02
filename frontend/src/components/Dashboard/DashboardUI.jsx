import {
  Box, Card, CardContent, Chip, Grid, LinearProgress, Paper, Typography, alpha,
} from '@mui/material';
import { LightbulbOutlined } from '@mui/icons-material';
import { STATUS } from './dashboardMetrics';

const CARD_SX = {
  height: '100%',
  borderRadius: 2,
  border: '1px solid',
  borderColor: 'divider',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
  transition: 'box-shadow 0.2s',
  '&:hover': { boxShadow: '0 4px 12px rgba(0,0,0,0.08)' },
};

export function PanelHeader({ icon, title, subtitle, action }) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          {icon}
          <Typography variant="h6" fontWeight={600}>{title}</Typography>
        </Box>
        {action}
      </Box>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 720 }}>
          {subtitle}
        </Typography>
      )}
    </Box>
  );
}

export function MetricCard({ icon, insight }) {
  if (!insight) return null;
  const st = STATUS[insight.status] || STATUS.neutral;
  return (
    <Grid item xs={12} sm={6} md={3}>
      <Card sx={CARD_SX}>
        <CardContent sx={{ pb: '16px !important' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {icon}
              <Typography variant="subtitle2" color="text.secondary" fontWeight={500}>
                {insight.label}
              </Typography>
            </Box>
            <Chip size="small" label={st.label} color={st.color} variant="outlined" sx={{ fontSize: '0.65rem' }} />
          </Box>
          <Typography variant="h4" fontWeight={700} sx={{ mb: 0.5 }}>
            {insight.value}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: insight.bar != null ? 1 : 1.5, lineHeight: 1.4 }}>
            {insight.description}
          </Typography>
          {insight.bar != null && (
            <LinearProgress
              variant="determinate"
              value={Math.min(insight.bar * 100, 100)}
              color={st.color === 'neutral' ? 'primary' : st.color}
              sx={{ height: 6, borderRadius: 3, mb: 1.5 }}
            />
          )}
          <RecommendationBox text={insight.recommendation} />
        </CardContent>
      </Card>
    </Grid>
  );
}

export function RecommendationBox({ text, compact }) {
  if (!text) return null;
  return (
    <Paper
      variant="outlined"
      sx={{
        p: compact ? 1 : 1.25,
        bgcolor: (t) => alpha(t.palette.info.main, 0.06),
        borderColor: (t) => alpha(t.palette.info.main, 0.2),
        borderRadius: 1.5,
        display: 'flex',
        gap: 1,
        alignItems: 'flex-start',
      }}
    >
      <LightbulbOutlined sx={{ fontSize: 18, color: 'info.main', mt: 0.15, flexShrink: 0 }} />
      <Typography variant="caption" color="text.secondary" lineHeight={1.5}>
        <Typography component="span" variant="caption" fontWeight={600} color="info.dark">
          Recommendation:{' '}
        </Typography>
        {text}
      </Typography>
    </Paper>
  );
}

export function ChartCard({ title, description, recommendation, children, height = 260 }) {
  return (
    <Grid item xs={12} md={6}>
      <Card sx={CARD_SX}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>{title}</Typography>
          {description && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {description}
            </Typography>
          )}
          <Box sx={{ width: '100%', height }}>{children}</Box>
          {recommendation && (
            <Box sx={{ mt: 1.5 }}>
              <RecommendationBox text={recommendation} compact />
            </Box>
          )}
        </CardContent>
      </Card>
    </Grid>
  );
}

export function RateInsightCard({ title, description, entries, asPct = true, recommendation }) {
  const rows = Object.entries(entries || {}).filter(([, v]) => v != null);
  return (
    <Grid item xs={12} md={4}>
      <Card sx={CARD_SX}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>{title}</Typography>
          {description && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {description}
            </Typography>
          )}
          {rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No data yet</Typography>
          ) : (
            rows.map(([k, v]) => (
              <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.75, py: 0.25 }}>
                <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</Typography>
                <Typography variant="body2" fontWeight={600}>{asPct ? `${Math.round(v * 100)}%` : v}</Typography>
              </Box>
            ))
          )}
          {recommendation && (
            <Box sx={{ mt: 1.5 }}>
              <RecommendationBox text={recommendation} compact />
            </Box>
          )}
        </CardContent>
      </Card>
    </Grid>
  );
}

export function SectionPaper({ children, sx }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: { xs: 2, md: 3 },
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        ...sx,
      }}
    >
      {children}
    </Paper>
  );
}
