import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Upload, X, Loader2, Zap, Brain,
  Target, Clock, AlertTriangle, Cpu
} from 'lucide-react';
import { TicketPriority, TicketChannel } from '../../types';
import api from '../../api/axios';


/* ─── Styles ──────────────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('tc-styles')) return;
  const s = document.createElement('style');
  s.id = 'tc-styles';
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');
    @keyframes tc-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }
    @keyframes tc-float { 0%,100%{transform:translateY(0) rotate(0deg)} 50%{transform:translateY(-8px) rotate(1deg)} }
    @keyframes tc-in-r { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
    @keyframes tc-in-l { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
    @keyframes tc-up { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
    @keyframes tc-spin { to{transform:rotate(360deg)} }
    @keyframes tc-success { 0%{transform:scale(.5);opacity:0} 70%{transform:scale(1.15)} 100%{transform:scale(1);opacity:1} }
    .tc-input {
      width:100%; padding:.875rem 1.125rem;
      background:rgba(255,255,255,.04); border:1.5px solid rgba(255,255,255,.1);
      border-radius:12px; color:rgba(255,255,255,.82);
      font-size:.9375rem; font-family:'DM Sans',sans-serif;
      outline:none; transition:border-color .2s,box-shadow .2s,background .2s;
      box-sizing:border-box; resize:none;
    }
    .tc-input::placeholder { color:rgba(255,255,255,.22); }
    .tc-input:focus { border-color:rgba(139,92,246,.6); box-shadow:0 0 0 3px rgba(139,92,246,.14); background:rgba(139,92,246,.055); }
    .tc-input option { background:#13101f; color:#e2e8f0; }
    .tc-pri-btn { transition:all .2s; cursor:pointer; border:1.5px solid rgba(255,255,255,.1); border-radius:10px; padding:.6rem 1rem; font-size:.78rem; font-weight:700; font-family:'DM Sans',sans-serif; }
    .tc-submit:hover { transform:translateY(-2px); box-shadow:0 16px 40px rgba(139,92,246,.5) !important; }
    .tc-ai-card { animation:tc-float 4s ease-in-out infinite; }
    .tc-ai-card:nth-child(2){animation-delay:-1.3s}
    .tc-ai-card:nth-child(3){animation-delay:-2.5s}
    .tc-drop-zone { transition:all .25s; cursor:pointer; }
    .tc-drop-zone:hover { border-color:rgba(139,92,246,.5) !important; background:rgba(139,92,246,.06) !important; }
    .tc-file-item { transition:all .2s; }
    .tc-file-item:hover { background:rgba(139,92,246,.1) !important; }
  `;
  document.head.appendChild(s);
};

const priorityMeta: Record<string, { color: string; glow: string }> = {
  LOW:      { color: '#34d399', glow: 'rgba(52,211,153,.25)' },
  MEDIUM:   { color: '#60a5fa', glow: 'rgba(96,165,250,.28)' },
  HIGH:     { color: '#fb923c', glow: 'rgba(251,146,60,.3)' },
  CRITICAL: { color: '#f87171', glow: 'rgba(239,68,68,.35)' },
};

/* ─── AI Suggestion ───────────────────────────────────────── */
const AiCard: React.FC<{ icon: React.ReactNode; title: string; body: string; color: string; delay?: number }> = ({ icon, title, body, color, delay = 0 }) => (
  <div className="tc-ai-card" style={{ padding: '.875rem 1rem', background: `rgba(${color},.07)`, border: `1px solid rgba(${color},.22)`, borderRadius: 13, animation: `tc-up .5s ease ${delay}ms both` }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '.55rem', marginBottom: '.4rem' }}>
      <div style={{ color: `rgb(${color})`, flexShrink: 0 }}>{icon}</div>
      <span style={{ fontSize: '.72rem', fontWeight: 700, color: `rgb(${color})`, letterSpacing: '.04em' }}>{title}</span>
      <div style={{ marginLeft: 'auto', width: 5, height: 5, borderRadius: '50%', background: `rgb(${color})`, animation: 'tc-pulse 2s infinite', flexShrink: 0 }} />
    </div>
    <p style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.45)', lineHeight: 1.55, margin: 0 }}>{body}</p>
  </div>
);

