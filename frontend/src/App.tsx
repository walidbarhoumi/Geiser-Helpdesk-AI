import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink, useLocation, Outlet, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './store/authContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import { Toaster } from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Ticket, Users, Bot, Shield,
  LogOut, Zap, ChevronRight, Bell, Search, Settings,
  Activity, Command, Sparkles
} from 'lucide-react';

// Pages
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import Verify2FA from './pages/auth/Verify2FA';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import Dashboard from './pages/dashboard/Dashboard';
import TicketList from './pages/tickets/TicketList';
import TicketCreate from './pages/tickets/TicketCreate';
import TicketDetails from './pages/tickets/TicketDetails';
import AgentList from './pages/agents/AgentList';
import AgentCreate from './pages/agents/AgentCreate';
import TeamList from './pages/teams/TeamList';
import TeamCreate from './pages/teams/TeamCreate';
import UserList from './pages/users/UserList';
import Profile from './pages/profile/Profile';

import { UserRole } from './types';

/* ─────────────────────────────────────────────
   GLOBAL STYLES INJECTED ONCE
───────────────────────────────────────────── */
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --purple-50: #f5f3ff;
      --purple-100: #ede9fe;
      --purple-200: #ddd6fe;
      --purple-400: #a78bfa;
      --purple-500: #8b5cf6;
      --purple-600: #7c3aed;
      --purple-700: #6d28d9;
      --purple-900: #2e1065;
      --glass-bg: rgba(255,255,255,0.03);
      --glass-border: rgba(139,92,246,0.15);
      --glass-border-hover: rgba(139,92,246,0.35);
      --sidebar-width: 260px;
      --navbar-height: 64px;
      --bg-primary: #080812;
      --bg-secondary: #0d0d1a;
      --text-primary: rgba(255,255,255,0.95);
      --text-secondary: rgba(255,255,255,0.5);
      --text-muted: rgba(255,255,255,0.3);
    }

    html, body, #root { height: 100%; }

    body {
      font-family: 'DM Sans', sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 2px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.5); }

    /* Nav active state */
    .nav-item { transition: all 0.2s ease; }
    .nav-item:hover { background: rgba(139,92,246,0.08) !important; }
    .nav-item.active {
      background: rgba(139,92,246,0.15) !important;
      border-color: rgba(139,92,246,0.4) !important;
    }
    .nav-item.active .nav-icon { color: #a78bfa !important; }
    .nav-item.active .nav-label { color: #fff !important; }

    /* User card hover */
    .user-card {
      transition: background 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease, transform 0.18s ease;
      cursor: pointer;
    }
    .user-card:hover {
      background: rgba(109,40,217,0.1) !important;
      border-color: rgba(139,92,246,0.28) !important;
      box-shadow: 0 0 0 1px rgba(139,92,246,0.12), 0 4px 20px rgba(109,40,217,0.18) !important;
      transform: translateY(-1px);
    }
    .user-card:hover .user-card-avatar {
      box-shadow: 0 0 14px rgba(124,58,237,0.6) !important;
      border-color: rgba(139,92,246,0.6) !important;
    }
    .user-card:active { transform: translateY(0px); }

    /* Profile active state — highlight card when on /profile */
    .user-card-active {
      background: rgba(109,40,217,0.14) !important;
      border-color: rgba(139,92,246,0.35) !important;
      box-shadow: 0 0 0 1px rgba(139,92,246,0.14), 0 4px 20px rgba(109,40,217,0.2) !important;
    }
    .user-card-active .user-card-avatar {
      box-shadow: 0 0 14px rgba(124,58,237,0.55) !important;
      border-color: rgba(139,92,246,0.55) !important;
    }

    @keyframes ambientPulse {
      0%, 100% { opacity: 0.4; transform: scale(1); }
      50% { opacity: 0.6; transform: scale(1.05); }
    }
    @keyframes aiPulse {
      0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(139,92,246,0.4); }
      50% { opacity: 0.8; box-shadow: 0 0 0 6px rgba(139,92,246,0); }
    }
    @keyframes shimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-8px); }
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes avatarPulse {
      0%, 100% { box-shadow: 0 0 10px rgba(124,58,237,0.45); }
      50%       { box-shadow: 0 0 20px rgba(124,58,237,0.75); }
    }

    /* Custom toast overrides */
    .hot-toast-container > div {
      background: rgba(13,13,26,0.95) !important;
      border: 1px solid rgba(139,92,246,0.2) !important;
      backdrop-filter: blur(20px) !important;
      color: rgba(255,255,255,0.9) !important;
      border-radius: 14px !important;
      font-family: 'DM Sans', sans-serif !important;
      font-size: 14px !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(139,92,246,0.1) !important;
    }
  `}</style>
);

/* ─────────────────────────────────────────────
   AMBIENT BACKGROUND
───────────────────────────────────────────── */
const AmbientBackground: React.FC = () => (
  <div style={{ position: 'fixed', inset: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' }}>
    <div style={{
      position: 'absolute', top: '-20%', left: '10%',
      width: '600px', height: '600px',
      background: 'radial-gradient(circle, rgba(109,40,217,0.18) 0%, transparent 70%)',
      animation: 'ambientPulse 8s ease-in-out infinite',
      borderRadius: '50%',
    }} />
    <div style={{
      position: 'absolute', bottom: '10%', right: '-10%',
      width: '500px', height: '500px',
      background: 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)',
      animation: 'ambientPulse 10s ease-in-out infinite 2s',
      borderRadius: '50%',
    }} />
    <div style={{
      position: 'absolute', top: '50%', left: '40%',
      width: '400px', height: '400px',
      background: 'radial-gradient(circle, rgba(79,70,229,0.08) 0%, transparent 70%)',
      animation: 'ambientPulse 12s ease-in-out infinite 4s',
      borderRadius: '50%',
    }} />
    <div style={{
      position: 'absolute', inset: 0,
      backgroundImage: `
        linear-gradient(rgba(139,92,246,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(139,92,246,0.03) 1px, transparent 1px)
      `,
      backgroundSize: '60px 60px',
    }} />
    <div style={{
      position: 'absolute', inset: 0,
      backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\' opacity=\'0.04\'/%3E%3C/svg%3E")',
      opacity: 0.4,
    }} />
  </div>
);

/* ─────────────────────────────────────────────
   SIDEBAR NAV ITEM
───────────────────────────────────────────── */
const NavItem: React.FC<{ to: string; icon: React.ReactNode; label: string; badge?: number }> = ({ to, icon, label, badge }) => (
  <NavLink
    to={to}
    className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
    style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '10px 14px', borderRadius: '12px',
      border: '1px solid transparent',
      textDecoration: 'none', cursor: 'pointer',
    }}
  >
    <span className="nav-icon" style={{ color: 'rgba(255,255,255,0.35)', display: 'flex', flexShrink: 0 }}>
      {icon}
    </span>
    <span className="nav-label" style={{
      fontSize: '13.5px', fontWeight: 500,
      color: 'rgba(255,255,255,0.55)', flex: 1, letterSpacing: '0.01em',
    }}>
      {label}
    </span>
    {badge !== undefined && badge > 0 && (
      <span style={{
        padding: '2px 7px', background: 'rgba(139,92,246,0.25)',
        borderRadius: '999px', fontSize: '11px', fontWeight: 700,
        color: '#a78bfa',
      }}>
        {badge}
      </span>
    )}
  </NavLink>
);

/* ─────────────────────────────────────────────
   SIDEBAR
───────────────────────────────────────────── */
const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isProfileActive = location.pathname === '/profile';

  // ── Nav sections — Profile removed ──
  const navSections = [
    {
      label: 'Workspace',
      items: [
        { to: '/',        icon: <LayoutDashboard size={17} />, label: 'Dashboard' },
        { to: '/tickets', icon: <Ticket          size={17} />, label: 'Tickets'   },
      ]
    },
    ...(user?.role === UserRole.ADMIN || user?.role === UserRole.AGENT ? [{
      label: 'Operations',
      items: [
        { to: '/teams',  icon: <Users size={17} />, label: 'Teams'  },
        { to: '/agents', icon: <Bot   size={17} />, label: 'Agents' },
      ]
    }] : []),
    ...(user?.role === UserRole.ADMIN ? [{
      label: 'Admin',
      items: [
        { to: '/users', icon: <Shield size={17} />, label: 'Users' },
      ]
    }] : []),
  ];

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() ?? '?';

  return (
    <aside style={{
      position: 'fixed', top: '12px', left: '12px', bottom: '12px',
      width: 'var(--sidebar-width)',
      display: 'flex', flexDirection: 'column',
      background: 'rgba(10,10,20,0.7)',
      backdropFilter: 'blur(24px)',
      border: '1px solid rgba(139,92,246,0.12)',
      borderRadius: '20px',
      zIndex: 100,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid rgba(139,92,246,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px', height: '38px', borderRadius: '12px', flexShrink: 0,
            background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(124,58,237,0.4)',
          }}>
            <Sparkles size={18} style={{ color: 'white' }} />
          </div>
          <div>
            <div style={{
              fontSize: '14px', fontWeight: 700, color: 'rgba(255,255,255,0.95)',
              letterSpacing: '-0.01em',
            }}>
              Geiser
            </div>
            <div style={{ fontSize: '10.5px', color: 'rgba(139,92,246,0.7)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              GEISER AI Workspace
            </div>
          </div>
        </div>

        <div style={{
          marginTop: '14px',
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '6px 10px',
          background: 'rgba(139,92,246,0.08)',
          border: '1px solid rgba(139,92,246,0.15)',
          borderRadius: '8px',
        }}>
          <div style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: '#10b981',
            animation: 'aiPulse 2s ease-in-out infinite',
            flexShrink: 0,
          }} />
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'rgba(255,255,255,0.5)', letterSpacing: '0.06em' }}>
            AI SYSTEMS OPERATIONAL
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '12px 8px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navSections.map((section) => (
          <div key={section.label} style={{ marginBottom: '8px' }}>
            <div style={{
              fontSize: '10px', fontWeight: 700,
              color: 'rgba(255,255,255,0.2)',
              textTransform: 'uppercase', letterSpacing: '0.1em',
              padding: '8px 14px 4px',
            }}>
              {section.label}
            </div>
            {section.items.map(item => (
              <NavItem key={item.to} {...item} />
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 8px', borderTop: '1px solid rgba(139,92,246,0.08)' }}>
        {/* AI Productivity Score */}
        <div style={{
          padding: '10px 12px', marginBottom: '8px',
          background: 'rgba(139,92,246,0.06)',
          border: '1px solid rgba(139,92,246,0.1)',
          borderRadius: '12px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.04em' }}>
              AI PRODUCTIVITY
            </span>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#a78bfa' }}>87%</span>
          </div>
          <div style={{ height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '999px' }}>
            <div style={{
              width: '87%', height: '100%',
              background: 'linear-gradient(90deg, #7c3aed, #a78bfa)',
              borderRadius: '999px',
            }} />
          </div>
        </div>

        {/* ── CLICKABLE USER CARD ── */}
        <motion.div
          className={`user-card${isProfileActive ? ' user-card-active' : ''}`}
          onClick={() => navigate('/profile')}
          whileHover={{ y: -1 }}
          whileTap={{ y: 0, scale: 0.99 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 12px', borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.05)',
            background: 'rgba(255,255,255,0.02)',
            position: 'relative', overflow: 'hidden',
          }}
          title="View your profile"
        >
          {/* Shimmer highlight on active */}
          {isProfileActive && (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'linear-gradient(90deg, transparent 0%, rgba(139,92,246,0.06) 50%, transparent 100%)',
              pointerEvents: 'none',
            }} />
          )}

          {/* Avatar */}
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div
              className="user-card-avatar"
              style={{
                width: '34px', height: '34px', borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(124,58,237,0.6), rgba(79,70,229,0.6))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 700, color: 'white',
                border: '1px solid rgba(139,92,246,0.3)',
                transition: 'box-shadow 0.22s ease, border-color 0.22s ease',
                animation: isProfileActive ? 'avatarPulse 2.4s ease-in-out infinite' : undefined,
              }}
            >
              {initials}
            </div>
            <div style={{
              position: 'absolute', bottom: '-1px', right: '-1px',
              width: '9px', height: '9px', borderRadius: '50%',
              background: '#10b981', border: '2px solid #080812',
            }} />
          </div>

          {/* Name + role */}
          <div style={{ flex: 1, overflow: 'hidden', userSelect: 'none' }}>
            <div style={{
              fontSize: '12.5px', fontWeight: 600,
              color: isProfileActive ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.85)',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              transition: 'color 0.2s',
            }}>
              {user?.full_name || user?.email || 'User'}
            </div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', textTransform: 'capitalize' }}>
              {user?.role?.toLowerCase() || 'member'}
            </div>
          </div>

          {/* Logout — stops propagation so it doesn't trigger profile nav */}
          <button
            onClick={e => { e.stopPropagation(); logout(); }}
            title="Sign out"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,0.25)', padding: '4px',
              borderRadius: '6px', display: 'flex', alignItems: 'center',
              transition: 'color 0.2s',
              flexShrink: 0, position: 'relative', zIndex: 1,
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.25)')}
          >
            <LogOut size={15} />
          </button>
        </motion.div>
      </div>
    </aside>
  );
};

/* ─────────────────────────────────────────────
   TOP NAVBAR
───────────────────────────────────────────── */
const Navbar: React.FC = () => {
  const location = useLocation();

  const crumbMap: Record<string, string> = {
    '/': 'Dashboard',
    '/tickets': 'Tickets',
    '/tickets/create': 'Create Ticket',
    '/agents': 'Agents',
    '/agents/create': 'Create Agent',
    '/teams': 'Teams',
    '/teams/create': 'Create Team',
    '/users': 'Users',
    '/profile': 'Profile',
  };

  const currentPage = crumbMap[location.pathname] || 'Workspace';

  return (
    <header style={{
      position: 'fixed',
      top: '12px',
      left: `calc(var(--sidebar-width) + 24px)`,
      right: '12px',
      height: '56px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 16px 0 20px',
      background: 'rgba(10,10,20,0.6)',
      backdropFilter: 'blur(24px)',
      border: '1px solid rgba(139,92,246,0.1)',
      borderRadius: '16px',
      zIndex: 99,
      gap: '16px',
    }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.25)', fontWeight: 500 }}>
          Workspace
        </span>
        <ChevronRight size={12} style={{ color: 'rgba(255,255,255,0.2)' }} />
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>
          {currentPage}
        </span>
      </div>

      {/* Search Bar */}
      <div style={{
        flex: 1, maxWidth: '360px',
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '0 12px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(139,92,246,0.1)',
        borderRadius: '10px', height: '36px',
      }}>
        <Search size={14} style={{ color: 'rgba(255,255,255,0.25)', flexShrink: 0 }} />
        <input
          type="text"
          placeholder="Search workspace..."
          style={{
            background: 'none', border: 'none', outline: 'none',
            fontSize: '13px', color: 'rgba(255,255,255,0.7)',
            flex: 1, fontFamily: 'DM Sans, sans-serif',
          }}
        />
        <div style={{
          display: 'flex', alignItems: 'center', gap: '3px',
          padding: '2px 6px',
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '5px',
          flexShrink: 0,
        }}>
          <Command size={10} style={{ color: 'rgba(255,255,255,0.25)' }} />
          <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.25)', fontWeight: 600 }}>K</span>
        </div>
      </div>

      {/* Right actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '6px 12px',
          background: 'rgba(16,185,129,0.08)',
          border: '1px solid rgba(16,185,129,0.15)',
          borderRadius: '8px',
        }}>
          <Activity size={12} style={{ color: '#10b981' }} />
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'rgba(16,185,129,0.9)', letterSpacing: '0.04em' }}>
            LIVE
          </span>
        </div>

        <button style={{
          width: '36px', height: '36px', borderRadius: '10px',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(139,92,246,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', position: 'relative',
          color: 'rgba(255,255,255,0.4)', transition: 'all 0.2s',
        }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.1)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.8)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
          }}
        >
          <Bell size={15} />
          <div style={{
            position: 'absolute', top: '8px', right: '8px',
            width: '6px', height: '6px', borderRadius: '50%',
            background: '#a78bfa', border: '1.5px solid #080812',
          }} />
        </button>

        <button style={{
          width: '36px', height: '36px', borderRadius: '10px',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(139,92,246,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer',
          color: 'rgba(255,255,255,0.4)', transition: 'all 0.2s',
        }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.1)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.8)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
          }}
        >
          <Settings size={15} />
        </button>
      </div>
    </header>
  );
};

/* ─────────────────────────────────────────────
   PAGE TRANSITION WRAPPER
───────────────────────────────────────────── */
const PageTransition: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        style={{ height: '100%' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
};

/* ─────────────────────────────────────────────
   APP LAYOUT
───────────────────────────────────────────── */
const AppLayout: React.FC = () => {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', position: 'relative' }}>
      <AmbientBackground />
      <Sidebar />
      <Navbar />
      <main style={{
        marginLeft: `calc(var(--sidebar-width) + 24px)`,
        marginRight: '12px',
        marginTop: `calc(56px + 24px)`,
        marginBottom: '12px',
        paddingTop: '8px',
        position: 'relative', zIndex: 1,
        minHeight: 'calc(100vh - 56px - 36px)',
      }}>
        <PageTransition>
          <Outlet />
        </PageTransition>
      </main>
    </div>
  );
};

/* ─────────────────────────────────────────────
   CUSTOM TOASTER CONFIG
───────────────────────────────────────────── */
const CustomToaster = () => (
  <Toaster
    position="top-right"
    gutter={8}
    toastOptions={{
      duration: 4000,
      style: {
        background: 'rgba(13,13,26,0.95)',
        color: 'rgba(255,255,255,0.9)',
        border: '1px solid rgba(139,92,246,0.2)',
        backdropFilter: 'blur(20px)',
        borderRadius: '14px',
        fontFamily: "'DM Sans', sans-serif",
        fontSize: '13.5px',
        padding: '12px 16px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      },
      success: {
        iconTheme: { primary: '#10b981', secondary: 'rgba(13,13,26,0.95)' },
        style: { borderColor: 'rgba(16,185,129,0.25)' },
      },
      error: {
        iconTheme: { primary: '#ef4444', secondary: 'rgba(13,13,26,0.95)' },
        style: { borderColor: 'rgba(239,68,68,0.25)' },
      },
    }}
  />
);

/* ─────────────────────────────────────────────
   ROOT APP
───────────────────────────────────────────── */
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <GlobalStyles />
      <AuthProvider>
        <CustomToaster />
        <Routes>
          <Route path="/login"           element={<Login />} />
          <Route path="/register"        element={<Register />} />
          <Route path="/verify-2fa"      element={<Verify2FA />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />

          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/"               element={<Dashboard />} />
            <Route path="/tickets"        element={<TicketList />} />
            <Route path="/tickets/create" element={<TicketCreate />} />
            <Route path="/tickets/:id"    element={<TicketDetails />} />
            <Route path="/profile"        element={<Profile />} />

            <Route path="/users" element={
              <ProtectedRoute roles={[UserRole.ADMIN]}><UserList /></ProtectedRoute>
            } />
            <Route path="/agents" element={
              <ProtectedRoute roles={[UserRole.ADMIN]}><AgentList /></ProtectedRoute>
            } />
            <Route path="/agents/create" element={
              <ProtectedRoute roles={[UserRole.ADMIN]}><AgentCreate /></ProtectedRoute>
            } />
            <Route path="/teams" element={
              <ProtectedRoute roles={[UserRole.AGENT, UserRole.ADMIN]}><TeamList /></ProtectedRoute>
            } />
            <Route path="/teams/create" element={
              <ProtectedRoute roles={[UserRole.AGENT, UserRole.ADMIN]}><TeamCreate /></ProtectedRoute>
            } />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;