import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Lock, Eye, EyeOff, Loader2, CheckCircle2, ArrowLeft, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';
import api from '../../api/axios';

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setError('Ce lien de réinitialisation est invalide ou le token est manquant.');
    }
  }, [token]);

  // Validation criteria
  const hasMinLength = password.length >= 8;
  const passwordsMatch = password && confirmPassword ? password === confirmPassword : false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError('Token de réinitialisation manquant.');
      return;
    }
    if (!hasMinLength) {
      setError('Le mot de passe doit comporter au moins 8 caractères.');
      return;
    }
    if (!passwordsMatch) {
      setError('Les deux mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Échec de la réinitialisation. Le lien a peut-être expiré ou a déjà été utilisé.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&display=swap');

        .rp-root * { box-sizing: border-box; margin: 0; padding: 0; }

        .rp-root {
          display: flex;
          min-height: 100vh;
          background: #0a0a0f;
          font-family: 'DM Sans', sans-serif;
        }

        /* LEFT PANEL */
        .rp-left {
          position: relative;
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 48px 56px;
          overflow: hidden;
          background: #0d0d18;
        }
        .rp-left::before {
          content: '';
          position: absolute; inset: 0;
          background:
            radial-gradient(ellipse 75% 55% at 15% 85%, rgba(99,80,245,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 55% 45% at 85% 15%, rgba(168,85,247,0.12) 0%, transparent 55%);
          pointer-events: none;
        }
        .rp-left::after {
          content: '';
          position: absolute; top: 0; right: 0;
          width: 1px; height: 100%;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 30%, rgba(255,255,255,0.06) 70%, transparent);
        }

        .rp-logo {
          display: flex; align-items: center; gap: 12px;
          z-index: 1;
        }
        .rp-logo-icon {
          width: 40px; height: 40px; border-radius: 10px;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          display: flex; align-items: center; justify-content: center;
          color: #fff; font-size: 16px; font-weight: 700;
        }
        .rp-logo-name { font-size: 18px; font-weight: 500; color: #fff; letter-spacing: -0.3px; }

        .rp-hero { z-index: 1; }
        .rp-tagline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(32px, 3vw, 48px);
          line-height: 1.12; color: #fff;
          letter-spacing: -1px; margin-bottom: 20px;
        }
        .rp-tagline em { font-style: italic; color: #a78bfa; }
        .rp-sub {
          font-size: 15px; color: rgba(255,255,255,0.45);
          line-height: 1.65; max-width: 360px; font-weight: 300;
        }

        .rp-deco {
          position: absolute;
          top: 50%; right: 64px;
          transform: translateY(-50%) rotate(-3deg);
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 22px 26px; width: 230px;
          animation: rpFloat 6s ease-in-out infinite;
          z-index: 1;
        }
        @keyframes rpFloat {
          0%,100% { transform: translateY(-50%) rotate(-3deg); }
          50% { transform: translateY(calc(-50% - 10px)) rotate(-3deg); }
        }
        .rp-deco-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: #a78bfa; letter-spacing: 1px; margin-bottom: 12px; }
        .rp-deco-list { display: flex; flex-direction: column; gap: 8px; }
        .rp-deco-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: rgba(255,255,255,0.6); }

        .rp-stats { display: flex; gap: 40px; z-index: 1; }
        .rp-stat-num { font-family: 'DM Serif Display', serif; font-size: 26px; color: #fff; }
        .rp-stat-label { font-size: 11px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px; }

        /* RIGHT PANEL */
        .rp-right {
          width: 500px; min-width: 500px;
          display: flex; align-items: center; justify-content: center;
          padding: 48px 56px;
          background: #fff;
        }
        .rp-form-wrap { width: 100%; max-width: 380px; }

        .rp-back {
          display: inline-flex; align-items: center; gap: 7px;
          font-size: 13px; font-weight: 500;
          color: #888; text-decoration: none;
          margin-bottom: 28px;
          transition: color 0.2s;
        }
        .rp-back:hover { color: #6350f5; }

        .form-eyebrow {
          font-size: 12px; font-weight: 500;
          letter-spacing: 1.5px; text-transform: uppercase;
          color: #6350f5; margin-bottom: 10px;
        }
        .form-title {
          font-family: 'DM Serif Display', serif;
          font-size: 32px; color: #0a0a0f;
          letter-spacing: -0.8px; line-height: 1.15; margin-bottom: 8px;
        }
        .form-subtitle {
          font-size: 14px; color: #888; font-weight: 300;
          margin-bottom: 28px; line-height: 1.5;
        }

        .error-box {
          display: flex; align-items: flex-start; gap: 10px;
          background: #fff5f5; border: 1px solid #fecaca;
          color: #dc2626; padding: 12px 14px;
          border-radius: 10px; margin-bottom: 20px; font-size: 13px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
        .field-label { font-size: 13px; font-weight: 500; color: #1a1a2e; }
        .input-wrap { position: relative; }
        .input-icon {
          position: absolute; left: 14px; top: 50%;
          transform: translateY(-50%); color: #bbb;
          pointer-events: none; display: flex;
        }
        .input-toggle {
          position: absolute; right: 12px; top: 50%;
          transform: translateY(-50%); color: #999;
          background: none; border: none; cursor: pointer; display: flex;
          padding: 4px; border-radius: 6px;
        }
        .input-toggle:hover { color: #6350f5; }

        .field-input {
          width: 100%;
          padding: 13px 40px 13px 44px;
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

        .rule-checks { display: flex; flex-direction: column; gap: 6px; margin: 12px 0 20px; padding: 10px 14px; background: #f8fafc; border-radius: 8px; border: 1px solid #edf2f7; }
        .rule-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #64748b; }
        .rule-item.valid { color: #059669; font-weight: 500; }

        .submit-btn {
          width: 100%; padding: 14px 20px;
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
        .rp-success { text-align: center; padding: 20px 0; }
        .rp-success-icon {
          width: 72px; height: 72px; border-radius: 20px;
          background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(16,185,129,0.05));
          border: 1px solid rgba(16,185,129,0.2);
          display: inline-flex; align-items: center; justify-content: center;
          color: #10b981; margin-bottom: 24px;
        }
        .rp-success-title {
          font-family: 'DM Serif Display', serif;
          font-size: 30px; color: #0a0a0f;
          letter-spacing: -0.6px; margin-bottom: 10px;
        }
        .rp-success-desc {
          font-size: 14px; color: #888; font-weight: 300;
          line-height: 1.6; margin-bottom: 28px; max-width: 320px; margin-left: auto; margin-right: auto;
        }

        @media (max-width: 900px) {
          .rp-left { display: none; }
          .rp-right { width: 100%; min-width: 0; padding: 40px 24px; }
        }
      `}</style>

      <div className="rp-root">
        {/* LEFT BRAND */}
        <div className="rp-left">
          <div className="rp-logo">
            <div className="rp-logo-icon">G</div>
            <span className="rp-logo-name">Geiser Helpdesk AI</span>
          </div>

          <div className="rp-hero">
            <h1 className="rp-tagline">
              Secured.<br /><em>Protected.</em>
            </h1>
            <p className="rp-sub">
              Your security is our highest priority. Create a strong password to safeguard your ITSM workspace.
            </p>
          </div>

          <div className="rp-deco">
            <div className="rp-deco-title">Password Standards</div>
            <div className="rp-deco-list">
              <div className="rp-deco-item">
                <ShieldCheck size={14} color="#a78bfa" /> Minimum 8 characters
              </div>
              <div className="rp-deco-item">
                <ShieldCheck size={14} color="#a78bfa" /> Bcrypt cryptographic hash
              </div>
              <div className="rp-deco-item">
                <ShieldCheck size={14} color="#a78bfa" /> Single-use token invalidation
              </div>
            </div>
          </div>

          <div className="rp-stats">
            <div>
              <div className="rp-stat-num">256-bit</div>
              <div className="rp-stat-label">Encryption</div>
            </div>
            <div>
              <div className="rp-stat-num">ISO 27001</div>
              <div className="rp-stat-label">Compliant</div>
            </div>
          </div>
        </div>

        {/* RIGHT FORM */}
        <div className="rp-right">
          <div className="rp-form-wrap">
            {success ? (
              <div className="rp-success">
                <div className="rp-success-icon">
                  <CheckCircle2 size={34} />
                </div>
                <h1 className="rp-success-title">Mot de passe réinitialisé !</h1>
                <p className="rp-success-desc">
                  Votre mot de passe a été mis à jour avec succès. Vous allez être redirigé vers la page de connexion...
                </p>
                <Link to="/login" className="submit-btn" style={{ textDecoration: 'none' }}>
                  Aller à la connexion <ArrowRight size={16} />
                </Link>
              </div>
            ) : (
              <>
                <Link to="/login" className="rp-back">
                  <ArrowLeft size={15} /> Retour à la connexion
                </Link>

                <p className="form-eyebrow">Sécurité du compte</p>
                <h2 className="form-title">Nouveau mot de passe</h2>
                <p className="form-subtitle">
                  Saisissez votre nouveau mot de passe sécurisé pour réactiver votre accès.
                </p>

                {error && (
                  <div className="error-box">
                    <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>{error}</span>
                  </div>
                )}

                <form onSubmit={handleSubmit}>
                  {/* Nouveau mot de passe */}
                  <div className="field-group">
                    <label className="field-label">Nouveau mot de passe</label>
                    <div className="input-wrap">
                      <span className="input-icon"><Lock size={16} /></span>
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        className="field-input"
                        placeholder="••••••••"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="input-toggle"
                        onClick={() => setShowPassword(!showPassword)}
                        tabIndex={-1}
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* Confirmation */}
                  <div className="field-group">
                    <label className="field-label">Confirmer le mot de passe</label>
                    <div className="input-wrap">
                      <span className="input-icon"><Lock size={16} /></span>
                      <input
                        type={showConfirmPassword ? 'text' : 'password'}
                        required
                        className="field-input"
                        placeholder="••••••••"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="input-toggle"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        tabIndex={-1}
                      >
                        {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* Validation Rules Indicator */}
                  <div className="rule-checks">
                    <div className={`rule-item ${hasMinLength ? 'valid' : ''}`}>
                      <CheckCircle2 size={13} color={hasMinLength ? '#10b981' : '#cbd5e1'} />
                      Au moins 8 caractères
                    </div>
                    <div className={`rule-item ${passwordsMatch ? 'valid' : ''}`}>
                      <CheckCircle2 size={13} color={passwordsMatch ? '#10b981' : '#cbd5e1'} />
                      Les mots de passe correspondent
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !token || !hasMinLength || !passwordsMatch}
                    className="submit-btn"
                  >
                    {loading ? (
                      <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <>Valider le nouveau mot de passe <ArrowRight size={16} /></>
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

export default ResetPassword;
