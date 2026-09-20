"""
Suite de tests unitaires et d'intégration pour la Sécurité et Conformité ISO/IEC 27001:2013 (GEISER).

Vérifie les 5 piliers de sécurité :
1-15:  Matrice RBAC (Permissions par Rôle : ADMIN, SUPERVISOR, AGENT, USER)
16-25: Contrôleur d'accès (RoleChecker, interdiction 403, journalisation ACCESS_DENIED)
26-38: Piste d'audit des tickets (action_history : CREATED, STATUS_CHANGED, AGENT_ASSIGNED, etc.)
39-48: Service d'Audit ISO 27001 (log_event, filtrage, pagination, statistiques, export CSV)
49-57: Journalisation des flux d'authentification (Login, 2FA, Reset de mot de passe)

Exécution : pytest test_security_audit.py -v
"""
import io
import csv
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from core.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    has_role_permission,
)
from schemas.schemas import (
    UserRole,
    TicketActionType,
    TicketActionLog,
    AuditEventCategory,
    AuditSeverity,
    TicketStatus,
)
from core.deps import RoleChecker, get_client_metadata
from services.audit_service import AuditService
from services.ticket_service import TicketService


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Tests 1 à 15 : Matrice des permissions RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_admin_has_full_permissions():
    """L'Administrateur possède les permissions critiques (suppression, gestion utilisateurs, export audit)."""
    assert has_role_permission(UserRole.ADMIN, Permission.USER_MANAGE) is True
    assert has_role_permission(UserRole.ADMIN, Permission.TICKET_DELETE) is True
    assert has_role_permission(UserRole.ADMIN, Permission.AUDIT_EXPORT) is True
    assert has_role_permission(UserRole.ADMIN, Permission.AUDIT_VIEW) is True
    assert has_role_permission(UserRole.ADMIN, Permission.SLA_OVERRIDE) is True


def test_02_supervisor_has_governance_permissions():
    """Le Superviseur peut consulter et exporter les audits, superviser les SLA, et assigner des tickets."""
    assert has_role_permission(UserRole.SUPERVISOR, Permission.AUDIT_VIEW) is True
    assert has_role_permission(UserRole.SUPERVISOR, Permission.AUDIT_EXPORT) is True
    assert has_role_permission(UserRole.SUPERVISOR, Permission.TICKET_ASSIGN) is True
    assert has_role_permission(UserRole.SUPERVISOR, Permission.SLA_VIEW) is True
    assert has_role_permission(UserRole.SUPERVISOR, Permission.TICKET_READ_ALL) is True
    # Séparation des pouvoirs : seul l'Admin peut modifier/outrepasser les SLA
    assert has_role_permission(UserRole.SUPERVISOR, Permission.SLA_OVERRIDE) is False


def test_03_supervisor_cannot_delete_ticket():
    """Conformité ITIL / Sécurité : Le superviseur ne peut PAS supprimer de tickets (réservé à l'ADMIN)."""
    assert has_role_permission(UserRole.SUPERVISOR, Permission.TICKET_DELETE) is False


def test_04_supervisor_cannot_manage_users():
    """Conformité ISO 27001 : Séparation des tâches, le superviseur ne gère pas les comptes système."""
    assert has_role_permission(UserRole.SUPERVISOR, Permission.USER_MANAGE) is False


def test_05_agent_cannot_assign_ticket():
    """Principe de moindre privilège : L'agent ne s'auto-attribue pas les tickets arbitrairement."""
    assert has_role_permission(UserRole.AGENT, Permission.TICKET_ASSIGN) is False


def test_06_agent_cannot_view_or_export_audit():
    """L'agent de support n'a pas accès à la piste d'audit de sécurité globale."""
    assert has_role_permission(UserRole.AGENT, Permission.AUDIT_VIEW) is False
    assert has_role_permission(UserRole.AGENT, Permission.AUDIT_EXPORT) is False


