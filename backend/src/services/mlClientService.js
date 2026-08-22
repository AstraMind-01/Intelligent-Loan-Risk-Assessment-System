const axios = require('axios');
const { ML_SERVICE_URL } = require('../config/env');
const logger = require('../utils/logger');

// We will mock the ML service responses if the external service is not running
// so that the backend can still be tested standalone.
const IS_MOCK_MODE = true; // In production, this might be tied to an env variable

/**
 * Call ML service for risk prediction
 * @param {object} applicationData
 * @returns {object} { riskScore, riskLevel, confidence, topFactors, explanation }
 */
const callPredictRiskScore = async (applicationData) => {
  if (IS_MOCK_MODE) {
    // Generate a deterministically random score based on applicant's income for mock purposes
    const income = applicationData.financialInfo?.income || 50000;
    const loanAmount = applicationData.financialInfo?.loanAmountRequested || 10000;
    
    // Higher income relative to loan amount = lower risk
    let score = Math.floor(Math.random() * 40) + 20; // Base 20-60
    if (income / loanAmount > 5) score -= 15;
    if (income / loanAmount < 1) score += 20;
    
    // Ensure 0-100 bounds
    score = Math.max(0, Math.min(100, score));
    
    let level = 'low';
    if (score > 40) level = 'medium';
    if (score > 70) level = 'high';

    return {
      riskScore: score,
      riskLevel: level,
      confidenceScore: 0.92,
      topFactors: [
        { feature: 'Debt-to-Income Ratio', impact: score > 50 ? 'negative' : 'positive', weight: 0.45, description: 'Applicant debt relative to income.' },
        { feature: 'Credit History Length', impact: 'positive', weight: 0.25, description: 'Length of credit history is sufficient.' }
      ],
      plainLanguageExplanation: [
        `Based on the provided financial information, the applicant's risk score is ${score}.`,
        'The primary factor is the debt-to-income ratio.'
      ]
    };
  }

  try {
    const response = await axios.post(`${ML_SERVICE_URL}/predict`, applicationData);
    return response.data;
  } catch (error) {
    logger.error(`ML Service Error (/predict): ${error.message}`);
    throw new Error('Failed to get risk prediction from ML service');
  }
};

/**
 * Call ML service for fraud check
 * @param {object} applicationData
 * @returns {object} { fraudFlag, reason }
 */
const callFraudCheck = async (applicationData) => {
  if (IS_MOCK_MODE) {
    const isFraud = Math.random() > 0.95; // 5% chance of mock fraud
    return {
      fraudFlag: isFraud,
      reason: isFraud ? 'Suspicious identity pattern detected' : null
    };
  }

  try {
    const response = await axios.post(`${ML_SERVICE_URL}/fraud-check`, applicationData);
    return response.data;
  } catch (error) {
    logger.error(`ML Service Error (/fraud-check): ${error.message}`);
    // Don't block application if fraud check fails, just log it
    return { fraudFlag: false, reason: 'Fraud check service unavailable' };
  }
};

/**
 * Call ML service for What-If Simulator (no persistence)
 * @param {object} adjustedData
 */
const callSimulate = async (adjustedData) => {
  return await callPredictRiskScore(adjustedData);
};

module.exports = {
  callPredictRiskScore,
  callFraudCheck,
  callSimulate,
};
