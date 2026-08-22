import React, { useState } from 'react';
import { mockApplications } from '../../utils/mockData';
import { formatCurrency, formatDate, formatPercent, getStatusBadge } from '../../utils/formatters';
import { Search, Filter, Eye, CheckCircle, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function ApplicantQueue() {
  const [filter, setFilter] = useState('All');
  const [search, setSearch] = useState('');

  const filtered = mockApplications.filter(app => {
    if (filter !== 'All' && app.status !== filter) return false;
    if (search && !app.applicantName.toLowerCase().includes(search.toLowerCase()) && !app.id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Applicant Queue</h1>
        <p>Review and process pending loan applications.</p>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-ivory-muted)' }} />
            <input className="form-input" placeholder="Search by name or ID..." value={search} onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 36 }} />
          </div>
          {['All', 'Submitted', 'Under Review', 'Approved', 'Rejected'].map(f => (
            <button key={f} className={`btn ${filter === f ? 'btn-primary' : 'btn-ghost'} btn-sm`} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
      </div>

      {/* Queue Table */}
      <div className="card">
        <div className="card-header">
          <h4>Applications ({filtered.length})</h4>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Applicant</th>
                <th>Amount</th>
                <th>Purpose</th>
                <th>DTI</th>
                <th>Risk Score</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(app => (
                <tr key={app.id}>
                  <td style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{app.id}</td>
                  <td style={{ fontWeight: 500 }}>{app.applicantName}</td>
                  <td style={{ color: 'var(--color-gold)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>{formatCurrency(app.loanAmount)}</td>
                  <td>{app.purpose}</td>
                  <td style={{ color: app.dti <= 0.36 ? 'var(--color-emerald)' : 'var(--color-ruby)' }}>{formatPercent(app.dti)}</td>
                  <td>
                    {app.riskScore ? (
                      <span style={{ fontWeight: 600, color: app.riskScore >= 700 ? 'var(--color-emerald)' : app.riskScore >= 550 ? 'var(--color-amber)' : 'var(--color-ruby)' }}>
                        {app.riskScore}
                      </span>
                    ) : '—'}
                  </td>
                  <td><span className={`badge badge-${getStatusBadge(app.status)}`}>{app.status}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <Link to="/officer/risk-analysis" className="btn btn-ghost btn-sm" title="Review"><Eye size={16} /></Link>
                      {(app.status === 'Submitted' || app.status === 'Under Review') && (
                        <>
                          <button className="btn btn-ghost btn-sm" title="Approve" style={{ color: 'var(--color-emerald)' }}><CheckCircle size={16} /></button>
                          <button className="btn btn-ghost btn-sm" title="Reject" style={{ color: 'var(--color-ruby)' }}><XCircle size={16} /></button>
                        </>
                      )}
                    </div>
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
