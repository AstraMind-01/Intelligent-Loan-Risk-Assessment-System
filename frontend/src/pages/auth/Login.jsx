import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Shield, Eye, EyeOff } from 'lucide-react';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('applicant');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email || !password) { setError('Please fill in all fields'); return; }
    const result = login(email, password, role);
    if (result.success) {
      navigate(role === 'admin' ? '/admin' : role === 'officer' ? '/officer' : '/applicant');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card slide-up">
        <div className="auth-logo">
          <Shield size={40} strokeWidth={1.5} />
          LoanRisk
          <span>Intelligent Assessment System</span>
        </div>
        <h1>Welcome Back</h1>
        <p className="subtitle">Sign in to access your dashboard</p>

        {error && <div style={{ background: 'var(--color-ruby-bg)', border: '1px solid rgba(231,76,60,0.3)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', marginBottom: '16px', color: 'var(--color-ruby)', fontSize: '0.8125rem' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email Address</label>
            <input className="form-input" type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Password</label>
            <div style={{ position: 'relative' }}>
              <input className="form-input" type={showPw ? 'text' : 'password'} placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)} />
              <button type="button" onClick={() => setShowPw(!showPw)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--color-ivory-muted)', cursor: 'pointer' }}>
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <div className="form-group">
            <label>Login As (Demo)</label>
            <select className="form-input" value={role} onChange={e => setRole(e.target.value)}>
              <option value="applicant">Applicant</option>
              <option value="officer">Loan Officer</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <button type="submit" className="btn btn-primary btn-block btn-lg" style={{ marginTop: 8 }}>Sign In</button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: '0.875rem', color: 'var(--color-ivory-muted)' }}>
          Don't have an account? <Link to="/signup" style={{ color: 'var(--color-gold)', fontWeight: 600 }}>Create Account</Link>
        </p>
      </div>
    </div>
  );
}
