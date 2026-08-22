const express = require('express');
const { protect } = require('../middlewares/authMiddleware');
const { authorize } = require('../middlewares/roleMiddleware');
const {
  getOverview,
  getRiskDistribution,
  getUsers,
  updateUser,
  deleteUser,
  getModelPerformance,
  getAuditLogs,
  getSettings
} = require('../controllers/adminController');

const router = express.Router();

router.use(protect);
router.use(authorize('admin')); // Strictly admin only

router.get('/overview', getOverview);
router.get('/analytics/risk-distribution', getRiskDistribution);

router.route('/users')
  .get(getUsers);

router.route('/users/:id')
  .patch(updateUser)
  .delete(deleteUser);

router.get('/model-performance', getModelPerformance);
router.get('/audit-logs', getAuditLogs);
router.get('/settings', getSettings);

module.exports = router;
