import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Clock, AlertTriangle, Shield, User,
  Bot, Sparkles, Loader2, CheckCircle2, XCircle,
  Activity, Zap, Paperclip, MessageSquare, Send,
  Cpu, Target, Award, Brain, Info, Check, Copy, RefreshCw
} from 'lucide-react';
import { type Ticket, type RoutingResult, TicketStatus, TicketPriority, UserRole } from '../../types';
import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import { format } from 'date-fns';

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
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  
  // AI States
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const [editableResponse, setEditableResponse] = useState('');
  
  const [isRouting, setIsRouting] = useState(false);
  const [routingResult, setRoutingResult] = useState<RoutingResult | null>(null);

  useEffect(() => { injectStyles(); }, []);

  const fetchTicket = async () => {
    try {
      const res = await api.get(`/tickets/${id}`);
      setTicket(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchTicket();
  }, [id]);

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

  const handleGenerateAiResponse = async () => {
    if (!id) return;
    setIsGenerating(true);
    try {
      const res = await api.post(`/ai/tickets/${id}/generate-response`);
      setAiResult(res.data);
      setEditableResponse(res.data.generated_response);
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendResponse = async () => {
    // Mock send - in real app, call /tickets/{id}/send-ai-response
    alert("Response sent to user via email!");
    setAiResult(null);
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
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '2rem', alignItems: 'start' }}>
        
        {/* Left Content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* AI Kopilot Section */}
          <div className="ai-smart-card" style={{ padding: '1.5rem' }}>
             <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem' }}>
                  <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(139,92,246,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa' }}>
                    <Brain size={22} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f1f5f9' }}>AI Smart Reply</h3>
                    <p style={{ margin: 0, fontSize: '.75rem', color: 'rgba(255,255,255,.4)' }}>Generate professional responses and solutions.</p>
                  </div>
                </div>
                {!aiResult && !isGenerating && (
                  <button onClick={handleGenerateAiResponse} className="td-auto-btn" style={{ padding: '.6rem 1.25rem', borderRadius: 12, fontSize: '.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                    <Sparkles size={16} /> Generate AI Response
                  </button>
                )}
             </div>

             {isGenerating && (
               <div style={{ padding: '2rem', textAlign: 'center' }}>
                 <Loader2 size={32} className="animate-spin" style={{ color: '#8b5cf6', margin: '0 auto 1rem', animation: 'td-spin 1s linear infinite' }} />
                 <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.5)' }}>Gemma3 is analyzing ticket intent and drafting response...</p>
                 <div className="ai-shimmer" style={{ height: 4, width: '100%', borderRadius: 2, marginTop: '1rem' }} />
               </div>
             )}

             {aiResult && (
               <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'td-in-up 0.4s ease both' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(139,92,246,0.1)', padding: '.75rem 1rem', borderRadius: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Target size={14} style={{ color: '#a78bfa' }} />
                      <span style={{ fontSize: '.75rem', fontWeight: 700, color: '#a78bfa' }}>INTENT: {aiResult.intent}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Award size={14} style={{ color: aiResult.confidence_score > 85 ? '#34d399' : '#fb923c' }} />
                      <span style={{ fontSize: '.75rem', fontWeight: 700, color: '#f1f5f9' }}>{aiResult.confidence_score}% Confidence</span>
                      <span style={{ fontSize: '.6rem', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: 4, color: 'rgba(255,255,255,0.4)' }}>{aiResult.match_quality}</span>
                    </div>
                  </div>

                  <textarea 
                    className="ai-input-area"
                    value={editableResponse}
                    onChange={(e) => setEditableResponse(e.target.value)}
                    placeholder="AI generated response..."
                  />

                  <div>
                    <div style={{ fontSize: '.7rem', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Info size={12} /> Tech Suggestions
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {aiResult.suggestions.map((s: string, i: number) => (
                        <div key={i} className="suggestion-chip" onClick={() => setEditableResponse(prev => prev + "\n\n💡 Suggestion: " + s)}>
                          <Zap size={12} /> {s}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '1.25rem' }}>
                    <button onClick={() => setAiResult(null)} className="td-action-btn" style={{ padding: '.6rem 1.25rem', borderRadius: 12, fontSize: '.875rem', fontWeight: 700 }}>
                      Discard
                    </button>
                    <button onClick={handleSendResponse} className="td-auto-btn" style={{ flex: 1, padding: '.6rem 1.25rem', borderRadius: 12, fontSize: '.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                      <Check size={18} /> Approve & Send Response
                    </button>
                  </div>
               </div>
             )}
          </div>

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
            
            {ticket.attachments && ticket.attachments.length > 0 && (
              <div>
                <h3 style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '1rem' }}>Attachments</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                  {ticket.attachments.map((at, i) => (
                    <a key={i} href={at} target="_blank" rel="noreferrer" style={{ display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.75rem 1rem', borderRadius: 12, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)', color: 'rgba(255,255,255,.6)', textDecoration: 'none', fontSize: '.8125rem', transition: 'all .2s' }}
                      onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(139,92,246,.4)'}
                      onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,.08)'}
                    >
                      <Paperclip size={16} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{at.split('/').pop()}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Activity / Messages (Mock for now) */}
          <div className="td-glass" style={{ borderRadius: 24, padding: '2rem' }}>
            <h3 style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.28)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '.5rem' }}>
              <MessageSquare size={14} /> Activity Stream
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(139,92,246,.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa', flexShrink: 0 }}>
                  <Bot size={16} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.25rem' }}>
                    <span style={{ fontSize: '.8125rem', fontWeight: 700, color: '#f1f5f9' }}>GEISER AI</span>
                    <span style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.2)' }}>{format(new Date(ticket.created_at), 'HH:mm')}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '.875rem', color: 'rgba(255,255,255,.5)', lineHeight: 1.5 }}>Ticket initialized and awaiting manual review or auto-routing triggers.</p>
                </div>
              </div>
              
              {/* Message Input */}
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', padding: '1rem', borderRadius: 16, background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)' }}>
                <input placeholder="Add a comment…" style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: '#f1f5f9', fontSize: '.875rem' }} />
                <button style={{ background: 'none', border: 'none', color: '#8b5cf6', cursor: 'pointer' }}><Send size={18} /></button>
              </div>
            </div>
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
            </div>
          </div>

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
               <div style={{ padding: '.75rem', borderRadius: 12, background: 'rgba(52,211,153,.05)', border: '1px solid rgba(52,211,153,.15)', display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                 <CheckCircle2 size={14} style={{ color: '#34d399' }} />
                 <span style={{ fontSize: '.75rem', color: '#34d399', fontWeight: 600 }}>SLA Active: 2h left</span>
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
    </div>
  );
};

export default TicketDetails;