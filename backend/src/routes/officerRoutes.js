const express = require('express');
const { protect } = require('../middlewares/authMiddleware');
const { authorize } = require('../middlewares/roleMiddleware');
const {
  getDashboardStats,
  getQueue,
  getApplicationAnalysis,
  makeDecision,
  getDecisionHistory
} = require('../controllers/officerController');

const router = express.Router();

router.use(protect);
router.use(authorize('officer', 'admin'));

router.get('/dashboard', getDashboardStats);
router.get('/queue', getQueue);
router.get('/applications/:id/analysis', getApplicationAnalysis);
router.post('/applications/:id/decision', makeDecision);
router.get('/history', getDecisionHistory);

module.exports = router;
