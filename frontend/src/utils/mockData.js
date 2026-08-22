// ====================================================
// Mock Data for the Intelligent Loan Risk Assessment System
// Used to power the frontend in standalone mode (no backend)
// ====================================================

export const mockUsers = {
  applicant: { id: 'u1', name: 'Sarah Mitchell', email: 'sarah@example.com', role: 'applicant', avatar: 'SM' },
  officer: { id: 'u2', name: 'James Harrington', email: 'james@example.com', role: 'officer', avatar: 'JH' },
  admin: { id: 'u3', name: 'Victoria Sterling', email: 'victoria@example.com', role: 'admin', avatar: 'VS' },
};

export const mockApplications = [
  { id: 'LA-2024-001', applicantName: 'Sarah Mitchell', loanAmount: 250000, purpose: 'Home Purchase', status: 'Under Review', riskScore: 742, date: '2024-08-15', dti: 0.28, lti: 3.2, income: 78000, employment: 'Full-time', creditScore: 745 },
  { id: 'LA-2024-002', applicantName: 'Marcus Johnson', loanAmount: 45000, purpose: 'Auto Loan', status: 'Approved', riskScore: 810, date: '2024-08-12', dti: 0.15, lti: 0.5, income: 92000, employment: 'Full-time', creditScore: 800 },
  { id: 'LA-2024-003', applicantName: 'Elena Rodriguez', loanAmount: 180000, purpose: 'Business', status: 'Submitted', riskScore: 620, date: '2024-08-18', dti: 0.42, lti: 4.5, income: 40000, employment: 'Self-employed', creditScore: 640 },
  { id: 'LA-2024-004', applicantName: 'David Kim', loanAmount: 35000, purpose: 'Education', status: 'Approved', riskScore: 780, date: '2024-08-10', dti: 0.12, lti: 0.7, income: 50000, employment: 'Part-time', creditScore: 770 },
  { id: 'LA-2024-005', applicantName: 'Priya Sharma', loanAmount: 120000, purpose: 'Debt Consolidation', status: 'Rejected', riskScore: 480, date: '2024-08-05', dti: 0.55, lti: 2.0, income: 60000, employment: 'Contract', creditScore: 520 },
  { id: 'LA-2024-006', applicantName: 'Robert Chen', loanAmount: 500000, purpose: 'Home Purchase', status: 'Under Review', riskScore: 695, date: '2024-08-19', dti: 0.35, lti: 5.0, income: 100000, employment: 'Full-time', creditScore: 710 },
  { id: 'LA-2024-007', applicantName: 'Amanda Foster', loanAmount: 25000, purpose: 'Medical', status: 'Submitted', riskScore: 715, date: '2024-08-20', dti: 0.22, lti: 0.4, income: 65000, employment: 'Full-time', creditScore: 730 },
  { id: 'LA-2024-008', applicantName: 'Thomas Wright', loanAmount: 75000, purpose: 'Personal', status: 'Draft', riskScore: null, date: '2024-08-21', dti: 0.30, lti: 1.5, income: 50000, employment: 'Full-time', creditScore: 680 },
];

export const mockRiskExplanations = [
  { factor: 'Credit History Length', impact: 'positive', weight: 0.23, explanation: 'Your 12-year credit history demonstrates long-term financial responsibility.' },
  { factor: 'Debt-to-Income Ratio', impact: 'positive', weight: 0.19, explanation: 'Your DTI of 28% is well below the 36% threshold, indicating manageable debt levels.' },
  { factor: 'Payment History', impact: 'positive', weight: 0.25, explanation: 'Consistent on-time payments over 8+ years significantly boost your risk profile.' },
  { factor: 'Loan Amount vs Income', impact: 'negative', weight: -0.12, explanation: 'The requested loan is 3.2x your annual income, which is slightly elevated for this loan type.' },
  { factor: 'Employment Stability', impact: 'positive', weight: 0.15, explanation: '5 years at current employer signals strong job stability.' },
  { factor: 'Credit Utilization', impact: 'negative', weight: -0.08, explanation: 'Current credit utilization at 45% is above the recommended 30% threshold.' },
];

export const mockMonthlyTrends = [
  { month: 'Mar', applications: 120, approved: 85, avgScore: 690 },
  { month: 'Apr', applications: 145, approved: 102, avgScore: 705 },
  { month: 'May', applications: 132, approved: 90, avgScore: 695 },
  { month: 'Jun', applications: 168, approved: 120, avgScore: 710 },
  { month: 'Jul', applications: 155, approved: 108, avgScore: 720 },
  { month: 'Aug', applications: 180, approved: 130, avgScore: 715 },
];

