import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  RefreshCw,
  Sparkles,
  Star,
  ThumbsUp,
  ThumbsDown,
  FileText,
  CheckCircle2,
  Layers,
  MessageSquare,
  Activity,
  X,
  Copy,
  Check,
  ArrowUpDown,
  Filter,
  Lightbulb,
  Wrench
} from 'lucide-react';
import api from '../../api/axios';
import toast from 'react-hot-toast';

interface DatasetItem {
  id: string;
  category: string;
  priority: string;
  intent: string;
  context: Record<string, string>;
  sop?: string;
  result?: string;
  tags: string[];
  turns_count: number;
  first_user_query: string;
  last_solution: string;
}

interface DatasetResponse {
  total_items: number;
  total_dataset_count: number;
  skip: number;
  limit: number;
  categories: string[];
  intents: string[];
  sops_count: number;
  priorities: string[];
  items: DatasetItem[];
}

interface DocDetail {
  id: string;
  category: string;
  priority: string;
  intent: string;
  context: Record<string, string>;
  sop?: string;
  result?: string;
  tags: string[];
  conversation: [string, string][];
}

interface SearchResultItem {
  id: string;
  score: number;
  similarity_percent: number;
  intent: string;
  category: string;
  priority: string;
  sop?: string;
  result?: string;
  context: Record<string, string>;
  first_user_query?: string;
  last_assistant_solution?: string;
  solution_steps?: string[];
  content: string;
}

interface EvaluationItem {
  id: string;
  query: string;
  retrieved_docs: string[];
  generated_reply: string;
  rating: number;
  is_sop_correct: boolean;
  is_helpful: boolean;
  feedback_notes?: string;
  evaluator_name: string;
  created_at: string;
}

/* ─────────────────────────── CONSTANTES & HELPERS ─────────────────────────── */

