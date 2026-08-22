const AuditLog = require('../models/AuditLog');
const logger = require('../utils/logger');

/**
 * Log an action to the AuditLog collection
 * @param {object} param0 
 * @param {string} param0.actorType - 'AI', 'Officer', 'Admin', 'System'
 * @param {string} param0.actorId - ObjectId of the user, or 'AI'/'System'
 * @param {string} param0.applicationId - Optional ObjectId of the application
 * @param {string} param0.action - Description of the action
 * @param {string} param0.details - Additional details
 * @param {number} param0.aiScore - The AI risk score at the time (if applicable)
 * @param {string} param0.overrideReason - Reason for overriding AI (if applicable)
 * @param {object} param0.metadata - Any additional data
 */
const logAction = async ({
  actorType,
  actorId,
  applicationId,
  action,
  details,
  aiScore,
  overrideReason,
  metadata
}) => {
  try {
    await AuditLog.create({
      actorType,
      actorId,
      applicationId,
      action,
      details,
      aiScore,
      overrideReason,
      metadata
    });
  } catch (error) {
    // We don't want audit log failures to crash the main transaction, just log it
    logger.error(`Failed to create audit log: ${error.message}`);
  }
};

module.exports = { logAction };
