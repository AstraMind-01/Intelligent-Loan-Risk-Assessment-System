const express = require('express');
const { protect } = require('../middlewares/authMiddleware');
const { authorize } = require('../middlewares/roleMiddleware');
const { getNotifications, markNotificationRead, handleChat } = require('../controllers/sharedController');

const router = express.Router();

router.use(protect); // Shared routes require authentication

router.get('/notifications', getNotifications);
router.patch('/notifications/:id/read', markNotificationRead);

// Chat is mostly for applicants
router.post('/chat', authorize('applicant'), handleChat);

module.exports = router;
