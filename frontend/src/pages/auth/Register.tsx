import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, User, Loader2, ArrowRight } from 'lucide-react';
import api from '../../api/axios';


const Register: React.FC = () => {
  const [formData, setFormData] = useState({ email: '', password: '', full_name: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api.post('/auth/register', formData);
      navigate('/login', { state: { message: 'Account created! Please sign in.' } });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to register. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const passwordStrength = (pw: string) => {
    if (!pw) return 0;
    let s = 0;
    if (pw.length >= 8) s++;
    if (/[A-Z]/.test(pw)) s++;
    if (/[0-9]/.test(pw)) s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;
    return s;
  };
  const strength = passwordStrength(formData.password);
  const strengthLabel = ['', 'Weak', 'Fair', 'Good', 'Strong'][strength];
  const strengthColor = ['', '#ef4444', '#f59e0b', '#6350f5', '#10b981'][strength];

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

        .reg-root * { box-sizing: border-box; margin: 0; padding: 0; }

        .reg-root {
          display: flex;
          min-height: 100vh;
          background: #0a0a0f;
          font-family: 'DM Sans', sans-serif;
        }

        /* LEFT */
        .reg-left {
          position: relative;
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 48px 56px;
          overflow: hidden;
          background: #0d0d18;
        }
        .reg-left::before {
          content: '';
          position: absolute; inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 20% 80%, rgba(99,80,245,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 80% 20%, rgba(168,85,247,0.12) 0%, transparent 55%);
          pointer-events: none;
        }
        .reg-left::after {
          content: '';
          position: absolute; top: 0; right: 0;
          width: 1px; height: 100%;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
        }

        .reg-logo { display: flex; align-items: center; gap: 12px; z-index: 1; }
        .reg-logo-icon {
          width: 40px; height: 40px; border-radius: 10px;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-size: 16px; font-weight: 700;
        }
        .reg-logo-name { font-size: 18px; font-weight: 500; color: #fff; letter-spacing: -0.3px; }

        .reg-hero { z-index: 1; }
        .reg-tagline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(32px, 3vw, 48px);
          line-height: 1.12; color: #fff;
          letter-spacing: -1px; margin-bottom: 20px;
        }
        .reg-tagline em { font-style: italic; color: #a78bfa; }
        .reg-sub {
          font-size: 15px; color: rgba(255,255,255,0.4);
          line-height: 1.65; max-width: 360px; font-weight: 300;
        }

        /* onboarding steps card */
        .reg-steps-card {
          position: absolute;
          top: 50%; right: 64px;
          transform: translateY(-50%) rotate(-2deg);
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 22px 26px; width: 220px;
          animation: regFloat 6s ease-in-out infinite;
          z-index: 1;
        }
        @keyframes regFloat {
          0%,100% { transform: translateY(-50%) rotate(-2deg); }
          50% { transform: translateY(calc(-50% - 10px)) rotate(-2deg); }
        }
        .reg-steps-label {
          font-size: 10px; font-weight: 600; letter-spacing: 1px;
          text-transform: uppercase; color: rgba(255,255,255,0.25);
          margin-bottom: 14px;
        }
        .reg-step { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .reg-step:last-child { margin-bottom: 0; }
        .reg-step-dot {
          width: 22px; height: 22px; border-radius: 6px; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          font-size: 9px; font-weight: 700;
        }
        .reg-step-dot.active {
          background: rgba(99,80,245,0.25);
          border: 1px solid rgba(99,80,245,0.35);
          color: #a78bfa;
        }
        .reg-step-dot.done {
          background: rgba(16,185,129,0.15);
          border: 1px solid rgba(16,185,129,0.25);
          color: #34d399;
        }
        .reg-step-dot.pending {
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.08);
          color: rgba(255,255,255,0.2);
        }
        .reg-step-label { font-size: 11.5px; color: rgba(255,255,255,0.45); }
        .reg-step-label.active-label { color: rgba(255,255,255,0.8); }

        .reg-stats { display: flex; gap: 40px; z-index: 1; }
        .reg-stat-num { font-family: 'DM Serif Display', serif; font-size: 26px; color: #fff; }
        .reg-stat-label { font-size: 11px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px; }

        /* RIGHT */
        .reg-right {
          width: 500px; min-width: 500px;
          display: flex; align-items: center; justify-content: center;
          padding: 48px 56px;
          background: #fff;
        }
        .reg-form-wrap { width: 100%; max-width: 380px; }

        .form-eyebrow {
          font-size: 12px; font-weight: 500;
          letter-spacing: 1.5px; text-transform: uppercase;
          color: #6350f5; margin-bottom: 12px;
        }
        .form-title {
          font-family: 'DM Serif Display', serif;
          font-size: 34px; color: #0a0a0f;
          letter-spacing: -0.8px; line-height: 1.1; margin-bottom: 8px;
        }
        .form-subtitle {
          font-size: 14px; color: #888; font-weight: 300;
          margin-bottom: 36px; line-height: 1.5;
        }

        .error-box {
          display: flex; align-items: center; gap: 10px;
          background: #fff5f5; border: 1px solid #fecaca;
          color: #dc2626; padding: 12px 14px;
          border-radius: 10px; margin-bottom: 24px; font-size: 13px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
        .field-label { font-size: 13px; font-weight: 500; color: #1a1a2e; }
        .input-wrap { position: relative; }
        .input-icon {
          position: absolute; left: 14px; top: 50%;
          transform: translateY(-50%); color: #bbb;
          pointer-events: none; display: flex;
        }
        .field-input {
          width: 100%;
          padding: 13px 14px 13px 44px;
          font-family: 'DM Sans', sans-serif;
          font-size: 14px; border: 1.5px solid #e8e8ef;
          border-radius: 10px; background: #fafafa;
          color: #0a0a0f; outline: none; transition: all 0.2s;
        }
        .field-input::placeholder { color: #c0c0cc; }
        .field-input:hover { border-color: #c4bffa; background: #fff; }
        .field-input:focus { border-color: #6350f5; background: #fff; box-shadow: 0 0 0 3px rgba(99,80,245,0.08); }

        .strength-row { display: flex; gap: 4px; margin-top: 8px; }
        .strength-bar {
          flex: 1; height: 2px; border-radius: 1px;
          background: #e8e8ef; transition: background 0.3s;
        }

        .strength-hint {
          font-size: 11px; margin-top: 5px;
          font-weight: 500; transition: color 0.3s;
        }

        .submit-btn {
          width: 100%;
          padding: 14px 20px;
          background: #0a0a0f; color: #fff; border: none;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 15px; font-weight: 500; cursor: pointer;
          display: flex; align-items: center; justify-content: center; gap: 8px;
          transition: all 0.2s; margin-top: 8px;
        }
        .submit-btn:hover:not(:disabled) { background: #1a1a2e; transform: translateY(-1px); }
        .submit-btn:disabled { opacity: 0.55; cursor: not-allowed; }

        .divider {
          display: flex; align-items: center; gap: 12px;
          margin: 28px 0;
        }
        .divider-line { flex: 1; height: 1px; background: #e8e8ef; }
        .divider-text { font-size: 12px; color: #bbb; }

        .login-link { text-align: center; font-size: 14px; color: #888; font-weight: 300; }
        .login-link a { color: #6350f5; font-weight: 500; text-decoration: none; }
        .login-link a:hover { text-decoration: underline; }

        @media (max-width: 900px) {
          .reg-left { display: none; }
          .reg-right { width: 100%; min-width: 0; padding: 40px 24px; }
        }
      `}</style>

      <div className="reg-root">
        {/* LEFT */}
        <div className="reg-left">
          <div className="reg-logo">
            <div className="reg-logo-icon">G</div>
            <span className="reg-logo-name">Geiser Helpdesk AI</span>
          </div>

          <div className="reg-hero">
            <h1 className="reg-tagline">
              Start your<br /><em>AI journey.</em>
            </h1>
            <p className="reg-sub">
              Join support teams worldwide who use Geiser's AI-powered platform to deliver exceptional customer experiences.
            </p>
          </div>

          <div className="reg-steps-card">
            <div className="reg-steps-label">Getting started</div>
            <div className="reg-step">
              <div className="reg-step-dot active">1</div>
              <div className="reg-step-label active-label">Create your account</div>
            </div>
            <div className="reg-step">
              <div className="reg-step-dot pending">2</div>
              <div className="reg-step-label">Invite your team</div>
            </div>
            <div className="reg-step">
              <div className="reg-step-dot pending">3</div>
              <div className="reg-step-label">Configure AI workflows</div>
            </div>
            <div className="reg-step">
              <div className="reg-step-dot pending">4</div>
              <div className="reg-step-label">Go live in minutes</div>
            </div>
          </div>

          <div className="reg-stats">
            <div>
              <div className="reg-stat-num">2 min</div>
              <div className="reg-stat-label">Setup time</div>
            </div>
            <div>
              <div className="reg-stat-num">Free</div>
              <div className="reg-stat-label">14-day trial</div>
            </div>
            <div>
              <div className="reg-stat-num">No</div>
              <div className="reg-stat-label">Card needed</div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="reg-right">
          <div className="reg-form-wrap">
            <p className="form-eyebrow">Get started</p>
            <h2 className="form-title">Create account</h2>
            <p className="form-subtitle">Set up your workspace in under 2 minutes. No credit card required.</p>

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
                <label className="field-label">Full name</label>
                <div className="input-wrap">
                  <span className="input-icon"><User size={16} /></span>
                  <input
                    type="text"
                    name="full_name"
                    required
                    className="field-input"
                    placeholder="John Doe"
                    value={formData.full_name}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Work email</label>
                <div className="input-wrap">
                  <span className="input-icon"><Mail size={16} /></span>
                  <input
                    type="email"
                    name="email"
                    required
                    className="field-input"
                    placeholder="name@company.com"
                    value={formData.email}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Password</label>
                <div className="input-wrap">
                  <span className="input-icon"><Lock size={16} /></span>
                  <input
                    type="password"
                    name="password"
                    required
                    className="field-input"
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                  />
                </div>
                {formData.password && (
                  <>
                    <div className="strength-row">
                      {[1, 2, 3, 4].map(i => (
                        <div
                          key={i}
                          className="strength-bar"
                          style={{ background: i <= strength ? strengthColor : '#e8e8ef' }}
                        />
                      ))}
                    </div>
                    <div className="strength-hint" style={{ color: strengthColor }}>
                      {strengthLabel} password
                    </div>
                  </>
                )}
              </div>

              <button type="submit" disabled={loading} className="submit-btn">
                {loading ? (
                  <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <>Create account <ArrowRight size={16} /></>
                )}
              </button>
            </form>

            <div className="divider">
              <div className="divider-line" />
              <span className="divider-text">Have an account?</span>
              <div className="divider-line" />
            </div>

            <p className="login-link">
              <Link to="/login">Sign in instead →</Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default Register;