export const mockRiskDistribution = [
  { name: 'Low Risk', value: 42, color: '#2ECC71' },
  { name: 'Moderate Risk', value: 35, color: '#F39C12' },
  { name: 'High Risk', value: 23, color: '#E74C3C' },
];

export const mockPurposeBreakdown = [
  { name: 'Home Purchase', count: 45 },
  { name: 'Auto Loan', count: 28 },
  { name: 'Business', count: 22 },
  { name: 'Education', count: 18 },
  { name: 'Personal', count: 15 },
  { name: 'Medical', count: 12 },
  { name: 'Debt Consolidation', count: 10 },
];

export const mockAuditLogs = [
  { id: 1, action: 'Application Approved', user: 'James Harrington', target: 'LA-2024-002', timestamp: '2024-08-12T14:30:00', details: 'Risk score: 810. Auto-approved by system.' },
  { id: 2, action: 'User Created', user: 'System', target: 'elena@example.com', timestamp: '2024-08-11T09:15:00', details: 'New applicant registration.' },
  { id: 3, action: 'Model Retrained', user: 'Victoria Sterling', target: 'risk_model_v3.2', timestamp: '2024-08-10T22:00:00', details: 'Retrained with 15,000 new samples. AUC-ROC: 0.94.' },
  { id: 4, action: 'Application Rejected', user: 'James Harrington', target: 'LA-2024-005', timestamp: '2024-08-05T16:45:00', details: 'Risk score: 480. High DTI ratio flagged.' },
  { id: 5, action: 'Settings Updated', user: 'Victoria Sterling', target: 'System Config', timestamp: '2024-08-04T11:20:00', details: 'Updated auto-approval threshold from 750 to 780.' },
  { id: 6, action: 'Fraud Flag Raised', user: 'ML Service', target: 'LA-2024-009', timestamp: '2024-08-03T08:55:00', details: 'Anomalous income pattern detected. Manual review required.' },
];

export const mockAdminUsers = [
  { id: 'u1', name: 'Sarah Mitchell', email: 'sarah@example.com', role: 'applicant', status: 'Active', lastLogin: '2024-08-21T18:30:00' },
  { id: 'u2', name: 'James Harrington', email: 'james@example.com', role: 'officer', status: 'Active', lastLogin: '2024-08-21T09:15:00' },
  { id: 'u3', name: 'Victoria Sterling', email: 'victoria@example.com', role: 'admin', status: 'Active', lastLogin: '2024-08-21T20:00:00' },
  { id: 'u4', name: 'Marcus Johnson', email: 'marcus@example.com', role: 'applicant', status: 'Active', lastLogin: '2024-08-19T14:20:00' },
  { id: 'u5', name: 'Elena Rodriguez', email: 'elena@example.com', role: 'applicant', status: 'Active', lastLogin: '2024-08-18T10:45:00' },
  { id: 'u6', name: 'David Kim', email: 'david@example.com', role: 'applicant', status: 'Suspended', lastLogin: '2024-08-01T12:00:00' },
];

export const mockModelMetrics = {
  accuracy: 0.927,
  precision: 0.912,
  recall: 0.935,
  aucRoc: 0.961,
  f1Score: 0.923,
  totalPredictions: 15420,
  avgLatency: 45,
  driftScore: 0.03,
  lastTrained: '2024-08-10T22:00:00',
  version: 'v3.2',
  history: [
    { date: 'Mar', accuracy: 0.91, aucRoc: 0.94 },
    { date: 'Apr', accuracy: 0.915, aucRoc: 0.945 },
    { date: 'May', accuracy: 0.92, aucRoc: 0.95 },
    { date: 'Jun', accuracy: 0.918, aucRoc: 0.952 },
    { date: 'Jul', accuracy: 0.925, aucRoc: 0.958 },
    { date: 'Aug', accuracy: 0.927, aucRoc: 0.961 },
  ],
};

export const mockNotifications = [
  { id: 1, title: 'Application Approved', message: 'Your loan application LA-2024-002 has been approved.', time: '2024-08-21T14:30:00', read: false },
  { id: 2, title: 'Document Required', message: 'Please upload your latest bank statement for LA-2024-001.', time: '2024-08-20T09:15:00', read: false },
  { id: 3, title: 'Risk Report Ready', message: 'Your risk assessment report is now available for review.', time: '2024-08-19T16:00:00', read: true },
];

export const mockChatMessages = [
  { id: 1, sender: 'bot', text: 'Welcome to Loan Risk Assessment Support! I can help you with application status, document requirements, or general questions about the risk assessment process. How can I assist you today?' },
];
