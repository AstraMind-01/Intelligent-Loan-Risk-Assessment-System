const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const path = require('path');

const { FRONTEND_URL, NODE_ENV } = require('./config/env');
const { errorHandler, notFound } = require('./middlewares/errorHandler');

// Route imports
const authRoutes = require('./routes/authRoutes');
const applicantRoutes = require('./routes/applicantRoutes');
const officerRoutes = require('./routes/officerRoutes');
const adminRoutes = require('./routes/adminRoutes');
const sharedRoutes = require('./routes/sharedRoutes');

const app = express();

// ===========================
// Middlewares
// ===========================

// Security Headers
app.use(helmet());

// CORS
app.use(cors({
  origin: FRONTEND_URL || 'http://localhost:3000',
  credentials: true,
}));

// Body Parsers
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Static folder for uploaded documents
app.use('/uploads', express.static(path.join(__dirname, '../../uploads')));

// Logging
if (NODE_ENV === 'development') {
  app.use(morgan('dev'));
}

// Rate Limiting (apply to all requests, tighten for auth in production)
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  message: { success: false, message: 'Too many requests, please try again later.' }
});
app.use('/api', limiter);

// ===========================
// Routes
// ===========================
app.get('/api/health', (req, res) => {
  res.status(200).json({ success: true, message: 'API is running' });
});

app.use('/api/auth', authRoutes);
app.use('/api/applicant', applicantRoutes);
app.use('/api/officer', officerRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api', sharedRoutes); // shared routes

// ===========================
// Error Handling
// ===========================
app.use(notFound);
app.use(errorHandler);

module.exports = app;