def test_07_agent_can_respond_and_resolve():
    """L'agent de support peut répondre aux tickets et marquer la résolution."""
    assert has_role_permission(UserRole.AGENT, Permission.TICKET_RESPOND) is True
    assert has_role_permission(UserRole.AGENT, Permission.TICKET_RESOLVE) is True
    assert has_role_permission(UserRole.AGENT, Permission.AI_USE_COPILOT) is True


def test_08_user_cannot_access_audit():
    """L'utilisateur final n'a aucun accès aux journaux d'audit."""
    assert has_role_permission(UserRole.USER, Permission.AUDIT_VIEW) is False
    assert has_role_permission(UserRole.USER, Permission.AUDIT_EXPORT) is False


def test_09_user_can_create_and_view_own_tickets():
    """L'utilisateur final peut créer un ticket et consulter ses propres incidents."""
    assert has_role_permission(UserRole.USER, Permission.TICKET_CREATE) is True
    assert has_role_permission(UserRole.USER, Permission.TICKET_READ_OWN) is True


def test_10_user_cannot_assign_or_delete_tickets():
    """L'utilisateur final n'a aucune permission administrative sur les tickets."""
    assert has_role_permission(UserRole.USER, Permission.TICKET_ASSIGN) is False
    assert has_role_permission(UserRole.USER, Permission.TICKET_DELETE) is False


def test_11_user_cannot_override_sla():
    """L'utilisateur final et l'agent ne peuvent pas modifier les politiques SLA."""
    assert has_role_permission(UserRole.USER, Permission.SLA_OVERRIDE) is False
    assert has_role_permission(UserRole.AGENT, Permission.SLA_OVERRIDE) is False


def test_12_all_roles_defined_in_matrix():
    """Tous les 4 rôles métier sont répertoriés dans la matrice ROLE_PERMISSIONS."""
    assert UserRole.ADMIN in ROLE_PERMISSIONS
    assert UserRole.SUPERVISOR in ROLE_PERMISSIONS
    assert UserRole.AGENT in ROLE_PERMISSIONS
    assert UserRole.USER in ROLE_PERMISSIONS


def test_13_permissions_hierarchy_integrity():
    """Le nombre de permissions de l'ADMIN est strictement supérieur à celui du SUPERVISOR, etc."""
    admin_count = len(ROLE_PERMISSIONS[UserRole.ADMIN])
    supervisor_count = len(ROLE_PERMISSIONS[UserRole.SUPERVISOR])
    agent_count = len(ROLE_PERMISSIONS[UserRole.AGENT])
    user_count = len(ROLE_PERMISSIONS[UserRole.USER])

    assert admin_count > supervisor_count
    assert supervisor_count > agent_count
    assert agent_count > user_count


def test_14_unknown_role_returns_false():
    """Un rôle inexistant ou None retourne False sans exception."""
    assert has_role_permission("HACKER", Permission.AUDIT_VIEW) is False
    assert has_role_permission(None, Permission.AUDIT_VIEW) is False


def test_15_string_role_compatibility():
    """has_role_permission fonctionne aussi bien avec des chaînes qu'avec l'Enum UserRole."""
    assert has_role_permission("ADMIN", Permission.TICKET_DELETE) is True
    assert has_role_permission("SUPERVISOR", Permission.AUDIT_VIEW) is True
    assert has_role_permission("USER", Permission.AUDIT_VIEW) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Tests 16 à 25 : Contrôle d'accès et détection d'intrusions (RoleChecker)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_16_role_checker_authorized_user():
    """Un utilisateur avec le rôle requis est accepté."""
    checker = RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])
    mock_user = {"id": str(ObjectId()), "email": "supervisor@geiser.tn", "role": "SUPERVISOR"}
    mock_request = MagicMock()
    mock_db = MagicMock()

    result = await checker(request=mock_request, user=mock_user, db=mock_db)
    assert result == mock_user


