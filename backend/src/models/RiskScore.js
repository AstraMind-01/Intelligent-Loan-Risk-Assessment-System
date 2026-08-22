// ===========================
// RiskScore Model
// ===========================
const mongoose = require('mongoose');

const topFactorSchema = new mongoose.Schema({
  feature: { type: String, required: true },
  impact: { type: String, enum: ['positive', 'negative'], required: true },
  weight: { type: Number },
  description: { type: String, required: true },
}, { _id: false });

const riskScoreSchema = new mongoose.Schema({
  applicationId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'LoanApplication',
    required: true,
    index: true,
  },
  riskScore: {
    type: Number,
    required: true,
    min: 0,
    max: 100,
  },
  riskLevel: {
    type: String,
    enum: ['low', 'medium', 'high'],
    required: true,
  },
  confidenceScore: {
    type: Number,
    min: 0,
    max: 1,
  },
  topFactors: [topFactorSchema],
  plainLanguageExplanation: [{
    type: String,
  }],
  fraudFlag: {
    type: Boolean,
    default: false,
  },
  fraudReason: {
    type: String,
  },
}, {
  timestamps: true,
});

riskScoreSchema.index({ applicationId: 1, createdAt: -1 });

module.exports = mongoose.model('RiskScore', riskScoreSchema);
