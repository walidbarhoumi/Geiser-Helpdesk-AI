from enum import Enum
from typing import Set, Dict, Union
from schemas.schemas import UserRole


class Permission(str, Enum):
    # Tickets
    TICKET_CREATE = "ticket:create"
    TICKET_READ_OWN = "ticket:read_own"
    TICKET_READ_ALL = "ticket:read_all"
    TICKET_UPDATE_OWN = "ticket:update_own"
    TICKET_UPDATE_ALL = "ticket:update_all"
    TICKET_ASSIGN = "ticket:assign"
    TICKET_AUTO_ROUTE = "ticket:auto_route"
    TICKET_RESPOND = "ticket:respond"
    TICKET_RESOLVE = "ticket:resolve"
    TICKET_DELETE = "ticket:delete"
    TICKET_OVERRIDE_PRIORITY = "ticket:override_priority"

    # SLA
    SLA_VIEW = "sla:view"
    SLA_OVERRIDE = "sla:override"
    SLA_SCAN = "sla:scan"

    # Users & Teams
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"
    TEAM_VIEW = "team:view"
    TEAM_MANAGE = "team:manage"
    AGENT_VIEW = "agent:view"
    AGENT_MANAGE = "agent:manage"

    # Audit & Security (ISO 27001)
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"

    # Analytics & Reports
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # AI & System
    AI_USE_COPILOT = "ai:use_copilot"
    AI_REINDEX = "ai:reindex"
    GATEWAYS_MANAGE = "gateways:manage"


ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.USER: {
        Permission.TICKET_CREATE,
        Permission.TICKET_READ_OWN,
        Permission.TICKET_UPDATE_OWN,
    },
    UserRole.AGENT: {
        Permission.TICKET_CREATE,
        Permission.TICKET_READ_OWN,
        Permission.TICKET_READ_ALL,
        Permission.TICKET_UPDATE_ALL,
        Permission.TICKET_RESPOND,
        Permission.TICKET_RESOLVE,
        Permission.SLA_VIEW,
        Permission.TEAM_VIEW,
        Permission.AGENT_VIEW,
        Permission.AI_USE_COPILOT,
        Permission.ANALYTICS_VIEW,
    },
    UserRole.SUPERVISOR: {
        Permission.TICKET_CREATE,
        Permission.TICKET_READ_OWN,
        Permission.TICKET_READ_ALL,
        Permission.TICKET_UPDATE_ALL,
        Permission.TICKET_ASSIGN,
        Permission.TICKET_AUTO_ROUTE,
        Permission.TICKET_RESPOND,
        Permission.TICKET_RESOLVE,
        Permission.TICKET_OVERRIDE_PRIORITY,
        Permission.SLA_VIEW,
        Permission.TEAM_VIEW,
        Permission.AGENT_VIEW,
        Permission.AI_USE_COPILOT,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,
        Permission.AUDIT_VIEW,
        Permission.AUDIT_EXPORT,
    },
    UserRole.ADMIN: {
        p for p in Permission
    }
}


def has_role_permission(role: Union[UserRole, str], permission: Permission) -> bool:
    """Checks if a given role possesses the specified permission."""
    if isinstance(role, str):
        try:
            role = UserRole(role)
        except ValueError:
            return False
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms
