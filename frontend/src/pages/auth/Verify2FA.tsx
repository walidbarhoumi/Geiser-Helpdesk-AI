import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { ArrowRight, Loader2, ShieldCheck, RefreshCw } from 'lucide-react';
import { useAuth } from '../../store/authContext';
import api from '../../api/axios';

const Verify2FA: React.FC = () => {
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [timeLeft, setTimeLeft] = useState(299);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const email = location.state?.email;
  const message = location.state?.message;

  useEffect(() => {
    if (timeLeft <= 0) return;
    const t = setTimeout(() => setTimeLeft(v => v - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft]);

  if (!email) return <Navigate to="/login" replace />;

  const code = digits.join('');
  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const handleDigit = (idx: number, val: string) => {
    const v = val.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[idx] = v;
    setDigits(next);
    setError('');
    if (v && idx < 5) inputRefs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !digits[idx] && idx > 0) {
      inputRefs.current[idx - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted) {
      const next = [...digits];
      pasted.split('').forEach((c, i) => { if (i < 6) next[i] = c; });
      setDigits(next);
      inputRefs.current[Math.min(pasted.length, 5)]?.focus();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) { setError('Please enter the 6-digit code.'); return; }
    setLoading(true);
    setError('');
    try {
      const response = await api.post('/auth/verify-2fa', { email, code });
      const { user, ...tokenData } = response.data;
      login(tokenData, user);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid or expired code.');
      setDigits(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

        .v2fa-root * { box-sizing: border-box; margin: 0; padding: 0; }

        .v2fa-root {
          display: flex;
          min-height: 100vh;
          background: #0a0a0f;
          font-family: 'DM Sans', sans-serif;
        }

        /* LEFT PANEL */
        .v2fa-left {
          position: relative;
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 48px 56px;
          overflow: hidden;
          background: #0d0d18;
        }
        .v2fa-left::before {
          content: '';
          position: absolute;
          inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 20% 80%, rgba(99,80,245,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 80% 20%, rgba(168,85,247,0.12) 0%, transparent 55%);
          pointer-events: none;
        }
        .v2fa-left::after {
          content: '';
          position: absolute;
          top: 0; right: 0;
          width: 1px; height: 100%;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
        }

        .v2fa-logo {
          display: flex;
          align-items: center;
          gap: 12px;
          z-index: 1;
        }
        .v2fa-logo-icon {
          width: 40px; height: 40px;
          border-radius: 10px;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-size: 16px; font-weight: 700;
        }
        .v2fa-logo-name {
          font-size: 18px; font-weight: 500;
          color: #fff; letter-spacing: -0.3px;
        }

        .v2fa-hero { z-index: 1; }
        .v2fa-tagline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(32px, 3vw, 48px);
          line-height: 1.12;
          color: #fff;
          letter-spacing: -1px;
          margin-bottom: 20px;
        }
        .v2fa-tagline em { font-style: italic; color: #a78bfa; }
        .v2fa-sub {
          font-size: 15px;
          color: rgba(255,255,255,0.4);
          line-height: 1.65;
          max-width: 360px;
          font-weight: 300;
        }

        /* floating security card */
        .sec-card {
          position: absolute;
          top: 50%; right: 64px;
          transform: translateY(-50%) rotate(-2deg);
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 22px 26px;
          width: 230px;
          animation: secFloat 6s ease-in-out infinite;
          z-index: 1;
        }
        @keyframes secFloat {
          0%,100% { transform: translateY(-50%) rotate(-2deg); }
          50% { transform: translateY(calc(-50% - 10px)) rotate(-2deg); }
        }
        .sec-card-icon {
          width: 44px; height: 44px; border-radius: 12px;
          background: linear-gradient(135deg, rgba(99,80,245,0.25), rgba(168,85,247,0.15));
          border: 1px solid rgba(167,139,250,0.2);
          display: flex; align-items: center; justify-content: center;
          margin-bottom: 14px;
          color: #a78bfa;
        }
        .sec-card-title {
          font-size: 13px; font-weight: 500;
          color: rgba(255,255,255,0.85);
          margin-bottom: 6px;
        }
        .sec-card-desc {
          font-size: 11px;
          color: rgba(255,255,255,0.3);
          line-height: 1.5;
          margin-bottom: 14px;
        }
        .sec-progress-wrap {
          height: 3px;
          background: rgba(255,255,255,0.08);
          border-radius: 2px;
          overflow: hidden;
        }
        .sec-progress-bar {
          height: 100%;
          border-radius: 2px;
          background: linear-gradient(90deg, #6350f5, #a855f7);
          animation: secProg 3s ease-in-out infinite alternate;
        }
        @keyframes secProg { from { width: 55%; } to { width: 88%; } }

        .v2fa-stats { display: flex; gap: 40px; z-index: 1; }
        .v2fa-stat-num {
          font-family: 'DM Serif Display', serif;
          font-size: 26px; color: #fff; letter-spacing: -0.5px;
        }
        .v2fa-stat-label {
          font-size: 11px; color: rgba(255,255,255,0.3);
          text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px;
        }

        /* RIGHT PANEL */
        .v2fa-right {
          width: 500px; min-width: 500px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 48px 56px;
          background: #fff;
        }
        .v2fa-form-wrap {
          width: 100%;
          max-width: 380px;
        }

        .form-eyebrow {
          font-size: 12px; font-weight: 500;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          color: #6350f5;
          margin-bottom: 12px;
        }
        .form-title {
          font-family: 'DM Serif Display', serif;
          font-size: 34px; color: #0a0a0f;
          letter-spacing: -0.8px;
          line-height: 1.1;
          margin-bottom: 8px;
        }
        .form-subtitle {
          font-size: 14px; color: #888;
          font-weight: 300; line-height: 1.5;
          margin-bottom: 4px;
        }
        .form-email {
          font-size: 14px; font-weight: 500;
          color: #0a0a0f;
          margin-bottom: 32px;
        }

        .timer-badge {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          background: rgba(99,80,245,0.06);
          border: 1px solid rgba(99,80,245,0.15);
          border-radius: 100px;
          padding: 6px 14px;
          font-size: 13px; color: #6350f5;
          font-weight: 400;
          margin-bottom: 28px;
        }
        .timer-dot {
          width: 7px; height: 7px;
          border-radius: 50%;
          background: #6350f5;
          animation: tdot 1.2s ease-in-out infinite;
        }
        @keyframes tdot { 0%,100%{opacity:1} 50%{opacity:0.25} }

        .code-label {
          font-size: 13px; font-weight: 500;
          color: #1a1a2e;
          display: block;
          text-align: center;
          margin-bottom: 14px;
        }

        .code-grid {
          display: flex;
          gap: 10px;
          justify-content: center;
          margin-bottom: 32px;
        }
        .code-digit {
          width: 52px; height: 62px;
          border: 1.5px solid #e8e8ef;
          border-radius: 12px;
          background: #fafafa;
          font-family: 'DM Serif Display', serif;
          font-size: 28px;
          color: #0a0a0f;
          text-align: center;
          outline: none;
          transition: all 0.2s;
          caret-color: #6350f5;
        }
        .code-digit::placeholder { color: #ddd; font-family: 'DM Sans', sans-serif; font-size: 16px; }
        .code-digit:hover { border-color: #c4bffa; background: #fff; }
        .code-digit:focus { border-color: #6350f5; background: #fff; box-shadow: 0 0 0 3px rgba(99,80,245,0.08); }
        .code-digit.has-value { border-color: #6350f5; background: #faf9ff; }

        .error-box {
          display: flex; align-items: center; gap: 10px;
          background: #fff5f5;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px 14px;
          border-radius: 10px;
          margin-bottom: 20px;
          font-size: 13px;
        }

        .submit-btn {
          width: 100%;
          padding: 14px 20px;
          background: #0a0a0f;
          color: #fff; border: none;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 15px; font-weight: 500;
          cursor: pointer;
          display: flex; align-items: center; justify-content: center; gap: 8px;
          transition: all 0.2s;
          letter-spacing: -0.1px;
        }
        .submit-btn:hover:not(:disabled) { background: #1a1a2e; transform: translateY(-1px); }
        .submit-btn:disabled { opacity: 0.55; cursor: not-allowed; }

        .resend-row {
          text-align: center;
          font-size: 14px; color: #888;
          font-weight: 300;
          margin-top: 20px;
        }
        .resend-btn {
          background: none; border: none;
          color: #6350f5; font-size: 14px;
          font-weight: 500; cursor: pointer;
          font-family: 'DM Sans', sans-serif;
          padding: 0; display: inline-flex;
          align-items: center; gap: 5px;
        }
        .resend-btn:hover { text-decoration: underline; }

        @media (max-width: 900px) {
          .v2fa-left { display: none; }
          .v2fa-right { width: 100%; min-width: 0; padding: 40px 24px; }
        }
      `}</style>

      <div className="v2fa-root">
        {/* LEFT */}
        <div className="v2fa-left">
          <div className="v2fa-logo">
            <div className="v2fa-logo-icon">G</div>
            <span className="v2fa-logo-name">Geiser Helpdesk AI</span>
          </div>

          <div className="v2fa-hero">
            <h1 className="v2fa-tagline">
              Your identity,<br />
              <em>secured.</em>
            </h1>
            <p className="v2fa-sub">
              Two-factor authentication protects your workspace and all sensitive support data from unauthorized access.
            </p>
          </div>

          <div className="sec-card">
            <div className="sec-card-icon">
              <ShieldCheck size={22} />
            </div>
            <div className="sec-card-title">Identity verification</div>
            <div className="sec-card-desc">
              Validating your identity before granting workspace access.
            </div>
            <div className="sec-progress-wrap">
              <div className="sec-progress-bar" />
            </div>
          </div>

          <div className="v2fa-stats">
            <div>
              <div className="v2fa-stat-num">256-bit</div>
              <div className="v2fa-stat-label">Encryption</div>
            </div>
            <div>
              <div className="v2fa-stat-num">SOC 2</div>
              <div className="v2fa-stat-label">Compliant</div>
            </div>
            <div>
              <div className="v2fa-stat-num">GDPR</div>
              <div className="v2fa-stat-label">Ready</div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="v2fa-right">
          <div className="v2fa-form-wrap">
            <p className="form-eyebrow">Two-factor auth</p>
            <h2 className="form-title">Verify identity</h2>
            <p className="form-subtitle">{message || 'We sent a 6-digit code to'}</p>
            <p className="form-email">{email}</p>

            <div className="timer-badge">
              <span className="timer-dot" />
              Code expires in {formatTime(timeLeft)}
            </div>

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
              <label className="code-label">Enter 6-digit verification code</label>
              <div className="code-grid" onPaste={handlePaste}>
                {digits.map((d, i) => (
                  <input
                    key={i}
                    ref={el => { inputRefs.current[i] = el; }}
                    className={`code-digit${d ? ' has-value' : ''}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    placeholder="·"
                    value={d}
                    onChange={e => handleDigit(i, e.target.value)}
                    onKeyDown={e => handleKeyDown(i, e)}
                    autoFocus={i === 0}
                  />
                ))}
              </div>

              <button type="submit" disabled={loading || code.length !== 6} className="submit-btn">
                {loading ? (
                  <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <>Continue <ArrowRight size={16} /></>
                )}
              </button>
            </form>

            <p className="resend-row">
              Didn't receive the code?{' '}
              <button className="resend-btn" onClick={() => setTimeLeft(299)}>
                <RefreshCw size={13} /> Resend code
              </button>
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default Verify2FA;