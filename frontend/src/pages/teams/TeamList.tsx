import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, Plus, Settings, Shield, Zap, RefreshCw,
  TrendingUp, Activity, Target, Trash2, Edit2, X, Save, Loader2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { type Team, UserRole } from '../../types';
import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import toast from 'react-hot-toast';

/* ─────────────────────────────────────────────
   GLASS STYLE TOKEN
───────────────────────────────────────────── */
const glass: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(139,92,246,0.12)',
  backdropFilter: 'blur(20px)',
  borderRadius: '20px',
};

/* ─────────────────────────────────────────────
   ANALYTICS BADGE
───────────────────────────────────────────── */
const AnalyticBadge: React.FC<{ label: string; value: string; color: string; icon: React.ReactNode }> = ({ label, value, color, icon }) => (
  <div style={{
    display: 'flex', flexDirection: 'column', gap: '8px',
    padding: '18px', ...glass,
    borderRadius: '16px', position: 'relative', overflow: 'hidden',
  }}>
    <div style={{
      position: 'absolute', top: '-16px', right: '-16px',
      width: '72px', height: '72px', borderRadius: '50%',
      background: `${color}12`, pointerEvents: 'none',
    }} />
    <div style={{
      width: '32px', height: '32px', borderRadius: '9px',
      background: `${color}18`, border: `1px solid ${color}28`,
      display: 'flex', alignItems: 'center', justifyContent: 'center', color,
    }}>
      {icon}
    </div>
    <div>
      <div style={{ fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.95)', letterSpacing: '-0.03em' }}>{value}</div>
      <div style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.07em', marginTop: '2px' }}>{label}</div>
    </div>
  </div>
);

/* ─────────────────────────────────────────────
   EDIT MODAL  (self-contained, no Modal wrapper)
───────────────────────────────────────────── */
interface EditModalProps {
  isOpen: boolean;
  onClose: () => void;
  form: { name: string; description: string; competencies: string };
  onChange: (field: 'name' | 'description' | 'competencies', value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  saving: boolean;
}

const EditModal: React.FC<EditModalProps> = ({ isOpen, onClose, form, onChange, onSubmit, saving }) => {
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '11px 14px',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(139,92,246,0.15)',
    borderRadius: '12px', fontSize: '14px',
    color: 'rgba(255,255,255,0.85)',
    fontFamily: 'DM Sans, sans-serif', outline: 'none',
    transition: 'all 0.2s', boxSizing: 'border-box',
  };
  const onFocus = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = 'rgba(139,92,246,0.5)';
    e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.1)';
  };
  const onBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = 'rgba(139,92,246,0.15)';
    e.target.style.boxShadow = 'none';
  };

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
              width: '100%', maxWidth: '480px', pointerEvents: 'all',
              background: 'rgba(13,13,26,0.94)',
              border: '1px solid rgba(139,92,246,0.22)',
              backdropFilter: 'blur(36px)',
              borderRadius: '24px', overflow: 'hidden',
              boxShadow: '0 32px 80px rgba(0,0,0,0.72), 0 0 60px rgba(124,58,237,0.14)',
            }}>
              {/* Accent bar */}
              <div style={{ height: '3px', background: 'linear-gradient(90deg, #7c3aed, #6d28d9, #4f46e5)' }} />

              {/* Header */}
              <div style={{
                padding: '22px 24px 18px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div>
                  <div style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    padding: '3px 9px', borderRadius: '999px',
                    background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)',
                    color: '#c4b5fd', fontSize: '10px', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: '8px',
                  }}>
                    <Edit2 size={9} /> Edit Team
                  </div>
                  <h2 style={{
                    fontFamily: 'DM Serif Display, serif',
                    fontSize: '20px', fontWeight: 400,
                    color: 'rgba(255,255,255,0.92)', letterSpacing: '-0.01em', margin: 0,
                  }}>
                    {form.name || 'Update Team'}
                  </h2>
                </div>

                <button
                  onClick={onClose}
                  style={{
                    width: '34px', height: '34px', borderRadius: '10px', flexShrink: 0,
                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                    cursor: 'pointer', color: 'rgba(255,255,255,0.35)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.08)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,0.2)';
                    (e.currentTarget as HTMLElement).style.color = '#f87171';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.07)';
                    (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.35)';
                  }}
                >
                  <X size={15} />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={onSubmit} style={{ padding: '22px 24px 24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>

                {/* Name */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <label style={{
                    fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)',
                    textTransform: 'uppercase', letterSpacing: '0.09em',
                    display: 'flex', alignItems: 'center', gap: '5px',
                  }}>
                    <Users size={10} style={{ color: '#a78bfa' }} /> Team Name
                  </label>
                  <input
                    type="text" required
                    value={form.name}
                    placeholder="e.g. Infrastructure Response"
                    onChange={e => onChange('name', e.target.value)}
                    onFocus={onFocus} onBlur={onBlur}
                    style={inputStyle}
                  />
                </div>

                {/* Description */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <label style={{
                    fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)',
                    textTransform: 'uppercase', letterSpacing: '0.09em',
                  }}>
                    Description
                  </label>
                  <textarea
                    rows={2}
                    value={form.description}
                    placeholder="Brief description of this team's role…"
                    onChange={e => onChange('description', e.target.value)}
                    onFocus={onFocus} onBlur={onBlur}
                    style={{ ...inputStyle, resize: 'none' }}
                  />
                </div>

                {/* Competencies */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <label style={{
                    fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)',
                    textTransform: 'uppercase', letterSpacing: '0.09em',
                    display: 'flex', alignItems: 'center', gap: '5px',
                  }}>
                    <Zap size={10} style={{ color: '#f59e0b' }} /> Competencies
                  </label>
                  <input
                    type="text"
                    value={form.competencies}
                    placeholder="Hardware, Network, Cloud…"
                    onChange={e => onChange('competencies', e.target.value)}
                    onFocus={onFocus} onBlur={onBlur}
                    style={inputStyle}
                  />
                  {/* Live chip preview */}
                  {form.competencies.trim() && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '2px' }}>
                      {form.competencies.split(',').map(s => s.trim()).filter(Boolean).map((c, i) => (
                        <span key={i} style={{
                          padding: '2px 9px', borderRadius: '999px',
                          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.18)',
                          color: 'rgba(251,191,36,0.8)', fontSize: '11px', fontWeight: 600,
                        }}>{c}</span>
                      ))}
                    </div>
                  )}
                  <p style={{ fontSize: '11.5px', color: 'rgba(255,255,255,0.22)', margin: 0 }}>
                    Separate each competency with a comma
                  </p>
                </div>

                {/* Divider */}
                <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)' }} />

                {/* Actions */}
                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button
                    type="button" onClick={onClose}
                    style={{
                      padding: '10px 18px',
                      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '12px', color: 'rgba(255,255,255,0.45)',
                      fontSize: '13.5px', fontWeight: 600, cursor: 'pointer',
                      fontFamily: 'DM Sans, sans-serif', transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.15)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)'}
                  >
                    Cancel
                  </button>

                  <button
                    type="submit" disabled={saving}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '7px',
                      padding: '10px 22px',
                      background: saving ? 'rgba(124,58,237,0.4)' : 'linear-gradient(135deg, rgba(124,58,237,0.85), rgba(79,70,229,0.85))',
                      border: '1px solid rgba(167,139,250,0.3)',
                      borderRadius: '12px', color: 'white',
                      fontSize: '13.5px', fontWeight: 600,
                      cursor: saving ? 'not-allowed' : 'pointer',
                      fontFamily: 'DM Sans, sans-serif',
                      boxShadow: saving ? 'none' : '0 4px 16px rgba(124,58,237,0.35)',
                      transition: 'all 0.2s', opacity: saving ? 0.8 : 1,
                    }}
                    onMouseEnter={e => { if (!saving) (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 24px rgba(124,58,237,0.55)'; }}
                    onMouseLeave={e => { if (!saving) (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 16px rgba(124,58,237,0.35)'; }}
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

          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </>
      )}
    </AnimatePresence>
  );
};

/* ─────────────────────────────────────────────
   TEAM CARD
───────────────────────────────────────────── */
const TeamCard: React.FC<{ team: Team; onEdit: () => void; onDelete: () => void; index: number }> = ({
  team, onEdit, onDelete, index,
}) => {
  const { user } = useAuth();
  const [hovered, setHovered] = useState(false);

  const palette = [
    { from: '#7c3aed', to: '#6d28d9', glow: 'rgba(124,58,237,0.25)' },
    { from: '#2563eb', to: '#1d4ed8', glow: 'rgba(37,99,235,0.2)' },
    { from: '#0891b2', to: '#0e7490', glow: 'rgba(8,145,178,0.2)' },
    { from: '#059669', to: '#047857', glow: 'rgba(5,150,105,0.2)' },
    { from: '#d97706', to: '#b45309', glow: 'rgba(217,119,6,0.2)' },
    { from: '#dc2626', to: '#b91c1c', glow: 'rgba(220,38,38,0.2)' },
  ];
  const color = palette[(team.name.charCodeAt(0) || 0) % palette.length];

  const sla = 85 + (team.name.charCodeAt(0) % 15);
  const efficiency = 70 + (team.name.charCodeAt(1) % 28);
  const workload = 40 + (team.name.charCodeAt(0) % 55);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: 'easeOut' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        ...glass, display: 'flex', flexDirection: 'column',
        overflow: 'hidden', transition: 'all 0.3s ease',
        borderColor: hovered ? 'rgba(139,92,246,0.28)' : 'rgba(139,92,246,0.12)',
        boxShadow: hovered ? `0 16px 48px rgba(0,0,0,0.5), 0 0 40px ${color.glow}` : '0 4px 16px rgba(0,0,0,0.2)',
        transform: hovered ? 'translateY(-4px)' : 'translateY(0)',
      }}
    >
      <div style={{ height: '3px', background: `linear-gradient(90deg, ${color.from}, ${color.to})` }} />

      {/* Header */}
      <div style={{ padding: '22px 22px 16px', display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
        <div style={{
          width: '52px', height: '52px', borderRadius: '15px', flexShrink: 0,
          background: `linear-gradient(135deg, ${color.from}, ${color.to})`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 8px 20px ${color.glow}`,
        }}>
          <Users size={22} style={{ color: 'white' }} />
        </div>

        <div style={{ flex: 1 }}>
          <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'rgba(255,255,255,0.95)', letterSpacing: '-0.01em', lineHeight: 1.3 }}>
            {team.name}
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 5px rgba(16,185,129,0.6)' }} />
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontWeight: 500 }}>
              {team.agent_ids.length} agent{team.agent_ids.length !== 1 ? 's' : ''} · Active
            </span>
          </div>
        </div>

        <button
          style={{
            width: '32px', height: '32px', borderRadius: '9px', flexShrink: 0,
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)',
            cursor: 'pointer', color: 'rgba(255,255,255,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.12)';
            (e.currentTarget as HTMLElement).style.color = '#a78bfa';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.3)';
          }}
        >
          <Settings size={14} />
        </button>
      </div>

      {/* Metrics */}
      <div style={{ padding: '0 22px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
        {[
          { label: 'SLA', value: `${sla}%`, color: sla >= 95 ? '#10b981' : sla >= 85 ? '#f59e0b' : '#ef4444' },
          { label: 'AI Score', value: `${efficiency}%`, color: '#a78bfa' },
          { label: 'Load', value: `${workload}%`, color: workload > 80 ? '#ef4444' : workload > 60 ? '#f59e0b' : '#10b981' },
        ].map(m => (
          <div key={m.label} style={{
            padding: '10px', borderRadius: '10px',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center',
          }}>
            <div style={{ fontSize: '16px', fontWeight: 700, color: m.color, letterSpacing: '-0.02em' }}>{m.value}</div>
            <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: '2px' }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div style={{ height: '1px', background: 'rgba(255,255,255,0.04)', margin: '0 22px' }} />

      {/* Competencies */}
      <div style={{ padding: '16px 22px' }}>
        <div style={{
          fontSize: '10px', fontWeight: 700, color: 'rgba(255,255,255,0.2)',
          textTransform: 'uppercase', letterSpacing: '0.1em',
          display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '10px',
        }}>
          <Zap size={10} style={{ color: '#f59e0b' }} /> Competencies
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {team.competencies.length > 0 ? team.competencies.slice(0, 4).map((c, i) => (
            <span key={i} style={{
              padding: '3px 10px', borderRadius: '999px',
              background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.18)',
              color: 'rgba(251,191,36,0.8)', fontSize: '11.5px', fontWeight: 600,
            }}>{c}</span>
          )) : (
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.2)', fontStyle: 'italic' }}>No competencies listed</span>
          )}
          {team.competencies.length > 4 && (
            <span style={{
              padding: '3px 10px', borderRadius: '999px',
              background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)',
              color: '#a78bfa', fontSize: '11.5px', fontWeight: 600,
            }}>+{team.competencies.length - 4}</span>
          )}
        </div>
      </div>

      {/* Agent avatars */}
      {team.agent_ids.length > 0 && (
        <div style={{ padding: '0 22px 16px' }}>
          <div style={{
            fontSize: '10px', fontWeight: 700, color: 'rgba(255,255,255,0.2)',
            textTransform: 'uppercase', letterSpacing: '0.1em',
            display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '10px',
          }}>
            <Shield size={10} style={{ color: '#60a5fa' }} /> Active Agents
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ display: 'flex' }}>
              {team.agent_ids.slice(0, 6).map((id, i) => (
                <div key={i} style={{
                  width: '30px', height: '30px', borderRadius: '50%',
                  border: '2px solid rgba(13,13,26,0.8)',
                  background: `hsl(${(parseInt(id.slice(-3), 16) || i * 47) % 360},60%,40%)`,
                  color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '11px', fontWeight: 700,
                  marginLeft: i === 0 ? 0 : '-8px', position: 'relative', zIndex: 6 - i,
                }}>
                  {id.slice(-1).toUpperCase()}
                </div>
              ))}
            </div>
            {team.agent_ids.length > 6 && (
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#a78bfa' }}>+{team.agent_ids.length - 6} more</span>
            )}
          </div>
        </div>
      )}

      {/* Footer actions */}
      <div style={{
        padding: '14px 22px', borderTop: '1px solid rgba(255,255,255,0.04)',
        background: 'rgba(0,0,0,0.1)', display: 'flex', gap: '8px', marginTop: 'auto',
      }}>
        <button
          onClick={onEdit}
          style={{
            flex: 1, padding: '9px',
            background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)',
            borderRadius: '10px', color: '#c4b5fd', fontSize: '12.5px', fontWeight: 600,
            cursor: 'pointer', fontFamily: 'DM Sans, sans-serif',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.2s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.15)';
            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.35)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.08)';
            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.2)';
          }}
        >
          <Edit2 size={13} /> Edit Team
        </button>

        {user?.role === UserRole.ADMIN && (
          <button
            onClick={onDelete}
            style={{
              padding: '9px 14px',
              background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
              borderRadius: '10px', color: '#fca5a5', fontSize: '12.5px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'DM Sans, sans-serif',
              display: 'flex', alignItems: 'center', gap: '5px', transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.12)';
              (e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,0.3)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.06)';
              (e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,0.15)';
            }}
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>
    </motion.div>
  );
};

/* ─────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────── */
const TeamList: React.FC = () => {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [editForm, setEditForm] = useState({ name: '', description: '', competencies: '' });

  const fetchTeams = async () => {
    setLoading(true);
    try {
      const res = await api.get('/teams');
      setTeams(res.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchTeams(); }, []);

  const handleDeleteTeam = async (id: string) => {
    if (!window.confirm('Delete this team?')) return;
    try {
      await api.delete(`/teams/${id}`);
      fetchTeams();
      toast.success('Team deleted');
    } catch {
      toast.error('Failed to delete team');
    }
  };

  const openEditModal = (team: Team) => {
    setSelectedTeam(team);
    setEditForm({ name: team.name || '', description: '', competencies: team.competencies.join(', ') });
    setIsEditModalOpen(true);
  };

  const handleUpdateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTeam) return;
    setSaving(true);
    try {
      await api.put(`/teams/${selectedTeam.id}`, {
        name: editForm.name,
        description: editForm.description,
        competencies: editForm.competencies.split(',').map(s => s.trim()).filter(Boolean),
      });
      setIsEditModalOpen(false);
      fetchTeams();
      toast.success('Team updated');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update team');
    } finally {
      setSaving(false);
    }
  };

  const totalAgents = teams.reduce((sum, t) => sum + t.agent_ids.length, 0);
  const avgSLA = teams.length > 0
    ? Math.round(teams.reduce((sum, t) => sum + 85 + (t.name.charCodeAt(0) % 15), 0) / teams.length)
    : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '40px' }}>
      {/* ── Hero ── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}
      >
        <div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '5px',
            padding: '4px 10px', borderRadius: '999px',
            background: 'rgba(96,165,250,0.1)', border: '1px solid rgba(96,165,250,0.2)',
            color: '#93c5fd', fontSize: '11px', fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px',
          }}>
            <Activity size={10} /> Operations Center
          </div>
          <h1 style={{
            fontFamily: 'DM Serif Display, serif',
            fontSize: '32px', fontWeight: 400,
            color: 'rgba(255,255,255,0.95)', letterSpacing: '-0.02em', lineHeight: 1.2,
          }}>
            Team Intelligence
          </h1>
          <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.4)', marginTop: '6px' }}>
            Organize AI agents into specialized operational units
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={fetchTeams}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '10px 16px', ...glass, borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.45)', fontSize: '13px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'DM Sans, sans-serif', transition: 'all 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.25)'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)'}
          >
            <RefreshCw size={14} /> Refresh
          </button>

          <Link
            to="/teams/create"
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 20px',
              background: 'linear-gradient(135deg, rgba(124,58,237,0.85), rgba(79,70,229,0.85))',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(167,139,250,0.3)',
              borderRadius: '14px', color: 'white',
              fontSize: '13.5px', fontWeight: 600, textDecoration: 'none',
              boxShadow: '0 4px 20px rgba(124,58,237,0.35)', transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 28px rgba(124,58,237,0.55)';
              (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 20px rgba(124,58,237,0.35)';
              (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
            }}
          >
            <Plus size={16} /> Create Team
          </Link>
        </div>
      </motion.div>

      {/* ── Analytics Row ── */}
      {!loading && teams.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
          <AnalyticBadge icon={<Users size={16} />} label="Total Teams" value={String(teams.length)} color="#a78bfa" />
          <AnalyticBadge icon={<Shield size={16} />} label="Active Agents" value={String(totalAgents)} color="#60a5fa" />
          <AnalyticBadge icon={<Target size={16} />} label="Avg SLA" value={`${avgSLA}%`} color="#10b981" />
          <AnalyticBadge icon={<TrendingUp size={16} />} label="AI Efficiency" value="91%" color="#f59e0b" />
        </div>
      )}

      {/* ── Content ── */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {[1, 2, 3].map(i => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: [0.3, 0.6, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
              style={{ ...glass, height: '360px', borderRadius: '20px' }}
            />
          ))}
        </div>
      ) : teams.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{
            ...glass, padding: '80px 40px', textAlign: 'center',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px',
          }}
        >
          <div style={{
            width: '72px', height: '72px', borderRadius: '20px',
            background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Users size={30} style={{ color: 'rgba(139,92,246,0.5)' }} />
          </div>
          <div>
            <h3 style={{
              fontFamily: 'DM Serif Display, serif',
              fontSize: '22px', fontWeight: 400, color: 'rgba(255,255,255,0.7)', marginBottom: '8px',
            }}>No teams configured</h3>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.3)', maxWidth: '340px' }}>
              Create your first team to organize AI agents by specialization and route tickets intelligently.
            </p>
          </div>
          <Link
            to="/teams/create"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '8px',
              padding: '12px 24px', marginTop: '8px',
              background: 'linear-gradient(135deg, rgba(124,58,237,0.8), rgba(79,70,229,0.8))',
              border: '1px solid rgba(167,139,250,0.3)',
              borderRadius: '14px', color: 'white',
              fontSize: '14px', fontWeight: 600, textDecoration: 'none',
              boxShadow: '0 4px 20px rgba(124,58,237,0.3)',
            }}
          >
            <Plus size={16} /> Create First Team
          </Link>
        </motion.div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {teams.map((team, i) => (
            <TeamCard
              key={team.id}
              team={team}
              onEdit={() => openEditModal(team)}
              onDelete={() => handleDeleteTeam(team.id)}
              index={i}
            />
          ))}
        </div>
      )}

      {/* ── Edit Modal ── */}
      <EditModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        form={editForm}
        onChange={(field, value) => setEditForm(f => ({ ...f, [field]: value }))}
        onSubmit={handleUpdateTeam}
        saving={saving}
      />
    </div>
  );
};

export default TeamList;