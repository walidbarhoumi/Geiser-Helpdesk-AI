import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, AlertTriangle, Shield, User,
  Bot, Sparkles, Loader2, CheckCircle2, XCircle,
  Activity, Zap, MessageSquare, Send,
  Award, Paperclip, Clock, History, ChevronDown, ChevronUp,
  Download, Upload, Star
} from 'lucide-react';
import { type Ticket, type RoutingResult, type Attachment, UserRole } from '../../types';
import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import { useWebSocket } from '../../context/WebSocketContext';
import { format } from 'date-fns';
import SLABadge from '../../components/sla/SLABadge';
import { type SLATicketDetail } from '../../types';
import IntelligentTriagePanel from '../../components/ai/IntelligentTriagePanel';
import { AgentCopilotDrawer } from '../../components/ai/AgentCopilotDrawer';


/* ─── Styles ──────────────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('td-styles')) return;
  const s = document.createElement('style');
  s.id = 'td-styles';
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');
    @keyframes td-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }
    @keyframes td-in-up { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
    @keyframes td-spin { to{transform:rotate(360deg)} }
    @keyframes td-shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
    .td-glass { background:rgba(15,15,25,.72); border:1px solid rgba(255,255,255,.07); backdrop-filter:blur(20px); }
    .td-action-btn { transition:all .2s; border:1px solid rgba(255,255,255,.1); background:rgba(255,255,255,.04); color:rgba(255,255,255,.5); cursor:pointer; }
    .td-action-btn:hover { background:rgba(139,92,246,.15); color:#c4b5fd; border-color:rgba(139,92,246,.3); }
    .td-auto-btn { background:linear-gradient(135deg,rgba(139,92,246,.2) 0%,rgba(236,72,153,.2) 100%) !important; border:1px solid rgba(139,92,246,.3) !important; color:#c4b5fd !important; }
    .td-auto-btn:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(139,92,246,.25); }
    .td-auto-btn:disabled { opacity:.5; cursor:not-allowed; transform:none; }
    
    /* AI Specific Styles */
    .ai-smart-card {
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(15, 15, 25, 0.8) 100%);
      border: 1px solid rgba(139, 92, 246, 0.25);
      border-radius: 20px;
      overflow: hidden;
      position: relative;
    }
    .ai-shimmer {
      background: linear-gradient(90deg, transparent, rgba(139, 92, 246, 0.1), transparent);
      background-size: 200% 100%;
      animation: td-shimmer 2s infinite;
    }
    .suggestion-chip {
      padding: 0.4rem 0.8rem;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.5);
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .suggestion-chip:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.3);
      color: #c4b5fd;
      transform: translateY(-1px);
    }
    .ai-input-area {
      width: 100%;
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 1rem;
      color: rgba(255, 255, 255, 0.8);
      font-family: 'DM Sans', sans-serif;
      font-size: 0.875rem;
      line-height: 1.5;
      resize: vertical;
      min-height: 100px;
      outline: none;
      transition: border-color 0.2s;
    }
    .ai-input-area:focus {
      border-color: rgba(139, 92, 246, 0.4);
    }
  `;
  document.head.appendChild(s);
};

const priorityConfig: Record<string, { color: string; bg: string; label: string }> = {
  URGENT:   { color: '#f87171', bg: 'rgba(239,68,68,.1)', label: 'Urgent' },
  HIGH:     { color: '#fb923c', bg: 'rgba(251,146,60,.1)', label: 'High' },
  MEDIUM:   { color: '#60a5fa', bg: 'rgba(96,165,250,.1)', label: 'Medium' },
  LOW:      { color: '#34d399', bg: 'rgba(52,211,153,.1)', label: 'Low' },
};

const Circle: React.FC<{ size: number }> = ({ size }) => (
  <div style={{ width: size, height: size, borderRadius: '50%', border: '2px solid currentColor' }} />
);

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  OPEN:        { color: '#60a5fa', bg: 'rgba(96,165,250,.12)', icon: <Circle size={12} />, label: 'Open' },
  IN_PROGRESS: { color: '#a78bfa', bg: 'rgba(167,139,250,.12)', icon: <Activity size={12} />, label: 'In Progress' },
  RESOLVED:    { color: '#34d399', bg: 'rgba(52,211,153,.12)', icon: <CheckCircle2 size={12} />, label: 'Resolved' },
  CLOSED:      { color: '#64748b', bg: 'rgba(100,116,139,.12)', icon: <XCircle size={12} />, label: 'Closed' },
};

const TicketDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { subscribe } = useWebSocket();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  
  const [isRouting, setIsRouting] = useState(false);
  const [routingResult, setRoutingResult] = useState<RoutingResult | null>(null);
  const [slaDetail, setSlaDetail] = useState<SLATicketDetail | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [isSendingComment, setIsSendingComment] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [csatRating, setCsatRating] = useState(0);
  const [csatHover, setCsatHover] = useState(0);
  const [csatComment, setCsatComment] = useState('');
  const [csatSubmitting, setCsatSubmitting] = useState(false);
  const [csatError, setCsatError] = useState<string | null>(null);

  const handleDownloadAttachment = async (at: Attachment | string) => {
    try {
      if (typeof at === 'string') {
        window.open(at, '_blank');
        return;
      }
      const response = await api.get(`/tickets/${id}/attachments/${at.id}/download`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: at.mime_type });
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = at.original_filename || 'piece-jointe';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      console.error('Failed to download attachment:', err);
      alert('Erreur lors du téléchargement de la pièce jointe.');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setIsUploadingAttachment(true);
    setAttachmentError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post(`/tickets/${id}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchTicket();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Erreur lors du téléversement du fichier.';
      setAttachmentError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsUploadingAttachment(false);
      e.target.value = '';
    }
  };

  const handleSubmitCSAT = async () => {
    if (!id || csatRating < 1 || csatRating > 5) return;
    setCsatSubmitting(true);
    setCsatError(null);
    try {
      await api.post(`/tickets/${id}/satisfaction`, {
        rating: csatRating,
        comment: csatComment.trim() || null,
      });
      await fetchTicket();
      setCsatComment('');
    } catch (err: any) {
      const msg = err.response?.data?.detail;
      setCsatError(typeof msg === 'string' ? msg : 'Erreur lors de la soumission de votre avis.');
    } finally {
      setCsatSubmitting(false);
    }
  };

  useEffect(() => { injectStyles(); }, []);

  const fetchTicket = async () => {
    try {
      const [ticketRes, slaRes] = await Promise.all([
        api.get(`/tickets/${id}`),
        api.get<SLATicketDetail>(`/sla/tickets/${id}/status`).catch(() => null),
      ]);
      setTicket(ticketRes.data);
      if (slaRes) setSlaDetail(slaRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchTicket();
  }, [id]);

  // Live WebSocket real-time updates for this ticket
  useEffect(() => {
    if (!id) return;

    const unsubStatus = subscribe('ticket.status_changed', (event) => {
      const d = event.data;
      if (d.ticket_id === id || d.id === id) {
        setTicket((prev) => (prev ? { ...prev, status: d.new_status || d.status } : prev));
      }
    });

    const unsubAssigned = subscribe('ticket.assigned', (event) => {
      const d = event.data;
      if (d.ticket_id === id || d.id === id) {
        setTicket((prev) => (prev ? { ...prev, assigned_agent_id: d.agent_id } : prev));
      }
    });

    const unsubPriority = subscribe('ticket.priority_changed', (event) => {
      const d = event.data;
      if (d.ticket_id === id || d.id === id) {
        setTicket((prev) => (prev ? { ...prev, priority: d.new_priority || d.priority } : prev));
      }
    });

    const unsubComment = subscribe('ticket.comment_added', (event) => {
      const d = event.data;
      if (d.ticket_id === id || d.id === id) {
        setTicket((prev) => {
          if (!prev) return prev;
          const currentResponses = prev.responses || [];
          if (currentResponses.some((r) => r.created_at === d.created_at && r.content === d.content)) {
            return prev;
          }
          return {
            ...prev,
            responses: [...currentResponses, d],
          };
        });
      }
    });

    const unsubSLA = subscribe('*', (event) => {
      if (event.event && event.event.startsWith('sla.')) {
        const d = event.data;
        if (d.ticket_id === id || d.id === id) {
          setTicket((prev) => (prev ? { ...prev, sla_status: d.sla_state || prev.sla_status } : prev));
        }
      }
    });

    return () => {
      unsubStatus();
      unsubAssigned();
      unsubPriority();
      unsubComment();
      unsubSLA();
    };
  }, [id, subscribe]);

  const handleAutoRoute = async () => {
    if (!id) return;
    setIsRouting(true);
    setRoutingResult(null);
    try {
      const res = await api.post<RoutingResult>(`/tickets/${id}/auto-route`);
      setRoutingResult(res.data);
      fetchTicket(); 
    } catch (err) {
      console.error(err);
    } finally {
      setIsRouting(false);
    }
  };

  const handleSendComment = async () => {
    if (!commentText.trim() || !id) return;
    setIsSendingComment(true);
    try {
      await api.post(`/tickets/${id}/send-response`, {
        response_text: commentText,
        is_internal: false
      });
      setCommentText('');
      fetchTicket();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSendingComment(false);
    }
  };

  if (loading) return (

    <div style={{ height: '70vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '1rem' }}>
      <Loader2 size={40} className="animate-spin" style={{ color: '#8b5cf6', animation: 'td-spin 1s linear infinite' }} />
      <span style={{ color: 'rgba(255,255,255,.3)', fontSize: '.875rem', fontWeight: 600 }}>Analyzing ticket sequence…</span>
    </div>
  );

  if (!ticket) return <div>Ticket not found</div>;

  const prio = priorityConfig[ticket.priority] || priorityConfig.MEDIUM;
  const stat = statusConfig[ticket.status] || statusConfig.OPEN;

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '2rem', animation: 'td-in-up .6s ease both' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button onClick={() => navigate('/tickets')} className="td-action-btn" style={{ padding: '.5rem', borderRadius: 10 }}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', marginBottom: '.25rem' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '.875rem', fontWeight: 700, color: 'rgba(139,92,246,.7)' }}>#{ticket.id.slice(-6).toUpperCase()}</span>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'rgba(255,255,255,.1)' }} />
              <span style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.3)' }}>Created {format(new Date(ticket.created_at), 'MMM dd, yyyy HH:mm')}</span>
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.75rem', color: '#f1f5f9', margin: 0 }}>{ticket.subject}</h1>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem' }}>
          {user?.role !== UserRole.USER && (
            <button 
              className="td-action-btn" 
              onClick={() => setCopilotOpen(true)}
              style={{
                padding: '.6rem 1.25rem',
                borderRadius: 12,
                fontSize: '.875rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '.5rem',
                background: 'linear-gradient(135deg, rgba(139,92,246,.25) 0%, rgba(99,102,241,.25) 100%)',
                border: '1px solid rgba(139,92,246,.45)',
                color: '#c4b5fd',
                boxShadow: '0 0 15px rgba(139, 92, 246, 0.2)',
              }}
            >
              <Sparkles size={16} />
              Agent Copilot
            </button>
          )}
          {user?.role !== UserRole.USER && (ticket.status === 'OPEN' || ticket.status === 'IN_PROGRESS') && (
            <button 
              className="td-action-btn td-auto-btn" 
              onClick={handleAutoRoute}
              disabled={isRouting}
              style={{ padding: '.6rem 1.25rem', borderRadius: 12, fontSize: '.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '.5rem' }}
            >
              {isRouting ? <Loader2 size={16} className="animate-spin" style={{ animation: 'td-spin 1s linear infinite' }} /> : <Bot size={16} />}
              Auto Route
            </button>
          )}
          <div style={{ padding: '.4rem .875rem', borderRadius: 8, background: prio.bg, border: `1px solid ${prio.color}30`, color: prio.color, fontSize: '.75rem', fontWeight: 700 }}>
            {prio.label}
          </div>
          <div style={{ padding: '.4rem .875rem', borderRadius: 8, background: stat.bg, border: `1px solid ${stat.color}30`, color: stat.color, fontSize: '.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '.4rem' }}>
            {stat.icon} {stat.label}
          </div>
          <SLABadge status={ticket.sla_status} deadline={ticket.sla_deadline} />
        </div>
      </div>

      {/* SLA Timeline Bar */}
      {slaDetail && ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED' && (
        <div className="td-glass" style={{ borderRadius: 16, padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.35)', textTransform: 'uppercase', letterSpacing: '.06em' }}>SLA Timeline</span>
            <span style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)' }}>
              {slaDetail.pct_consumed !== undefined ? `${slaDetail.pct_consumed}% consommé` : ''}
              {slaDetail.time_remaining_minutes !== undefined && slaDetail.time_remaining_minutes > 0
                ? ` · ${Math.floor(slaDetail.time_remaining_minutes / 60)}h ${slaDetail.time_remaining_minutes % 60}m restantes`
                : slaDetail.sla_status === 'BREACHED' ? ' · Délai dépassé' : ''}
            </span>
          </div>
          <div style={{ height: 8, background: 'rgba(255,255,255,.06)', borderRadius: 999, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${Math.min(100, slaDetail.pct_consumed ?? 0)}%`,
              borderRadius: 999,
              background: slaDetail.sla_status === 'BREACHED'
                ? 'linear-gradient(90deg,#ef4444,#f87171)'
                : slaDetail.sla_status === 'AT_RISK'
                  ? 'linear-gradient(90deg,#d97706,#fb923c)'
                  : 'linear-gradient(90deg,#059669,#34d399)',
              transition: 'width .5s ease',
            }} />
          </div>
          {ticket.sla_deadline && (
            <div style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.3)' }}>
              Échéance : {format(new Date(ticket.sla_deadline), 'dd/MM/yyyy HH:mm')}
            </div>
          )}
        </div>
      )}

      {/* Solution Appliquée / Résolue Banner */}
      {ticket.resolution_note && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.06) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
          borderRadius: '18px',
          padding: '1.25rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={18} style={{ color: '#34d399' }} />
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#6ee7b7', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Solution Validée & Enregistrée
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '0.92rem', color: '#f8fafc', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {ticket.resolution_note}
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '2rem', alignItems: 'start' }}>
        
        {/* Left Content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Intelligent Triage Panel */}
          {user?.role !== UserRole.USER && ticket.status !== 'CLOSED' && (
            <IntelligentTriagePanel
              ticketId={ticket.id}
              onResponseSent={fetchTicket}
              onTicketResolved={fetchTicket}
            />
          )}


          {/* AI Routing Result Banner or Persistent Reason */}
          {(routingResult || ticket.routing_reason) && (
            <div className="td-glass" style={{ borderRadius: 20, padding: '1.5rem', border: '1px solid rgba(139,92,246,.3)', background: 'linear-gradient(135deg,rgba(139,92,246,.1) 0%,rgba(15,15,25,.72) 100%)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem' }}>
                  <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(139,92,246,.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa' }}>
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '.9375rem', fontWeight: 700, color: '#f1f5f9' }}>
                      {routingResult ? "AI Routing Successful" : "AI Routing Insights"}
                    </h3>
                    <p style={{ margin: 0, fontSize: '.75rem', color: 'rgba(255,255,255,.4)' }}>
                      {routingResult ? "The ticket has been intelligently assigned." : "Historical routing context for this ticket."}
                    </p>
                  </div>
                </div>
                {routingResult && (
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#a78bfa' }}>{routingResult.confidence_score}%</div>
                    <div style={{ fontSize: '.6rem', fontWeight: 700, color: 'rgba(139,92,246,.7)', textTransform: 'uppercase' }}>Match Score</div>
                  </div>
                )}
              </div>
              
              {routingResult && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ padding: '1rem', borderRadius: 12, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)' }}>
                    <div style={{ fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', textTransform: 'uppercase', marginBottom: '.25rem' }}>Assigned Agent</div>
                    <div style={{ fontSize: '.875rem', fontWeight: 600, color: '#f1f5f9' }}>{routingResult.agent_name}</div>
                  </div>
                  <div style={{ padding: '1rem', borderRadius: 12, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)' }}>
                    <div style={{ fontSize: '.65rem', fontWeight: 700, color: 'rgba(255,255,255,.25)', textTransform: 'uppercase', marginBottom: '.25rem' }}>Best Match Team</div>
                    <div style={{ fontSize: '.875rem', fontWeight: 600, color: '#f1f5f9' }}>{routingResult.team_name}</div>
                  </div>
                </div>
              )}
              
              <div style={{ padding: '1rem', borderRadius: 12, background: 'rgba(139,92,246,.05)', border: '1px solid rgba(139,92,246,.15)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.35rem' }}>
                  <Bot size={14} style={{ color: '#a78bfa' }} />
                  <span style={{ fontSize: '.7rem', fontWeight: 700, color: '#a78bfa', textTransform: 'uppercase' }}>Routing Rationale</span>
                </div>
                <p style={{ margin: 0, fontSize: '.78rem', color: 'rgba(255,255,255,.5)', lineHeight: 1.5 }}>
                  {routingResult ? routingResult.routing_reason : ticket.routing_reason}
                </p>
              </div>
            </div>
          )}

          {/* Description */}
          <div className="td-glass" style={{ borderRadius: 24, padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h3 style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '1rem' }}>Description</h3>
              <div style={{ fontSize: '.9375rem', color: 'rgba(255,255,255,.7)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{ticket.description}</div>
            </div>
            
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '.5rem' }}>
                <h3 style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', letterSpacing: '.08em', margin: 0, display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                  <Paperclip size={14} /> Pièces Jointes ({ticket.attachments?.length || 0})
                </h3>
                <label className="td-action-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', padding: '.4rem .8rem', borderRadius: 10, fontSize: '.75rem', cursor: isUploadingAttachment ? 'not-allowed' : 'pointer', opacity: isUploadingAttachment ? 0.6 : 1 }}>
                  {isUploadingAttachment ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                  <span>{isUploadingAttachment ? 'Envoi en cours...' : 'Ajouter un fichier'}</span>
                  <input
                    type="file"
                    onChange={handleFileUpload}
                    disabled={isUploadingAttachment}
                    style={{ display: 'none' }}
                  />
                </label>
              </div>

              {attachmentError && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', padding: '.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)', color: '#f87171', fontSize: '.8125rem', marginBottom: '1rem' }}>
                  <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                  <span>{attachmentError}</span>
                </div>
              )}

              {ticket.attachments && ticket.attachments.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
                  {ticket.attachments.map((at, i) => {
                    const isObj = typeof at === 'object' && at !== null;
                    const fileName = isObj ? at.original_filename : String(at).split('/').pop() || 'Fichier';
                    const fileSize = isObj && at.size_bytes ? (
                      at.size_bytes < 1024 * 1024 
                        ? `${(at.size_bytes / 1024).toFixed(1)} Ko` 
                        : `${(at.size_bytes / (1024 * 1024)).toFixed(1)} Mo`
                    ) : null;
                    const mime = isObj ? at.mime_type : null;

                    return (
                      <div
                        key={isObj ? at.id : i}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '.75rem',
                          padding: '.75rem 1rem',
                          borderRadius: 12,
                          background: 'rgba(255,255,255,.03)',
                          border: '1px solid rgba(255,255,255,.08)',
                          transition: 'all .2s',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', minWidth: 0, flex: 1 }}>
                          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(139,92,246,.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c4b5fd', flexShrink: 0 }}>
                            <Paperclip size={16} />
                          </div>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: '.8125rem', fontWeight: 600, color: 'rgba(255,255,255,.85)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={fileName}>
                              {fileName}
                            </div>
                            <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.4)', display: 'flex', gap: '.5rem', alignItems: 'center' }}>
                              {fileSize && <span>{fileSize}</span>}
                              {mime && <span style={{ opacity: 0.7 }}>• {mime.split('/')[1]?.toUpperCase() || mime}</span>}
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={() => handleDownloadAttachment(at)}
                          className="td-action-btn"
                          title="Télécharger en toute sécurité"
                          style={{
                            padding: '.45rem',
                            borderRadius: 8,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <Download size={15} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ fontSize: '.8125rem', color: 'rgba(255,255,255,.3)', fontStyle: 'italic' }}>
                  Aucune pièce jointe sur ce ticket.
                </div>
              )}
            </div>
          </div>

          {/* Activity / Messages */}
          <div className="td-glass" style={{ borderRadius: 24, padding: '2rem' }}>
            <h3 style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '.5rem' }}>
              <MessageSquare size={14} /> Fil d'échanges & Historique
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(139,92,246,.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa', flexShrink: 0 }}>
                  <Bot size={16} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.25rem' }}>
                    <span style={{ fontSize: '.8125rem', fontWeight: 700, color: '#f1f5f9' }}>GEISER AI</span>
                    <span style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.2)' }}>{format(new Date(ticket.created_at), 'HH:mm')}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '.875rem', color: 'rgba(255,255,255,.5)', lineHeight: 1.5 }}>Ticket initialisé et journalisé dans le système.</p>
                </div>
              </div>

              {/* Dynamic responses */}
              {ticket.responses && ticket.responses.map((resp, i) => (
                <div key={resp.id || i} style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ width: 32, height: 32, borderRadius: '50%', background: resp.role === 'ADMIN' ? 'rgba(236,72,153,.2)' : 'rgba(59,130,246,.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: resp.role === 'ADMIN' ? '#f472b6' : '#60a5fa', flexShrink: 0 }}>
                    <User size={16} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.25rem' }}>
                      <span style={{ fontSize: '.8125rem', fontWeight: 700, color: '#f1f5f9' }}>{resp.sender_name || 'Agent Support'}</span>
                      {resp.created_at && (
                        <span style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.2)' }}>{format(new Date(resp.created_at), 'dd/MM HH:mm')}</span>
                      )}
                    </div>
                    <p style={{ margin: 0, fontSize: '.875rem', color: 'rgba(255,255,255,.8)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{resp.content}</p>
                  </div>
                </div>
              ))}
              
              {/* Message Input */}
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', padding: '1rem', borderRadius: 16, background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)' }}>
                <input 
                  placeholder="Rédiger un message ou utiliser le Copilot pour insérer des snippets…" 
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendComment(); } }}
                  style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: '#f1f5f9', fontSize: '.875rem' }} 
                />
                <button 
                  onClick={handleSendComment}
                  disabled={isSendingComment || !commentText.trim()}
                  style={{ background: 'none', border: 'none', color: '#8b5cf6', cursor: isSendingComment ? 'not-allowed' : 'pointer', opacity: commentText.trim() ? 1 : 0.4 }}
                >
                  {isSendingComment ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                </button>
              </div>
            </div>
          </div>

          {/* Action History / Audit Trail (ISO 27001) */}
          <div className="td-glass" style={{ borderRadius: 24, padding: '1.75rem', marginTop: '1.5rem' }}>
            <div
              onClick={() => setHistoryOpen(!historyOpen)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                cursor: 'pointer', userSelect: 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: 'rgba(139,92,246,.15)', border: '1px solid rgba(139,92,246,.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa'
                }}>
                  <History size={15} />
                </div>
                <div>
                  <span style={{ fontSize: '.78rem', fontWeight: 700, color: '#f1f5f9', letterSpacing: '.04em', textTransform: 'uppercase' }}>
                    Piste d'Audit & Historique des Actions
                  </span>
                  <span style={{ fontSize: '.68rem', color: 'rgba(255,255,255,.3)', marginLeft: '.5rem' }}>
                    (ISO/IEC 27001:2013)
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(139,92,246,.15)', color: '#c4b5fd',
                  fontSize: '.7rem', fontWeight: 700,
                }}>
                  {ticket.action_history?.length || 0} action{(ticket.action_history?.length || 0) > 1 ? 's' : ''}
                </span>
                {historyOpen ? <ChevronUp size={16} style={{ color: 'rgba(255,255,255,.4)' }} /> : <ChevronDown size={16} style={{ color: 'rgba(255,255,255,.4)' }} />}
              </div>
            </div>

            {historyOpen && (
              <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {(!ticket.action_history || ticket.action_history.length === 0) ? (
                  <div style={{ fontSize: '.8rem', color: 'rgba(255,255,255,.3)', fontStyle: 'italic', padding: '1rem 0' }}>
                    Aucune action enregistrée pour le moment.
                  </div>
                ) : (
                  <div style={{ position: 'relative', paddingLeft: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    {/* Vertical line */}
                    <div style={{
                      position: 'absolute', left: '7px', top: '8px', bottom: '8px',
                      width: '2px', background: 'linear-gradient(180deg, rgba(139,92,246,.4) 0%, rgba(139,92,246,.05) 100%)',
                    }} />

                    {ticket.action_history.map((action, idx) => {
                      const actionConfig: Record<string, { label: string; color: string; bg: string }> = {
                        CREATED: { label: 'Ticket Créé', color: '#34d399', bg: 'rgba(52,211,153,.12)' },
                        STATUS_CHANGED: { label: 'Statut Modifié', color: '#60a5fa', bg: 'rgba(96,165,250,.12)' },
                        AGENT_ASSIGNED: { label: 'Agent Assigné', color: '#a78bfa', bg: 'rgba(167,139,250,.12)' },
                        AGENT_REASSIGNED: { label: 'Agent Réassigné', color: '#c084fc', bg: 'rgba(192,132,252,.12)' },
                        PRIORITY_CHANGED: { label: 'Priorité Modifiée', color: '#fbbf24', bg: 'rgba(251,191,36,.12)' },
                        RESPONSE_SENT: { label: 'Réponse Envoyée', color: '#38bdf8', bg: 'rgba(56,189,248,.12)' },
                        RESOLUTION_RECORDED: { label: 'Résolution Validée', color: '#10b981', bg: 'rgba(16,185,129,.12)' },
                        ATTACHMENT_UPLOADED: { label: 'Pièce Jointe Ajoutée', color: '#818cf8', bg: 'rgba(129,140,248,.12)' },
                        SATISFACTION_SUBMITTED: { label: 'Satisfaction Notée', color: '#f59e0b', bg: 'rgba(245,158,11,.12)' },
                        SLA_RECALCULATED: { label: 'SLA Recalculé', color: '#ec4899', bg: 'rgba(236,72,153,.12)' },
                      };
                      const cfg = actionConfig[action.action_type] || { label: action.action_type, color: '#94a3b8', bg: 'rgba(148,163,184,.1)' };

                      return (
                        <div key={action.id || idx} style={{ position: 'relative' }}>
                          {/* Dot on line */}
                          <div style={{
                            position: 'absolute', left: '-1.5rem', top: '5px',
                            width: '8px', height: '8px', borderRadius: '50%',
                            background: cfg.color,
                            boxShadow: `0 0 8px ${cfg.color}`,
                            border: '2px solid #080812',
                          }} />

                          <div style={{
                            padding: '.75rem 1rem', borderRadius: 12,
                            background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)',
                            display: 'flex', flexDirection: 'column', gap: '.4rem',
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '.5rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                                <span style={{
                                  fontSize: '.68rem', fontWeight: 700, padding: '2px 7px', borderRadius: 6,
                                  background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}30`
                                }}>
                                  {cfg.label}
                                </span>
                                <span style={{ fontSize: '.78rem', fontWeight: 600, color: '#e2e8f0' }}>
                                  {action.actor_name || 'Système'}
                                </span>
                                <span style={{ fontSize: '.68rem', color: 'rgba(255,255,255,.3)', textTransform: 'capitalize' }}>
                                  ({action.actor_role?.toLowerCase() || 'système'})
                                </span>
                              </div>
                              <span style={{ fontSize: '.68rem', color: 'rgba(255,255,255,.3)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                                <Clock size={11} />
                                {action.timestamp ? format(new Date(action.timestamp), 'dd/MM/yyyy HH:mm:ss') : '—'}
                              </span>
                            </div>

                            {action.comment && (
                              <div style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.7)', marginTop: '.2rem' }}>
                                {action.comment}
                              </div>
                            )}

                            {action.details && Object.keys(action.details).length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.4rem', marginTop: '.2rem' }}>
                                {Object.entries(action.details).map(([k, v]) => (
                                  <span key={k} style={{
                                    fontSize: '.65rem', padding: '1px 6px', borderRadius: 4,
                                    background: 'rgba(255,255,255,.04)', color: 'rgba(255,255,255,.45)',
                                    fontFamily: 'monospace'
                                  }}>
                                    {k}: <strong style={{ color: 'rgba(255,255,255,.7)' }}>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</strong>
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* Metadata Card */}
          <div className="td-glass" style={{ borderRadius: 20, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <h4 style={{ margin: 0, fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', letterSpacing: '.05em', textTransform: 'uppercase' }}>Ticket Info</h4>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>Category</div>
                <div style={{ fontSize: '.875rem', color: '#f1f5f9', fontWeight: 600 }}>{ticket.category}</div>
              </div>
              {ticket.subcategory && (
                <div>
                  <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>Subcategory</div>
                  <div style={{ fontSize: '.875rem', color: '#f1f5f9', fontWeight: 600 }}>{ticket.subcategory}</div>
                </div>
              )}
              <div>
                <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>Channel</div>
                <div style={{ fontSize: '.875rem', color: '#f1f5f9', fontWeight: 600 }}>{ticket.channel}</div>
              </div>
              {ticket.impact && (
                <div>
                  <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>ITIL Impact</div>
                  <div style={{ fontSize: '.875rem', color: '#c4b5fd', fontWeight: 600 }}>{ticket.impact}</div>
                </div>
              )}
              {ticket.urgency && (
                <div>
                  <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>ITIL Urgence</div>
                  <div style={{ fontSize: '.875rem', color: '#93c5fd', fontWeight: 600 }}>{ticket.urgency}</div>
                </div>
              )}
              {ticket.priority_source && (
                <div>
                  <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '.25rem' }}>Source Priorité</div>
                  <div style={{ fontSize: '.875rem', color: '#86efac', fontWeight: 600 }}>
                    {ticket.priority_source === 'itil_matrix' ? 'Matrice ITIL' : ticket.priority_source === 'ai' ? 'Classification IA' : 'Manuel'}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* CSAT Customer Satisfaction Card */}
          {(ticket.status === 'RESOLVED' || ticket.status === 'CLOSED') && (
            <div className="td-glass" style={{
              borderRadius: 20,
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              background: 'linear-gradient(135deg, rgba(234, 179, 8, 0.08) 0%, rgba(15, 15, 25, 0.85) 100%)',
              border: '1px solid rgba(234, 179, 8, 0.3)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                  <Star size={16} style={{ color: '#eab308' }} fill="#eab308" />
                  <h4 style={{ margin: 0, fontSize: '.75rem', fontWeight: 700, color: '#fef08a', letterSpacing: '.05em', textTransform: 'uppercase' }}>
                    Satisfaction Client (CSAT)
                  </h4>
                </div>
                {ticket.satisfaction_rating && (
                  <span style={{
                    fontSize: '.7rem',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: 'rgba(234,179,8,.15)',
                    color: '#facc15',
                    border: '1px solid rgba(234,179,8,.3)'
                  }}>
                    {ticket.satisfaction_rating >= 4 ? 'Avis Positif' : ticket.satisfaction_rating === 3 ? 'Neutre' : 'À améliorer'}
                  </span>
                )}
              </div>

              {ticket.satisfaction_rating ? (
                /* Already rated state */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star
                        key={s}
                        size={20}
                        fill={s <= ticket.satisfaction_rating! ? '#eab308' : 'none'}
                        color={s <= ticket.satisfaction_rating! ? '#eab308' : '#475569'}
                      />
                    ))}
                    <span style={{ marginLeft: '6px', fontSize: '.95rem', fontWeight: 800, color: '#fef08a' }}>
                      {ticket.satisfaction_rating} / 5
                    </span>
                  </div>
                  {ticket.satisfaction_comment && (
                    <div style={{
                      padding: '.65rem .85rem',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,.03)',
                      border: '1px solid rgba(255,255,255,.06)',
                      fontSize: '.82rem',
                      color: '#e2e8f0',
                      fontStyle: 'italic',
                      lineHeight: 1.5
                    }}>
                      &ldquo;{ticket.satisfaction_comment}&rdquo;
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', fontSize: '.68rem', color: 'rgba(255,255,255,.3)' }}>
                    <Clock size={11} />
                    <span>
                      {ticket.satisfaction_submitted_at
                        ? `Évalué le ${format(new Date(ticket.satisfaction_submitted_at), 'dd/MM/yyyy HH:mm')}`
                        : 'Avis enregistré'}
                    </span>
                  </div>
                </div>
              ) : (user?.id === ticket.user_id || user?.role === UserRole.ADMIN) ? (
                /* Interactive rating form */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '.85rem' }}>
                  <p style={{ margin: 0, fontSize: '.78rem', color: 'rgba(255,255,255,.6)', lineHeight: 1.4 }}>
                    Comment évaluez-vous la résolution de votre demande ?
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setCsatRating(s)}
                        onMouseEnter={() => setCsatHover(s)}
                        onMouseLeave={() => setCsatHover(0)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          transform: (csatHover || csatRating) >= s ? 'scale(1.15)' : 'scale(1)',
                          transition: 'transform 0.15s ease'
                        }}
                        aria-label={`${s} étoiles`}
                      >
                        <Star
                          size={24}
                          fill={s <= (csatHover || csatRating) ? '#eab308' : 'none'}
                          color={s <= (csatHover || csatRating) ? '#eab308' : '#64748b'}
                        />
                      </button>
                    ))}
                    {(csatHover || csatRating) > 0 && (
                      <span style={{ fontSize: '.8rem', fontWeight: 700, color: '#fef08a', marginLeft: '4px' }}>
                        {csatHover || csatRating}/5
                      </span>
                    )}
                  </div>
                  <textarea
                    rows={2}
                    maxLength={500}
                    placeholder="Commentaire ou retour d'expérience (optionnel)..."
                    value={csatComment}
                    onChange={(e) => setCsatComment(e.target.value)}
                    style={{
                      background: 'rgba(255,255,255,.04)',
                      border: '1px solid rgba(255,255,255,.1)',
                      borderRadius: 10,
                      padding: '.6rem .75rem',
                      color: '#f1f5f9',
                      fontSize: '.8rem',
                      resize: 'none',
                      outline: 'none',
                      fontFamily: 'inherit'
                    }}
                  />
                  {csatError && (
                    <div style={{ fontSize: '.75rem', color: '#f87171', padding: '4px 8px', borderRadius: 6, background: 'rgba(239,68,68,.1)' }}>
                      {csatError}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={handleSubmitCSAT}
                    disabled={csatRating === 0 || csatSubmitting}
                    style={{
                      padding: '.55rem 1rem',
                      borderRadius: 10,
                      border: 'none',
                      background: csatRating === 0 ? 'rgba(255,255,255,.05)' : 'linear-gradient(135deg, #eab308 0%, #ca8a04 100%)',
                      color: csatRating === 0 ? 'rgba(255,255,255,.25)' : '#0f172a',
                      fontWeight: 700,
                      fontSize: '.8rem',
                      cursor: csatRating === 0 || csatSubmitting ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '.5rem',
                      transition: 'all 0.2s'
                    }}
                  >
                    {csatSubmitting ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>Envoi en cours...</span>
                      </>
                    ) : (
                      <span>Envoyer mon évaluation</span>
                    )}
                  </button>
                </div>
              ) : (
                <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.35)', fontStyle: 'italic' }}>
                  En attente de l'évaluation du demandeur.
                </div>
              )}
            </div>
          )}

          {/* Assignment Card */}
          <div className="td-glass" style={{ borderRadius: 20, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <h4 style={{ margin: 0, fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', letterSpacing: '.05em', textTransform: 'uppercase' }}>Assignment</h4>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(255,255,255,.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,.2)' }}>
                {ticket.assigned_agent_id ? <User size={24} /> : <Shield size={24} />}
              </div>
              <div>
                <div style={{ fontSize: '.875rem', fontWeight: 700, color: ticket.assigned_agent_id ? '#f1f5f9' : 'rgba(255,255,255,.3)' }}>
                  {ticket.assigned_agent_id ? "Agent Assigned" : "Unassigned"}
                </div>
                <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.3)' }}>{ticket.assigned_agent_id || "Awaiting routing"}</div>
              </div>
            </div>
            
            {ticket.assigned_agent_id && (
               <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
                 <SLABadge status={ticket.sla_status} deadline={ticket.sla_deadline} />
                 {ticket.sla_deadline && (
                   <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)' }}>
                     Échéance : {format(new Date(ticket.sla_deadline), 'dd/MM HH:mm')}
                   </span>
                 )}
               </div>
            )}
          </div>

          {/* AI Insights Sidebar */}
          <div style={{ background: 'linear-gradient(180deg,rgba(139,92,246,.1) 0%,transparent 100%)', borderRadius: 20, padding: '1.5rem', border: '1px solid rgba(139,92,246,.15)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '1rem' }}>
              <Zap size={16} style={{ color: '#8b5cf6' }} />
              <span style={{ fontSize: '.75rem', fontWeight: 700, color: '#f1f5f9', letterSpacing: '.05em', textTransform: 'uppercase' }}>AI Insights</span>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {[
                { label: 'Complexity', val: 'Low', color: '#34d399', icon: <Activity size={12} /> },
                { label: 'Priority Rec', val: ticket.priority, color: prio.color, icon: <AlertTriangle size={12} /> },
                { label: 'Sentiment', val: 'Neutral', color: '#60a5fa', icon: <Award size={12} /> },
              ].map((ins, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', color: 'rgba(255,255,255,.3)' }}>
                    {ins.icon}
                    <span style={{ fontSize: '.75rem' }}>{ins.label}</span>
                  </div>
                  <span style={{ fontSize: '.75rem', fontWeight: 700, color: ins.color }}>{ins.val}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* Agent Copilot Drawer */}
      <AgentCopilotDrawer
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        ticketId={ticket.id}
        onInsertSnippet={(snippet) => {
          setCommentText((prev) => (prev ? `${prev}\n\n${snippet}` : snippet));
        }}
      />
    </div>
  );
};

export default TicketDetails;