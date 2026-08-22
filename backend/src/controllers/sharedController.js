const Notification = require('../models/Notification');
const { sendSuccess, sendError } = require('../utils/responseFormatter');
const RiskScore = require('../models/RiskScore');

// @desc    Get current user's notifications
// @route   GET /api/notifications
// @access  Private (All roles)
const getNotifications = async (req, res, next) => {
  try {
    const notifications = await Notification.find({ userId: req.user._id })
      .sort('-createdAt')
      .limit(50);
    sendSuccess(res, 'Notifications retrieved', { notifications });
  } catch (error) {
    next(error);
  }
};

// @desc    Mark notification as read
// @route   PATCH /api/notifications/:id/read
// @access  Private (All roles)
const markNotificationRead = async (req, res, next) => {
  try {
    const notification = await Notification.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { read: true },
      { new: true }
    );
    
    if (!notification) return sendError(res, 'Notification not found', 404);
    sendSuccess(res, 'Notification marked read', { notification });
  } catch (error) {
    next(error);
  }
};

// @desc    Chatbot endpoint for applicant FAQs
// @route   POST /api/chat
// @access  Private (Applicant)
const handleChat = async (req, res, next) => {
  try {
    const { question, applicationId } = req.body;
    let answer = "I'm a simple AI assistant. Please contact support for more complex queries.";

    // Very basic rule-based NLP for the demo
    const q = question.toLowerCase();

    if (q.includes('rejected') || q.includes('why')) {
      if (applicationId) {
        const risk = await RiskScore.findOne({ applicationId });
        if (risk && risk.plainLanguageExplanation.length > 0) {
            answer = `Based on your application, ${risk.plainLanguageExplanation[0].toLowerCase()}`;
        } else {
            answer = "I don't have the specific risk explanation for this application yet.";
        }
      } else {
        answer = "I need your application ID to explain the decision.";
      }
    } else if (q.includes('document') || q.includes('upload')) {
        answer = "You can upload ID proofs, bank statements, and tax returns in the 'Documents' tab.";
    }

    sendSuccess(res, 'Chat response generated', { answer });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getNotifications,
  markNotificationRead,
  handleChat
};