@pytest.mark.asyncio
async def test_17_role_checker_forbidden_user_raises_403():
    """Un utilisateur non autorisé déclenche une exception 403 Forbidden."""
    checker = RoleChecker([UserRole.ADMIN])
    mock_user = {"id": str(ObjectId()), "email": "user@geiser.tn", "role": "USER"}
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.50"
    mock_request.headers = {"User-Agent": "Mozilla/5.0"}
    mock_request.url.path = "/api/v1/audit/export"
    mock_request.method = "GET"
    mock_db = MagicMock()
    mock_db.audit_logs.insert_one = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await checker(request=mock_request, user=mock_user, db=mock_db)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_18_role_checker_logs_access_denied_audit():
    """Lorsqu'un 403 survient, un événement ACCESS_DENIED est consigné pour la conformité ISO 27001."""
    checker = RoleChecker([UserRole.ADMIN])
    user_id = str(ObjectId())
    mock_user = {"id": user_id, "email": "agent@geiser.tn", "role": "AGENT", "full_name": "Agent Dupont"}
    
    mock_request = MagicMock()
    mock_request.client.host = "10.0.0.15"
    mock_request.headers = {"User-Agent": "Mozilla/5.0 SecurityTest"}
    mock_request.url.path = "/api/v1/audit/logs"
    mock_request.method = "GET"
    mock_db = MagicMock()

    with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_log:
        with pytest.raises(HTTPException):
            await checker(request=mock_request, user=mock_user, db=mock_db)
        
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_category"] == AuditEventCategory.ACCESS_CONTROL
        assert call_kwargs["event_type"] == "ACCESS_DENIED"
        assert call_kwargs["severity"] == AuditSeverity.WARNING
        assert call_kwargs["actor_email"] == "agent@geiser.tn"
        assert call_kwargs["client_ip"] == "10.0.0.15"
        assert call_kwargs["status"] == "DENIED"


def test_19_client_metadata_extraction_forwarded_for():
    """get_client_metadata extrait correctement l'IP depuis le header X-Forwarded-For."""
    mock_request = MagicMock()
    mock_request.headers.get.side_effect = lambda k, default=None: {
        "X-Forwarded-For": "203.0.113.195, 70.41.3.18",
        "User-Agent": "Chrome/120.0"
    }.get(k, default)
    ip, ua = get_client_metadata(mock_request)
    assert ip == "203.0.113.195"
    assert ua == "Chrome/120.0"


def test_20_client_metadata_extraction_direct_ip():
    """get_client_metadata extrait correctement l'IP directe si pas de proxy."""
    mock_request = MagicMock()
    mock_request.headers.get.side_effect = lambda k, default=None: {
        "User-Agent": "Firefox/115.0"
    }.get(k, default)
    mock_request.client.host = "192.168.1.100"
    ip, ua = get_client_metadata(mock_request)
    assert ip == "192.168.1.100"
    assert ua == "Firefox/115.0"


def test_21_client_metadata_handles_none_client():
    """get_client_metadata gère élégamment les requêtes sans informations client."""
    ip, ua = get_client_metadata(None)
    assert ip == "127.0.0.1"
    assert ua == "Internal/Test"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Tests 26 à 38 : Piste d'audit des tickets (action_history)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_26_record_ticket_action_pushes_history():
    """La méthode record_ticket_action pousse un objet TicketActionLog dans le document ticket."""
    mock_db = MagicMock()
    mock_db.tickets.update_one = AsyncMock()
    svc = TicketService(mock_db)

    ticket_id = str(ObjectId())
    actor = {"id": "user123", "full_name": "Jean Dupont", "role": "AGENT"}

    await svc.record_ticket_action(
        ticket_id=ticket_id,
        action_type=TicketActionType.STATUS_CHANGED.value,
        actor_user=actor,
        details={"old_status": "OPEN", "new_status": "IN_PROGRESS"},
        comment="Prise en charge de l'incident"
    )

    mock_db.tickets.update_one.assert_called_once()
    args, kwargs = mock_db.tickets.update_one.call_args
    assert "$push" in args[1]
    history_entry = args[1]["$push"]["action_history"]
    assert history_entry["actor_name"] == "Jean Dupont"
    assert history_entry["actor_role"] == "AGENT"
    assert history_entry["action_type"] == TicketActionType.STATUS_CHANGED.value
    assert history_entry["details"]["new_status"] == "IN_PROGRESS"
    assert history_entry["comment"] == "Prise en charge de l'incident"


