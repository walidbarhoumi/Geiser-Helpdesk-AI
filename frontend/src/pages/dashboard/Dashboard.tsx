import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, CheckCircle2, Clock,
  AlertTriangle, Sparkles, RefreshCw,

  ShieldCheck, Loader2, Award, Zap,
  BarChart3, ChevronRight, Layers, ArrowUpRight
} from 'lucide-react';
import api from '../../api/axios';
import { type AnalyticsDashboardData, TicketPriority } from '../../types';
import toast from 'react-hot-toast';

const Dashboard: React.FC = () => {
  const [data, setData] = useState<AnalyticsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodDays, setPeriodDays] = useState<number>(30);
  const [hoveredBarIndex, setHoveredBarIndex] = useState<number | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<AnalyticsDashboardData>(`/analytics/dashboard?period_days=${periodDays}`);
      setData(res.data);
    } catch (err) {
      console.error('Failed to load analytics dashboard', err);
      toast.error('Erreur lors du chargement des analyses.');
    } finally {
      setLoading(false);
    }
  }, [periodDays]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const maxVolume = data?.volume_trends?.length
    ? Math.max(...data.volume_trends.map(t => t.total_tickets), 1)
    : 1;

  return (
    <div style={{
      minHeight: '100vh',
      padding: '28px 32px 64px',
      display: 'flex',
      flexDirection: 'column',
      gap: '28px',
      color: '#f8fafc',
      fontFamily: "'DM Sans', sans-serif"
    }}>

      {/* ── TOP HEADER & CONTROLS ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <div style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: '#10b981', boxShadow: '0 0 10px #10b981'
            }} />
            <span style={{
              fontSize: '11px', fontWeight: 700,
              color: 'rgba(167, 139, 250, 0.9)',
              letterSpacing: '0.08em', textTransform: 'uppercase'
            }}>
              Intelligence Artificielle & Pilotage Helpdesk
            </span>
          </div>
          <h1 style={{
            margin: 0,
            fontFamily: "'DM Serif Display', serif",
            fontSize: 'clamp(1.75rem, 3vw, 2.35rem)',
            fontWeight: 400,
            letterSpacing: '-0.02em',
            color: '#fff'
          }}>
            Analyse Prédictive <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg, #a78bfa, #ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>& Insights Stratégiques</span>
          </h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Period selector buttons */}
          <div style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(139, 92, 246, 0.2)',
            borderRadius: '12px',
            padding: '3px'
          }}>
            {[7, 14, 30].map(days => (
              <button
                key={days}
                onClick={() => setPeriodDays(days)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '9px',
                  border: 'none',
                  background: periodDays === days ? 'rgba(139, 92, 246, 0.28)' : 'transparent',
                  color: periodDays === days ? '#fff' : 'rgba(255, 255, 255, 0.5)',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.18s'
                }}
              >
                {days}j
              </button>
            ))}
          </div>

          <button
            onClick={fetchAnalytics}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#c4b5fd',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            {loading ? "Actualisation..." : "Actualiser"}
          </button>
        </div>
      </div>

      {loading && !data && (
        <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '14px' }}>
          <Loader2 size={42} className="animate-spin" style={{ color: '#8b5cf6' }} />
          <span style={{ fontSize: '13.5px', color: 'rgba(255, 255, 255, 0.4)', fontWeight: 500 }}>
            Calcul des métriques prédictives et agrégations temps réel...
          </span>
        </div>
      )}

      {data && (
        <>
          {/* ── 1. SUMMARY KPIS GRID ── */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: '16px'
          }}>
            {[
              {
                label: 'Total Tickets Enregistrés',
                value: data.kpis.total_tickets,
                subtext: `${data.kpis.open_tickets} ouverts · ${data.kpis.in_progress_tickets} en cours`,
                color: '#8b5cf6',
                icon: <Layers size={18} />
              },
              {
                label: 'Taux de Résolution',
                value: `${data.kpis.resolution_rate_pct}%`,
                subtext: `${data.kpis.resolved_tickets} tickets clôturés`,
                color: '#10b981',
                icon: <CheckCircle2 size={18} />
              },
              {
                label: 'Temps Moyen de Résolution (MTTR)',
                value: `${data.kpis.overall_mttr_hours}h`,
                subtext: `Moyenne sur l'ensemble des catégories`,
                color: '#38bdf8',
                icon: <Clock size={18} />
              },
              {
                label: 'Respect Global des SLA',
                value: `${data.kpis.overall_sla_compliance_pct}%`,
                subtext: `Tickets traités dans les délais`,
                color: data.kpis.overall_sla_compliance_pct >= 90 ? '#34d399' : '#fbbf24',
                icon: <ShieldCheck size={18} />
              },
              {
                label: 'Problèmes Systémiques Détectés',
                value: data.kpis.critical_recurring_count,
                subtext: `Clusters nécessitant action stratégique`,
                color: data.kpis.critical_recurring_count > 0 ? '#f87171' : '#10b981',
                icon: <AlertTriangle size={18} />
              },
            ].map((kpi, idx) => (
              <div
                key={idx}
                style={{
                  background: 'rgba(15, 15, 28, 0.75)',
                  border: '1px solid rgba(255, 255, 255, 0.07)',
                  borderRadius: '18px',
                  padding: '18px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'rgba(255, 255, 255, 0.45)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {kpi.label}
                  </span>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '10px',
                    background: `${kpi.color}15`, color: kpi.color,
                    border: `1px solid ${kpi.color}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {kpi.icon}
                  </div>
                </div>
                <div style={{ fontSize: '1.9rem', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                  {kpi.value}
                </div>
                <div style={{ fontSize: '11.5px', color: 'rgba(255, 255, 255, 0.4)' }}>
                  {kpi.subtext}
                </div>
              </div>
            ))}
          </div>

          {/* ── 2. CARTE D'INSIGHTS PRÉDICTIFS IA ── */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(124, 58, 237, 0.12) 0%, rgba(219, 39, 119, 0.08) 50%, rgba(15, 15, 28, 0.95) 100%)',
            border: '1px solid rgba(139, 92, 246, 0.35)',
            borderRadius: '24px',
            padding: '24px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '42px', height: '42px', borderRadius: '14px',
                  background: 'linear-gradient(135deg, #7c3aed, #ec4899)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', boxShadow: '0 6px 20px rgba(124, 58, 237, 0.4)'
                }}>
                  <Sparkles size={22} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                      Prévisions & Recommandations Prédictives IA (Gemma 3)
                    </h3>
                    <span style={{
                      fontSize: '10.5px', padding: '2px 8px', borderRadius: '999px',
                      background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)',
                      color: '#34d399', fontWeight: 700
                    }}>
                      MODÈLE OPÉRATIONNEL
                    </span>
                  </div>
                  <p style={{ margin: '3px 0 0', fontSize: '0.84rem', color: 'rgba(255, 255, 255, 0.5)' }}>
                    Projection de charge sur les 7 prochains jours · Anticipation des flux et prévention des engorgements
                  </p>
                </div>
              </div>

              {/* Risk Badge */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '6px 14px', borderRadius: '12px',
                background: data.predictive_insights.predicted_spike_risk === 'ÉLEVÉ'
                  ? 'rgba(239, 68, 68, 0.15)'
                  : data.predictive_insights.predicted_spike_risk === 'MODÉRÉ'
                    ? 'rgba(245, 158, 11, 0.15)'
                    : 'rgba(16, 185, 129, 0.15)',
                border: `1px solid ${
                  data.predictive_insights.predicted_spike_risk === 'ÉLEVÉ'
                    ? 'rgba(239, 68, 68, 0.35)'
                    : data.predictive_insights.predicted_spike_risk === 'MODÉRÉ'
                      ? 'rgba(245, 158, 11, 0.35)'
                      : 'rgba(16, 185, 129, 0.35)'
                }`
              }}>
                <span style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.6)', fontWeight: 600 }}>
                  Risque d'Engorgement :
                </span>
                <span style={{
                  fontSize: '12px', fontWeight: 700,
                  color: data.predictive_insights.predicted_spike_risk === 'ÉLEVÉ'
                    ? '#f87171'
                    : data.predictive_insights.predicted_spike_risk === 'MODÉRÉ'
                      ? '#fbbf24'
                      : '#34d399'
                }}>
                  {data.predictive_insights.predicted_spike_risk}
                </span>
              </div>
            </div>

            {/* Forecast Summary Text */}
            <div style={{
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '14px',
              padding: '14px 18px',
              fontSize: '0.9rem',
              lineHeight: 1.6,
              color: 'rgba(255, 255, 255, 0.85)'
            }}>
              {data.predictive_insights.forecast_summary}
            </div>

            {/* Peak Windows & Focus Areas */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
              <div style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '14px',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', fontWeight: 700, color: '#fbbf24', textTransform: 'uppercase' }}>
                  <Clock size={13} /> Créneaux de Pointe Anticipés
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {data.predictive_insights.peak_time_windows.map((win, i) => (
                    <span key={i} style={{
                      padding: '4px 10px', borderRadius: '8px',
                      background: 'rgba(251, 191, 36, 0.1)',
                      border: '1px solid rgba(251, 191, 36, 0.25)',
                      color: '#fde68a', fontSize: '11.5px', fontWeight: 600
                    }}>
                      {win}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '14px',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase' }}>
                  <Zap size={13} /> Actions Prioritaires Recommandées
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {data.predictive_insights.recommended_focus_areas.map((rec, i) => (
                    <div key={i} style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ color: '#38bdf8' }}>•</span>
                      <span>{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── 3. GRAPHIQUE DES VOLUMES & RÉPARTITION PAR CATÉGORIE ── */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(320px, 1.6fr) minmax(280px, 1fr)',
            gap: '20px'
          }}>

            {/* Volume Trend Histogram */}
            <div style={{
              background: 'rgba(15, 15, 28, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.07)',
              borderRadius: '20px',
              padding: '22px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              backdropFilter: 'blur(16px)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <BarChart3 size={18} style={{ color: '#a78bfa' }} />
                  <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700, color: '#f8fafc' }}>
                    Évolution Temporelle des Flux de Tickets ({periodDays} jours)
                  </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: 'rgba(255, 255, 255, 0.45)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#7c3aed' }} /> Total
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#10b981' }} /> Résolus
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#ef4444' }} /> Urgents
                  </span>
                </div>
              </div>

              {/* Bar Chart Container */}
              <div style={{
                height: '210px',
                display: 'flex',
                alignItems: 'flex-end',
                gap: '8px',
                paddingTop: '20px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                position: 'relative'
              }}>
                {data.volume_trends.map((point, idx) => {
                  const barHeightPct = Math.max(8, (point.total_tickets / maxVolume) * 100);
                  const isHovered = hoveredBarIndex === idx;

                  return (
                    <div
                      key={idx}
                      onMouseEnter={() => setHoveredBarIndex(idx)}
                      onMouseLeave={() => setHoveredBarIndex(null)}
                      style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        height: '100%',
                        justifyContent: 'flex-end',
                        cursor: 'pointer',
                        position: 'relative'
                      }}
                    >
                      {/* Tooltip on Hover */}
                      {isHovered && (
                        <div style={{
                          position: 'absolute',
                          bottom: `${barHeightPct + 12}%`,
                          background: 'rgba(10, 10, 22, 0.95)',
                          border: '1px solid rgba(139, 92, 246, 0.4)',
                          borderRadius: '8px',
                          padding: '6px 10px',
                          fontSize: '11px',
                          whiteSpace: 'nowrap',
                          zIndex: 20,
                          boxShadow: '0 8px 20px rgba(0,0,0,0.6)',
                          pointerEvents: 'none'
                        }}>
                          <div style={{ fontWeight: 700, color: '#f8fafc' }}>{point.label}</div>
                          <div style={{ color: '#a78bfa' }}>Total : {point.total_tickets}</div>
                          <div style={{ color: '#34d399' }}>Résolus : {point.resolved_count}</div>
                          {point.urgent_count > 0 && <div style={{ color: '#f87171' }}>Urgents : {point.urgent_count}</div>}
                        </div>
                      )}

                      {/* Bar Stack */}
                      <div style={{
                        width: '100%',
                        maxWidth: '28px',
                        height: `${barHeightPct}%`,
                        borderRadius: '6px 6px 0 0',
                        background: isHovered
                          ? 'linear-gradient(180deg, #9061f9 0%, #6d28d9 100%)'
                          : 'linear-gradient(180deg, #7c3aed 0%, #4c1d95 100%)',
                        boxShadow: isHovered ? '0 0 12px rgba(124, 58, 237, 0.6)' : 'none',
                        transition: 'all 0.18s ease'
                      }} />
                    </div>
                  );
                })}
              </div>

              {/* X Axis Labels */}
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px', fontSize: '10.5px', color: 'rgba(255, 255, 255, 0.35)' }}>
                {data.volume_trends.map((p, idx) => {
                  if (idx % 3 === 0 || idx === data.volume_trends.length - 1) {
                    return <span key={idx}>{p.label}</span>;
                  }
                  return null;
                })}
              </div>
            </div>

            {/* Category Distribution Breakdown */}
            <div style={{
              background: 'rgba(15, 15, 28, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.07)',
              borderRadius: '20px',
              padding: '22px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              backdropFilter: 'blur(16px)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700, color: '#f8fafc' }}>
                  Répartition par Catégories
                </h3>
                <span style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>
                  {data.category_distribution.length} catégories
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', maxHeight: '250px' }}>
                {data.category_distribution.map((cat, idx) => (
                  <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px' }}>
                      <span style={{ fontWeight: 600, color: 'rgba(255, 255, 255, 0.85)' }}>{cat.category}</span>
                      <span style={{ color: '#a78bfa', fontWeight: 700 }}>{cat.count} ({cat.percentage}%)</span>
                    </div>
                    {/* Progress Bar */}
                    <div style={{ height: '6px', width: '100%', background: 'rgba(255, 255, 255, 0.06)', borderRadius: '999px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${cat.percentage}%`,
                        background: 'linear-gradient(90deg, #7c3aed, #ec4899)',
                        borderRadius: '999px'
                      }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '10.5px', color: 'rgba(255, 255, 255, 0.35)' }}>
                      MTTR moyen : {cat.avg_resolution_hours}h
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* ── 4. MATRICE MTTR & RESPECT DES SLA PAR PRIORITÉ ── */}
          <div style={{
            background: 'rgba(15, 15, 28, 0.75)',
            border: '1px solid rgba(255, 255, 255, 0.07)',
            borderRadius: '20px',
            padding: '22px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            backdropFilter: 'blur(16px)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                  Temps Moyen de Résolution (MTTR) vs Cibles SLA
                </h3>
                <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'rgba(255, 255, 255, 0.4)' }}>
                  Comparaison des délais constatés de clôture face aux seuils contractuels
                </p>
              </div>
              <Link to="/sla" style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                color: '#a78bfa', fontSize: '12px', fontWeight: 600, textDecoration: 'none'
              }}>
                Gérer les Politiques SLA <ChevronRight size={14} />
              </Link>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              {data.mttr_metrics.by_priority.map((prioItem, idx) => {
                let prioColor = '#34d399';
                if (prioItem.priority === TicketPriority.URGENT) prioColor = '#f87171';
                else if (prioItem.priority === TicketPriority.HIGH) prioColor = '#fb923c';
                else if (prioItem.priority === TicketPriority.MEDIUM) prioColor = '#60a5fa';

                return (
                  <div
                    key={idx}
                    style={{
                      background: 'rgba(255, 255, 255, 0.025)',
                      border: `1px solid ${prioItem.is_within_sla ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.3)'}`,
                      borderRadius: '16px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: prioColor }}>
                        {prioItem.priority}
                      </span>
                      <span style={{
                        fontSize: '10.5px', padding: '2px 7px', borderRadius: '6px',
                        background: prioItem.is_within_sla ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: prioItem.is_within_sla ? '#34d399' : '#f87171',
                        fontWeight: 700
                      }}>
                        {prioItem.is_within_sla ? "✓ Dans le SLA" : "⚠️ Dépassement"}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                      <span style={{ fontSize: '1.6rem', fontWeight: 700, color: '#f8fafc' }}>
                        {prioItem.avg_resolution_hours}h
                      </span>
                      <span style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.4)' }}>
                        / cible {prioItem.sla_target_hours}h
                      </span>
                    </div>

                    {/* Visual Ratio Bar */}
                    <div style={{ height: '6px', width: '100%', background: 'rgba(255, 255, 255, 0.06)', borderRadius: '999px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (prioItem.avg_resolution_hours / prioItem.sla_target_hours) * 100)}%`,
                        background: prioItem.is_within_sla ? '#10b981' : '#ef4444',
                        borderRadius: '999px'
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── 5. PERFORMANCE OPÉRATIONNELLE DES AGENTS ── */}
          <div style={{
            background: 'rgba(15, 15, 28, 0.75)',
            border: '1px solid rgba(255, 255, 255, 0.07)',
            borderRadius: '20px',
            padding: '22px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            backdropFilter: 'blur(16px)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Users size={18} style={{ color: '#a78bfa' }} />
                <div>
                  <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                    Performance des Techniciens & Équipes Support
                  </h3>
                  <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'rgba(255, 255, 255, 0.4)' }}>
                    Volumes traités, MTTR individuel, respect des engagements et équilibrage de charge
                  </p>
                </div>
              </div>
              <Link to="/agents" style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                color: '#a78bfa', fontSize: '12px', fontWeight: 600, textDecoration: 'none'
              }}>
                Gérer les Agents <ChevronRight size={14} />
              </Link>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.35)', fontSize: '11px', textTransform: 'uppercase' }}>
                    <th style={{ textAlign: 'left', padding: '10px 14px' }}>Agent</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px' }}>Compétences</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>Assignés</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>Résolus</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>MTTR</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>SLA %</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>Charge</th>
                    <th style={{ textAlign: 'center', padding: '10px 14px' }}>Évaluation IA</th>
                  </tr>
                </thead>
                <tbody>
                  {data.agent_performances.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'rgba(255, 255, 255, 0.4)' }}>
                        Aucun agent enregistré dans le système.
                      </td>
                    </tr>
                  ) : (
                    data.agent_performances.map((ag) => (
                      <tr
                        key={ag.agent_id}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          transition: 'background 0.15s'
                        }}
                      >
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 600, color: '#f8fafc' }}>{ag.agent_name}</div>
                          <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>{ag.email}</div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                            {ag.skills.slice(0, 2).map((sk, i) => (
                              <span key={i} style={{
                                padding: '2px 6px', borderRadius: '4px',
                                background: 'rgba(139, 92, 246, 0.1)', color: '#c4b5fd',
                                fontSize: '10.5px'
                              }}>
                                {sk}
                              </span>
                            ))}
                            {ag.skills.length > 2 && (
                              <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)' }}>
                                +{ag.skills.length - 2}
                              </span>
                            )}
                          </div>
                        </td>
                        <td style={{ textAlign: 'center', padding: '12px 14px', fontWeight: 600 }}>{ag.assigned_count}</td>
                        <td style={{ textAlign: 'center', padding: '12px 14px', fontWeight: 700, color: '#34d399' }}>{ag.resolved_count}</td>
                        <td style={{ textAlign: 'center', padding: '12px 14px', color: 'rgba(255,255,255,0.8)' }}>{ag.avg_resolution_hours}h</td>
                        <td style={{ textAlign: 'center', padding: '12px 14px' }}>
                          <span style={{
                            padding: '2px 8px', borderRadius: '999px', fontSize: '11.5px', fontWeight: 700,
                            background: ag.sla_compliance_pct >= 90 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: ag.sla_compliance_pct >= 90 ? '#34d399' : '#fbbf24'
                          }}>
                            {ag.sla_compliance_pct}%
                          </span>
                        </td>
                        <td style={{ textAlign: 'center', padding: '12px 14px' }}>
                          <span style={{
                            padding: '2px 8px', borderRadius: '6px', fontSize: '11px',
                            background: ag.workload > 5 ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.05)',
                            color: ag.workload > 5 ? '#f87171' : 'rgba(255,255,255,0.7)',
                            fontWeight: 600
                          }}>
                            {ag.workload} en cours
                          </span>
                        </td>
                        <td style={{ textAlign: 'center', padding: '12px 14px' }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            fontSize: '11px', fontWeight: 700,
                            color: ag.efficiency_rating === 'Excellent' ? '#34d399' : '#a78bfa'
                          }}>
                            <Award size={13} /> {ag.efficiency_rating}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── 6. TICKETS RÉCURRENTS NÉCESSITANT UNE ACTION STRATÉGIQUE (PROBLEM MANAGEMENT) ── */}
          <div style={{
            background: 'rgba(15, 15, 28, 0.75)',
            border: '1px solid rgba(255, 255, 255, 0.07)',
            borderRadius: '20px',
            padding: '22px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            backdropFilter: 'blur(16px)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} style={{ color: '#f87171' }} />
                <div>
                  <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                    Tickets Récurrents & Actions Stratégiques (Root Cause Analysis ITIL)
                  </h3>
                  <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'rgba(255, 255, 255, 0.4)' }}>
                    Détection des causes racines communes et plans d'action préventifs formulés par l'IA
                  </p>
                </div>
              </div>
              <span style={{
                fontSize: '11px', padding: '3px 10px', borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#fca5a5', fontWeight: 700
              }}>
                {data.predictive_insights.strategic_issues.length} PROBLÈMES CLÉS IDENTIFIÉS
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px' }}>
              {data.predictive_insights.strategic_issues.map((issue) => (
                <div
                  key={issue.cluster_id}
                  style={{
                    background: 'rgba(255, 255, 255, 0.025)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    borderRadius: '16px',
                    padding: '18px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{
                      fontSize: '11px', padding: '2px 8px', borderRadius: '6px',
                      background: 'rgba(239, 68, 68, 0.18)', color: '#f87171', fontWeight: 700
                    }}>
                      {issue.impact_level} · {issue.recurrence_count} OCCURRENCES
                    </span>
                    <span style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>
                      ~{issue.estimated_hours_lost}h perdues
                    </span>
                  </div>

                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700, color: '#f8fafc' }}>
                      {issue.title}
                    </h4>
                    <span style={{ fontSize: '11.5px', color: '#a78bfa' }}>Catégorie : {issue.category}</span>
                  </div>

                  {/* Root Cause Analysis */}
                  <div style={{
                    background: 'rgba(0, 0, 0, 0.25)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    fontSize: '12px',
                    color: 'rgba(255, 255, 255, 0.75)',
                    lineHeight: 1.5
                  }}>
                    <div style={{ fontWeight: 700, color: '#fbbf24', fontSize: '11px', marginBottom: '2px', textTransform: 'uppercase' }}>
                      🔍 Cause Racine Détectée :
                    </div>
                    {issue.root_cause_analysis}
                  </div>

                  {/* Strategic Recommendation */}
                  <div style={{
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    fontSize: '12px',
                    color: '#d1fae5',
                    lineHeight: 1.5
                  }}>
                    <div style={{ fontWeight: 700, color: '#34d399', fontSize: '11px', marginBottom: '2px', textTransform: 'uppercase' }}>
                      💡 Action Stratégique Recommandée :
                    </div>
                    {issue.ai_strategic_recommendation}
                  </div>

                  {/* Preventive Action Steps */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '2px' }}>
                    {issue.preventive_action_plan.map((step, sIdx) => (
                      <div key={sIdx} style={{ fontSize: '11.5px', color: 'rgba(255, 255, 255, 0.65)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ color: '#10b981', fontWeight: 700 }}>✓</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>

                  {/* Sample Tickets Links */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '10px', marginTop: '4px' }}>
                    <span style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.35)' }}>
                      Exemples : {issue.sample_ticket_ids.map(id => `#${id}`).join(', ')}
                    </span>
                    <Link
                      to="/tickets"
                      style={{
                        display: 'flex', alignItems: 'center', gap: '3px',
                        fontSize: '11.5px', color: '#c4b5fd', fontWeight: 600, textDecoration: 'none'
                      }}
                    >
                      Examiner le cluster <ArrowUpRight size={12} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

    </div>
  );
};

export default Dashboard;