import React from 'react';
import { mockApplications } from '../../utils/mockData';
import { formatCurrency, formatDate, getStatusBadge } from '../../utils/formatters';
import { Download, FileText } from 'lucide-react';

export default function ReportsHistory() {
  const completedApps = mockApplications.filter(a => a.status === 'Approved' || a.status === 'Rejected');

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Reports History</h1>
        <p>Access past risk assessment reports for completed applications.</p>
      </div>

      <div className="card">
        <div className="card-header">
          <h4>Completed Assessments</h4>
          <button className="btn btn-secondary btn-sm"><Download size={14} /> Export CSV</button>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Application ID</th>
                <th>Applicant</th>
                <th>Amount</th>
                <th>Purpose</th>
                <th>Risk Score</th>
                <th>Decision</th>
                <th>Date</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {completedApps.map(app => (
                <tr key={app.id}>
                  <td style={{ fontWeight: 600 }}>{app.id}</td>
                  <td>{app.applicantName}</td>
                  <td style={{ color: 'var(--color-gold)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>{formatCurrency(app.loanAmount)}</td>
                  <td>{app.purpose}</td>
                  <td>
                    <span style={{ fontWeight: 600, color: app.riskScore >= 700 ? 'var(--color-emerald)' : app.riskScore >= 550 ? 'var(--color-amber)' : 'var(--color-ruby)' }}>
                      {app.riskScore}
                    </span>
                  </td>
                  <td><span className={`badge badge-${getStatusBadge(app.status)}`}>{app.status}</span></td>
                  <td style={{ color: 'var(--color-ivory-muted)' }}>{formatDate(app.date)}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" title="Download Report"><FileText size={16} color="#D4AF37" /></button>
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