@pytest.mark.asyncio
async def test_27_record_ticket_action_system_fallback():
    """Si aucun acteur n'est spécifié, l'action est imputée au SYSTEM / Système."""
    mock_db = MagicMock()
    mock_db.tickets.update_one = AsyncMock()
    svc = TicketService(mock_db)

    await svc.record_ticket_action(
        ticket_id=str(ObjectId()),
        action_type=TicketActionType.SLA_RECALCULATED.value,
        actor_user=None,
        details={"sla_deadline": "2026-09-20T18:00:00Z"}
    )

    args, kwargs = mock_db.tickets.update_one.call_args
    history_entry = args[1]["$push"]["action_history"]
    assert history_entry["actor_name"] == "Système"
    assert history_entry["actor_role"] == "SYSTEM"


@pytest.mark.asyncio
async def test_28_update_status_records_action_history():
    """Changer le statut d'un ticket enregistre l'historique STATUS_CHANGED avec ancien et nouveau statut."""
    mock_db = MagicMock()
    ticket_id = ObjectId()
    mock_db.tickets.find_one = AsyncMock(return_value={"_id": ticket_id, "status": "OPEN"})
    mock_db.tickets.update_one = AsyncMock()

    svc = TicketService(mock_db)
    svc.get_ticket = AsyncMock(return_value={"id": str(ticket_id), "status": TicketStatus.IN_PROGRESS.value})
    svc.record_ticket_action = AsyncMock()

    actor = {"id": "sup1", "full_name": "Superviseur Sarah", "role": "SUPERVISOR"}
    with patch("services.ticket_service.SLAService.compute_sla_status", new_callable=AsyncMock) as mock_sla:
        mock_sla.return_value = MagicMock(value="OK")
        await svc.update_status(str(ticket_id), TicketStatus.IN_PROGRESS, actor_user=actor)

    svc.record_ticket_action.assert_called_once()
    kwargs = svc.record_ticket_action.call_args.kwargs
    assert kwargs["action_type"] == TicketActionType.STATUS_CHANGED.value
    assert kwargs["actor_user"] == actor
    assert kwargs["details"]["old_status"] == "OPEN"
    assert kwargs["details"]["new_status"] == TicketStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_29_assign_agent_records_action_history():
    """Assigner un agent enregistre l'historique AGENT_ASSIGNED."""
    mock_db = MagicMock()
    ticket_id = ObjectId()
    agent_id = ObjectId()
    mock_db.agents.find_one = AsyncMock(return_value={"_id": agent_id, "user_id": "u1"})
    mock_db.agents.update_one = AsyncMock()
    mock_db.tickets.update_one = AsyncMock()

    svc = TicketService(mock_db)
    svc.get_ticket = AsyncMock(return_value={"id": str(ticket_id), "assigned_agent_id": None})
    svc.record_ticket_action = AsyncMock()

    actor = {"id": "admin1", "full_name": "Admin Root", "role": "ADMIN"}
    await svc.assign_agent(str(ticket_id), str(agent_id), actor_user=actor)

    svc.record_ticket_action.assert_called_once()
    kwargs = svc.record_ticket_action.call_args.kwargs
    assert kwargs["action_type"] == TicketActionType.AGENT_ASSIGNED.value
    assert kwargs["details"]["assigned_agent_id"] == str(agent_id)


