import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Play, CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronRight, Brain, Database, Cpu, BarChart3, Zap } from 'lucide-react';
import api from '../../api/axios';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type EvalStatus = 'PASS' | 'DEGRADED' | 'FAIL';
type MetricType = 'DETERMINISTIC' | 'HEURISTIC' | 'UNAVAILABLE' | 'DEEPEVAL_RAG_TRIAD' | 'DETERMINISTIC_SIMILARITY' | string;

type AIEvalSummary = {
  category_accuracy: number;
  category_f1: number;
  subcategory_accuracy: number;
  priority_accuracy: number;
  rag_hit_rate: number;
  rag_avg_score: number;
  answer_quality_score: number;
  triage_accuracy: number;
  rag_contextual_precision?: number;
  rag_contextual_recall?: number;
  deepeval_faithfulness?: number;
  deepeval_relevancy?: number;
};

type ClassificationResult = {
  metric_type: MetricType;
  dataset_size: number;
  latency_ms: number;
  fallback_used: boolean;
  llm_used: boolean;
  avg_confidence: number;
  category: { accuracy: number; macro_f1: number; macro_precision: number; macro_recall: number; correct: number; total: number };
  subcategory: { accuracy: number; macro_f1: number; correct: number; total: number };
  priority: { accuracy: number; macro_f1: number; correct: number; total: number };
  deepeval_avg_score?: number;
};

type RAGResult = {
  metric_type: MetricType;
  dataset_size: number;
  latency_ms: number;
  hit_rate_at_k: number;
  hits: number;
  total_queries: number;
  zero_result_queries: number;
  avg_top_score: number;
  avg_contextual_precision?: number;
  avg_contextual_recall?: number;
};

type AnswerQualityResult = {
  metric_type: MetricType;
  dataset_size: number;
  avg_heuristic_quality_score: number;
  avg_faithfulness?: number;
  avg_answer_relevancy?: number;
  note: string;
};

type TriageResult = {
  metric_type: MetricType;
  dataset_size: number;
  latency_ms: number;
  accuracy: number;
  correct: number;
  total: number;
};

type FullEvaluation = {
  evaluated_at: string;
  overall_status: EvalStatus;
  evaluation_framework?: string;
  total_latency_ms: number;
  ai_provider: string;
  model: string;
  ollama_available: boolean;
  ollama_detail: string;
  fallback_used: boolean;
  classification: ClassificationResult;
  rag_retrieval: RAGResult;
  answer_quality: AnswerQualityResult;
  triage_similarity: TriageResult;
  summary: AIEvalSummary;
};

type EvalStatusLight = {
  evaluated: boolean;
  overall_status: EvalStatus | null;
  evaluated_at: string | null;
  ollama_available: boolean | null;
  model: string;
  running: boolean;
  summary?: AIEvalSummary;
};

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const pct = (v: number | undefined) =>
  v !== undefined ? `${(v * 100).toFixed(1)}%` : '—';

const score = (v: number | undefined) =>
  v !== undefined ? v.toFixed(1) : '—';

function StatusBadge({ status }: { status: EvalStatus | null | undefined }) {
  if (!status) return <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)' }}>—</span>;
  const cfg = {
    PASS:     { bg: 'rgba(16,185,129,.15)', color: '#10b981', label: 'PASS' },
    DEGRADED: { bg: 'rgba(245,158,11,.15)', color: '#f59e0b', label: 'DÉGRADÉ' },
    FAIL:     { bg: 'rgba(239,68,68,.15)',  color: '#ef4444', label: 'ÉCHEC' },
  }[status] ?? { bg: 'rgba(255,255,255,.06)', color: 'rgba(255,255,255,.4)', label: status };
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 999, fontSize: '.7rem', fontWeight: 700,
      background: cfg.bg, color: cfg.color,
    }}>
      {cfg.label}
    </span>
  );
}

