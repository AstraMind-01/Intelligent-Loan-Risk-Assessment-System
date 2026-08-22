export const ROLES = {
  APPLICANT: 'applicant',
  OFFICER: 'officer',
  ADMIN: 'admin',
};

export const LOAN_STATUS = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  DISBURSED: 'Disbursed',
};

export const RISK_LEVELS = {
  LOW: { label: 'Low Risk', color: 'emerald', min: 700, max: 850 },
  MODERATE: { label: 'Moderate Risk', color: 'amber', min: 550, max: 699 },
  HIGH: { label: 'High Risk', color: 'ruby', min: 0, max: 549 },
};

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export const LOAN_PURPOSES = [
  'Home Purchase', 'Auto Loan', 'Education', 'Personal', 'Business', 'Debt Consolidation', 'Medical', 'Other'
];

export const EMPLOYMENT_TYPES = [
  'Full-time', 'Part-time', 'Self-employed', 'Contract', 'Retired', 'Unemployed'
];
