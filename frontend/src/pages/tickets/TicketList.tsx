import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, Plus, ChevronLeft, ChevronRight,
  Zap, AlertTriangle, TrendingUp, Clock, Activity,
  Target, Award, RefreshCw, Cpu, Trash2,
  ArrowUpRight, CheckCircle2, Circle, XCircle, AlertCircle, Bot, Sparkles, Loader2
} from 'lucide-react';
import { type Ticket, type RoutingResult, TicketStatus, TicketPriority, UserRole } from '../../types';

import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import { format } from 'date-fns';
import SLABadge from '../../components/sla/SLABadge';

/* ─── Global styles ───────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('tl-styles')) return;
  const s = document.createElement('style');
  s.id = 'tl-styles';
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');
    @keyframes tl-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }
    @keyframes tl-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
    @keyframes tl-shimmer { 0%{background-position:-700px 0} 100%{background-position:700px 0} }
    @keyframes tl-in { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
    @keyframes tl-spin { to{transform:rotate(360deg)} }
    @keyframes tl-toast { from{transform:translateX(100%); opacity:0} to{transform:translateX(0); opacity:1} }
    .tl-row { transition:background .18s ease; cursor:pointer; }
    .tl-row:hover { background:rgba(139,92,246,.065) !important; }
    .tl-kpi { transition:transform .3s,box-shadow .3s; }
    .tl-kpi:hover { transform:translateY(-4px); box-shadow:0 24px 48px rgba(0,0,0,.4) !important; }
    .tl-kpi:hover .tl-kpi-glow { opacity:1 !important; }
    .tl-filter-btn { transition:all .2s; }
    .tl-filter-btn:hover { background:rgba(255,255,255,.07) !important; }
    .tl-filter-btn.active { background:rgba(139,92,246,.18) !important; border-color:rgba(139,92,246,.45) !important; color:#c4b5fd !important; }
    .tl-insight { animation:tl-float 4s ease-in-out infinite; }
    .tl-insight:nth-child(2){animation-delay:-1s}
    .tl-insight:nth-child(3){animation-delay:-2s}
    .tl-insight:nth-child(4){animation-delay:-3s}
    .tl-shimmer {
      background:linear-gradient(90deg,rgba(255,255,255,.03) 25%,rgba(255,255,255,.08) 50%,rgba(255,255,255,.03) 75%);
      background-size:700px 100%; animation:tl-shimmer 1.5s infinite linear;
    }
    .tl-action-btn { transition:all .2s; }
    .tl-action-btn:hover { background:rgba(139,92,246,.15) !important; color:#c4b5fd !important; }
    .tl-del-btn:hover { background:rgba(239,68,68,.15) !important; color:#f87171 !important; }
    .tl-auto-btn { background:linear-gradient(135deg,rgba(139,92,246,.2) 0%,rgba(236,72,153,.2) 100%) !important; border:1px solid rgba(139,92,246,.3) !important; color:#c4b5fd !important; }
    .tl-auto-btn:hover { background:linear-gradient(135deg,rgba(139,92,246,.3) 0%,rgba(236,72,153,.3) 100%) !important; transform:translateY(-1px); }
    .tl-auto-btn:disabled { opacity:.5; cursor:not-allowed; }
  `;
  document.head.appendChild(s);
};

/* ─── Helpers ─────────────────────────────────────────────── */
const priorityConfig: Record<string, { color: string; glow: string; label: string }> = {
  URGENT:   { color: '#f87171', glow: 'rgba(239,68,68,.35)', label: 'Urgent' },
  HIGH:     { color: '#fb923c', glow: 'rgba(251,146,60,.3)', label: 'High' },
  MEDIUM:   { color: '#60a5fa', glow: 'rgba(96,165,250,.3)', label: 'Medium' },
  LOW:      { color: '#34d399', glow: 'rgba(52,211,153,.25)', label: 'Low' },
};

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  OPEN:        { color: '#60a5fa', bg: 'rgba(96,165,250,.12)', icon: <Circle size={10} />, label: 'Open' },
  IN_PROGRESS: { color: '#a78bfa', bg: 'rgba(167,139,250,.12)', icon: <Activity size={10} />, label: 'In Progress' },
  RESOLVED:    { color: '#34d399', bg: 'rgba(52,211,153,.12)', icon: <CheckCircle2 size={10} />, label: 'Resolved' },
  CLOSED:      { color: '#64748b', bg: 'rgba(100,116,139,.12)', icon: <XCircle size={10} />, label: 'Closed' },
  PENDING:     { color: '#fb923c', bg: 'rgba(251,146,60,.12)', icon: <AlertCircle size={10} />, label: 'Pending' },
};

