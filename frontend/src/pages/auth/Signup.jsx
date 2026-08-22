import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Shield } from 'lucide-react';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name || !email || !password) { setError('Please fill in all fields'); return; }
    if (password !== confirm) { setError('Passwords do not match'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters'); return; }
    const result = signup(name, email, password);
    if (result.success) navigate('/applicant');
  };

  return (
    <div className="auth-container">
      <div className="auth-card slide-up">
        <div className="auth-logo">
          <Shield size={40} strokeWidth={1.5} />
          LoanRisk
          <span>Create Your Account</span>
        </div>
        <h1>Get Started</h1>
        <p className="subtitle">Apply for loans with AI-powered risk assessment</p>

        {error && <div style={{ background: 'var(--color-ruby-bg)', border: '1px solid rgba(231,76,60,0.3)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', marginBottom: '16px', color: 'var(--color-ruby)', fontSize: '0.8125rem' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Full Name</label>
            <input className="form-input" type="text" placeholder="John Doe" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Email Address</label>
            <input className="form-input" type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input className="form-input" type="password" placeholder="Min. 6 characters" value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Confirm Password</label>
            <input className="form-input" type="password" placeholder="Re-enter password" value={confirm} onChange={e => setConfirm(e.target.value)} />
          </div>
          <button type="submit" className="btn btn-primary btn-block btn-lg" style={{ marginTop: 8 }}>Create Account</button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: '0.875rem', color: 'var(--color-ivory-muted)' }}>
          Already have an account? <Link to="/login" style={{ color: 'var(--color-gold)', fontWeight: 600 }}>Sign In</Link>
        </p>
      </div>
    </div>
  );
}
