import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  UserPlus, Search, RefreshCw, Zap, TrendingUp,
  AlertTriangle, CheckCircle2, XCircle, Activity,
  MoreHorizontal, Edit3, Trash2, Shield, Star,
  Users, Clock, Target, Award, ChevronRight, Cpu,
  X, Save, Loader2,
} from 'lucide-react';
import { type Agent, UserRole } from '../../types';
import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import toast from 'react-hot-toast';
import { AnimatePresence, motion } from 'framer-motion';

/* ─── Keyframe injection ─────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('agentlist-styles')) return;
  const style = document.createElement('style');
  style.id = 'agentlist-styles';
  style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');

    @keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.85)} }
    @keyframes float-card { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
    @keyframes shimmer { 0%{background-position:-700px 0} 100%{background-position:700px 0} }
    @keyframes glow-pulse { 0%,100%{box-shadow:0 0 20px rgba(139,92,246,.25)} 50%{box-shadow:0 0 40px rgba(139,92,246,.5)} }
    @keyframes slide-in { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
    @keyframes bar-fill { from{width:0} to{width:var(--w)} }
    @keyframes spin { to{transform:rotate(360deg)} }

    .agent-row:hover { background: rgba(139,92,246,.06) !important; }
    .agent-row { transition: background .2s ease; }

    .kpi-card:hover .kpi-glow { opacity: 1 !important; }
    .kpi-card { transition: transform .3s ease, box-shadow .3s ease; }
    .kpi-card:hover { transform: translateY(-4px) !important; box-shadow: 0 24px 48px rgba(0,0,0,.4) !important; }

    .filter-btn.active {
      background: rgba(139,92,246,.2) !important;
      border-color: rgba(139,92,246,.5) !important;
      color: #c4b5fd !important;
    }
    .filter-btn:hover { background: rgba(255,255,255,.06) !important; }

    .action-btn:hover { background: rgba(139,92,246,.15) !important; color: #c4b5fd !important; }
    .delete-btn:hover { background: rgba(239,68,68,.15) !important; color: #f87171 !important; }

    .insight-widget { animation: float-card 4s ease-in-out infinite; }
    .insight-widget:nth-child(2) { animation-delay: -1s; }
    .insight-widget:nth-child(3) { animation-delay: -2s; }
    .insight-widget:nth-child(4) { animation-delay: -3s; }

    .shimmer-card {
      background: linear-gradient(90deg, rgba(255,255,255,.03) 25%, rgba(255,255,255,.08) 50%, rgba(255,255,255,.03) 75%);
      background-size: 700px 100%;
      animation: shimmer 1.5s infinite linear;
    }

    .edit-modal-input:focus {
      border-color: rgba(139,92,246,.5) !important;
      box-shadow: 0 0 0 3px rgba(139,92,246,.1) !important;
    }
    .toggle-track { transition: background .2s ease; }
  `;
  document.head.appendChild(style);
};

/* ─── Mini sparkline ──────────────────────────────────────── */
const Sparkline: React.FC<{ values: number[]; color?: string }> = ({
  values, color = '#8b5cf6'
}) => {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const h = 28, w = 60;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / (max - min + 1)) * h;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" opacity=".8" />
    </svg>
  );
};

