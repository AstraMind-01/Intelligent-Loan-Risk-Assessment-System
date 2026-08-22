const { AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD } = require('../config/env');
const { APPLICATION_STATUS, DECISION_TYPES } = require('../config/constants');
const Decision = require('../models/Decision');
const { logAction } = require('./auditService');
const { createNotification } = require('./notificationService');

/**
 * Evaluates the risk score and applies auto-decision logic
 * @param {object} application - LoanApplication document
 * @param {object} riskData - RiskScore data
 * @returns {string} - The new status of the application
 */
const evaluateApplication = async (application, riskData) => {
  let newStatus = APPLICATION_STATUS.UNDER_REVIEW;
  let aiRecommendation = DECISION_TYPES.REVIEW;
  let finalDecision = null;

  // Auto-decision logic based on thresholds
  if (riskData.riskScore <= AUTO_APPROVE_THRESHOLD && !riskData.fraudFlag) {
    newStatus = APPLICATION_STATUS.APPROVED;
    aiRecommendation = DECISION_TYPES.APPROVE;
    finalDecision = DECISION_TYPES.APPROVE;
  } else if (riskData.riskScore >= AUTO_REJECT_THRESHOLD || riskData.fraudFlag) {
    newStatus = APPLICATION_STATUS.REJECTED;
    aiRecommendation = DECISION_TYPES.REJECT;
    finalDecision = DECISION_TYPES.REJECT;
  }

  // If auto-decided, create a Decision record
  if (finalDecision) {
    await Decision.create({
      applicationId: application._id,
      decidedBy: 'AI',
      aiRecommendation,
      finalDecision,
    });

    await logAction({
      actorType: 'AI',
      actorId: 'AI',
      applicationId: application._id,
      action: `Auto-${finalDecision} application`,
      aiScore: riskData.riskScore,
      details: `Application auto-${finalDecision} based on score ${riskData.riskScore}. Fraud flag: ${riskData.fraudFlag}`
    });

    // Notify applicant
    await createNotification(
      application.applicantId,
      `Application ${finalDecision.charAt(0).toUpperCase() + finalDecision.slice(1)}`,
      `Your loan application has been ${finalDecision}.`,
      'status_update'
    );
  }

  return newStatus;
};

module.exports = { evaluateApplication };
