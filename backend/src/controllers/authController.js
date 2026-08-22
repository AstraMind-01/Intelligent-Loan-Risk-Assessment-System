const User = require('../models/User');
const jwt = require('jsonwebtoken');
const { JWT_SECRET, JWT_EXPIRE } = require('../config/env');
const { sendSuccess, sendError } = require('../utils/responseFormatter');

// Generate JWT
const generateToken = (id) => {
  return jwt.sign({ id }, JWT_SECRET, {
    expiresIn: JWT_EXPIRE,
  });
};

// @desc    Register a new user
// @route   POST /api/auth/register
// @access  Public
const register = async (req, res, next) => {
  try {
    const { name, email, password, role, phone } = req.body;

    // Prevent public creation of admin users
    if (role === 'admin') {
      return sendError(res, 'Cannot register as admin', 403);
    }

    const userExists = await User.findOne({ email });
    if (userExists) {
      return sendError(res, 'User already exists', 400);
    }

    const user = await User.create({
      name,
      email,
      password,
      role: role || 'applicant',
      phone,
    });

    const token = generateToken(user._id);

    sendSuccess(res, 'User registered successfully', {
      user,
      token,
    }, 201);
  } catch (error) {
    next(error);
  }
};

// @desc    Login user & get token
// @route   POST /api/auth/login
// @access  Public
const login = async (req, res, next) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return sendError(res, 'Please provide email and password', 400);
    }

    const user = await User.findOne({ email }).select('+password');

    if (!user || !(await user.comparePassword(password))) {
      return sendError(res, 'Invalid credentials', 401);
    }

    if (user.status !== 'active') {
      return sendError(res, 'User account is suspended', 403);
    }

    const token = generateToken(user._id);

    sendSuccess(res, 'Login successful', {
      user: {
        _id: user._id,
        name: user.name,
        email: user.email,
        role: user.role,
      },
      token,
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Get current logged in user
// @route   GET /api/auth/me
// @access  Private
const getMe = async (req, res, next) => {
  try {
    const user = await User.findById(req.user.id);
    sendSuccess(res, 'User profile retrieved', { user });
  } catch (error) {
    next(error);
  }
};

// @desc    Logout user / clear cookie if we were using cookies
// @route   POST /api/auth/logout
// @access  Private
const logout = async (req, res, next) => {
  try {
    sendSuccess(res, 'Logged out successfully', {});
  } catch (error) {
    next(error);
  }
};

module.exports = {
  register,
  login,
  getMe,
  logout,
};