const PriorityDot: React.FC<{ priority: string }> = ({ priority }) => {
  const cfg = priorityConfig[priority] ?? priorityConfig.MEDIUM;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.color, boxShadow: `0 0 6px ${cfg.glow}`, animation: priority === 'URGENT' ? 'tl-pulse 1.5s infinite' : 'none', flexShrink: 0 }} />
      <span style={{ fontSize: '.75rem', fontWeight: 700, color: cfg.color }}>{cfg.label}</span>
    </div>
  );
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg = statusConfig[status] ?? statusConfig.OPEN;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '.3rem', padding: '.28rem .7rem', borderRadius: 999, background: cfg.bg, border: `1px solid ${cfg.color}30`, fontSize: '.7rem', fontWeight: 700, color: cfg.color, whiteSpace: 'nowrap' }}>
      {cfg.icon} {cfg.label}
    </span>
  );
};

const MatchBadge: React.FC<{ quality: string }> = ({ quality }) => {
  const color = quality === 'Excellent Match' ? '#34d399' : quality === 'Good Match' ? '#60a5fa' : '#fb923c';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '.25rem', padding: '.15rem .45rem', borderRadius: 6, background: `${color}15`, border: `1px solid ${color}30`, fontSize: '.6rem', fontWeight: 700, color }}>
      <Sparkles size={8} /> {quality}
    </span>
  );
};

/* ─── KPI Card ────────────────────────────────────────────── */
const KpiCard: React.FC<{ label: string; value: string | number; insight: string; icon: React.ReactNode; color: string; delay?: number }> = ({ label, value, insight, icon, color, delay = 0 }) => (
  <div className="tl-kpi" style={{ position: 'relative', borderRadius: 20, padding: '1.375rem', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.08)', backdropFilter: 'blur(20px)', overflow: 'hidden', animation: `tl-in .5s ease ${delay}ms both` }}>
    <div className="tl-kpi-glow" style={{ position: 'absolute', inset: 0, opacity: 0, background: `radial-gradient(circle at 50% 0%, ${color}1a 0%, transparent 70%)`, transition: 'opacity .4s', pointerEvents: 'none' }} />
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '.75rem' }}>
      <div style={{ width: 38, height: 38, borderRadius: 11, background: `${color}18`, border: `1px solid ${color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', color, flexShrink: 0 }}>{icon}</div>
    </div>
    <div style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.875rem', color: '#f1f5f9', letterSpacing: '-0.02em', lineHeight: 1, marginBottom: '.3rem' }}>{value}</div>
    <div style={{ fontSize: '.7rem', fontWeight: 700, color: 'rgba(255,255,255,.35)', letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: '.5rem' }}>{label}</div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '.35rem', background: `${color}10`, border: `1px solid ${color}22`, borderRadius: 7, padding: '.3rem .55rem' }}>
      <div style={{ width: 5, height: 5, borderRadius: '50%', background: color, animation: 'tl-pulse 2s infinite', flexShrink: 0 }} />
      <span style={{ fontSize: '.68rem', color: 'rgba(255,255,255,.45)', lineHeight: 1.4 }}>{insight}</span>
    </div>
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg,transparent,${color}55,transparent)` }} />
  </div>
);

/* ─── Skeleton row ────────────────────────────────────────── */
const SkeletonRow: React.FC<{ i: number }> = ({ i }) => (
  <tr style={{ borderBottom: '1px solid rgba(255,255,255,.04)' }}>
    {[80, 200, 90, 80, 100, 60].map((w, j) => (
      <td key={j} style={{ padding: '.9rem 1.25rem' }}>
        <div className="tl-shimmer" style={{ height: 11, width: w, borderRadius: 4, animationDelay: `${i * 80}ms` }} />
      </td>
    ))}
  </tr>
);

