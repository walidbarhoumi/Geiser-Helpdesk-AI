import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, Download, RefreshCw, AlertTriangle, Info,
  XCircle, Search, Filter, Activity, Lock, Eye
} from 'lucide-react';
import api from '../../api/axios';
import { type SecurityAuditLog, type AuditStats } from '../../types';
import { format } from 'date-fns';

/* ─── Styles ─────────────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('audit-styles')) return;
  const s = document.createElement('style');
  s.id = 'audit-styles';
  s.textContent = `
    @keyframes audit-in { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
    @keyframes audit-spin { to{transform:rotate(360deg)} }
    @keyframes audit-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
    .audit-glass { background:rgba(10,10,20,.75); border:1px solid rgba(255,255,255,.07); backdrop-filter:blur(20px); border-radius:20px; }
    .audit-row { transition:background .15s; }
    .audit-row:hover { background:rgba(139,92,246,.06) !important; }
    .audit-filter-btn { transition:all .2s; cursor:pointer; }
    .audit-filter-btn:hover { background:rgba(139,92,246,.15) !important; border-color:rgba(139,92,246,.3) !important; }
    .audit-filter-btn.active { background:rgba(139,92,246,.2) !important; border-color:rgba(139,92,246,.4) !important; color:#c4b5fd !important; }
    .audit-export-btn { background:linear-gradient(135deg,rgba(16,185,129,.2),rgba(5,150,105,.2)); border:1px solid rgba(16,185,129,.3); color:#34d399; transition:all .2s; cursor:pointer; }
    .audit-export-btn:hover { background:linear-gradient(135deg,rgba(16,185,129,.3),rgba(5,150,105,.3)); transform:translateY(-1px); }
    .audit-export-btn:disabled { opacity:.5; cursor:not-allowed; transform:none; }
  `;
  document.head.appendChild(s);
};

/* ─── Severity Badge ──────────────────────────────────────── */
const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const cfg = {
    INFO:     { color: '#34d399', bg: 'rgba(52,211,153,.12)',  border: 'rgba(52,211,153,.25)',  Icon: Info },
    WARNING:  { color: '#fbbf24', bg: 'rgba(251,191,36,.12)', border: 'rgba(251,191,36,.25)',  Icon: AlertTriangle },
    CRITICAL: { color: '#ef4444', bg: 'rgba(239,68,68,.12)',  border: 'rgba(239,68,68,.25)',   Icon: XCircle },
  }[severity] ?? { color: '#94a3b8', bg: 'rgba(148,163,184,.1)', border: 'rgba(148,163,184,.2)', Icon: Info };

  const { color, bg, border, Icon } = cfg;

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '2px 8px', borderRadius: 999,
      background: bg, border: `1px solid ${border}`,
      fontSize: '.7rem', fontWeight: 700, color, letterSpacing: '.04em',
    }}>
      <Icon size={10} />
      {severity}
    </span>
  );
};

/* ─── Category Badge ──────────────────────────────────────── */
const CategoryBadge: React.FC<{ category: string }> = ({ category }) => {
  const colors: Record<string, string> = {
    AUTH: '#818cf8', ACCESS_CONTROL: '#f472b6', TICKET: '#60a5fa',
    SLA: '#34d399', USER_MGMT: '#a78bfa', TELECOM: '#fb923c',
    DATA_EXPORT: '#facc15', SYSTEM: '#94a3b8',
  };
  const color = colors[category] ?? '#94a3b8';
  return (
    <span style={{
      fontSize: '.65rem', fontWeight: 700, color,
      background: `${color}18`, border: `1px solid ${color}30`,
      padding: '1px 7px', borderRadius: 999, letterSpacing: '.04em',
    }}>
      {category.replace('_', ' ')}
    </span>
  );
};

