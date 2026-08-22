import React from 'react';
import { mockModelMetrics } from '../../utils/mockData';
import TrendLineChart from '../../components/charts/TrendLineChart';
import { Activity, Cpu, Clock, Zap, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';

export default function ModelMonitor() {
  const m = mockModelMetrics;

  const metricCards = [
    { label: 'Accuracy', value: `${(m.accuracy * 100).toFixed(1)}%`, icon: <CheckCircle size={20} />, color: '#2ECC71', bg: 'rgba(46,204,113,0.12)' },
    { label: 'Precision', value: `${(m.precision * 100).toFixed(1)}%`, icon: <Zap size={20} />, color: '#D4AF37', bg: 'rgba(212,175,55,0.12)' },
    { label: 'Recall', value: `${(m.recall * 100).toFixed(1)}%`, icon: <Activity size={20} />, color: '#3498DB', bg: 'rgba(52,152,219,0.12)' },
    { label: 'AUC-ROC', value: `${(m.aucRoc * 100).toFixed(1)}%`, icon: <Cpu size={20} />, color: '#7B4FBF', bg: 'rgba(123,79,191,0.12)' },
    { label: 'F1 Score', value: `${(m.f1Score * 100).toFixed(1)}%`, icon: <Zap size={20} />, color: '#F39C12', bg: 'rgba(243,156,18,0.12)' },
    { label: 'Avg Latency', value: `${m.avgLatency}ms`, icon: <Clock size={20} />, color: '#2ECC71', bg: 'rgba(46,204,113,0.12)' },
  ];

  return (
    <div className="slide-up">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Model Monitor</h1>
          <p>Track ML model performance, drift, and health metrics in real-time.</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span className="badge badge-emerald">Model {m.version}</span>
          <button className="btn btn-secondary btn-sm"><RefreshCw size={14} /> Retrain Model</button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-3 gap-6" style={{ marginBottom: 32 }}>
        {metricCards.map(mc => (
          <div className="stat-card" key={mc.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="stat-label">{mc.label}</div>
              <div style={{ width: 36, height: 36, borderRadius: 'var(--radius-md)', background: mc.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', color: mc.color }}>{mc.icon}</div>
            </div>
            <div className="stat-value" style={{ color: mc.color }}>{mc.value}</div>
          </div>
        ))}
      </div>

      {/* Performance Over Time */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h4>Performance Over Time</h4>
          <span className="badge badge-gold">Last 6 Months</span>
        </div>
        <TrendLineChart
          data={m.history}
          lines={[
            { dataKey: 'accuracy', name: 'Accuracy', color: '#2ECC71' },
            { dataKey: 'aucRoc', name: 'AUC-ROC', color: '#D4AF37' },
          ]}
          height={300}
        />
      </div>

      {/* Model Info */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div className="card">
          <h4 style={{ marginBottom: 16 }}>Model Details</h4>
          {[
            ['Version', m.version],
            ['Total Predictions', m.totalPredictions.toLocaleString()],
            ['Last Trained', new Date(m.lastTrained).toLocaleDateString()],
            ['Algorithm', 'XGBoost Ensemble'],
            ['Features', '24 engineered features'],
            ['Training Samples', '45,000'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--color-ivory-muted)', fontSize: '0.875rem' }}>{k}</span>
              <span style={{ fontWeight: 500 }}>{v}</span>
            </div>
          ))}
        </div>

        <div className="card">
          <h4 style={{ marginBottom: 16 }}>Drift Monitoring</h4>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px', background: m.driftScore < 0.1 ? 'var(--color-emerald-bg)' : 'var(--color-amber-bg)', borderRadius: 'var(--radius-md)', border: `1px solid ${m.driftScore < 0.1 ? 'rgba(46,204,113,0.2)' : 'rgba(243,156,18,0.2)'}`, marginBottom: 16 }}>
            {m.driftScore < 0.1 ? <CheckCircle size={24} color="#2ECC71" /> : <AlertTriangle size={24} color="#F39C12" />}
            <div>
              <div style={{ fontWeight: 600 }}>Drift Score: {m.driftScore}</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>
                {m.driftScore < 0.1 ? 'Model is stable — no significant drift detected.' : 'Moderate drift detected — consider retraining.'}
              </div>
            </div>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>
            Drift is measured using Population Stability Index (PSI). A score below 0.1 indicates stable model performance. Values above 0.2 suggest significant distribution shift requiring retraining.
          </p>
        </div>
      </div>
    </div>
  );
}
