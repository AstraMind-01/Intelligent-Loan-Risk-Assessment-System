import React from 'react';
import { mockApplications, mockMonthlyTrends, mockRiskDistribution } from '../../utils/mockData';
import { formatCurrency } from '../../utils/formatters';
import TrendLineChart from '../../components/charts/TrendLineChart';
import DonutChart from '../../components/charts/DonutChart';
import { Users, FileText, CheckCircle, AlertTriangle, TrendingUp, Clock } from 'lucide-react';

export default function Dashboard() {
  const totalApps = mockApplications.length;
  const pending = mockApplications.filter(a => a.status === 'Submitted' || a.status === 'Under Review').length;
  const approved = mockApplications.filter(a => a.status === 'Approved').length;
  const avgScore = Math.round(mockApplications.filter(a => a.riskScore).reduce((sum, a) => sum + a.riskScore, 0) / mockApplications.filter(a => a.riskScore).length);

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Officer Dashboard</h1>
        <p>Overview of loan applications, risk metrics, and pending reviews.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-4 gap-6" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(212,175,55,0.15)', color: '#D4AF37' }}><FileText size={22} /></div>
          <div className="stat-value">{totalApps}</div>
          <div className="stat-label">Total Applications</div>
          <div className="stat-change positive"><TrendingUp size={12} /> +12% this month</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(243,156,18,0.15)', color: '#F39C12' }}><Clock size={22} /></div>
          <div className="stat-value">{pending}</div>
          <div className="stat-label">Pending Review</div>
          <div className="stat-change negative"><AlertTriangle size={12} /> Requires attention</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(46,204,113,0.15)', color: '#2ECC71' }}><CheckCircle size={22} /></div>
          <div className="stat-value">{approved}</div>
          <div className="stat-label">Approved</div>
          <div className="stat-change positive"><TrendingUp size={12} /> 75% approval rate</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52,152,219,0.15)', color: '#3498DB' }}><Users size={22} /></div>
          <div className="stat-value">{avgScore}</div>
          <div className="stat-label">Avg. Risk Score</div>
          <div className="stat-change positive"><TrendingUp size={12} /> +8 from last month</div>
        </div>
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24, marginBottom: 32 }}>
        <div className="card">
          <div className="card-header">
            <h4>Application Trends</h4>
            <span className="badge badge-gold">Last 6 Months</span>
          </div>
          <TrendLineChart
            data={mockMonthlyTrends}
            lines={[
              { dataKey: 'applications', name: 'Total Applications', color: '#D4AF37' },
              { dataKey: 'approved', name: 'Approved', color: '#2ECC71' },
            ]}
            height={260}
          />
        </div>
        <div className="card">
          <div className="card-header">
            <h4>Risk Distribution</h4>
          </div>
          <DonutChart data={mockRiskDistribution} height={260} />
        </div>
      </div>

      {/* Recent Applications */}
      <div className="card">
        <div className="card-header">
          <h4>Recent Applications</h4>
          <span className="label-caps">{pending} awaiting review</span>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Amount</th>
                <th>Purpose</th>
                <th>Risk Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {mockApplications.slice(0, 5).map(app => (
                <tr key={app.id}>
                  <td style={{ fontWeight: 500 }}>{app.applicantName}</td>
                  <td style={{ color: 'var(--color-gold)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>{formatCurrency(app.loanAmount)}</td>
                  <td>{app.purpose}</td>
                  <td>
                    {app.riskScore ? (
                      <span style={{ fontWeight: 600, color: app.riskScore >= 700 ? 'var(--color-emerald)' : app.riskScore >= 550 ? 'var(--color-amber)' : 'var(--color-ruby)' }}>
                        {app.riskScore}
                      </span>
                    ) : '—'}
                  </td>
                  <td><span className={`badge badge-${app.status === 'Approved' ? 'emerald' : app.status === 'Rejected' ? 'ruby' : 'amber'}`}>{app.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