/* ─── KPI Card ────────────────────────────────────────────── */
const KpiCard: React.FC<{
  label: string; value: string | number; insight: string;
  icon: React.ReactNode; sparkData?: number[]; color: string; delay?: number;
}> = ({ label, value, insight, icon, sparkData, color, delay = 0 }) => (
  <div className="kpi-card" style={{
    position: 'relative', borderRadius: '20px', padding: '1.5rem',
    background: 'rgba(15,15,25,.7)', border: '1px solid rgba(255,255,255,.08)',
    backdropFilter: 'blur(20px)', overflow: 'hidden',
    animation: `slide-in .5s ease ${delay}ms both`,
    cursor: 'default',
  }}>
    <div className="kpi-glow" style={{
      position: 'absolute', inset: 0, opacity: 0,
      background: `radial-gradient(circle at 50% 0%, ${color}20 0%, transparent 70%)`,
      transition: 'opacity .4s ease', pointerEvents: 'none',
    }} />
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '.875rem' }}>
      <div style={{
        width: 40, height: 40, borderRadius: 12,
        background: `${color}20`, border: `1px solid ${color}40`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', color,
        flexShrink: 0,
      }}>{icon}</div>
      {sparkData && <Sparkline values={sparkData} color={color} />}
    </div>
    <div style={{
      fontFamily: "'DM Serif Display', serif", fontSize: '2rem', color: '#f1f5f9',
      letterSpacing: '-0.02em', lineHeight: 1, marginBottom: '.375rem',
    }}>{value}</div>
    <div style={{ fontSize: '.75rem', fontWeight: 600, color: 'rgba(255,255,255,.4)', letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: '.625rem' }}>
      {label}
    </div>
    <div style={{
      display: 'flex', alignItems: 'center', gap: '.375rem',
      background: `${color}12`, border: `1px solid ${color}25`,
      borderRadius: 8, padding: '.375rem .625rem',
    }}>
      <div style={{ width: 5, height: 5, borderRadius: '50%', background: color, animation: 'pulse-dot 2s infinite', flexShrink: 0 }} />
      <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.55)', lineHeight: 1.4 }}>{insight}</span>
    </div>
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${color}60, transparent)` }} />
  </div>
);

/* ─── Role badge ──────────────────────────────────────────── */
const RoleBadge: React.FC<{ role?: string }> = ({ role }) => {
  const cfg: Record<string, { label: string; bg: string; color: string; border: string }> = {
    admin: { label: 'Admin', bg: 'rgba(139,92,246,.18)', color: '#c4b5fd', border: 'rgba(139,92,246,.35)' },
    senior: { label: 'Senior', bg: 'rgba(59,130,246,.18)', color: '#93c5fd', border: 'rgba(59,130,246,.35)' },
    default: { label: 'Agent', bg: 'rgba(255,255,255,.06)', color: 'rgba(255,255,255,.45)', border: 'rgba(255,255,255,.12)' },
  };
  const c = cfg[role?.toLowerCase() ?? ''] ?? cfg.default;
  return (
    <span style={{ padding: '.25rem .625rem', borderRadius: 999, fontSize: '.7rem', fontWeight: 700, letterSpacing: '.04em', background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>
      {c.label}
    </span>
  );
};

/* ─── Progress bar ────────────────────────────────────────── */
const ProgressBar: React.FC<{ value: number; color?: string }> = ({ value, color }) => {
  const clamp = Math.min(Math.max(value, 0), 100);
  const hue = color ?? (clamp > 80 ? '#f97316' : clamp > 60 ? '#8b5cf6' : '#10b981');
  return (
    <div style={{ height: 4, borderRadius: 999, background: 'rgba(255,255,255,.08)', overflow: 'hidden', width: '100%' }}>
      <div style={{
        height: '100%', borderRadius: 999, width: `${clamp}%`,
        background: `linear-gradient(90deg, ${hue}, ${hue}aa)`,
        transition: 'width .8s cubic-bezier(.4,0,.2,1)',
      }} />
    </div>
  );
};

/* ─── Agent row ───────────────────────────────────────────── */
const AgentRow: React.FC<{
  agent: Agent; index: number;
  onEdit: () => void; onDelete: () => void; isAdmin: boolean;
}> = ({ agent, index, onEdit, onDelete, isAdmin }) => {
  const hue = agent.id ? (parseInt(agent.id.slice(-3), 16) % 360) : 240;
  const initials = agent.id ? agent.id.slice(-2).toUpperCase() : '??';
  const shortId = agent.id ? agent.id.slice(-6).toUpperCase() : 'N/A';
  const productivity = Math.round(65 + (parseInt(agent.id?.slice(-2) ?? '30', 16) % 35));
  const sla = Math.round(82 + (parseInt(agent.id?.slice(-4, -2) ?? '10', 16) % 18));

  return (
    <tr className="agent-row" style={{
      animation: `slide-in .4s ease ${index * 60}ms both`,
      borderBottom: '1px solid rgba(255,255,255,.04)',
    }}>
      <td style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.875rem' }}>
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 14,
              background: `hsla(${hue},60%,15%,1)`, border: `1px solid hsla(${hue},60%,35%,.4)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'DM Serif Display', serif", fontSize: '.9rem',
              color: `hsl(${hue},70%,70%)`, fontWeight: 400,
            }}>{initials}</div>
            <div style={{
              position: 'absolute', bottom: 1, right: 1, width: 9, height: 9,
              borderRadius: '50%', background: agent.is_available ? '#10b981' : '#64748b',
              border: '2px solid #0a0a14',
              animation: agent.is_available ? 'pulse-dot 2.5s infinite' : 'none',
            }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '.875rem' }}>
              Agent <span style={{ fontFamily: 'monospace', fontSize: '.75rem', color: 'rgba(139,92,246,.8)' }}>#{shortId}</span>
            </div>
            <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.35)', marginTop: 2 }}>
              {agent.is_available
                ? <span style={{ color: '#10b981' }}>● Online</span>
                : <span style={{ color: '#64748b' }}>● Offline</span>}
            </div>
          </div>
        </div>
      </td>

      <td style={{ padding: '1rem .75rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.3rem', maxWidth: 220 }}>
          {agent.skills.slice(0, 3).map((s, i) => (
            <span key={i} style={{
              padding: '.2rem .55rem', borderRadius: 999,
              background: 'rgba(139,92,246,.12)', color: 'rgba(196,181,253,.8)',
              border: '1px solid rgba(139,92,246,.2)', fontSize: '.68rem', fontWeight: 600,
            }}>{s}</span>
          ))}
          {agent.skills.length > 3 && (
            <span style={{ padding: '.2rem .55rem', borderRadius: 999, background: 'rgba(255,255,255,.05)', color: 'rgba(255,255,255,.35)', fontSize: '.68rem' }}>
              +{agent.skills.length - 3}
            </span>
          )}
          {agent.skills.length === 0 && <span style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.25)', fontStyle: 'italic' }}>—</span>}
        </div>
      </td>

      <td style={{ padding: '1rem .75rem', minWidth: 120 }}>
        <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', marginBottom: '.35rem' }}>
          <span style={{ color: '#8b5cf6', fontWeight: 700 }}>{productivity}%</span>
        </div>
        <ProgressBar value={productivity} color="#8b5cf6" />
      </td>

      <td style={{ padding: '1rem .75rem', minWidth: 120 }}>
        <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', marginBottom: '.35rem' }}>
          <span style={{ color: agent.workload > 80 ? '#f97316' : '#e2e8f0', fontWeight: 700 }}>{agent.workload}%</span>
        </div>
        <ProgressBar value={agent.workload} />
      </td>

      <td style={{ padding: '1rem .75rem' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '.35rem',
          padding: '.3rem .7rem', borderRadius: 999,
          background: sla >= 90 ? 'rgba(16,185,129,.12)' : 'rgba(251,146,60,.12)',
          border: `1px solid ${sla >= 90 ? 'rgba(16,185,129,.25)' : 'rgba(251,146,60,.25)'}`,
        }}>
          <span style={{ fontSize: '.7rem', fontWeight: 700, color: sla >= 90 ? '#34d399' : '#fb923c' }}>{sla}%</span>
        </div>
      </td>

      <td style={{ padding: '1rem .75rem' }}>
        <RoleBadge role="agent" />
      </td>

      <td style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.375rem' }}>
          <button className="action-btn" onClick={onEdit} style={{
            padding: '.375rem .75rem', borderRadius: 8,
            background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
            color: 'rgba(255,255,255,.5)', fontSize: '.75rem', fontWeight: 600,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '.3rem',
            transition: 'all .2s',
          }}>
            <Edit3 size={12} /> Edit
          </button>
          {isAdmin && (
            <button className="delete-btn" onClick={onDelete} style={{
              padding: '.375rem', borderRadius: 8,
              background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
              color: 'rgba(255,255,255,.3)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', transition: 'all .2s',
            }}>
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
};

/* ─── Skeleton row ────────────────────────────────────────── */
const SkeletonRow: React.FC<{ index: number }> = ({ index }) => (
  <tr style={{ borderBottom: '1px solid rgba(255,255,255,.04)', animationDelay: `${index * 80}ms` }}>
    {[44, 160, 100, 100, 60, 60, 80].map((w, i) => (
      <td key={i} style={{ padding: '1rem 1.25rem' }}>
        <div className="shimmer-card" style={{ height: i === 0 ? 44 : 12, width: w, borderRadius: i === 0 ? 14 : 4 }} />
      </td>
    ))}
  </tr>
);

/* ─── Edit Modal ──────────────────────────────────────────── */
interface EditModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: Agent | null;
  form: { skills: string; is_available: boolean };
  onChange: (field: 'skills' | 'is_available', value: string | boolean) => void;
  onSubmit: (e: React.FormEvent) => void;
  saving: boolean;
}

