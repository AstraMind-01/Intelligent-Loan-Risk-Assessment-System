import React from 'react';
import { mockApplications } from '../../utils/mockData';
import { formatCurrency, formatDate, getStatusBadge } from '../../utils/formatters';
import { Eye, Filter } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function MyApplications() {
  const apps = mockApplications;

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>My Applications</h1>
        <p>Track all your loan applications and their current status.</p>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h4>All Applications</h4>
          <div className="flex items-center gap-3">
            <button className="btn btn-ghost btn-sm"><Filter size={14} /> Filter</button>
          </div>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Application ID</th>
                <th>Amount</th>
                <th>Purpose</th>
                <th>Date</th>
                <th>Risk Score</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {apps.map(app => (
                <tr key={app.id}>
                  <td style={{ fontWeight: 600 }}>{app.id}</td>
                  <td style={{ color: 'var(--color-gold)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>{formatCurrency(app.loanAmount)}</td>
                  <td>{app.purpose}</td>
                  <td style={{ color: 'var(--color-ivory-muted)' }}>{formatDate(app.date)}</td>
                  <td>
                    {app.riskScore ? (
                      <span style={{ fontWeight: 600, color: app.riskScore >= 700 ? 'var(--color-emerald)' : app.riskScore >= 550 ? 'var(--color-amber)' : 'var(--color-ruby)' }}>
                        {app.riskScore}
                      </span>
                    ) : '—'}
                  </td>
                  <td><span className={`badge badge-${getStatusBadge(app.status)}`}>{app.status}</span></td>
                  <td>
                    <Link to="/applicant/risk-report" className="btn btn-ghost btn-sm" title="View Details">
                      <Eye size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
