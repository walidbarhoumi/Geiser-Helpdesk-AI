import React, { useState, useEffect } from 'react';
import {
  Sparkles, X, FileText, Zap, BookOpen,
  RefreshCw, Check, Copy, ArrowRight, ShieldAlert,
  HelpCircle, AlertTriangle, Search
} from 'lucide-react';
import api from '../../api/axios';
import toast from 'react-hot-toast';
import {
  type ThreadSummary,
  type SuggestedAction,
  type InternalDocItem
} from '../../types';

interface AgentCopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  onInsertSnippet?: (text: string) => void;
}

export const AgentCopilotDrawer: React.FC<AgentCopilotDrawerProps> = ({
  isOpen,
  onClose,
  ticketId,
  onInsertSnippet,
}) => {
  const [activeTab, setActiveTab] = useState<'summary' | 'actions' | 'docs'>('summary');
  
  // Summary state
  const [summary, setSummary] = useState<ThreadSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Actions state
  const [actions, setActions] = useState<SuggestedAction[]>([]);
  const [loadingActions, setLoadingActions] = useState(false);

  // Docs state
  const [docs, setDocs] = useState<InternalDocItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDocCategory, setSelectedDocCategory] = useState<string>('all');
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);

  // Copied state indicator
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchSummary = async () => {
    setLoadingSummary(true);
    try {
      const res = await api.get<ThreadSummary>(`/ai/tickets/${ticketId}/summarize`);
      setSummary(res.data);
    } catch (err) {
      console.error('Error fetching summary:', err);
      toast.error('Impossible de charger le résumé du ticket.');
    } finally {
      setLoadingSummary(false);
    }
  };

  const fetchActions = async () => {
    setLoadingActions(true);
    try {
      const res = await api.get<SuggestedAction[]>(`/ai/tickets/${ticketId}/suggested-actions`);
      setActions(res.data);
    } catch (err) {
      console.error('Error fetching actions:', err);
      toast.error('Impossible de charger les actions suggérées.');
    } finally {
      setLoadingActions(false);
    }
  };

  const fetchDocs = async (query = '', cat = 'all') => {
    setLoadingDocs(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append('query', query.trim());
      if (cat !== 'all') params.append('category', cat);
      const res = await api.get<InternalDocItem[]>(`/ai/internal-docs/search?${params.toString()}`);
      setDocs(res.data);
    } catch (err) {
      console.error('Error fetching docs:', err);
      toast.error('Impossible de rechercher les documents internes.');
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    if (isOpen && ticketId) {
      fetchSummary();
      fetchActions();
      fetchDocs('', 'all');
    }
  }, [isOpen, ticketId]);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success('Texte copié dans le presse-papier !');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleInsert = (text: string) => {
    if (onInsertSnippet) {
      onInsertSnippet(text);
      toast.success('Snippet inséré dans votre réponse !');
    } else {
      handleCopy('inserted', text);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(5, 5, 10, 0.65)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          height: '100%',
          background: '#0e0e18',
          borderLeft: '1px solid rgba(139, 92, 246, 0.25)',
          boxShadow: '-10px 0 35px rgba(0, 0, 0, 0.6)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'slideInRight 0.25s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(15, 15, 25, 0.9) 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                boxShadow: '0 4px 12px rgba(139, 92, 246, 0.35)',
              }}
            >
              <Sparkles size={18} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
                Copilot Agent
                <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(139, 92, 246, 0.2)', color: '#c4b5fd', fontWeight: 600, border: '1px solid rgba(139, 92, 246, 0.3)' }}>
                  IA NIVEAU 2
                </span>
              </h2>
              <p style={{ margin: 0, fontSize: '0.75rem', color: 'rgba(255, 255, 255, 0.45)' }}>
                Assistance opérationnelle & conformité ISO 27001
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '6px',
              color: 'rgba(255, 255, 255, 0.6)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '4px',
            padding: '0.75rem 1.25rem',
            background: 'rgba(255, 255, 255, 0.02)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          }}
        >
          <button
            onClick={() => setActiveTab('summary')}
            style={{
              padding: '0.6rem 0.5rem',
              borderRadius: '8px',
              border: activeTab === 'summary' ? '1px solid rgba(139, 92, 246, 0.4)' : '1px solid transparent',
              background: activeTab === 'summary' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
              color: activeTab === 'summary' ? '#c4b5fd' : 'rgba(255, 255, 255, 0.5)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            <FileText size={14} />
            Résumé
          </button>
          <button
            onClick={() => setActiveTab('actions')}
            style={{
              padding: '0.6rem 0.5rem',
              borderRadius: '8px',
              border: activeTab === 'actions' ? '1px solid rgba(139, 92, 246, 0.4)' : '1px solid transparent',
              background: activeTab === 'actions' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
              color: activeTab === 'actions' ? '#c4b5fd' : 'rgba(255, 255, 255, 0.5)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            <Zap size={14} />
            Actions Conseillées
          </button>
          <button
            onClick={() => setActiveTab('docs')}
            style={{
              padding: '0.6rem 0.5rem',
              borderRadius: '8px',
              border: activeTab === 'docs' ? '1px solid rgba(139, 92, 246, 0.4)' : '1px solid transparent',
              background: activeTab === 'docs' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
              color: activeTab === 'docs' ? '#c4b5fd' : 'rgba(255, 255, 255, 0.5)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            <BookOpen size={14} />
            Docs & SOPs
          </button>
        </div>

        {/* Tab Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem' }}>
          {/* ────────────────── TAB 1: RÉSUMÉ DE CONVERSATION ────────────────── */}
          {activeTab === 'summary' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Synthèse Exécutive du Dossier
                </span>
                <button
                  onClick={fetchSummary}
                  disabled={loadingSummary}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#8b5cf6',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <RefreshCw size={12} className={loadingSummary ? 'animate-spin' : ''} />
                  Actualiser
                </button>
              </div>

              {loadingSummary ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255, 255, 255, 0.4)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.75rem auto', color: '#8b5cf6' }} />
                  <p style={{ fontSize: '0.85rem' }}>Analyse sémantique de la conversation en cours…</p>
                </div>
              ) : summary ? (
                <>
                  {/* Executive Summary Card */}
                  <div
                    style={{
                      background: 'rgba(139, 92, 246, 0.08)',
                      border: '1px solid rgba(139, 92, 246, 0.25)',
                      borderRadius: '12px',
                      padding: '1.1rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#c4b5fd', textTransform: 'uppercase' }}>
                        État de la Situation
                      </span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          background: summary.urgency_evaluation.includes('ÉLEVÉE') || summary.urgency_evaluation.includes('CRITIQUE')
                            ? 'rgba(239, 68, 68, 0.2)'
                            : 'rgba(16, 185, 129, 0.2)',
                          color: summary.urgency_evaluation.includes('ÉLEVÉE') || summary.urgency_evaluation.includes('CRITIQUE')
                            ? '#fca5a5'
                            : '#6ee7b7',
                          border: `1px solid ${
                            summary.urgency_evaluation.includes('ÉLEVÉE') || summary.urgency_evaluation.includes('CRITIQUE')
                              ? 'rgba(239, 68, 68, 0.3)'
                              : 'rgba(16, 185, 129, 0.3)'
                          }`,
                        }}
                      >
                        Urgence : {summary.urgency_evaluation}
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.88rem', color: '#f1f5f9', lineHeight: 1.55 }}>
                      {summary.summary}
                    </p>
                  </div>

                  {/* Problem Statement */}
                  <div
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '12px',
                      padding: '1rem',
                    }}
                  >
                    <h4 style={{ margin: '0 0 0.4rem 0', fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.45)', textTransform: 'uppercase' }}>
                      Problème Initial Identifié
                    </h4>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.5 }}>
                      {summary.problem_statement}
                    </p>
                  </div>

                  {/* Actions Already Taken */}
                  <div
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '12px',
                      padding: '1rem',
                    }}
                  >
                    <h4 style={{ margin: '0 0 0.6rem 0', fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.45)', textTransform: 'uppercase' }}>
                      Actions déjà entreprises dans les échanges
                    </h4>
                    {summary.actions_already_taken.length === 0 ? (
                      <span style={{ fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.35)', fontStyle: 'italic' }}>
                        Aucune tentative technique préalable notée dans la discussion.
                      </span>
                    ) : (
                      <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.6 }}>
                        {summary.actions_already_taken.map((act, i) => (
                          <li key={i}>{act}</li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* Blocker (if any) */}
                  {summary.current_blocker && (
                    <div
                      style={{
                        background: 'rgba(245, 158, 11, 0.08)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        borderRadius: '12px',
                        padding: '1rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '0.35rem' }}>
                        <AlertTriangle size={15} style={{ color: '#f59e0b' }} />
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#fbbf24', textTransform: 'uppercase' }}>
                          Point de Blocage Actuel
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: '0.84rem', color: '#fef3c7', lineHeight: 1.5 }}>
                        {summary.current_blocker}
                      </p>
                    </div>
                  )}

                  {/* Next Step Recommendation */}
                  <div
                    style={{
                      background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.05) 100%)',
                      border: '1px solid rgba(99, 102, 241, 0.35)',
                      borderRadius: '12px',
                      padding: '1rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Zap size={15} style={{ color: '#818cf8' }} />
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#a5b4fc', textTransform: 'uppercase' }}>
                          Prochaine Étape Recommandée par l'IA
                        </span>
                      </div>
                      <button
                        onClick={() => handleInsert(summary.suggested_next_step)}
                        style={{
                          background: 'rgba(99, 102, 241, 0.2)',
                          border: '1px solid rgba(99, 102, 241, 0.4)',
                          borderRadius: '6px',
                          padding: '3px 8px',
                          color: '#c7d2fe',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <ArrowRight size={12} />
                        Insérer
                      </button>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#e0e7ff', lineHeight: 1.5 }}>
                      {summary.suggested_next_step}
                    </p>
                  </div>
                </>
              ) : null}
            </div>
          )}

          {/* ────────────────── TAB 2: ACTIONS CONSEILLÉES ────────────────── */}
          {activeTab === 'actions' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Actions Immédiates Suggérées ({actions.length})
                </span>
                <button
                  onClick={fetchActions}
                  disabled={loadingActions}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#8b5cf6',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <RefreshCw size={12} className={loadingActions ? 'animate-spin' : ''} />
                  Actualiser
                </button>
              </div>

              {loadingActions ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255, 255, 255, 0.4)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.75rem auto', color: '#8b5cf6' }} />
                  <p style={{ fontSize: '0.85rem' }}>Calcul des meilleures actions de résolution…</p>
                </div>
              ) : (
                actions.map((act) => (
                  <div
                    key={act.id}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '12px',
                      padding: '1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.6rem',
                      transition: 'border-color 0.2s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {act.action_type === 'ESCALATION' ? (
                          <ShieldAlert size={15} style={{ color: '#f87171' }} />
                        ) : act.action_type === 'DIAGNOSTIC' ? (
                          <HelpCircle size={15} style={{ color: '#38bdf8' }} />
                        ) : act.action_type === 'COMMUNICATION' ? (
                          <FileText size={15} style={{ color: '#a78bfa' }} />
                        ) : (
                          <Zap size={15} style={{ color: '#34d399' }} />
                        )}
                        <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.45)', textTransform: 'uppercase' }}>
                          {act.action_type} · {act.category}
                        </span>
                      </div>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: act.impact === 'HIGH' ? 'rgba(239, 68, 68, 0.15)' : act.impact === 'MEDIUM' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                          color: act.impact === 'HIGH' ? '#fca5a5' : act.impact === 'MEDIUM' ? '#fcd34d' : '#93c5fd',
                          border: `1px solid ${act.impact === 'HIGH' ? 'rgba(239, 68, 68, 0.3)' : act.impact === 'MEDIUM' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(59, 130, 246, 0.3)'}`,
                        }}
                      >
                        Impact {act.impact}
                      </span>
                    </div>

                    <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9' }}>
                      {act.title}
                    </h4>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.65)', lineHeight: 1.45 }}>
                      {act.description}
                    </p>

                    {act.snippet_to_insert && (
                      <div
                        style={{
                          background: 'rgba(15, 15, 25, 0.75)',
                          border: '1px solid rgba(255, 255, 255, 0.06)',
                          borderRadius: '8px',
                          padding: '0.75rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <p style={{ margin: 0, fontSize: '0.8rem', color: '#c4b5fd', fontStyle: 'italic', lineHeight: 1.4 }}>
                          "{act.snippet_to_insert}"
                        </p>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '4px' }}>
                          <button
                            onClick={() => handleCopy(act.id, act.snippet_to_insert || '')}
                            style={{
                              background: 'rgba(255, 255, 255, 0.05)',
                              border: '1px solid rgba(255, 255, 255, 0.1)',
                              borderRadius: '6px',
                              padding: '4px 8px',
                              color: 'rgba(255, 255, 255, 0.7)',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            {copiedId === act.id ? <Check size={12} style={{ color: '#34d399' }} /> : <Copy size={12} />}
                            {copiedId === act.id ? 'Copié' : 'Copier'}
                          </button>
                          <button
                            onClick={() => handleInsert(act.snippet_to_insert || '')}
                            style={{
                              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '4px 10px',
                              color: '#fff',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <ArrowRight size={12} />
                            Insérer dans ma réponse
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* ────────────────── TAB 3: DOCUMENTATION INTERNE & SOPS ────────────────── */}
          {activeTab === 'docs' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Search Bar */}
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  placeholder="Rechercher une SOP, ISO 27001, VPN, certificat..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    fetchDocs(e.target.value, selectedDocCategory);
                  }}
                  style={{
                    width: '100%',
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '10px',
                    padding: '0.65rem 1rem 0.65rem 2.4rem',
                    color: '#f8fafc',
                    fontSize: '0.82rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
                <Search size={15} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'rgba(255, 255, 255, 0.4)' }} />
              </div>

              {/* Category Filters */}
              <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
                {['all', 'Réseau', 'Sécurité', 'Matériel', 'Logiciel', 'Escalade'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => {
                      setSelectedDocCategory(cat);
                      fetchDocs(searchQuery, cat);
                    }}
                    style={{
                      background: selectedDocCategory === cat ? 'rgba(139, 92, 246, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                      border: selectedDocCategory === cat ? '1px solid rgba(139, 92, 246, 0.45)' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '14px',
                      padding: '3px 10px',
                      color: selectedDocCategory === cat ? '#c4b5fd' : 'rgba(255, 255, 255, 0.5)',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {cat === 'all' ? 'Toutes' : cat}
                  </button>
                ))}
              </div>

              {/* Docs List */}
              {loadingDocs ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255, 255, 255, 0.4)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.75rem auto', color: '#8b5cf6' }} />
                  <p style={{ fontSize: '0.85rem' }}>Indexation de la base documentaire…</p>
                </div>
              ) : docs.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'rgba(255, 255, 255, 0.35)' }}>
                  <BookOpen size={30} style={{ margin: '0 auto 0.5rem auto', opacity: 0.5 }} />
                  <p style={{ fontSize: '0.82rem' }}>Aucune procédure interne ne correspond à la recherche.</p>
                </div>
              ) : (
                docs.map((doc) => {
                  const isExpanded = expandedDocId === doc.id;
                  return (
                    <div
                      key={doc.id}
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '12px',
                        padding: '1rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.6rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                fontSize: '0.65rem',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: doc.source_type.includes('ISO') ? 'rgba(239, 68, 68, 0.15)' : 'rgba(139, 92, 246, 0.15)',
                                color: doc.source_type.includes('ISO') ? '#fca5a5' : '#c4b5fd',
                                border: `1px solid ${doc.source_type.includes('ISO') ? 'rgba(239, 68, 68, 0.3)' : 'rgba(139, 92, 246, 0.3)'}`,
                              }}
                            >
                              {doc.source_type === 'GUIDE_SECURITE_ISO27001' ? 'ISO 27001' : 'SOP'}
                            </span>
                            <span style={{ fontSize: '0.68rem', color: 'rgba(255, 255, 255, 0.4)', fontWeight: 600 }}>
                              {doc.category}
                            </span>
                          </div>
                          <h4 style={{ margin: '4px 0 0 0', fontSize: '0.88rem', fontWeight: 600, color: '#f8fafc', lineHeight: 1.35 }}>
                            {doc.title}
                          </h4>
                        </div>
                        <div
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '10px',
                            background: doc.relevance_score >= 80 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: doc.relevance_score >= 80 ? '#6ee7b7' : '#fcd34d',
                            border: `1px solid ${doc.relevance_score >= 80 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {doc.relevance_score}% pertinence
                        </div>
                      </div>

                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.65)', lineHeight: 1.45 }}>
                        {doc.content_snippet}
                      </p>

                      {/* Expandable full content */}
                      {isExpanded && (
                        <div
                          style={{
                            background: 'rgba(0, 0, 0, 0.4)',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            borderRadius: '8px',
                            padding: '0.85rem',
                            fontSize: '0.78rem',
                            color: '#cbd5e1',
                            lineHeight: 1.55,
                            whiteSpace: 'pre-wrap',
                            maxHeight: '260px',
                            overflowY: 'auto',
                          }}
                        >
                          {doc.full_content}
                        </div>
                      )}

                      {/* Actions */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                        <button
                          onClick={() => setExpandedDocId(isExpanded ? null : doc.id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#a78bfa',
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            padding: 0,
                          }}
                        >
                          {isExpanded ? 'Réduire la procédure' : 'Lire la procédure complète →'}
                        </button>

                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            onClick={() => handleCopy(doc.id, doc.full_content)}
                            style={{
                              background: 'rgba(255, 255, 255, 0.05)',
                              border: '1px solid rgba(255, 255, 255, 0.1)',
                              borderRadius: '6px',
                              padding: '4px 8px',
                              color: 'rgba(255, 255, 255, 0.7)',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            {copiedId === doc.id ? <Check size={12} style={{ color: '#34d399' }} /> : <Copy size={12} />}
                            {copiedId === doc.id ? 'Copié' : 'Copier'}
                          </button>
                          <button
                            onClick={() => handleInsert(`[RÉFÉRENCE PROCÉDURE ${doc.title}]\n${doc.content_snippet}`)}
                            style={{
                              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '4px 10px',
                              color: '#fff',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <ArrowRight size={12} />
                            Insérer dans ma réponse
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
