import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Home, FileText, BarChart3, Upload, MessageSquare, Calculator, Bell, LogOut, Shield } from 'lucide-react';

export default function ApplicantLayout() {
  const { user, logout, switchRole } = useAuth();
  const { unreadCount } = useNotifications();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  const links = [
    { to: '/applicant', icon: <Home size={18} />, label: 'Home', end: true },
    { to: '/applicant/new-application', icon: <FileText size={18} />, label: 'New Application' },
    { to: '/applicant/my-applications', icon: <BarChart3 size={18} />, label: 'My Applications' },
    { to: '/applicant/risk-report', icon: <Shield size={18} />, label: 'Risk Report' },
    { to: '/applicant/simulator', icon: <Calculator size={18} />, label: 'Eligibility Simulator' },
    { to: '/applicant/documents', icon: <Upload size={18} />, label: 'Document Upload' },
    { to: '/applicant/chat', icon: <MessageSquare size={18} />, label: 'Chat Support' },
  ];

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">LR</div>
          <div>LoanRisk<span style={{ display: 'block', fontSize: '0.625rem', color: 'var(--color-ivory-muted)', fontFamily: 'var(--font-body)', fontWeight: 400, letterSpacing: '0.08em' }}>ASSESSMENT</span></div>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Navigation</div>
            {links.map(l => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
                {l.icon} {l.label}
              </NavLink>
            ))}
          </div>
          {/* Demo role switcher */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">Demo Switch</div>
            <button className="sidebar-link" onClick={() => { switchRole('officer'); navigate('/officer'); }} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit' }}>
              <Shield size={18} /> Officer View
            </button>
            <button className="sidebar-link" onClick={() => { switchRole('admin'); navigate('/admin'); }} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit' }}>
              <BarChart3 size={18} /> Admin View
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
          <div className="navbar-left">
            <h2>Applicant Portal</h2>
          </div>
          <div className="navbar-right">
            <div className="notification-bell">
              <Bell size={20} />
              {unreadCount > 0 && <div className="notification-dot" />}
            </div>
            <div className="navbar-avatar">{user?.avatar || 'U'}</div>
          </div>
        </header>
        <main className="page-content fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
