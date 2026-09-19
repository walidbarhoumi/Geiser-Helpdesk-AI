import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Upload, X, Loader2, Zap, Brain,
  Target, AlertTriangle, Cpu, Sparkles, CheckCircle2,
  Tag, ShieldCheck
} from 'lucide-react';
import { TicketPriority, TicketChannel, ImpactLevel, UrgencyLevel, PrioritySource, type TicketClassificationResult } from '../../types';
import api from '../../api/axios';
import toast from 'react-hot-toast';

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
    .tc-ai-card { transition: all .3s ease; }
    .tc-ai-card:hover { transform: translateY(-2px); border-color: rgba(139,92,246,.4) !important; }
    .tc-drop-zone { transition:all .25s; cursor:pointer; }
    .tc-drop-zone:hover { border-color:rgba(139,92,246,.5) !important; background:rgba(139,92,246,.06) !important; }
    .tc-file-item { transition:all .2s; }
    .tc-file-item:hover { background:rgba(139,92,246,.1) !important; }
    .tc-ai-btn {
      background: linear-gradient(135deg, rgba(139,92,246,.3) 0%, rgba(236,72,153,.25) 100%);
      border: 1px solid rgba(139,92,246,.45);
      color: #e9d5ff;
      transition: all .2s;
      cursor: pointer;
    }
    .tc-ai-btn:hover:not(:disabled) {
      background: linear-gradient(135deg, rgba(139,92,246,.5) 0%, rgba(236,72,153,.4) 100%);
      transform: translateY(-1px);
      box-shadow: 0 4px 16px rgba(139,92,246,.3);
    }
    .tc-ai-btn:disabled {
      opacity: .55;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(s);
};

// Official GEISER ITSM Taxonomy
const GEISER_TAXONOMY: Record<string, string[]> = {
  'Infrastructure & Réseau': [
    'VPN & Accès Distant',
    'Connexion Wi-Fi / Filaire',
    'Serveurs & Cloud',
  ],
  'Authentification & Accès': [
    'Réinitialisation Mot de passe',
    'Double Facteur (2FA)',
    'Déverrouillage de Compte',
  ],
  'Matériel & Poste de Travail': [
    'PC Portable / Fixe',
    'Imprimante & Scanner',
    'Écran & Périphériques',
  ],
  'Logiciels & Applications': [
    'Suite Office / Messagerie',
    'ERP & Outils Métier',
    'Installation & Mise à jour',
  ],
  'Sécurité IT': [
    'Email Suspect / Phishing',
    'Alerte Antivirus',
    'Incident de Sécurité (ISO 27001)',
  ],
  'Support Général': [
    'Assistance Utilisateur',
    'Autre Demande',
  ],
};

const priorityMeta: Record<string, { color: string; glow: string; label: string }> = {
  LOW:      { color: '#34d399', glow: 'rgba(52,211,153,.25)', label: 'Faible' },
  MEDIUM:   { color: '#60a5fa', glow: 'rgba(96,165,250,.28)', label: 'Moyenne' },
  HIGH:     { color: '#fb923c', glow: 'rgba(251,146,60,.3)', label: 'Élevée' },
  URGENT:   { color: '#f87171', glow: 'rgba(239,68,68,.35)', label: 'Urgente' },
};

// ITIL Priority Matrix (Impact × Urgence)
const ITIL_MATRIX: Record<string, Record<string, TicketPriority>> = {
  HIGH: { HIGH: TicketPriority.URGENT, MEDIUM: TicketPriority.URGENT, LOW: TicketPriority.HIGH },
  MEDIUM: { HIGH: TicketPriority.URGENT, MEDIUM: TicketPriority.HIGH, LOW: TicketPriority.MEDIUM },
  LOW: { HIGH: TicketPriority.HIGH, MEDIUM: TicketPriority.MEDIUM, LOW: TicketPriority.LOW },
};

