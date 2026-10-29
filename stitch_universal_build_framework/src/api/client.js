import axios from 'axios';

// Single source of truth for the backend URL.
// In dev, defaults to local backend. In production (Vercel), set VITE_API_BASE_URL
// to the Render backend URL (e.g. https://blocktrace-v2.onrender.com).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// ==================== Workspace ====================
// Each browser gets its own private workspace (graph + saved cases) on the shared
// backend. The ID is random, kept in localStorage, and sent with every request.
const WORKSPACE_KEY = 'bt_workspace_id';

const newWorkspaceId = () =>
  (window.crypto?.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`);

let workspaceId;
export const getWorkspaceId = () => {
  if (workspaceId) return workspaceId;
  try {
    workspaceId = localStorage.getItem(WORKSPACE_KEY);
    if (!workspaceId) {
      workspaceId = newWorkspaceId();
      localStorage.setItem(WORKSPACE_KEY, workspaceId);
    }
  } catch {
    // Storage blocked (private mode etc.): keep a per-tab workspace instead.
    workspaceId = workspaceId || newWorkspaceId();
  }
  return workspaceId;
};

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  config.headers['X-Workspace-Id'] = getWorkspaceId();
  return config;
});

// ==================== Health & public endpoints ====================
export const checkHealth = async () => {
  const { data } = await axios.get(`${API_BASE_URL}/health`);
  return data;
};

export const checkSanctionsPublic = async (address) => {
  const { data } = await axios.get(`${API_BASE_URL}/sanctions/check`, {
    params: { address },
  });
  return data;
};

export const fetchContracts = async () => {
  const { data } = await axios.get(`${API_BASE_URL}/contracts`);
  return data;
};

// Helper for formatting and displaying error messages
export const getErrorMessage = (error) => {
  if (error?.response?.data?.detail) {
    if (typeof error.response.data.detail === 'string') {
      return error.response.data.detail;
    }
    if (Array.isArray(error.response.data.detail)) {
      return error.response.data.detail.map(d => d.msg || d).join(', ');
    }
    return JSON.stringify(error.response.data.detail);
  }
  return error.message || 'An unexpected error occurred';
};

// Chains & Curated Cases
export const fetchChains = async () => {
  const { data } = await api.get('/chains');
  return data.chains || [];
};

export const fetchCuratedCases = async () => {
  const { data } = await api.get('/curated-cases');
  return data.cases || [];
};

export const loadCuratedCase = async (caseName) => {
  const encodedName = encodeURIComponent(caseName);
  const { data } = await api.post(`/curated-cases/${encodedName}/load`);
  return data;
};

// Investigation & Tracing
export const expandWallet = async ({ wallet, hops = 2, tx_per_wallet = 15, chain = 'Ethereum' }) => {
  const { data } = await api.post('/expand', {
    wallet,
    hops: Number(hops),
    tx_per_wallet: Number(tx_per_wallet),
    chain,
  });
  return data;
};

export const findPath = async ({ source, destination, max_hops = 4, tx_per_wallet = 15, chain = 'Ethereum' }) => {
  const { data } = await api.post('/path', {
    source,
    destination,
    max_hops: Number(max_hops),
    tx_per_wallet: Number(tx_per_wallet),
    chain,
  });
  return data;
};

export const fetchGraphData = async () => {
  const { data } = await api.get('/graph');
  return data.edges || [];
};

export const fetchSummary = async () => {
  const { data } = await api.get('/summary');
  return data;
};

export const clearGraph = async () => {
  const { data } = await api.post('/clear');
  return data;
};

// Findings & Detection Endpoints
export const fetchNarrative = async (startWallet) => {
  const params = startWallet ? { start_wallet: startWallet } : {};
  const { data } = await api.get('/narrative', { params });
  return data.paragraphs || [];
};

export const fetchSanctions = async () => {
  const { data } = await api.get('/sanctions');
  return data.matches || [];
};

export const fetchRiskOverview = async () => {
  const { data } = await api.get('/risk');
  return data.results || [];
};

export const fetchHubDetections = async () => {
  const { data } = await api.get('/detections/hub');
  return data.results || [];
};

export const fetchFanoutDetections = async () => {
  const { data } = await api.get('/detections/fanout');
  return data.results || [];
};

export const fetchPeelDetections = async () => {
  const { data } = await api.get('/detections/peel-chains');
  return data.results || [];
};

export const fetchRoundDetections = async () => {
  const { data } = await api.get('/detections/round-number');
  return data.results || [];
};

export const fetchCircularDetections = async () => {
  const { data } = await api.get('/detections/circular');
  return data.results || [];
};

// Certificates
export const issueCertificate = async (startWallet) => {
  const body = startWallet ? { start_wallet: startWallet } : {};
  const { data } = await api.post('/certificate', body);
  return data;
};

export const verifyCertificate = async ({ certificate_hash, previous_hash, payload }) => {
  const { data } = await api.post('/certificate/verify', {
    certificate_hash,
    previous_hash,
    payload,
  });
  return data;
};

// Cases & Reports
export const fetchSavedCases = async () => {
  const { data } = await api.get('/cases');
  return data.cases || [];
};

export const saveCase = async ({ name, case_number, start_wallet, anchor_on_chain = true }) => {
  const { data } = await api.post('/cases', {
    name,
    case_number: case_number ? case_number.trim() : null,
    start_wallet: start_wallet || null,
    anchor_on_chain: !!anchor_on_chain,
  });
  return data;
};

export const retryAnchorCase = async (caseNumber) => {
  const encodedName = encodeURIComponent(caseNumber);
  const { data } = await api.post(`/cases/${encodedName}/anchor`);
  return data;
};

export const reanchorCase = async (caseNumber) => {
  const encodedName = encodeURIComponent(caseNumber);
  const { data } = await api.post(`/cases/${encodedName}/reanchor`);
  return data;
};

export const verifyCaseOnChain = async (caseNumber) => {
  const encodedName = encodeURIComponent(caseNumber);
  const { data } = await api.get(`/cases/${encodedName}/verify`);
  return data;
};

export const loadSavedCase = async (name) => {
  const encodedName = encodeURIComponent(name);
  const { data } = await api.post(`/cases/${encodedName}/load`);
  return data;
};

export const deleteSavedCase = async (name) => {
  const encodedName = encodeURIComponent(name);
  const { data } = await api.delete(`/cases/${encodedName}`);
  return data;
};

export const getReportUrl = (startWallet) => {
  // Direct link to the backend for browser download (not through axios), so the
  // workspace goes in the query string instead of a header.
  const params = new URLSearchParams({ ws: getWorkspaceId() });
  if (startWallet) params.set('start_wallet', startWallet);
  return `${API_BASE_URL}/report?${params}`;
};

export const publishReport = async (startWallet) => {
  const body = startWallet ? { start_wallet: startWallet } : {};
  const { data } = await api.post('/report/publish', body);
  return data;
};

export const verifyReport = async ({ file, investigationHash }) => {
  const formData = new FormData();
  formData.append('file', file);
  if (investigationHash && investigationHash.trim()) {
    formData.append('investigation_hash', investigationHash.trim());
  }
  const { data } = await api.post('/report/verify', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export default api;
