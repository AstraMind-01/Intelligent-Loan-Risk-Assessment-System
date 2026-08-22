import React, { useState } from 'react';
import { mockAdminUsers } from '../../utils/mockData';
import { timeAgo } from '../../utils/formatters';
import { Search, UserPlus, MoreVertical, Shield, Edit, Trash2 } from 'lucide-react';

export default function ManageUsers() {
  const [users, setUsers] = useState(mockAdminUsers);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);

  const filtered = users.filter(u =>
    u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase())
  );

  const getRoleBadge = (role) => {
    if (role === 'admin') return 'badge-gold';
    if (role === 'officer') return 'badge-sapphire';
    return 'badge-emerald';
  };

  const toggleStatus = (id) => {
    setUsers(prev => prev.map(u => u.id === id ? { ...u, status: u.status === 'Active' ? 'Suspended' : 'Active' } : u));
  };

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Manage Users</h1>
        <p>View, create, and manage user accounts across all roles.</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ position: 'relative', minWidth: 280 }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-ivory-muted)' }} />
            <input className="form-input" placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 36 }} />
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowModal(true)}><UserPlus size={14} /> Add User</button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Login</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(user => (
                <tr key={user.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 'var(--radius-full)', background: 'linear-gradient(135deg, var(--color-purple-mid), var(--color-gold))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8125rem', fontWeight: 600, flexShrink: 0 }}>
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <div style={{ fontWeight: 500 }}>{user.name}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td><span className={`badge ${getRoleBadge(user.role)}`} style={{ textTransform: 'capitalize' }}>{user.role}</span></td>
                  <td><span className={`badge ${user.status === 'Active' ? 'badge-emerald' : 'badge-ruby'}`}>{user.status}</span></td>
                  <td style={{ color: 'var(--color-ivory-muted)', fontSize: '0.8125rem' }}>{timeAgo(user.lastLogin)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" title="Edit"><Edit size={14} /></button>
                      <button className="btn btn-ghost btn-sm" title={user.status === 'Active' ? 'Suspend' : 'Activate'} onClick={() => toggleStatus(user.id)}>
                        <Shield size={14} color={user.status === 'Active' ? '#F39C12' : '#2ECC71'} />
                      </button>
                      <button className="btn btn-ghost btn-sm" title="Delete" style={{ color: 'var(--color-ruby)' }}><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Simple Add User Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add New User</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <div className="form-group">
              <label>Full Name</label>
              <input className="form-input" placeholder="Enter full name" />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input className="form-input" type="email" placeholder="user@example.com" />
            </div>
            <div className="form-group">
              <label>Role</label>
              <select className="form-input">
                <option value="applicant">Applicant</option>
                <option value="officer">Loan Officer</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => setShowModal(false)}>Create User</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
