import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Users, X, Plus, Loader2, CheckCircle2, Zap, Sparkles,
  Bot, Brain, TrendingUp, Shield, Target, ChevronRight, Activity
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Agent } from '../../types';
import api from '../../api/axios';

type FormData = {
  name: string;
  competencies: string[];
  agent_ids: string[];
};

/* ─────────────────────────────────────────────
   GLASS TOKEN
───────────────────────────────────────────── */
const glass: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(139,92,246,0.12)',
  backdropFilter: 'blur(20px)',
  borderRadius: '20px',
};

/* ─────────────────────────────────────────────
   PREMIUM LABELED INPUT
───────────────────────────────────────────── */
const PremiumField: React.FC<{
  label: string;
  required?: boolean;
  children: React.ReactNode;
}> = ({ label, required, children }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
    <label style={{
      fontSize: '11px', fontWeight: 700,
      color: 'rgba(255,255,255,0.35)',
      textTransform: 'uppercase', letterSpacing: '0.1em',
    }}>
      {label} {required && <span style={{ color: '#a78bfa' }}>*</span>}
    </label>
    {children}
  </div>
);

/* ─────────────────────────────────────────────
   AI ASSISTANT PANEL
───────────────────────────────────────────── */
const AIAssistantPanel: React.FC<{ formData: FormData; agentCount: number }> = ({ formData, agentCount }) => {
  const hasName = formData.name.trim().length > 0;
  const hasCompetencies = formData.competencies.length > 0;
  const hasAgents = formData.agent_ids.length > 0;

  const tips = [
    {
      show: !hasName,
      icon: <Brain size={13} />,
      color: '#a78bfa',
      text: 'Give your team a descriptive name that reflects their specialization, e.g. "Tier 2 Network Response".',
    },
    {
      show: hasName && !hasCompetencies,
      icon: <Zap size={13} />,
      color: '#f59e0b',
      text: `AI recommends adding 3–5 competencies to enable precise ticket routing for ${formData.name || 'this team'}.`,
    },
    {
      show: hasCompetencies && !hasAgents,
      icon: <Shield size={13} />,
      color: '#60a5fa',
      text: 'Assign at least 2 agents to ensure coverage. AI will balance workload automatically.',
    },
    {
      show: hasAgents && hasCompetencies && hasName,
      icon: <TrendingUp size={13} />,
      color: '#10b981',
      text: `Team looks great! ${formData.agent_ids.length} agent${formData.agent_ids.length > 1 ? 's' : ''} with ${formData.competencies.length} competencie${formData.competencies.length > 1 ? 's' : ''} — AI predicts high routing efficiency.`,
    },
  ];

  const activeTip = tips.find(t => t.show) || tips[tips.length - 1];

  const predictedMetrics = [
    { label: 'Routing Match', value: hasCompetencies ? `${75 + formData.competencies.length * 5}%` : '—' },
    { label: 'Est. Workload', value: hasAgents ? `${Math.min(40, 20 * formData.agent_ids.length)} tickets/day` : '—' },
    { label: 'SLA Forecast', value: hasAgents && hasCompetencies ? '94%' : '—' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.3, duration: 0.5 }}
      style={{
        display: 'flex', flexDirection: 'column', gap: '16px',
        position: 'sticky', top: '80px',
      }}
    >
      {/* AI Assistant card */}
      <div style={{
        ...glass,
        padding: '20px',
        borderColor: 'rgba(139,92,246,0.2)',
        background: 'rgba(124,58,237,0.05)',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Purple glow bg */}
        <div style={{
          position: 'absolute', top: '-30px', right: '-30px',
          width: '120px', height: '120px',
          background: 'radial-gradient(circle, rgba(124,58,237,0.2) 0%, transparent 70%)',
          pointerEvents: 'none', borderRadius: '50%',
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
          <div style={{
            width: '34px', height: '34px', borderRadius: '10px',
            background: 'linear-gradient(135deg, rgba(124,58,237,0.7), rgba(79,70,229,0.7))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(124,58,237,0.4)',
          }}>
            <Bot size={17} style={{ color: 'white' }} />
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'rgba(255,255,255,0.9)' }}>AI Assistant</div>
            <div style={{ fontSize: '10.5px', color: '#a78bfa', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              GEISER Intelligence
            </div>
          </div>
          <div style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px',
            padding: '3px 8px', borderRadius: '999px',
            background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)',
          }}>
            <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#10b981', animation: 'aiPulse 2s ease-in-out infinite' }} />
            <span style={{ fontSize: '10px', color: '#6ee7b7', fontWeight: 700 }}>LIVE</span>
          </div>
        </div>

        {/* Tip */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTip.text}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
            style={{
              padding: '12px 14px',
              background: 'rgba(0,0,0,0.2)',
              border: `1px solid ${activeTip.color}20`,
              borderRadius: '12px',
            }}
          >
            <div style={{ display: 'flex', gap: '8px' }}>
              <div style={{
                width: '24px', height: '24px', borderRadius: '7px', flexShrink: 0,
                background: `${activeTip.color}18`, border: `1px solid ${activeTip.color}25`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: activeTip.color,
                marginTop: '1px',
              }}>
                {activeTip.icon}
              </div>
              <p style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.6, margin: 0 }}>
                {activeTip.text}
              </p>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Predicted metrics */}
      <div style={{ ...glass, padding: '18px' }}>
        <div style={{
          fontSize: '10.5px', fontWeight: 700, color: 'rgba(255,255,255,0.25)',
          textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '14px',
          display: 'flex', alignItems: 'center', gap: '5px',
        }}>
          <Activity size={10} /> AI Predictions
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {predictedMetrics.map(m => (
            <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>{m.label}</span>
              <span style={{
                fontSize: '13px', fontWeight: 700,
                color: m.value === '—' ? 'rgba(255,255,255,0.2)' : '#a78bfa',
              }}>
                {m.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Suggested roles */}
      <div style={{ ...glass, padding: '18px' }}>
        <div style={{
          fontSize: '10.5px', fontWeight: 700, color: 'rgba(255,255,255,0.25)',
          textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px',
          display: 'flex', alignItems: 'center', gap: '5px',
        }}>
          <Target size={10} /> Suggested Competencies
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {['Network Issues', 'Cloud Infra', 'SaaS', 'Hardware', 'Security', 'Billing', 'API Support'].map(c => {
            const already = formData.competencies.includes(c);
            return (
              <span key={c} style={{
                padding: '4px 10px', borderRadius: '999px',
                fontSize: '11.5px', fontWeight: 600,
                background: already ? 'rgba(245,158,11,0.12)' : 'rgba(255,255,255,0.04)',
                border: already ? '1px solid rgba(245,158,11,0.25)' : '1px solid rgba(255,255,255,0.07)',
                color: already ? 'rgba(251,191,36,0.8)' : 'rgba(255,255,255,0.3)',
                transition: 'all 0.2s',
              }}>
                {c}
              </span>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
};

/* ─────────────────────────────────────────────
   SUCCESS SCREEN
───────────────────────────────────────────── */
const SuccessScreen: React.FC<{ teamName: string }> = ({ teamName }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '60vh', gap: '20px', textAlign: 'center',
    }}
  >
    <motion.div
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
      style={{
        width: '80px', height: '80px', borderRadius: '24px',
        background: 'linear-gradient(135deg, rgba(16,185,129,0.3), rgba(5,150,105,0.3))',
        border: '1px solid rgba(16,185,129,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 0 40px rgba(16,185,129,0.3)',
      }}
    >
      <CheckCircle2 size={38} style={{ color: '#10b981' }} />
    </motion.div>
    <div>
      <h2 style={{
        fontFamily: 'DM Serif Display, serif',
        fontSize: '28px', fontWeight: 400,
        color: 'rgba(255,255,255,0.95)', marginBottom: '8px',
      }}>
        Team Created
      </h2>
      <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.4)' }}>
        <span style={{ color: '#a78bfa', fontWeight: 600 }}>{teamName}</span> is now live. Redirecting…
      </p>
    </div>
    <div style={{ display: 'flex', gap: '6px' }}>
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.25 }}
          style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#a78bfa' }}
        />
      ))}
    </div>
  </motion.div>
);

