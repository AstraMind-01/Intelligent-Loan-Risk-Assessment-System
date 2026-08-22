import React, { useState } from 'react';
import { mockAuditLogs } from '../../utils/mockData';
import { formatDate, timeAgo } from '../../utils/formatters';
import { Search, Download, Filter, Clock, User, AlertTriangle } from 'lucide-react';

export default function AuditLogs() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState('All');

  const actions = ['All', ...new Set(mockAuditLogs.map(l => l.action))];

  const filtered = mockAuditLogs.filter(log => {
    if (filterAction !== 'All' && log.action !== filterAction) return false;
    if (search && !log.action.toLowerCase().includes(search.toLowerCase()) && !log.user.toLowerCase().includes(search.toLowerCase()) && !log.target.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const getActionIcon = (action) => {
    if (action.includes('Approved')) return <span style={{ color: 'var(--color-emerald)' }}>✓</span>;
    if (action.includes('Rejected') || action.includes('Fraud')) return <AlertTriangle size={14} color="#E74C3C" />;
    if (action.includes('User')) return <User size={14} color="#3498DB" />;
    return <Clock size={14} color="#D4AF37" />;
  };

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Audit Logs</h1>
        <p>Complete audit trail of all system actions and user activities.</p>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-ivory-muted)' }} />
            <input className="form-input" placeholder="Search logs..." value={search} onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 36 }} />
          </div>
          <select className="form-input" value={filterAction} onChange={e => setFilterAction(e.target.value)} style={{ width: 'auto', minWidth: 180 }}>
            {actions.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <button className="btn btn-secondary btn-sm"><Download size={14} /> Export</button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h4>Activity Log ({filtered.length} entries)</h4>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {filtered.map(log => (
            <div key={log.id} style={{ display: 'flex', gap: 16, padding: '14px 0', borderBottom: '1px solid var(--border-subtle)', alignItems: 'flex-start' }}>
              <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-full)', background: 'rgba(61,30,109,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                {getActionIcon(log.action)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{log.action}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>{timeAgo(log.timestamp)}</span>
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)', marginBottom: 4 }}>
                  By <span style={{ color: 'var(--color-gold)' }}>{log.user}</span> → <span style={{ color: 'var(--color-sapphire)' }}>{log.target}</span>
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)', opacity: 0.8 }}>{log.details}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
