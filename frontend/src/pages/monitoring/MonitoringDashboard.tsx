import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, CheckCircle2, AlertTriangle, XCircle, RefreshCw, Play,
  Server, Cpu, Database, Mail, Inbox, Bell, Timer, Radio,
  HardDrive, Clock, Zap, Sparkles, TrendingUp
} from 'lucide-react';
import api from '../../api/axios';
import {
  type SystemHealth, type ComponentHealth,
  type BackgroundJob, type OperationalMetrics
} from '../../types';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

export const MonitoringDashboard: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<number>(30); // seconds
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);

  const fetchData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const [healthRes, metricsRes, jobsRes] = await Promise.all([
        api.get<SystemHealth>('/monitoring/system-status'),
        api.get<OperationalMetrics>('/monitoring/metrics'),
        api.get<BackgroundJob[]>('/monitoring/jobs'),
      ]);
      setHealth(healthRes.data);
      setMetrics(metricsRes.data);
      setJobs(jobsRes.data);
    } catch (err: any) {
      console.error('Failed to fetch monitoring data:', err);
      if (isManual) toast.error("Erreur lors de l'actualisation des métriques.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh interval
  useEffect(() => {
    if (refreshInterval <= 0) return;
    const timer = setInterval(() => {
      fetchData();
    }, refreshInterval * 1000);
    return () => clearInterval(timer);
  }, [refreshInterval, fetchData]);

  const handleTriggerJob = async (jobId: string, jobName: string) => {
    setTriggeringJob(jobId);
    try {
      await api.post(`/monitoring/jobs/${jobId}/trigger`);
      toast.success(`Tâche "${jobName}" déclenchée avec succès.`);
      // Refresh after small delay to show running state
      setTimeout(() => fetchData(), 1200);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Erreur lors du déclenchement.';
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setTriggeringJob(null);
    }
  };

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const parts = [];
    if (d > 0) parts.push(`${d}j`);
    if (h > 0 || d > 0) parts.push(`${h}h`);
    parts.push(`${m}m`);
    return parts.join(' ');
  };

  const getStatusBadge = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'success':
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.35)',
          color: '#34d399',
          icon: <CheckCircle2 size={13} />,
          text: 'Opérationnel'
        };
      case 'degraded':
      case 'running':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          border: 'rgba(245, 158, 11, 0.35)',
          color: '#fbbf24',
          icon: <AlertTriangle size={13} />,
          text: status === 'running' ? 'En cours' : 'Dégradé'
        };
      case 'unhealthy':
      case 'failed':
        return {
          bg: 'rgba(239, 68, 68, 0.15)',
          border: 'rgba(239, 68, 68, 0.35)',
          color: '#f87171',
          icon: <XCircle size={13} />,
          text: 'Critique'
        };
      case 'not_configured':
      case 'idle':
      default:
        return {
          bg: 'rgba(148, 163, 184, 0.1)',
          border: 'rgba(148, 163, 184, 0.25)',
          color: '#94a3b8',
          icon: <Clock size={13} />,
          text: status === 'not_configured' ? 'Non configuré' : 'En attente'
        };
    }
  };

  const getComponentIcon = (name: string) => {
    const n = name.toLowerCase();
    if (n.includes('mongo') || n.includes('data')) return <Database size={18} />;
    if (n.includes('ollama') || n.includes('ia') || n.includes('ai')) return <Cpu size={18} />;
    if (n.includes('rag') || n.includes('connaissance')) return <Sparkles size={18} />;
    if (n.includes('smtp') || (n.includes('email') && n.includes('sort'))) return <Mail size={18} />;
    if (n.includes('imap') || n.includes('entrant')) return <Inbox size={18} />;
    if (n.includes('notif')) return <Bell size={18} />;
    if (n.includes('sla') || n.includes('ordonn')) return <Timer size={18} />;
    if (n.includes('websocket') || n.includes('temps')) return <Radio size={18} />;
    if (n.includes('sauvegarde') || n.includes('backup') || n.includes('pra')) return <HardDrive size={18} />;
    return <Server size={18} />;
  };

  if (loading) {
    return (
      <div style={{ padding: '2.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: '1rem' }}>
        <RefreshCw size={32} className="animate-spin" style={{ color: '#8b5cf6' }} />
        <span style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.5)' }}>Chargement de la télémétrie système...</span>
      </div>
    );
  }

  const overall = getStatusBadge(health?.status || 'healthy');

  return (
    <div style={{ padding: '2rem', maxWidth: '1440px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      
      {/* ── HEADER ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '42px', height: '42px', borderRadius: '14px',
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(59, 130, 246, 0.25) 100%)',
              border: '1px solid rgba(139, 92, 246, 0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#c4b5fd'
            }}>
              <Activity size={22} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                Supervision & Observabilité
              </h1>
              <p style={{ margin: '3px 0 0', fontSize: '0.86rem', color: 'rgba(255, 255, 255, 0.45)' }}>
                Télémétrie opérationnelle en direct · Santé des 9 sous-systèmes & ordonnanceur d'arrière-plan
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Refresh interval selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', padding: '6px 12px' }}>
            <Clock size={14} style={{ color: 'rgba(255,255,255,0.4)' }} />
            <span style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.45)' }}>Actualisation:</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#f1f5f9',
                fontSize: '0.78rem',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value={10} style={{ background: '#0f172a' }}>10s</option>
              <option value={30} style={{ background: '#0f172a' }}>30s</option>
              <option value={60} style={{ background: '#0f172a' }}>60s</option>
              <option value={0} style={{ background: '#0f172a' }}>Manuelle</option>
            </select>
          </div>

          {/* Manual Refresh Button */}
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '8px 16px', borderRadius: '12px',
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%)',
              border: '1px solid rgba(139, 92, 246, 0.35)',
              color: '#c4b5fd', fontSize: '0.82rem', fontWeight: 600,
              cursor: refreshing ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s'
            }}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Actualisation...' : 'Actualiser'}</span>
          </button>
        </div>
      </div>

      {/* ── TOP SYSTEM STATUS BANNER ── */}
      <div style={{
        background: overall.bg,
        border: `1px solid ${overall.border}`,
        borderRadius: '20px',
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1.25rem',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.2)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            background: overall.bg, border: `1px solid ${overall.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: overall.color
          }}>
            {React.cloneElement(overall.icon, { size: 24 })}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc' }}>
                État Global : {health?.status === 'healthy' ? 'Système Sain & Opérationnel' : health?.status === 'degraded' ? 'Fonctionnement Dégradé' : 'Incident Critique'}
              </span>
              <span style={{
                fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: '999px',
                background: overall.bg, color: overall.color, border: `1px solid ${overall.border}`
              }}>
                {overall.text.toUpperCase()}
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'rgba(255,255,255,0.6)' }}>
              GEISER v{health?.version} · Temps de service actif : <strong>{health?.uptime_seconds ? formatUptime(health.uptime_seconds) : '—'}</strong> · Dernière vérification : {health?.server_time ? format(new Date(health.server_time), 'HH:mm:ss') : '—'}
            </p>
          </div>
        </div>

        {/* Summary Badges */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ padding: '6px 12px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399' }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#34d399' }}>{health?.summary.healthy_count ?? 0} Sains</span>
          </div>
          <div style={{ padding: '6px 12px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.25)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#fbbf24' }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#fbbf24' }}>{health?.summary.degraded_count ?? 0} Dégradés</span>
          </div>
          {(health?.summary.unhealthy_count ?? 0) > 0 && (
            <div style={{ padding: '6px 12px', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.25)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f87171' }} />
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f87171' }}>{health?.summary.unhealthy_count} Critiques</span>
            </div>
          )}
        </div>
      </div>

      {/* ── 9 SERVICES HEALTH GRID ── */}
      <div>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Server size={18} style={{ color: '#8b5cf6' }} />
          État Détaillé des Sous-Systèmes
        </h3>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1.25rem'
        }}>
          {health?.components.map((comp: ComponentHealth, idx: number) => {
            const status = getStatusBadge(comp.status);
            return (
              <div
                key={idx}
                style={{
                  background: 'rgba(15, 15, 28, 0.75)',
                  border: '1px solid rgba(255, 255, 255, 0.07)',
                  borderRadius: '18px',
                  padding: '1.25rem 1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
                  transition: 'border-color 0.2s',
                  position: 'relative'
                }}
              >
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '10px',
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: status.color
                    }}>
                      {getComponentIcon(comp.name)}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f8fafc' }}>
                        {comp.name}
                      </div>
                      {comp.critical && (
                        <span style={{ fontSize: '0.65rem', color: '#f87171', fontWeight: 700, textTransform: 'uppercase' }}>
                          Composant Critique
                        </span>
                      )}
                    </div>
                  </div>

                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700,
                    padding: '3px 8px', borderRadius: '6px',
                    background: status.bg, color: status.color,
                    border: `1px solid ${status.border}`,
                    display: 'flex', alignItems: 'center', gap: '4px'
                  }}>
                    {status.icon}
                    {status.text}
                  </span>
                </div>

                {/* Details text */}
                <div style={{ fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.65)', lineHeight: 1.4 }}>
                  {comp.details || 'Aucune anomalie détectée'}
                </div>

                {/* Latency / Extra metadata pill */}
                {comp.latency_ms !== undefined && comp.latency_ms !== null && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'rgba(255,255,255,0.4)' }}>
                    <Zap size={12} style={{ color: comp.latency_ms < 50 ? '#34d399' : '#fbbf24' }} />
                    <span>Latence : <strong style={{ color: '#f1f5f9' }}>{comp.latency_ms} ms</strong></span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── OPERATIONAL METRICS STRIP ── */}
      {metrics && (
        <div>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={18} style={{ color: '#38bdf8' }} />
            Métriques Opérationnelles en Direct
          </h3>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem'
          }}>
            <div style={{ background: 'rgba(15, 15, 28, 0.75)', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '16px', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Tickets Actifs (24h)</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc' }}>{metrics.tickets.open + metrics.tickets.in_progress}</span>
              <span style={{ fontSize: '0.72rem', color: '#a78bfa' }}>+{metrics.tickets.created_last_24h} créés aujourd'hui</span>
            </div>

            <div style={{ background: 'rgba(15, 15, 28, 0.75)', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '16px', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Respect des SLA</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: metrics.sla.breached > 0 ? '#f87171' : '#34d399' }}>
                {metrics.sla.breached} <span style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>dépassés</span>
              </span>
              <span style={{ fontSize: '0.72rem', color: '#fbbf24' }}>{metrics.sla.at_risk} ticket(s) sous risque</span>
            </div>

            <div style={{ background: 'rgba(15, 15, 28, 0.75)', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '16px', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>File Notifications</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc' }}>{metrics.notifications.pending}</span>
              <span style={{ fontSize: '0.72rem', color: metrics.notifications.dead_letter > 0 ? '#f87171' : 'rgba(255,255,255,0.4)' }}>
                {metrics.notifications.dead_letter} rebut(s) non délivrable(s)
              </span>
            </div>

            <div style={{ background: 'rgba(15, 15, 28, 0.75)', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '16px', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Clients WebSockets</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#38bdf8' }}>{metrics.websockets.active_connections}</span>
              <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.4)' }}>{metrics.websockets.active_users} utilisateur(s) connecté(s)</span>
            </div>

            <div style={{ background: 'rgba(15, 15, 28, 0.75)', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '16px', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Authentifications (24h)</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#34d399' }}>{metrics.security.logins_last_24h}</span>
              <span style={{ fontSize: '0.72rem', color: metrics.security.failed_logins_24h > 5 ? '#f87171' : 'rgba(255,255,255,0.4)' }}>
                {metrics.security.failed_logins_24h} échec(s) de connexion
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── BACKGROUND JOBS TRACKER TABLE ── */}
      <div style={{
        background: 'rgba(15, 15, 28, 0.75)',
        border: '1px solid rgba(255, 255, 255, 0.07)',
        borderRadius: '20px',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.3)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Timer size={18} style={{ color: '#a78bfa' }} />
              Tâches d'Arrière-Plan & Workers Planifiés
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'rgba(255, 255, 255, 0.45)' }}>
              Historique d'exécution en direct, durées, compteurs d'échecs et déclenchement manuel à la demande
            </p>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.4)', fontSize: '0.74rem', textTransform: 'uppercase' }}>
                <th style={{ textAlign: 'left', padding: '10px 14px' }}>Tâche / Worker</th>
                <th style={{ textAlign: 'center', padding: '10px 14px' }}>État</th>
                <th style={{ textAlign: 'left', padding: '10px 14px' }}>Prochaine Exécution</th>
                <th style={{ textAlign: 'left', padding: '10px 14px' }}>Dernier Succès</th>
                <th style={{ textAlign: 'center', padding: '10px 14px' }}>Durée</th>
                <th style={{ textAlign: 'center', padding: '10px 14px' }}>Bilan Succès / Échecs</th>
                <th style={{ textAlign: 'right', padding: '10px 14px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: 'rgba(255, 255, 255, 0.4)' }}>
                    Aucune tâche d'arrière-plan enregistrée.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => {
                  const badge = getStatusBadge(job.status);
                  const isBusy = triggeringJob === job.job_id || job.is_running;
                  return (
                    <tr
                      key={job.job_id}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                        transition: 'background 0.15s'
                      }}
                    >
                      {/* Name & ID */}
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ fontWeight: 600, color: '#f8fafc' }}>{job.name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'rgba(255, 255, 255, 0.4)', fontFamily: 'monospace' }}>
                          ID : {job.job_id}
                        </div>
                        {job.last_error && (
                          <div style={{ fontSize: '0.72rem', color: '#f87171', marginTop: '4px' }}>
                            Dernière erreur : {job.last_error}
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td style={{ textAlign: 'center', padding: '12px 14px' }}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: '4px',
                          padding: '3px 8px', borderRadius: '6px',
                          background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
                          fontSize: '0.72rem', fontWeight: 700
                        }}>
                          {badge.icon} {badge.text}
                        </span>
                      </td>

                      {/* Next run time */}
                      <td style={{ padding: '12px 14px', color: 'rgba(255, 255, 255, 0.7)' }}>
                        {job.next_run_time ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} style={{ color: '#a78bfa' }} />
                            <span>{format(new Date(job.next_run_time), 'dd/MM/yyyy HH:mm:ss')}</span>
                          </div>
                        ) : (
                          <span style={{ color: 'rgba(255,255,255,0.3)' }}>Non programmée</span>
                        )}
                      </td>

                      {/* Last success */}
                      <td style={{ padding: '12px 14px', color: 'rgba(255, 255, 255, 0.7)' }}>
                        {job.last_success_at ? (
                          format(new Date(job.last_success_at), 'dd/MM/yyyy HH:mm:ss')
                        ) : (
                          <span style={{ color: 'rgba(255,255,255,0.3)' }}>—</span>
                        )}
                      </td>

                      {/* Duration */}
                      <td style={{ textAlign: 'center', padding: '12px 14px', color: 'rgba(255, 255, 255, 0.7)' }}>
                        {job.last_duration_seconds !== null && job.last_duration_seconds !== undefined ? (
                          `${job.last_duration_seconds}s`
                        ) : (
                          '—'
                        )}
                      </td>

                      {/* Success / Failure Counters */}
                      <td style={{ textAlign: 'center', padding: '12px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                          <span style={{ color: '#34d399', fontWeight: 700 }}>{job.success_count} ✓</span>
                          <span style={{ color: 'rgba(255,255,255,0.2)' }}>/</span>
                          <span style={{ color: job.failure_count > 0 ? '#f87171' : 'rgba(255,255,255,0.4)', fontWeight: job.failure_count > 0 ? 700 : 500 }}>
                            {job.failure_count} ✗
                          </span>
                        </div>
                      </td>

                      {/* Manual trigger button */}
                      <td style={{ textAlign: 'right', padding: '12px 14px' }}>
                        <button
                          type="button"
                          onClick={() => handleTriggerJob(job.job_id, job.name)}
                          disabled={isBusy}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '6px',
                            padding: '6px 12px', borderRadius: '8px',
                            background: isBusy ? 'rgba(255,255,255,0.05)' : 'rgba(139, 92, 246, 0.15)',
                            border: '1px solid rgba(139, 92, 246, 0.3)',
                            color: isBusy ? 'rgba(255,255,255,0.3)' : '#c4b5fd',
                            fontSize: '0.74rem', fontWeight: 600,
                            cursor: isBusy ? 'not-allowed' : 'pointer',
                            transition: 'all 0.15s'
                          }}
                        >
                          <Play size={11} fill={isBusy ? 'none' : '#c4b5fd'} />
                          <span>{isBusy ? 'En cours...' : 'Exécuter'}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MonitoringDashboard;
