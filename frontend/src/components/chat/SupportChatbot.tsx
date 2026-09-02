import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Send, Bot, Sparkles, Zap,
  RotateCcw, ArrowRight, Loader2, CheckCircle2,
  ExternalLink, Paperclip, FileText
} from 'lucide-react';
import api from '../../api/axios';
import toast from 'react-hot-toast';
import axios from 'axios';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  source?: 'knowledge_base' | 'llm' | 'fallback';
  suggestions?: string[];
  canEscalate?: boolean;
}

interface AttachedFile {
  filename: string;
  path: string;
  size?: number;
}

const QUICK_PROMPTS = [
  { label: '🔑 Mot de passe oublié', query: "J'ai oublié mon mot de passe pour accéder à ma session GEISER." },
  { label: '🌐 Problème de connexion VPN', query: "Mon client VPN n'arrive pas à se connecter au réseau entreprise." },
  { label: '💻 PC lent / Mémoire saturée', query: "Mon ordinateur est extrêmement lent et bloque souvent." },
  { label: '📦 Demande de logiciel', query: "Comment faire une demande d'installation d'un nouveau logiciel ?" },
];

export const SupportChatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Bonjour ! Je suis **GEISER Support Bot**, votre assistant IA disponible 24/7.\n\nDécrivez votre problème ou choisissez une question fréquente ci-dessous :",
      timestamp: new Date(),
      suggestions: [
        "J'ai un problème d'accès ou de mot de passe",
        "Problème matériel ou réseau",
        "Créer directement un ticket"
      ],
      canEscalate: false
    }
  ]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isEscalating, setIsEscalating] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [escalatedTicket, setEscalatedTicket] = useState<{ id: string; subject: string; category: string; subcategory?: string; priority: string; keywords: string[] } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [isOpen, messages, loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date()
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const payloadMessages = newMessages.map(m => ({ role: m.role, content: m.content }));
      const res = await api.post('/chat/message', { messages: payloadMessages });
      const data = res.data;

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply,
        timestamp: new Date(),
        source: data.source,
        suggestions: data.suggested_actions,
        canEscalate: data.can_escalate
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      toast.error("Erreur de connexion au service d'assistance IA.");
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: "Désolé, une erreur est survenue. Vous pouvez convertir cette demande en ticket officiel ci-dessous.",
          timestamp: new Date(),
          canEscalate: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    setUploadingFile(true);

    try {
      const res = await api.post('/chat/upload-attachment', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setAttachedFiles(prev => [...prev, {
        filename: res.data.filename,
        path: res.data.path,
        size: res.data.size
      }]);
      toast.success(`Fichier joint : ${file.name}`);
    } catch (err) {
      console.error(err);
      toast.error("Échec du téléversement du fichier.");
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (index: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index));
  };

  /** 1-click AI ticket creation — no form needed */
  const handleEscalateToTicket = async () => {
    const hasRealContent = messages.some(m => m.role === 'user');
    if (!hasRealContent || isEscalating) return;

    setIsEscalating(true);
    const toastId = toast.loading("L'IA analyse votre demande et crée le ticket...");

    try {
      const payloadMessages = messages.map(m => ({ role: m.role, content: m.content }));

      const res = await api.post('/chat/escalate', {
        messages: payloadMessages,
        attachments: attachedFiles.map(f => f.path)
      });

      const ticket = res.data;
      setEscalatedTicket({
        id: ticket.id,
        subject: ticket.subject,
        category: ticket.category,
        subcategory: ticket.subcategory,
        priority: ticket.priority,
        keywords: ticket.keywords || []
      });

      toast.success(`Ticket #${ticket.id.slice(-6).toUpperCase()} créé avec succès !`, { id: toastId });

      const priorityLabel: Record<string, string> = {
        LOW: '🟢 Faible', MEDIUM: '🔵 Moyenne', HIGH: '🟠 Haute', URGENT: '🔴 Urgente'
      };
      const kwLine = ticket.keywords?.length
        ? `\n- **Mots-clés IA :** ${ticket.keywords.join(', ')}`
        : '';

      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'assistant',
          content: `✅ **Ticket créé et analysé par l'IA !**\n\n- **Numéro :** #${ticket.id.slice(-6).toUpperCase()}\n- **Objet :** ${ticket.subject}\n- **Catégorie :** ${ticket.category} > ${ticket.subcategory || 'Général'}\n- **Priorité :** ${priorityLabel[ticket.priority] || ticket.priority}${kwLine}\n- **Canal :** Chat en ligne`,
          timestamp: new Date(),
          canEscalate: false
        }
      ]);

    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 400) {
        // AI rejected — invalid / casual conversation
        const reason = err.response?.data?.detail || "Veuillez décrire un problème technique réel pour créer un ticket.";
        toast.dismiss(toastId);
        toast.error(reason, { duration: 6000 });

        setMessages(prev => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'assistant',
            content: `⚠️ **Ticket non créé**\n\n${reason}\n\nExemples de problèmes valides :\n- "Mon accès VPN est bloqué depuis ce matin"\n- "Mon ordinateur affiche un écran bleu"\n- "Je ne peux plus me connecter à Outlook"`,
            timestamp: new Date(),
            canEscalate: false
          }
        ]);
      } else {
        console.error(err);
        toast.error("Échec de la création du ticket.", { id: toastId });
      }
    } finally {
      setIsEscalating(false);
    }
  };

  const handleResetChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: "Conversation réinitialisée. Comment puis-je vous aider ?",
        timestamp: new Date(),
        suggestions: [
          "J'ai un problème d'accès ou de mot de passe",
          "Problème matériel ou réseau",
          "Créer directement un ticket"
        ],
        canEscalate: false
      }
    ]);
    setAttachedFiles([]);
    setEscalatedTicket(null);
  };

  const hasUserMessages = messages.some(m => m.role === 'user');

  return (
    <>
      {/* ── FLOATING ACTION BUTTON ── */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999 }}>
        {!isOpen && (
          <motion.button
            onClick={() => setIsOpen(true)}
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.95 }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '12px 20px', borderRadius: '999px',
              background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
              border: '1px solid rgba(139, 92, 246, 0.4)',
              boxShadow: '0 8px 32px rgba(124, 58, 237, 0.45), 0 0 0 1px rgba(255,255,255,0.1)',
              color: 'white', cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
              fontWeight: 600, fontSize: '14px',
            }}
          >
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <Bot size={20} />
              <span style={{
                position: 'absolute', top: '-2px', right: '-2px',
                width: '8px', height: '8px', borderRadius: '50%',
                background: '#10b981', border: '1.5px solid #080812', boxShadow: '0 0 6px #10b981',
              }} />
            </div>
            <span>Support IA 24/7</span>
            <Sparkles size={15} style={{ color: '#a78bfa' }} />
          </motion.button>
        )}
      </div>

      {/* ── CHAT WINDOW ── */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.95 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            style={{
              position: 'fixed', bottom: '24px', right: '24px',
              width: '420px', maxWidth: 'calc(100vw - 32px)',
              height: '620px', maxHeight: 'calc(100vh - 48px)',
              borderRadius: '24px',
              background: 'rgba(10, 10, 20, 0.96)',
              backdropFilter: 'blur(30px)',
              border: '1px solid rgba(139, 92, 246, 0.25)',
              boxShadow: '0 24px 60px rgba(0, 0, 0, 0.7), 0 0 40px rgba(124, 58, 237, 0.2)',
              display: 'flex', flexDirection: 'column', overflow: 'hidden',
              zIndex: 10000, fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {/* ── HEADER ── */}
            <div style={{
              padding: '14px 18px',
              borderBottom: '1px solid rgba(139, 92, 246, 0.15)',
              background: 'linear-gradient(180deg, rgba(124, 58, 237, 0.15) 0%, rgba(10, 10, 20, 0.4) 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '38px', height: '38px', borderRadius: '12px',
                  background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', boxShadow: '0 4px 16px rgba(124, 58, 237, 0.4)',
                  position: 'relative',
                }}>
                  <Bot size={20} />
                  <div style={{
                    position: 'absolute', bottom: '-1px', right: '-1px',
                    width: '9px', height: '9px', borderRadius: '50%',
                    background: '#10b981', border: '2px solid #0a0a14',
                  }} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#f1f5f9' }}>
                      GEISER Support IA
                    </h3>
                    <span style={{
                      fontSize: '9px', padding: '2px 5px', borderRadius: '4px',
                      background: 'rgba(16, 185, 129, 0.15)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      color: '#34d399', fontWeight: 700, textTransform: 'uppercase',
                    }}>24/7</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '10.5px', color: 'rgba(255, 255, 255, 0.4)' }}>
                    Triage IA automatique · Canal Chat en ligne
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button onClick={handleResetChat} title="Réinitialiser" style={{
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px', width: '30px', height: '30px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
                }}>
                  <RotateCcw size={13} />
                </button>
                <button onClick={() => setIsOpen(false)} title="Fermer" style={{
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px', width: '30px', height: '30px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
                }}>
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* ── AI TRIAGE BADGE ── */}
            <div style={{
              padding: '7px 14px',
              background: 'rgba(139, 92, 246, 0.06)',
              borderBottom: '1px solid rgba(139, 92, 246, 0.1)',
              display: 'flex', alignItems: 'center', gap: '8px',
            }}>
              <Sparkles size={11} style={{ color: '#a78bfa', flexShrink: 0 }} />
              <span style={{ fontSize: '10.5px', color: 'rgba(255,255,255,0.45)' }}>
                L'IA détermine automatiquement la catégorie, la priorité et les mots-clés à la création du ticket.
              </span>
            </div>

            {/* ── MESSAGES ── */}
            <div style={{
              flex: 1, padding: '14px', overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: '12px',
            }}>
              {/* Quick Prompts */}
              {messages.length <= 1 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '4px' }}>
                  <span style={{
                    fontSize: '10.5px', fontWeight: 600, color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>
                    Questions fréquentes
                  </span>
                  {QUICK_PROMPTS.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(item.query)}
                      style={{
                        padding: '8px 10px', borderRadius: '10px',
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(139, 92, 246, 0.15)',
                        color: 'rgba(255,255,255,0.75)', fontSize: '12px',
                        textAlign: 'left', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = 'rgba(139, 92, 246, 0.12)';
                        e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.35)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                        e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.15)';
                      }}
                    >
                      <span>{item.label}</span>
                      <ArrowRight size={12} style={{ color: '#a78bfa' }} />
                    </button>
                  ))}
                </div>
              )}

              {/* Messages */}
              {messages.map(msg => (
                <div key={msg.id} style={{
                  display: 'flex', flexDirection: 'column',
                  alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  gap: '4px',
                }}>
                  <div style={{
                    maxWidth: '88%', padding: '10px 12px',
                    borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, #7c3aed, #6d28d9)'
                      : 'rgba(255,255,255,0.05)',
                    border: msg.role === 'user'
                      ? '1px solid rgba(139, 92, 246, 0.4)'
                      : '1px solid rgba(255,255,255,0.08)',
                    color: 'rgba(255,255,255,0.95)', fontSize: '12.5px',
                    lineHeight: '1.5', whiteSpace: 'pre-wrap',
                  }}>
                    {msg.content}
                  </div>

                  {msg.source && (
                    <span style={{
                      fontSize: '9.5px',
                      color: msg.source === 'knowledge_base' ? '#34d399' : '#a78bfa',
                      fontWeight: 600, padding: '0 4px',
                    }}>
                      {msg.source === 'knowledge_base' ? '📚 Base de connaissances GEISER' : '✨ Modèle IA Gemma 3'}
                    </span>
                  )}

                  {msg.suggestions && msg.suggestions.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '4px' }}>
                      {msg.suggestions.map((s, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            if (s.toLowerCase().includes('ticket') || s.toLowerCase().includes('humain')) {
                              handleEscalateToTicket();
                            } else {
                              handleSendMessage(s);
                            }
                          }}
                          style={{
                            padding: '3px 8px', borderRadius: '999px',
                            background: 'rgba(139, 92, 246, 0.1)',
                            border: '1px solid rgba(139, 92, 246, 0.25)',
                            color: '#c4b5fd', fontSize: '10.5px', fontWeight: 600, cursor: 'pointer',
                          }}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '6px 10px', background: 'rgba(255,255,255,0.03)',
                  borderRadius: '10px', width: 'fit-content',
                }}>
                  <Loader2 size={14} className="animate-spin" style={{ color: '#a78bfa' }} />
                  <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
                    L'IA formule une réponse...
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* ── ATTACHED FILES CHIPS ── */}
            {attachedFiles.length > 0 && (
              <div style={{
                padding: '6px 12px',
                background: 'rgba(139,92,246,0.07)',
                borderTop: '1px solid rgba(139,92,246,0.15)',
                display: 'flex', gap: '6px', overflowX: 'auto',
              }}>
                {attachedFiles.map((file, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '4px',
                    padding: '3px 8px', borderRadius: '6px',
                    background: 'rgba(255,255,255,0.05)',
                    fontSize: '11px', color: '#c4b5fd', flexShrink: 0,
                  }}>
                    <FileText size={11} />
                    <span style={{ maxWidth: '90px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {file.filename}
                    </span>
                    <button onClick={() => handleRemoveFile(i)} style={{
                      background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)',
                      cursor: 'pointer', padding: 0,
                    }}>
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* ── ESCALATE / TICKET SUCCESS BANNER ── */}
            {hasUserMessages && !escalatedTicket && (
              <div style={{
                padding: '8px 14px',
                background: 'rgba(139, 92, 246, 0.07)',
                borderTop: '1px solid rgba(139, 92, 246, 0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px',
              }}>
                <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)' }}>
                  Besoin d'un technicien ?
                </div>
                <button
                  onClick={handleEscalateToTicket}
                  disabled={isEscalating}
                  title="L'IA classe et priorise le ticket automatiquement"
                  style={{
                    padding: '5px 12px', borderRadius: '8px',
                    background: 'linear-gradient(135deg, rgba(124,58,237,0.4), rgba(79,70,229,0.4))',
                    border: '1px solid rgba(139,92,246,0.45)',
                    color: '#e9d5ff', fontSize: '11px', fontWeight: 700,
                    cursor: isEscalating ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: '5px',
                  }}
                >
                  {isEscalating
                    ? <><Loader2 size={12} className="animate-spin" /> Analyse IA en cours...</>
                    : <><Zap size={12} /> Créer un Ticket (IA auto-triage)</>
                  }
                </button>
              </div>
            )}

            {/* Ticket created confirmation */}
            {escalatedTicket && (
              <div style={{
                padding: '8px 14px',
                background: 'rgba(16, 185, 129, 0.08)',
                borderTop: '1px solid rgba(16, 185, 129, 0.2)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={13} style={{ color: '#34d399' }} />
                    <span style={{ fontSize: '11px', color: '#34d399', fontWeight: 700 }}>
                      Ticket #{escalatedTicket.id.slice(-6).toUpperCase()}
                    </span>
                  </div>
                  <button
                    onClick={() => { navigate(`/tickets/${escalatedTicket.id}`); setIsOpen(false); }}
                    style={{
                      background: 'none', border: 'none', color: '#a78bfa',
                      fontSize: '11px', fontWeight: 700, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '3px',
                    }}
                  >
                    Voir le ticket <ExternalLink size={11} />
                  </button>
                </div>
                {escalatedTicket.keywords.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {escalatedTicket.keywords.map((k, i) => (
                      <span key={i} style={{
                        padding: '1px 6px', borderRadius: '4px', fontSize: '9.5px',
                        background: 'rgba(139,92,246,0.12)', color: '#c4b5fd',
                        border: '1px solid rgba(139,92,246,0.2)',
                      }}>
                        #{k}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── FILE INPUT (hidden) ── */}
            <input type="file" ref={fileInputRef} onChange={handleFileUpload} style={{ display: 'none' }} />

            {/* ── INPUT BAR ── */}
            <form
              onSubmit={e => { e.preventDefault(); handleSendMessage(); }}
              style={{
                padding: '10px 14px',
                borderTop: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(10, 10, 20, 0.6)',
                display: 'flex', alignItems: 'center', gap: '6px',
              }}
            >
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                title="Joindre un fichier (optionnel)"
                disabled={uploadingFile}
                style={{
                  width: '34px', height: '34px', borderRadius: '10px',
                  background: uploadingFile ? 'rgba(139,92,246,0.15)' : 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: uploadingFile ? '#a78bfa' : 'rgba(255,255,255,0.5)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: uploadingFile ? 'not-allowed' : 'pointer', flexShrink: 0,
                }}
              >
                {uploadingFile ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={15} />}
              </button>

              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Décrivez votre problème..."
                disabled={loading}
                style={{
                  flex: 1, background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(139, 92, 246, 0.2)',
                  borderRadius: '10px', padding: '8px 12px',
                  color: 'white', fontSize: '12.5px', outline: 'none',
                  fontFamily: "'DM Sans', sans-serif",
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                style={{
                  width: '34px', height: '34px', borderRadius: '10px',
                  background: input.trim() && !loading
                    ? 'linear-gradient(135deg, #7c3aed, #4f46e5)'
                    : 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                  color: input.trim() && !loading ? 'white' : 'rgba(255,255,255,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                  flexShrink: 0,
                }}
              >
                <Send size={14} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};
