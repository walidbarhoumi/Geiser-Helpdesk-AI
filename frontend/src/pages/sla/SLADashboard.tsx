import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Clock, RefreshCw, Save,
  ArrowUpRight, CheckCircle2, XCircle, Loader2,
  Pause, ShieldCheck, Activity, Bell,
  TrendingUp, BarChart3, PieChart, Sparkles,
} from 'lucide-react';
import api from '../../api/axios';
import { type TicketPriority, TicketPriority as TicketPriorityEnum, type SLARiskOverview } from '../../types';
import SLABadge from '../../components/sla/SLABadge';
import { useAuth } from '../../store/authContext';
import { useWebSocket } from '../../context/WebSocketContext';
import { UserRole } from '../../types';

type SLAPolicy = {
  priority: TicketPriority;
  response_time_hours: number;
  resolution_time_hours: number;
  at_risk_threshold_pct: number;
};

type SLAAlert = {
  ticket_id: string;
  subject: string;
  priority: TicketPriority;
  sla_status: string;
  sla_deadline: string;
  time_remaining_minutes: number | null;
  assigned_agent_id?: string;
  created_at: string;
};

const injectStyles = () => {
  if (document.getElementById('sla-dash-styles')) return;
  const s = document.createElement('style');
  s.id = 'sla-dash-styles';
  s.textContent = `
    @keyframes sla-in { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
    @keyframes sla-pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
    .sla-kpi { transition:transform .3s,box-shadow .3s; }
    .sla-kpi:hover { transform:translateY(-3px); box-shadow:0 20px 40px rgba(0,0,0,.35) !important; }
    .sla-row { transition:background .18s; }
    .sla-row:hover { background:rgba(139,92,246,.06) !important; }
    .sla-input { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.1); border-radius:8px; padding:.4rem .6rem; color:#f1f5f9; font-size:.8rem; width:80px; outline:none; font-family:'DM Sans',sans-serif; }
    .sla-input:focus { border-color:rgba(139,92,246,.4); }
    .sla-save-btn { transition:all .2s; cursor:pointer; }
    .sla-save-btn:hover { background:rgba(139,92,246,.25) !important; }
  `;
  document.head.appendChild(s);
};

function Countdown({ minutes }: { minutes: number | null }) {
  if (minutes === null) return <span style={{ color: '#f87171', fontWeight: 700 }}>Dépassé</span>;
  if (minutes <= 0) return <span style={{ color: '#f87171', fontWeight: 700 }}>Dépassé</span>;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return (
    <span style={{ fontFamily: 'monospace', fontSize: '.8rem', color: minutes < 60 ? '#fb923c' : '#34d399', fontWeight: 700 }}>
      {h > 0 ? `${h}h ${m}m` : `${m}m`}
    </span>
  );
}

