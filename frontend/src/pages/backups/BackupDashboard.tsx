import React, { useState, useEffect, useCallback } from 'react';
import {
  Database, RefreshCw, Plus, CheckCircle2, XCircle, AlertTriangle,
  HardDrive, ShieldCheck, Trash2, FileCheck, Play, Eye,
  Copy, Check, X
} from 'lucide-react';
import api from '../../api/axios';
import { useAuth } from '../../store/authContext';
import { UserRole, type BackupRecord, type BackupStats, type RestoreTestResult } from '../../types';
import toast from 'react-hot-toast';

/* ─── CSS Styles ─────────────────────────────────────────── */
const injectStyles = () => {
  if (document.getElementById('backup-styles')) return;
  const s = document.createElement('style');
  s.id = 'backup-styles';
  s.textContent = `
    @keyframes bkp-in { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
    @keyframes bkp-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
    .bkp-glass { background:rgba(10,10,20,.75); border:1px solid rgba(255,255,255,.07); backdrop-filter:blur(20px); border-radius:20px; }
    .bkp-row { transition:background .15s; }
    .bkp-row:hover { background:rgba(139,92,246,.06) !important; }
    .bkp-btn { transition:all .2s; cursor:pointer; }
    .bkp-btn:hover { transform:translateY(-1px); }
    .bkp-btn:disabled { opacity:.5; cursor:not-allowed; transform:none; }
  `;
  document.head.appendChild(s);
};

/* ─── Helpers ────────────────────────────────────────────── */
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

const formatDate = (isoString?: string): string => {
  if (!isoString) return 'Jamais';
  try {
    return new Date(isoString).toLocaleString('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return isoString;
  }
};

/* ─── Badges ─────────────────────────────────────────────── */
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg: Record<string, { label: string; color: string; bg: string; border: string; Icon: any }> = {
    SUCCESS:   { label: 'Réussie', color: '#34d399', bg: 'rgba(52,211,153,.12)',  border: 'rgba(52,211,153,.25)',  Icon: CheckCircle2 },
    RUNNING:   { label: 'En cours', color: '#60a5fa', bg: 'rgba(96,165,250,.12)',  border: 'rgba(96,165,250,.25)',  Icon: RefreshCw },
    FAILED:    { label: 'Échec', color: '#f87171', bg: 'rgba(248,113,113,.12)', border: 'rgba(248,113,113,.25)', Icon: XCircle },
    CORRUPTED: { label: 'Corrompue', color: '#fb923c', bg: 'rgba(251,146,60,.12)',  border: 'rgba(251,146,60,.25)',  Icon: AlertTriangle },
    DELETED:   { label: 'Supprimée', color: '#94a3b8', bg: 'rgba(148,163,184,.1)', border: 'rgba(148,163,184,.2)', Icon: Trash2 },
  };
  const { label, color, bg, border, Icon } = cfg[status] ?? cfg.SUCCESS;

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 9px', borderRadius: 999,
      background: bg, border: `1px solid ${border}`,
      fontSize: '.72rem', fontWeight: 700, color, letterSpacing: '.03em',
    }}>
      <Icon size={11} className={status === 'RUNNING' ? 'animate-spin' : ''} />
      {label}
    </span>
  );
};

const VerificationBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg: Record<string, { label: string; color: string; bg: string }> = {
    VERIFIED:  { label: 'SHA-256 Valide', color: '#34d399', bg: 'rgba(52,211,153,.1)' },
    PENDING:   { label: 'Non Vérifié', color: '#94a3b8', bg: 'rgba(148,163,184,.1)' },
    CORRUPTED: { label: 'Checksum Invalide', color: '#f87171', bg: 'rgba(248,113,113,.1)' },
    FAILED:    { label: 'Erreur Vérif', color: '#fb923c', bg: 'rgba(251,146,60,.1)' },
    SKIPPED:   { label: 'Ignoré', color: '#64748b', bg: 'rgba(100,116,139,.1)' },
  };
  const { label, color, bg } = cfg[status] ?? cfg.PENDING;
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 6,
      background: bg, color, fontSize: '.7rem', fontWeight: 600,
    }}>
      {label}
    </span>
  );
};

