// ===========================
// Decision Model
// ===========================
const mongoose = require('mongoose');

const decisionSchema = new mongoose.Schema({
  applicationId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'LoanApplication',
    required: true,
    index: true,
  },
  decidedBy: {
    type: mongoose.Schema.Types.Mixed, // ObjectId (officer) or string "AI"
    required: true,
  },
  aiRecommendation: {
    type: String,
    enum: ['approve', 'reject', 'review'],
  },
  finalDecision: {
    type: String,
    enum: ['approve', 'reject'],
    required: true,
  },
  overrideReason: {
    type: String,
    maxlength: 500,
  },
  decidedAt: {
    type: Date,
    default: Date.now,
  },
}, {
  timestamps: true,
});

decisionSchema.index({ decidedBy: 1, decidedAt: -1 });

module.exports = mongoose.model('Decision', decisionSchema);
