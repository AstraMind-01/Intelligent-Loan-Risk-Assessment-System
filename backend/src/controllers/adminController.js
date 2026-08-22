const LoanApplication = require('../models/LoanApplication');
const RiskScore = require('../models/RiskScore');
const User = require('../models/User');
const AuditLog = require('../models/AuditLog');
const ModelMetric = require('../models/ModelMetric');
const { sendSuccess, sendError, sendPaginated } = require('../utils/responseFormatter');
const { APPLICATION_STATUS } = require('../config/constants');
const { logAction } = require('../services/auditService');

// @desc    Get top-level KPIs
// @route   GET /api/admin/overview
// @access  Private (Admin)
const getOverview = async (req, res, next) => {
  try {
    const totalApps = await LoanApplication.countDocuments();
    const approvedApps = await LoanApplication.countDocuments({ status: APPLICATION_STATUS.APPROVED });
    const rejectedApps = await LoanApplication.countDocuments({ status: APPLICATION_STATUS.REJECTED });
    
    // Aggregation for avg risk score
    const avgRiskResult = await RiskScore.aggregate([
      { $group: { _id: null, avgScore: { $avg: "$riskScore" } } }
    ]);
    const avgRiskScore = avgRiskResult.length > 0 ? Math.round(avgRiskResult[0].avgScore) : 0;

    sendSuccess(res, 'Overview metrics retrieved', {
      totalApplications: totalApps,
      approvalRate: totalApps ? (approvedApps / totalApps) : 0,
      rejectionRate: totalApps ? (rejectedApps / totalApps) : 0,
      avgRiskScore
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Get risk distribution analytics
// @route   GET /api/admin/analytics/risk-distribution
// @access  Private (Admin)
const getRiskDistribution = async (req, res, next) => {
  try {
    const distribution = await RiskScore.aggregate([
      { $group: { _id: "$riskLevel", count: { $sum: 1 } } }
    ]);
    
    const formatted = { low: 0, medium: 0, high: 0 };
    distribution.forEach(d => {
        if(d._id) formatted[d._id] = d.count;
    });

    sendSuccess(res, 'Risk distribution retrieved', { distribution: formatted });
  } catch (error) {
    next(error);
  }
};

// @desc    Get all users (for management)
// @route   GET /api/admin/users
// @access  Private (Admin)
const getUsers = async (req, res, next) => {
  try {
    const { role, status } = req.query;
    const query = {};
    if (role) query.role = role;
    if (status) query.status = status;

    const users = await User.find(query).select('-password').sort('-createdAt');
    sendSuccess(res, 'Users retrieved', { users });
  } catch (error) {
    next(error);
  }
};

// @desc    Update a user
// @route   PATCH /api/admin/users/:id
// @access  Private (Admin)
const updateUser = async (req, res, next) => {
  try {
    const { status, role } = req.body;
    
    // Don't allow changing one's own role/status from this endpoint to prevent accidental lockouts
    if (req.user._id.toString() === req.params.id) {
        return sendError(res, 'Cannot modify your own user account from this endpoint', 400);
    }

    const user = await User.findByIdAndUpdate(
        req.params.id, 
        { status, role },
        { new: true, runValidators: true }
    ).select('-password');

    if (!user) return sendError(res, 'User not found', 404);

    await logAction({
        actorType: 'Admin',
        actorId: req.user._id,
        action: 'Updated User Account',
        details: `Admin updated user ${user.email}. Role: ${role}, Status: ${status}`
    });

    sendSuccess(res, 'User updated', { user });
  } catch (error) {
    next(error);
  }
};

// @desc    Delete a user
// @route   DELETE /api/admin/users/:id
// @access  Private (Admin)
const deleteUser = async (req, res, next) => {
  try {
    if (req.user._id.toString() === req.params.id) {
        return sendError(res, 'Cannot delete your own admin account', 400);
    }

    const user = await User.findByIdAndDelete(req.params.id);
    if (!user) return sendError(res, 'User not found', 404);

    await logAction({
        actorType: 'Admin',
        actorId: req.user._id,
        action: 'Deleted User Account',
        details: `Admin deleted user ${user.email}`
    });

    sendSuccess(res, 'User deleted');
  } catch (error) {
    next(error);
  }
};

// @desc    Get model performance metrics
// @route   GET /api/admin/model-performance
// @access  Private (Admin)
const getModelPerformance = async (req, res, next) => {
  try {
    const metrics = await ModelMetric.find().sort('date').limit(30);
    sendSuccess(res, 'Model metrics retrieved', { metrics });
  } catch (error) {
    next(error);
  }
};

// @desc    Get audit logs with pagination
// @route   GET /api/admin/audit-logs
// @access  Private (Admin)
const getAuditLogs = async (req, res, next) => {
  try {
    const page = parseInt(req.query.page, 10) || 1;
    const limit = parseInt(req.query.limit, 10) || 20;
    const skip = (page - 1) * limit;

    const query = {};
    if (req.query.actorType) query.actorType = req.query.actorType;
    if (req.query.action) query.action = { $regex: req.query.action, $options: 'i' };

    const logs = await AuditLog.find(query).sort('-timestamp').skip(skip).limit(limit);
    const total = await AuditLog.countDocuments(query);

    sendPaginated(res, 'Audit logs retrieved', logs, { page, limit, total });
  } catch (error) {
    next(error);
  }
};

// @desc    Get system settings (Mocked for now since settings aren't in DB yet)
// @route   GET /api/admin/settings
// @access  Private (Admin)
const getSettings = async (req, res, next) => {
    try {
        sendSuccess(res, 'Settings retrieved', {
            autoApproveThreshold: process.env.AUTO_APPROVE_THRESHOLD || 25,
            autoRejectThreshold: process.env.AUTO_REJECT_THRESHOLD || 75
        });
    } catch(err) {
        next(err);
    }
}

module.exports = {
  getOverview,
  getRiskDistribution,
  getUsers,
  updateUser,
  deleteUser,
  getModelPerformance,
  getAuditLogs,
  getSettings
};
