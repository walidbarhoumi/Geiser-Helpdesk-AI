import React, { useEffect, useState } from 'react';
import {
  Search, Plus, Loader2, Shield, Edit2, Trash2,
  X, Users, Zap, Filter, MoreVertical,
  Sparkles, UserCheck
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { User, UserRole } from '../../types';
import api from '../../api/axios';

/* ─────────────────────────────────────────────
   DESIGN TOKENS
───────────────────────────────────────────── */
const glass = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(139,92,246,0.12)',
  backdropFilter: 'blur(20px)',
  borderRadius: '20px',
} as React.CSSProperties;


/* ─────────────────────────────────────────────
   STAT CARD
───────────────────────────────────────────── */
const StatCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  delay?: number;
}> = ({ icon, label, value, sub, color, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.4, ease: 'easeOut' }}
    style={{
      ...glass,
      padding: '20px',
      display: 'flex', flexDirection: 'column', gap: '12px',
      position: 'relative', overflow: 'hidden',
    }}
  >
    <div style={{
      position: 'absolute', top: '-20px', right: '-20px',
      width: '80px', height: '80px', borderRadius: '50%',
      background: `${color}15`,
    }} />
    <div style={{
      width: '36px', height: '36px', borderRadius: '10px',
      background: `${color}20`,
      border: `1px solid ${color}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: color,
    }}>
      {icon}
    </div>
    <div>
      <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgba(255,255,255,0.95)', letterSpacing: '-0.03em' }}>
        {value}
      </div>
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'rgba(255,255,255,0.4)', marginTop: '2px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      {sub && <div style={{ fontSize: '11px', color, marginTop: '4px', fontWeight: 600 }}>{sub}</div>}
    </div>
  </motion.div>
);

/* ─────────────────────────────────────────────
   ROLE BADGE
───────────────────────────────────────────── */
const RoleBadge: React.FC<{ role: string }> = ({ role }) => {
  const config = {
    ADMIN: { bg: 'rgba(167,139,250,0.15)', border: 'rgba(167,139,250,0.3)', color: '#c4b5fd', label: 'Admin' },
    AGENT: { bg: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.25)', color: '#93c5fd', label: 'Agent' },
    USER: { bg: 'rgba(52,211,153,0.10)', border: 'rgba(52,211,153,0.2)', color: '#6ee7b7', label: 'User' },
  }[role] || { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)', label: role };

  return (
    <span style={{
      padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: 700,
      background: config.bg, border: `1px solid ${config.border}`, color: config.color,
      letterSpacing: '0.04em', textTransform: 'uppercase',
      boxShadow: `0 0 8px ${config.border}`,
    }}>
      {config.label}
    </span>
  );
};

/* ─────────────────────────────────────────────
   AVATAR
───────────────────────────────────────────── */
const Avatar: React.FC<{ name: string; email: string; size?: number }> = ({ name, email, size = 42 }) => {
  const initial = (name || email || '?')[0].toUpperCase();
  const hue = (name || email).split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 360;

  return (
    <div style={{
      width: `${size}px`, height: `${size}px`, borderRadius: `${size * 0.28}px`, flexShrink: 0,
      background: `linear-gradient(135deg, hsl(${hue},60%,35%), hsl(${(hue + 40) % 360},60%,45%))`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: `${size * 0.38}px`, fontWeight: 700, color: 'white',
      border: '1.5px solid rgba(255,255,255,0.1)',
      boxShadow: `0 4px 12px hsl(${hue},60%,25%)40`,
    }}>
      {initial}
    </div>
  );
};

/* ─────────────────────────────────────────────
   USER ROW
───────────────────────────────────────────── */
const UserRow: React.FC<{
  user: User;
  onEdit: () => void;
  onDelete: () => void;
  delay: number;
}> = ({ user, onEdit, onDelete, delay }) => {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.3 }}
      style={{ position: 'relative' }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.04)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'transparent';
        setMenuOpen(false);
      }}
    >
      {/* User */}
      <td style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ position: 'relative' }}>
            <Avatar name={user.full_name || ''} email={user.email} />
            <div style={{
              position: 'absolute', bottom: '-1px', right: '-1px',
              width: '10px', height: '10px', borderRadius: '50%',
              background: user.is_active ? '#10b981' : '#4b5563',
              border: '2px solid #080812',
            }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'rgba(255,255,255,0.9)', fontSize: '14px', letterSpacing: '-0.01em' }}>
              {user.full_name || 'Unnamed User'}
            </div>
            <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '12.5px', marginTop: '2px' }}>
              {user.email}
            </div>
          </div>
        </div>
      </td>

      {/* Role */}
      <td style={{ padding: '14px 20px' }}>
        <RoleBadge role={user.role} />
      </td>

      {/* AI Score */}
      <td style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ flex: 1, height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '999px', maxWidth: '64px' }}>
            <div style={{
              width: `${50 + Math.floor(Math.random() * 50)}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #7c3aed, #a78bfa)',
              borderRadius: '999px',
            }} />
          </div>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#a78bfa' }}>
            {50 + Math.floor(((user.email.charCodeAt(0) + user.email.charCodeAt(1)) % 50))}%
          </span>
        </div>
      </td>

      {/* Status */}
      <td style={{ padding: '14px 20px' }}>
        {user.is_active ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px rgba(16,185,129,0.6)' }} />
            <span style={{ fontSize: '12.5px', fontWeight: 600, color: '#6ee7b7' }}>Active</span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4b5563' }} />
            <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'rgba(255,255,255,0.3)' }}>Inactive</span>
          </div>
        )}
      </td>

      {/* Actions */}
      <td style={{ padding: '14px 20px', textAlign: 'right' }}>
        <div style={{ position: 'relative', display: 'inline-block' }}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            style={{
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '8px', padding: '6px 8px',
              color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.12)';
              (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.25)';
              (e.currentTarget as HTMLElement).style.color = '#a78bfa';
            }}
            onMouseLeave={e => {
              if (!menuOpen) {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)';
                (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)';
                (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
              }
            }}
          >
            <MoreVertical size={14} />
          </button>

          <AnimatePresence>
            {menuOpen && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9, y: -4 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: -4 }}
                transition={{ duration: 0.15 }}
                style={{
                  position: 'absolute', right: 0, top: '100%', marginTop: '6px',
                  background: 'rgba(12,12,22,0.95)',
                  border: '1px solid rgba(139,92,246,0.2)',
                  borderRadius: '12px', overflow: 'hidden',
                  backdropFilter: 'blur(20px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                  zIndex: 50, minWidth: '140px',
                }}
              >
                <button onClick={() => { onEdit(); setMenuOpen(false); }} style={{
                  width: '100%', padding: '10px 14px', background: 'none', border: 'none',
                  color: 'rgba(255,255,255,0.7)', cursor: 'pointer', textAlign: 'left',
                  fontSize: '13px', fontWeight: 500, fontFamily: 'DM Sans, sans-serif',
                  display: 'flex', alignItems: 'center', gap: '8px',
                  transition: 'background 0.15s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(139,92,246,0.12)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                >
                  <Edit2 size={13} style={{ color: '#a78bfa' }} /> Edit User
                </button>
                <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)' }} />
                <button onClick={() => { onDelete(); setMenuOpen(false); }} style={{
                  width: '100%', padding: '10px 14px', background: 'none', border: 'none',
                  color: '#fca5a5', cursor: 'pointer', textAlign: 'left',
                  fontSize: '13px', fontWeight: 500, fontFamily: 'DM Sans, sans-serif',
                  display: 'flex', alignItems: 'center', gap: '8px',
                  transition: 'background 0.15s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                >
                  <Trash2 size={13} /> Delete
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </td>
    </motion.tr>
  );
};

/* ─────────────────────────────────────────────
   PREMIUM MODAL
───────────────────────────────────────────── */
const PremiumModal: React.FC<{
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}> = ({ open, onClose, title, children }) => (
  <AnimatePresence>
    {open && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '20px',
        }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 16 }}
          transition={{ duration: 0.2 }}
          onClick={e => e.stopPropagation()}
          style={{
            background: 'rgba(10,10,22,0.98)',
            border: '1px solid rgba(139,92,246,0.2)',
            borderRadius: '24px', padding: '28px',
            width: '100%', maxWidth: '420px',
            backdropFilter: 'blur(40px)',
            boxShadow: '0 24px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(139,92,246,0.08)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h2 style={{
              fontFamily: 'DM Serif Display, serif',
              fontSize: '20px', fontWeight: 400,
              color: 'rgba(255,255,255,0.95)',
            }}>
              {title}
            </h2>
            <button onClick={onClose} style={{
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '8px', padding: '6px', cursor: 'pointer',
              color: 'rgba(255,255,255,0.4)', display: 'flex', alignItems: 'center',
              transition: 'all 0.15s',
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.1)';
                (e.currentTarget as HTMLElement).style.color = '#ef4444';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)';
                (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
              }}
            >
              <X size={16} />
            </button>
          </div>
          {children}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);