@pytest.mark.asyncio
async def test_30_reassign_agent_records_reassigned_action():
    """Réassigner un ticket déjà affecté enregistre AGENT_REASSIGNED."""
    mock_db = MagicMock()
    ticket_id = ObjectId()
    new_agent_id = ObjectId()
    mock_db.agents.find_one = AsyncMock(return_value={"_id": new_agent_id, "user_id": "u2"})
    mock_db.agents.update_one = AsyncMock()
    mock_db.tickets.update_one = AsyncMock()

    svc = TicketService(mock_db)
    svc.get_ticket = AsyncMock(return_value={"id": str(ticket_id), "assigned_agent_id": "old_agent_99"})
    svc.record_ticket_action = AsyncMock()

    actor = {"id": "sup1", "full_name": "Superviseur Sarah", "role": "SUPERVISOR"}
    await svc.assign_agent(str(ticket_id), str(new_agent_id), actor_user=actor)

    kwargs = svc.record_ticket_action.call_args.kwargs
    assert kwargs["action_type"] == TicketActionType.AGENT_REASSIGNED.value
    assert kwargs["details"]["from_agent_id"] == "old_agent_99"
    assert kwargs["details"]["to_agent_id"] == str(new_agent_id)


@pytest.mark.asyncio
async def test_31_delete_ticket_logs_critical_audit():
    """La suppression d'un ticket génère un événement CRITICAL dans la collection audit_logs."""
    mock_db = MagicMock()
    ticket_id = ObjectId()
    mock_db.tickets.find_one = AsyncMock(return_value={"_id": ticket_id, "subject": "Incident réseau critique", "category": "NETWORK", "priority": "URGENT"})
    mock_del_res = MagicMock()
    mock_del_res.deleted_count = 1
    mock_db.tickets.delete_one = AsyncMock(return_value=mock_del_res)

    svc = TicketService(mock_db)
    actor = {"id": "admin1", "email": "admin@geiser.tn", "full_name": "Admin Root", "role": "ADMIN"}

    with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        res = await svc.delete_ticket(str(ticket_id), actor_user=actor)
        assert res is True

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["event_category"] == AuditEventCategory.TICKET
        assert kwargs["event_type"] == "TICKET_DELETED"
        assert kwargs["severity"] == AuditSeverity.CRITICAL
        assert kwargs["actor_email"] == "admin@geiser.tn"
        assert kwargs["details"]["deleted_ticket_subject"] == "Incident réseau critique"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Tests 39 à 48 : Service d'Audit ISO 27001 (log, filtrage, stats, export CSV)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_39_audit_service_log_event_inserts_document():
    """log_event insère correctement un document d'audit complet dans MongoDB."""
    mock_db = MagicMock()
    mock_insert_res = MagicMock()
    mock_insert_res.inserted_id = ObjectId()
    mock_db.audit_logs.insert_one = AsyncMock(return_value=mock_insert_res)
    svc = AuditService(mock_db)

    result = await svc.log_event(
        event_category=AuditEventCategory.AUTH,
        event_type="AUTH_LOGIN_SUCCESS",
        severity=AuditSeverity.INFO,
        target_resource_type="auth",
        target_resource_id="user_123",
        actor_id="user_123",
        actor_email="admin@geiser.tn",
        actor_name="Admin",
        actor_role="ADMIN",
        client_ip="192.168.1.1",
        user_agent="Mozilla/5.0",
        status="SUCCESS",
        details={"session_duration": 3600}
    )

    assert result is not None
    mock_db.audit_logs.insert_one.assert_called_once()
    doc = mock_db.audit_logs.insert_one.call_args[0][0]
    assert doc["event_category"] == "AUTH"
    assert doc["event_type"] == "AUTH_LOGIN_SUCCESS"
    assert doc["severity"] == "INFO"
    assert doc["actor_email"] == "admin@geiser.tn"
    assert doc["client_ip"] == "192.168.1.1"
    assert isinstance(doc["timestamp"], datetime)


