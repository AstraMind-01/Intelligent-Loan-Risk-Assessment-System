// ===========================
// Consistent API Response Formatter
// ===========================

/**
 * Send a success response
 * @param {object} res - Express response object
 * @param {string} message - Success message
 * @param {*} data - Response payload
 * @param {number} statusCode - HTTP status code (default 200)
 */
const sendSuccess = (res, message, data = null, statusCode = 200) => {
  const response = {
    success: true,
    message,
  };
  if (data !== null) response.data = data;
  return res.status(statusCode).json(response);
};

/**
 * Send an error response
 * @param {object} res - Express response object
 * @param {string} message - Error message
 * @param {number} statusCode - HTTP status code (default 500)
 * @param {*} error - Error details (dev only)
 */
const sendError = (res, message, statusCode = 500, error = null) => {
  const response = {
    success: false,
    message,
  };
  if (error && process.env.NODE_ENV === 'development') {
    response.error = typeof error === 'string' ? error : error.message;
  }
  return res.status(statusCode).json(response);
};

/**
 * Send a paginated response
 */
const sendPaginated = (res, message, data, pagination) => {
  return res.status(200).json({
    success: true,
    message,
    data,
    pagination: {
      page: pagination.page,
      limit: pagination.limit,
      total: pagination.total,
      pages: Math.ceil(pagination.total / pagination.limit),
    },
  });
};

module.exports = { sendSuccess, sendError, sendPaginated };
