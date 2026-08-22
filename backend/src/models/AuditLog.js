// ===========================
// AuditLog Model
// ===========================
const mongoose = require('mongoose');

const auditLogSchema = new mongoose.Schema({
  actorType: {
    type: String,
    enum: ['AI', 'Officer', 'Admin', 'System'],
    required: true,
  },
  actorId: {
    type: mongoose.Schema.Types.Mixed, // ObjectId or null for AI/System
  },
  applicationId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'LoanApplication',
    index: true,
  },
  action: {
    type: String,
    required: true,
    maxlength: 200,
  },
  details: {
    type: String,
    maxlength: 1000,
  },
  aiScore: {
    type: Number,
  },
  overrideReason: {
    type: String,
  },
  metadata: {
    type: mongoose.Schema.Types.Mixed, // Flexible extra data
  },
  timestamp: {
    type: Date,
    default: Date.now,
    index: true,
  },
});

auditLogSchema.index({ timestamp: -1 });
auditLogSchema.index({ actorType: 1, timestamp: -1 });

module.exports = mongoose.model('AuditLog', auditLogSchema);
