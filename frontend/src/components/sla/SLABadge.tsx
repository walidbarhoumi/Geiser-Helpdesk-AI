import React, { useEffect } from 'react';
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';
import { type SLAStatus } from '../../types';

const slaConfig: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string; pulse?: boolean }> = {
  ON_TRACK: {
    color: '#34d399',
    bg: 'rgba(52,211,153,.12)',
    icon: <CheckCircle2 size={10} />,
    label: 'On Track',
  },
  AT_RISK: {
    color: '#fb923c',
    bg: 'rgba(251,146,60,.12)',
    icon: <Clock size={10} />,
    label: 'Délai proche',
    pulse: true,
  },
  BREACHED: {
    color: '#f87171',
    bg: 'rgba(239,68,68,.12)',
    icon: <AlertTriangle size={10} />,
    label: 'SLA Dépassé',
  },
};

function formatTimeRemaining(deadline?: string | null): string | null {
  if (!deadline) return null;
  const remainingMs = new Date(deadline).getTime() - Date.now();
  if (remainingMs <= 0) return null;
  const totalMin = Math.floor(remainingMs / 60000);
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

type SLABadgeProps = {
  status?: SLAStatus | string | null;
  deadline?: string | null;
  compact?: boolean;
};

const SLABadge: React.FC<SLABadgeProps> = ({ status = 'ON_TRACK', deadline, compact = false }) => {
  const cfg = slaConfig[status ?? 'ON_TRACK'] ?? slaConfig.ON_TRACK;
  const timeLeft = status === 'ON_TRACK' ? formatTimeRemaining(deadline) : null;
  const displayLabel = status === 'ON_TRACK' && timeLeft ? timeLeft : cfg.label;

  useEffect(() => {
    if (!document.getElementById('sla-badge-styles')) {
      const s = document.createElement('style');
      s.id = 'sla-badge-styles';
      s.textContent = `@keyframes sla-pulse { 0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(251,146,60,.4)} 50%{opacity:.85;box-shadow:0 0 0 4px rgba(251,146,60,.15)} }`;
      document.head.appendChild(s);
    }
  }, []);

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '.3rem',
        padding: compact ? '.2rem .55rem' : '.28rem .7rem',
        borderRadius: 999,
        background: cfg.bg,
        border: `1px solid ${cfg.color}30`,
        fontSize: compact ? '.65rem' : '.7rem',
        fontWeight: 700,
        color: cfg.color,
        whiteSpace: 'nowrap',
        animation: cfg.pulse ? 'sla-pulse 2s ease-in-out infinite' : undefined,
      }}
    >
      {cfg.icon} {displayLabel}
    </span>
  );
};

export default SLABadge;
