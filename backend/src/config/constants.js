// ===========================
// Application Constants
// ===========================
module.exports = {
  ROLES: {
    APPLICANT: 'applicant',
    OFFICER: 'officer',
    ADMIN: 'admin',
  },

  APPLICATION_STATUS: {
    SUBMITTED: 'submitted',
    UNDER_REVIEW: 'under_review',
    APPROVED: 'approved',
    REJECTED: 'rejected',
  },

  RISK_LEVELS: {
    LOW: 'low',
    MEDIUM: 'medium',
    HIGH: 'high',
  },

  DECISION_TYPES: {
    APPROVE: 'approve',
    REJECT: 'reject',
    REVIEW: 'review',
  },

  ACTOR_TYPES: {
    AI: 'AI',
    OFFICER: 'Officer',
    ADMIN: 'Admin',
  },

  NOTIFICATION_TYPES: {
    STATUS_UPDATE: 'status_update',
    SYSTEM: 'system',
  },

  EMPLOYMENT_TYPES: [
    'full_time',
    'part_time',
    'self_employed',
    'contract',
    'retired',
    'unemployed',
  ],

  DOCUMENT_TYPES: [
    'id_proof',
    'income_proof',
    'bank_statement',
    'tax_return',
    'address_proof',
    'other',
  ],

  ALLOWED_FILE_TYPES: [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/jpg',
  ],

  PAGINATION: {
    DEFAULT_PAGE: 1,
    DEFAULT_LIMIT: 20,
    MAX_LIMIT: 100,
  },
};