/* ─── Main Component ─────────────────────────────────────── */
const BackupDashboard: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === UserRole.ADMIN;

  const [backups, setBackups] = useState<BackupRecord[]>([]);
  const [stats, setStats] = useState<BackupStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningBackup, setRunningBackup] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'SUCCESS' | 'FAILED'>('all');

  // Modals state
  const [selectedBackup, setSelectedBackup] = useState<BackupRecord | null>(null);
  const [restoreTestResult, setRestoreTestResult] = useState<RestoreTestResult | null>(null);
  const [restoringTest, setRestoringTest] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => { injectStyles(); }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, statsRes] = await Promise.allSettled([
        api.get('/backups?limit=50'),
        api.get('/backups/stats'),
      ]);
      if (listRes.status === 'fulfilled') setBackups(listRes.value.data.items || []);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
    } catch {
      toast.error('Erreur lors du chargement des sauvegardes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Actions
  const handleRunBackup = async () => {
    if (!isAdmin) return;
    setRunningBackup(true);
    try {
      const res = await api.post('/backups/run');
      toast.success(`Sauvegarde '${res.data.backup_id}' initiée avec succès !`);
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Échec de la sauvegarde');
    } finally {
      setRunningBackup(false);
    }
  };

  const handleVerify = async (backupId: string) => {
    if (!isAdmin) return;
    setVerifyingId(backupId);
    try {
      const res = await api.post(`/backups/${backupId}/verify`);
      if (res.data.verified) {
        toast.success('Intégrité SHA-256 vérifiée avec succès !');
      } else {
        toast.error(`Alerte corruption : ${res.data.error || 'Empreinte invalide'}`);
      }
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur de vérification');
    } finally {
      setVerifyingId(null);
    }
  };

  const handleTestRestore = async (backupId: string) => {
    if (!isAdmin) return;
    setRestoringTest(true);
    setRestoreTestResult(null);
    try {
      const res = await api.post(`/backups/${backupId}/restore-test`);
      setRestoreTestResult(res.data);
      if (res.data.success) {
        toast.success(`Restauration isolée validée (${res.data.total_documents_restored} documents restaurés)`);
      } else {
        toast.error(`Échec du test de restauration: ${res.data.error_message}`);
      }
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors du test de restauration');
    } finally {
      setRestoringTest(false);
    }
  };

  const handleDelete = async (backupId: string) => {
    if (!isAdmin) return;
    if (!window.confirm(`Confirmez-vous la suppression définitive de l'archive '${backupId}' ?`)) return;
    try {
      await api.delete(`/backups/${backupId}`);
      toast.success('Archive de sauvegarde supprimée');
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur de suppression');
    }
  };

  const copyChecksum = (checksum: string) => {
    navigator.clipboard.writeText(checksum);
    setCopiedId(checksum);
    toast.success('Empreinte SHA-256 copiée');
    setTimeout(() => setCopiedId(null), 2500);
  };

  const filteredBackups = backups.filter(b => {
    if (activeTab === 'all') return true;
    return b.status === activeTab;
  });

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* ─── Header ─────────────────────────────────────────── */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        flexWrap: 'wrap', gap: '1.25rem', marginBottom: '2rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '40px', height: '40px', borderRadius: '12px',
              background: 'linear-gradient(135deg, rgba(124,58,237,.3), rgba(79,70,229,.3))',
              border: '1px solid rgba(139,92,246,.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c4b5fd'
            }}>
              <Database size={20} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.02em', margin: 0 }}>
                Sauvegardes & Plan de Reprise d'Activité
              </h1>
              <p style={{ fontSize: '.85rem', color: 'rgba(255,255,255,.5)', margin: '4px 0 0' }}>
                Sauvegardes MongoDB automatiques, rétention GFS, intégrité SHA-256 et tests de reprise isolés
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={fetchData}
            disabled={loading}
            className="bkp-btn"
            style={{
              padding: '.6rem 1rem', borderRadius: '10px',
              background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)',
              color: '#f1f5f9', fontSize: '.82rem', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '6px'
            }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Actualiser
          </button>

          {isAdmin && (
            <button
              onClick={handleRunBackup}
              disabled={runningBackup}
              className="bkp-btn"
              style={{
                padding: '.6rem 1.25rem', borderRadius: '10px',
                background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                border: '1px solid rgba(139,92,246,.4)',
                boxShadow: '0 4px 16px rgba(124,58,237,.3)',
                color: '#fff', fontSize: '.85rem', fontWeight: 700,
                display: 'flex', alignItems: 'center', gap: '8px'
              }}
            >
              {runningBackup ? <RefreshCw size={15} className="animate-spin" /> : <Plus size={16} />}
              {runningBackup ? 'Sauvegarde en cours...' : 'Créer une Sauvegarde'}
            </button>
          )}
        </div>
      </div>

      {/* ─── KPI Cards ──────────────────────────────────────── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '1rem', marginBottom: '2rem'
      }}>
        {/* Total Storage */}
        <div className="bkp-glass" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <span style={{ fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              Stockage Utilisé
            </span>
            <div style={{ color: '#a78bfa' }}><HardDrive size={18} /></div>
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#f1f5f9' }}>
            {formatBytes(stats?.total_storage_bytes || 0)}
          </div>
          <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', marginTop: '.25rem' }}>
            {stats?.active_backups || 0} archive(s) compressée(s)
          </div>
        </div>

        {/* Total Backups */}
        <div className="bkp-glass" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <span style={{ fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              Total Sauvegardes
            </span>
            <div style={{ color: '#60a5fa' }}><Database size={18} /></div>
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#f1f5f9' }}>
            {stats?.total_backups || 0}
          </div>
          <div style={{ fontSize: '.75rem', color: '#34d399', marginTop: '.25rem' }}>
            {stats?.verified_count || 0} vérifiée(s) avec succès
          </div>
        </div>

        {/* Last Success */}
        <div className="bkp-glass" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <span style={{ fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              Dernière Réussite
            </span>
            <div style={{ color: '#34d399' }}><CheckCircle2 size={18} /></div>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f1f5f9', marginTop: '.35rem' }}>
            {formatDate(stats?.last_successful_backup)}
          </div>
          <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', marginTop: '.25rem' }}>
            Planification quotidienne à 02:00 UTC
          </div>
        </div>

        {/* Health / Failures */}
        <div className="bkp-glass" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <span style={{ fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              État du PRA
            </span>
            <div style={{ color: (stats?.corrupted_count || 0) > 0 ? '#f87171' : '#34d399' }}>
              <ShieldCheck size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: (stats?.corrupted_count || 0) > 0 ? '#f87171' : '#34d399' }}>
            {(stats?.corrupted_count || 0) === 0 ? 'Conforme & Sain' : `${stats?.corrupted_count} Corrompue(s)`}
          </div>
          <div style={{ fontSize: '.75rem', color: 'rgba(255,255,255,.4)', marginTop: '.25rem' }}>
            {stats?.failed_count || 0} échec(s) historique(s)
          </div>
        </div>
      </div>

      {/* ─── Table Filter Tabs ──────────────────────────────── */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '1rem' }}>
        {[
          { key: 'all', label: `Toutes (${backups.length})` },
          { key: 'SUCCESS', label: `Réussies (${backups.filter(b => b.status === 'SUCCESS').length})` },
          { key: 'FAILED', label: `Échecs (${backups.filter(b => b.status === 'FAILED').length})` },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            style={{
              padding: '.45rem .9rem', borderRadius: '8px',
              background: activeTab === tab.key ? 'rgba(139,92,246,.25)' : 'rgba(255,255,255,.03)',
              border: `1px solid ${activeTab === tab.key ? 'rgba(139,92,246,.5)' : 'rgba(255,255,255,.06)'}`,
              color: activeTab === tab.key ? '#c4b5fd' : 'rgba(255,255,255,.6)',
              fontSize: '.78rem', fontWeight: 600, cursor: 'pointer',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ─── Backups Table ──────────────────────────────────── */}
      <div className="bkp-glass" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,.07)', background: 'rgba(255,255,255,.02)' }}>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>ARCHIVE & ID</th>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>DATE CRÉATION</th>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>TAILLE</th>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>TYPE / RÉTENTION</th>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>STATUT</th>
              <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)' }}>INTÉGRITÉ</th>
              {isAdmin && (
                <th style={{ padding: '1rem', fontSize: '.75rem', fontWeight: 700, color: 'rgba(255,255,255,.5)', textAlign: 'right' }}>
                  ACTIONS
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {filteredBackups.length === 0 ? (
              <tr>
                <td colSpan={isAdmin ? 7 : 6} style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255,255,255,.4)', fontSize: '.85rem' }}>
                  Aucune archive de sauvegarde trouvée.
                </td>
              </tr>
            ) : (
              filteredBackups.map(b => (
                <tr key={b.backup_id} className="bkp-row" style={{ borderBottom: '1px solid rgba(255,255,255,.04)' }}>
                  {/* Filename & ID */}
                  <td style={{ padding: '.9rem 1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Database size={15} style={{ color: '#a78bfa', flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: '.85rem', fontWeight: 600, color: '#f1f5f9' }}>
                          {b.filename}
                        </div>
                        <div style={{ fontSize: '.7rem', color: 'rgba(255,255,255,.4)', fontFamily: 'monospace' }}>
                          {b.backup_id}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Date */}
                  <td style={{ padding: '.9rem 1rem', fontSize: '.8rem', color: 'rgba(255,255,255,.7)' }}>
                    {formatDate(b.created_at)}
                  </td>

                  {/* Size */}
                  <td style={{ padding: '.9rem 1rem', fontSize: '.8rem', color: '#f1f5f9', fontWeight: 600 }}>
                    {b.status === 'SUCCESS' ? formatBytes(b.size_bytes) : '—'}
                  </td>

                  {/* Type / Retention */}
                  <td style={{ padding: '.9rem 1rem' }}>
                    <span style={{
                      padding: '2px 7px', borderRadius: 4,
                      background: 'rgba(139,92,246,.1)', color: '#c4b5fd',
                      fontSize: '.7rem', fontWeight: 600, marginRight: '6px'
                    }}>
                      {b.backup_type}
                    </span>
                    <span style={{
                      padding: '2px 7px', borderRadius: 4,
                      background: 'rgba(255,255,255,.05)', color: 'rgba(255,255,255,.6)',
                      fontSize: '.7rem'
                    }}>
                      {b.retention_class}
                    </span>
                  </td>

                  {/* Status */}
                  <td style={{ padding: '.9rem 1rem' }}>
                    <StatusBadge status={b.status} />
                  </td>

                  {/* Integrity */}
                  <td style={{ padding: '.9rem 1rem' }}>
                    <VerificationBadge status={b.verification_status} />
                  </td>

                  {/* Actions */}
                  {isAdmin && (
                    <td style={{ padding: '.9rem 1rem', textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '6px' }}>
                        {/* Verify button */}
                        <button
                          onClick={() => handleVerify(b.backup_id)}
                          disabled={verifyingId === b.backup_id || b.status !== 'SUCCESS'}
                          title="Vérifier l'empreinte SHA-256"
                          className="bkp-btn"
                          style={{
                            padding: '6px', borderRadius: '8px',
                            background: 'rgba(52,211,153,.1)', border: '1px solid rgba(52,211,153,.2)',
                            color: '#34d399', display: 'flex', alignItems: 'center'
                          }}
                        >
                          <FileCheck size={14} className={verifyingId === b.backup_id ? 'animate-spin' : ''} />
                        </button>

                        {/* Mode A Test restore */}
                        <button
                          onClick={() => handleTestRestore(b.backup_id)}
                          disabled={restoringTest || b.status !== 'SUCCESS'}
                          title="Tester la restauration en environnement isolé"
                          className="bkp-btn"
                          style={{
                            padding: '6px', borderRadius: '8px',
                            background: 'rgba(96,165,250,.1)', border: '1px solid rgba(96,165,250,.2)',
                            color: '#60a5fa', display: 'flex', alignItems: 'center'
                          }}
                        >
                          <Play size={14} className={restoringTest ? 'animate-spin' : ''} />
                        </button>

                        {/* View Details */}
                        <button
                          onClick={() => setSelectedBackup(b)}
                          title="Voir les détails et métadonnées"
                          className="bkp-btn"
                          style={{
                            padding: '6px', borderRadius: '8px',
                            background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)',
                            color: '#f1f5f9', display: 'flex', alignItems: 'center'
                          }}
                        >
                          <Eye size={14} />
                        </button>

                        {/* Delete button */}
                        <button
                          onClick={() => handleDelete(b.backup_id)}
                          title="Supprimer l'archive"
                          className="bkp-btn"
                          style={{
                            padding: '6px', borderRadius: '8px',
                            background: 'rgba(248,113,113,.1)', border: '1px solid rgba(248,113,113,.2)',
                            color: '#f87171', display: 'flex', alignItems: 'center'
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ─── Details Modal ──────────────────────────────────── */}
      {selectedBackup && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,.75)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem'
        }}>
          <div className="bkp-glass" style={{ width: '100%', maxWidth: '600px', padding: '1.75rem', position: 'relative' }}>
            <button
              onClick={() => setSelectedBackup(null)}
              style={{
                position: 'absolute', top: '16px', right: '16px',
                background: 'none', border: 'none', color: 'rgba(255,255,255,.5)',
                cursor: 'pointer', padding: '4px'
              }}
            >
              <X size={18} />
            </button>

            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#f1f5f9', margin: '0 0 1rem' }}>
              Détails de la Sauvegarde
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '.85rem' }}>
              <div>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Identifiant Unique :</span>
                <div style={{ fontFamily: 'monospace', color: '#c4b5fd', marginTop: '2px' }}>
                  {selectedBackup.backup_id}
                </div>
              </div>

              <div>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Fichier Archive :</span>
                <div style={{ color: '#f1f5f9', marginTop: '2px' }}>
                  {selectedBackup.filename}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <span style={{ color: 'rgba(255,255,255,.5)' }}>Taille brute :</span>
                  <div style={{ color: '#f1f5f9', fontWeight: 700 }}>
                    {formatBytes(selectedBackup.size_bytes)}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'rgba(255,255,255,.5)' }}>Durée de dump :</span>
                  <div style={{ color: '#f1f5f9', fontWeight: 700 }}>
                    {selectedBackup.duration_seconds}s
                  </div>
                </div>
              </div>

              {selectedBackup.checksum_sha256 && (
                <div>
                  <span style={{ color: 'rgba(255,255,255,.5)' }}>Empreinte Cryptographique SHA-256 :</span>
                  <div style={{
                    marginTop: '4px', padding: '8px 10px', borderRadius: '8px',
                    background: 'rgba(0,0,0,.4)', border: '1px solid rgba(255,255,255,.1)',
                    fontFamily: 'monospace', fontSize: '.75rem', color: '#34d399',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                  }}>
                    <span style={{ wordBreak: 'break-all' }}>{selectedBackup.checksum_sha256}</span>
                    <button
                      onClick={() => copyChecksum(selectedBackup.checksum_sha256!)}
                      style={{ background: 'none', border: 'none', color: '#a78bfa', cursor: 'pointer', marginLeft: '8px' }}
                    >
                      {copiedId === selectedBackup.checksum_sha256 ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              )}

              {selectedBackup.error_message && (
                <div style={{
                  padding: '10px', borderRadius: '8px',
                  background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)',
                  color: '#f87171', fontSize: '.8rem'
                }}>
                  <strong>Diagnostic d'erreur :</strong> {selectedBackup.error_message}
                </div>
              )}
            </div>

            <div style={{ marginTop: '1.5rem', textAlign: 'right' }}>
              <button
                onClick={() => setSelectedBackup(null)}
                style={{
                  padding: '.5rem 1.25rem', borderRadius: '8px',
                  background: 'rgba(255,255,255,.1)', border: 'none',
                  color: '#fff', fontSize: '.82rem', cursor: 'pointer'
                }}
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Mode A Isolated Restore Modal ──────────────────── */}
      {restoreTestResult && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,.75)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem'
        }}>
          <div className="bkp-glass" style={{ width: '100%', maxWidth: '580px', padding: '1.75rem', position: 'relative' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1rem' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                background: restoreTestResult.success ? 'rgba(52,211,153,.2)' : 'rgba(248,113,113,.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: restoreTestResult.success ? '#34d399' : '#f87171'
              }}>
                {restoreTestResult.success ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#f1f5f9', margin: 0 }}>
                Rapport de Test de Restauration Isolé (Mode A)
              </h3>
            </div>

            <p style={{ fontSize: '.82rem', color: 'rgba(255,255,255,.6)', lineHeight: 1.5, marginBottom: '1rem' }}>
              Ce test a vérifié l'empreinte SHA-256 de l'archive, restauré l'ensemble des données dans une
              base de données temporaire isolée <code>{restoreTestResult.test_database}</code>, vérifié
              le contenu des collections métiers, puis détruit la base de test pour préserver l'espace disque.
            </p>

            <div style={{
              background: 'rgba(0,0,0,.3)', border: '1px solid rgba(255,255,255,.08)',
              borderRadius: '12px', padding: '12px', marginBottom: '1.25rem', fontSize: '.82rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Intégrité SHA-256 :</span>
                <span style={{ color: restoreTestResult.checksum_verified ? '#34d399' : '#f87171', fontWeight: 700 }}>
                  {restoreTestResult.checksum_verified ? 'Vérifiée (Conforme)' : 'Échec Checksum'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Temps d'exécution :</span>
                <span style={{ color: '#f1f5f9', fontWeight: 700 }}>{restoreTestResult.duration_seconds}s</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Total documents restaurés :</span>
                <span style={{ color: '#34d399', fontWeight: 700 }}>{restoreTestResult.total_documents_restored}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                <span style={{ color: 'rgba(255,255,255,.5)' }}>Collections vérifiées :</span>
                <span style={{ color: '#c4b5fd', fontWeight: 700 }}>
                  {restoreTestResult.collections_found.length} collections
                </span>
              </div>
            </div>

            {restoreTestResult.error_message && (
              <div style={{
                padding: '10px', borderRadius: '8px',
                background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)',
                color: '#f87171', fontSize: '.8rem', marginBottom: '1rem'
              }}>
                {restoreTestResult.error_message}
              </div>
            )}

            <div style={{ textAlign: 'right' }}>
              <button
                onClick={() => setRestoreTestResult(null)}
                style={{
                  padding: '.5rem 1.25rem', borderRadius: '8px',
                  background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', border: 'none',
                  color: '#fff', fontSize: '.82rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Fermer le Rapport
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BackupDashboard;