/* ─────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────── */
const TeamCreate: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [competencyInput, setCompetencyInput] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [formData, setFormData] = useState<FormData>({ name: '', competencies: [], agent_ids: [] });

  useEffect(() => {
    api.get('/agents')
      .then(r => setAgents(r.data))
      .catch(() => setAgents([]))
      .finally(() => setAgentsLoading(false));
  }, []);

  const addCompetency = () => {
    const c = competencyInput.trim();
    if (c && !formData.competencies.includes(c)) {
      setFormData(prev => ({ ...prev, competencies: [...prev.competencies, c] }));
    }
    setCompetencyInput('');
  };

  const removeCompetency = (c: string) => {
    setFormData(prev => ({ ...prev, competencies: prev.competencies.filter(x => x !== c) }));
  };

  const toggleAgent = (id: string) => {
    setFormData(prev => ({
      ...prev,
      agent_ids: prev.agent_ids.includes(id)
        ? prev.agent_ids.filter(x => x !== id)
        : [...prev.agent_ids, id],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) { setError('Team name is required.'); return; }
    setLoading(true);
    setError('');
    try {
      await api.post('/teams', formData);
      setSuccess(true);
      setTimeout(() => navigate('/teams'), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create team.');
    } finally {
      setLoading(false);
    }
  };

  const inputBase: React.CSSProperties = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(139,92,246,0.15)',
    borderRadius: '14px', padding: '12px 16px',
    fontSize: '14px', color: 'rgba(255,255,255,0.85)',
    fontFamily: 'DM Sans, sans-serif', outline: 'none',
    transition: 'all 0.2s', width: '100%', boxSizing: 'border-box' as const,
  };

  const focusEvents = {
    onFocus: (e: React.FocusEvent<HTMLInputElement>) => {
      e.target.style.borderColor = 'rgba(139,92,246,0.5)';
      e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.1)';
      e.target.style.background = 'rgba(255,255,255,0.06)';
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.target.style.borderColor = 'rgba(139,92,246,0.15)';
      e.target.style.boxShadow = 'none';
      e.target.style.background = 'rgba(255,255,255,0.04)';
    },
  };

  if (success) return <SuccessScreen teamName={formData.name} />;

  return (
    <div style={{ paddingBottom: '60px' }}>
      {/* Back */}
      <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} style={{ marginBottom: '28px' }}>
        <Link
          to="/teams"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            color: 'rgba(255,255,255,0.35)', fontSize: '13px', fontWeight: 500,
            textDecoration: 'none', transition: 'color 0.2s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
        >
          <ArrowLeft size={16} /> Back to Teams
        </Link>
      </motion.div>

      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ marginBottom: '32px' }}
      >
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '5px',
          padding: '4px 10px', borderRadius: '999px', marginBottom: '12px',
          background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)',
          color: '#c4b5fd', fontSize: '11px', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.08em',
        }}>
          <Sparkles size={10} /> New Team
        </div>
        <h1 style={{
          fontFamily: 'DM Serif Display, serif',
          fontSize: '36px', fontWeight: 400,
          color: 'rgba(255,255,255,0.95)',
          letterSpacing: '-0.02em', lineHeight: 1.2,
        }}>
          Configure Team
        </h1>
        <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.4)', marginTop: '8px' }}>
          Define a specialized unit. The AI will route tickets to your team based on its competencies.
        </p>
      </motion.div>

      {/* Main grid: form + AI panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px', alignItems: 'start' }}>
        {/* ── Form column ── */}
        <div>
          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -8, height: 0 }}
                style={{
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: '14px', padding: '12px 16px', marginBottom: '20px',
                  fontSize: '13.5px', color: '#fca5a5', fontWeight: 500,
                }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* ── Team Name ── */}
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              style={{ ...glass, padding: '24px' }}
            >
              <h2 style={{
                fontFamily: 'DM Serif Display, serif',
                fontSize: '18px', fontWeight: 400, color: 'rgba(255,255,255,0.85)',
                marginBottom: '20px',
              }}>
                Team Identity
              </h2>

              <PremiumField label="Team Name" required>
                <input
                  type="text"
                  placeholder="e.g. Infrastructure Response Unit"
                  value={formData.name}
                  onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
                  style={inputBase}
                  required
                  {...focusEvents}
                />
              </PremiumField>
            </motion.section>

            {/* ── Competencies ── */}
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              style={{ ...glass, padding: '24px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
                <div style={{
                  width: '28px', height: '28px', borderRadius: '8px',
                  background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Zap size={14} style={{ color: '#f59e0b' }} />
                </div>
                <h2 style={{
                  fontFamily: 'DM Serif Display, serif',
                  fontSize: '18px', fontWeight: 400, color: 'rgba(255,255,255,0.85)',
                }}>
                  Competencies
                </h2>
              </div>

              <PremiumField label="Add Competency">
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input
                    type="text"
                    placeholder="e.g. Network Issues, Cloud, Billing…"
                    value={competencyInput}
                    onChange={e => setCompetencyInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCompetency(); } }}
                    style={{ ...inputBase, flex: 1 }}
                    {...focusEvents}
                  />
                  <button
                    type="button"
                    onClick={addCompetency}
                    style={{
                      padding: '0 18px', flexShrink: 0,
                      background: 'rgba(139,92,246,0.15)',
                      border: '1px solid rgba(139,92,246,0.3)',
                      borderRadius: '14px', cursor: 'pointer',
                      color: '#c4b5fd', fontSize: '13px', fontWeight: 600,
                      fontFamily: 'DM Sans, sans-serif',
                      display: 'flex', alignItems: 'center', gap: '6px',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.25)';
                      (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.5)';
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.15)';
                      (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.3)';
                    }}
                  >
                    <Plus size={15} /> Add
                  </button>
                </div>
              </PremiumField>

              {/* Tags */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '16px' }}>
                <AnimatePresence>
                  {formData.competencies.map(c => (
                    <motion.span
                      key={c}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '5px 12px',
                        background: 'rgba(245,158,11,0.1)',
                        border: '1px solid rgba(245,158,11,0.22)',
                        borderRadius: '999px', fontSize: '12.5px', fontWeight: 600,
                        color: 'rgba(251,191,36,0.85)',
                      }}
                    >
                      {c}
                      <button
                        type="button"
                        onClick={() => removeCompetency(c)}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          padding: 0, color: 'rgba(245,158,11,0.5)', display: 'flex', lineHeight: 1,
                          transition: 'color 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.color = '#f59e0b')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(245,158,11,0.5)')}
                      >
                        <X size={12} />
                      </button>
                    </motion.span>
                  ))}
                </AnimatePresence>
                {formData.competencies.length === 0 && (
                  <p style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.2)', fontStyle: 'italic', padding: '4px 0' }}>
                    Press Enter or click Add to tag competencies
                  </p>
                )}
              </div>
            </motion.section>

            {/* ── Assign Agents ── */}
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              style={{ ...glass, padding: '24px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <div style={{
                  width: '28px', height: '28px', borderRadius: '8px',
                  background: 'rgba(96,165,250,0.12)', border: '1px solid rgba(96,165,250,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Users size={14} style={{ color: '#60a5fa' }} />
                </div>
                <h2 style={{
                  fontFamily: 'DM Serif Display, serif',
                  fontSize: '18px', fontWeight: 400, color: 'rgba(255,255,255,0.85)',
                }}>
                  Assign Agents
                </h2>
                {formData.agent_ids.length > 0 && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    style={{
                      marginLeft: 'auto', padding: '3px 10px', borderRadius: '999px',
                      background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.25)',
                      fontSize: '12px', fontWeight: 700, color: '#c4b5fd',
                    }}
                  >
                    {formData.agent_ids.length} selected
                  </motion.span>
                )}
              </div>
              <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)', marginBottom: '20px', lineHeight: 1.6 }}>
                Select agents for this team. You can modify assignments anytime.
              </p>

              {agentsLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{
                      height: '68px', borderRadius: '14px',
                      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)',
                      animation: 'shimmer 1.5s infinite',
                      backgroundImage: 'linear-gradient(90deg, transparent 25%, rgba(139,92,246,0.04) 50%, transparent 75%)',
                      backgroundSize: '200% 100%',
                    }} />
                  ))}
                </div>
              ) : agents.length === 0 ? (
                <div style={{
                  textAlign: 'center', padding: '32px 20px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
                  borderRadius: '14px',
                }}>
                  <Bot size={28} style={{ color: 'rgba(255,255,255,0.15)', marginBottom: '10px' }} />
                  <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.35)' }}>
                    No agents available.{' '}
                    <Link to="/agents/create" style={{ color: '#a78bfa', fontWeight: 600, textDecoration: 'none' }}>
                      Create one first →
                    </Link>
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {agents.map((agent, i) => {
                    const selected = formData.agent_ids.includes(agent.id);
                    return (
                      <motion.label
                        key={agent.id}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '14px',
                          padding: '14px 16px', borderRadius: '14px', cursor: 'pointer',
                          background: selected ? 'rgba(139,92,246,0.08)' : 'rgba(255,255,255,0.02)',
                          border: `1px solid ${selected ? 'rgba(139,92,246,0.25)' : 'rgba(255,255,255,0.05)'}`,
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={e => {
                          if (!selected) {
                            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.15)';
                          }
                        }}
                        onMouseLeave={e => {
                          if (!selected) {
                            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.02)';
                            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.05)';
                          }
                        }}
                      >
                        {/* Custom checkbox */}
                        <div
                          onClick={() => toggleAgent(agent.id)}
                          style={{
                            width: '20px', height: '20px', borderRadius: '6px', flexShrink: 0,
                            background: selected ? 'rgba(139,92,246,0.4)' : 'rgba(255,255,255,0.06)',
                            border: `1.5px solid ${selected ? 'rgba(139,92,246,0.7)' : 'rgba(255,255,255,0.15)'}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'all 0.15s',
                          }}
                        >
                          {selected && <div style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'white' }} />}
                        </div>

                        {/* Avatar */}
                        <div style={{
                          width: '40px', height: '40px', borderRadius: '12px', flexShrink: 0,
                          background: selected
                            ? 'linear-gradient(135deg, rgba(124,58,237,0.5), rgba(79,70,229,0.5))'
                            : 'rgba(255,255,255,0.08)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '13px', fontWeight: 700, color: selected ? 'white' : 'rgba(255,255,255,0.4)',
                          transition: 'all 0.2s',
                        }}>
                          {agent.id?.slice(-2).toUpperCase() ?? 'AI'}
                        </div>

                        <div style={{ flex: 1 }} onClick={() => toggleAgent(agent.id)}>
                          <p style={{ fontSize: '13.5px', fontWeight: 600, color: 'rgba(255,255,255,0.85)', marginBottom: '3px' }}>
                            Agent{' '}
                            <span style={{ fontFamily: 'monospace', color: '#a78bfa', fontSize: '12px' }}>
                              #{agent.id?.slice(-6).toUpperCase() ?? 'N/A'}
                            </span>
                          </p>
                          <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.3)' }}>
                            {agent.skills.slice(0, 3).join(', ') || 'No skills defined'}
                            {agent.skills.length > 3 ? ` +${agent.skills.length - 3}` : ''}
                          </p>
                        </div>

                        <span style={{
                          padding: '3px 9px', borderRadius: '999px', fontSize: '10.5px', fontWeight: 700,
                          flexShrink: 0,
                          background: agent.is_available ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.08)',
                          border: agent.is_available ? '1px solid rgba(16,185,129,0.2)' : '1px solid rgba(239,68,68,0.15)',
                          color: agent.is_available ? '#6ee7b7' : '#fca5a5',
                          letterSpacing: '0.04em',
                        }}>
                          {agent.is_available ? 'Available' : 'Busy'}
                        </span>
                      </motion.label>
                    );
                  })}
                </div>
              )}
            </motion.section>

            {/* ── Actions ── */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', paddingTop: '8px' }}
            >
              <button
                type="button"
                onClick={() => navigate(-1)}
                style={{
                  padding: '12px 24px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '14px', color: 'rgba(255,255,255,0.45)',
                  fontSize: '14px', fontWeight: 600, cursor: 'pointer',
                  fontFamily: 'DM Sans, sans-serif', transition: 'all 0.2s',
                }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'}
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '12px 32px',
                  background: loading
                    ? 'rgba(124,58,237,0.4)'
                    : 'linear-gradient(135deg, rgba(124,58,237,0.85), rgba(79,70,229,0.85))',
                  border: '1px solid rgba(167,139,250,0.3)',
                  borderRadius: '14px', color: 'white',
                  fontSize: '14px', fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontFamily: 'DM Sans, sans-serif',
                  display: 'flex', alignItems: 'center', gap: '8px',
                  boxShadow: loading ? 'none' : '0 4px 20px rgba(124,58,237,0.4)',
                  transition: 'all 0.2s', opacity: loading ? 0.8 : 1,
                }}
                onMouseEnter={e => {
                  if (!loading) {
                    (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 28px rgba(124,58,237,0.6)';
                    (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
                  }
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.boxShadow = loading ? 'none' : '0 4px 20px rgba(124,58,237,0.4)';
                  (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
                }}
              >
                {loading ? (
                  <>
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                    Creating team…
                  </>
                ) : (
                  <>
                    <Users size={16} /> Create Team
                    <ChevronRight size={14} />
                  </>
                )}
              </button>
            </motion.div>
          </form>
        </div>

        {/* ── AI Assistant Panel ── */}
        <div>
          <AIAssistantPanel formData={formData} agentCount={agents.length} />
        </div>
      </div>
    </div>
  );
};

export default TeamCreate;