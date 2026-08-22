import React from 'react';
import { mockApplications, mockRiskExplanations } from '../../utils/mockData';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import RiskGauge from '../../components/charts/RiskGauge';
import { TrendingUp, TrendingDown, CheckCircle, XCircle, AlertTriangle, Shield, Fingerprint } from 'lucide-react';

export default function RiskAnalysis() {
  const app = mockApplications[0]; // Viewing first application
  const explanations = mockRiskExplanations;

  return (
    <div className="slide-up">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Risk Analysis — {app.applicantName}</h1>
          <p>Application {app.id} • {app.purpose} • Submitted on {app.date}</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn btn-success"><CheckCircle size={16} /> Approve</button>
          <button className="btn btn-danger"><XCircle size={16} /> Reject</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, marginBottom: 32 }}>
        {/* Gauge */}
        <div className="card card-highlight">
          <h4 style={{ textAlign: 'center', marginBottom: 4 }}>Risk Score</h4>
          <RiskGauge score={app.riskScore} size={200} />
        </div>

        {/* Financial Metrics */}
        <div className="card">
          <h4 style={{ marginBottom: 16 }}>Financial Metrics</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { label: 'Loan Amount', value: formatCurrency(app.loanAmount), color: 'var(--color-gold)' },
              { label: 'Annual Income', value: formatCurrency(app.income), color: 'var(--color-ivory)' },
              { label: 'Debt-to-Income', value: formatPercent(app.dti), color: app.dti <= 0.36 ? 'var(--color-emerald)' : 'var(--color-ruby)' },
              { label: 'Loan-to-Income', value: `${app.lti}x`, color: app.lti <= 4 ? 'var(--color-emerald)' : 'var(--color-amber)' },
              { label: 'Credit Score', value: app.creditScore, color: 'var(--color-ivory)' },
              { label: 'Employment', value: app.employment, color: 'var(--color-ivory-muted)' },
            ].map(m => (
              <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-ivory-muted)', fontSize: '0.8125rem' }}>{m.label}</span>
                <span style={{ fontWeight: 600, color: m.color, fontFamily: 'var(--font-display)' }}>{m.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Fraud & Bias */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Fingerprint size={20} color="#2ECC71" />
              <h4>Fraud Detection</h4>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--color-emerald-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(46,204,113,0.2)' }}>
              <CheckCircle size={16} color="#2ECC71" />
              <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>No fraud indicators detected</span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginTop: 8 }}>Confidence: 97.3%</p>
          </div>
          <div className="card" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Shield size={20} color="#D4AF37" />
              <h4>Bias Check</h4>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'rgba(212,175,55,0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(212,175,55,0.2)' }}>
              <CheckCircle size={16} color="#D4AF37" />
              <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Demographic parity met</span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginTop: 8 }}>Fairness score: 0.96 / 1.00</p>
          </div>
        </div>
      </div>

      {/* Explanations */}
      <div className="card">
        <div className="card-header">
          <h3>Model Explanations (SHAP)</h3>
          <span className="badge badge-gold">AI-Generated</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {explanations.map((exp, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: exp.impact === 'positive' ? 'rgba(46,204,113,0.05)' : 'rgba(231,76,60,0.05)', borderRadius: 'var(--radius-sm)', border: `1px solid ${exp.impact === 'positive' ? 'rgba(46,204,113,0.15)' : 'rgba(231,76,60,0.15)'}` }}>
              {exp.impact === 'positive' ? <TrendingUp size={18} color="#2ECC71" /> : <TrendingDown size={18} color="#E74C3C" />}
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{exp.factor}</span>
                <span style={{ color: 'var(--color-ivory-muted)', fontSize: '0.8125rem' }}> — {exp.explanation}</span>
              </div>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: exp.impact === 'positive' ? 'var(--color-emerald)' : 'var(--color-ruby)' }}>
                {exp.weight > 0 ? '+' : ''}{(exp.weight * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
