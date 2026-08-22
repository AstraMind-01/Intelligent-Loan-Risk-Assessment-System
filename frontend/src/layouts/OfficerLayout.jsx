import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { LayoutDashboard, Users, BarChart3, FileText, Bell, LogOut, Shield, Home } from 'lucide-react';

export default function OfficerLayout() {
  const { user, logout, switchRole } = useAuth();
  const { unreadCount } = useNotifications();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  const links = [
    { to: '/officer', icon: <LayoutDashboard size={18} />, label: 'Dashboard', end: true },
    { to: '/officer/queue', icon: <Users size={18} />, label: 'Applicant Queue' },
    { to: '/officer/risk-analysis', icon: <BarChart3 size={18} />, label: 'Risk Analysis' },
    { to: '/officer/reports', icon: <FileText size={18} />, label: 'Reports History' },
  ];

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">LR</div>
          <div>LoanRisk<span style={{ display: 'block', fontSize: '0.625rem', color: 'var(--color-ivory-muted)', fontFamily: 'var(--font-body)', fontWeight: 400, letterSpacing: '0.08em' }}>OFFICER PORTAL</span></div>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Officer Tools</div>
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
            <button className="sidebar-link" onClick={() => { switchRole('admin'); navigate('/admin'); }} style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', font: 'inherit' }}>
              <Shield size={18} /> Admin View
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
          <div className="navbar-left"><h2>Officer Dashboard</h2></div>
          <div className="navbar-right">
            <div className="notification-bell"><Bell size={20} />{unreadCount > 0 && <div className="notification-dot" />}</div>
            <div className="navbar-avatar">{user?.avatar || 'O'}</div>
          </div>
        </header>
        <main className="page-content fade-in"><Outlet /></main>
      </div>
    </div>
  );
}
