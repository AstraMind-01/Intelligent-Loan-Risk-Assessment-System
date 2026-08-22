// ===========================
// ModelMetric Model
// ===========================
const mongoose = require('mongoose');

const modelMetricSchema = new mongoose.Schema({
  date: {
    type: Date,
    required: true,
    index: true,
  },
  accuracy: {
    type: Number,
    min: 0,
    max: 1,
  },
  aucRoc: {
    type: Number,
    min: 0,
    max: 1,
  },
  precision: Number,
  recall: Number,
  f1Score: Number,
  driftScore: {
    type: Number,
    min: 0,
  },
  agreementRate: {
    type: Number, // % of officer decisions that agree with AI recommendation
    min: 0,
    max: 1,
  },
  totalPredictions: Number,
  avgLatencyMs: Number,
  modelVersion: String,
}, {
  timestamps: true,
});

module.exports = mongoose.model('ModelMetric', modelMetricSchema);
