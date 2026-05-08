import React, { useEffect, useState } from 'react';
import {
  Ticket,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowUpRight,
  Zap,
} from 'lucide-react';
import { type Ticket as TicketType, TicketStatus } from '../../types';
import api from '../../api/axios';
import { formatDistanceToNow } from 'date-fns';

const Dashboard: React.FC = () => {
  const [tickets, setTickets] = useState<TicketType[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const response = await api.get('/tickets');
        setTickets(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard data', error);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const open = tickets.filter(t => t.status === TicketStatus.OPEN).length;
  const inProgress = tickets.filter(t => t.status === TicketStatus.IN_PROGRESS).length;
  const resolved = tickets.filter(t => t.status === TicketStatus.RESOLVED).length;

  const stats = [
    { label: 'Total Tickets', value: tickets.length, trend: '+12%', trendPos: true, colorClass: 'purple', icon: <Ticket size={18} /> },
    { label: 'Open Tickets', value: open, trend: '+5%', trendPos: true, colorClass: 'amber', icon: <AlertCircle size={18} /> },
    { label: 'In Progress', value: inProgress, trend: '−2%', trendPos: false, colorClass: 'blue', icon: <Clock size={18} /> },
    { label: 'Resolved', value: resolved, trend: '+18%', trendPos: true, colorClass: 'green', icon: <CheckCircle2 size={18} /> },
  ];

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase().replace('_', '-');
    if (s.includes('open')) return 'db-badge db-badge-open';
    if (s.includes('progress')) return 'db-badge db-badge-progress';
    if (s.includes('resolved')) return 'db-badge db-badge-resolved';
    return 'db-badge db-badge-open';
  };

  const getPriorityBadge = (priority: string) => {
    const p = priority.toLowerCase();
    if (p === 'critical') return 'db-badge db-badge-critical';
    if (p === 'high') return 'db-badge db-badge-high';
    return 'db-badge db-badge-low';
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');

        .db-root * { box-sizing: border-box; }

        .db-root {
          font-family: 'DM Sans', sans-serif;
          background: #080810;
          min-height: 100vh;
          padding: 32px;
          position: relative;
          overflow: hidden;
        }

        .db-root::before {
          content: '';
          position: fixed;
          inset: 0;
          background:
            radial-gradient(ellipse 70% 50% at 15% 20%, rgba(99,80,245,0.14) 0%, transparent 60%),
            radial-gradient(ellipse 50% 40% at 85% 70%, rgba(168,85,247,0.09) 0%, transparent 55%),
            radial-gradient(ellipse 40% 30% at 60% 10%, rgba(99,80,245,0.07) 0%, transparent 50%);
          pointer-events: none;
          z-index: 0;
        }

        .db-content { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 28px; }

        /* ── HERO ── */
        .db-hero {
          display: grid;
          grid-template-columns: 1fr 300px;
          gap: 20px;
          align-items: start;
        }

        .db-hero-main {
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(255,255,255,0.07);
          border-radius: 20px;
          padding: 36px 40px;
          position: relative;
          overflow: hidden;
        }

        .db-hero-main::before {
          content: '';
          position: absolute;
          inset: 0;
          background: radial-gradient(ellipse 60% 80% at 0% 100%, rgba(99,80,245,0.17) 0%, transparent 60%);
          pointer-events: none;
        }

        .db-eyebrow {
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: rgba(167,139,250,0.8);
          margin-bottom: 14px;
          font-weight: 500;
        }

        .db-hero-title {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(26px, 3vw, 40px);
          line-height: 1.1;
          color: #fff;
          letter-spacing: -0.8px;
          margin-bottom: 12px;
        }

        .db-hero-title em { font-style: italic; color: #a78bfa; }

        .db-hero-sub {
          font-size: 14px;
          color: rgba(255,255,255,0.38);
          font-weight: 300;
          line-height: 1.65;
          max-width: 400px;
          margin-bottom: 24px;
        }

        .db-hero-actions { display: flex; gap: 10px; }

        .db-btn-secondary {
          padding: 10px 18px;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.6);
          transition: all 0.2s;
        }

        .db-btn-secondary:hover { background: rgba(255,255,255,0.08); color: #fff; border-color: rgba(255,255,255,0.18); }

        .db-btn-primary {
          padding: 10px 18px;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          background: linear-gradient(135deg, #6350f5, #a855f7);
          border: none;
          color: #fff;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .db-btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }

        .db-live-row { display: flex; gap: 18px; flex-wrap: wrap; }

        .db-live-dot {
          display: flex;
          align-items: center;
          gap: 7px;
          font-size: 12px;
          color: rgba(255,255,255,0.45);
        }

        .db-live-dot span {
          width: 7px; height: 7px; border-radius: 50%; display: inline-block;
        }

        .db-dot-green { background: #34d399; box-shadow: 0 0 6px #34d39980; animation: dbPulse 2s ease-in-out infinite; }
        .db-dot-amber { background: #fbbf24; box-shadow: 0 0 6px #fbbf2480; animation: dbPulse 2.5s ease-in-out infinite; }
        .db-dot-purple { background: #a78bfa; box-shadow: 0 0 6px #a78bfa80; animation: dbPulse 3s ease-in-out infinite; }

        @keyframes dbPulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

        /* AI PANEL */
        .db-ai-panel {
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(167,139,250,0.15);
          border-radius: 20px;
          padding: 24px;
          animation: dbFloat 6s ease-in-out infinite;
        }

        @keyframes dbFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }

        .db-ai-head { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }

        .db-ai-icon {
          width: 32px; height: 32px; border-radius: 8px;
          background: linear-gradient(135deg,#6350f5,#a855f7);
          display: flex; align-items: center; justify-content: center;
          font-size: 15px; flex-shrink: 0;
        }

        .db-ai-title { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.85); }
        .db-ai-sub { font-size: 11px; color: rgba(255,255,255,0.28); }

        .db-ai-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 11px 0;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .db-ai-item:last-child { border-bottom: none; padding-bottom: 0; }

        .db-ai-dot {
          width: 6px; height: 6px; border-radius: 50%;
          margin-top: 5px; flex-shrink: 0;
        }

        .db-ai-dot-red   { background: #f87171; box-shadow: 0 0 6px #f8717180; }
        .db-ai-dot-green { background: #34d399; box-shadow: 0 0 6px #34d39980; }
        .db-ai-dot-amber { background: #fbbf24; box-shadow: 0 0 6px #fbbf2480; }

        .db-ai-item p { font-size: 12px; color: rgba(255,255,255,0.55); line-height: 1.55; font-weight: 300; }
        .db-ai-item strong { color: rgba(255,255,255,0.88); font-weight: 500; }

        /* KPI CARDS */
        .db-kpi-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 14px;
        }

        .db-kpi-card {
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px;
          padding: 22px;
          position: relative;
          overflow: hidden;
          transition: all 0.3s ease;
          cursor: default;
        }

        .db-kpi-card:hover {
          border-color: rgba(167,139,250,0.22);
          background: rgba(255,255,255,0.045);
          transform: translateY(-2px);
        }

        .db-kpi-card::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: 16px;
          opacity: 0;
          transition: opacity 0.3s;
          pointer-events: none;
        }

        .db-kpi-card:hover::after { opacity: 1; }

        .db-kpi-purple::after { background: radial-gradient(ellipse at 0% 100%, rgba(99,80,245,0.11) 0%, transparent 60%); }
        .db-kpi-amber::after  { background: radial-gradient(ellipse at 0% 100%, rgba(251,191,36,0.08) 0%, transparent 60%); }
        .db-kpi-blue::after   { background: radial-gradient(ellipse at 0% 100%, rgba(59,130,246,0.09) 0%, transparent 60%); }
        .db-kpi-green::after  { background: radial-gradient(ellipse at 0% 100%, rgba(52,211,153,0.09) 0%, transparent 60%); }

        .db-kpi-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }

        .db-kpi-icon {
          width: 36px; height: 36px; border-radius: 9px;
          display: flex; align-items: center; justify-content: center;
        }

        .db-kpi-icon-purple { background: rgba(99,80,245,0.14); border: 1px solid rgba(99,80,245,0.2); color: #a78bfa; }
        .db-kpi-icon-amber  { background: rgba(251,191,36,0.11); border: 1px solid rgba(251,191,36,0.2); color: #fbbf24; }
        .db-kpi-icon-blue   { background: rgba(59,130,246,0.11); border: 1px solid rgba(59,130,246,0.2); color: #60a5fa; }
        .db-kpi-icon-green  { background: rgba(52,211,153,0.11); border: 1px solid rgba(52,211,153,0.2); color: #34d399; }

        .db-kpi-trend {
          font-size: 11px; font-weight: 500;
          padding: 3px 8px; border-radius: 100px;
        }

        .db-trend-pos { background: rgba(52,211,153,0.11); color: #34d399; border: 1px solid rgba(52,211,153,0.2); }
        .db-trend-neg { background: rgba(248,113,113,0.11); color: #f87171; border: 1px solid rgba(248,113,113,0.2); }

        .db-kpi-num {
          font-family: 'DM Serif Display', serif;
          font-size: 34px; color: #fff; letter-spacing: -0.5px; margin-bottom: 3px;
        }

        .db-kpi-label { font-size: 12px; color: rgba(255,255,255,0.38); font-weight: 400; margin-bottom: 12px; }

        .db-kpi-bar { height: 2px; border-radius: 2px; background: rgba(255,255,255,0.06); overflow: hidden; margin-bottom: 8px; }
        .db-kpi-bar-fill { height: 100%; border-radius: 2px; }
        .db-bar-purple { background: linear-gradient(to right, #6350f5, #a855f7); }
        .db-bar-amber  { background: linear-gradient(to right, #f59e0b, #fbbf24); }
        .db-bar-blue   { background: linear-gradient(to right, #3b82f6, #60a5fa); }
        .db-bar-green  { background: linear-gradient(to right, #059669, #34d399); }

        .db-kpi-hint { font-size: 11px; color: rgba(167,139,250,0.55); font-style: italic; }

        /* BOTTOM GRID */
        .db-bottom { display: grid; grid-template-columns: 1fr 280px; gap: 20px; }

        /* TABLE PANEL */
        .db-panel {
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 20px;
          overflow: hidden;
        }

        .db-panel-head {
          padding: 18px 24px;
          border-bottom: 1px solid rgba(255,255,255,0.05);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .db-panel-title { font-size: 14px; font-weight: 500; color: rgba(255,255,255,0.88); }

        .db-panel-link {
          font-size: 12px; color: #a78bfa; cursor: pointer;
          display: flex; align-items: center; gap: 4px;
          opacity: 0.75; transition: opacity 0.2s;
          background: none; border: none; font-family: 'DM Sans', sans-serif;
        }

        .db-panel-link:hover { opacity: 1; }

        .db-table-header {
          display: grid;
          grid-template-columns: 1fr 110px 95px 105px;
          gap: 10px;
          padding: 10px 24px;
          border-bottom: 1px solid rgba(255,255,255,0.04);
        }

        .db-table-header span {
          font-size: 10px;
          letter-spacing: 1px;
          text-transform: uppercase;
          color: rgba(255,255,255,0.22);
          font-weight: 500;
        }

        .db-table-row {
          display: grid;
          grid-template-columns: 1fr 110px 95px 105px;
          gap: 10px;
          align-items: center;
          padding: 13px 24px;
          border-bottom: 1px solid rgba(255,255,255,0.03);
          transition: background 0.2s;
          cursor: pointer;
        }

        .db-table-row:hover { background: rgba(255,255,255,0.03); }
        .db-table-row:last-child { border-bottom: none; }

        .db-ticket-subject {
          font-size: 13px;
          color: rgba(255,255,255,0.82);
          font-weight: 400;
          margin-bottom: 3px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .db-ticket-cat { font-size: 11px; color: rgba(255,255,255,0.28); }
        .db-ticket-time { font-size: 12px; color: rgba(255,255,255,0.28); }

        .db-badge {
          display: inline-flex; align-items: center; gap: 5px;
          font-size: 11px; padding: 3px 9px;
          border-radius: 100px; font-weight: 500;
        }

        .db-badge-open     { background: rgba(251,191,36,0.11); color: #fbbf24; border: 1px solid rgba(251,191,36,0.2); }
        .db-badge-progress { background: rgba(99,80,245,0.14);  color: #a78bfa; border: 1px solid rgba(99,80,245,0.22); }
        .db-badge-resolved { background: rgba(52,211,153,0.11); color: #34d399; border: 1px solid rgba(52,211,153,0.2); }
        .db-badge-critical { background: rgba(248,113,113,0.11); color: #f87171; border: 1px solid rgba(248,113,113,0.2); }
        .db-badge-high     { background: rgba(251,191,36,0.11); color: #fbbf24; border: 1px solid rgba(251,191,36,0.2); }
        .db-badge-low      { background: rgba(52,211,153,0.11); color: #34d399; border: 1px solid rgba(52,211,153,0.2); }

        .db-empty {
          padding: 40px 24px;
          text-align: center;
          font-size: 13px;
          color: rgba(255,255,255,0.25);
        }

        /* METRICS PANEL */
        .db-metrics { background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 24px; }

        .db-score-wrap { text-align: center; margin: 16px 0 20px; }
        .db-score-ring { position: relative; width: 100px; height: 100px; margin: 0 auto 8px; }
        .db-score-ring svg { transform: rotate(-90deg); }
        .db-score-inner {
          position: absolute; inset: 0;
          display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        .db-score-num { font-family: 'DM Serif Display', serif; font-size: 28px; color: #fff; line-height: 1; }
        .db-score-lbl { font-size: 10px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }

        .db-sep { height: 1px; background: rgba(255,255,255,0.05); margin: 18px 0; }

        .db-metric-item { margin-bottom: 18px; }
        .db-metric-item:last-child { margin-bottom: 0; }
        .db-metric-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 7px; }
        .db-metric-name { font-size: 12px; color: rgba(255,255,255,0.4); }
        .db-metric-val  { font-size: 13px; color: rgba(255,255,255,0.82); font-weight: 500; }
        .db-metric-track { height: 2px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
        .db-metric-fill  { height: 100%; border-radius: 2px; }
        .db-hint-badge {
          margin-top: 6px;
          display: inline-block;
          padding: 2px 8px;
          background: rgba(99,80,245,0.11);
          border: 1px solid rgba(99,80,245,0.15);
          border-radius: 4px;
          font-size: 10px;
          color: rgba(167,139,250,0.7);
          font-style: italic;
        }

        @media (max-width: 900px) {
          .db-hero       { grid-template-columns: 1fr; }
          .db-ai-panel   { animation: none; }
          .db-kpi-grid   { grid-template-columns: 1fr 1fr; }
          .db-bottom     { grid-template-columns: 1fr; }
          .db-root       { padding: 20px 16px; }
        }
      `}</style>

      <div className="db-root">
        <div className="db-content">

          {/* ── HERO ── */}
          <div className="db-hero">
            <div className="db-hero-main">
              <p className="db-eyebrow">AI Operations Center</p>
              <h1 className="db-hero-title">
                Support <em>intelligence,</em><br />
                at full velocity.
              </h1>
              <p className="db-hero-sub">
                Real-time visibility across all queues. AI monitors SLA risk, detects patterns,
                and surfaces insights before they become incidents.
              </p>
              <div className="db-hero-actions">
                <button className="db-btn-secondary">Export PDF</button>
                <button className="db-btn-primary">
                  <Zap size={14} /> Create Ticket
                </button>
              </div>
              <div className="db-live-row" style={{ marginTop: '24px' }}>
                <div className="db-live-dot"><span className="db-dot-green" />System nominal</div>
                <div className="db-live-dot"><span className="db-dot-amber" />3 SLA at risk</div>
                <div className="db-live-dot"><span className="db-dot-purple" />AI active</div>
              </div>
            </div>

            <div className="db-ai-panel">
              <div className="db-ai-head">
                <div className="db-ai-icon">✦</div>
                <div>
                  <div className="db-ai-title">AI Insights</div>
                  <div className="db-ai-sub">Updated 2 min ago</div>
                </div>
              </div>
              <div className="db-ai-item">
                <div className="db-ai-dot db-ai-dot-red" />
                <p><strong>12 SLA risks</strong> detected today — billing queue above threshold</p>
              </div>
              <div className="db-ai-item">
                <div className="db-ai-dot db-ai-dot-green" />
                <p>Response efficiency <strong>+18%</strong> vs last week</p>
              </div>
              <div className="db-ai-item">
                <div className="db-ai-dot db-ai-dot-amber" />
                <p><strong>3 repetitive incidents</strong> identified — candidate for automation</p>
              </div>
            </div>
          </div>

          {/* ── KPI CARDS ── */}
          <div className="db-kpi-grid">
            {[
              { s: stats[0], color: 'purple', bar: 72, hint: 'AI: steady inflow, no anomalies' },
              { s: stats[1], color: 'amber',  bar: 45, hint: 'AI: 3 at SLA threshold' },
              { s: stats[2], color: 'blue',   bar: 38, hint: 'AI: team capacity optimal' },
              { s: stats[3], color: 'green',  bar: 84, hint: 'AI: continued improvement predicted' },
            ].map(({ s, color, bar, hint }) => (
              <div key={s.label} className={`db-kpi-card db-kpi-${color}`}>
                <div className="db-kpi-top">
                  <div className={`db-kpi-icon db-kpi-icon-${color}`}>{s.icon}</div>
                  <span className={`db-kpi-trend ${s.trendPos ? 'db-trend-pos' : 'db-trend-neg'}`}>{s.trend}</span>
                </div>
                <div className="db-kpi-num">{s.value.toLocaleString()}</div>
                <div className="db-kpi-label">{s.label}</div>
                <div className="db-kpi-bar">
                  <div className={`db-kpi-bar-fill db-bar-${color}`} style={{ width: `${bar}%` }} />
                </div>
                <div className="db-kpi-hint">{hint}</div>
              </div>
            ))}
          </div>

          {/* ── BOTTOM GRID ── */}
          <div className="db-bottom">

            {/* TICKETS TABLE */}
            <div className="db-panel">
              <div className="db-panel-head">
                <span className="db-panel-title">Recent Tickets</span>
                <button className="db-panel-link">
                  View all <ArrowUpRight size={13} />
                </button>
              </div>
              <div className="db-table-header">
                <span>Subject</span><span>Status</span><span>Priority</span><span>Created</span>
              </div>

              {loading && <div className="db-empty">Loading...</div>}
              {!loading && tickets.length === 0 && <div className="db-empty">No tickets found</div>}
              {!loading && tickets.slice(0, 5).map((ticket, index) => (
                <div key={ticket.id || index} className="db-table-row">
                  <div>
                    <div className="db-ticket-subject">{ticket.subject}</div>
                    <div className="db-ticket-cat">{ticket.category}</div>
                  </div>
                  <span className={getStatusBadge(ticket.status)}>
                    {ticket.status.replace('_', ' ')}
                  </span>
                  <span className={getPriorityBadge(ticket.priority)}>
                    {ticket.priority}
                  </span>
                  <span className="db-ticket-time">
                    {formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })}
                  </span>
                </div>
              ))}
            </div>

            {/* METRICS */}
            <div className="db-metrics">
              <div className="db-panel-title" style={{ marginBottom: '4px' }}>Performance</div>

              <div className="db-score-wrap">
                <div className="db-score-ring">
                  <svg width="100" height="100" viewBox="0 0 100 100">
                    <defs>
                      <linearGradient id="scoreGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#6350f5" />
                        <stop offset="100%" stopColor="#a855f7" />
                      </linearGradient>
                    </defs>
                    <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                    <circle cx="50" cy="50" r="42" fill="none" stroke="url(#scoreGrad)" strokeWidth="8"
                      strokeDasharray="264" strokeDashoffset="40" strokeLinecap="round" />
                  </svg>
                  <div className="db-score-inner">
                    <div className="db-score-num">87</div>
                    <div className="db-score-lbl">AI Score</div>
                  </div>
                </div>
              </div>

              <div className="db-sep" />

              {[
                { label: 'Response Time', val: '1.2 hrs', pct: 75, cls: 'db-bar-purple', hint: 'AI: −8 min vs forecast' },
                { label: 'Satisfaction',  val: '94%',    pct: 94, cls: 'db-bar-green',  hint: null },
                { label: 'Resolution',    val: '82%',    pct: 82, cls: 'db-bar-blue',   hint: 'AI: trending up' },
                { label: 'SLA Compliance',val: '91%',    pct: 91, cls: 'db-bar-green',  hint: null },
              ].map(m => (
                <div key={m.label} className="db-metric-item">
                  <div className="db-metric-row">
                    <span className="db-metric-name">{m.label}</span>
                    <span className="db-metric-val">{m.val}</span>
                  </div>
                  <div className="db-metric-track">
                    <div className={`db-metric-fill ${m.cls}`} style={{ width: `${m.pct}%` }} />
                  </div>
                  {m.hint && <div className="db-hint-badge">{m.hint}</div>}
                </div>
              ))}
            </div>

          </div>
        </div>
      </div>
    </>
  );
};

export default Dashboard;