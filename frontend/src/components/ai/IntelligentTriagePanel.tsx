import React, { useState, useEffect } from 'react';
import {
  Sparkles, AlertTriangle, CheckCircle2, History,
  Send, Check, Loader2,
  HelpCircle, ShieldAlert, Zap, BookOpen, Layers,
  ExternalLink, Copy
} from 'lucide-react';
import api from '../../api/axios';
import toast from 'react-hot-toast';
import {
  type IntelligentTriageResult,
  type CannedResponseTemplate
} from '../../types';

interface IntelligentTriagePanelProps {
  ticketId: string;
  onResponseSent?: () => void;
  onTicketResolved?: () => void;
}

export const IntelligentTriagePanel: React.FC<IntelligentTriagePanelProps> = ({
  ticketId,
  onResponseSent,
  onTicketResolved,
}) => {

  const [loading, setLoading] = useState(false);
  const [triageData, setTriageData] = useState<IntelligentTriageResult | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('canned_resolution');
  const [responseText, setResponseText] = useState<string>('');
  const [resolutionNote, setResolutionNote] = useState<string>('');
  const [isSending, setIsSending] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showResolveForm, setShowResolveForm] = useState(false);

  const runTriage = async () => {
    setLoading(true);
    try {
      const res = await api.get<IntelligentTriageResult>(`/ai/tickets/${ticketId}/intelligent-triage`);
      setTriageData(res.data);
      
      // Pre-fill response with default resolution template if available
      const defaultTpl = res.data.canned_responses.find(c => c.id === 'canned_resolution') || res.data.canned_responses[0];
      if (defaultTpl) {
        setSelectedTemplateId(defaultTpl.id);
        setResponseText(defaultTpl.full_body);
      }
      
      // Pre-fill resolution note from evaluated best solution
      if (res.data.best_solution?.recommended_solution) {
        setResolutionNote(res.data.best_solution.recommended_solution);
      }

      toast.success("Analyse de triage intelligent effectuée !");
    } catch (err) {
      console.error(err);
      toast.error("Échec de l'analyse IA de triage.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ticketId) {
      runTriage();
    }
  }, [ticketId]);

  const handleSelectTemplate = (tpl: CannedResponseTemplate) => {
    setSelectedTemplateId(tpl.id);
    setResponseText(tpl.full_body);
    toast.success(`Modèle « ${tpl.title} » appliqué`);
  };

  const handleSendResponse = async () => {
    if (!responseText.trim()) {
      toast.error("Veuillez saisir un message avant d'envoyer.");
      return;
    }

    setIsSending(true);
    const toastId = toast.loading("Envoi de la réponse au demandeur...");
    try {
      await api.post(`/tickets/${ticketId}/send-response`, {
        response_text: responseText
      });
      toast.success("Réponse envoyée avec succès par e-mail !", { id: toastId });
      if (onResponseSent) onResponseSent();
    } catch (err) {
      console.error(err);
      toast.error("Erreur lors de l'envoi de la réponse.", { id: toastId });
    } finally {
      setIsSending(false);
    }
  };

  const handleResolveTicket = async () => {
    if (!resolutionNote.trim()) {
      toast.error("Veuillez renseigner la solution appliquée.");
      return;
    }

    setIsResolving(true);
    const toastId = toast.loading("Clôture et enregistrement de la solution...");
    try {
      await api.post(`/tickets/${ticketId}/resolve`, {
        resolution_note: resolutionNote
      });
      toast.success("Ticket résolu ! Solution ajoutée à la base d'apprentissage.", { id: toastId });
      setShowResolveForm(false);
      if (onTicketResolved) onTicketResolved();
    } catch (err) {
      console.error(err);
      toast.error("Erreur lors de la résolution du ticket.", { id: toastId });
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(15, 15, 25, 0.95) 100%)',
      border: '1px solid rgba(139, 92, 246, 0.28)',
      borderRadius: '24px',
      padding: '1.75rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1.5rem',
      position: 'relative',
      boxShadow: '0 20px 50px rgba(0, 0, 0, 0.4)',
      fontFamily: "'DM Sans', sans-serif"
    }}>
      {/* ── HEADER ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '44px', height: '44px', borderRadius: '14px',
            background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', boxShadow: '0 4px 20px rgba(124, 58, 237, 0.45)'
          }}>
            <Sparkles size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f1f5f9' }}>
                Triage Intelligent & Réponses Types
              </h3>
              <span style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: '999px',
                background: 'rgba(139, 92, 246, 0.18)', border: '1px solid rgba(139, 92, 246, 0.35)',
                color: '#c4b5fd', fontWeight: 700, textTransform: 'uppercase'
              }}>
                IA Active
              </span>
            </div>
            <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.45)' }}>
              Analyse de l'historique · Détection de récurrence · Meilleure solution · Modèles prêts à l'envoi
            </p>
          </div>
        </div>

        <button
          onClick={runTriage}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '0.55rem 1.1rem', borderRadius: '12px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            color: '#c4b5fd', fontSize: '0.8rem', fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s'
          }}
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
          {loading ? "Analyse en cours..." : "Relancer le Triage"}
        </button>
      </div>

      {loading && (
        <div style={{ padding: '2.5rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
          <Loader2 size={36} className="animate-spin" style={{ color: '#8b5cf6' }} />
          <p style={{ fontSize: '0.9rem', color: 'rgba(255, 255, 255, 0.6)', margin: 0 }}>
            L'IA compare le ticket avec l'historique des incidents et évalue la solution optimale...
          </p>
        </div>
      )}

      {!loading && triageData && (
        <>
          {/* ── 1. BANNIÈRE TICKETS RÉPÉTITIFS ── */}
          <div style={{
            padding: '1rem 1.25rem',
            borderRadius: '16px',
            background: triageData.is_repetitive
              ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(245, 158, 11, 0.08) 100%)'
              : 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.06) 100%)',
            border: triageData.is_repetitive
              ? '1px solid rgba(239, 68, 68, 0.35)'
              : '1px solid rgba(16, 185, 129, 0.3)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
            gap: '12px', flexWrap: 'wrap'
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '10px',
                background: triageData.is_repetitive ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: triageData.is_repetitive ? '#f87171' : '#34d399', flexShrink: 0
              }}>
                {triageData.is_repetitive ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h4 style={{
                    margin: 0, fontSize: '0.92rem', fontWeight: 700,
                    color: triageData.is_repetitive ? '#fca5a5' : '#6ee7b7'
                  }}>
                    {triageData.is_repetitive
                      ? `⚠️ Incident Répétitif Détecté (${triageData.recurrence_count} cas similaires)`
                      : "✅ Incident Isolé (Aucune récurrence anormale)"}
                  </h4>
                  {triageData.intent && (
                    <span style={{
                      fontSize: '10px', padding: '2px 7px', borderRadius: '6px',
                      background: 'rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.7)',
                      fontWeight: 600
                    }}>
                      INTENT: {triageData.intent}
                    </span>
                  )}
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'rgba(255, 255, 255, 0.65)' }}>
                  {triageData.repetitive_reason || "Ce problème ne présente pas de pattern de récurrence élevé dans les 90 derniers jours."}
                </p>
              </div>
            </div>

            {triageData.similar_tickets.length > 0 && (
              <button
                onClick={() => setShowHistoryModal(!showHistoryModal)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '0.45rem 0.9rem', borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#e2e8f0', fontSize: '0.78rem', fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <History size={14} />
                {showHistoryModal ? "Masquer les cas similaires" : `Voir ${triageData.similar_tickets.length} cas similaires`}
              </button>
            )}
          </div>

          {/* ── LISTE DÉROULANTE DES TICKETS SIMILAIRES ── */}
          {showHistoryModal && triageData.similar_tickets.length > 0 && (
            <div style={{
              background: 'rgba(10, 10, 20, 0.6)',
              border: '1px solid rgba(139, 92, 246, 0.2)',
              borderRadius: '16px', padding: '1rem',
              display: 'flex', flexDirection: 'column', gap: '8px'
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                Historique des Tickets Rapprochés
              </div>
              {triageData.similar_tickets.map((st) => (
                <div key={st.ticket_id} style={{
                  padding: '10px 14px', borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: '12px', flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: 700,
                      background: st.similarity_score >= 70 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: st.similarity_score >= 70 ? '#f87171' : '#fbbf24',
                      border: `1px solid ${st.similarity_score >= 70 ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'}`
                    }}>
                      {st.similarity_score}% Similarité
                    </span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#f1f5f9' }}>
                        {st.subject}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'rgba(255, 255, 255, 0.4)' }}>
                        #{st.ticket_id.slice(-6).toUpperCase()} · {st.category} · Statut : {st.status}
                        {st.resolution_note && (
                          <span style={{ color: '#34d399', marginLeft: '6px' }}>
                            ✓ Résolu avec solution enregistrée
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <a
                    href={`/tickets/${st.ticket_id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'flex', alignItems: 'center', gap: '4px',
                      color: '#a78bfa', fontSize: '0.75rem', fontWeight: 600,
                      textDecoration: 'none', padding: '4px 8px',
                      borderRadius: '6px', background: 'rgba(139, 92, 246, 0.1)'
                    }}
                  >
                    Consulter <ExternalLink size={12} />
                  </a>
                </div>
              ))}
            </div>
          )}

          {/* ── 2. ÉVALUATION DE LA MEILLEURE SOLUTION ── */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: '18px', padding: '1.25rem',
            display: 'flex', flexDirection: 'column', gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '10px',
                  background: 'rgba(16, 185, 129, 0.18)', color: '#34d399',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Zap size={18} />
                </div>
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f1f5f9' }}>
                    Meilleure Solution Évaluée par l'IA
                  </h4>
                  <span style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: 600 }}>
                    {triageData.best_solution.confidence_score}% de pertinence estimée
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  fontSize: '11px', padding: '3px 9px', borderRadius: '8px',
                  background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: 'rgba(255, 255, 255, 0.7)', display: 'flex', alignItems: 'center', gap: '5px'
                }}>
                  {triageData.best_solution.source_type === 'HISTORICAL_TICKET' && <History size={12} style={{ color: '#a78bfa' }} />}
                  {triageData.best_solution.source_type === 'KNOWLEDGE_BASE' && <BookOpen size={12} style={{ color: '#34d399' }} />}
                  {triageData.best_solution.source_type === 'AI_SYNTHESIS' && <Sparkles size={12} style={{ color: '#60a5fa' }} />}
                  {triageData.best_solution.source_reference || triageData.best_solution.source_type}
                </span>
                <button
                  onClick={() => {
                    setResponseText(prev => prev + "\n\n💡 Solution recommandée :\n" + triageData.best_solution.recommended_solution);
                    toast.success("Solution copiée dans la zone de réponse !");
                  }}
                  title="Ajouter à la réponse"
                  style={{
                    display: 'flex', alignItems: 'center', gap: '4px',
                    padding: '4px 8px', borderRadius: '8px',
                    background: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(139, 92, 246, 0.3)',
                    color: '#c4b5fd', fontSize: '11px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  <Copy size={12} /> Copier dans la réponse
                </button>
              </div>
            </div>

            <p style={{
              margin: 0, fontSize: '0.88rem', color: '#f8fafc', lineHeight: '1.5',
              background: 'rgba(0, 0, 0, 0.25)', padding: '10px 14px', borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.04)'
            }}>
              {triageData.best_solution.recommended_solution}
            </p>

            {triageData.best_solution.actionable_steps && triageData.best_solution.actionable_steps.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Étapes de Résolution Conseillées
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '6px' }}>
                  {triageData.best_solution.actionable_steps.map((step, idx) => (
                    <div key={idx} style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      padding: '6px 10px', borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      fontSize: '0.78rem', color: 'rgba(255, 255, 255, 0.8)'
                    }}>
                      <span style={{
                        width: '18px', height: '18px', borderRadius: '50%',
                        background: 'rgba(16, 185, 129, 0.2)', color: '#34d399',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '10px', fontWeight: 700, flexShrink: 0
                      }}>
                        {idx + 1}
                      </span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── 3. PROPOSITION DE RÉPONSES TYPES ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={18} style={{ color: '#a78bfa' }} />
                <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f1f5f9' }}>
                  Réponses Types (Canned Templates)
                </h4>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'rgba(255, 255, 255, 0.4)' }}>
                Sélectionnez un modèle pour préremplir votre message
              </span>
            </div>

            {/* Template Selector Tabs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
              {triageData.canned_responses.map((tpl) => {
                const isSelected = selectedTemplateId === tpl.id;
                let tabIcon = <Check size={14} />;
                let activeColor = '#34d399';

                if (tpl.category === 'CLARIFICATION') {
                  tabIcon = <HelpCircle size={14} />;
                  activeColor = '#60a5fa';
                } else if (tpl.category === 'IN_PROGRESS') {
                  tabIcon = <Zap size={14} />;
                  activeColor = '#fbbf24';
                } else if (tpl.category === 'ESCALATION') {
                  tabIcon = <ShieldAlert size={14} />;
                  activeColor = '#f87171';
                }

                return (
                  <button
                    key={tpl.id}
                    onClick={() => handleSelectTemplate(tpl)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '12px',
                      background: isSelected ? 'rgba(139, 92, 246, 0.22)' : 'rgba(255, 255, 255, 0.03)',
                      border: isSelected ? '1px solid rgba(139, 92, 246, 0.6)' : '1px solid rgba(255, 255, 255, 0.07)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'all 0.18s'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: isSelected ? '#fff' : 'rgba(255, 255, 255, 0.8)', fontWeight: 700, fontSize: '0.82rem' }}>
                      <span style={{ color: activeColor }}>{tabIcon}</span>
                      <span>{tpl.title}</span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'rgba(255, 255, 255, 0.4)', lineHeight: '1.3' }}>
                      {tpl.preview_text}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Editable Response Area */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 700, color: 'rgba(255, 255, 255, 0.5)' }}>
                  Message à envoyer au demandeur (personnalisable) :
                </label>
                <span style={{ fontSize: '0.72rem', color: 'rgba(255, 255, 255, 0.35)' }}>
                  Envoi direct par e-mail avec copie dans le ticket
                </span>
              </div>
              <textarea
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                rows={7}
                style={{
                  width: '100%',
                  background: 'rgba(10, 10, 20, 0.75)',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                  borderRadius: '14px',
                  padding: '12px 14px',
                  color: '#f8fafc',
                  fontSize: '0.86rem',
                  lineHeight: '1.6',
                  outline: 'none',
                  fontFamily: "'DM Sans', sans-serif",
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Actions Bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <button
                onClick={() => setShowResolveForm(!showResolveForm)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '0.65rem 1.25rem', borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  color: '#34d399', fontSize: '0.85rem', fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                <CheckCircle2 size={16} />
                {showResolveForm ? "Annuler Clôture" : "Résoudre le Ticket avec cette Solution"}
              </button>

              <button
                onClick={handleSendResponse}
                disabled={isSending}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '0.65rem 1.5rem', borderRadius: '12px',
                  background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                  border: 'none',
                  color: '#fff', fontSize: '0.85rem', fontWeight: 700,
                  cursor: isSending ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 16px rgba(124, 58, 237, 0.4)'
                }}
              >
                {isSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {isSending ? "Envoi en cours..." : "Envoyer la Réponse au Demandeur"}
              </button>
            </div>

            {/* Formulaire de résolution avec enregistrement de solution */}
            {showResolveForm && (
              <div style={{
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '16px', padding: '1.25rem',
                display: 'flex', flexDirection: 'column', gap: '10px',
                marginTop: '6px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle2 size={18} style={{ color: '#34d399' }} />
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f1f5f9' }}>
                    Clôturer le Ticket & Capitaliser la Solution
                  </h4>
                </div>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.6)' }}>
                  La solution ci-dessous sera enregistrée sur le ticket et enrichira l'historique IA pour résoudre les futurs tickets similaires.
                </p>
                <textarea
                  value={resolutionNote}
                  onChange={(e) => setResolutionNote(e.target.value)}
                  rows={4}
                  placeholder="Décrivez la solution appliquée (ex: Réinitialisation du cache VPN et régénération du certificat utilisateur)..."
                  style={{
                    width: '100%',
                    background: 'rgba(10, 10, 20, 0.8)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    borderRadius: '10px', padding: '10px 12px',
                    color: '#f8fafc', fontSize: '0.85rem', outline: 'none'
                  }}
                />
                <button
                  onClick={handleResolveTicket}
                  disabled={isResolving}
                  style={{
                    alignSelf: 'flex-end',
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '0.55rem 1.25rem', borderRadius: '10px',
                    background: 'linear-gradient(135deg, #059669, #10b981)',
                    border: 'none', color: '#fff', fontSize: '0.82rem', fontWeight: 700,
                    cursor: isResolving ? 'not-allowed' : 'pointer'
                  }}
                >
                  {isResolving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                  Confirmer la Résolution du Ticket
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default IntelligentTriagePanel;
