import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, UserPlus, X, Plus, Loader2, CheckCircle2,
  Cpu, Target, TrendingUp, Brain
} from 'lucide-react';

import api from '../../api/axios';

/* ─── Styles ──────────────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('agentcreate-styles')) return;
  const style = document.createElement('style');
  style.id = 'agentcreate-styles';
  style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');

    @keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }
    @keyframes float-slow { 0%,100%{transform:translateY(0) rotate(0deg)} 50%{transform:translateY(-10px) rotate(2deg)} }
    @keyframes float-med { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }
    @keyframes slide-right { from{opacity:0;transform:translateX(-24px)} to{opacity:1;transform:translateX(0)} }
    @keyframes slide-left { from{opacity:0;transform:translateX(24px)} to{opacity:1;transform:translateX(0)} }
    @keyframes fade-up { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
    @keyframes spin { to{transform:rotate(360deg)} }
    @keyframes success-pop { 0%{transform:scale(.5);opacity:0} 70%{transform:scale(1.15)} 100%{transform:scale(1);opacity:1} }
    @keyframes orbit { from{transform:rotate(0deg) translateX(60px) rotate(0deg)} to{transform:rotate(360deg) translateX(60px) rotate(-360deg)} }

    .skill-tag { transition: all .2s ease; }
    .skill-tag:hover { background: rgba(139,92,246,.25) !important; border-color: rgba(139,92,246,.5) !important; }

    .ac-input {
      width: 100%; padding: .875rem 1.125rem;
      background: rgba(255,255,255,.04); border: 1.5px solid rgba(255,255,255,.1);
      border-radius: 12px; color: rgba(255,255,255,.85);
      font-size: .9375rem; font-family: 'DM Sans', sans-serif;
      outline: none; transition: border-color .2s, box-shadow .2s, background .2s;
      box-sizing: border-box;
    }
    .ac-input::placeholder { color: rgba(255,255,255,.25); }
    .ac-input:focus {
      border-color: rgba(139,92,246,.6);
      box-shadow: 0 0 0 3px rgba(139,92,246,.15);
      background: rgba(139,92,246,.06);
    }
    .ac-input option { background: #1a1a2e; color: #e2e8f0; }

    .submit-btn:hover { transform: translateY(-2px) !important; box-shadow: 0 16px 40px rgba(139,92,246,.5) !important; }
    .submit-btn:active { transform: translateY(0) !important; }

    .stat-item { transition: all .2s ease; }
    .stat-item:hover { background: rgba(255,255,255,.05) !important; }
  `;
  document.head.appendChild(style);
};

/* ─── AI Suggestion Widget ────────────────────────────────── */
const AiSuggestionCard: React.FC<{
  title: string; body: string; icon: React.ReactNode;
  color: string; delay?: number;
}> = ({ title, body, icon, color, delay = 0 }) => (
  <div style={{
    padding: '1rem 1.125rem',
    background: `rgba(${color},0.07)`, border: `1px solid rgba(${color},0.2)`,
    borderRadius: 14, animation: `fade-up .5s ease ${delay}ms both`,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '.625rem', marginBottom: '.5rem' }}>
      <div style={{ color: `rgb(${color})`, flexShrink: 0 }}>{icon}</div>
      <span style={{ fontSize: '.75rem', fontWeight: 700, color: `rgb(${color})`, letterSpacing: '.04em' }}>{title}</span>
      <div style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: `rgb(${color})`, animation: 'pulse-dot 2s infinite', flexShrink: 0 }} />
    </div>
    <p style={{ fontSize: '.8rem', color: 'rgba(255,255,255,.5)', lineHeight: 1.55, margin: 0 }}>{body}</p>
  </div>
);

/* ─── Left panel stat ─────────────────────────────────────── */
const StatChip: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div className="stat-item" style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '.75rem 1rem', borderRadius: 10,
    background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)',
    cursor: 'default',
  }}>
    <span style={{ fontSize: '.8rem', color: 'rgba(255,255,255,.4)', fontWeight: 500 }}>{label}</span>
    <span style={{ fontSize: '.9rem', fontWeight: 700, color }}>{value}</span>
  </div>
);

