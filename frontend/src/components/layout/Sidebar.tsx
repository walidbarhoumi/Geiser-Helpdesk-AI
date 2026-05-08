import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Ticket,
  Users,
  ShieldCheck,
  UserCircle,
  LogOut,
  Plus,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { useAuth } from '../../store/authContext';
import { UserRole } from '../../types';

type NavItem = {
  to: string;
  icon: React.ReactNode;
  label: string;
  roles: UserRole[];
  children?: { to: string; label: string }[];
};

const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  const navItems: NavItem[] = [
    {
      to: '/',
      icon: <LayoutDashboard size={18} />,
      label: 'Dashboard',
      roles: [UserRole.USER, UserRole.AGENT, UserRole.ADMIN],
    },
    {
      to: '/tickets',
      icon: <Ticket size={18} />,
      label: 'Tickets',
      roles: [UserRole.USER, UserRole.AGENT, UserRole.ADMIN],
      children: [
        { to: '/tickets', label: 'All Tickets' },
        { to: '/tickets/create', label: 'New Ticket' },
      ],
    },
    {
      to: '/users',
      icon: <Users size={18} />,
      label: 'Users',
      roles: [UserRole.ADMIN],
    },
    {
      to: '/agents',
      icon: <ShieldCheck size={18} />,
      label: 'Agents',
      roles: [UserRole.ADMIN],
      children: [
        { to: '/agents', label: 'All Agents' },
        { to: '/agents/create', label: 'Add Agent' },
      ],
    },
    {
      to: '/teams',
      icon: <Users size={18} />,
      label: 'Teams',
      roles: [UserRole.AGENT, UserRole.ADMIN],
      children: [
        { to: '/teams', label: 'All Teams' },
        { to: '/teams/create', label: 'Create Team' },
      ],
    },
    {
      to: '/profile',
      icon: <UserCircle size={18} />,
      label: 'Profile',
      roles: [UserRole.USER, UserRole.AGENT, UserRole.ADMIN],
    },
  ];

  const filtered = navItems.filter(
    item => user && item.roles.includes(user.role)
  );

  const toggleGroup = (label: string) => {
    setOpenGroups(prev => ({ ...prev, [label]: !prev[label] }));
  };

  const activeLinkStyle: React.CSSProperties = {
    background: 'rgba(99,102,241,0.1)',
    color: '#6366f1',
    fontWeight: 700,
  };
  const baseLinkStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '0.75rem',
    padding: '0.625rem 0.875rem', borderRadius: '0.75rem',
    fontSize: '0.875rem', fontWeight: 600,
    color: '#64748b', textDecoration: 'none',
    transition: 'all 0.15s', cursor: 'pointer',
    border: 'none', background: 'none', width: '100%', textAlign: 'left' as const,
    fontFamily: 'inherit'
  };

  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      height: '100vh',
      position: 'fixed',
      left: 0, top: 0,
      zIndex: 100,
      background: 'white',
      borderRight: '1px solid #f1f5f9',
      display: 'flex', flexDirection: 'column',
      padding: '1.5rem 1rem',
      overflowY: 'auto'
    }}>
      {/* Logo */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '0.625rem',
        marginBottom: '2rem', paddingLeft: '0.25rem'
      }}>
        <div style={{
          width: '34px', height: '34px',
          background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
          borderRadius: '10px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontWeight: 800, fontSize: '1rem',
          boxShadow: '0 4px 10px rgba(99,102,241,0.4)'
        }}>
          G
        </div>
        <span style={{
          fontSize: '1.25rem', fontWeight: 800, color: '#0f172a',
          letterSpacing: '-0.025em'
        }}>
          Geiser
        </span>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {filtered.map(item => {
          const hasChildren = item.children && item.children.length > 0;
          const isOpen = openGroups[item.label] ?? false;

          if (!hasChildren) {
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                style={({ isActive }) => ({
                  ...baseLinkStyle,
                  ...(isActive ? activeLinkStyle : {})
                })}
              >
                <span style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: '28px', height: '28px', borderRadius: '8px',
                  background: 'inherit', flexShrink: 0
                }}>
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            );
          }

          return (
            <div key={item.label}>
              {/* Group toggle button */}
              <button
                onClick={() => toggleGroup(item.label)}
                style={{
                  ...baseLinkStyle,
                  justifyContent: 'space-between'
                }}
                onMouseEnter={e => {
                  if (!isOpen) (e.currentTarget as HTMLElement).style.background = '#f8fafc';
                }}
                onMouseLeave={e => {
                  if (!isOpen) (e.currentTarget as HTMLElement).style.background = 'none';
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0
                  }}>
                    {item.icon}
                  </span>
                  {item.label}
                </span>
                {isOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>

              {/* Children */}
              {isOpen && (
                <div style={{
                  marginLeft: '1rem', paddingLeft: '0.875rem',
                  borderLeft: '2px solid #f1f5f9',
                  marginTop: '0.25rem', marginBottom: '0.25rem',
                  display: 'flex', flexDirection: 'column', gap: '0.125rem'
                }}>
                  {item.children!.map(child => (
                    <NavLink
                      key={child.to}
                      to={child.to}
                      end
                      style={({ isActive }) => ({
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                        padding: '0.5rem 0.75rem', borderRadius: '0.625rem',
                        fontSize: '0.8125rem', fontWeight: 600,
                        textDecoration: 'none', transition: 'all 0.15s',
                        color: isActive ? '#6366f1' : '#64748b',
                        background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent',
                      })}
                    >
                      {child.label.startsWith('New') || child.label.startsWith('Add') || child.label.startsWith('Create') ? (
                        <Plus size={13} style={{ flexShrink: 0 }} />
                      ) : (
                        <span style={{
                          width: '6px', height: '6px', borderRadius: '50%',
                          background: 'currentColor', flexShrink: 0
                        }} />
                      )}
                      {child.label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* User footer */}
      <div style={{
        borderTop: '1px solid #f1f5f9', paddingTop: '1rem',
        display: 'flex', flexDirection: 'column', gap: '0.5rem'
      }}>
        {/* User info */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            padding: '0.625rem 0.75rem', borderRadius: '0.75rem',
            cursor: 'pointer'
          }}
          onClick={() => navigate('/profile')}
        >
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: 'white', display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontWeight: 800, fontSize: '0.875rem',
            flexShrink: 0
          }}>
            {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
          </div>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <p style={{
              fontWeight: 700, fontSize: '0.8125rem', color: '#0f172a',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
            }}>
              {user?.full_name || 'User'}
            </p>
            <p style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600, marginTop: '0.125rem' }}>
              {user?.role}
            </p>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          style={{
            ...baseLinkStyle,
            color: '#ef4444',
          }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#fef2f2'}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'none'}
        >
          <LogOut size={18} />
          Sign Out
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