function MetricBadge({ type }: { type: MetricType }) {
  const cfg: Record<string, { color: string; label: string }> = {
    DEEPEVAL_RAG_TRIAD: { color: '#8b5cf6', label: 'DEEPEVAL TRIAD' },
    DETERMINISTIC_SIMILARITY: { color: '#6366f1', label: 'DEEPEVAL TESTCASE' },
    DETERMINISTIC: { color: '#6366f1', label: 'DÉTERMINISTE' },
    HEURISTIC:     { color: '#f59e0b', label: 'HEURISTIQUE' },
    UNAVAILABLE:   { color: '#9ca3af', label: 'INDISPONIBLE' },
  };
  const c = cfg[type] ?? { color: '#8b5cf6', label: String(type) };
  return (
    <span style={{
      fontSize: '.65rem', fontWeight: 700, color: c.color,
      background: `${c.color}18`, padding: '2px 8px', borderRadius: 999,
    }}>
      {c.label}
    </span>
  );
}

function GaugePct({ value, warn = 0.70, ok = 0.85 }: { value: number; warn?: number; ok?: number }) {
  const color = value >= ok ? '#10b981' : value >= warn ? '#f59e0b' : '#ef4444';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: '.85rem', fontWeight: 700, color }}>{pct(value)}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,.06)', borderRadius: 999 }}>
        <div style={{ width: `${value * 100}%`, height: '100%', borderRadius: 999, background: color, transition: 'width .5s' }} />
      </div>
    </div>
  );
}

