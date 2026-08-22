const express = require('express');
const { protect } = require('../middlewares/authMiddleware');
const { authorize } = require('../middlewares/roleMiddleware');
const upload = require('../middlewares/uploadMiddleware');
const {
  submitApplication,
  getMyApplications,
  getApplication,
  uploadDocument,
  getRiskReport,
  downloadRiskReportPdf,
  simulateRisk
} = require('../controllers/applicantController');

const router = express.Router();

// Apply auth and role middleware to all routes in this file
router.use(protect);
router.use(authorize('applicant', 'admin')); // Admins might need access for debugging

router.route('/applications')
  .post(submitApplication)
  .get(getMyApplications);

router.route('/applications/:id')
  .get(getApplication);

router.route('/applications/:id/documents')
  .post(upload.single('document'), uploadDocument);

router.route('/applications/:id/risk-report')
  .get(getRiskReport);

router.route('/applications/:id/risk-report/pdf')
  .get(downloadRiskReportPdf);

router.route('/applications/:id/simulate')
  .post(simulateRisk);

module.exports = router;