/* ─── Stats Card ──────────────────────────────────────────── */
const StatCard: React.FC<{
  label: string; value: number | string; icon: React.ReactNode;
  color: string; subtitle?: string;
}> = ({ label, value, icon, color, subtitle }) => (
  <div className="audit-glass" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ fontSize: '.7rem', fontWeight: 700, color: 'rgba(255,255,255,.35)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</span>
      <span style={{ color }}>{icon}</span>
    </div>
    <div style={{ fontSize: '1.75rem', fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
    {subtitle && <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.25)' }}>{subtitle}</div>}
  </div>
);

/* ─── Main Component ──────────────────────────────────────── */
const AuditTrail: React.FC = () => {
  const [logs, setLogs] = useState<SecurityAuditLog[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => { injectStyles(); }, []);

  const fetchData = useCallback(async (resetPage = false) => {
    setLoading(true);
    try {
      const currentPage = resetPage ? 1 : page;
      const params: Record<string, string | number> = { page: currentPage, page_size: 25 };
      if (severityFilter) params.severity = severityFilter;
      if (categoryFilter) params.event_category = categoryFilter;
      if (searchQuery)    params.actor_email = searchQuery;

      const [logsRes, statsRes] = await Promise.all([
        api.get('/audit/logs', { params }),
        api.get('/audit/stats'),
      ]);

      const data: SecurityAuditLog[] = logsRes.data?.logs ?? logsRes.data ?? [];
      setLogs(resetPage ? data : (prev) => [...prev, ...data]);
      setHasMore(data.length === 25);
      setStats(statsRes.data);
      if (resetPage) setPage(1);
    } catch (err) {
      console.error('Audit fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, severityFilter, categoryFilter, searchQuery]);

  useEffect(() => { fetchData(true); }, [severityFilter, categoryFilter]);

  useEffect(() => { fetchData(); }, [page]);

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const res = await api.get('/audit/export', { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_log_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
    } finally {
      setExporting(false);
    }
  };

  const SEVERITIES = ['', 'INFO', 'WARNING', 'CRITICAL'];
  const CATEGORIES = ['', 'AUTH', 'ACCESS_CONTROL', 'TICKET', 'SLA', 'USER_MGMT', 'DATA_EXPORT', 'SYSTEM'];

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '1.75rem', animation: 'audit-in .5s ease both' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.875rem' }}>
          <div style={{
            width: 44, height: 44, borderRadius: 14,
            background: 'linear-gradient(135deg,rgba(239,68,68,.25),rgba(220,38,38,.15))',
            border: '1px solid rgba(239,68,68,.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={20} style={{ color: '#ef4444' }} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-.02em' }}>
              Audit & Sécurité
            </h1>
            <p style={{ margin: 0, fontSize: '.78rem', color: 'rgba(255,255,255,.35)' }}>
              Journal d'audit ISO/IEC 27001:2013 — Piste d'audit immuable
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '.75rem' }}>
          <button
            onClick={() => fetchData(true)}
            disabled={loading}
            style={{
              display: 'flex', alignItems: 'center', gap: '.4rem',
              padding: '.55rem 1rem', borderRadius: 10,
              background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
              color: 'rgba(255,255,255,.5)', fontSize: '.8rem', fontWeight: 600, cursor: 'pointer',
              transition: 'all .2s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,.12)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,.04)'; }}
          >
            <RefreshCw size={14} style={{ animation: loading ? 'audit-spin 1s linear infinite' : 'none' }} />
            Actualiser
          </button>

          <button
            onClick={handleExportCSV}
            disabled={exporting}
            className="audit-export-btn"
            style={{
              display: 'flex', alignItems: 'center', gap: '.4rem',
              padding: '.55rem 1rem', borderRadius: 10,
              fontSize: '.8rem', fontWeight: 600,
            }}
          >
            <Download size={14} />
            {exporting ? 'Export...' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* ── Stats Cards ── */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
          <StatCard label="Total Événements" value={stats.total_events} icon={<Activity size={18} />} color="#a78bfa" subtitle="Toutes catégories" />
          <StatCard label="Avertissements" value={stats.warning_count} icon={<AlertTriangle size={18} />} color="#fbbf24" subtitle="Anomalies détectées" />
          <StatCard label="Critiques" value={stats.critical_count} icon={<XCircle size={18} />} color="#ef4444" subtitle="Incidents sécurité" />
          <StatCard label="Échecs Login" value={stats.login_failures} icon={<Lock size={18} />} color="#fb923c" subtitle="Tentatives refusées" />
          <StatCard label="Accès Refusés" value={stats.access_denied_count} icon={<Eye size={18} />} color="#f472b6" subtitle="Violations RBAC" />
        </div>
      )}

      {/* ── Filters ── */}
      <div className="audit-glass" style={{ padding: '1rem 1.25rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Search */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '.5rem',
          background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
          borderRadius: 10, padding: '.4rem .875rem', flex: '1 1 200px',
        }}>
          <Search size={13} style={{ color: 'rgba(255,255,255,.25)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Filtrer par email acteur..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchData(true)}
            style={{ background: 'none', border: 'none', outline: 'none', fontSize: '.8rem', color: 'rgba(255,255,255,.7)', fontFamily: 'inherit', flex: 1 }}
          />
        </div>

        {/* Severity filter */}
        <div style={{ display: 'flex', gap: '.4rem', alignItems: 'center' }}>
          <Filter size={13} style={{ color: 'rgba(255,255,255,.25)' }} />
          {SEVERITIES.map(sev => (
            <button
              key={sev || 'ALL'}
              onClick={() => setSeverityFilter(sev)}
              className={`audit-filter-btn${severityFilter === sev ? ' active' : ''}`}
              style={{
                padding: '.3rem .7rem', borderRadius: 8, fontSize: '.7rem', fontWeight: 700,
                background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
                color: 'rgba(255,255,255,.4)', cursor: 'pointer', letterSpacing: '.04em',
              }}
            >
              {sev || 'TOUT'}
            </button>
          ))}
        </div>

        {/* Category select */}
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          style={{
            background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)',
            borderRadius: 10, padding: '.4rem .875rem', fontSize: '.78rem',
            color: 'rgba(255,255,255,.6)', fontFamily: 'inherit', cursor: 'pointer', outline: 'none',
          }}
        >
          {CATEGORIES.map(cat => (
            <option key={cat || 'all'} value={cat} style={{ background: '#0d0d1a' }}>
              {cat || 'Toutes catégories'}
            </option>
          ))}
        </select>
      </div>

      {/* ── Table ── */}
      <div className="audit-glass" style={{ overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.8rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,.07)' }}>
                {['Horodatage', 'Sévérité', 'Catégorie', 'Événement', 'Acteur', 'IP Client', 'Statut'].map(h => (
                  <th key={h} style={{
                    padding: '.75rem 1rem', textAlign: 'left',
                    fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.3)',
                    textTransform: 'uppercase', letterSpacing: '.06em', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255,255,255,.2)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '.75rem' }}>
                      <RefreshCw size={16} style={{ animation: 'audit-spin 1s linear infinite', color: '#8b5cf6' }} />
                      Chargement des logs d'audit…
                    </div>
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255,255,255,.2)' }}>
                    Aucun événement d'audit trouvé.
                  </td>
                </tr>
              ) : logs.map((log, idx) => (
                <tr
                  key={log.id ?? idx}
                  className="audit-row"
                  style={{ borderBottom: '1px solid rgba(255,255,255,.04)' }}
                >
                  <td style={{ padding: '.75rem 1rem', color: 'rgba(255,255,255,.4)', whiteSpace: 'nowrap' }}>
                    {log.timestamp ? format(new Date(log.timestamp), 'dd/MM/yy HH:mm:ss') : '—'}
                  </td>
                  <td style={{ padding: '.75rem 1rem' }}>
                    <SeverityBadge severity={log.severity} />
                  </td>
                  <td style={{ padding: '.75rem 1rem' }}>
                    <CategoryBadge category={log.event_category} />
                  </td>
                  <td style={{ padding: '.75rem 1rem', color: '#e2e8f0', fontWeight: 600, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.event_type}
                  </td>
                  <td style={{ padding: '.75rem 1rem', color: 'rgba(255,255,255,.5)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.actor_email ?? log.actor_id ?? '—'}
                  </td>
                  <td style={{ padding: '.75rem 1rem', color: 'rgba(255,255,255,.3)', fontFamily: 'monospace', fontSize: '.75rem' }}>
                    {log.client_ip ?? '—'}
                  </td>
                  <td style={{ padding: '.75rem 1rem' }}>
                    <span style={{
                      fontSize: '.7rem', fontWeight: 700, letterSpacing: '.04em',
                      color: log.status === 'SUCCESS' ? '#34d399' : '#ef4444',
                    }}>
                      {log.status ?? '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Load More */}
        {hasMore && !loading && logs.length > 0 && (
          <div style={{ padding: '1rem', textAlign: 'center', borderTop: '1px solid rgba(255,255,255,.05)' }}>
            <button
              onClick={() => setPage(p => p + 1)}
              style={{
                padding: '.5rem 1.5rem', borderRadius: 10, fontSize: '.8rem', fontWeight: 600,
                background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.2)',
                color: '#c4b5fd', cursor: 'pointer', transition: 'all .2s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,.2)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,.12)'; }}
            >
              Charger plus
            </button>
          </div>
        )}
      </div>

      {/* ISO 27001 footer note */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '.5rem',
        padding: '.75rem 1rem', borderRadius: 10,
        background: 'rgba(239,68,68,.05)', border: '1px solid rgba(239,68,68,.1)',
      }}>
        <Shield size={13} style={{ color: '#ef4444', flexShrink: 0 }} />
        <span style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.3)' }}>
          Conforme ISO/IEC 27001:2013 — A.12.4 Journalisation et surveillance.
          Les logs d'audit sont immuables et conservés conformément à la politique de rétention.
        </span>
      </div>
    </div>
  );
};

export default AuditTrail;