/* ─── Success screen ──────────────────────────────────────── */
const SuccessScreen: React.FC = () => (
  <div style={{
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    minHeight: '60vh', gap: '1.5rem', fontFamily: "'DM Sans', sans-serif",
  }}>
    <div style={{ position: 'relative', width: 100, height: 100 }}>
      <div style={{
        width: 100, height: 100, borderRadius: '50%',
        background: 'linear-gradient(135deg, rgba(16,185,129,.2), rgba(139,92,246,.2))',
        border: '2px solid rgba(16,185,129,.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'success-pop .6s cubic-bezier(.34,1.56,.64,1) both',
        boxShadow: '0 0 40px rgba(16,185,129,.2)',
      }}>
        <CheckCircle2 size={44} style={{ color: '#34d399' }} />
      </div>
    </div>
    <div style={{ textAlign: 'center' }}>
      <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: '2rem', color: '#f1f5f9', margin: '0 0 .5rem' }}>
        Agent <span style={{ fontStyle: 'italic', color: '#a78bfa' }}>Onboarded</span>
      </h2>
      <p style={{ color: 'rgba(255,255,255,.4)', fontSize: '.9375rem' }}>Redirecting to your workforce dashboard…</p>
    </div>
  </div>
);

/* ─── MAIN ────────────────────────────────────────────────── */
type FormData = {
  user_id: string;
  skills: string[];
  is_available: boolean;
  workload: number;
};

