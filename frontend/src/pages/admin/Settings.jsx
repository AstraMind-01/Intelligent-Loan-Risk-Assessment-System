import React, { useState } from 'react';
import { Save, Bell, Shield, Database, Mail } from 'lucide-react';

export default function Settings() {
  const [settings, setSettings] = useState({
    autoApproveThreshold: 780,
    autoRejectThreshold: 400,
    maxLoanAmount: 1000000,
    sessionTimeout: 30,
    emailNotifications: true,
    smsNotifications: false,
    auditRetention: 90,
    modelRetrainingSchedule: 'monthly',
    maintenanceMode: false,
  });

  const update = (field) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    alert('Settings saved successfully!');
  };

  return (
    <div className="slide-up">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>System Settings</h1>
          <p>Configure system-wide parameters, thresholds, and notifications.</p>
        </div>
        <button className="btn btn-primary" onClick={handleSave}><Save size={16} /> Save Changes</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Risk Thresholds */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Shield size={20} color="#D4AF37" />
            <h4>Risk Thresholds</h4>
          </div>
          <div className="form-group">
            <label>Auto-Approve Threshold (Score ≥)</label>
            <input className="form-input" type="number" value={settings.autoApproveThreshold} onChange={update('autoApproveThreshold')} />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginTop: 4, display: 'block' }}>Applications with risk score at or above this will be auto-approved.</span>
          </div>
          <div className="form-group">
            <label>Auto-Reject Threshold (Score ≤)</label>
            <input className="form-input" type="number" value={settings.autoRejectThreshold} onChange={update('autoRejectThreshold')} />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginTop: 4, display: 'block' }}>Applications below this score will be auto-rejected.</span>
          </div>
          <div className="form-group">
            <label>Maximum Loan Amount ($)</label>
            <input className="form-input" type="number" value={settings.maxLoanAmount} onChange={update('maxLoanAmount')} />
          </div>
        </div>

        {/* Notifications */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Bell size={20} color="#D4AF37" />
            <h4>Notifications</h4>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={settings.emailNotifications} onChange={update('emailNotifications')} style={{ width: 18, height: 18, accentColor: '#D4AF37' }} />
              <div>
                <div style={{ fontWeight: 500 }}>Email Notifications</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>Send email alerts for application status changes</div>
              </div>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={settings.smsNotifications} onChange={update('smsNotifications')} style={{ width: 18, height: 18, accentColor: '#D4AF37' }} />
              <div>
                <div style={{ fontWeight: 500 }}>SMS Notifications</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>Send SMS for critical alerts</div>
              </div>
            </label>
          </div>
        </div>

        {/* System */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Database size={20} color="#D4AF37" />
            <h4>System Configuration</h4>
          </div>
          <div className="form-group">
            <label>Session Timeout (minutes)</label>
            <input className="form-input" type="number" value={settings.sessionTimeout} onChange={update('sessionTimeout')} />
          </div>
          <div className="form-group">
            <label>Audit Log Retention (days)</label>
            <input className="form-input" type="number" value={settings.auditRetention} onChange={update('auditRetention')} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', marginTop: 8 }}>
            <input type="checkbox" checked={settings.maintenanceMode} onChange={update('maintenanceMode')} style={{ width: 18, height: 18, accentColor: '#E74C3C' }} />
            <div>
              <div style={{ fontWeight: 500, color: 'var(--color-ruby)' }}>Maintenance Mode</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>Temporarily disable new applications</div>
            </div>
          </label>
        </div>

        {/* ML Config */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Mail size={20} color="#D4AF37" />
            <h4>ML Service Configuration</h4>
          </div>
          <div className="form-group">
            <label>Model Retraining Schedule</label>
            <select className="form-input" value={settings.modelRetrainingSchedule} onChange={update('modelRetrainingSchedule')}>
              <option value="weekly">Weekly</option>
              <option value="biweekly">Bi-weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </div>
          <div style={{ padding: '12px 16px', background: 'rgba(46,204,113,0.06)', border: '1px solid rgba(46,204,113,0.2)', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem' }}>
            <div style={{ fontWeight: 600, color: 'var(--color-emerald)', marginBottom: 4 }}>ML Service Status: Online</div>
            <div style={{ color: 'var(--color-ivory-muted)' }}>Endpoint: ml-service:8000 • Latency: 45ms avg</div>
          </div>
        </div>
      </div>
    </div>
  );
}