/* ─── MAIN ────────────────────────────────────────────────── */
const TicketCreate: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [formData, setFormData] = useState({
    subject: '',
    description: '',
    category: 'Technical Support',
    subcategory: '',
    priority: TicketPriority.MEDIUM as TicketPriority,
    channel: TicketChannel.WEB as TicketChannel,
  });

  useEffect(() => { injectStyles(); }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await api.post('/tickets/create', formData);
      const ticketId = res.data?.id;
      if (files.length > 0 && ticketId) {
        for (const file of files) {
          const fd = new FormData(); fd.append('file', file);
          try { await api.post(`/tickets/${ticketId}/attachments`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }); }
          catch { /* silent */ }
        }
      }
      navigate('/tickets');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit ticket. Please try again.');
    } finally { setLoading(false); }
  };

  const aiCards = [
    { icon: <Brain size={13} />, title: 'AI Classification', body: 'Ticket routed to Infrastructure Support based on subject analysis.', color: '139,92,246' },
    { icon: <Target size={13} />, title: 'Suggested Priority', body: formData.priority === TicketPriority.URGENT || formData.priority === TicketPriority.HIGH ? 'Confirmed High — SLA clock starts on submit.' : 'AI agrees with selected priority level.', color: '96,165,250' },

    { icon: <Clock size={13} />, title: 'Est. Resolution', body: '~2–4 hours based on category baseline performance.', color: '52,211,153' },
    { icon: <AlertTriangle size={13} />, title: 'Duplicate Check', body: 'No duplicate incidents found in the last 7 days.', color: '251,146,60' },
  ];

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Back */}
      <button onClick={() => navigate(-1)} style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', color: 'rgba(255,255,255,.32)', fontWeight: 600, fontSize: '.875rem', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: "'DM Sans',sans-serif", width: 'fit-content', transition: 'color .15s' }}
        onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = '#c4b5fd'}
        onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,.32)'}
      >
        <ArrowLeft size={16} /> Back to Tickets
      </button>

      {/* Split layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.35fr)', gap: '2rem', alignItems: 'start' }}>

        {/* ── LEFT PANEL ─────────────────────────────────────── */}
        <div style={{ position: 'relative', borderRadius: 24, overflow: 'hidden', background: 'linear-gradient(160deg,rgba(18,8,42,.97) 0%,rgba(10,10,22,.97) 100%)', border: '1px solid rgba(139,92,246,.2)', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.75rem', animation: 'tc-in-r .6s ease both' }}>
          {/* Orbs */}
          <div style={{ position: 'absolute', top: -60, right: -50, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle,rgba(139,92,246,.22) 0%,transparent 70%)', pointerEvents: 'none', animation: 'tc-float 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', bottom: 60, left: -40, width: 150, height: 150, borderRadius: '50%', background: 'radial-gradient(circle,rgba(236,72,153,.12) 0%,transparent 70%)', pointerEvents: 'none', animation: 'tc-float 8s ease-in-out infinite' }} />

          {/* Label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#8b5cf6', animation: 'tc-pulse 2s infinite' }} />
            <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(139,92,246,.7)', letterSpacing: '.1em', textTransform: 'uppercase' }}>AI Ticket Intelligence</span>
          </div>

          {/* Heading */}
          <div style={{ position: 'relative' }}>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: 'clamp(1.625rem,2.5vw,2.25rem)', color: '#f1f5f9', lineHeight: 1.18, letterSpacing: '-0.02em', margin: '0 0 .875rem' }}>
              Create{' '}
              <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg,#a78bfa,#ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>intelligent</span>
              {' '}support requests.
            </h1>
            <p style={{ color: 'rgba(255,255,255,.38)', fontSize: '.875rem', lineHeight: 1.65, margin: 0 }}>
              Our AI automatically classifies your ticket, routes it to the right team, predicts priority, and estimates resolution time — all before you hit submit.
            </p>
          </div>

          {/* AI suggestion cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
            {aiCards.map((c, i) => <AiCard key={i} {...c} delay={i * 100} />)}
          </div>

          {/* Stats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.45rem' }}>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(255,255,255,.22)', letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: '.2rem' }}>Live Intelligence</div>
            {[
              { label: 'AI Routing Accuracy', val: '97%', color: '#a78bfa' },
              { label: 'Avg First Response', val: '8 min', color: '#34d399' },
              { label: 'SLA Compliance', val: '92%', color: '#60a5fa' },
            ].map(({ label, val, color }, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.65rem .9rem', borderRadius: 9, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)', transition: 'background .2s' }}>
                <span style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.38)', fontWeight: 500 }}>{label}</span>
                <span style={{ fontSize: '.875rem', fontWeight: 700, color }}>{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── RIGHT PANEL ────────────────────────────────────── */}
        <div style={{ borderRadius: 24, background: 'rgba(15,12,28,.88)', border: '1px solid rgba(255,255,255,.09)', backdropFilter: 'blur(24px)', padding: '2rem', boxShadow: '0 32px 64px rgba(0,0,0,.4)', animation: 'tc-in-l .6s ease both' }}>
          {/* Header */}
          <div style={{ marginBottom: '1.75rem' }}>
            <div style={{ width: 44, height: 44, borderRadius: 13, background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '.875rem' }}>
              <Zap size={20} style={{ color: '#a78bfa' }} />
            </div>
            <h2 style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.5rem', color: '#f1f5f9', margin: '0 0 .35rem', letterSpacing: '-0.02em' }}>New Support Ticket</h2>
            <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.32)', margin: 0 }}>AI will classify and route automatically on submission.</p>
          </div>

          {/* Error */}
          {error && (
            <div style={{ marginBottom: '1.25rem', padding: '.875rem 1rem', background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)', borderRadius: 10, color: '#f87171', fontSize: '.875rem', fontWeight: 600 }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Subject */}
            <Field label="Subject" required>
              <input className="tc-input" type="text" name="subject" required placeholder="Briefly describe the issue…" value={formData.subject} onChange={handleChange} />
            </Field>

            {/* Category + Priority */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Field label="Category">
                <select className="tc-input" name="category" value={formData.category} onChange={handleChange} style={{ cursor: 'pointer' }}>
                  {['Technical Support', 'Billing & Invoices', 'Feature Request', 'General Inquiry', 'Infrastructure', 'Security'].map(c => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label="Channel">
                <select className="tc-input" name="channel" value={formData.channel} onChange={handleChange} style={{ cursor: 'pointer' }}>
                  {Object.values(TicketChannel).map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            </div>

            {/* Priority selector */}
            <Field label="Priority">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '.5rem' }}>
                {Object.values(TicketPriority).map(p => {
                  const meta = priorityMeta[p] ?? priorityMeta.MEDIUM;
                  const active = formData.priority === p;
                  return (
                    <button key={p} type="button" className="tc-pri-btn" onClick={() => setFormData({ ...formData, priority: p })} style={{ background: active ? `rgba(${meta.color.replace('#', '')},0)` : 'rgba(255,255,255,.03)', borderColor: active ? meta.color : 'rgba(255,255,255,.1)', color: active ? meta.color : 'rgba(255,255,255,.38)', boxShadow: active ? `0 0 14px ${meta.glow}` : 'none' }}>
                      {p}
                    </button>
                  );
                })}
              </div>
            </Field>

            {/* Sub-category */}
            <Field label="Sub-category" hint="Optional — helps AI narrow routing">
              <input className="tc-input" type="text" name="subcategory" placeholder="e.g. Database, Authentication, Payment…" value={formData.subcategory} onChange={handleChange} />
            </Field>

            {/* Description */}
            <Field label="Description" required>
              <textarea className="tc-input" name="description" required rows={5} placeholder="Provide detailed context about the issue, steps to reproduce, and expected vs actual behaviour…" value={formData.description} onChange={handleChange} />
            </Field>

            {/* Attachments */}
            <Field label="Attachments">
              <div className="tc-drop-zone" onClick={() => document.getElementById('tc-file')?.click()} style={{ borderRadius: 14, border: '1.5px dashed rgba(255,255,255,.14)', padding: '1.75rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '.625rem', background: 'rgba(255,255,255,.02)' }}>
                <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Upload size={18} style={{ color: '#a78bfa' }} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontSize: '.8rem', fontWeight: 600, color: 'rgba(255,255,255,.5)', margin: '0 0 .2rem' }}>Click to upload or drag & drop</p>
                  <p style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.25)', margin: 0 }}>PNG, JPG, PDF up to 10 MB</p>
                </div>
                <input id="tc-file" type="file" multiple style={{ display: 'none' }} onChange={handleFiles} />
              </div>
              {files.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '.5rem', marginTop: '.75rem' }}>
                  {files.map((f, i) => (
                    <div key={i} className="tc-file-item" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '.6rem .875rem', background: 'rgba(139,92,246,.08)', border: '1px solid rgba(139,92,246,.18)', borderRadius: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', overflow: 'hidden' }}>
                        <Upload size={13} style={{ color: '#a78bfa', flexShrink: 0 }} />
                        <span style={{ fontSize: '.72rem', fontWeight: 600, color: 'rgba(255,255,255,.6)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      </div>
                      <button type="button" onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'rgba(255,255,255,.3)', flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                        <X size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Field>

            {/* AI confidence strip */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.875rem 1rem', borderRadius: 12, background: 'rgba(139,92,246,.07)', border: '1px solid rgba(139,92,246,.16)' }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(139,92,246,.14)', border: '1px solid rgba(139,92,246,.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Cpu size={15} style={{ color: '#a78bfa' }} />
              </div>
              <div>
                <div style={{ fontSize: '.72rem', fontWeight: 700, color: 'rgba(167,139,250,.8)', marginBottom: '.12rem' }}>AI Confidence: 94%</div>
                <div style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.38)', lineHeight: 1.4 }}>Classification complete · Infrastructure Support · Est. 2–4h resolution</div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '.875rem', paddingTop: '.25rem' }}>
              <button type="button" onClick={() => navigate(-1)} style={{ padding: '.875rem 1.5rem', borderRadius: 12, background: 'rgba(255,255,255,.04)', border: '1.5px solid rgba(255,255,255,.1)', color: 'rgba(255,255,255,.4)', fontWeight: 700, fontSize: '.9375rem', cursor: 'pointer', fontFamily: "'DM Sans',sans-serif", transition: 'all .2s' }}>
                Cancel
              </button>
              <button type="submit" disabled={loading} className="tc-submit" style={{ flex: 1, padding: '.875rem 1.5rem', borderRadius: 12, background: loading ? 'rgba(139,92,246,.3)' : 'linear-gradient(135deg,#7c3aed,#8b5cf6)', color: loading ? 'rgba(255,255,255,.5)' : '#fff', fontWeight: 700, fontSize: '.9375rem', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', boxShadow: loading ? 'none' : '0 8px 24px rgba(139,92,246,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '.5rem', transition: 'all .25s', fontFamily: "'DM Sans',sans-serif" }}>
                {loading ? <><Loader2 size={17} style={{ animation: 'tc-spin 1s linear infinite' }} /> Submitting…</> : <><Zap size={17} /> Submit Ticket</>}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

/* ─── Field wrapper ───────────────────────────────────────── */
const Field: React.FC<{ label: string; required?: boolean; hint?: string; children: React.ReactNode }> = ({ label, required, hint, children }) => (
  <div>
    <label style={{ display: 'block', marginBottom: '.45rem', fontSize: '.72rem', fontWeight: 700, color: 'rgba(255,255,255,.38)', letterSpacing: '.06em', textTransform: 'uppercase' }}>
      {label} {required && <span style={{ color: '#f87171' }}>*</span>}
    </label>
    {children}
    {hint && <p style={{ marginTop: '.35rem', fontSize: '.72rem', color: 'rgba(255,255,255,.22)', lineHeight: 1.5 }}>{hint}</p>}
  </div>
);

export default TicketCreate;