const impactMeta: Record<string, { label: string; desc: string }> = {
  LOW:    { label: 'Faible', desc: '1 utilisateur ou impact limité' },
  MEDIUM: { label: 'Moyen', desc: 'Plusieurs utilisateurs / service partiel' },
  HIGH:   { label: 'Élevé', desc: 'Service critique / impact majeur' },
};

const urgencyMeta: Record<string, { label: string; desc: string }> = {
  LOW:    { label: 'Faible', desc: 'Peut attendre, contournement possible' },
  MEDIUM: { label: 'Moyenne', desc: 'Traitement prochainement requis' },
  HIGH:   { label: 'Élevée', desc: 'Intervention immédiate requise' },
};

/* ─── MAIN ────────────────────────────────────────────────── */
const TicketCreate: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState<File[]>([]);

  const [formData, setFormData] = useState({
    subject: '',
    description: '',
    category: 'Infrastructure & Réseau',
    subcategory: 'VPN & Accès Distant',
    impact: ImpactLevel.MEDIUM as ImpactLevel,
    urgency: UrgencyLevel.MEDIUM as UrgencyLevel,
    priority: TicketPriority.HIGH as TicketPriority,
    priority_source: PrioritySource.ITIL_MATRIX as PrioritySource,
    channel: TicketChannel.WEB as TicketChannel,
  });

  // Track manual modifications vs AI suggestions
  const [manuallyModified, setManuallyModified] = useState({
    category: false,
    subcategory: false,
    priority: false,
  });

  // AI Classification state
  const [aiResult, setAiResult] = useState<TicketClassificationResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiStatus, setAiStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [aiErrorMessage, setAiErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    injectStyles();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleCategorySelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newCat = e.target.value;
    const allowedSubs = GEISER_TAXONOMY[newCat] || ['Assistance Utilisateur'];
    setManuallyModified(prev => ({ ...prev, category: true }));
    setFormData(prev => ({
      ...prev,
      category: newCat,
      subcategory: allowedSubs.includes(prev.subcategory) ? prev.subcategory : allowedSubs[0],
    }));
  };

  const handleSubcategoryChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setManuallyModified(prev => ({ ...prev, subcategory: true }));
    setFormData(prev => ({ ...prev, subcategory: e.target.value }));
  };

  const handlePrioritySelect = (p: TicketPriority) => {
    setManuallyModified(prev => ({ ...prev, priority: true }));
    setFormData(prev => ({
      ...prev,
      priority: p,
      priority_source: PrioritySource.MANUAL,
    }));
  };

  const handleImpactChange = (impact: ImpactLevel) => {
    const calculatedPriority = ITIL_MATRIX[impact]?.[formData.urgency] || formData.priority;
    setFormData(prev => ({
      ...prev,
      impact,
      priority: calculatedPriority,
      priority_source: PrioritySource.ITIL_MATRIX,
    }));
  };

  const handleUrgencyChange = (urgency: UrgencyLevel) => {
    const calculatedPriority = ITIL_MATRIX[formData.impact]?.[urgency] || formData.priority;
    setFormData(prev => ({
      ...prev,
      urgency,
      priority: calculatedPriority,
      priority_source: PrioritySource.ITIL_MATRIX,
    }));
  };

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
  };

  // AI Classification execution
  const handleClassify = async (silent: boolean = false) => {
    const sub = formData.subject.trim();
    const desc = formData.description.trim();

    if (sub.length < 5 || desc.length < 20) {
      if (!silent) {
        toast.error("Veuillez saisir au moins 5 caractères pour le sujet et 20 caractères pour la description.");
      }
      return;
    }

    setAiLoading(true);
    setAiStatus('loading');
    setAiErrorMessage(null);

    try {
      const res = await api.post<TicketClassificationResult>('/ai/classify-ticket', {
        subject: sub,
        description: desc,
      });

      const result = res.data;
      setAiResult(result);
      setAiStatus('success');

      // Pre-fill ONLY fields the user hasn't manually modified
      setFormData(prev => ({
        ...prev,
        category: manuallyModified.category ? prev.category : result.category,
        subcategory: manuallyModified.subcategory ? prev.subcategory : result.subcategory,
        priority: manuallyModified.priority ? prev.priority : result.priority,
        priority_source: manuallyModified.priority ? prev.priority_source : PrioritySource.AI,
      }));

      if (!silent) {
        toast.success("Classification IA effectuée avec succès !");
      }
    } catch (err: any) {
      console.error("AI classification error:", err);
      setAiStatus('error');
      const msg = "Analyse IA indisponible. Vous pouvez continuer à créer le ticket manuellement.";
      setAiErrorMessage(msg);
      if (!silent) {
        toast.error(msg);
      }
    } finally {
      setAiLoading(false);
    }
  };

  // Debounced auto-trigger: runs after 800ms when user pauses typing
  useEffect(() => {
    const sub = formData.subject.trim();
    const desc = formData.description.trim();

    if (sub.length < 5 || desc.length < 20) {
      return;
    }

    const timer = setTimeout(() => {
      if (!aiLoading) {
        handleClassify(true);
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [formData.subject, formData.description]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload = {
      ...formData,
      keywords: aiResult?.tags || [],
    };

    try {
      const res = await api.post('/tickets/create', payload);
      const ticketId = res.data?.id;

      if (files.length > 0 && ticketId) {
        for (const file of files) {
          const fd = new FormData();
          fd.append('file', file);
          try {
            await api.post(`/tickets/${ticketId}/attachments`, fd, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });
          } catch {
            /* silent fallback */
          }
        }
      }
      toast.success("Ticket créé avec succès !");
      navigate('/tickets');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Échec de la soumission du ticket. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  };

  const currentAvailableSubcategories = GEISER_TAXONOMY[formData.category] || ['Assistance Utilisateur'];

  return (
    <div style={{ fontFamily: "'DM Sans',sans-serif", display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '.5rem',
          color: 'rgba(255,255,255,.32)', fontWeight: 600, fontSize: '.875rem',
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: "'DM Sans',sans-serif", width: 'fit-content', transition: 'color .15s'
        }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = '#c4b5fd')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,.32)')}
      >
        <ArrowLeft size={16} /> Retour aux Tickets
      </button>

      {/* Split layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.35fr)', gap: '2rem', alignItems: 'start' }}>

        {/* ── LEFT PANEL : DYNAMIC AI INTELLIGENCE ──────────────── */}
        <div style={{
          position: 'relative', borderRadius: 24, overflow: 'hidden',
          background: 'linear-gradient(160deg,rgba(18,8,42,.97) 0%,rgba(10,10,22,.97) 100%)',
          border: '1px solid rgba(139,92,246,.25)', padding: '2rem',
          display: 'flex', flexDirection: 'column', gap: '1.5rem',
          animation: 'tc-in-r .6s ease both'
        }}>
          {/* Ambient Glows */}
          <div style={{ position: 'absolute', top: -60, right: -50, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle,rgba(139,92,246,.22) 0%,transparent 70%)', pointerEvents: 'none', animation: 'tc-float 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', bottom: 60, left: -40, width: 150, height: 150, borderRadius: '50%', background: 'radial-gradient(circle,rgba(236,72,153,.12) 0%,transparent 70%)', pointerEvents: 'none', animation: 'tc-float 8s ease-in-out infinite' }} />

          {/* Label & Classifier Trigger */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#8b5cf6', animation: 'tc-pulse 2s infinite' }} />
              <span style={{ fontSize: '.68rem', fontWeight: 700, color: 'rgba(139,92,246,.85)', letterSpacing: '.1em', textTransform: 'uppercase' }}>
                Classification IA en Temps Réel
              </span>
            </div>

            {/* Manual Button Trigger */}
            <button
              type="button"
              onClick={() => handleClassify(false)}
              disabled={aiLoading}
              className="tc-ai-btn"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '.4rem',
                padding: '.45rem .85rem', borderRadius: 10,
                fontSize: '.75rem', fontWeight: 700,
              }}
            >
              {aiLoading ? (
                <>
                  <Loader2 size={13} style={{ animation: 'tc-spin 1s linear infinite' }} />
                  <span>Analyse...</span>
                </>
              ) : aiStatus === 'success' ? (
                <>
                  <CheckCircle2 size={13} />
                  <span>Classifié (Relancer)</span>
                </>
              ) : (
                <>
                  <Sparkles size={13} />
                  <span>Classifier avec l'IA</span>
                </>
              )}
            </button>
          </div>

          {/* Heading */}
          <div>
            <h1 style={{ fontFamily: "'DM Serif Display',serif", fontSize: 'clamp(1.5rem,2.2vw,2rem)', color: '#f1f5f9', lineHeight: 1.2, letterSpacing: '-0.02em', margin: '0 0 .65rem' }}>
              Assistance{' '}
              <span style={{ fontStyle: 'italic', background: 'linear-gradient(135deg,#a78bfa,#ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                intelligente
              </span>
              {' '}GEISER.
            </h1>
            <p style={{ color: 'rgba(255,255,255,.45)', fontSize: '.84rem', lineHeight: 1.55, margin: 0 }}>
              Saisissez le sujet et la description : l'IA classifie la panne, évalue la criticité et propose les tags en temps réel.
            </p>
          </div>

          {/* Fallback Warning if AI Error */}
          {aiStatus === 'error' && (
            <div style={{
              padding: '.85rem 1rem', borderRadius: 12,
              background: 'rgba(245,158,11,.1)', border: '1px solid rgba(245,158,11,.25)',
              color: '#fbbf24', fontSize: '.78rem', lineHeight: 1.5, display: 'flex', gap: '.6rem', alignItems: 'flex-start'
            }}>
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Analyse IA indisponible.</strong>
                <p style={{ margin: '2px 0 0', opacity: .9 }}>{aiErrorMessage || "Vous pouvez continuer à créer le ticket manuellement."}</p>
              </div>
            </div>
          )}

          {/* Dynamic AI Results Panel */}
          {aiResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.75rem' }}>
              {/* Category & Subcategory Card */}
              <div className="tc-ai-card" style={{
                padding: '.9rem 1.1rem', borderRadius: 14,
                background: 'rgba(139,92,246,.08)', border: '1px solid rgba(139,92,246,.25)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', color: '#c4b5fd', fontSize: '.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em' }}>
                    <Brain size={14} /> Classification IA
                  </div>
                  <span style={{
                    fontSize: '.68rem', fontWeight: 800, padding: '.2rem .55rem', borderRadius: 8,
                    background: 'rgba(139,92,246,.2)', color: '#d8b4fe', border: '1px solid rgba(139,92,246,.3)'
                  }}>
                    Confiance {Math.round(aiResult.confidence * 100)}%
                  </span>
                </div>
                <div style={{ fontSize: '.95rem', fontWeight: 700, color: '#fff', marginBottom: '.2rem' }}>
                  {aiResult.category}
                </div>
                <div style={{ fontSize: '.8rem', color: 'rgba(255,255,255,.6)' }}>
                  Sous-catégorie : <strong style={{ color: '#e2e8f0' }}>{aiResult.subcategory}</strong>
                </div>
              </div>

              {/* Priority & Tags Card */}
              <div className="tc-ai-card" style={{
                padding: '.9rem 1.1rem', borderRadius: 14,
                background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', color: 'rgba(255,255,255,.6)', fontSize: '.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em' }}>
                    <Target size={14} /> Priorité suggérée
                  </div>
                  <span style={{
                    fontSize: '.72rem', fontWeight: 800, padding: '.25rem .65rem', borderRadius: 8,
                    background: priorityMeta[aiResult.priority]?.glow || 'rgba(96,165,250,.2)',
                    color: priorityMeta[aiResult.priority]?.color || '#60a5fa',
                    border: `1px solid ${priorityMeta[aiResult.priority]?.color || '#60a5fa'}`
                  }}>
                    {aiResult.priority}
                  </span>
                </div>

                {/* Tags */}
                {aiResult.tags && aiResult.tags.length > 0 && (
                  <div style={{ marginTop: '.6rem' }}>
                    <div style={{ fontSize: '.68rem', fontWeight: 600, color: 'rgba(255,255,255,.4)', marginBottom: '.35rem', display: 'flex', alignItems: 'center', gap: '.3rem' }}>
                      <Tag size={11} /> Mots-clés / Tags :
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.35rem' }}>
                      {aiResult.tags.map((t, idx) => (
                        <span key={idx} style={{
                          fontSize: '.7rem', fontWeight: 600, padding: '.2rem .5rem', borderRadius: 6,
                          background: 'rgba(139,92,246,.12)', color: '#c4b5fd', border: '1px solid rgba(139,92,246,.25)'
                        }}>
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Reasoning Card */}
              <div className="tc-ai-card" style={{
                padding: '.85rem 1.1rem', borderRadius: 14,
                background: 'rgba(52,211,153,.05)', border: '1px solid rgba(52,211,153,.2)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', color: '#34d399', fontSize: '.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.35rem' }}>
                  <ShieldCheck size={13} /> Raisonnement Technique
                </div>
                <p style={{ fontSize: '.78rem', color: 'rgba(255,255,255,.65)', lineHeight: 1.5, margin: 0 }}>
                  {aiResult.reasoning}
                </p>
              </div>
            </div>
          ) : (
            /* Standby / Placeholder info */
            <div style={{
              padding: '1.25rem', borderRadius: 16,
              background: 'rgba(255,255,255,.02)', border: '1px dashed rgba(255,255,255,.1)',
              display: 'flex', flexDirection: 'column', gap: '.75rem', alignItems: 'center', textAlign: 'center'
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa'
              }}>
                <Cpu size={20} />
              </div>
              <div>
                <p style={{ fontSize: '.84rem', fontWeight: 600, color: 'rgba(255,255,255,.7)', margin: '0 0 .25rem' }}>
                  En attente de description
                </p>
                <p style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.35)', margin: 0, lineHeight: 1.45 }}>
                  Remplissez au moins 5 caractères pour le sujet et 20 caractères pour la description pour déclencher la classification automatique.
                </p>
              </div>
            </div>
          )}

          {/* SLA & Taxonomie Info */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.75rem 1rem', borderRadius: 10, background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)' }}>
            <span style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)' }}>Taxonomie GEISER</span>
            <span style={{ fontSize: '.75rem', fontWeight: 700, color: '#a78bfa' }}>6 Catégories ITSM</span>
          </div>
        </div>

        {/* ── RIGHT PANEL : FORM ─────────────────────────────── */}
        <div style={{
          borderRadius: 24, background: 'rgba(15,12,28,.88)',
          border: '1px solid rgba(255,255,255,.09)', backdropFilter: 'blur(24px)',
          padding: '2rem', boxShadow: '0 32px 64px rgba(0,0,0,.4)',
          animation: 'tc-in-l .6s ease both'
        }}>
          {/* Header */}
          <div style={{ marginBottom: '1.75rem' }}>
            <div style={{
              width: 44, height: 44, borderRadius: 13,
              background: 'rgba(139,92,246,.12)', border: '1px solid rgba(139,92,246,.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '.875rem'
            }}>
              <Zap size={20} style={{ color: '#a78bfa' }} />
            </div>
            <h2 style={{ fontFamily: "'DM Serif Display',serif", fontSize: '1.5rem', color: '#f1f5f9', margin: '0 0 .35rem', letterSpacing: '-0.02em' }}>
              Nouveau Ticket de Support
            </h2>
            <p style={{ fontSize: '.875rem', color: 'rgba(255,255,255,.32)', margin: 0 }}>
              L'IA préremplit les champs automatiquement. Vous gardez la main pour ajuster vos préférences.
            </p>
          </div>

          {/* Form Error */}
          {error && (
            <div style={{
              marginBottom: '1.25rem', padding: '.875rem 1rem',
              background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)',
              borderRadius: 10, color: '#f87171', fontSize: '.875rem', fontWeight: 600
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Subject */}
            <Field label="Sujet du problème" required hint="Résumez en quelques mots votre panne ou votre besoin.">
              <input
                className="tc-input"
                type="text"
                name="subject"
                required
                placeholder="Ex: Impossibilité de me connecter au VPN depuis ce matin..."
                value={formData.subject}
                onChange={handleChange}
              />
            </Field>

            {/* Description */}
            <Field label="Description détaillée" required hint="Indiquez le contexte, les messages d'erreur et l'impact sur votre travail.">
              <textarea
                className="tc-input"
                name="description"
                required
                rows={5}
                placeholder="Ex: Lors de la connexion à Cisco AnyConnect, le message 'Login failed: certificate invalid' apparaît. Bloquant pour mon télétravail..."
                value={formData.description}
                onChange={handleChange}
              />
            </Field>

            {/* Category + Channel */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '1rem' }}>
              <Field
                label="Catégorie"
                badge={
                  aiResult && !manuallyModified.category ? (
                    <span style={{ fontSize: '.65rem', color: '#c4b5fd', background: 'rgba(139,92,246,.2)', padding: '1px 6px', borderRadius: 6 }}>
                      ✨ IA
                    </span>
                  ) : manuallyModified.category ? (
                    <span style={{ fontSize: '.65rem', color: '#94a3b8', background: 'rgba(255,255,255,.08)', padding: '1px 6px', borderRadius: 6 }}>
                      👤 Manuel
                    </span>
                  ) : null
                }
              >
                <select
                  className="tc-input"
                  name="category"
                  value={formData.category}
                  onChange={handleCategorySelect}
                  style={{ cursor: 'pointer' }}
                >
                  {Object.keys(GEISER_TAXONOMY).map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>

              <Field label="Canal">
                <select
                  className="tc-input"
                  name="channel"
                  value={formData.channel}
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                >
                  {Object.values(TicketChannel).map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>
            </div>

            {/* Sub-category */}
            <Field
              label="Sous-catégorie"
              badge={
                aiResult && !manuallyModified.subcategory ? (
                  <span style={{ fontSize: '.65rem', color: '#c4b5fd', background: 'rgba(139,92,246,.2)', padding: '1px 6px', borderRadius: 6 }}>
                    ✨ IA
                  </span>
                ) : manuallyModified.subcategory ? (
                  <span style={{ fontSize: '.65rem', color: '#94a3b8', background: 'rgba(255,255,255,.08)', padding: '1px 6px', borderRadius: 6 }}>
                    👤 Manuel
                  </span>
                ) : null
              }
              hint="Précision technique aidant au routage vers le bon technicien."
            >
              <div style={{ display: 'flex', gap: '.5rem' }}>
                <select
                  className="tc-input"
                  name="subcategory"
                  value={formData.subcategory}
                  onChange={handleSubcategoryChange}
                  style={{ cursor: 'pointer' }}
                >
                  {currentAvailableSubcategories.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </Field>

            {/* ITIL Matrix: Impact & Urgency */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              {/* Impact */}
              <Field
                label="Impact ITIL (Périmètre)"
                hint="Étendue de l'incident sur l'activité ou les utilisateurs"
              >
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '.4rem' }}>
                  {[ImpactLevel.LOW, ImpactLevel.MEDIUM, ImpactLevel.HIGH].map(lvl => {
                    const active = formData.impact === lvl;
                    const meta = impactMeta[lvl];
                    return (
                      <button
                        key={lvl}
                        type="button"
                        className="tc-pri-btn"
                        onClick={() => handleImpactChange(lvl)}
                        title={meta.desc}
                        style={{
                          background: active ? 'rgba(139,92,246,.2)' : 'rgba(255,255,255,.03)',
                          borderColor: active ? '#a78bfa' : 'rgba(255,255,255,.1)',
                          color: active ? '#e9d5ff' : 'rgba(255,255,255,.45)',
                          boxShadow: active ? '0 0 12px rgba(139,92,246,.25)' : 'none',
                          padding: '.5rem .25rem',
                          textAlign: 'center',
                          fontSize: '.8rem',
                          lineHeight: 1.2
                        }}
                      >
                        <div style={{ fontWeight: 600 }}>{meta.label}</div>
                        <div style={{ fontSize: '.65rem', opacity: 0.7, marginTop: 2 }}>{lvl}</div>
                      </button>
                    );
                  })}
                </div>
              </Field>

              {/* Urgency */}
              <Field
                label="Urgence ITIL (Délai)"
                hint="Rapidité requise pour la résolution de la demande"
              >
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '.4rem' }}>
                  {[UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH].map(lvl => {
                    const active = formData.urgency === lvl;
                    const meta = urgencyMeta[lvl];
                    return (
                      <button
                        key={lvl}
                        type="button"
                        className="tc-pri-btn"
                        onClick={() => handleUrgencyChange(lvl)}
                        title={meta.desc}
                        style={{
                          background: active ? 'rgba(59,130,246,.2)' : 'rgba(255,255,255,.03)',
                          borderColor: active ? '#60a5fa' : 'rgba(255,255,255,.1)',
                          color: active ? '#bfdbfe' : 'rgba(255,255,255,.45)',
                          boxShadow: active ? '0 0 12px rgba(59,130,246,.25)' : 'none',
                          padding: '.5rem .25rem',
                          textAlign: 'center',
                          fontSize: '.8rem',
                          lineHeight: 1.2
                        }}
                      >
                        <div style={{ fontWeight: 600 }}>{meta.label}</div>
                        <div style={{ fontSize: '.65rem', opacity: 0.7, marginTop: 2 }}>{lvl}</div>
                      </button>
                    );
                  })}
                </div>
              </Field>
            </div>

            {/* Priority selector with ITIL matrix indication */}
            <Field
              label="Niveau de Priorité"
              hint="Déterminé automatiquement par la matrice ITIL (Impact × Urgence) ou modifiable manuellement."
              badge={
                formData.priority_source === PrioritySource.ITIL_MATRIX ? (
                  <span style={{ fontSize: '.65rem', color: '#6ee7b7', background: 'rgba(16,185,129,.15)', border: '1px solid rgba(16,185,129,.3)', padding: '1px 7px', borderRadius: 6 }}>
                    🎯 Matrice ITIL ({formData.impact} × {formData.urgency})
                  </span>
                ) : formData.priority_source === PrioritySource.AI ? (
                  <span style={{ fontSize: '.65rem', color: '#c4b5fd', background: 'rgba(139,92,246,.2)', padding: '1px 6px', borderRadius: 6 }}>
                    ✨ IA
                  </span>
                ) : (
                  <span style={{ fontSize: '.65rem', color: '#94a3b8', background: 'rgba(255,255,255,.08)', padding: '1px 6px', borderRadius: 6 }}>
                    👤 Forçage Manuel
                  </span>
                )
              }
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '.5rem' }}>
                {[TicketPriority.LOW, TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.URGENT].map(p => {
                  const meta = priorityMeta[p] ?? priorityMeta.MEDIUM;
                  const active = formData.priority === p;
                  return (
                    <button
                      key={p}
                      type="button"
                      className="tc-pri-btn"
                      onClick={() => handlePrioritySelect(p)}
                      style={{
                        background: active ? meta.glow : 'rgba(255,255,255,.03)',
                        borderColor: active ? meta.color : 'rgba(255,255,255,.1)',
                        color: active ? meta.color : 'rgba(255,255,255,.38)',
                        boxShadow: active ? `0 0 14px ${meta.glow}` : 'none'
                      }}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </Field>

            {/* Attachments */}
            <Field label="Pièces Jointes (optionnel)">
              <div
                className="tc-drop-zone"
                onClick={() => document.getElementById('tc-file')?.click()}
                style={{
                  borderRadius: 14, border: '1.5px dashed rgba(255,255,255,.14)',
                  padding: '1.5rem', display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: '.5rem',
                  background: 'rgba(255,255,255,.02)'
                }}
              >
                <div style={{
                  width: 38, height: 38, borderRadius: 10,
                  background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Upload size={16} style={{ color: '#a78bfa' }} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontSize: '.8rem', fontWeight: 600, color: 'rgba(255,255,255,.5)', margin: '0 0 .2rem' }}>
                    Glissez-déposez ou cliquez pour ajouter un fichier
                  </p>
                  <p style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.25)', margin: 0 }}>
                    PNG, JPG, PDF jusqu'à 10 Mo
                  </p>
                </div>
                <input id="tc-file" type="file" multiple style={{ display: 'none' }} onChange={handleFiles} />
              </div>
              {files.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '.5rem', marginTop: '.75rem' }}>
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="tc-file-item"
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '.55rem .8rem', background: 'rgba(139,92,246,.08)',
                        border: '1px solid rgba(139,92,246,.18)', borderRadius: 10
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', overflow: 'hidden' }}>
                        <Upload size={13} style={{ color: '#a78bfa', flexShrink: 0 }} />
                        <span style={{
                          fontSize: '.72rem', fontWeight: 600, color: 'rgba(255,255,255,.6)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                        }}>
                          {f.name}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          padding: 0, color: 'rgba(255,255,255,.3)', flexShrink: 0,
                          display: 'flex', alignItems: 'center'
                        }}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Field>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '.875rem', paddingTop: '.5rem' }}>
              <button
                type="button"
                onClick={() => navigate(-1)}
                style={{
                  padding: '.875rem 1.5rem', borderRadius: 12,
                  background: 'rgba(255,255,255,.04)', border: '1.5px solid rgba(255,255,255,.1)',
                  color: 'rgba(255,255,255,.4)', fontWeight: 700, fontSize: '.9375rem',
                  cursor: 'pointer', fontFamily: "'DM Sans',sans-serif", transition: 'all .2s'
                }}
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={loading}
                className="tc-submit"
                style={{
                  flex: 1, padding: '.875rem 1.5rem', borderRadius: 12,
                  background: loading ? 'rgba(139,92,246,.3)' : 'linear-gradient(135deg,#7c3aed,#8b5cf6)',
                  color: loading ? 'rgba(255,255,255,.5)' : '#fff',
                  fontWeight: 700, fontSize: '.9375rem', border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: loading ? 'none' : '0 8px 24px rgba(139,92,246,.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  gap: '.5rem', transition: 'all .25s', fontFamily: "'DM Sans',sans-serif"
                }}
              >
                {loading ? (
                  <>
                    <Loader2 size={17} style={{ animation: 'tc-spin 1s linear infinite' }} />
                    <span>Création du ticket...</span>
                  </>
                ) : (
                  <>
                    <Zap size={17} />
                    <span>Soumettre le Ticket</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

/* ─── Field wrapper ───────────────────────────────────────── */
const Field: React.FC<{
  label: string;
  required?: boolean;
  hint?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}> = ({ label, required, hint, badge, children }) => (
  <div>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '.45rem' }}>
      <label style={{
        fontSize: '.72rem', fontWeight: 700,
        color: 'rgba(255,255,255,.38)', letterSpacing: '.06em', textTransform: 'uppercase'
      }}>
        {label} {required && <span style={{ color: '#f87171' }}>*</span>}
      </label>
      {badge}
    </div>
    {children}
    {hint && (
      <p style={{ marginTop: '.35rem', fontSize: '.72rem', color: 'rgba(255,255,255,.22)', lineHeight: 1.5 }}>
        {hint}
      </p>
    )}
  </div>
);

export default TicketCreate;