const AgentCreate: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [skillInput, setSkillInput] = useState('');
  const [formData, setFormData] = useState<FormData>({
    user_id: '', skills: [], is_available: true, workload: 0,
  });

  useEffect(() => { injectStyles(); }, []);

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !formData.skills.includes(s)) setFormData(p => ({ ...p, skills: [...p.skills, s] }));
    setSkillInput('');
  };

  const removeSkill = (s: string) => setFormData(p => ({ ...p, skills: p.skills.filter(x => x !== s) }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.user_id.trim()) { setError('User ID is required.'); return; }
    setLoading(true); setError('');
    try {
      await api.post('/agents', formData);
      setSuccess(true);
      setTimeout(() => navigate('/agents'), 1800);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create agent. Please try again.');
    } finally { setLoading(false); }
  };

  const aiSuggestions = [
    {
      title: 'Team Recommendation',
      body: 'AI suggests assigning to Infrastructure Support based on detected skill profile.',
      icon: <Brain size={14} />,
      color: '139,92,246',
    },
    {
      title: 'Predicted Performance',
      body: 'Estimated 88% SLA compliance in first 30 days — above team average.',
      icon: <TrendingUp size={14} />,
      color: '16,185,129',
    },
    {
      title: 'Skill Match',
      body: 'High alignment with current high-demand ticket categories.',
      icon: <Target size={14} />,
      color: '59,130,246',
    },
  ];

  if (success) return <SuccessScreen />;

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif", display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Back link */}
      <Link to="/agents" style={{
        display: 'inline-flex', alignItems: 'center', gap: '.5rem',
        color: 'rgba(255,255,255,.35)', fontWeight: 600, fontSize: '.875rem',
        textDecoration: 'none', transition: 'color .2s',
        width: 'fit-content',
      }}>
        <ArrowLeft size={16} /> Back to Workforce
      </Link>

      {/* Main split layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.3fr)', gap: '2rem', alignItems: 'start' }}>

        {/* ── LEFT PANEL ─────────────────────────────────────── */}
        <div style={{
          position: 'relative', borderRadius: 24, overflow: 'hidden',
          background: 'linear-gradient(160deg, rgba(20,10,45,.97) 0%, rgba(10,10,22,.97) 100%)',
          border: '1px solid rgba(139,92,246,.2)',
          padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.75rem',
          animation: 'slide-right .6s ease both',
        }}>
          {/* Ambient orbs */}
          <div style={{ position: 'absolute', top: -60, right: -60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(139,92,246,.25) 0%, transparent 70%)', pointerEvents: 'none', animation: 'float-slow 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', bottom: 40, left: -40, width: 160, height: 160, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,.15) 0%, transparent 70%)', pointerEvents: 'none', animation: 'float-med 8s ease-in-out infinite' }} />

          {/* Label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#8b5cf6', animation: 'pulse-dot 2s infinite' }} />
            <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(139,92,246,.7)', letterSpacing: '.1em', textTransform: 'uppercase' }}>
              AI Workforce Onboarding
            </span>
          </div>

          {/* Heading */}
          <div style={{ position: 'relative' }}>
            <h1 style={{
              fontFamily: "'DM Serif Display', serif",
              fontSize: 'clamp(1.75rem, 3vw, 2.5rem)', color: '#f1f5f9',
              lineHeight: 1.15, letterSpacing: '-0.02em', margin: 0,
            }}>
              Build your{' '}
              <span style={{
                fontStyle: 'italic',
                background: 'linear-gradient(135deg, #a78bfa, #ec4899)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                support workforce.
              </span>
            </h1>
            <p style={{ color: 'rgba(255,255,255,.4)', marginTop: '.875rem', fontSize: '.875rem', lineHeight: 1.65 }}>
              AI-powered onboarding assigns agents to the right teams, predicts their performance, and ensures optimal workload distribution across your enterprise.
            </p>
          </div>

          {/* AI suggestions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.625rem' }}>
            {aiSuggestions.map((s, i) => (
              <AiSuggestionCard key={i} {...s} delay={i * 120} />
            ))}
          </div>

          {/* Bottom stats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <div style={{ fontSize: '.7rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: '.25rem' }}>
              Team Performance
            </div>
            <StatChip label="Avg Agent Productivity" value="87%" color="#a78bfa" />
            <StatChip label="SLA Success Rate" value="92%" color="#34d399" />
            <StatChip label="Team Efficiency Index" value="94/100" color="#60a5fa" />
          </div>
        </div>

        {/* ── RIGHT PANEL (FORM) ─────────────────────────────── */}
        <div style={{
          borderRadius: 24, overflow: 'hidden',
          background: 'rgba(15,12,28,.85)', border: '1px solid rgba(255,255,255,.09)',
          backdropFilter: 'blur(24px)', padding: '2rem',
          display: 'flex', flexDirection: 'column', gap: '0',
          animation: 'slide-left .6s ease both',
          boxShadow: '0 32px 64px rgba(0,0,0,.4)',
        }}>
          {/* Form header */}
          <div style={{ marginBottom: '1.75rem' }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14, marginBottom: '1rem',
              background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <UserPlus size={22} style={{ color: '#a78bfa' }} />
            </div>
            <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: '1.625rem', color: '#f1f5f9', margin: '0 0 .375rem', letterSpacing: '-0.02em' }}>
              Agent Configuration
            </h2>
            <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.35)', margin: 0 }}>
              Configure agent profile and AI will handle team placement.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              marginBottom: '1.25rem', padding: '.875rem 1rem',
              background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)',
              borderRadius: 10, color: '#f87171', fontSize: '.875rem', fontWeight: 600,
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.375rem' }}>
            {/* User ID */}
            <FormField label="User ID" required hint="The user must be registered. Their role will be upgraded to AGENT.">
              <input
                className="ac-input"
                type="text"
                placeholder="Paste the MongoDB user _id here"
                value={formData.user_id}
                onChange={e => setFormData(p => ({ ...p, user_id: e.target.value }))}
                required
              />
            </FormField>

            {/* Skills */}
            <FormField label="Skills & Expertise" hint="Press Enter or click Add to tag skills.">
              <div style={{ display: 'flex', gap: '.625rem' }}>
                <input
                  className="ac-input"
                  type="text"
                  placeholder="e.g. Technical Support, Billing…"
                  value={skillInput}
                  onChange={e => setSkillInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                  style={{ flex: 1 }}
                />
                <button type="button" onClick={addSkill} style={{
                  padding: '.875rem 1.125rem', borderRadius: 12, flexShrink: 0,
                  background: 'rgba(139,92,246,.2)', border: '1.5px solid rgba(139,92,246,.35)',
                  color: '#c4b5fd', fontWeight: 700, fontSize: '.875rem', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '.35rem', transition: 'all .2s',
                }}>
                  <Plus size={15} /> Add
                </button>
              </div>
              {/* Tags */}
              {formData.skills.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.425rem', marginTop: '.75rem' }}>
                  {formData.skills.map(skill => (
                    <span key={skill} className="skill-tag" style={{
                      display: 'flex', alignItems: 'center', gap: '.375rem',
                      padding: '.35rem .75rem',
                      background: 'rgba(139,92,246,.12)', color: '#c4b5fd',
                      border: '1px solid rgba(139,92,246,.25)', borderRadius: 999,
                      fontSize: '.78rem', fontWeight: 600,
                    }}>
                      {skill}
                      <button type="button" onClick={() => removeSkill(skill)} style={{
                        background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                        color: 'rgba(196,181,253,.5)', lineHeight: 1, display: 'flex', alignItems: 'center',
                        transition: 'color .15s',
                      }}>
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {formData.skills.length === 0 && (
                <p style={{ marginTop: '.625rem', fontSize: '.78rem', color: 'rgba(255,255,255,.2)', fontStyle: 'italic' }}>
                  No skills added yet.
                </p>
              )}
            </FormField>

            {/* Availability toggle */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '1rem 1.125rem', borderRadius: 12,
              background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.07)',
            }}>
              <div>
                <div style={{ fontSize: '.875rem', fontWeight: 600, color: 'rgba(255,255,255,.7)', marginBottom: '.2rem' }}>
                  Available for assignment
                </div>
                <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.3)' }}>
                  Agent will receive ticket assignments immediately
                </div>
              </div>
              {/* Toggle switch */}
              <div
                onClick={() => setFormData(p => ({ ...p, is_available: !p.is_available }))}
                style={{
                  width: 48, height: 26, borderRadius: 999, cursor: 'pointer',
                  background: formData.is_available ? 'rgba(139,92,246,.5)' : 'rgba(255,255,255,.1)',
                  border: `1.5px solid ${formData.is_available ? 'rgba(139,92,246,.7)' : 'rgba(255,255,255,.15)'}`,
                  position: 'relative', transition: 'all .3s ease', flexShrink: 0,
                  boxShadow: formData.is_available ? '0 0 16px rgba(139,92,246,.3)' : 'none',
                }}>
                <div style={{
                  position: 'absolute', top: 3, width: 18, height: 18, borderRadius: '50%',
                  background: formData.is_available ? '#c4b5fd' : 'rgba(255,255,255,.3)',
                  left: formData.is_available ? 25 : 3,
                  transition: 'left .3s ease, background .3s ease',
                }} />
              </div>
            </div>

            {/* AI insight strip */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '.75rem',
              padding: '.875rem 1rem', borderRadius: 12,
              background: 'rgba(139,92,246,.07)', border: '1px solid rgba(139,92,246,.15)',
            }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(139,92,246,.15)', border: '1px solid rgba(139,92,246,.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Cpu size={15} style={{ color: '#a78bfa' }} />
              </div>
              <div>
                <div style={{ fontSize: '.75rem', fontWeight: 700, color: 'rgba(167,139,250,.8)', marginBottom: '.15rem' }}>AI Confidence: 94%</div>
                <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', lineHeight: 1.4 }}>
                  Profile matches Infrastructure team. Predicted top-quartile performance.
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '.875rem', paddingTop: '.25rem' }}>
              <button type="button" onClick={() => navigate(-1)} style={{
                padding: '.875rem 1.5rem', borderRadius: 12,
                background: 'rgba(255,255,255,.04)', border: '1.5px solid rgba(255,255,255,.1)',
                color: 'rgba(255,255,255,.4)', fontWeight: 700, fontSize: '.9375rem', cursor: 'pointer',
                transition: 'all .2s', fontFamily: "'DM Sans', sans-serif",
              }}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="submit-btn"
                style={{
                  flex: 1, padding: '.875rem 1.5rem', borderRadius: 12,
                  background: loading ? 'rgba(139,92,246,.3)' : 'linear-gradient(135deg, #7c3aed, #8b5cf6)',
                  color: loading ? 'rgba(255,255,255,.5)' : '#fff',
                  fontWeight: 700, fontSize: '.9375rem', border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: loading ? 'none' : '0 8px 24px rgba(139,92,246,.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '.5rem',
                  transition: 'all .25s ease', fontFamily: "'DM Sans', sans-serif",
                }}>
                {loading ? (
                  <><Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> Onboarding…</>
                ) : (
                  <><UserPlus size={18} /> Onboard Agent</>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

/* ─── Form field wrapper ──────────────────────────────────── */
const FormField: React.FC<{
  label: string; required?: boolean; hint?: string; children: React.ReactNode;
}> = ({ label, required, hint, children }) => (
  <div>
    <label style={{
      display: 'block', marginBottom: '.5rem',
      fontSize: '.78rem', fontWeight: 700, color: 'rgba(255,255,255,.45)',
      letterSpacing: '.05em', textTransform: 'uppercase',
    }}>
      {label} {required && <span style={{ color: '#f87171' }}>*</span>}
    </label>
    {children}
    {hint && (
      <p style={{ marginTop: '.4rem', fontSize: '.75rem', color: 'rgba(255,255,255,.25)', lineHeight: 1.5 }}>
        {hint}
      </p>
    )}
  </div>
);

export default AgentCreate;