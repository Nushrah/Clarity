import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { useAuthStore } from './store/authStore';

import Login from './components/Auth/Login';
import ManagerDashboard from './components/Dashboard/ManagerDashboard';
import GapBiasAnalytics from './components/Analytics/Analytics';
import Layout from './components/Layout/Layout';
import TeamOverview from './components/CommunityDashboard/CommunityDashboard';
import TeamManagement from './components/Admin/UserManagement';
import UserSettings from './components/Settings/UserSettings';
import ResumeScreening from './components/ResumeScreening/ResumeScreening';
import DecisionLogger from './components/DecisionLogger/DecisionLogger';
import AdaptiveTraining from './components/AdaptiveTraining/AdaptiveTraining';
import GapAnalysis from './components/GapAnalysis/GapAnalysis';
import Recommendations from './components/Recommendations/Recommendations';

const theme = createTheme({
  palette: {
    primary: { main: '#1565c0', light: '#42a5f5', dark: '#0d47a1' },
    secondary: { main: '#6a1b9a', light: '#9c4dcc', dark: '#4a148c' },
    success: { main: '#2e7d32' },
    warning: { main: '#ed6c02' },
    error: { main: '#d32f2f' },
    info: { main: '#0288d1' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  components: {
    MuiCard: { styleOverrides: { root: { borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' } } },
    MuiButton: { styleOverrides: { root: { textTransform: 'none', borderRadius: 8 } } },
  },
});

function ProtectedRoute({ children, requiredRoles = null }) {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (requiredRoles && !requiredRoles.includes(user?.role)) {
    return <Navigate to="/manager-home" replace />;
  }
  return <Layout>{children}</Layout>;
}

function UserRoute({ children }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function RoleBasedRedirect() {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Navigate to="/manager-home" replace />;
}

const managerRoles = ['moderator', 'senior_moderator', 'content_analyst', 'policy_specialist', 'admin'];

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/manager-home" element={<ProtectedRoute requiredRoles={managerRoles}><ManagerDashboard /></ProtectedRoute>} />
          <Route path="/dashboard" element={<Navigate to="/manager-home" replace />} />

          <Route path="/team-overview" element={<ProtectedRoute requiredRoles={managerRoles}><TeamOverview /></ProtectedRoute>} />
          <Route path="/community" element={<Navigate to="/team-overview" replace />} />

          <Route path="/gap-analysis" element={<ProtectedRoute requiredRoles={managerRoles}><GapAnalysis /></ProtectedRoute>} />
          <Route path="/recommendations" element={<ProtectedRoute requiredRoles={managerRoles}><Recommendations /></ProtectedRoute>} />
          <Route path="/resume-screening" element={<ProtectedRoute requiredRoles={managerRoles}><ResumeScreening /></ProtectedRoute>} />
          <Route path="/decision-logger" element={<ProtectedRoute requiredRoles={managerRoles}><DecisionLogger /></ProtectedRoute>} />
          <Route path="/bias-dashboard" element={<ProtectedRoute requiredRoles={['content_analyst', 'senior_moderator', 'policy_specialist', 'admin']}><GapBiasAnalytics /></ProtectedRoute>} />
          <Route path="/analytics" element={<Navigate to="/bias-dashboard" replace />} />
          <Route path="/adaptive-training" element={<ProtectedRoute requiredRoles={managerRoles}><AdaptiveTraining /></ProtectedRoute>} />

          <Route path="/team-management" element={<ProtectedRoute requiredRoles={['admin']}><TeamManagement /></ProtectedRoute>} />
          <Route path="/user-management" element={<Navigate to="/team-management" replace />} />

          <Route path="/settings" element={<UserRoute><UserSettings /></UserRoute>} />
          <Route path="/" element={<RoleBasedRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