/* ─── MAIN ────────────────────────────────────────────────── */
const TicketList: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [routingIds, setRoutingIds] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<any[]>([]);
  const [filter, setFilter] = useState({ status: '', priority: '', search: '' });
  const [currentPage, setCurrentPage] = useState(1);
  const { user } = useAuth();
  const ticketsPerPage = 10;

  useEffect(() => { injectStyles(); }, []);

  const addToast = (t: any) => {
    const id = Date.now();
    setToasts(prev => [...prev, { ...t, id }]);
    setTimeout(() => setToasts(prev => prev.filter(x => x.id !== id)), 5000);
  };

  const fetchTickets = async () => {
    setLoading(true);
    try { const r = await api.get('/tickets'); setTickets(r.data); }
    catch { /* silent */ } finally { setLoading(false); }
  };

  useEffect(() => { fetchTickets(); }, []);

  const handleAutoRoute = async (ticketId: string) => {
    setRoutingIds(prev => new Set(prev).add(ticketId));
    try {
      const response = await api.post<RoutingResult>(`/tickets/${ticketId}/auto-route`);
      const result = response.data;
      
      addToast({
        title: 'Auto Route Success',
        message: `Assigned to ${result.agent_name} (${result.team_name}). Score: ${result.confidence_score}%`,
        quality: result.match_quality,
        type: 'success'
      });
      
      fetchTickets();
    } catch (err: any) {
      addToast({
        title: 'Routing Failed',
        message: err.response?.data?.detail || 'An error occurred during AI routing.',
        type: 'error'
      });
    } finally {
      setRoutingIds(prev => {
        const next = new Set(prev);
        next.delete(ticketId);
        return next;
      });
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this ticket?')) return;
    try { await api.delete(`/tickets/${id}`); fetchTickets(); }
    catch { alert('Failed to delete ticket.'); }
  };

  const filtered = tickets.filter(t =>
    (filter.status === '' || t.status === filter.status) &&
    (filter.priority === '' || t.priority === filter.priority) &&
    (filter.search === '' || t.subject.toLowerCase().includes(filter.search.toLowerCase()) || (t.id && t.id.toLowerCase().includes(filter.search.toLowerCase())))
  );

  const totalPages = Math.ceil(filtered.length / ticketsPerPage);
  const paginated = filtered.slice((currentPage - 1) * ticketsPerPage, currentPage * ticketsPerPage);

  const openCount = tickets.filter(t => t.status === 'OPEN').length;
  const criticalCount = tickets.filter(t => t.priority === 'URGENT' || t.priority === 'HIGH').length;
  const resolvedToday = tickets.filter(t => t.status === 'RESOLVED').length;
  const atRiskCount = tickets.filter(t => t.sla_status === 'AT_RISK').length;
  const breachedCount = tickets.filter(t => t.sla_status === 'BREACHED').length;
  const onTrackCount = tickets.filter(t => !t.sla_status || t.sla_status === 'ON_TRACK').length;
  const slaCompliance = tickets.length > 0 ? Math.round(onTrackCount / tickets.length * 100) : 100;

  const insights = [
    { icon: <AlertTriangle size={13} />, text: `${atRiskCount + breachedCount} ticket(s) SLA à risque`, color: '#f87171' },
    { icon: <TrendingUp size={13} />, text: 'Response efficiency +14%', color: '#34d399' },
    { icon: <Cpu size={13} />, text: '12 repetitive incidents detected', color: '#a78bfa' },
    { icon: <Clock size={13} />, text: 'Workload spike predicted at 3 PM', color: '#fb923c' },
  ];

  const kpis = [
    { label: 'Total Tickets', value: tickets.length, insight: 'Across all categories', icon: <Target size={17} />, color: '#8b5cf6' },
    { label: 'Open Tickets', value: openCount, insight: 'Awaiting resolution', icon: <Circle size={17} />, color: '#60a5fa' },
    { label: 'Critical', value: criticalCount, insight: criticalCount > 0 ? 'Immediate attention needed' : 'All clear', icon: <AlertTriangle size={17} />, color: '#f87171' },
    { label: 'Resolved Today', value: resolvedToday, insight: `${Math.round(resolvedToday / Math.max(tickets.length, 1) * 100)}% resolution rate`, icon: <CheckCircle2 size={17} />, color: '#34d399' },
    { label: 'Avg Resolution', value: '4.2h', insight: '18% faster than baseline', icon: <Clock size={17} />, color: '#fb923c' },
    { label: 'SLA Compliance', value: `${slaCompliance}%`, insight: breachedCount > 0 ? `${breachedCount} dépassé(s)` : 'Above enterprise target', icon: <Award size={17} />, color: '#ec4899' },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '2rem', position: 'relative' }}>
      
      {/* Toast Container */}
      <div style={{ position: 'fixed', top: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: '1rem', pointerEvents: 'none' }}>
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents: 'auto', animation: 'tl-toast .3s ease both', background: 'rgba(15,15,25,.9)', border: `1px solid ${t.type === 'error' ? '#ef444450' : 'rgba(139,92,246,.3)'}`, backdropFilter: 'blur(16px)', borderRadius: 16, padding: '1rem', minWidth: 300, boxShadow: '0 20px 40px rgba(0,0,0,.4)', display: 'flex', gap: '.875rem' }}>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: t.type === 'error' ? '#ef444415' : 'rgba(139,92,246,.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: t.type === 'error' ? '#ef4444' : '#8b5cf6', flexShrink: 0 }}>
              {t.type === 'error' ? <XCircle size={20} /> : <Sparkles size={20} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '.25rem' }}>
                <h4 style={{ margin: 0, fontSize: '.875rem', fontWeight: 700, color: '#f1f5f9' }}>{t.title}</h4>
                {t.quality && <MatchBadge quality={t.quality} />}
              </div>
              <p style={{ margin: 0, fontSize: '.75rem', color: 'rgba(255,255,255,.5)', lineHeight: 1.4 }}>{t.message}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── HERO ─────────────────────────────────────────────── */}
      <div style={{ position: 'relative', borderRadius: 24, overflow: 'hidden', background: 'linear-gradient(135deg,rgba(10,10,20,.96) 0%,rgba(22,10,42,.96) 50%,rgba(10,10,20,.96) 100%)', border: '1px solid rgba(139,92,246,.2)', padding: '2.5rem' }}>
        <div style={{ position: 'absolute', top: -80, left: -80, width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle,rgba(139,92,246,.22) 0%,transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', bottom: -50, right: 120, width: 220, height: 220, borderRadius: '50%', background: 'radial-gradient(circle,rgba(59,130,246,.13) 0%,transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '2rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.7rem', marginBottom: '.875rem' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#8b5cf6', animation: 'tl-pulse 2s infinite' }} />
              <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(139,92,246,.75)', letterSpacing: '.1em', textTransform: 'uppercase' }}>AI Ticket Operations</span>
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: 'clamp(1.875rem,4vw,2.75rem)', color: '#f1f5f9', lineHeight: 1.1, letterSpacing: '-0.02em', margin: 0 }}>
              AI Ticket{' '}
              <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg,#8b5cf6,#ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Command Center</span>
            </h1>
            <p style={{ color: 'rgba(255,255,255,.42)', marginTop: '.75rem', fontSize: '.9375rem', maxWidth: 420, lineHeight: 1.65 }}>
              Monitor and manage intelligent support workflows. AI classifies, prioritizes, and routes every ticket automatically.
            </p>
            <div style={{ display: 'flex', gap: '.75rem', marginTop: '1.5rem', flexWrap: 'wrap' }}>
              <Link to="/tickets/create" style={{ display: 'flex', alignItems: 'center', gap: '.5rem', padding: '.75rem 1.5rem', background: 'linear-gradient(135deg,#7c3aed,#8b5cf6)', borderRadius: 12, color: '#fff', fontSize: '.875rem', fontWeight: 700, textDecoration: 'none', boxShadow: '0 8px 24px rgba(139,92,246,.35)', transition: 'all .2s' }}>
                <Plus size={16} /> New Ticket
              </Link>
              <button onClick={fetchTickets} style={{ display: 'flex', alignItems: 'center', gap: '.5rem', padding: '.75rem 1.25rem', background: 'rgba(255,255,255,.055)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, color: 'rgba(255,255,255,.55)', fontSize: '.875rem', fontWeight: 600, cursor: 'pointer', transition: 'all .2s' }}>
                <RefreshCw size={14} /> Sync
              </button>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.6rem', minWidth: 250 }}>
            {insights.map((w, i) => (
              <div key={i} className="tl-insight" style={{ display: 'flex', alignItems: 'center', gap: '.6rem', padding: '.6rem .875rem', background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 11, backdropFilter: 'blur(12px)' }}>
                <div style={{ color: w.color, flexShrink: 0 }}>{w.icon}</div>
                <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.55)', fontWeight: 500 }}>{w.text}</span>
                <div style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: w.color, animation: 'tl-pulse 2s infinite', flexShrink: 0 }} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── KPI GRID ─────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(175px,1fr))', gap: '1rem' }}>
        {kpis.map((k, i) => <KpiCard key={i} {...k} delay={i * 70} />)}
      </div>

      {/* ── FILTER BAR ───────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', padding: '.875rem 1.125rem', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 16, backdropFilter: 'blur(16px)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', flex: '1 1 220px', padding: '.6rem 1rem', background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 10 }}>
          <Search size={14} style={{ color: 'rgba(255,255,255,.3)', flexShrink: 0 }} />
          <input placeholder="AI semantic search…" value={filter.search} onChange={e => setFilter({ ...filter, search: e.target.value })} style={{ border: 'none', outline: 'none', background: 'transparent', fontSize: '.875rem', color: 'rgba(255,255,255,.7)', width: '100%', fontFamily: "'DM Sans',sans-serif" }} />
        </div>
        <div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap' }}>
          {['', ...Object.values(TicketStatus)].map(s => (
            <button key={s} className={`tl-filter-btn${filter.status === s ? ' active' : ''}`} onClick={() => setFilter({ ...filter, status: s })} style={{ padding: '.45rem .8rem', borderRadius: 8, fontSize: '.72rem', fontWeight: 700, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.4)', cursor: 'pointer', textTransform: s ? 'capitalize' : undefined }}>
              {s ? s.replace('_', ' ') : 'All Status'}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '.35rem' }}>
          {['', ...Object.values(TicketPriority)].map(p => (
            <button key={p} className={`tl-filter-btn${filter.priority === p ? ' active' : ''}`} onClick={() => setFilter({ ...filter, priority: p })} style={{ padding: '.45rem .8rem', borderRadius: 8, fontSize: '.72rem', fontWeight: 700, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: p ? (priorityConfig[p]?.color ?? 'rgba(255,255,255,.4)') : 'rgba(255,255,255,.4)', cursor: 'pointer' }}>
              {p || 'All Priority'}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: 'auto', fontSize: '.75rem', color: 'rgba(255,255,255,.28)', whiteSpace: 'nowrap' }}>{filtered.length} ticket{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {/* ── TABLE ────────────────────────────────────────────── */}
      <div style={{ borderRadius: 20, overflow: 'hidden', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,.07)' }}>
                {['ID', 'Subject & Category', 'Status', 'Priority', 'SLA', 'Created', 'Actions'].map((h, i) => (
                  <th key={i} style={{ padding: '.9rem 1.25rem', textAlign: 'left', fontSize: '.68rem', fontWeight: 700, letterSpacing: '.07em', color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', background: 'rgba(255,255,255,.02)', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }, (_, i) => <SkeletonRow key={i} i={i} />)
              ) : paginated.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: '5rem 2rem', textAlign: 'center' }}>
                  <div style={{ width: 60, height: 60, borderRadius: 18, margin: '0 auto 1.25rem', background: 'rgba(139,92,246,.08)', border: '1px solid rgba(139,92,246,.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Zap size={24} style={{ color: 'rgba(139,92,246,.55)' }} />
                  </div>
                  <p style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.375rem', color: 'rgba(255,255,255,.45)', marginBottom: '.5rem' }}>
                    {filter.search || filter.status || filter.priority ? 'No tickets match' : 'No tickets yet'}
                  </p>
                  <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.22)', marginBottom: '1.5rem' }}>
                    {filter.search ? 'Try a different search term.' : 'Create your first support ticket.'}
                  </p>
                  {!filter.search && !filter.status && !filter.priority && (
                    <Link to="/tickets/create" style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', padding: '.7rem 1.5rem', background: 'rgba(139,92,246,.18)', border: '1px solid rgba(139,92,246,.35)', borderRadius: 10, color: '#c4b5fd', fontWeight: 700, fontSize: '.875rem', textDecoration: 'none' }}>
                      <Plus size={15} /> Create Ticket
                    </Link>
                  )}
                </td></tr>
              ) : (
                paginated.map((ticket, i) => (
                  <tr key={ticket.id || i} className="tl-row" style={{ borderBottom: '1px solid rgba(255,255,255,.04)', animation: `tl-in .4s ease ${i * 50}ms both` }}>
                    <td style={{ padding: '.9rem 1.25rem' }}>
                      <span style={{ fontFamily: 'monospace', fontSize: '.72rem', fontWeight: 700, color: 'rgba(139,92,246,.7)' }}>#{ticket.id ? ticket.id.slice(-6).toUpperCase() : 'N/A'}</span>
                    </td>
                    <td style={{ padding: '.9rem 1.25rem', maxWidth: 280 }}>
                      <Link to={`/tickets/${ticket.id}`} style={{ display: 'block', fontWeight: 600, color: 'rgba(255,255,255,.8)', fontSize: '.875rem', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', transition: 'color .15s' }}>{ticket.subject}</Link>
                      <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)', marginTop: '.15rem', display: 'block' }}>{ticket.category} · {ticket.channel}</span>
                    </td>
                    <td style={{ padding: '.9rem 1.25rem' }}><StatusBadge status={ticket.status} /></td>
                    <td style={{ padding: '.9rem 1.25rem' }}><PriorityDot priority={ticket.priority} /></td>
                    <td style={{ padding: '.9rem 1.25rem' }}>
                      <SLABadge status={ticket.sla_status} deadline={ticket.sla_deadline} />
                    </td>
                    <td style={{ padding: '.9rem 1.25rem', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.35)' }}>{format(new Date(ticket.created_at), 'MMM dd, yyyy')}</span>
                    </td>
                    <td style={{ padding: '.9rem 1.25rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}>
                        {user?.role !== UserRole.USER && (ticket.status === 'OPEN' || ticket.status === 'IN_PROGRESS') && (
                          <button 
                            className="tl-action-btn tl-auto-btn" 
                            onClick={(e) => { e.stopPropagation(); handleAutoRoute(ticket.id); }}
                            disabled={routingIds.has(ticket.id)}
                            style={{ padding: '.35rem .75rem', borderRadius: 8, fontSize: '.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '.3rem', cursor: 'pointer' }}
                          >
                            {routingIds.has(ticket.id) ? <Loader2 size={12} className="animate-spin" style={{ animation: 'tl-spin 1s linear infinite' }} /> : <Bot size={12} />}
                            Auto Route
                          </button>
                        )}
                        <Link to={`/tickets/${ticket.id}`} className="tl-action-btn" style={{ padding: '.35rem .75rem', borderRadius: 8, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.45)', fontSize: '.75rem', fontWeight: 600, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '.3rem', transition: 'all .2s' }}>
                          <ArrowUpRight size={12} /> View
                        </Link>
                        {user?.role === UserRole.ADMIN && (
                          <button className="tl-action-btn tl-del-btn" onClick={(e) => { e.stopPropagation(); handleDelete(ticket.id); }} style={{ padding: '.35rem', borderRadius: 8, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.3)', cursor: 'pointer', display: 'flex', alignItems: 'center', transition: 'all .2s' }}>
                            <Trash2 size={12} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div style={{ padding: '.875rem 1.25rem', borderTop: '1px solid rgba(255,255,255,.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.3)' }}>
            Showing <strong style={{ color: 'rgba(255,255,255,.6)' }}>{Math.min((currentPage - 1) * ticketsPerPage + 1, filtered.length)}</strong>–<strong style={{ color: 'rgba(255,255,255,.6)' }}>{Math.min(currentPage * ticketsPerPage, filtered.length)}</strong> of <strong style={{ color: 'rgba(255,255,255,.6)' }}>{filtered.length}</strong>
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
            <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} style={{ padding: '.4rem', borderRadius: 8, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.45)', cursor: 'pointer', display: 'flex', opacity: currentPage === 1 ? .35 : 1 }}>
              <ChevronLeft size={16} />
            </button>
            <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.45)', padding: '0 .5rem' }}>{currentPage} / {totalPages || 1}</span>
            <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage >= totalPages} style={{ padding: '.4rem', borderRadius: 8, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.45)', cursor: 'pointer', display: 'flex', opacity: currentPage >= totalPages ? .35 : 1 }}>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TicketList;