function Section({
  title, children, icon, badge, defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  icon: React.ReactNode;
  badge?: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{
      background: 'rgba(255,255,255,.025)', border: '1px solid rgba(139,92,246,.12)',
      borderRadius: 16, overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '14px 18px', background: 'none', border: 'none', cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <span style={{ color: '#a78bfa' }}>{icon}</span>
        <span style={{ flex: 1, fontSize: '.8rem', fontWeight: 700, color: 'rgba(255,255,255,.55)', letterSpacing: '.05em', textTransform: 'uppercase' }}>{title}</span>
        {badge}
        <span style={{ color: 'rgba(255,255,255,.25)', marginLeft: 4 }}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>
      {open && <div style={{ padding: '0 18px 18px' }}>{children}</div>}
    </div>
  );
}

function StatGrid({ stats }: { stats: { label: string; value: string | number; sub?: string; color?: string }[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
      {stats.map(s => (
        <div key={s.label} style={{
          background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)',
          borderRadius: 12, padding: '12px 14px',
        }}>
          <div style={{ fontSize: '.65rem', fontWeight: 600, color: 'rgba(255,255,255,.3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>{s.label}</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: s.color ?? 'rgba(255,255,255,.9)' }}>{s.value}</div>
          {s.sub && <div style={{ fontSize: '.65rem', color: 'rgba(255,255,255,.25)', marginTop: 2 }}>{s.sub}</div>}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────

const AIEvaluationDashboard: React.FC = () => {
  const [evaluation, setEvaluation] = useState<FullEvaluation | null>(null);
  const [_status, setStatus] = useState<EvalStatusLight | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await api.get<EvalStatusLight>('/ai-eval/status');
      setStatus(r.data);
    } catch {
      // ignore status errors
    }
  }, []);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<FullEvaluation>('/ai-eval/latest');
      setEvaluation(r.data);
      setLastRefresh(new Date());
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Erreur lors du chargement de l\'évaluation.');
    } finally {
      setLoading(false);
    }
  }, []);

  const runEvaluation = async () => {
    setRunning(true);
    setError(null);
    try {
      const r = await api.post<FullEvaluation>('/ai-eval/run');
      setEvaluation(r.data);
      setLastRefresh(new Date());
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Erreur lors de l\'évaluation.');
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLatest();
  }, [fetchStatus, fetchLatest]);

  const cls = evaluation?.classification;
  const rag = evaluation?.rag_retrieval;
  const ans = evaluation?.answer_quality;
  const tri = evaluation?.triage_similarity;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 4px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'rgba(255,255,255,.95)', margin: 0 }}>
              Évaluation IA / RAG
            </h1>
            <span style={{
              padding: '3px 10px', borderRadius: 999, fontSize: '.72rem', fontWeight: 700,
              background: 'rgba(139,92,246,.18)', color: '#c084fc', border: '1px solid rgba(139,92,246,.35)',
              display: 'flex', alignItems: 'center', gap: 4
            }}>
              ⚡ Framework DeepEval
            </span>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: '.8rem', color: 'rgba(255,255,255,.35)' }}>
            Évaluation rigoureuse des composants IA (Classification, RAG Triad & Triage) avec le framework DeepEval.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {lastRefresh && (
            <span style={{ fontSize: '.68rem', color: 'rgba(255,255,255,.2)' }}>
              {lastRefresh.toLocaleTimeString('fr-FR')}
            </span>
          )}
          <button
            onClick={fetchLatest}
            disabled={loading}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', borderRadius: 10, border: '1px solid rgba(255,255,255,.08)',
              background: 'rgba(255,255,255,.04)', cursor: loading ? 'not-allowed' : 'pointer',
              color: 'rgba(255,255,255,.6)', fontSize: '.8rem', fontWeight: 600,
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Rafraîchir
          </button>
          <button
            onClick={runEvaluation}
            disabled={running}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', borderRadius: 10, border: 'none',
              background: running ? 'rgba(139,92,246,.3)' : 'linear-gradient(135deg,#7c3aed,#4f46e5)',
              cursor: running ? 'not-allowed' : 'pointer',
              color: 'white', fontSize: '.8rem', fontWeight: 700,
            }}
          >
            <Play size={13} />
            {running ? 'Évaluation en cours...' : 'Lancer l\'évaluation'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.2)',
          borderRadius: 12, padding: '12px 16px', marginBottom: 16,
          fontSize: '.8rem', color: '#f87171',
        }}>
          {error}
        </div>
      )}

      {/* Overall status banner */}
      {evaluation && (
        <div style={{
          background: evaluation.overall_status === 'PASS'
            ? 'rgba(16,185,129,.08)'
            : evaluation.overall_status === 'DEGRADED'
            ? 'rgba(245,158,11,.08)'
            : 'rgba(239,68,68,.08)',
          border: `1px solid ${evaluation.overall_status === 'PASS' ? 'rgba(16,185,129,.2)' : evaluation.overall_status === 'DEGRADED' ? 'rgba(245,158,11,.2)' : 'rgba(239,68,68,.2)'}`,
          borderRadius: 14, padding: '14px 20px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        }}>
          {evaluation.overall_status === 'PASS'
            ? <CheckCircle size={20} color="#10b981" />
            : evaluation.overall_status === 'DEGRADED'
            ? <AlertTriangle size={20} color="#f59e0b" />
            : <XCircle size={20} color="#ef4444" />}
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '.9rem', fontWeight: 700, color: 'rgba(255,255,255,.9)' }}>
                Statut global :
              </span>
              <StatusBadge status={evaluation.overall_status} />
              {evaluation.evaluation_framework && (
                <span style={{
                  fontSize: '.68rem', fontWeight: 700, color: '#a78bfa',
                  background: 'rgba(167,139,250,.12)', padding: '2px 8px', borderRadius: 999,
                }}>
                  {evaluation.evaluation_framework}
                </span>
              )}
            </div>
            <div style={{ fontSize: '.72rem', color: 'rgba(255,255,255,.3)', marginTop: 3 }}>
              Évalué le {new Date(evaluation.evaluated_at).toLocaleString('fr-FR')} •
              Durée {evaluation.total_latency_ms.toFixed(0)} ms •
              Modèle : {evaluation.model} •
              Ollama : {evaluation.ollama_available
                ? <span style={{ color: '#10b981' }}>disponible</span>
                : <span style={{ color: '#f59e0b' }}>indisponible — mode heuristique</span>}
              {evaluation.fallback_used && <> • Fallback utilisé</>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.35)' }}>
              Dataset classif. : {evaluation.classification.dataset_size} tickets
            </span>
            <span style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.35)' }}>
              RAG : {evaluation.rag_retrieval.dataset_size} requêtes
            </span>
          </div>
        </div>
      )}

      {/* Summary KPI strip */}
      {evaluation?.summary && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
          gap: 10, marginBottom: 20,
        }}>
          {[
            { label: 'Préc. catégorie', value: pct(evaluation.summary.category_accuracy), color: evaluation.summary.category_accuracy >= 0.85 ? '#10b981' : evaluation.summary.category_accuracy >= 0.70 ? '#f59e0b' : '#ef4444', sub: `F1 ${pct(evaluation.summary.category_f1)}` },
            { label: 'Préc. sous-cat.', value: pct(evaluation.summary.subcategory_accuracy), color: 'rgba(255,255,255,.8)' },
            { label: 'Préc. priorité', value: pct(evaluation.summary.priority_accuracy), color: 'rgba(255,255,255,.8)' },
            { label: 'RAG hit@K', value: pct(evaluation.summary.rag_hit_rate), color: evaluation.summary.rag_hit_rate >= 0.70 ? '#10b981' : '#f59e0b', sub: `Score moy. ${evaluation.summary.rag_avg_score.toFixed(2)}` },
            ...(evaluation.summary.deepeval_faithfulness !== undefined && evaluation.summary.deepeval_relevancy !== undefined ? [
              { label: 'DeepEval Fidélité', value: pct(evaluation.summary.deepeval_faithfulness), color: evaluation.summary.deepeval_faithfulness >= 0.80 ? '#10b981' : '#f59e0b', sub: 'Faithfulness' },
              { label: 'DeepEval Pertinence', value: pct(evaluation.summary.deepeval_relevancy), color: evaluation.summary.deepeval_relevancy >= 0.80 ? '#10b981' : '#f59e0b', sub: 'Answer Relevancy' },
            ] : [
              { label: 'Qualité réponse', value: `${score(evaluation.summary.answer_quality_score)}/100`, sub: 'heuristique', color: 'rgba(255,255,255,.8)' },
            ]),
            { label: 'Préc. triage', value: pct(evaluation.summary.triage_accuracy), color: 'rgba(255,255,255,.8)' },
          ].map(s => (
            <div key={s.label} style={{
              background: 'rgba(255,255,255,.025)', border: '1px solid rgba(139,92,246,.1)',
              borderRadius: 12, padding: '12px 14px',
            }}>
              <div style={{ fontSize: '.6rem', fontWeight: 600, color: 'rgba(255,255,255,.3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: s.color }}>{s.value}</div>
              {s.sub && <div style={{ fontSize: '.62rem', color: 'rgba(255,255,255,.25)', marginTop: 2 }}>{s.sub}</div>}
            </div>
          ))}
        </div>
      )}

      {!evaluation && !loading && (
        <div style={{
          textAlign: 'center', padding: '60px 20px',
          color: 'rgba(255,255,255,.25)', fontSize: '.85rem',
        }}>
          <Brain size={40} style={{ opacity: .3, marginBottom: 12 }} />
          <p>Aucune évaluation disponible.</p>
          <p>Cliquez sur « Lancer l'évaluation » pour obtenir les métriques.</p>
        </div>
      )}

      {loading && !evaluation && (
        <div style={{ textAlign: 'center', padding: 60, color: 'rgba(255,255,255,.3)', fontSize: '.85rem' }}>
          <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: 12 }} />
          <p>Chargement en cours...</p>
        </div>
      )}

      {evaluation && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Classification */}
          <Section title="Classification IA" icon={<Brain size={16} />} badge={<MetricBadge type={cls?.metric_type ?? 'DETERMINISTIC'} />}>
            {cls && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <StatGrid stats={[
                  { label: 'Précision catégorie', value: pct(cls.category.accuracy), color: cls.category.accuracy >= 0.85 ? '#10b981' : '#f59e0b', sub: `${cls.category.correct}/${cls.category.total} corrects` },
                  { label: 'F1 macro catégorie', value: pct(cls.category.macro_f1), color: 'rgba(255,255,255,.9)' },
                  { label: 'Précision (macro)', value: pct(cls.category.macro_precision) },
                  { label: 'Rappel (macro)', value: pct(cls.category.macro_recall) },
                  { label: 'Sous-catégorie acc.', value: pct(cls.subcategory.accuracy), sub: `${cls.subcategory.correct}/${cls.subcategory.total}` },
                  { label: 'Priorité acc.', value: pct(cls.priority.accuracy), sub: `${cls.priority.correct}/${cls.priority.total}` },
                  { label: 'Confiance moy.', value: pct(cls.avg_confidence), sub: 'heuristique' },
                  { label: 'Mode', value: cls.llm_used ? 'LLM' : 'Heuristique', color: cls.llm_used ? '#10b981' : '#f59e0b' },
                ]} />
                <div>
                  <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)', marginBottom: 6 }}>Précision catégorie</div>
                  <GaugePct value={cls.category.accuracy} />
                </div>
              </div>
            )}
          </Section>

          {/* RAG Retrieval */}
          <Section title="Récupération RAG (FAISS)" icon={<Database size={16} />} badge={<MetricBadge type={rag?.metric_type ?? 'DETERMINISTIC'} />}>
            {rag && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <StatGrid stats={[
                  { label: 'Hit rate @K', value: pct(rag.hit_rate_at_k), color: rag.hit_rate_at_k >= 0.70 ? '#10b981' : '#f59e0b', sub: `${rag.hits}/${rag.total_queries} requêtes` },
                  { label: 'Score moyen', value: rag.avg_top_score.toFixed(4) },
                  ...(evaluation?.summary?.rag_contextual_precision !== undefined ? [
                    { label: 'Préc. contextuelle', value: pct(evaluation.summary.rag_contextual_precision), sub: 'Contextual Prec.' },
                    { label: 'Rappel contextuel', value: pct(evaluation.summary.rag_contextual_recall), sub: 'Contextual Recall' },
                  ] : []),
                  { label: 'Requêtes sans résultat', value: rag.zero_result_queries, color: rag.zero_result_queries === 0 ? 'rgba(255,255,255,.8)' : '#f59e0b' },
                  { label: 'Latence', value: `${rag.latency_ms.toFixed(0)} ms`, sub: 'total dataset' },
                ]} />
                <div>
                  <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)', marginBottom: 6 }}>Hit rate @K</div>
                  <GaugePct value={rag.hit_rate_at_k} />
                </div>
                <div style={{
                  background: 'rgba(99,102,241,.08)', border: '1px solid rgba(99,102,241,.15)',
                  borderRadius: 10, padding: '10px 14px', fontSize: '.72rem', color: 'rgba(255,255,255,.4)',
                }}>
                  <strong style={{ color: 'rgba(255,255,255,.6)' }}>Note :</strong> Le hit rate et la précision contextuelle mesurent si le document attendu apparaît dans le contexte de retrieval DeepEval.
                </div>
              </div>
            )}
          </Section>

          {/* Answer Quality & DeepEval RAG Triad */}
          <Section
            title="Qualité des réponses & DeepEval RAG Triad"
            icon={<Zap size={16} />}
            badge={<MetricBadge type={ans?.metric_type ?? 'DEEPEVAL_RAG_TRIAD'} />}
          >
            {ans && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <StatGrid stats={[
                  ...(evaluation?.summary?.deepeval_faithfulness !== undefined && evaluation?.summary?.deepeval_relevancy !== undefined ? [
                    {
                      label: 'DeepEval Fidélité',
                      value: pct(evaluation.summary.deepeval_faithfulness),
                      color: evaluation.summary.deepeval_faithfulness >= 0.80 ? '#10b981' : '#f59e0b',
                      sub: 'Grounding factuel'
                    },
                    {
                      label: 'DeepEval Pertinence',
                      value: pct(evaluation.summary.deepeval_relevancy),
                      color: evaluation.summary.deepeval_relevancy >= 0.80 ? '#10b981' : '#f59e0b',
                      sub: 'Answer Relevancy'
                    },
                    {
                      label: 'Score RAG Composite',
                      value: pct(evaluation.summary.answer_quality_score),
                      color: '#a78bfa',
                      sub: 'Triad moyenne'
                    },
                  ] : [
                    { label: 'Score qualité moy.', value: `${score(ans.avg_heuristic_quality_score)}/100`, color: ans.avg_heuristic_quality_score >= 70 ? '#10b981' : '#f59e0b' },
                  ]),
                  { label: 'Cas de test DeepEval', value: ans.dataset_size, sub: 'requêtes testées' },
                ]} />

                {evaluation?.summary?.deepeval_faithfulness !== undefined && evaluation?.summary?.deepeval_relevancy !== undefined && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div>
                      <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.4)', marginBottom: 6 }}>
                        Fidélité au contexte (DeepEval Faithfulness)
                      </div>
                      <GaugePct value={evaluation.summary.deepeval_faithfulness} />
                    </div>
                    <div>
                      <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.4)', marginBottom: 6 }}>
                        Pertinence de la réponse (DeepEval Relevancy)
                      </div>
                      <GaugePct value={evaluation.summary.deepeval_relevancy} />
                    </div>
                  </div>
                )}

                <div style={{
                  background: 'rgba(139,92,246,.08)', border: '1px solid rgba(139,92,246,.2)',
                  borderRadius: 10, padding: '12px 16px', fontSize: '.74rem', color: 'rgba(255,255,255,.5)',
                  lineHeight: 1.5
                }}>
                  <strong style={{ color: '#c084fc' }}>DeepEval LLMTestCase & RAG Triad :</strong> {ans.note || 'Évalué selon les métriques de fidélité (grounding factuel) et de pertinence sémantique du framework DeepEval.'}
                </div>
              </div>
            )}
          </Section>

          {/* Triage Similarity */}
          <Section title="Triage — Similarité de tickets" icon={<BarChart3 size={16} />} badge={<MetricBadge type={tri?.metric_type ?? 'DETERMINISTIC'} />}>
            {tri && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <StatGrid stats={[
                  { label: 'Précision similarité', value: pct(tri.accuracy), color: tri.accuracy >= 0.80 ? '#10b981' : '#f59e0b', sub: `${tri.correct}/${tri.total} paires` },
                  { label: 'Paires testées', value: tri.dataset_size },
                  { label: 'Latence', value: `${tri.latency_ms.toFixed(0)} ms` },
                ]} />
                <div>
                  <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.3)', marginBottom: 6 }}>Précision triage</div>
                  <GaugePct value={tri.accuracy} />
                </div>
              </div>
            )}
          </Section>

          {/* AI Provider / model info */}
          <Section title="Environnement IA" icon={<Cpu size={16} />} defaultOpen={false}>
            <StatGrid stats={[
              { label: 'Fournisseur', value: evaluation.ai_provider.toUpperCase() },
              { label: 'Modèle', value: evaluation.model },
              { label: 'Ollama', value: evaluation.ollama_available ? '✓ Disponible' : '✗ Indisponible', color: evaluation.ollama_available ? '#10b981' : '#f59e0b' },
              { label: 'Fallback heuristique', value: evaluation.fallback_used ? 'Oui' : 'Non' },
              { label: 'Durée totale', value: `${evaluation.total_latency_ms.toFixed(0)} ms` },
            ]} />
            {evaluation.ollama_detail && !evaluation.ollama_available && (
              <div style={{ marginTop: 10, fontSize: '.72rem', color: 'rgba(255,255,255,.25)' }}>
                Détail Ollama : {evaluation.ollama_detail}
              </div>
            )}
          </Section>
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default AIEvaluationDashboard;
