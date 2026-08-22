const LoanApplication = require('../models/LoanApplication');
const RiskScore = require('../models/RiskScore');
const Decision = require('../models/Decision');
const { sendSuccess, sendError } = require('../utils/responseFormatter');
const { logAction } = require('../services/auditService');
const { createNotification } = require('../services/notificationService');
const { APPLICATION_STATUS } = require('../config/constants');

// @desc    Get officer dashboard summary
// @route   GET /api/officer/dashboard
// @access  Private (Officer)
const getDashboardStats = async (req, res, next) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [pendingReviews, approvedToday, rejectedToday, totalDecisionsByOfficer] = await Promise.all([
      LoanApplication.countDocuments({ status: APPLICATION_STATUS.UNDER_REVIEW }),
      Decision.countDocuments({ finalDecision: 'approve', decidedAt: { $gte: today } }),
      Decision.countDocuments({ finalDecision: 'reject', decidedAt: { $gte: today } }),
      Decision.countDocuments({ decidedBy: req.user._id })
    ]);

    sendSuccess(res, 'Dashboard stats retrieved', {
      pendingReviews,
      approvedToday,
      rejectedToday,
      totalDecisionsByOfficer
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Get queue of applications pending review
// @route   GET /api/officer/queue
// @access  Private (Officer)
const getQueue = async (req, res, next) => {
  try {
    const { riskLevel, fraudFlag } = req.query;
    
    // First find applications under review
    let appsQuery = { status: APPLICATION_STATUS.UNDER_REVIEW };
    const applications = await LoanApplication.find(appsQuery)
      .populate('applicantId', 'name email')
      .sort('createdAt')
      .lean();

    // If filtering by risk data, we need to fetch corresponding RiskScores
    let filteredApps = applications;
    if (riskLevel || fraudFlag !== undefined) {
      const appIds = applications.map(a => a._id);
      
      let riskQuery = { applicationId: { $in: appIds } };
      if (riskLevel) riskQuery.riskLevel = riskLevel;
      if (fraudFlag !== undefined) riskQuery.fraudFlag = fraudFlag === 'true';

      const riskScores = await RiskScore.find(riskQuery).select('applicationId').lean();
      const validAppIds = riskScores.map(rs => rs.applicationId.toString());
      
      filteredApps = applications.filter(a => validAppIds.includes(a._id.toString()));
    }

    sendSuccess(res, 'Queue retrieved', { applications: filteredApps });
  } catch (error) {
    next(error);
  }
};

// @desc    Get full analysis for a specific application
// @route   GET /api/officer/applications/:id/analysis
// @access  Private (Officer)
const getApplicationAnalysis = async (req, res, next) => {
  try {
    const application = await LoanApplication.findById(req.params.id)
      .populate('applicantId', 'name email phone');

    if (!application) return sendError(res, 'Application not found', 404);

    const riskScore = await RiskScore.findOne({ applicationId: application._id });
    const pastDecisions = await Decision.find({ applicationId: application._id }).sort('-decidedAt');

    sendSuccess(res, 'Analysis retrieved', {
      application,
      riskScore,
      history: pastDecisions
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Make a manual decision on an application
// @route   POST /api/officer/applications/:id/decision
// @access  Private (Officer)
const makeDecision = async (req, res, next) => {
  try {
    const { decision, overrideReason } = req.body;
    
    if (!['approve', 'reject', 'review'].includes(decision)) {
      return sendError(res, 'Invalid decision', 400);
    }

    const application = await LoanApplication.findById(req.params.id);
    if (!application) return sendError(res, 'Application not found', 404);

    const riskScore = await RiskScore.findOne({ applicationId: application._id });
    
    // Check if officer is disagreeing with AI
    let isOverride = false;
    const aiRec = riskScore ? (riskScore.riskScore > 50 ? 'reject' : 'approve') : null;
    
    if (aiRec && decision !== aiRec && decision !== 'review') {
        isOverride = true;
        if (!overrideReason) {
            return sendError(res, 'Override reason is required when disagreeing with AI recommendation', 400);
        }
    }

    // Save decision
    await Decision.create({
      applicationId: application._id,
      decidedBy: req.user._id,
      aiRecommendation: aiRec || 'review',
      finalDecision: decision,
      overrideReason: isOverride ? overrideReason : null,
    });

    // Update application status
    application.status = decision === 'approve' ? APPLICATION_STATUS.APPROVED : 
                         decision === 'reject' ? APPLICATION_STATUS.REJECTED : 
                         APPLICATION_STATUS.UNDER_REVIEW;
    await application.save();

    // Audit log
    await logAction({
      actorType: 'Officer',
      actorId: req.user._id,
      applicationId: application._id,
      action: `Officer ${decision} application`,
      aiScore: riskScore?.riskScore,
      overrideReason: isOverride ? overrideReason : null,
      details: `Officer manually set status to ${decision}`
    });

    // Notify applicant
    if (decision !== 'review') {
      await createNotification(
        application.applicantId,
        `Application ${decision.charAt(0).toUpperCase() + decision.slice(1)}`,
        `Your loan application has been manually reviewed and ${decision}ed.`,
        'status_update'
      );
    }

    sendSuccess(res, `Application ${decision}ed successfully`, { application });
  } catch (error) {
    next(error);
  }
};

// @desc    Get decision history for the current officer
// @route   GET /api/officer/history
// @access  Private (Officer)
const getDecisionHistory = async (req, res, next) => {
  try {
    const history = await Decision.find({ decidedBy: req.user._id })
      .populate({
          path: 'applicationId',
          select: 'applicantId financialInfo.loanAmountRequested createdAt',
          populate: { path: 'applicantId', select: 'name' }
      })
      .sort('-decidedAt')
      .limit(50);
      
    sendSuccess(res, 'Decision history retrieved', { history });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getDashboardStats,
  getQueue,
  getApplicationAnalysis,
  makeDecision,
  getDecisionHistory
};