@pytest.mark.asyncio
async def test_40_audit_service_never_raises_on_db_failure():
    """ISO 27001 résilience : log_event intercepte toute erreur DB pour ne pas bloquer les transactions métier."""
    mock_db = MagicMock()
    mock_db.audit_logs.insert_one = AsyncMock(side_effect=Exception("MongoDB unreachable"))
    svc = AuditService(mock_db)

    result = await svc.log_event(
        event_category=AuditEventCategory.SYSTEM,
        event_type="SYS_TEST",
        severity=AuditSeverity.INFO,
        target_resource_type="system"
    )
    assert result is None


@pytest.mark.asyncio
async def test_41_get_audit_logs_with_filters():
    """get_audit_logs applique correctement les filtres de sévérité et catégorie."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[
        {"_id": ObjectId(), "timestamp": datetime.utcnow(), "event_category": "AUTH", "event_type": "AUTH_LOGIN_FAILURE", "severity": "WARNING", "status": "FAILURE"}
    ])
    mock_db.audit_logs.find.return_value = mock_cursor

    svc = AuditService(mock_db)
    logs = await svc.get_audit_logs(
        category="AUTH",
        severity="WARNING",
        actor_id="u_bad",
        limit=10,
        skip=0
    )

    assert len(logs) == 1
    mock_db.audit_logs.find.assert_called_once()
    query = mock_db.audit_logs.find.call_args[0][0]
    assert query["event_category"] == "AUTH"
    assert query["severity"] == "WARNING"
    assert query["actor_id"] == "u_bad"


@pytest.mark.asyncio
async def test_42_get_security_stats_aggregations():
    """get_security_stats compte fidèlement les 7 métriques ISO 27001."""
    mock_db = MagicMock()
    mock_db.audit_logs.count_documents = AsyncMock(side_effect=[
        1200,  # total_events
        1000,  # info_count
        150,   # warning_count
        50,    # critical_count
        900,   # login_successes
        45,    # login_failures
        12,    # access_denied_count
    ])

    svc = AuditService(mock_db)
    stats = await svc.get_security_stats()

    assert stats["total_events"] == 1200
    assert stats["info_count"] == 1000
    assert stats["warning_count"] == 150
    assert stats["critical_count"] == 50
    assert stats["login_successes"] == 900
    assert stats["login_failures"] == 45
    assert stats["access_denied_count"] == 12


@pytest.mark.asyncio
async def test_43_export_audit_logs_csv_rfc4180():
    """export_audit_logs_csv génère un CSV avec séparateur point-virgule."""
    mock_db = MagicMock()
    dt = datetime(2026, 9, 20, 10, 30, 0)
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "_id": ObjectId(),
            "timestamp": dt,
            "severity": "WARNING",
            "event_category": "ACCESS_CONTROL",
            "event_type": "ACCESS_DENIED",
            "actor_id": "u_99",
            "actor_email": "agent@geiser.tn",
            "actor_role": "AGENT",
            "client_ip": "10.0.0.1",
            "user_agent": "Mozilla/5.0",
            "status": "DENIED",
            "target_resource_type": "audit",
            "target_resource_id": "export",
            "details": {"attempted_role": "AGENT"}
        }
    ])
    mock_db.audit_logs.find.return_value = mock_cursor

    svc = AuditService(mock_db)
    csv_stream = await svc.export_audit_logs_csv()

    reader = csv.reader(csv_stream, delimiter=";")
    rows = list(reader)
    assert len(rows) == 2  # Header + 1 row
    header = rows[0]
    assert "Timestamp (UTC)" in header
    assert "Severity" in header
    assert "Category" in header
    assert "Client IP" in header

    data = rows[1]
    assert "WARNING" in data
    assert "ACCESS_DENIED" in data
    assert "agent@geiser.tn" in data
    assert "10.0.0.1" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Tests 49 à 52 : Audit des flux d'authentification (ISO 27001 A.9 & A.12)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_49_login_failure_logs_warning():
    """Une tentative de connexion avec mot de passe erroné enregistre AUTH_LOGIN_FAILURE (WARNING)."""
    from services.auth_service import AuthService
    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value={
        "_id": ObjectId(), "email": "victim@geiser.tn", "is_active": True, "hashed_password": "fake_hashed_pwd"
    })
    
    svc = AuthService(mock_db)
    
    with patch("services.auth_service.verify_password", return_value=False):
        with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
            user = await svc.authenticate_user("victim@geiser.tn", "wrongpassword", client_ip="198.51.100.4")
            assert user is None
            
            mock_audit.assert_called_once()
            kwargs = mock_audit.call_args.kwargs
            assert kwargs["event_type"] == "AUTH_LOGIN_FAILURE"
            assert kwargs["severity"] == AuditSeverity.WARNING
            assert kwargs["client_ip"] == "198.51.100.4"
            assert kwargs["status"] == "FAILURE"


@pytest.mark.asyncio
async def test_50_login_success_logs_info():
    """Une connexion réussie enregistre AUTH_LOGIN_SUCCESS (INFO)."""
    from services.auth_service import AuthService
    user_id = ObjectId()
    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value={
        "_id": user_id,
        "email": "agent@geiser.tn",
        "full_name": "Agent Dupont",
        "role": "AGENT",
        "is_active": True,
        "two_factor_enabled": False,
        "hashed_password": "fake_hashed_pwd"
    })
    
    svc = AuthService(mock_db)
    
    with patch("services.auth_service.verify_password", return_value=True):
        with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
            user = await svc.authenticate_user("agent@geiser.tn", "goodpassword", client_ip="10.0.0.5")
            assert user is not None
            mock_audit.assert_called_once()
            kwargs = mock_audit.call_args.kwargs
            assert kwargs["event_type"] == "AUTH_LOGIN_SUCCESS"
            assert kwargs["severity"] == AuditSeverity.INFO
            assert kwargs["client_ip"] == "10.0.0.5"
            assert kwargs["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_51_2fa_failure_logs_warning():
    """Un code OTP 2FA erroné enregistre AUTH_2FA_FAILURE."""
    from services.auth_service import AuthService
    mock_db = MagicMock()
    # Utilisateur non trouvé avec ce code OTP
    mock_db.users.find_one = AsyncMock(return_value=None)
    svc = AuthService(mock_db)

    with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        res = await svc.verify_2fa("vip@geiser.tn", "000000", client_ip="172.16.0.4")
        assert res is None
        
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["event_type"] == "AUTH_2FA_FAILURE"
        assert mock_audit.call_args.kwargs["status"] == "FAILURE"


@pytest.mark.asyncio
async def test_52_password_reset_flow_audited():
    """La demande et la validation d'un reset de mot de passe génèrent les événements d'audit requis."""
    from services.auth_service import AuthService
    user_id = ObjectId()
    reset_id = ObjectId()
    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value={"_id": user_id, "email": "forgetful@geiser.tn", "is_active": True})
    mock_db.users.update_one = AsyncMock()
    mock_db.password_resets.update_many = AsyncMock()
    mock_db.password_resets.find_one = AsyncMock(return_value={
        "_id": reset_id,
        "user_id": user_id,
        "email": "forgetful@geiser.tn",
        "expires_at": datetime(2099, 1, 1),
        "used": False
    })
    mock_db.password_resets.update_one = AsyncMock()
    mock_db.password_resets.insert_one = AsyncMock()

    svc = AuthService(mock_db)

    with patch("services.auth_service.EmailService.send_password_reset"):
        with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
            # 1. Demande de réinitialisation
            await svc.request_password_reset("forgetful@geiser.tn", client_ip="1.2.3.4")
            assert mock_audit.call_args.kwargs["event_type"] == "PASSWORD_RESET_REQUESTED"

            # 2. Validation du nouveau mot de passe
            await svc.reset_password("valid_token_abc", "NewSecurePassword123!", client_ip="1.2.3.4")
            assert mock_audit.call_args.kwargs["event_type"] == "PASSWORD_RESET_SUCCESS"
            assert mock_audit.call_args.kwargs["status"] == "SUCCESS"
