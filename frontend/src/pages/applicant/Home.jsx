import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { mockApplications } from '../../utils/mockData';
import { formatCurrency } from '../../utils/formatters';
import { FileText, Calculator, Upload, TrendingUp, ArrowRight, Shield, Clock } from 'lucide-react';

export default function Home() {
  const { user } = useAuth();
  const myApps = mockApplications.filter(a => a.applicantName === 'Sarah Mitchell');
  const latestApp = myApps[0];

  const quickActions = [
    { to: '/applicant/new-application', icon: <FileText size={24} />, title: 'New Application', desc: 'Start a new loan application', color: '#D4AF37' },
    { to: '/applicant/simulator', icon: <Calculator size={24} />, title: 'Eligibility Simulator', desc: 'Check your eligibility instantly', color: '#2ECC71' },
    { to: '/applicant/documents', icon: <Upload size={24} />, title: 'Upload Documents', desc: 'Submit required documentation', color: '#3498DB' },
    { to: '/applicant/risk-report', icon: <TrendingUp size={24} />, title: 'Risk Report', desc: 'View your detailed risk analysis', color: '#F39C12' },
  ];

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Welcome back, {user?.name?.split(' ')[0] || 'User'} 👋</h1>
        <p>Here's an overview of your loan applications and quick actions.</p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-4 gap-6" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(212,175,55,0.15)', color: '#D4AF37' }}><FileText size={22} /></div>
          <div className="stat-value">{myApps.length}</div>
          <div className="stat-label">Total Applications</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(46,204,113,0.15)', color: '#2ECC71' }}><Shield size={22} /></div>
          <div className="stat-value">{myApps.filter(a => a.status === 'Approved').length}</div>
          <div className="stat-label">Approved</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(243,156,18,0.15)', color: '#F39C12' }}><Clock size={22} /></div>
          <div className="stat-value">{myApps.filter(a => a.status === 'Under Review').length}</div>
          <div className="stat-label">Under Review</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52,152,219,0.15)', color: '#3498DB' }}><TrendingUp size={22} /></div>
          <div className="stat-value">{latestApp?.riskScore || '—'}</div>
          <div className="stat-label">Latest Risk Score</div>
        </div>
      </div>

      {/* Quick Actions */}
      <h3 style={{ marginBottom: 16 }}>Quick Actions</h3>
      <div className="grid grid-4 gap-6" style={{ marginBottom: 32 }}>
        {quickActions.map(qa => (
          <Link key={qa.to} to={qa.to} className="card card-highlight" style={{ textDecoration: 'none', cursor: 'pointer' }}>
            <div style={{ color: qa.color, marginBottom: 12 }}>{qa.icon}</div>
            <h4 style={{ color: 'var(--color-ivory)', marginBottom: 4 }}>{qa.title}</h4>
            <p style={{ color: 'var(--color-ivory-muted)', fontSize: '0.8125rem', marginBottom: 12 }}>{qa.desc}</p>
            <div style={{ color: qa.color, fontSize: '0.8125rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              Get Started <ArrowRight size={14} />
            </div>
          </Link>
        ))}
      </div>

      {/* Latest Application */}
      {latestApp && (
        <>
          <h3 style={{ marginBottom: 16 }}>Latest Application</h3>
          <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 4 }}>Application ID</div>
              <div style={{ fontWeight: 600, fontSize: '1.125rem' }}>{latestApp.id}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 4 }}>Amount</div>
              <div style={{ fontWeight: 600, color: 'var(--color-gold)', fontFamily: 'var(--font-display)', fontSize: '1.125rem' }}>{formatCurrency(latestApp.loanAmount)}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 4 }}>Purpose</div>
              <div style={{ fontWeight: 500 }}>{latestApp.purpose}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 4 }}>Status</div>
              <span className="badge badge-amber">{latestApp.status}</span>
            </div>
            <Link to="/applicant/my-applications" className="btn btn-secondary btn-sm">View All <ArrowRight size={14} /></Link>
          </div>
        </>
      )}
    </div>
  );
}