const EditModal: React.FC<EditModalProps> = ({ isOpen, onClose, agent, form, onChange, onSubmit, saving }) => {
  const shortId = agent?.id ? agent.id.slice(-6).toUpperCase() : '';
  const hue = agent?.id ? (parseInt(agent.id.slice(-3), 16) % 360) : 240;

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '11px 14px',
    background: 'rgba(255,255,255,.04)',
    border: '1px solid rgba(139,92,246,.15)',
    borderRadius: '12px', fontSize: '14px',
    color: 'rgba(255,255,255,.85)',
    fontFamily: "'DM Sans', sans-serif", outline: 'none',
    transition: 'all .2s', boxSizing: 'border-box',
  };

  const skillChips = form.skills.split(',').map(s => s.trim()).filter(Boolean);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0, zIndex: 999,
              background: 'rgba(0,0,0,0.65)',
              backdropFilter: 'blur(6px)',
            }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.96, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 20 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            style={{
              position: 'fixed', inset: 0, zIndex: 1000,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: '24px', pointerEvents: 'none',
            }}
          >
            <div style={{
              width: '100%', maxWidth: '460px', pointerEvents: 'all',
              background: 'rgba(13,13,26,0.94)',
              border: '1px solid rgba(139,92,246,.22)',
              backdropFilter: 'blur(36px)',
              borderRadius: '24px', overflow: 'hidden',
              boxShadow: '0 32px 80px rgba(0,0,0,.72), 0 0 60px rgba(124,58,237,.14)',
            }}>
              {/* Accent bar */}
              <div style={{ height: '3px', background: 'linear-gradient(90deg, #7c3aed, #8b5cf6, #ec4899)' }} />

              {/* Header */}
              <div style={{
                padding: '22px 24px 18px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                borderBottom: '1px solid rgba(255,255,255,.05)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  {/* Agent avatar */}
                  <div style={{
                    width: 46, height: 46, borderRadius: 14, flexShrink: 0,
                    background: `hsla(${hue},60%,15%,1)`,
                    border: `1px solid hsla(${hue},60%,35%,.4)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: "'DM Serif Display', serif", fontSize: '.95rem',
                    color: `hsl(${hue},70%,70%)`,
                  }}>
                    {agent?.id?.slice(-2).toUpperCase() ?? '??'}
                  </div>
                  <div>
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      padding: '2px 8px', borderRadius: '999px',
                      background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.2)',
                      color: '#c4b5fd', fontSize: '10px', fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: '5px',
                    }}>
                      <Edit3 size={9} /> Edit Agent
                    </div>
                    <h2 style={{
                      fontFamily: "'DM Serif Display', serif",
                      fontSize: '18px', fontWeight: 400,
                      color: 'rgba(255,255,255,.92)', letterSpacing: '-0.01em', margin: 0,
                    }}>
                      Agent <span style={{ fontFamily: 'monospace', fontSize: '15px', color: `hsl(${hue},70%,65%)` }}>#{shortId}</span>
                    </h2>
                  </div>
                </div>

                <button
                  onClick={onClose}
                  style={{
                    width: '34px', height: '34px', borderRadius: '10px', flexShrink: 0,
                    background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.07)',
                    cursor: 'pointer', color: 'rgba(255,255,255,.35)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all .2s',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,.08)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,.2)';
                    (e.currentTarget as HTMLElement).style.color = '#f87171';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,.04)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,.07)';
                    (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,.35)';
                  }}
                >
                  <X size={15} />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={onSubmit} style={{ padding: '22px 24px 24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>

                {/* Skills input */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <label style={{
                    fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,.35)',
                    textTransform: 'uppercase', letterSpacing: '0.09em',
                    display: 'flex', alignItems: 'center', gap: '5px',
                  }}>
                    <Zap size={10} style={{ color: '#8b5cf6' }} /> Skills & Expertise
                  </label>
                  <input
                    className="edit-modal-input"
                    type="text"
                    value={form.skills}
                    onChange={e => onChange('skills', e.target.value)}
                    placeholder="React, Python, Networking…"
                    style={inputStyle}
                  />
                  {/* Live skill chips */}
                  {skillChips.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '2px' }}>
                      {skillChips.map((s, i) => (
                        <span key={i} style={{
                          padding: '2px 9px', borderRadius: '999px',
                          background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.2)',
                          color: 'rgba(196,181,253,.85)', fontSize: '11px', fontWeight: 600,
                        }}>{s}</span>
                      ))}
                    </div>
                  )}
                  <p style={{ fontSize: '11.5px', color: 'rgba(255,255,255,.22)', margin: 0 }}>
                    Separate each skill with a comma
                  </p>
                </div>

                {/* Availability toggle */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <label style={{
                    fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,.35)',
                    textTransform: 'uppercase', letterSpacing: '0.09em',
                    display: 'flex', alignItems: 'center', gap: '5px',
                  }}>
                    <Activity size={10} style={{ color: '#10b981' }} /> Availability Status
                  </label>

                  <button
                    type="button"
                    onClick={() => onChange('is_available', !form.is_available)}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px 16px',
                      background: form.is_available ? 'rgba(16,185,129,.07)' : 'rgba(255,255,255,.03)',
                      border: `1px solid ${form.is_available ? 'rgba(16,185,129,.25)' : 'rgba(255,255,255,.08)'}`,
                      borderRadius: '12px', cursor: 'pointer',
                      transition: 'all .25s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        width: '8px', height: '8px', borderRadius: '50%',
                        background: form.is_available ? '#10b981' : '#64748b',
                        boxShadow: form.is_available ? '0 0 6px rgba(16,185,129,.6)' : 'none',
                        animation: form.is_available ? 'pulse-dot 2s infinite' : 'none',
                        transition: 'all .2s',
                      }} />
                      <span style={{
                        fontSize: '13.5px', fontWeight: 600,
                        color: form.is_available ? 'rgba(52,211,153,.9)' : 'rgba(255,255,255,.35)',
                        fontFamily: "'DM Sans', sans-serif",
                        transition: 'color .2s',
                      }}>
                        {form.is_available ? 'Available for assignment' : 'Unavailable / Offline'}
                      </span>
                    </div>

                    {/* Toggle pill */}
                    <div style={{
                      width: '42px', height: '24px', borderRadius: '999px', position: 'relative',
                      background: form.is_available ? 'rgba(16,185,129,.35)' : 'rgba(255,255,255,.08)',
                      border: `1px solid ${form.is_available ? 'rgba(16,185,129,.4)' : 'rgba(255,255,255,.1)'}`,
                      transition: 'all .25s ease', flexShrink: 0,
                    }}>
                      <div style={{
                        position: 'absolute', top: '3px',
                        left: form.is_available ? '20px' : '3px',
                        width: '16px', height: '16px', borderRadius: '50%',
                        background: form.is_available ? '#10b981' : 'rgba(255,255,255,.3)',
                        transition: 'all .25s cubic-bezier(.4,0,.2,1)',
                        boxShadow: form.is_available ? '0 0 6px rgba(16,185,129,.5)' : 'none',
                      }} />
                    </div>
                  </button>
                </div>

                {/* Divider */}
                <div style={{ height: '1px', background: 'rgba(255,255,255,.05)' }} />

                {/* Actions */}
                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button
                    type="button" onClick={onClose}
                    style={{
                      padding: '10px 18px',
                      background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
                      borderRadius: '12px', color: 'rgba(255,255,255,.45)',
                      fontSize: '13.5px', fontWeight: 600, cursor: 'pointer',
                      fontFamily: "'DM Sans', sans-serif", transition: 'all .2s',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,.18)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,.08)'}
                  >
                    Cancel
                  </button>

                  <button
                    type="submit" disabled={saving}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '7px',
                      padding: '10px 22px',
                      background: saving
                        ? 'rgba(124,58,237,.4)'
                        : 'linear-gradient(135deg, rgba(124,58,237,.85), rgba(139,92,246,.85))',
                      border: '1px solid rgba(167,139,250,.3)',
                      borderRadius: '12px', color: 'white',
                      fontSize: '13.5px', fontWeight: 600,
                      cursor: saving ? 'not-allowed' : 'pointer',
                      fontFamily: "'DM Sans', sans-serif",
                      boxShadow: saving ? 'none' : '0 4px 16px rgba(124,58,237,.35)',
                      transition: 'all .2s', opacity: saving ? 0.8 : 1,
                    }}
                    onMouseEnter={e => { if (!saving) (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 24px rgba(124,58,237,.55)'; }}
                    onMouseLeave={e => { if (!saving) (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 16px rgba(124,58,237,.35)'; }}
                  >
                    {saving
                      ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Saving…</>
                      : <><Save size={14} /> Save Changes</>
                    }
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

/* ─── MAIN COMPONENT ──────────────────────────────────────── */
const AgentList: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterAvail, setFilterAvail] = useState<'all' | 'available' | 'busy'>('all');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [editForm, setEditForm] = useState({ skills: '', is_available: true });
  const { user } = useAuth();

  useEffect(() => { injectStyles(); }, []);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const res = await api.get('/agents');
      setAgents(res.data);
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAgents(); }, []);

  const filtered = agents.filter(a => {
    const matchSearch = search === '' ||
      a.skills.some(s => s.toLowerCase().includes(search.toLowerCase())) ||
      a.id?.toLowerCase().includes(search.toLowerCase());
    const matchAvail = filterAvail === 'all' ||
      (filterAvail === 'available' && a.is_available) ||
      (filterAvail === 'busy' && !a.is_available);
    return matchSearch && matchAvail;
  });

  const activeCount = agents.filter(a => a.is_available).length;
  const avgWorkload = agents.length ? Math.round(agents.reduce((s, a) => s + a.workload, 0) / agents.length) : 0;

  const handleDelete = async (id: string) => {
    if (!window.confirm('Remove this agent from the workforce?')) return;
    try {
      await api.delete(`/agents/${id}`);
      fetchAgents();
      toast.success('Agent removed');
    } catch { toast.error('Failed to remove agent'); }
  };

  const openEdit = (agent: Agent) => {
    setSelectedAgent(agent);
    setEditForm({ skills: agent.skills.join(', '), is_available: agent.is_available });
    setIsEditModalOpen(true);
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgent) return;
    setSaving(true);
    try {
      await api.put(`/agents/${selectedAgent.id}`, {
        skills: editForm.skills.split(',').map(s => s.trim()).filter(Boolean),
        is_available: editForm.is_available,
      });
      setIsEditModalOpen(false);
      fetchAgents();
      toast.success('Agent updated');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update');
    } finally { setSaving(false); }
  };

  const kpiData = [
    { label: 'Total Agents', value: agents.length, insight: 'Workforce capacity nominal', icon: <Users size={18} />, color: '#8b5cf6', sparkData: [4, 6, 5, 8, 7, 9, agents.length] },
    { label: 'Online Now', value: activeCount, insight: `${Math.round(activeCount / Math.max(agents.length, 1) * 100)}% availability rate`, icon: <Activity size={18} />, color: '#10b981', sparkData: [3, 4, 3, 5, 4, 6, activeCount] },
    { label: 'Avg Workload', value: `${avgWorkload}%`, insight: avgWorkload > 75 ? 'High load — consider adding agents' : 'Workload distribution healthy', icon: <Target size={18} />, color: avgWorkload > 75 ? '#f97316' : '#3b82f6', sparkData: [55, 62, 58, 70, 65, 72, avgWorkload] },
    { label: 'SLA Score', value: '92%', insight: 'Above enterprise benchmark', icon: <Award size={18} />, color: '#ec4899', sparkData: [88, 90, 87, 91, 89, 93, 92] },
    { label: 'Avg Resolution', value: '4.2h', insight: '18% faster than last week', icon: <Clock size={18} />, color: '#06b6d4', sparkData: [5.1, 4.8, 5.0, 4.6, 4.4, 4.3, 4.2] },
    { label: 'AI Score', value: '87', insight: 'Top performers identified', icon: <Cpu size={18} />, color: '#a855f7', sparkData: [78, 80, 82, 84, 83, 86, 87] },
  ];

  const insightWidgets = [
    { icon: <TrendingUp size={14} />, text: 'AI predicts +34% workload today', color: '#8b5cf6' },
    { icon: <AlertTriangle size={14} />, text: '3 agents at burnout risk', color: '#f97316' },
    { icon: <CheckCircle2 size={14} />, text: '92% avg SLA compliance', color: '#10b981' },
    { icon: <Star size={14} />, text: 'Top team identified by AI', color: '#ec4899' },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif", display: 'flex', flexDirection: 'column', gap: '2rem', minHeight: '100%' }}>

      {/* ── HERO ─────────────────────────────────────────────── */}
      <div style={{
        position: 'relative', borderRadius: '24px', overflow: 'hidden',
        background: 'linear-gradient(135deg, rgba(10,10,20,.95) 0%, rgba(20,10,40,.95) 50%, rgba(10,10,20,.95) 100%)',
        border: '1px solid rgba(139,92,246,.2)', padding: '2.5rem',
      }}>
        <div style={{ position: 'absolute', top: -80, left: -80, width: 320, height: 320, borderRadius: '50%', background: 'radial-gradient(circle, rgba(139,92,246,.2) 0%, transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', bottom: -60, right: 100, width: 240, height: 240, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,.12) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '2rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', marginBottom: '.875rem' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#8b5cf6', animation: 'pulse-dot 2s infinite' }} />
              <span style={{ fontSize: '.7rem', fontWeight: 700, color: 'rgba(139,92,246,.8)', letterSpacing: '.1em', textTransform: 'uppercase' }}>AI Workforce System</span>
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 'clamp(2rem, 4vw, 2.75rem)', color: '#f1f5f9', lineHeight: 1.1, letterSpacing: '-0.02em', margin: 0 }}>
              AI Support{' '}
              <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg, #8b5cf6, #ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Workforce</span>
            </h1>
            <p style={{ color: 'rgba(255,255,255,.45)', marginTop: '.75rem', fontSize: '.9375rem', maxWidth: 400, lineHeight: 1.6 }}>
              Orchestrate your intelligent support team. Monitor performance, predict workload, and optimize resolution quality.
            </p>
            <div style={{ display: 'flex', gap: '.75rem', marginTop: '1.5rem', flexWrap: 'wrap' }}>
              <Link to="/agents/create" style={{
                display: 'flex', alignItems: 'center', gap: '.5rem',
                padding: '.75rem 1.5rem',
                background: 'linear-gradient(135deg, #7c3aed, #8b5cf6)',
                borderRadius: 12, color: '#fff', fontSize: '.875rem', fontWeight: 700,
                textDecoration: 'none', boxShadow: '0 8px 24px rgba(139,92,246,.35)',
                transition: 'all .2s',
              }}>
                <UserPlus size={16} /> Onboard Agent
              </Link>
              <button onClick={fetchAgents} style={{
                display: 'flex', alignItems: 'center', gap: '.5rem',
                padding: '.75rem 1.25rem',
                background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                borderRadius: 12, color: 'rgba(255,255,255,.6)', fontSize: '.875rem', fontWeight: 600,
                cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'all .2s',
              }}>
                <RefreshCw size={15} /> Sync
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '.625rem', minWidth: 240 }}>
            {insightWidgets.map((w, i) => (
              <div key={i} className="insight-widget" style={{
                display: 'flex', alignItems: 'center', gap: '.625rem',
                padding: '.625rem .875rem',
                background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
                borderRadius: 12, backdropFilter: 'blur(12px)',
              }}>
                <div style={{ color: w.color, flexShrink: 0 }}>{w.icon}</div>
                <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.6)', fontWeight: 500 }}>{w.text}</span>
                <div style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: w.color, animation: 'pulse-dot 2s infinite', flexShrink: 0 }} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── KPI GRID ─────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem' }}>
        {kpiData.map((k, i) => <KpiCard key={i} {...k} delay={i * 80} />)}
      </div>

      {/* ── FILTERS ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap',
        padding: '1rem 1.25rem',
        background: 'rgba(15,15,25,.7)', border: '1px solid rgba(255,255,255,.06)',
        borderRadius: 16, backdropFilter: 'blur(16px)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '.625rem', flex: '1 1 220px',
          padding: '.625rem 1rem', background: 'rgba(255,255,255,.04)',
          border: '1px solid rgba(255,255,255,.08)', borderRadius: 10,
        }}>
          <Search size={15} style={{ color: 'rgba(255,255,255,.3)', flexShrink: 0 }} />
          <input
            placeholder="Search by skill or ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              border: 'none', outline: 'none', background: 'transparent',
              fontSize: '.875rem', color: 'rgba(255,255,255,.7)',
              width: '100%', fontFamily: "'DM Sans', sans-serif",
            }}
          />
        </div>
        <div style={{ display: 'flex', gap: '.375rem' }}>
          {(['all', 'available', 'busy'] as const).map(f => (
            <button key={f} className={`filter-btn ${filterAvail === f ? 'active' : ''}`}
              onClick={() => setFilterAvail(f)}
              style={{
                padding: '.5rem .875rem', borderRadius: 8, fontSize: '.78rem', fontWeight: 600,
                background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
                color: 'rgba(255,255,255,.4)', cursor: 'pointer', transition: 'all .2s',
                textTransform: 'capitalize',
              }}>
              {f === 'all' ? 'All Agents' : f}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: 'auto', fontSize: '.78rem', color: 'rgba(255,255,255,.3)', whiteSpace: 'nowrap' }}>
          {filtered.length} agent{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── TABLE ────────────────────────────────────────────── */}
      <div style={{
        borderRadius: 20, overflow: 'hidden',
        background: 'rgba(15,15,25,.7)', border: '1px solid rgba(255,255,255,.07)',
        backdropFilter: 'blur(20px)',
      }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,.07)' }}>
                {['Agent', 'Skills & Expertise', 'AI Productivity', 'Workload', 'SLA', 'Role', 'Actions'].map((h, i) => (
                  <th key={i} style={{
                    padding: '1rem 1.25rem', textAlign: 'left',
                    fontSize: '.7rem', fontWeight: 700, letterSpacing: '.07em',
                    color: 'rgba(255,255,255,.3)', textTransform: 'uppercase',
                    background: 'rgba(255,255,255,.02)', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }, (_, i) => <SkeletonRow key={i} index={i} />)
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '5rem 2rem', textAlign: 'center' }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: 20, margin: '0 auto 1.25rem',
                      background: 'rgba(139,92,246,.08)', border: '1px solid rgba(139,92,246,.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <UserPlus size={26} style={{ color: 'rgba(139,92,246,.6)' }} />
                    </div>
                    <p style={{ fontFamily: "'DM Serif Display', serif", fontSize: '1.375rem', color: 'rgba(255,255,255,.5)', marginBottom: '.5rem' }}>
                      {search ? 'No agents found' : 'Your workforce awaits'}
                    </p>
                    <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.25)', marginBottom: '1.5rem' }}>
                      {search ? 'Try a different keyword or filter.' : 'Onboard your first AI support agent.'}
                    </p>
                    {!search && (
                      <Link to="/agents/create" style={{
                        display: 'inline-flex', alignItems: 'center', gap: '.5rem',
                        padding: '.75rem 1.5rem', background: 'rgba(139,92,246,.2)',
                        border: '1px solid rgba(139,92,246,.35)', borderRadius: 10,
                        color: '#c4b5fd', fontWeight: 700, fontSize: '.875rem', textDecoration: 'none',
                      }}>
                        <UserPlus size={15} /> Onboard First Agent
                      </Link>
                    )}
                  </td>
                </tr>
              ) : (
                filtered.map((agent, i) => (
                  <AgentRow
                    key={agent.id} agent={agent} index={i}
                    onEdit={() => openEdit(agent)}
                    onDelete={() => handleDelete(agent.id)}
                    isAdmin={user?.role === UserRole.ADMIN}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── EDIT MODAL ───────────────────────────────────────── */}
      <EditModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        agent={selectedAgent}
        form={editForm}
        onChange={(field, value) => setEditForm(f => ({ ...f, [field]: value }))}
        onSubmit={handleUpdate}
        saving={saving}
      />
    </div>
  );
};

export default AgentList;