const PRIORITY_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  P1: { label: 'P1 · Critique', color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  P2: { label: 'P2 · Élevée', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
  P3: { label: 'P3 · Moyenne', color: '#eab308', bg: 'rgba(234,179,8,0.12)' },
  P4: { label: 'P4 · Basse', color: '#22c55e', bg: 'rgba(34,197,94,0.12)' },
};

const QUICK_QUERIES = [
  'Mot de passe oublié et compte AD verrouillé',
  'Mon imprimante ne répond plus et reste hors ligne',
  'Le VPN se déconnecte toutes les 10 minutes',
  'Accès refusé au dossier SharePoint Finance',
  'Écran bleu Windows au démarrage avec code erreur',
  'Teams ne détecte pas mon microphone Jabra',
  'Outlook ne synchronise plus mes nouveaux e-mails',
];

const RAGDashboard: React.FC = () => {
  /* Onglets : recherche en premier car c'est le coeur du RAG Explorer */
  const [activeTab, setActiveTab] = useState<'search' | 'dataset' | 'evaluation' | 'history'>('search');

  /* Recherche sémantique */
  const [problemQuery, setProblemQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchElapsedMs, setSearchElapsedMs] = useState<number | null>(null);
  const [topK, setTopK] = useState<number>(5);
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [sortBy, setSortBy] = useState<'score' | 'priority' | 'category'>('score');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  /* Modal de conversation complète */
  const [selectedDoc, setSelectedDoc] = useState<DocDetail | null>(null);

  /* Dataset explorer */
  const [datasetData, setDatasetData] = useState<DatasetResponse | null>(null);
  const [loadingDataset, setLoadingDataset] = useState(false);
  const [datasetSearch, setDatasetSearch] = useState('');
  const [datasetCategory, setDatasetCategory] = useState('');
  const [datasetPriority, setDatasetPriority] = useState('');

  /* Test de génération & Évaluation */
  const [evalQuery, setEvalQuery] = useState('');
  const [generatedReply, setGeneratedReply] = useState('');
  const [generating, setGenerating] = useState(false);
  const [evalMeta, setEvalMeta] = useState<{ source: string; elapsed_ms: number; docs_used: number } | null>(null);
  const [rating, setRating] = useState<number>(0);
  const [isSopCorrect, setIsSopCorrect] = useState<boolean | null>(null);
  const [isHelpful, setIsHelpful] = useState<boolean | null>(null);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [submittingEval, setSubmittingEval] = useState(false);

  /* Historique des évaluations */
  const [evaluations, setEvaluations] = useState<EvaluationItem[]>([]);
  const [evalStats, setEvalStats] = useState<{
    total: number;
    avg_rating: number;
    sop_accuracy_pct: number;
    helpfulness_pct: number;
  } | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  /* Réindexation */
  const [reindexing, setReindexing] = useState(false);

  /* ─────────────────────────── RECHERCHE FAISS ─────────────────────────── */

  const handleSearchSolutions = async (customQuery?: string) => {
    const q = (customQuery !== undefined ? customQuery : problemQuery).trim();
    if (!q) {
      toast.error('Veuillez décrire le problème informatique à rechercher.');
      return;
    }
    setSearching(true);
    setSearchElapsedMs(null);
    try {
      const payload: Record<string, any> = {
        query: q,
        top_k: topK,
        min_score: 0.25,
      };
      if (filterCategory) {
        payload.filter_category = filterCategory;
      }
      const { data } = await api.post('/rag/search', payload);
      setSearchResults(data.results || []);
      setSearchElapsedMs(data.elapsed_ms ?? null);
      if (!data.results || data.results.length === 0) {
        toast('Aucune solution vectorielle trouvée pour cette requête.', { icon: 'ℹ️' });
      } else {
        toast.success(`${data.results.length} solutions les plus proches trouvées !`);
      }
    } catch {
      toast.error('Erreur lors de la recherche vectorielle FAISS.');
    } finally {
      setSearching(false);
    }
  };

  /* Tri des résultats de recherche */
  const sortedSearchResults = useMemo(() => {
    const items = [...searchResults];
    if (sortBy === 'score') {
      return items.sort((a, b) => b.score - a.score);
    }
    if (sortBy === 'priority') {
      const pOrder: Record<string, number> = { P1: 1, P2: 2, P3: 3, P4: 4 };
      return items.sort((a, b) => (pOrder[a.priority] || 99) - (pOrder[b.priority] || 99));
    }
    if (sortBy === 'category') {
      return items.sort((a, b) => a.category.localeCompare(b.category));
    }
    return items;
  }, [searchResults, sortBy]);

  /* Copie rapide d'une solution dans le presse-papier */
  const handleCopySolution = (text: string, id: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success('Solution copiée dans le presse-papier !');
    setTimeout(() => setCopiedId(null), 2500);
  };

  /* Chargement détail d'une conversation */
  const handleOpenDocModal = async (docId: string) => {
    try {
      const { data } = await api.get(`/rag/dataset/${docId}`);
      setSelectedDoc(data);
    } catch {
      toast.error('Impossible de charger le dialogue complet.');
    }
  };

  /* ─────────────────────────── DATASET EXPLORER ─────────────────────────── */

  const fetchDataset = useCallback(async () => {
    setLoadingDataset(true);
    try {
      const params: Record<string, string> = { skip: '0', limit: '50' };
      if (datasetSearch) params.search = datasetSearch;
      if (datasetCategory) params.category = datasetCategory;
      if (datasetPriority) params.priority = datasetPriority;

      const { data } = await api.get('/rag/dataset', { params });
      setDatasetData(data);
    } catch {
      toast.error('Erreur lors du chargement du dataset.');
    } finally {
      setLoadingDataset(false);
    }
  }, [datasetSearch, datasetCategory, datasetPriority]);

  useEffect(() => {
    if (activeTab === 'dataset') {
      fetchDataset();
    }
  }, [activeTab, fetchDataset]);

  /* ─────────────────────────── HISTORIQUE & ÉVALUATION ─────────────────────────── */

  const fetchEvaluationsHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const { data } = await api.get('/rag/evaluations');
      setEvaluations(data.evaluations || []);
      setEvalStats({
        total: data.total_evaluations || 0,
        avg_rating: data.average_rating || 0,
        sop_accuracy_pct: data.sop_accuracy_pct || 0,
        helpfulness_pct: data.helpfulness_pct || 0,
      });
    } catch {
      toast.error('Erreur lors du chargement de l\'historique.');
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'history') {
      fetchEvaluationsHistory();
    }
  }, [activeTab, fetchEvaluationsHistory]);

  /* Génération RAG + LLM pour évaluation */
  const handleGenerateReply = async () => {
    const q = evalQuery.trim();
    if (!q) {
      toast.error('Veuillez saisir une requête pour tester la génération.');
      return;
    }
    setGenerating(true);
    setGeneratedReply('');
    setEvalMeta(null);
    setRating(0);
    setIsSopCorrect(null);
    setIsHelpful(null);
    setFeedbackNotes('');

    try {
      const { data } = await api.post('/rag/test-generate', { query: q, top_k: 3 });
      const reply = data.generated_reply || data.reply || '';
      setGeneratedReply(reply);
      setEvalMeta({
        source: data.source || 'rag',
        elapsed_ms: data.elapsed_ms || 0,
        docs_used: data.docs_used || data.retrieved_count || 0,
      });
      toast.success('Réponse générée par RAG avec succès !');
    } catch {
      toast.error('Erreur lors de la génération IA.');
    } finally {
      setGenerating(false);
    }
  };

  /* Soumission d'évaluation */
  const handleSubmitEvaluation = async () => {
    if (!evalQuery.trim() || !generatedReply) {
      toast.error('Veuillez générer une réponse avant de soumettre.');
      return;
    }
    if (rating === 0) {
      toast.error('Veuillez attribuer une note (1 à 5 étoiles).');
      return;
    }
    if (isSopCorrect === null) {
      toast.error('Veuillez indiquer si le SOP est correct.');
      return;
    }
    if (isHelpful === null) {
      toast.error('Veuillez indiquer si la solution est utile.');
      return;
    }

    setSubmittingEval(true);
    try {
      await api.post('/rag/evaluate', {
        query: evalQuery,
        retrieved_docs: searchResults.map(r => r.id),
        generated_reply: generatedReply,
        rating,
        is_sop_correct: isSopCorrect,
        is_helpful: isHelpful,
        feedback_notes: feedbackNotes || undefined,
      });
      toast.success('Évaluation enregistrée avec succès !');
      setRating(0);
      setIsSopCorrect(null);
      setIsHelpful(null);
      setFeedbackNotes('');
    } catch {
      toast.error('Erreur lors de l\'enregistrement de l\'évaluation.');
    } finally {
      setSubmittingEval(false);
    }
  };

  /* Réindexation globale */
  const handleReindex = async () => {
    setReindexing(true);
    try {
      await api.post('/chat/reindex');
      toast.success('Réindexation FAISS terminée (250 documents indexés) !');
    } catch {
      toast.error('Erreur lors de la réindexation FAISS.');
    } finally {
      setReindexing(false);
    }
  };

  /* Basculer une recherche vers l'évaluation */
  const handleTransferToEval = (queryText: string) => {
    setEvalQuery(queryText);
    setActiveTab('evaluation');
  };

  /* ─────────────────────────── RENDU UI ─────────────────────────── */

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1400px', margin: '0 auto', color: '#0f172a' }}>

      {/* ── EN-TÊTE PRINCIPAL ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '1.75rem',
        flexWrap: 'wrap',
        gap: '1rem',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.06) 0%, rgba(139,92,246,0.04) 100%)',
        padding: '1.25rem 1.5rem',
        borderRadius: '1.25rem',
        border: '1px solid rgba(99,102,241,0.15)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: 46,
            height: 46,
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 20px rgba(99,102,241,0.35)'
          }}>
            <Sparkles size={24} color="white" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <h1 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#0f172a', margin: 0, letterSpacing: '-0.02em' }}>
                RAG Explorer
              </h1>
              <span style={{
                background: 'rgba(99,102,241,0.12)',
                color: '#6366f1',
                padding: '0.2rem 0.6rem',
                borderRadius: '999px',
                fontSize: '0.72rem',
                fontWeight: 700
              }}>
                FAISS · MiniLM-L12-v2
              </span>
            </div>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0.25rem 0 0 0' }}>
              Moteur de recherche sémantique vectorielle pour identifier immédiatement les solutions IT les plus proches
            </p>
          </div>
        </div>

        <button
          onClick={handleReindex}
          disabled={reindexing}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 1.1rem',
            borderRadius: '0.75rem',
            background: 'white',
            border: '1px solid #e2e8f0',
            color: '#475569',
            fontWeight: 700,
            fontSize: '0.82rem',
            cursor: reindexing ? 'not-allowed' : 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            transition: 'all 0.15s'
          }}
        >
          <RefreshCw size={15} className={reindexing ? 'spin' : ''} />
          {reindexing ? 'Réindexation en cours…' : 'Réindexer FAISS'}
        </button>
      </div>

      {/* ── BARRE D'ONGLETS ── */}
      <div style={{
        display: 'flex',
        gap: '0.4rem',
        background: '#f1f5f9',
        borderRadius: '0.875rem',
        padding: '0.35rem',
        marginBottom: '1.75rem',
        width: 'fit-content',
        flexWrap: 'wrap'
      }}>
        <button
          onClick={() => setActiveTab('search')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.55rem 1.25rem',
            borderRadius: '0.65rem',
            border: 'none',
            fontWeight: 700,
            fontSize: '0.84rem',
            cursor: 'pointer',
            background: activeTab === 'search' ? '#6366f1' : 'transparent',
            color: activeTab === 'search' ? 'white' : '#64748b',
            boxShadow: activeTab === 'search' ? '0 4px 12px rgba(99,102,241,0.25)' : 'none',
            transition: 'all 0.15s'
          }}
        >
          <Search size={15} />
          Recherche de Solutions
        </button>

        <button
          onClick={() => setActiveTab('dataset')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.55rem 1.25rem',
            borderRadius: '0.65rem',
            border: 'none',
            fontWeight: 700,
            fontSize: '0.84rem',
            cursor: 'pointer',
            background: activeTab === 'dataset' ? '#6366f1' : 'transparent',
            color: activeTab === 'dataset' ? 'white' : '#64748b',
            boxShadow: activeTab === 'dataset' ? '0 4px 12px rgba(99,102,241,0.25)' : 'none',
            transition: 'all 0.15s'
          }}
        >
          <Layers size={15} />
          Dataset (250 conversations)
        </button>

        <button
          onClick={() => setActiveTab('evaluation')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.55rem 1.25rem',
            borderRadius: '0.65rem',
            border: 'none',
            fontWeight: 700,
            fontSize: '0.84rem',
            cursor: 'pointer',
            background: activeTab === 'evaluation' ? '#6366f1' : 'transparent',
            color: activeTab === 'evaluation' ? 'white' : '#64748b',
            boxShadow: activeTab === 'evaluation' ? '0 4px 12px rgba(99,102,241,0.25)' : 'none',
            transition: 'all 0.15s'
          }}
        >
          <Sparkles size={15} />
          Génération & Évaluation IA
        </button>

        <button
          onClick={() => setActiveTab('history')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.55rem 1.25rem',
            borderRadius: '0.65rem',
            border: 'none',
            fontWeight: 700,
            fontSize: '0.84rem',
            cursor: 'pointer',
            background: activeTab === 'history' ? '#6366f1' : 'transparent',
            color: activeTab === 'history' ? 'white' : '#64748b',
            boxShadow: activeTab === 'history' ? '0 4px 12px rgba(99,102,241,0.25)' : 'none',
            transition: 'all 0.15s'
          }}
        >
          <Activity size={15} />
          Historique & Métriques
        </button>
      </div>

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── ONGLET 1 : RECHERCHE DE SOLUTIONS LES PLUS PROCHES ──────────── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeTab === 'search' && (
        <div>
          {/* Boîte de recherche de problème */}
          <div style={{
            background: 'white',
            borderRadius: '1.25rem',
            border: '1px solid #e2e8f0',
            padding: '1.5rem',
            boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
            marginBottom: '1.5rem'
          }}>
            <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 800, color: '#1e293b', marginBottom: '0.6rem' }}>
              🔍 Décrivez le problème ou la panne de l'utilisateur :
            </label>

            <div style={{ position: 'relative', marginBottom: '0.85rem' }}>
              <textarea
                value={problemQuery}
                onChange={e => setProblemQuery(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    handleSearchSolutions();
                  }
                }}
                placeholder="Exemple : Mon mot de passe est refusé, mon compte Windows est verrouillé après plusieurs tentatives..."
                style={{
                  width: '100%',
                  minHeight: '95px',
                  padding: '0.875rem 1rem',
                  borderRadius: '0.875rem',
                  border: '1.5px solid #cbd5e1',
                  fontSize: '0.92rem',
                  color: '#0f172a',
                  background: '#f8fafc',
                  outline: 'none',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                  lineHeight: 1.5,
                  transition: 'border-color 0.15s'
                }}
              />
            </div>

            {/* Suggestions rapides */}
            <div style={{ marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginRight: '0.5rem' }}>
                Cas fréquents :
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.4rem' }}>
                {QUICK_QUERIES.map(q => (
                  <button
                    key={q}
                    onClick={() => {
                      setProblemQuery(q);
                      handleSearchSolutions(q);
                    }}
                    style={{
                      background: '#f1f5f9',
                      border: '1px solid #e2e8f0',
                      borderRadius: '999px',
                      padding: '0.3rem 0.75rem',
                      fontSize: '0.74rem',
                      fontWeight: 600,
                      color: '#475569',
                      cursor: 'pointer',
                      transition: 'all 0.15s'
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = 'rgba(99,102,241,0.1)';
                      e.currentTarget.style.color = '#6366f1';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = '#f1f5f9';
                      e.currentTarget.style.color = '#475569';
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Barre de contrôles & filtres */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.75rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid #f1f5f9'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                {/* Sélecteur Top K */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b' }}>Nombre :</span>
                  <select
                    value={topK}
                    onChange={e => setTopK(Number(e.target.value))}
                    style={{
                      padding: '0.4rem 0.6rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      background: 'white',
                      color: '#0f172a'
                    }}
                  >
                    <option value={3}>Top 3</option>
                    <option value={5}>Top 5</option>
                    <option value={8}>Top 8</option>
                    <option value={10}>Top 10</option>
                  </select>
                </div>

                {/* Filtre Catégorie */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Filter size={13} color="#64748b" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b' }}>Catégorie :</span>
                  <select
                    value={filterCategory}
                    onChange={e => setFilterCategory(e.target.value)}
                    style={{
                      padding: '0.4rem 0.6rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      background: 'white',
                      color: '#0f172a'
                    }}
                  >
                    <option value="">Toutes catégories</option>
                    <option value="L1">L1 · Support Premier Niveau</option>
                    <option value="qual">qual · Support Qualification</option>
                    <option value="class">class · Support Classification</option>
                  </select>
                </div>

                {/* Sélecteur de Tri */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <ArrowUpDown size={13} color="#64748b" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b' }}>Trier par :</span>
                  <select
                    value={sortBy}
                    onChange={e => setSortBy(e.target.value as any)}
                    style={{
                      padding: '0.4rem 0.6rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      background: '#f8fafc',
                      color: '#6366f1'
                    }}
                  >
                    <option value="score">Similarité sémantique (Score %)</option>
                    <option value="priority">Priorité d'urgence (P1 → P4)</option>
                    <option value="category">Catégorie IT</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => {
                    setProblemQuery('');
                    setSearchResults([]);
                    setSearchElapsedMs(null);
                  }}
                  style={{
                    padding: '0.55rem 0.9rem',
                    borderRadius: '0.65rem',
                    border: '1px solid #e2e8f0',
                    background: '#f8fafc',
                    color: '#64748b',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    cursor: 'pointer'
                  }}
                >
                  Effacer
                </button>

                <button
                  onClick={() => handleSearchSolutions()}
                  disabled={searching}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.55rem 1.4rem',
                    borderRadius: '0.65rem',
                    border: 'none',
                    background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                    color: 'white',
                    fontWeight: 700,
                    fontSize: '0.84rem',
                    cursor: searching ? 'not-allowed' : 'pointer',
                    boxShadow: '0 4px 14px rgba(99,102,241,0.3)',
                    transition: 'all 0.15s'
                  }}
                >
                  <Search size={15} />
                  {searching ? 'Recherche vectorielle…' : 'Trouver les solutions'}
                </button>
              </div>
            </div>
          </div>

          {/* ── LISTE DES SOLUTIONS TROUVÉES ── */}
          {searching && (
            <div style={{ textAlign: 'center', padding: '3.5rem', color: '#64748b' }}>
              <div style={{
                width: '40px',
                height: '40px',
                border: '3px solid rgba(99,102,241,0.2)',
                borderTopColor: '#6366f1',
                borderRadius: '50%',
                margin: '0 auto 1rem auto',
                animation: 'spin 0.8s linear infinite'
              }} />
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1e293b' }}>
                Recherche sémantique dans l'index FAISS…
              </div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                Calcul de similarité cosinus sur 250 conversations
              </div>
            </div>
          )}

          {!searching && searchResults.length > 0 && (
            <div>
              {/* Résumé de recherche */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '1rem',
                padding: '0.5rem 0.75rem',
                background: '#f8fafc',
                borderRadius: '0.75rem',
                fontSize: '0.8rem',
                color: '#64748b'
              }}>
                <div>
                  <strong>{searchResults.length}</strong> solutions candidates trouvées
                  {searchElapsedMs !== null && (
                    <span> en <strong style={{ color: '#22c55e' }}>{searchElapsedMs} ms</strong></span>
                  )}
                  {filterCategory && <span> (filtre: <strong>{filterCategory}</strong>)</span>}
                </div>
                <div style={{ fontSize: '0.74rem' }}>
                  Tri actuel : <strong>
                    {sortBy === 'score' ? 'Similarité décroissante' : sortBy === 'priority' ? 'Priorité P1 → P4' : 'Catégorie'}
                  </strong>
                </div>
              </div>

              {/* Cartes de solutions détaillées */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {sortedSearchResults.map((sol, index) => {
                  const prioInfo = PRIORITY_BADGES[sol.priority] || { label: sol.priority, color: '#64748b', bg: '#f1f5f9' };
                  const isTopMatch = index === 0 && sortBy === 'score';
                  const simPct = sol.similarity_percent;
                  const simColor = simPct >= 50 ? '#22c55e' : simPct >= 38 ? '#eab308' : '#f97316';

                  return (
                    <div
                      key={sol.id}
                      style={{
                        background: 'white',
                        borderRadius: '1.25rem',
                        border: isTopMatch ? '2px solid #6366f1' : '1px solid #e2e8f0',
                        boxShadow: isTopMatch
                          ? '0 8px 30px rgba(99,102,241,0.12)'
                          : '0 2px 8px rgba(0,0,0,0.04)',
                        padding: '1.25rem 1.5rem',
                        position: 'relative',
                        transition: 'all 0.15s'
                      }}
                    >
                      {/* Badge Top Match */}
                      {isTopMatch && (
                        <div style={{
                          position: 'absolute',
                          top: '-11px',
                          left: '20px',
                          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                          color: 'white',
                          padding: '0.15rem 0.65rem',
                          borderRadius: '999px',
                          fontSize: '0.68rem',
                          fontWeight: 800,
                          letterSpacing: '0.04em',
                          textTransform: 'uppercase',
                          boxShadow: '0 2px 8px rgba(99,102,241,0.3)'
                        }}>
                          ★ Solution la plus proche
                        </div>
                      )}

                      {/* Header de la carte */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '0.75rem',
                        marginBottom: '0.85rem'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                          <span style={{
                            fontSize: '0.78rem',
                            fontWeight: 800,
                            color: '#6366f1',
                            background: 'rgba(99,102,241,0.08)',
                            padding: '0.25rem 0.6rem',
                            borderRadius: '0.5rem'
                          }}>
                            #{index + 1} · {sol.id}
                          </span>

                          <span style={{
                            fontSize: '0.88rem',
                            fontWeight: 800,
                            color: '#0f172a'
                          }}>
                            {sol.intent}
                          </span>

                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '0.2rem 0.55rem',
                            borderRadius: '999px',
                            background: prioInfo.bg,
                            color: prioInfo.color
                          }}>
                            {prioInfo.label}
                          </span>

                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            padding: '0.2rem 0.55rem',
                            borderRadius: '999px',
                            background: '#f1f5f9',
                            color: '#475569'
                          }}>
                            Catégorie : {sol.category}
                          </span>
                        </div>

                        {/* Similarité */}
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          background: '#f8fafc',
                          padding: '0.35rem 0.75rem',
                          borderRadius: '0.65rem',
                          border: '1px solid #e2e8f0'
                        }}>
                          <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>Similarité :</span>
                          <span style={{ fontSize: '0.88rem', fontWeight: 800, color: simColor }}>
                            {simPct.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {/* Question initiale de l'utilisateur */}
                      {sol.first_user_query && (
                        <div style={{
                          fontSize: '0.8rem',
                          color: '#475569',
                          marginBottom: '0.85rem',
                          background: '#f8fafc',
                          padding: '0.6rem 0.85rem',
                          borderRadius: '0.65rem',
                          borderLeft: '3px solid #cbd5e1'
                        }}>
                          <strong style={{ color: '#1e293b' }}>Question / Symptôme utilisateur : </strong>
                          « {sol.first_user_query} »
                        </div>
                      )}

                      {/* ── ENCADRÉ DE RÉSOLUTION DU PROBLÈME (GUIDE PAS-À-PAS) ── */}
                      <div style={{
                        background: 'linear-gradient(135deg, rgba(99,102,241,0.06) 0%, rgba(139,92,246,0.03) 100%)',
                        border: '1.5px solid rgba(99,102,241,0.25)',
                        borderRadius: '0.875rem',
                        padding: '1rem 1.25rem',
                        marginBottom: '0.85rem'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{
                              width: 26,
                              height: 26,
                              borderRadius: '0.4rem',
                              background: '#6366f1',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center'
                            }}>
                              <Wrench size={14} />
                            </div>
                            <div>
                              <div style={{ fontSize: '0.84rem', fontWeight: 800, color: '#312e81', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                Comment résoudre ce problème
                              </div>
                              <div style={{ fontSize: '0.7rem', color: '#6366f1', fontWeight: 600 }}>
                                Procédure technique validée par le support
                              </div>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            {sol.result && (
                              <span style={{
                                background: 'rgba(34,197,94,0.12)',
                                color: '#16a34a',
                                padding: '0.18rem 0.55rem',
                                borderRadius: '0.4rem',
                                fontSize: '0.7rem',
                                fontWeight: 800
                              }}>
                                ✓ Statut : {sol.result}
                              </span>
                            )}
                            {sol.sop && (
                              <span style={{
                                background: 'rgba(99,102,241,0.15)',
                                color: '#4338ca',
                                padding: '0.2rem 0.6rem',
                                borderRadius: '0.5rem',
                                fontSize: '0.74rem',
                                fontWeight: 800
                              }}>
                                SOP : {sol.sop}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Étapes pas-à-pas ou texte de solution */}
                        {sol.solution_steps && sol.solution_steps.length > 1 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                            {sol.solution_steps.map((stepText, sIdx) => (
                              <div
                                key={sIdx}
                                style={{
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: '0.65rem',
                                  background: 'white',
                                  padding: '0.6rem 0.85rem',
                                  borderRadius: '0.65rem',
                                  border: '1px solid rgba(99,102,241,0.15)'
                                }}
                              >
                                <span style={{
                                  background: '#6366f1',
                                  color: 'white',
                                  fontSize: '0.7rem',
                                  fontWeight: 800,
                                  borderRadius: '999px',
                                  padding: '0.1rem 0.5rem',
                                  flexShrink: 0,
                                  marginTop: 1
                                }}>
                                  Étape {sIdx + 1}
                                </span>
                                <span style={{
                                  fontSize: '0.86rem',
                                  color: '#0f172a',
                                  lineHeight: 1.55,
                                  fontWeight: 500,
                                  whiteSpace: 'pre-wrap'
                                }}>
                                  {stepText}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{
                            background: 'white',
                            padding: '0.75rem 0.95rem',
                            borderRadius: '0.65rem',
                            border: '1px solid rgba(99,102,241,0.15)',
                            fontSize: '0.88rem',
                            color: '#0f172a',
                            lineHeight: 1.6,
                            fontWeight: 600,
                            whiteSpace: 'pre-wrap'
                          }}>
                            {sol.last_assistant_solution || (
                              <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                                Consultez le dialogue complet pour voir la démarche détaillée.
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Métadonnées contextuelles & Actions */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '0.75rem',
                        paddingTop: '0.5rem'
                      }}>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', fontSize: '0.74rem', color: '#64748b' }}>
                          {sol.context?.app && <span>App: <strong>{sol.context.app}</strong></span>}
                          {sol.context?.os && <span>· OS: <strong>{sol.context.os}</strong></span>}
                          {sol.context?.imp && <span>· Impact: <strong>{sol.context.imp}</strong></span>}
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {sol.last_assistant_solution && (
                            <button
                              onClick={() => handleCopySolution(sol.last_assistant_solution || '', sol.id)}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '0.4rem 0.75rem',
                                borderRadius: '0.5rem',
                                border: '1px solid #e2e8f0',
                                background: 'white',
                                color: copiedId === sol.id ? '#16a34a' : '#475569',
                                fontSize: '0.76rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                transition: 'all 0.15s'
                              }}
                            >
                              {copiedId === sol.id ? <Check size={13} /> : <Copy size={13} />}
                              {copiedId === sol.id ? 'Copié !' : 'Copier la solution'}
                            </button>
                          )}

                          <button
                            onClick={() => handleOpenDocModal(sol.id)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              padding: '0.4rem 0.75rem',
                              borderRadius: '0.5rem',
                              border: '1px solid #cbd5e1',
                              background: '#f8fafc',
                              color: '#334155',
                              fontSize: '0.76rem',
                              fontWeight: 700,
                              cursor: 'pointer'
                            }}
                          >
                            <MessageSquare size={13} />
                            Dialogue complet
                          </button>

                          <button
                            onClick={() => handleTransferToEval(problemQuery || sol.first_user_query || '')}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              padding: '0.4rem 0.75rem',
                              borderRadius: '0.5rem',
                              border: 'none',
                              background: 'rgba(99,102,241,0.1)',
                              color: '#6366f1',
                              fontSize: '0.76rem',
                              fontWeight: 700,
                              cursor: 'pointer'
                            }}
                          >
                            <Sparkles size={13} />
                            Tester réponse IA
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!searching && searchResults.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '3.5rem 1.5rem',
              background: 'white',
              borderRadius: '1.25rem',
              border: '1px dashed #cbd5e1',
              color: '#94a3b8'
            }}>
              <Lightbulb size={36} color="#cbd5e1" style={{ marginBottom: '0.75rem' }} />
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#475569' }}>
                Aucune recherche active
              </div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem', maxWidth: '450px', margin: '0.25rem auto 0 auto' }}>
                Tapez un problème dans la boîte ci-dessus ou cliquez sur une suggestion rapide pour afficher les solutions et procédures SOP correspondantes.
              </div>
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── ONGLET 2 : EXPLORATEUR DU DATASET (250 DOCS) ────────────────── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeTab === 'dataset' && (
        <div>
          {/* Métriques globales */}
          {datasetData && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
              {[
                { label: 'Conversations indexées', value: datasetData.total_dataset_count, icon: <FileText size={16} />, color: '#6366f1' },
                { label: 'Catégories IT', value: datasetData.categories.length, icon: <Layers size={16} />, color: '#8b5cf6' },
                { label: 'Procédures SOP', value: datasetData.sops_count, icon: <CheckCircle2 size={16} />, color: '#22c55e' },
                { label: 'Intentions distinctes', value: datasetData.intents.length, icon: <MessageSquare size={16} />, color: '#f97316' },
              ].map(s => (
                <div key={s.label} style={{
                  background: 'white',
                  borderRadius: '1rem',
                  padding: '1rem',
                  border: '1px solid #e2e8f0',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem'
                }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: '0.5rem',
                    background: s.color + '15',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: s.color
                  }}>
                    {s.icon}
                  </div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '1.2rem', color: '#0f172a' }}>{s.value}</div>
                    <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Filtres de recherche dataset */}
          <div style={{
            background: 'white',
            borderRadius: '1rem',
            border: '1px solid #e2e8f0',
            padding: '1rem',
            marginBottom: '1rem',
            display: 'flex',
            gap: '0.75rem',
            flexWrap: 'wrap',
            alignItems: 'center'
          }}>
            <div style={{ flex: 1, minWidth: 220, position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
              <input
                type="text"
                placeholder="Filtrer par mot-clé, intention, SOP..."
                value={datasetSearch}
                onChange={e => setDatasetSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchDataset()}
                style={{
                  width: '100%',
                  padding: '0.55rem 0.75rem 0.55rem 2.2rem',
                  borderRadius: '0.65rem',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.85rem',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <select
              value={datasetCategory}
              onChange={e => setDatasetCategory(e.target.value)}
              style={{
                padding: '0.55rem 0.75rem',
                borderRadius: '0.65rem',
                border: '1px solid #cbd5e1',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: 'white'
              }}
            >
              <option value="">Toutes catégories</option>
              {datasetData?.categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <select
              value={datasetPriority}
              onChange={e => setDatasetPriority(e.target.value)}
              style={{
                padding: '0.55rem 0.75rem',
                borderRadius: '0.65rem',
                border: '1px solid #cbd5e1',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: 'white'
              }}
            >
              <option value="">Toutes priorités</option>
              {datasetData?.priorities.map(p => <option key={p} value={p}>{p}</option>)}
            </select>

            <button
              onClick={fetchDataset}
              disabled={loadingDataset}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.55rem 1.1rem',
                borderRadius: '0.65rem',
                border: 'none',
                background: '#6366f1',
                color: 'white',
                fontWeight: 700,
                fontSize: '0.82rem',
                cursor: 'pointer'
              }}
            >
              <Search size={14} /> Filtrer
            </button>
          </div>

          {/* Grille des cartes dataset */}
          {loadingDataset ? (
            <div style={{ textAlign: 'center', padding: '3.5rem', color: '#94a3b8' }}>Chargement du dataset…</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: '1rem' }}>
              {(datasetData?.items || []).map(item => {
                const prio = PRIORITY_BADGES[item.priority] || { label: item.priority, color: '#64748b', bg: '#f1f5f9' };
                return (
                  <div
                    key={item.id}
                    style={{
                      background: 'white',
                      borderRadius: '1rem',
                      border: '1px solid #e2e8f0',
                      padding: '1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.55rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 800, fontSize: '0.82rem', color: '#6366f1' }}>{item.id}</span>
                      <span style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '999px',
                        background: prio.bg,
                        color: prio.color
                      }}>
                        {prio.label}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>
                      {item.category} · {item.intent}
                    </div>

                    <p style={{
                      fontSize: '0.8rem',
                      color: '#1e293b',
                      margin: 0,
                      lineHeight: 1.45,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {item.first_user_query}
                    </p>

                    {item.sop && (
                      <span style={{
                        alignSelf: 'flex-start',
                        background: 'rgba(99,102,241,0.1)',
                        color: '#6366f1',
                        padding: '0.15rem 0.5rem',
                        borderRadius: '0.4rem',
                        fontSize: '0.7rem',
                        fontWeight: 700
                      }}>
                        SOP: {item.sop}
                      </span>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: '0.5rem' }}>
                      <button
                        onClick={() => handleOpenDocModal(item.id)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          background: '#f8fafc',
                          border: '1px solid #e2e8f0',
                          borderRadius: '0.5rem',
                          padding: '0.35rem 0.7rem',
                          fontSize: '0.74rem',
                          fontWeight: 600,
                          color: '#475569',
                          cursor: 'pointer'
                        }}
                      >
                        <MessageSquare size={12} /> Voir dialogue
                      </button>
                      <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                        {item.turns_count} tours
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── ONGLET 3 : GÉNÉRATION & ÉVALUATION DES RÉPONSES ─────────────── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeTab === 'evaluation' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
          {/* Colonne gauche : Requête et génération */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              background: 'white',
              borderRadius: '1.25rem',
              border: '1px solid #e2e8f0',
              padding: '1.25rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
            }}>
              <h3 style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.75rem 0' }}>
                1. Requête de test pour le RAG
              </h3>
              <textarea
                value={evalQuery}
                onChange={e => setEvalQuery(e.target.value)}
                placeholder="Entrez le problème pour tester la chaîne RAG complète (FAISS + Prompt augmenté + Ollama)..."
                style={{
                  width: '100%',
                  minHeight: '100px',
                  padding: '0.75rem',
                  borderRadius: '0.75rem',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.88rem',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                  resize: 'vertical',
                  outline: 'none',
                  marginBottom: '0.75rem'
                }}
              />
              <button
                onClick={handleGenerateReply}
                disabled={generating}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.6rem 1.25rem',
                  borderRadius: '0.65rem',
                  border: 'none',
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '0.84rem',
                  cursor: generating ? 'not-allowed' : 'pointer'
                }}
              >
                <Sparkles size={15} />
                {generating ? 'Génération IA en cours…' : 'Générer réponse RAG'}
              </button>
            </div>

            {/* Réponse générée */}
            <div style={{
              background: 'white',
              borderRadius: '1.25rem',
              border: '1px solid #e2e8f0',
              padding: '1.25rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
            }}>
              <h3 style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.75rem 0' }}>
                2. Réponse générée par l'IA
              </h3>

              {evalMeta && (
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                  <span style={{
                    background: 'rgba(99,102,241,0.12)',
                    color: '#6366f1',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '999px',
                    fontSize: '0.72rem',
                    fontWeight: 700
                  }}>
                    Source : {evalMeta.source}
                  </span>
                  <span style={{
                    background: 'rgba(34,197,94,0.12)',
                    color: '#16a34a',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '999px',
                    fontSize: '0.72rem',
                    fontWeight: 700
                  }}>
                    {evalMeta.elapsed_ms} ms
                  </span>
                  <span style={{
                    background: 'rgba(249,115,22,0.12)',
                    color: '#ea580c',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '999px',
                    fontSize: '0.72rem',
                    fontWeight: 700
                  }}>
                    {evalMeta.docs_used} documents injectés
                  </span>
                </div>
              )}

              {generatedReply ? (
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '0.75rem',
                  padding: '1rem',
                  fontSize: '0.85rem',
                  color: '#1e293b',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  maxHeight: '280px',
                  overflowY: 'auto'
                }}>
                  {generatedReply}
                </div>
              ) : (
                <div style={{ color: '#94a3b8', fontSize: '0.82rem', textAlign: 'center', padding: '2rem' }}>
                  Aucune réponse générée pour le moment. Cliquez sur « Générer réponse RAG ».
                </div>
              )}
            </div>
          </div>

          {/* Colonne droite : Formulaire d'évaluation */}
          <div>
            <div style={{
              background: 'white',
              borderRadius: '1.25rem',
              border: '1px solid #e2e8f0',
              padding: '1.25rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
            }}>
              <h3 style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0f172a', margin: '0 0 1rem 0' }}>
                3. Évaluation qualité & conformité SOP
              </h3>

              {/* Note par étoiles */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.4rem' }}>
                  Note globale de pertinence :
                </div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  {[1, 2, 3, 4, 5].map(s => (
                    <button
                      key={s}
                      onClick={() => setRating(s)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}
                    >
                      <Star
                        size={26}
                        fill={s <= rating ? '#eab308' : 'none'}
                        color={s <= rating ? '#eab308' : '#cbd5e1'}
                      />
                    </button>
                  ))}
                  {rating > 0 && (
                    <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#eab308', alignSelf: 'center', marginLeft: '0.5rem' }}>
                      {rating} / 5
                    </span>
                  )}
                </div>
              </div>

              {/* Conformité SOP */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.4rem' }}>
                  La réponse suit-elle la procédure SOP appropriée ?
                </div>
                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <button
                    onClick={() => setIsSopCorrect(true)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      padding: '0.45rem 0.9rem',
                      borderRadius: '0.6rem',
                      border: '1px solid #cbd5e1',
                      background: isSopCorrect === true ? '#22c55e' : '#f8fafc',
                      color: isSopCorrect === true ? 'white' : '#475569',
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    <ThumbsUp size={14} /> Oui, conforme SOP
                  </button>

                  <button
                    onClick={() => setIsSopCorrect(false)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      padding: '0.45rem 0.9rem',
                      borderRadius: '0.6rem',
                      border: '1px solid #cbd5e1',
                      background: isSopCorrect === false ? '#ef4444' : '#f8fafc',
                      color: isSopCorrect === false ? 'white' : '#475569',
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    <ThumbsDown size={14} /> Non conforme
                  </button>
                </div>
              </div>

              {/* Utilité générale */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.4rem' }}>
                  La solution permet-elle de résoudre le problème utilisateur ?
                </div>
                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <button
                    onClick={() => setIsHelpful(true)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      padding: '0.45rem 0.9rem',
                      borderRadius: '0.6rem',
                      border: '1px solid #cbd5e1',
                      background: isHelpful === true ? '#22c55e' : '#f8fafc',
                      color: isHelpful === true ? 'white' : '#475569',
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    <ThumbsUp size={14} /> Oui, solution utile
                  </button>

                  <button
                    onClick={() => setIsHelpful(false)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      padding: '0.45rem 0.9rem',
                      borderRadius: '0.6rem',
                      border: '1px solid #cbd5e1',
                      background: isHelpful === false ? '#ef4444' : '#f8fafc',
                      color: isHelpful === false ? 'white' : '#475569',
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    <ThumbsDown size={14} /> Pas utile
                  </button>
                </div>
              </div>

              {/* Remarques et notes */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.4rem' }}>
                  Remarques et axes d'amélioration (optionnel) :
                </div>
                <textarea
                  value={feedbackNotes}
                  onChange={e => setFeedbackNotes(e.target.value)}
                  placeholder="Précisez un éventuel manque d'étape, ton inadéquat, ou proposition d'amélioration..."
                  style={{
                    width: '100%',
                    minHeight: '75px',
                    padding: '0.65rem',
                    borderRadius: '0.65rem',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.82rem',
                    fontFamily: 'inherit',
                    boxSizing: 'border-box',
                    outline: 'none',
                    resize: 'vertical'
                  }}
                />
              </div>

              <button
                onClick={handleSubmitEvaluation}
                disabled={submittingEval || !generatedReply}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.4rem',
                  borderRadius: '0.75rem',
                  border: 'none',
                  background: !generatedReply ? '#cbd5e1' : '#16a34a',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '0.84rem',
                  cursor: !generatedReply || submittingEval ? 'not-allowed' : 'pointer',
                  boxShadow: generatedReply ? '0 4px 12px rgba(22,163,74,0.3)' : 'none'
                }}
              >
                <CheckCircle2 size={16} />
                {submittingEval ? 'Enregistrement…' : "Enregistrer l'évaluation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── ONGLET 4 : HISTORIQUE DES ÉVALUATIONS & MÉTRIQUES ───────────── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {activeTab === 'history' && (
        <div>
          {/* Métriques agrégées */}
          {evalStats && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              {[
                { label: 'Total Évaluations', value: evalStats.total, color: '#6366f1' },
                { label: 'Note moyenne', value: `${evalStats.avg_rating.toFixed(2)} / 5 ★`, color: '#eab308' },
                { label: 'Conformité SOP', value: `${evalStats.sop_accuracy_pct.toFixed(0)}%`, color: '#22c55e' },
                { label: 'Taux de résolution utile', value: `${evalStats.helpfulness_pct.toFixed(0)}%`, color: '#f97316' },
              ].map(st => (
                <div key={st.label} style={{
                  background: 'white',
                  borderRadius: '1rem',
                  padding: '1.25rem',
                  border: '1px solid #e2e8f0',
                  textAlign: 'center',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.03)'
                }}>
                  <div style={{ fontWeight: 800, fontSize: '1.5rem', color: st.color, marginBottom: '0.2rem' }}>
                    {st.value}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#64748b', fontWeight: 600 }}>
                    {st.label}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.85rem' }}>
            <button
              onClick={fetchEvaluationsHistory}
              disabled={loadingHistory}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.5rem 0.9rem',
                borderRadius: '0.6rem',
                border: '1px solid #e2e8f0',
                background: 'white',
                color: '#475569',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={13} className={loadingHistory ? 'spin' : ''} />
              Actualiser l'historique
            </button>
          </div>

          {/* Liste des évaluations */}
          {loadingHistory ? (
            <div style={{ textAlign: 'center', padding: '3.5rem', color: '#94a3b8' }}>Chargement…</div>
          ) : evaluations.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '3.5rem',
              background: 'white',
              borderRadius: '1rem',
              border: '1px dashed #cbd5e1',
              color: '#94a3b8'
            }}>
              Aucune évaluation enregistrée pour le moment.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {evaluations.map(ev => (
                <div
                  key={ev.id}
                  style={{
                    background: 'white',
                    borderRadius: '1rem',
                    border: '1px solid #e2e8f0',
                    padding: '1.1rem',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.03)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0f172a', marginBottom: '0.35rem' }}>
                        « {ev.query} »
                      </div>
                      <div style={{
                        fontSize: '0.82rem',
                        color: '#475569',
                        marginBottom: '0.65rem',
                        background: '#f8fafc',
                        padding: '0.6rem 0.85rem',
                        borderRadius: '0.5rem',
                        lineHeight: 1.5,
                        maxHeight: '80px',
                        overflowY: 'auto'
                      }}>
                        {ev.generated_reply}
                      </div>

                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', gap: '0.15rem' }}>
                          {[1, 2, 3, 4, 5].map(s => (
                            <Star
                              key={s}
                              size={15}
                              fill={s <= ev.rating ? '#eab308' : 'none'}
                              color={s <= ev.rating ? '#eab308' : '#cbd5e1'}
                            />
                          ))}
                        </div>

                        <span style={{
                          background: ev.is_sop_correct ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                          color: ev.is_sop_correct ? '#16a34a' : '#dc2626',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: 700
                        }}>
                          SOP {ev.is_sop_correct ? '✓ Conforme' : '✗ Non conforme'}
                        </span>

                        <span style={{
                          background: ev.is_helpful ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                          color: ev.is_helpful ? '#16a34a' : '#dc2626',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: 700
                        }}>
                          {ev.is_helpful ? '✓ Solution Utile' : '✗ Non utile'}
                        </span>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b' }}>
                        {ev.evaluator_name}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                        {ev.created_at ? new Date(ev.created_at).toLocaleDateString('fr-FR', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        }) : ''}
                      </div>
                    </div>
                  </div>

                  {ev.feedback_notes && (
                    <div style={{
                      marginTop: '0.65rem',
                      fontSize: '0.78rem',
                      color: '#475569',
                      background: '#f8fafc',
                      borderRadius: '0.5rem',
                      padding: '0.5rem 0.75rem',
                      borderLeft: '3px solid #6366f1'
                    }}>
                      💬 <strong>Remarque de l'évaluateur :</strong> {ev.feedback_notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────── */}
      {/* ── MODAL : DIALOGUE COMPLET DE LA CONVERSATION ─────────────────── */}
      {/* ────────────────────────────────────────────────────────────────── */}
      {selectedDoc && (
        <div
          onClick={() => setSelectedDoc(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem'
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              width: '100%',
              maxWidth: '680px',
              maxHeight: '88vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              boxShadow: '0 25px 60px rgba(0,0,0,0.3)',
              border: '1px solid #e2e8f0'
            }}
          >
            {/* Header modal */}
            <div style={{
              padding: '1.2rem 1.5rem',
              borderBottom: '1px solid #f1f5f9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: '#f8fafc'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>
                    Dialogue complet · {selectedDoc.id}
                  </span>
                  <span style={{
                    background: 'rgba(99,102,241,0.1)',
                    color: '#6366f1',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '0.4rem',
                    fontSize: '0.72rem',
                    fontWeight: 700
                  }}>
                    {selectedDoc.category}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.2rem' }}>
                  Intention : <strong>{selectedDoc.intent}</strong>
                  {selectedDoc.sop && <span> · SOP : <strong>{selectedDoc.sop}</strong></span>}
                </div>
              </div>

              <button
                onClick={() => setSelectedDoc(null)}
                style={{
                  background: 'white',
                  border: '1px solid #e2e8f0',
                  borderRadius: '0.5rem',
                  padding: '0.4rem',
                  cursor: 'pointer',
                  color: '#64748b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Bulles de conversation */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.85rem'
            }}>
              {(selectedDoc.conversation || []).map(([speakerRaw, text], idx) => {
                const isUser = speakerRaw === 'u';
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: isUser ? 'flex-end' : 'flex-start'
                    }}
                  >
                    <div style={{
                      maxWidth: '80%',
                      padding: '0.75rem 1rem',
                      borderRadius: isUser ? '1rem 1rem 0.25rem 1rem' : '1rem 1rem 1rem 0.25rem',
                      background: isUser ? 'linear-gradient(135deg, #6366f1, #4f46e5)' : '#f1f5f9',
                      color: isUser ? 'white' : '#0f172a',
                      fontSize: '0.86rem',
                      lineHeight: 1.5,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                    }}>
                      <div style={{
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        marginBottom: '0.3rem',
                        opacity: isUser ? 0.85 : 0.6,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em'
                      }}>
                        {isUser ? 'Utilisateur' : 'Support IT / Assistant'}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer modal */}
            {selectedDoc.result && (
              <div style={{
                padding: '0.85rem 1.5rem',
                borderTop: '1px solid #f1f5f9',
                background: '#f8fafc',
                fontSize: '0.78rem',
                color: '#64748b',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <strong>Résultat final : </strong>
                  <span style={{ color: '#16a34a', fontWeight: 700 }}>{selectedDoc.result}</span>
                </div>
                {selectedDoc.tags && selectedDoc.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: '0.3rem' }}>
                    {selectedDoc.tags.map(t => (
                      <span key={t} style={{
                        background: '#e2e8f0',
                        color: '#475569',
                        padding: '0.1rem 0.4rem',
                        borderRadius: '0.3rem',
                        fontSize: '0.68rem'
                      }}>
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RAGDashboard;