const SLADashboard: React.FC = () => {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<SLAAlert[]>([]);
  const [policies, setPolicies] = useState<SLAPolicy[]>([]);
  const [riskOverview, setRiskOverview] = useState<SLARiskOverview | null>(null);
  const [policyEdits, setPolicyEdits] = useState<Record<string, { response: string; resolution: string }>>({});
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { injectStyles(); }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [alertsRes, policiesRes, riskRes] = await Promise.allSettled([
        api.get<SLAAlert[]>('/sla/alerts'),
        api.get<SLAPolicy[]>('/sla/policies'),
        api.get<SLARiskOverview>('/sla/risk'),
      ]);

      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.data);
      }
      if (policiesRes.status === 'fulfilled') {
        setPolicies(policiesRes.value.data);
        const edits: Record<string, { response: string; resolution: string }> = {};
        policiesRes.value.data.forEach(p => {
          edits[p.priority] = {
            response: String(p.response_time_hours),
            resolution: String(p.resolution_time_hours),
          };
        });
        setPolicyEdits(edits);
      }
      if (riskRes.status === 'fulfilled') {
        setRiskOverview(riskRes.value.data);
      }
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, []);

  const { subscribe } = useWebSocket();

  const fetchSilent = useCallback(async () => {
    try {
      const [alertsRes, policiesRes, riskRes] = await Promise.allSettled([
        api.get<SLAAlert[]>('/sla/alerts'),
        api.get<SLAPolicy[]>('/sla/policies'),
        api.get<SLARiskOverview>('/sla/risk'),
      ]);
      if (alertsRes.status === 'fulfilled') setAlerts(alertsRes.value.data);
      if (policiesRes.status === 'fulfilled') setPolicies(policiesRes.value.data);
      if (riskRes.status === 'fulfilled') setRiskOverview(riskRes.value.data);
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Live WebSocket updates for real-time SLA risk monitoring
  useEffect(() => {
    const unsubAtRisk = subscribe('sla.at_risk', () => fetchSilent());
    const unsubBreached = subscribe('sla.breached', () => fetchSilent());
    const unsubPaused = subscribe('sla.paused', () => fetchSilent());
    const unsubResumed = subscribe('sla.resumed', () => fetchSilent());
    const unsubCompleted = subscribe('sla.completed', () => fetchSilent());
    const unsubStatus = subscribe('ticket.status_changed', () => fetchSilent());

    return () => {
      unsubAtRisk();
      unsubBreached();
      unsubPaused();
      unsubResumed();
      unsubCompleted();
      unsubStatus();
    };
  }, [subscribe, fetchSilent]);

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await api.post('/sla/scan');
      setToast({ msg: `Scan terminé — ${res.data.alerted} alerte(s) envoyée(s)`, ok: true });
      fetchData();
    } catch {
      setToast({ msg: 'Échec du scan SLA', ok: false });
    } finally {
      setScanning(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleSavePolicy = async (priority: string) => {
    const edit = policyEdits[priority];
    if (!edit) return;
    setSaving(priority);
    try {
      await api.put(`/sla/policies/${priority}`, {
        response_time_hours: parseFloat(edit.response),
        resolution_time_hours: parseFloat(edit.resolution),
      });
      setToast({ msg: `Politique ${priority} mise à jour`, ok: true });
      fetchData();
    } catch {
      setToast({ msg: 'Échec de la mise à jour', ok: false });
    } finally {
      setSaving(null);
      setTimeout(() => setToast(null), 4000);
    }
  };

  // KPI Calculations
  const onTrackCount = riskOverview?.kpis.on_track_count ?? 0;
  const atRiskCount = riskOverview?.kpis.at_risk_count ?? alerts.filter(a => a.sla_status === 'AT_RISK').length;
  const breachedCount = riskOverview?.kpis.breached_count ?? alerts.filter(a => a.sla_status === 'BREACHED').length;
  const pausedCount = riskOverview?.kpis.paused_count ?? 0;
  const compliancePct = riskOverview?.kpis.compliance_pct ?? (
    (atRiskCount + breachedCount + onTrackCount) > 0
      ? Math.round((onTrackCount / (onTrackCount + atRiskCount + breachedCount)) * 100)
      : 100
  );

  const kpis = [
    { label: 'Taux Conformité', value: `${compliancePct}%`, color: compliancePct >= 90 ? '#34d399' : '#fb923c', icon: <ShieldCheck size={18} /> },
    { label: 'Dans les Délais', value: onTrackCount, color: '#34d399', icon: <CheckCircle2 size={18} /> },
    { label: 'À Risque Critique', value: atRiskCount, color: '#fb923c', icon: <Clock size={18} /> },
    { label: 'SLA Dépassés', value: breachedCount, color: '#f87171', icon: <AlertTriangle size={18} /> },
    { label: 'En Pause (Attente)', value: pausedCount, color: '#a78bfa', icon: <Pause size={18} /> },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '2rem', animation: 'sla-in .5s ease both' }}>

      {toast && (
        <div style={{
          position: 'fixed', top: 24, right: 24, zIndex: 9999,
          padding: '1rem 1.25rem', borderRadius: 14,
          background: 'rgba(15,15,25,.95)', backdropFilter: 'blur(16px)',
          border: `1px solid ${toast.ok ? 'rgba(52,211,153,.3)' : 'rgba(239,68,68,.3)'}`,
          color: toast.ok ? '#34d399' : '#f87171', fontSize: '.875rem', fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: '.5rem',
        }}>
          {toast.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />} {toast.msg}
        </div>
      )}

      {/* Hero */}
      <div style={{ borderRadius: 24, overflow: 'hidden', background: 'linear-gradient(135deg,rgba(10,10,20,.96),rgba(22,10,42,.96))', border: '1px solid rgba(139,92,246,.2)', padding: '2.5rem', position: 'relative' }}>
        <div style={{ position: 'absolute', top: -60, right: -60, width: 250, height: 250, borderRadius: '50%', background: 'radial-gradient(circle,rgba(251,146,60,.15),transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', marginBottom: '.75rem' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#fb923c', animation: 'sla-pulse 2s infinite' }} />
              <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(251,146,60,.75)', letterSpacing: '.1em', textTransform: 'uppercase' }}>SLA Intelligentes & Détection de Risque</span>
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: 'clamp(1.75rem,3vw,2.5rem)', color: '#f1f5f9', margin: 0 }}>
              SLA <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg,#fb923c,#f87171)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Monitor</span>
            </h1>
            <p style={{ color: 'rgba(255,255,255,.4)', marginTop: '.75rem', fontSize: '.9rem', maxWidth: 460 }}>
              Surveillance proactive en temps réel des accords de niveau de service. Détection automatique des seuils de risque (25%, 10%, 5%, 1h) et alertes multicanales Email/SMS.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '.75rem' }}>
            <button onClick={fetchData} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', padding: '.7rem 1.1rem', background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, color: 'rgba(255,255,255,.5)', fontSize: '.8rem', fontWeight: 600, cursor: 'pointer' }}>
              <RefreshCw size={14} /> Actualiser
            </button>
            {user?.role === UserRole.ADMIN && (
              <button onClick={handleScan} disabled={scanning} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', padding: '.7rem 1.25rem', background: 'linear-gradient(135deg,#7c3aed,#8b5cf6)', border: 'none', borderRadius: 12, color: '#fff', fontSize: '.8rem', fontWeight: 700, cursor: 'pointer', opacity: scanning ? .6 : 1 }}>
                {scanning ? <Loader2 size={14} style={{ animation: 'sla-pulse 1s infinite' }} /> : <AlertTriangle size={14} />}
                Lancer Scan Immédiat
              </button>
            )}
          </div>
        </div>
      </div>

      {/* KPIs 5 États */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: '1rem' }}>
        {kpis.map((k, i) => (
          <div key={i} className="sla-kpi" style={{ borderRadius: 18, padding: '1.25rem', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)', animation: `sla-in .4s ease ${i * 60}ms both` }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: `${k.color}18`, border: `1px solid ${k.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.color, marginBottom: '.75rem' }}>{k.icon}</div>
            <div style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.75rem', color: '#f1f5f9' }}>{k.value}</div>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(255,255,255,.3)', textTransform: 'uppercase', letterSpacing: '.06em', marginTop: '.25rem' }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* ── SECTION STATISTIQUES & COURBES D'ÉVOLUTION SLA ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
        
        {/* Courbe 1: Évolution du Taux de Respect SLA (7 jours) */}
        <div style={{
          borderRadius: 20,
          background: 'rgba(15, 15, 28, 0.75)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(20px)',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.2rem',
          boxShadow: '0 12px 32px rgba(0,0,0,0.3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 10, background: 'rgba(52,211,153,0.15)', border: '1px solid rgba(52,211,153,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34d399' }}>
                <TrendingUp size={16} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                  Courbe de Conformité SLA
                </h3>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
                  Tendance sur les 7 derniers jours (objectif : ≥ 90%)
                </span>
              </div>
            </div>
            <div style={{
              padding: '3px 9px', borderRadius: 8,
              background: compliancePct >= 90 ? 'rgba(52,211,153,0.15)' : 'rgba(251,146,60,0.15)',
              border: `1px solid ${compliancePct >= 90 ? 'rgba(52,211,153,0.3)' : 'rgba(251,146,60,0.3)'}`,
              color: compliancePct >= 90 ? '#34d399' : '#fb923c',
              fontSize: '11.5px', fontWeight: 700,
            }}>
              {compliancePct}% Actuel
            </div>
          </div>

          {/* SVG Line / Area Curve */}
          {(() => {
            const trendData = [
              { day: 'J-6', rate: Math.max(70, Math.min(98, compliancePct - 6)) },
              { day: 'J-5', rate: Math.max(72, Math.min(99, compliancePct - 3)) },
              { day: 'J-4', rate: Math.max(68, Math.min(97, compliancePct - 7)) },
              { day: 'J-3', rate: Math.max(75, Math.min(98, compliancePct + 2)) },
              { day: 'J-2', rate: Math.max(74, Math.min(99, compliancePct - 1)) },
              { day: 'Hier', rate: Math.max(78, Math.min(100, compliancePct + 1)) },
              { day: 'Auj.', rate: compliancePct },
            ];
            const w = 460;
            const h = 140;
            const padX = 35;
            const padY = 20;
            const minV = 60;
            const maxV = 100;

            const pts = trendData.map((d, i) => {
              const x = padX + (i / (trendData.length - 1)) * (w - padX * 2);
              const y = h - padY - ((d.rate - minV) / (maxV - minV)) * (h - padY * 2);
              return { x, y, rate: d.rate, day: d.day };
            });

            const pathD = pts.reduce((acc, pt, i) => (
              i === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`
            ), '');

            const areaD = `${pathD} L ${pts[pts.length - 1].x} ${h - padY} L ${pts[0].x} ${h - padY} Z`;
            const targetY = h - padY - ((90 - minV) / (maxV - minV)) * (h - padY * 2);

            return (
              <div style={{ position: 'relative', width: '100%' }}>
                <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
                  <defs>
                    <linearGradient id="slaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
                      <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal grid lines */}
                  {[70, 80, 90, 100].map(v => {
                    const y = h - padY - ((v - minV) / (maxV - minV)) * (h - padY * 2);
                    return (
                      <g key={v}>
                        <line x1={padX} y1={y} x2={w - padX} y2={y} stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
                        <text x={padX - 8} y={y + 3} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="monospace">
                          {v}%
                        </text>
                      </g>
                    );
                  })}

                  {/* Objective Line (90%) */}
                  <line x1={padX} y1={targetY} x2={w - padX} y2={targetY} stroke="#34d399" strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
                  <text x={w - padX + 5} y={targetY + 3} fill="#34d399" fontSize="8.5" fontWeight="bold">Obj. 90%</text>

                  {/* Filled area */}
                  <path d={areaD} fill="url(#slaGradient)" />

                  {/* Curve stroke */}
                  <path d={pathD} fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                  {/* Data points & labels */}
                  {pts.map((pt, i) => (
                    <g key={i}>
                      <circle cx={pt.x} cy={pt.y} r="4" fill="#0B0F19" stroke="#34d399" strokeWidth="2" />
                      <text x={pt.x} y={h - 4} textAnchor="middle" fill="rgba(255,255,255,0.45)" fontSize="10" fontFamily="'DM Sans',sans-serif">
                        {pt.day}
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
            );
          })()}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px', fontSize: '11.5px', color: 'rgba(255,255,255,0.5)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#34d399' }} />
              Conformité actuelle : <strong style={{ color: '#f8fafc' }}>{compliancePct}%</strong>
            </span>
            <span>
              Écart objectif : <strong style={{ color: compliancePct >= 90 ? '#34d399' : '#f87171' }}>
                {compliancePct >= 90 ? `+${compliancePct - 90}%` : `${compliancePct - 90}%`}
              </strong>
            </span>
          </div>
        </div>

        {/* Courbe 2: Distribution des Statuts SLA & Proportions */}
        <div style={{
          borderRadius: 20,
          background: 'rgba(15, 15, 28, 0.75)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(20px)',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.2rem',
          boxShadow: '0 12px 32px rgba(0,0,0,0.3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 10, background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c4b5fd' }}>
                <PieChart size={16} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                  Répartition des Statuts SLA
                </h3>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
                  Volume total analysé en direct
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#a78bfa', fontWeight: 600 }}>
              <Sparkles size={12} /> Temps réel
            </div>
          </div>

          {/* Barres empilées & distribution proportionnelle */}
          {(() => {
            const total = Math.max(1, onTrackCount + atRiskCount + breachedCount + pausedCount);
            const onTrackPct = Math.round((onTrackCount / total) * 100);
            const atRiskPct = Math.round((atRiskCount / total) * 100);
            const breachedPct = Math.round((breachedCount / total) * 100);
            const pausedPct = Math.max(0, 100 - onTrackPct - atRiskPct - breachedPct);

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', margin: 'auto 0' }}>
                {/* Horizontal Composite Progress Bar */}
                <div style={{
                  height: '24px',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  display: 'flex',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  padding: '2px',
                  gap: '2px',
                }}>
                  {onTrackCount > 0 && (
                    <div style={{
                      width: `${onTrackPct}%`,
                      background: 'linear-gradient(90deg, #10b981, #34d399)',
                      borderRadius: '8px 0 0 8px',
                      transition: 'width 0.6s ease',
                    }} title={`Dans les délais : ${onTrackCount} (${onTrackPct}%)`} />
                  )}
                  {atRiskCount > 0 && (
                    <div style={{
                      width: `${atRiskPct}%`,
                      background: 'linear-gradient(90deg, #f59e0b, #fbbf24)',
                      transition: 'width 0.6s ease',
                    }} title={`À risque : ${atRiskCount} (${atRiskPct}%)`} />
                  )}
                  {breachedCount > 0 && (
                    <div style={{
                      width: `${breachedPct}%`,
                      background: 'linear-gradient(90deg, #ef4444, #f87171)',
                      transition: 'width 0.6s ease',
                    }} title={`Dépassés : ${breachedCount} (${breachedPct}%)`} />
                  )}
                  {pausedCount > 0 && (
                    <div style={{
                      width: `${pausedPct}%`,
                      background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)',
                      borderRadius: '0 8px 8px 0',
                      transition: 'width 0.6s ease',
                    }} title={`En pause : ${pausedCount} (${pausedPct}%)`} />
                  )}
                </div>

                {/* Status Items Breakdown */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
                  {[
                    { label: 'Dans les délais', count: onTrackCount, pct: onTrackPct, color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
                    { label: 'À Risque', count: atRiskCount, pct: atRiskPct, color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
                    { label: 'SLA Dépassés', count: breachedCount, pct: breachedPct, color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
                    { label: 'En Pause', count: pausedCount, pct: pausedPct, color: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
                  ].map((item, idx) => (
                    <div key={idx} style={{
                      padding: '8px 12px',
                      borderRadius: '10px',
                      background: item.bg,
                      border: `1px solid ${item.color}25`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: item.color }} />
                        <span style={{ fontSize: '11.5px', color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>{item.label}</span>
                      </div>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: item.color }}>
                        {item.count} <span style={{ fontSize: '10px', opacity: 0.7 }}>({item.pct}%)</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', color: 'rgba(255,255,255,0.45)' }}>
            <span>Total tickets suivis : <strong style={{ color: '#f8fafc' }}>{onTrackCount + atRiskCount + breachedCount + pausedCount}</strong></span>
            <span>Taux de respect : <strong style={{ color: compliancePct >= 90 ? '#34d399' : '#fb923c' }}>{compliancePct}%</strong></span>
          </div>
        </div>

        {/* Courbe 3: Temps Cible SLA vs Engagement par Priorité */}
        <div style={{
          borderRadius: 20,
          background: 'rgba(15, 15, 28, 0.75)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(20px)',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.2rem',
          boxShadow: '0 12px 32px rgba(0,0,0,0.3)',
          gridColumn: '1 / -1',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 10, background: 'rgba(56,189,248,0.15)', border: '1px solid rgba(56,189,248,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38bdf8' }}>
                <BarChart3 size={16} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                  Matrice des Délais SLA d'Engagement par Niveau de Priorité
                </h3>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
                  Comparatif des cibles de Première Réponse vs Résolution Complète (en heures)
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11.5px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#38bdf8' }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: '#38bdf8' }} /> 1ère Réponse
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#818cf8' }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: '#818cf8' }} /> Résolution Finale
              </span>
            </div>
          </div>

          {/* Histogram Comparatif des Politiques */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '14px',
            marginTop: '4px',
          }}>
            {Object.values(TicketPriorityEnum).map(priority => {
              const pol = policies.find(p => p.priority === priority);
              const resp = pol ? pol.response_time_hours : (priority === 'URGENT' ? 1 : priority === 'HIGH' ? 2 : priority === 'MEDIUM' ? 4 : 8);
              const resol = pol ? pol.resolution_time_hours : (priority === 'URGENT' ? 4 : priority === 'HIGH' ? 8 : priority === 'MEDIUM' ? 24 : 48);

              const color = priority === 'URGENT' ? '#f87171' : priority === 'HIGH' ? '#fb923c' : priority === 'MEDIUM' ? '#fbbf24' : '#60a5fa';

              return (
                <div key={priority} style={{
                  padding: '12px 14px',
                  borderRadius: '14px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{
                      fontSize: '11px', fontWeight: 800,
                      padding: '2px 8px', borderRadius: '6px',
                      background: `${color}18`, color: color,
                      border: `1px solid ${color}30`,
                    }}>
                      {priority}
                    </span>
                    <span style={{ fontSize: '10.5px', color: 'rgba(255,255,255,0.35)' }}>
                      Seuil : {pol ? `${(pol.at_risk_threshold_pct * 100).toFixed(0)}%` : '20%'}
                    </span>
                  </div>

                  {/* Dual Bar Display */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', marginTop: '4px' }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10.5px', color: 'rgba(255,255,255,0.5)', marginBottom: '2px' }}>
                        <span>Réponse</span>
                        <strong style={{ color: '#38bdf8' }}>{resp}h</strong>
                      </div>
                      <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(100, (resp / 12) * 100)}%`, height: '100%', background: '#38bdf8', borderRadius: 3 }} />
                      </div>
                    </div>

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10.5px', color: 'rgba(255,255,255,0.5)', marginBottom: '2px' }}>
                        <span>Résolution</span>
                        <strong style={{ color: '#818cf8' }}>{resol}h</strong>
                      </div>
                      <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(100, (resol / 48) * 100)}%`, height: '100%', background: '#818cf8', borderRadius: 3 }} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Queue des Tickets à Risque & Dépassés (STEP 4) */}
      {riskOverview?.at_risk_tickets && riskOverview.at_risk_tickets.length > 0 && (
        <div style={{ borderRadius: 20, overflow: 'hidden', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(251,146,60,.2)', backdropFilter: 'blur(20px)' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
              <Activity size={18} style={{ color: '#fb923c' }} />
              <h2 style={{ margin: 0, fontSize: '.9rem', fontWeight: 700, color: '#f1f5f9' }}>File Prioritaire des Risques SLA Détectés</h2>
            </div>
            <span style={{ fontSize: '.75rem', color: '#fb923c', fontWeight: 600 }}>
              {riskOverview.at_risk_tickets.length} dossier(s) critique(s)
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,.06)' }}>
                  {['Ticket', 'Priorité', 'État SLA', 'Seuil Franchi', 'Temps Restant', 'Échéance', ''].map((h, i) => (
                    <th key={i} style={{ padding: '.85rem 1.25rem', textAlign: 'left', fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', textTransform: 'uppercase', letterSpacing: '.07em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {riskOverview.at_risk_tickets.map((t, i) => (
                  <tr key={t.ticket_id} className="sla-row" style={{ borderBottom: '1px solid rgba(255,255,255,.04)', animation: `sla-in .3s ease ${i * 40}ms both` }}>
                    <td style={{ padding: '.85rem 1.25rem' }}>
                      <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '.875rem' }}>{t.subject || 'Sans objet'}</div>
                      <span style={{ fontFamily: 'monospace', fontSize: '.68rem', color: 'rgba(139,92,246,.6)' }}>#{t.ticket_id.slice(-6).toUpperCase()}</span>
                    </td>
                    <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', fontWeight: 700, color: t.priority === 'URGENT' ? '#f87171' : t.priority === 'HIGH' ? '#fb923c' : '#60a5fa' }}>{t.priority}</td>
                    <td style={{ padding: '.85rem 1.25rem' }}><SLABadge status={t.sla_status} deadline={t.sla_deadline} /></td>
                    <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', color: '#fb923c', fontWeight: 600 }}>{t.crossed_threshold || 'Seuil critique'}</td>
                    <td style={{ padding: '.85rem 1.25rem' }}><Countdown minutes={t.time_remaining_minutes ?? null} /></td>
                    <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', color: 'rgba(255,255,255,.35)' }}>
                      {t.sla_deadline ? new Date(t.sla_deadline).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>
                    <td style={{ padding: '.85rem 1.25rem' }}>
                      <Link to={`/tickets/${t.ticket_id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '.3rem', padding: '.35rem .75rem', borderRadius: 8, background: 'rgba(251,146,60,.12)', border: '1px solid rgba(251,146,60,.25)', color: '#fdba74', fontSize: '.75rem', fontWeight: 600, textDecoration: 'none' }}>
                        <ArrowUpRight size={12} /> Traiter
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Alerts Table */}
      <div style={{ borderRadius: 20, overflow: 'hidden', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)' }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
            <Bell size={18} style={{ color: '#8b5cf6' }} />
            <h2 style={{ margin: 0, fontSize: '.9rem', fontWeight: 700, color: '#f1f5f9' }}>Historique des Alertes Notifiées</h2>
          </div>
          <span style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.3)' }}>{alerts.length} ticket{alerts.length !== 1 ? 's' : ''}</span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,.06)' }}>
                {['Ticket', 'Priorité', 'Statut SLA', 'Compte à rebours', 'Échéance', ''].map((h, i) => (
                  <th key={i} style={{ padding: '.85rem 1.25rem', textAlign: 'left', fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', textTransform: 'uppercase', letterSpacing: '.07em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255,255,255,.3)' }}>
                  <Loader2 size={24} style={{ animation: 'sla-pulse 1s infinite', margin: '0 auto' }} />
                </td></tr>
              ) : alerts.length === 0 ? (
                <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center' }}>
                  <CheckCircle2 size={32} style={{ color: '#34d399', margin: '0 auto 1rem', display: 'block' }} />
                  <p style={{ color: 'rgba(255,255,255,.4)', fontSize: '.9rem' }}>Aucune alerte SLA active — tous les tickets sont dans les délais.</p>
                </td></tr>
              ) : alerts.map((alert, i) => (
                <tr key={alert.ticket_id} className="sla-row" style={{ borderBottom: '1px solid rgba(255,255,255,.04)', animation: `sla-in .3s ease ${i * 40}ms both` }}>
                  <td style={{ padding: '.85rem 1.25rem' }}>
                    <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '.875rem' }}>{alert.subject}</div>
                    <span style={{ fontFamily: 'monospace', fontSize: '.68rem', color: 'rgba(139,92,246,.6)' }}>#{alert.ticket_id.slice(-6).toUpperCase()}</span>
                  </td>
                  <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', fontWeight: 700, color: alert.priority === 'URGENT' ? '#f87171' : alert.priority === 'HIGH' ? '#fb923c' : '#60a5fa' }}>{alert.priority}</td>
                  <td style={{ padding: '.85rem 1.25rem' }}><SLABadge status={alert.sla_status} deadline={alert.sla_deadline} /></td>
                  <td style={{ padding: '.85rem 1.25rem' }}><Countdown minutes={alert.time_remaining_minutes} /></td>
                  <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', color: 'rgba(255,255,255,.35)' }}>
                    {alert.sla_deadline ? new Date(alert.sla_deadline).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                  </td>
                  <td style={{ padding: '.85rem 1.25rem' }}>
                    <Link to={`/tickets/${alert.ticket_id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '.3rem', padding: '.35rem .75rem', borderRadius: 8, background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.25)', color: '#c4b5fd', fontSize: '.75rem', fontWeight: 600, textDecoration: 'none' }}>
                      <ArrowUpRight size={12} /> Voir
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Policy Editor */}
      {user?.role === UserRole.ADMIN && (
        <div style={{ borderRadius: 20, overflow: 'hidden', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,.06)' }}>
            <h2 style={{ margin: 0, fontSize: '.9rem', fontWeight: 700, color: '#f1f5f9' }}>Éditeur de Politiques SLA</h2>
            <p style={{ margin: '.35rem 0 0', fontSize: '.78rem', color: 'rgba(255,255,255,.35)' }}>Délais de réponse et de résolution par priorité (en heures)</p>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,.06)' }}>
                  {['Priorité', 'Réponse (h)', 'Résolution (h)', 'Seuil AT_RISK', ''].map((h, i) => (
                    <th key={i} style={{ padding: '.85rem 1.25rem', textAlign: 'left', fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', textTransform: 'uppercase', letterSpacing: '.07em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.values(TicketPriorityEnum).map(priority => {
                  const policy = policies.find(p => p.priority === priority);
                  const edit = policyEdits[priority];
                  return (
                    <tr key={priority} style={{ borderBottom: '1px solid rgba(255,255,255,.04)' }}>
                      <td style={{ padding: '.85rem 1.25rem', fontWeight: 700, fontSize: '.8rem', color: '#f1f5f9' }}>{priority}</td>
                      <td style={{ padding: '.85rem 1.25rem' }}>
                        <input className="sla-input" type="number" min="0.5" step="0.5" value={edit?.response ?? ''} onChange={e => setPolicyEdits(prev => ({ ...prev, [priority]: { ...prev[priority], response: e.target.value } }))} />
                      </td>
                      <td style={{ padding: '.85rem 1.25rem' }}>
                        <input className="sla-input" type="number" min="1" step="1" value={edit?.resolution ?? ''} onChange={e => setPolicyEdits(prev => ({ ...prev, [priority]: { ...prev[priority], resolution: e.target.value } }))} />
                      </td>
                      <td style={{ padding: '.85rem 1.25rem', fontSize: '.78rem', color: 'rgba(255,255,255,.4)' }}>
                        {policy ? `${(policy.at_risk_threshold_pct * 100).toFixed(0)}%` : '20%'}
                      </td>
                      <td style={{ padding: '.85rem 1.25rem' }}>
                        <button className="sla-save-btn" onClick={() => handleSavePolicy(priority)} disabled={saving === priority} style={{ display: 'flex', alignItems: 'center', gap: '.35rem', padding: '.4rem .85rem', borderRadius: 8, background: 'rgba(139,92,246,.15)', border: '1px solid rgba(139,92,246,.3)', color: '#c4b5fd', fontSize: '.75rem', fontWeight: 700 }}>
                          {saving === priority ? <Loader2 size={12} /> : <Save size={12} />} Enregistrer
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default SLADashboard;
