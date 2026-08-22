const Notification = require('../models/Notification');
const logger = require('../utils/logger');

/**
 * Create a new notification for a user
 * @param {string} userId - User's ObjectId
 * @param {string} title - Notification title
 * @param {string} message - Notification message body
 * @param {string} type - 'status_update' or 'system'
 */
const createNotification = async (userId, title, message, type = 'status_update') => {
  try {
    const notification = await Notification.create({
      userId,
      title,
      message,
      type
    });
    
    // In a real system, you might also trigger WebSocket events or Emails here
    // sendEmail(user.email, title, message);

    return notification;
  } catch (error) {
    logger.error(`Failed to create notification: ${error.message}`);
  }
};

module.exports = { createNotification };
