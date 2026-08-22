const app = require('./src/app');
const connectDB = require('./src/config/db');
const { PORT, NODE_ENV } = require('./src/config/env');
const logger = require('./src/utils/logger');

// Connect to Database
connectDB();

const server = app.listen(PORT, () => {
  logger.info(`Server running in ${NODE_ENV} mode on port ${PORT}`);
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (err, promise) => {
  logger.error(`Unhandled Rejection: ${err.message}`);
  // Close server & exit process
  server.close(() => process.exit(1));
});
