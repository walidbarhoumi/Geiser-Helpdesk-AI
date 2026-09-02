import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Loader2, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import api from '../../api/axios';


const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api.post('/auth/forgot-password', { email });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

        .fp-root * { box-sizing: border-box; margin: 0; padding: 0; }

        .fp-root {
          display: flex;
          min-height: 100vh;
          background: #0a0a0f;
          font-family: 'DM Sans', sans-serif;
        }

        /* LEFT */
        .fp-left {
          position: relative;
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 48px 56px;
          overflow: hidden;
          background: #0d0d18;
        }
        .fp-left::before {
          content: '';
          position: absolute; inset: 0;
          background:
            radial-gradient(ellipse 75% 55% at 15% 85%, rgba(99,80,245,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 55% 45% at 85% 15%, rgba(168,85,247,0.12) 0%, transparent 55%);
          pointer-events: none;
        }
        .fp-left::after {
          content: '';
          position: absolute; top: 0; right: 0;
          width: 1px; height: 100%;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
        }

        .fp-logo {
          display: flex; align-items: center; gap: 12px;
          z-index: 1;
        }
        .fp-logo-icon {
          width: 40px; height: 40px; border-radius: 10px;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-size: 16px; font-weight: 700;
        }
        .fp-logo-name { font-size: 18px; font-weight: 500; color: #fff; letter-spacing: -0.3px; }

        .fp-hero { z-index: 1; }
        .fp-tagline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(32px, 3vw, 48px);
          line-height: 1.12; color: #fff;
          letter-spacing: -1px; margin-bottom: 20px;
        }
        .fp-tagline em { font-style: italic; color: #a78bfa; }
        .fp-sub {
          font-size: 15px; color: rgba(255,255,255,0.4);
          line-height: 1.65; max-width: 360px; font-weight: 300;
        }

        /* deco card */
        .fp-deco {
          position: absolute;
          top: 50%; right: 64px;
          transform: translateY(-50%) rotate(-3deg);
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 22px 26px; width: 220px;
          animation: fpFloat 6s ease-in-out infinite;
          z-index: 1;
        }
        @keyframes fpFloat {
          0%,100% { transform: translateY(-50%) rotate(-3deg); }
          50% { transform: translateY(calc(-50% - 10px)) rotate(-3deg); }
        }
        .fp-deco-steps { display: flex; flex-direction: column; gap: 12px; }
        .fp-deco-step { display: flex; align-items: center; gap: 10px; }
        .fp-deco-step-num {
          width: 24px; height: 24px; border-radius: 6px;
          background: rgba(99,80,245,0.2);
          border: 1px solid rgba(99,80,245,0.3);
          display: flex; align-items: center; justify-content: center;
          font-size: 10px; font-weight: 600; color: #a78bfa; flex-shrink: 0;
        }
        .fp-deco-step-num.done {
          background: rgba(16,185,129,0.15);
          border-color: rgba(16,185,129,0.25);
          color: #34d399;
        }
        .fp-deco-step-text { font-size: 11px; color: rgba(255,255,255,0.45); }

        .fp-stats { display: flex; gap: 40px; z-index: 1; }
        .fp-stat-num { font-family: 'DM Serif Display', serif; font-size: 26px; color: #fff; }
        .fp-stat-label { font-size: 11px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px; }

        /* RIGHT */
        .fp-right {
          width: 500px; min-width: 500px;
          display: flex; align-items: center; justify-content: center;
          padding: 48px 56px;
          background: #fff;
        }
        .fp-form-wrap { width: 100%; max-width: 380px; }

        .fp-back {
          display: inline-flex; align-items: center; gap: 7px;
          font-size: 13px; font-weight: 500;
          color: #888; text-decoration: none;
          margin-bottom: 32px;
          transition: color 0.2s;
        }
        .fp-back:hover { color: #6350f5; }

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
          margin-bottom: 36px; line-height: 1.55;
        }

        .error-box {
          display: flex; align-items: center; gap: 10px;
          background: #fff5f5; border: 1px solid #fecaca;
          color: #dc2626; padding: 12px 14px;
          border-radius: 10px; margin-bottom: 24px; font-size: 13px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
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
          font-size: 14px; font-weight: 400;
          border: 1.5px solid #e8e8ef;
          border-radius: 10px;
          background: #fafafa; color: #0a0a0f;
          outline: none;
          transition: all 0.2s;
        }
        .field-input::placeholder { color: #c0c0cc; }
        .field-input:hover { border-color: #c4bffa; background: #fff; }
        .field-input:focus { border-color: #6350f5; background: #fff; box-shadow: 0 0 0 3px rgba(99,80,245,0.08); }

        .submit-btn {
          width: 100%; padding: 14px 20px; margin-top: 20px;
          background: #0a0a0f; color: #fff; border: none;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 15px; font-weight: 500; cursor: pointer;
          display: flex; align-items: center; justify-content: center; gap: 8px;
          transition: all 0.2s;
        }
        .submit-btn:hover:not(:disabled) { background: #1a1a2e; transform: translateY(-1px); }
        .submit-btn:disabled { opacity: 0.55; cursor: not-allowed; }

        /* SUCCESS */
        .fp-success {
          text-align: center; padding: 20px 0;
        }
        .fp-success-icon {
          width: 72px; height: 72px; border-radius: 20px;
          background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(16,185,129,0.05));
          border: 1px solid rgba(16,185,129,0.2);
          display: inline-flex; align-items: center; justify-content: center;
          color: #10b981; margin-bottom: 24px;
        }
        .fp-success-title {
          font-family: 'DM Serif Display', serif;
          font-size: 30px; color: #0a0a0f;
          letter-spacing: -0.6px; margin-bottom: 10px;
        }
        .fp-success-desc {
          font-size: 14px; color: #888; font-weight: 300;
          line-height: 1.6; margin-bottom: 28px; max-width: 300px; margin-left: auto; margin-right: auto;
        }
        .fp-success-desc strong { color: #0a0a0f; font-weight: 500; }
        .fp-retry {
          background: none; border: none;
          font-family: 'DM Sans', sans-serif;
          font-size: 14px; color: #6350f5; font-weight: 500;
          cursor: pointer; padding: 0;
        }
        .fp-retry:hover { text-decoration: underline; }

        @media (max-width: 900px) {
          .fp-left { display: none; }
          .fp-right { width: 100%; min-width: 0; padding: 40px 24px; }
        }
      `}</style>

      <div className="fp-root">
        {/* LEFT */}
        <div className="fp-left">
          <div className="fp-logo">
            <div className="fp-logo-icon">G</div>
            <span className="fp-logo-name">Geiser Helpdesk AI</span>
          </div>

          <div className="fp-hero">
            <h1 className="fp-tagline">
              Back in<br /><em>no time.</em>
            </h1>
            <p className="fp-sub">
              Resetting your password is quick and secure. We'll have you back in your workspace within minutes.
            </p>
          </div>

          <div className="fp-deco">
            <div className="fp-deco-steps">
              <div className="fp-deco-step">
                <div className="fp-deco-step-num done">✓</div>
                <div className="fp-deco-step-text">Enter your email</div>
              </div>
              <div className="fp-deco-step">
                <div className="fp-deco-step-num">2</div>
                <div className="fp-deco-step-text">Check your inbox</div>
              </div>
              <div className="fp-deco-step">
                <div className="fp-deco-step-num">3</div>
                <div className="fp-deco-step-text">Set new password</div>
              </div>
              <div className="fp-deco-step">
                <div className="fp-deco-step-num">4</div>
                <div className="fp-deco-step-text">Back to work</div>
              </div>
            </div>
          </div>

          <div className="fp-stats">
            <div>
              <div className="fp-stat-num">&lt;2 min</div>
              <div className="fp-stat-label">Reset time</div>
            </div>
            <div>
              <div className="fp-stat-num">Secure</div>
              <div className="fp-stat-label">Encrypted link</div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="fp-right">
          <div className="fp-form-wrap">
            {success ? (
              <div className="fp-success">
                <div className="fp-success-icon">
                  <CheckCircle2 size={32} />
                </div>
                <h1 className="fp-success-title">Check your email</h1>
                <p className="fp-success-desc">
                  If an account exists for <strong>{email}</strong>, you'll receive password reset instructions shortly.
                </p>
                <button className="fp-retry" onClick={() => setSuccess(false)}>
                  Try a different email
                </button>
              </div>
            ) : (
              <>
                <Link to="/login" className="fp-back">
                  <ArrowLeft size={15} /> Back to login
                </Link>

                <p className="form-eyebrow">Password recovery</p>
                <h2 className="form-title">Reset password</h2>
                <p className="form-subtitle">
                  Enter your email and we'll send you a secure link to reset your password.
                </p>

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
                        onChange={e => setEmail(e.target.value)}
                      />
                    </div>
                  </div>

                  <button type="submit" disabled={loading || !email} className="submit-btn">
                    {loading ? (
                      <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <>Send reset link <ArrowRight size={16} /></>
                    )}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default ForgotPassword;