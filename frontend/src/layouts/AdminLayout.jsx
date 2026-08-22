import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { LayoutDashboard, Users, Activity, FileSearch, Settings, Bell, LogOut, Home, Shield } from 'lucide-react';

export default function AdminLayout() {
  const { user, logout, switchRole } = useAuth();
  const { unreadCount } = useNotifications();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  const links = [
    { to: '/admin', icon: <LayoutDashboard size={18} />, label: 'Overview', end: true },
    { to: '/admin/users', icon: <Users size={18} />, label: 'Manage Users' },
    { to: '/admin/model-monitor', icon: <Activity size={18} />, label: 'Model Monitor' },
    { to: '/admin/audit-logs', icon: <FileSearch size={18} />, label: 'Audit Logs' },
    { to: '/admin/settings', icon: <Settings size={18} />, label: 'Settings' },
  ];

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">LR</div>
          <div>LoanRisk<span style={{ display: 'block', fontSize: '0.625rem', color: 'var(--color-ivory-muted)', fontFamily: 'var(--font-body)', fontWeight: 400, letterSpacing: '0.08em' }}>ADMIN PANEL</span></div>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Administration</div>
            {links.map(l => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
                {l.icon} {l.label}
              </NavLink>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-section-title">Demo Switch</div>
            <button className="sidebar-link" onClick={() => { switchRole('applicant'); navigate('/applicant'); }} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit' }}>
              <Home size={18} /> Applicant View
            </button>
            <button className="sidebar-link" onClick={() => { switchRole('officer'); navigate('/officer'); }} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit' }}>
              <Shield size={18} /> Officer View
            </button>
          </div>
        </nav>
        <div className="sidebar-footer">
          <button className="sidebar-link" onClick={handleLogout} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit', color: 'var(--color-ruby)' }}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>
      <div className="main-content">
        <header className="navbar">
          <div className="navbar-left"><h2>Admin Panel</h2></div>
          <div className="navbar-right">
            <div className="notification-bell"><Bell size={20} />{unreadCount > 0 && <div className="notification-dot" />}</div>
            <div className="navbar-avatar">{user?.avatar || 'A'}</div>
          </div>
        </header>
        <main className="page-content fade-in"><Outlet /></main>
      </div>
    </div>
  );
}
