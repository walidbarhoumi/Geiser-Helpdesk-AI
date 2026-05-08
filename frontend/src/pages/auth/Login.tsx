import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, Loader2, ArrowRight, Headphones } from 'lucide-react';
import { useAuth } from '../../store/authContext';
import api from '../../api/axios';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/login', { email, password });

      if (response.data.requires_2fa) {
        navigate('/verify-2fa', { state: { email, message: response.data.message } });
        return;
      }

      const { user, ...tokenData } = response.data;
      login(tokenData, user);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to login. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');

        .login-root * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }

        .login-root {
          display: flex;
          min-height: 100vh;
          background: #0a0a0f;
          font-family: 'DM Sans', sans-serif;
        }

        /* ── LEFT PANEL ── */
        .login-left {
          position: relative;
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 48px 56px;
          overflow: hidden;
          background: #0d0d18;
        }

        .login-left::before {
          content: '';
          position: absolute;
          inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 20% 80%, rgba(99, 80, 245, 0.18) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 80% 20%, rgba(168, 85, 247, 0.12) 0%, transparent 55%);
          pointer-events: none;
        }

        /* geometric accent lines */
        .login-left::after {
          content: '';
          position: absolute;
          top: 0; right: 0;
          width: 1px;
          height: 100%;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
        }

        .left-logo {
          display: flex;
          align-items: center;
          gap: 12px;
          z-index: 1;
        }

        .left-logo-icon {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
        }

        .left-logo-name {
          font-size: 18px;
          font-weight: 500;
          color: #fff;
          letter-spacing: -0.3px;
        }

        .left-hero {
          z-index: 1;
        }

        .left-tagline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(36px, 3.5vw, 52px);
          line-height: 1.12;
          color: #ffffff;
          letter-spacing: -1px;
          margin-bottom: 20px;
        }

        .left-tagline em {
          font-style: italic;
          color: #a78bfa;
        }

        .left-sub {
          font-size: 15px;
          color: rgba(255,255,255,0.45);
          line-height: 1.65;
          max-width: 360px;
          font-weight: 300;
        }

        .left-stats {
          display: flex;
          gap: 40px;
          z-index: 1;
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .stat-num {
          font-family: 'DM Serif Display', serif;
          font-size: 28px;
          color: #fff;
          letter-spacing: -0.5px;
        }

        .stat-label {
          font-size: 12px;
          color: rgba(255,255,255,0.35);
          font-weight: 400;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }

        /* decorative floating card */
        .deco-card {
          position: absolute;
          top: 50%;
          right: 64px;
          transform: translateY(-50%) rotate(-3deg);
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 20px 24px;
          width: 220px;
          animation: float 6s ease-in-out infinite;
        }

        @keyframes float {
          0%, 100% { transform: translateY(-50%) rotate(-3deg); }
          50% { transform: translateY(calc(-50% - 10px)) rotate(-3deg); }
        }

        .deco-card-head {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 14px;
        }

        .deco-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6350f5, #a855f7);
        }

        .deco-name {
          font-size: 13px;
          font-weight: 500;
          color: rgba(255,255,255,0.85);
        }

        .deco-role {
          font-size: 11px;
          color: rgba(255,255,255,0.35);
        }

        .deco-tag {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          font-size: 11px;
          padding: 4px 10px;
          border-radius: 100px;
          background: rgba(99, 80, 245, 0.2);
          color: #a78bfa;
          border: 1px solid rgba(167, 139, 250, 0.2);
        }

        .deco-tag-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #a78bfa;
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }

        /* ── RIGHT PANEL ── */
        .login-right {
          width: 480px;
          min-width: 480px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 48px 56px;
          background: #fff;
          position: relative;
        }

        .login-form-wrap {
          width: 100%;
          max-width: 360px;
        }

        .form-eyebrow {
          font-size: 12px;
          font-weight: 500;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          color: #6350f5;
          margin-bottom: 12px;
        }

        .form-title {
          font-family: 'DM Serif Display', serif;
          font-size: 34px;
          color: #0a0a0f;
          letter-spacing: -0.8px;
          line-height: 1.1;
          margin-bottom: 8px;
        }

        .form-subtitle {
          font-size: 14px;
          color: #888;
          font-weight: 300;
          margin-bottom: 40px;
          line-height: 1.5;
        }

        .error-box {
          display: flex;
          align-items: center;
          gap: 10px;
          background: #fff5f5;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px 14px;
          border-radius: 10px;
          margin-bottom: 24px;
          font-size: 13px;
          font-weight: 400;
        }

        .field-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-bottom: 20px;
        }

        .field-label {
          font-size: 13px;
          font-weight: 500;
          color: #1a1a2e;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .field-label a {
          font-size: 12px;
          font-weight: 400;
          color: #6350f5;
          text-decoration: none;
        }

        .field-label a:hover {
          text-decoration: underline;
        }

        .input-wrap {
          position: relative;
        }

        .input-icon {
          position: absolute;
          left: 14px;
          top: 50%;
          transform: translateY(-50%);
          color: #bbb;
          pointer-events: none;
          display: flex;
        }

        .field-input {
          width: 100%;
          padding: 13px 14px 13px 42px;
          font-family: 'DM Sans', sans-serif;
          font-size: 14px;
          font-weight: 400;
          border: 1.5px solid #e8e8ef;
          border-radius: 10px;
          background: #fafafa;
          color: #0a0a0f;
          outline: none;
          transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
        }

        .field-input::placeholder {
          color: #c0c0cc;
        }

        .field-input:hover {
          border-color: #c4bffa;
          background: #fff;
        }

        .field-input:focus {
          border-color: #6350f5;
          background: #fff;
          box-shadow: 0 0 0 3px rgba(99, 80, 245, 0.08);
        }

        .submit-btn {
          width: 100%;
          padding: 14px 20px;
          margin-top: 8px;
          background: #0a0a0f;
          color: #fff;
          border: none;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 15px;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: background 0.2s, transform 0.15s;
          letter-spacing: -0.1px;
        }

        .submit-btn:hover:not(:disabled) {
          background: #1a1a2e;
          transform: translateY(-1px);
        }

        .submit-btn:active:not(:disabled) {
          transform: translateY(0);
        }

        .submit-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .divider {
          display: flex;
          align-items: center;
          gap: 12px;
          margin: 28px 0;
        }

        .divider-line {
          flex: 1;
          height: 1px;
          background: #e8e8ef;
        }

        .divider-text {
          font-size: 12px;
          color: #bbb;
          font-weight: 400;
        }

        .register-link {
          text-align: center;
          font-size: 14px;
          color: #888;
          font-weight: 300;
        }

        .register-link a {
          color: #6350f5;
          font-weight: 500;
          text-decoration: none;
        }

        .register-link a:hover {
          text-decoration: underline;
        }

        @media (max-width: 900px) {
          .login-left {
            display: none;
          }
          .login-right {
            width: 100%;
            min-width: 0;
            padding: 40px 24px;
          }
        }
      `}</style>

      <div className="login-root">
        {/* ── LEFT: Brand panel ── */}
        <div className="login-left">
          <div className="left-logo">
            <div className="left-logo-icon">
              <Headphones size={20} />
            </div>
            <span className="left-logo-name">Geiser Helpdesk AI</span>
          </div>

          <div className="left-hero">
            <h1 className="left-tagline">
              Support that<br />
              <em>actually</em> works.
            </h1>
            <p className="left-sub">
              A helpdesk platform built for teams who care about customer experience — fast, intuitive, and always reliable.
            </p>
          </div>

          {/* floating decorative card */}
          <div className="deco-card">
            <div className="deco-card-head">
              <div className="deco-avatar" />
              <div>
                <div className="deco-name">Sarah K.</div>
                <div className="deco-role">Support Agent</div>
              </div>
            </div>
            <div className="deco-tag">
              <div className="deco-tag-dot" />
              Online · 12 open tickets
            </div>
          </div>

          <div className="left-stats">
            <div className="stat-item">
              <span className="stat-num">98%</span>
              <span className="stat-label">Satisfaction</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">4 min</span>
              <span className="stat-label">Avg. response</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">24/7</span>
              <span className="stat-label">Uptime</span>
            </div>
          </div>
        </div>

        {/* ── RIGHT: Form panel ── */}
        <div className="login-right">
          <div className="login-form-wrap">
            <p className="form-eyebrow">Welcome back</p>
            <h2 className="form-title">Sign in</h2>
            <p className="form-subtitle">Enter your credentials to access your workspace.</p>

            {error && (
              <div className="error-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="7" stroke="#dc2626" strokeWidth="1.5" />
                  <path d="M8 5v3.5M8 11h.01" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="field-group">
                <label className="field-label">Email address</label>
                <div className="input-wrap">
                  <span className="input-icon"><Mail size={16} /></span>
                  <input
                    type="email"
                    required
                    className="field-input"
                    placeholder="name@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">
                  Password
                  <Link to="/forgot-password">Forgot password?</Link>
                </label>
                <div className="input-wrap">
                  <span className="input-icon"><Lock size={16} /></span>
                  <input
                    type="password"
                    required
                    className="field-input"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>

              <button type="submit" disabled={loading} className="submit-btn">
                {loading
                  ? <Loader2 size={18} className="animate-spin" />
                  : <>Continue <ArrowRight size={16} /></>
                }
              </button>
            </form>

            <div className="divider">
              <div className="divider-line" />
              <span className="divider-text">New here?</span>
              <div className="divider-line" />
            </div>

            <p className="register-link">
              <Link to="/register">Create a free account →</Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default Login;