import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/api/auth/login', { username, password });
    const { token, user } = response.data;
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    return response.data;
  },

  logout: async () => {
    try {
      await api.post('/api/auth/logout');
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  },

  getCurrentUser: async () => {
    const response = await api.get('/api/auth/current-user');
    return response.data;
  },

  register: async (userData) => {
    const response = await api.post('/api/auth/register', userData);
    return response.data;
  },

  updatePassword: async (currentPassword, newPassword) => {
    const response = await api.put('/api/auth/password', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  },

  getAllUsers: async () => {
    const response = await api.get('/api/auth/users');
    return response.data;
  },

  updateUser: async (userId, userData) => {
    const response = await api.put(`/api/auth/users/${userId}`, userData);
    return response.data;
  },

  deleteUser: async (userId) => {
    const response = await api.delete(`/api/auth/users/${userId}`);
    return response.data;
  },
};

export const talentAPI = {
  submitDecision: async (data) => {
    const response = await api.post('/api/talent/decisions/submit', data);
    return response.data;
  },

  getTeamMembers: async (teamId = 'team_alpha') => {
    const response = await api.get('/api/talent/team/members', { params: { team_id: teamId } });
    return response.data;
  },

  runGapAnalysis: async (data) => {
    const response = await api.post('/api/talent/gap-analysis/run', data);
    return response.data;
  },

  getLatestRecommendation: async (managerId = 'mgr_001') => {
    const response = await api.get('/api/talent/recommendations/latest', { params: { manager_id: managerId } });
    return response.data;
  },

  uploadResume: async (file, candidateId = null, roleId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    const params = {};
    if (candidateId) params.candidate_id = candidateId;
    if (roleId) params.role_id = roleId;
    const response = await api.post('/api/talent/resumes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    });
    return response.data;
  },

  getDecisionHistory: async (managerId = null, limit = 50) => {
    const response = await api.get('/api/talent/decisions/history', { params: { manager_id: managerId, limit } });
    return response.data;
  },

  getUnifiedDecisionHistory: async (managerId = 'mgr_001', limit = 100) => {
    const response = await api.get('/api/talent/decisions/unified-history', { params: { manager_id: managerId, limit } });
    return response.data;
  },

  submitManagerChoice: async (decisionId, data) => {
    const response = await api.post(`/api/talent/decisions/${decisionId}/manager-choice`, data);
    return response.data;
  },

  getReflectionQueue: async () => {
    const response = await api.get('/api/talent/reflections/queue');
    return response.data;
  },

  submitReflection: async (decisionId, data) => {
    const response = await api.post(`/api/talent/reflections/${decisionId}/submit`, data);
    return response.data;
  },

  submitManagerDecision: async (decisionId, data) => {
    const response = await api.post(`/api/talent/decisions/${decisionId}/manager-decision`, data);
    return response.data;
  },

  getAnalyticsSummary: async () => {
    const response = await api.get('/api/talent/analytics/summary');
    return response.data;
  },

  getGapAnalytics: async () => {
    const response = await api.get('/api/talent/analytics/gap-summary');
    return response.data;
  },

  getBiasAnalytics: async () => {
    const response = await api.get('/api/talent/analytics/bias-summary');
    return response.data;
  },

  getManagerPatterns: async (managerId = 'mgr_001') => {
    const response = await api.get('/api/talent/analytics/manager-patterns', { params: { manager_id: managerId } });
    return response.data;
  },

  getResumeFunnel: async () => {
    const response = await api.get('/api/talent/analytics/resume-funnel');
    return response.data;
  },

  getTrainingRecommendations: async (managerId = 'mgr_001') => {
    const response = await api.get('/api/talent/training/recommendations', { params: { manager_id: managerId } });
    return response.data;
  },
};

// Bias-reduction hiring pipeline
export const hiringAPI = {
  buildRubric: async (data) => {
    const response = await api.post('/api/hiring/jobs/rubric', data);
    return response.data;
  },

  extractResume: async (resumeId) => {
    const response = await api.post(`/api/hiring/resumes/${resumeId}/extract`);
    return response.data;
  },

  generateScorecards: async (data) => {
    const response = await api.post('/api/hiring/scorecards/generate', data);
    return response.data;
  },

  getScorecards: async (jobId) => {
    const response = await api.get(`/api/hiring/jobs/${jobId}/scorecards`);
    return response.data;
  },

  logDecision: async (data) => {
    const response = await api.post('/api/hiring/decisions', data);
    return response.data;
  },

  getDecisions: async (jobId = null) => {
    const response = await api.get('/api/hiring/decisions', { params: { job_id: jobId } });
    return response.data;
  },

  getMetrics: async (jobId = null) => {
    const response = await api.get('/api/hiring/metrics', { params: { job_id: jobId } });
    return response.data;
  },

  getWarnings: async (jobId = null) => {
    const response = await api.get('/api/hiring/warnings', { params: { job_id: jobId } });
    return response.data;
  },

  getDemographicFairness: async (jobId = null) => {
    const response = await api.get('/api/hiring/metrics/demographic-fairness', { params: { job_id: jobId } });
    return response.data;
  },

  setDemographic: async (candidateId, data) => {
    const response = await api.post(`/api/hiring/candidates/${candidateId}/demographics`, data);
    return response.data;
  },
};

export default api;
