// ===========================
// LoanApplication Model
// ===========================
const mongoose = require('mongoose');
const { APPLICATION_STATUS, EMPLOYMENT_TYPES, DOCUMENT_TYPES } = require('../config/constants');

const documentSubSchema = new mongoose.Schema({
  type: {
    type: String,
    enum: DOCUMENT_TYPES,
    required: true,
  },
  fileUrl: {
    type: String,
    required: true,
  },
  originalName: String,
  mimeType: String,
  size: Number,
  verified: {
    type: Boolean,
    default: false,
  },
  uploadedAt: {
    type: Date,
    default: Date.now,
  },
}, { _id: true });

const loanApplicationSchema = new mongoose.Schema({
  applicantId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: [true, 'Applicant ID is required'],
    index: true,
  },
  personalInfo: {
    age: {
      type: Number,
      min: [18, 'Applicant must be at least 18'],
      max: [100, 'Invalid age'],
    },
    maritalStatus: {
      type: String,
      enum: ['single', 'married', 'divorced', 'widowed'],
    },
    employmentType: {
      type: String,
      enum: EMPLOYMENT_TYPES,
    },
    dependents: {
      type: Number,
      min: 0,
      default: 0,
    },
    education: {
      type: String,
      enum: ['high_school', 'bachelors', 'masters', 'doctorate', 'other'],
    },
  },
  financialInfo: {
    income: {
      type: Number,
      required: [true, 'Income is required'],
      min: [0, 'Income cannot be negative'],
    },
    existingDebts: {
      type: Number,
      default: 0,
      min: 0,
    },
    loanAmountRequested: {
      type: Number,
      required: [true, 'Loan amount is required'],
      min: [100, 'Minimum loan amount is $100'],
    },
    tenure: {
      type: Number,
      required: [true, 'Loan tenure is required'],
      min: [1, 'Minimum tenure is 1 month'],
      max: [360, 'Maximum tenure is 360 months'],
    },
    creditScore: {
      type: Number,
      min: 300,
      max: 850,
    },
    purpose: {
      type: String,
      enum: ['home_purchase', 'auto_loan', 'education', 'personal', 'business', 'debt_consolidation', 'medical', 'other'],
    },
  },
  documents: [documentSubSchema],
  status: {
    type: String,
    enum: Object.values(APPLICATION_STATUS),
    default: APPLICATION_STATUS.SUBMITTED,
    index: true,
  },
  notes: {
    type: String,
    maxlength: 1000,
  },
}, {
  timestamps: true,
});

// Indexes for query performance
loanApplicationSchema.index({ status: 1, createdAt: -1 });
loanApplicationSchema.index({ applicantId: 1, createdAt: -1 });

module.exports = mongoose.model('LoanApplication', loanApplicationSchema);
