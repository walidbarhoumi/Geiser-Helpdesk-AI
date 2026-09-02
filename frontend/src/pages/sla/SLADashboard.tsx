import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Clock, Award, RefreshCw, Save,
  ArrowUpRight, CheckCircle2, XCircle, Loader2,
} from 'lucide-react';
import api from '../../api/axios';
import { type TicketPriority, TicketPriority as TicketPriorityEnum } from '../../types';
import SLABadge from '../../components/sla/SLABadge';
import { useAuth } from '../../store/authContext';
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
  const [policyEdits, setPolicyEdits] = useState<Record<string, { response: string; resolution: string }>>({});
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { injectStyles(); }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [alertsRes, policiesRes] = await Promise.all([
        api.get<SLAAlert[]>('/sla/alerts'),
        api.get<SLAPolicy[]>('/sla/policies'),
      ]);
      setAlerts(alertsRes.data);
      setPolicies(policiesRes.data);
      const edits: Record<string, { response: string; resolution: string }> = {};
      policiesRes.data.forEach(p => {
        edits[p.priority] = {
          response: String(p.response_time_hours),
          resolution: String(p.resolution_time_hours),
        };
      });
      setPolicyEdits(edits);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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

  const atRiskCount = alerts.filter(a => a.sla_status === 'AT_RISK').length;
  const breachedCount = alerts.filter(a => a.sla_status === 'BREACHED').length;
  const avgResolution = policies.length
    ? (policies.reduce((s, p) => s + p.resolution_time_hours, 0) / policies.length).toFixed(1)
    : '—';

  const kpis = [
    { label: 'À Risque', value: atRiskCount, color: '#fb923c', icon: <Clock size={18} /> },
    { label: 'Dépassés', value: breachedCount, color: '#f87171', icon: <AlertTriangle size={18} /> },
    { label: 'Résolution Moy.', value: `${avgResolution}h`, color: '#8b5cf6', icon: <Award size={18} /> },
    { label: 'Total Alertes', value: alerts.length, color: '#60a5fa', icon: <CheckCircle2 size={18} /> },
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
              <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(251,146,60,.75)', letterSpacing: '.1em', textTransform: 'uppercase' }}>SLA Intelligentes</span>
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: 'clamp(1.75rem,3vw,2.5rem)', color: '#f1f5f9', margin: 0 }}>
              SLA <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg,#fb923c,#f87171)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Monitor</span>
            </h1>
            <p style={{ color: 'rgba(255,255,255,.4)', marginTop: '.75rem', fontSize: '.9rem', maxWidth: 420 }}>
              Surveillance en temps réel des accords de niveau de service. Alertes automatiques par email et dans l'application.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '.75rem' }}>
            <button onClick={fetchData} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', padding: '.7rem 1.1rem', background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, color: 'rgba(255,255,255,.5)', fontSize: '.8rem', fontWeight: 600, cursor: 'pointer' }}>
              <RefreshCw size={14} /> Actualiser
            </button>
            {user?.role === UserRole.ADMIN && (
              <button onClick={handleScan} disabled={scanning} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', padding: '.7rem 1.25rem', background: 'linear-gradient(135deg,#7c3aed,#8b5cf6)', border: 'none', borderRadius: 12, color: '#fff', fontSize: '.8rem', fontWeight: 700, cursor: 'pointer', opacity: scanning ? .6 : 1 }}>
                {scanning ? <Loader2 size={14} style={{ animation: 'sla-pulse 1s infinite' }} /> : <AlertTriangle size={14} />}
                Lancer Scan
              </button>
            )}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: '1rem' }}>
        {kpis.map((k, i) => (
          <div key={i} className="sla-kpi" style={{ borderRadius: 18, padding: '1.25rem', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)', animation: `sla-in .4s ease ${i * 60}ms both` }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: `${k.color}18`, border: `1px solid ${k.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.color, marginBottom: '.75rem' }}>{k.icon}</div>
            <div style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.75rem', color: '#f1f5f9' }}>{k.value}</div>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(255,255,255,.3)', textTransform: 'uppercase', letterSpacing: '.06em', marginTop: '.25rem' }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Alerts Table */}
      <div style={{ borderRadius: 20, overflow: 'hidden', background: 'rgba(15,15,25,.72)', border: '1px solid rgba(255,255,255,.07)', backdropFilter: 'blur(20px)' }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '.9rem', fontWeight: 700, color: '#f1f5f9' }}>Alertes Actives</h2>
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