/* ─────────────────────────────────────────────
   PREMIUM INPUT
───────────────────────────────────────────── */
const PremiumInput: React.FC<{
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  hint?: string;
}> = ({ label, type = 'text', value, onChange, placeholder, required, hint }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
    <label style={{ fontSize: '12px', fontWeight: 700, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
      {label} {required && <span style={{ color: '#a78bfa' }}>*</span>}
      {hint && <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, color: 'rgba(255,255,255,0.25)', marginLeft: '6px' }}>{hint}</span>}
    </label>
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(139,92,246,0.15)',
        borderRadius: '12px', padding: '10px 14px',
        fontSize: '14px', color: 'rgba(255,255,255,0.85)',
        fontFamily: 'DM Sans, sans-serif',
        outline: 'none', transition: 'all 0.2s',
        width: '100%',
      }}
      onFocus={e => {
        e.target.style.borderColor = 'rgba(139,92,246,0.5)';
        e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.1)';
        e.target.style.background = 'rgba(255,255,255,0.06)';
      }}
      onBlur={e => {
        e.target.style.borderColor = 'rgba(139,92,246,0.15)';
        e.target.style.boxShadow = 'none';
        e.target.style.background = 'rgba(255,255,255,0.04)';
      }}
    />
  </div>
);

/* ─────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────── */
const UserList: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    email: '', password: '', full_name: '', role: 'USER' as UserRole, is_active: true,
  });
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleOpenModal = (user?: User) => {
    setError('');
    if (user) {
      setEditUser(user);
      setFormData({ email: user.email, password: '', full_name: user.full_name || '', role: user.role, is_active: user.is_active });
    } else {
      setEditUser(null);
      setFormData({ email: '', password: '', full_name: '', role: 'USER' as UserRole, is_active: true });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError('');
    try {
      if (editUser) {
        const payload: any = { email: formData.email, full_name: formData.full_name, role: formData.role, is_active: formData.is_active };
        if (formData.password) payload.password = formData.password;
        await api.put(`/users/${editUser.id}`, payload);
      } else {
        await api.post('/users', formData);
      }
      setShowModal(false);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save user.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this user?')) return;
    try {
      await api.delete(`/users/${id}`);
      fetchUsers();
    } catch { alert('Failed to delete user.'); }
  };

  const filtered = users.filter(u =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.full_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const activeCount = users.filter(u => u.is_active).length;
  const adminCount = users.filter(u => u.role === 'ADMIN').length;
  const agentCount = users.filter(u => u.role === 'AGENT').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '40px' }}>
      {/* ── Hero Section ── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <div style={{
              padding: '4px 10px', borderRadius: '999px', fontSize: '11px',
              fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
              background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.2)',
              color: '#c4b5fd', display: 'flex', alignItems: 'center', gap: '5px',
            }}>
              <Sparkles size={10} /> Workspace Members
            </div>
          </div>
          <h1 style={{
            fontFamily: 'DM Serif Display, serif',
            fontSize: '32px', fontWeight: 400,
            color: 'rgba(255,255,255,0.95)',
            letterSpacing: '-0.02em', lineHeight: 1.2,
          }}>
            User Management
          </h1>
          <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.4)', marginTop: '6px', fontWeight: 400 }}>
            Manage platform access, roles, and AI-powered team accounts
          </p>
        </div>

        <button
          onClick={() => handleOpenModal()}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 20px',
            background: 'linear-gradient(135deg, rgba(124,58,237,0.8), rgba(79,70,229,0.8))',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(167,139,250,0.3)',
            borderRadius: '14px', color: 'white',
            fontSize: '13.5px', fontWeight: 600,
            cursor: 'pointer', fontFamily: 'DM Sans, sans-serif',
            boxShadow: '0 4px 20px rgba(124,58,237,0.35)',
            transition: 'all 0.2s',
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
          <Plus size={16} /> Add Member
        </button>
      </motion.div>

      {/* ── Stat Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <StatCard icon={<Users size={17} />} label="Total Members" value={users.length} color="#a78bfa" delay={0.05} />
        <StatCard icon={<UserCheck size={17} />} label="Active Users" value={activeCount} sub={`${Math.round(activeCount / Math.max(users.length, 1) * 100)}% online`} color="#10b981" delay={0.1} />
        <StatCard icon={<Shield size={17} />} label="Admins" value={adminCount} color="#f59e0b" delay={0.15} />
        <StatCard icon={<Zap size={17} />} label="Agents" value={agentCount} color="#60a5fa" delay={0.2} />
      </div>

      {/* ── Search + Filter Bar ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25 }}
        style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}
      >
        <div style={{
          flex: 1, minWidth: '240px', maxWidth: '400px',
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '0 14px',
          ...glass,
          borderRadius: '12px', height: '42px',
        }}>
          <Search size={15} style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search members..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              background: 'none', border: 'none', outline: 'none',
              fontSize: '13.5px', color: 'rgba(255,255,255,0.8)',
              flex: 1, fontFamily: 'DM Sans, sans-serif',
            }}
          />
        </div>

        <button style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '10px 16px', ...glass, borderRadius: '12px',
          color: 'rgba(255,255,255,0.5)', fontSize: '13px', fontWeight: 500,
          cursor: 'pointer', border: '1px solid rgba(255,255,255,0.06)',
          fontFamily: 'DM Sans, sans-serif', transition: 'all 0.2s',
        }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,0.25)'}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)'}
        >
          <Filter size={14} /> Filters
        </button>

        {search && (
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ fontSize: '12px', color: 'rgba(255,255,255,0.3)' }}>
            {filtered.length} result{filtered.length !== 1 ? 's' : ''}
          </motion.span>
        )}
      </motion.div>

      {/* ── Table ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        style={{ ...glass, overflow: 'hidden' }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          {/* Sticky header */}
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(139,92,246,0.08)' }}>
              {['Member', 'Role', 'AI Score', 'Status', ''].map((col, i) => (
                <th key={i} style={{
                  padding: '14px 20px',
                  fontSize: '10.5px', fontWeight: 700,
                  color: 'rgba(255,255,255,0.25)',
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                  textAlign: i === 4 ? 'right' : 'left',
                  whiteSpace: 'nowrap',
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {loading ? (
              /* Loading skeleton */
              [...Array(4)].map((_, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  {[...Array(5)].map((_, j) => (
                    <td key={j} style={{ padding: '18px 20px' }}>
                      <div style={{
                        height: '14px', borderRadius: '6px',
                        background: 'linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(139,92,246,0.06) 50%, rgba(255,255,255,0.04) 75%)',
                        backgroundSize: '200% 100%',
                        animation: 'shimmer 1.5s infinite',
                        width: j === 0 ? '160px' : j === 4 ? '60px' : '80px',
                      }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '60px', textAlign: 'center' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '56px', height: '56px', borderRadius: '16px',
                      background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Users size={24} style={{ color: 'rgba(139,92,246,0.5)' }} />
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.4)' }}>
                      {search ? 'No members found' : 'No members yet'}
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.2)' }}>
                      {search ? 'Try adjusting your search' : 'Add your first team member to get started'}
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((user, idx) => (
                <React.Fragment key={user.id}>
                  <UserRow
                    user={user}
                    onEdit={() => handleOpenModal(user)}
                    onDelete={() => handleDelete(user.id)}
                    delay={idx * 0.04}
                  />
                  {idx < filtered.length - 1 && (
                    <tr><td colSpan={5} style={{ padding: 0 }}>
                      <div style={{ height: '1px', background: 'rgba(255,255,255,0.03)', margin: '0 20px' }} />
                    </td></tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </motion.div>

      {/* ── Modal ── */}
      <PremiumModal
        open={showModal}
        onClose={() => setShowModal(false)}
        title={editUser ? 'Edit Member' : 'Add Member'}
      >
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: '10px', padding: '10px 14px', marginBottom: '20px',
              fontSize: '13px', color: '#fca5a5',
            }}
          >
            {error}
          </motion.div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <PremiumInput label="Email Address" type="email" value={formData.email} onChange={v => setFormData(p => ({ ...p, email: v }))} placeholder="member@company.com" required />
          <PremiumInput label="Full Name" value={formData.full_name} onChange={v => setFormData(p => ({ ...p, full_name: v }))} placeholder="Jane Smith" />
          <PremiumInput
            label="Password"
            type="password"
            value={formData.password}
            onChange={v => setFormData(p => ({ ...p, password: v }))}
            placeholder="••••••••"
            required={!editUser}
            hint={editUser ? '(leave blank to keep)' : undefined}
          />

          {/* Role Selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 700, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Role <span style={{ color: '#a78bfa' }}>*</span>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
              {(['USER', 'AGENT', 'ADMIN'] as const).map(role => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setFormData(p => ({ ...p, role }))}
                  style={{
                    padding: '8px', borderRadius: '10px', cursor: 'pointer',
                    fontFamily: 'DM Sans, sans-serif', fontSize: '12px', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    transition: 'all 0.2s',
                    ...(formData.role === role ? {
                      background: 'rgba(139,92,246,0.2)',
                      border: '1px solid rgba(139,92,246,0.4)',
                      color: '#c4b5fd',
                    } : {
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      color: 'rgba(255,255,255,0.35)',
                    }),
                  }}
                >
                  {role.charAt(0) + role.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Active toggle */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '12px 14px',
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '12px', cursor: 'pointer',
          }}>
            <div style={{ position: 'relative' }}>
              <input type="checkbox" checked={formData.is_active} onChange={e => setFormData(p => ({ ...p, is_active: e.target.checked }))} style={{ opacity: 0, position: 'absolute' }} />
              <div style={{
                width: '36px', height: '20px', borderRadius: '999px', transition: 'all 0.2s',
                background: formData.is_active ? 'rgba(16,185,129,0.5)' : 'rgba(255,255,255,0.1)',
                border: formData.is_active ? '1px solid rgba(16,185,129,0.4)' : '1px solid rgba(255,255,255,0.1)',
                position: 'relative', cursor: 'pointer',
              }} onClick={() => setFormData(p => ({ ...p, is_active: !p.is_active }))}>
                <div style={{
                  position: 'absolute', top: '2px',
                  left: formData.is_active ? '18px' : '2px',
                  width: '14px', height: '14px', borderRadius: '50%',
                  background: 'white', transition: 'left 0.2s',
                }} />
              </div>
            </div>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>Active Account</div>
              <div style={{ fontSize: '11.5px', color: 'rgba(255,255,255,0.3)' }}>User can sign in and access the workspace</div>
            </div>
          </label>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
            <button
              type="button"
              onClick={() => setShowModal(false)}
              style={{
                flex: 1, padding: '11px',
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px', color: 'rgba(255,255,255,0.5)',
                fontSize: '13.5px', fontWeight: 600, cursor: 'pointer',
                fontFamily: 'DM Sans, sans-serif', transition: 'all 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)'}
              onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={actionLoading}
              style={{
                flex: 2, padding: '11px',
                background: 'linear-gradient(135deg, rgba(124,58,237,0.8), rgba(79,70,229,0.8))',
                border: '1px solid rgba(167,139,250,0.3)',
                borderRadius: '12px', color: 'white',
                fontSize: '13.5px', fontWeight: 600, cursor: actionLoading ? 'not-allowed' : 'pointer',
                fontFamily: 'DM Sans, sans-serif',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                boxShadow: '0 4px 16px rgba(124,58,237,0.3)',
                transition: 'all 0.2s', opacity: actionLoading ? 0.7 : 1,
              }}
            >
              {actionLoading ? (
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                editUser ? 'Save Changes' : 'Create Member'
              )}
            </button>
          </div>
        </form>
      </PremiumModal>
    </div>
  );
};

export default UserList;