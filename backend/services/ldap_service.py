import os
import ssl
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import ldap3
from ldap3 import Server, Connection, ALL, SUBTREE, Tls
from ldap3.core.exceptions import (
    LDAPException,
    LDAPSocketOpenError,
    LDAPBindError,
    LDAPInvalidCredentialsResult,
    LDAPCommunicationError,
    LDAPResponseTimeoutError,
)

from core.config import settings
from schemas.schemas import UserRole
from models.base import MongoModel

logger = logging.getLogger(__name__)


class LdapService:
    """
    Modular, enterprise-grade LDAP / Active Directory Service for GEISER Helpdesk IA.
    Supports:
      - Active Directory (sAMAccountName, userPrincipalName) and OpenLDAP (uid, mail).
      - Secure LDAPS (port 636) and STARTTLS (port 389).
      - Configurable group-to-role mappings (Admin, Supervisor, Agent, User).
      - First-time user auto-provisioning and existing user profile synchronization.
      - Zero storage or logging of directory passwords.
    """

    def __init__(self, custom_settings=None):
        self.cfg = custom_settings or settings

    def is_enabled(self) -> bool:
        """Checks if LDAP integration is actively enabled in configuration."""
        return bool(self.cfg.LDAP_ENABLED)

    def _get_server(self) -> Server:
        """Instantiates an ldap3 Server object with configured protocol, TLS, and timeouts."""
        tls_config = None
        if self.cfg.LDAP_USE_SSL or self.cfg.LDAP_USE_TLS:
            tls_kwargs = {}
            if self.cfg.LDAP_TLS_CA_CERT_FILE and os.path.exists(self.cfg.LDAP_TLS_CA_CERT_FILE):
                tls_kwargs["ca_certs_file"] = self.cfg.LDAP_TLS_CA_CERT_FILE
            
            if not self.cfg.LDAP_TLS_VALIDATE_CERT:
                tls_kwargs["validate"] = ssl.CERT_NONE
            else:
                tls_kwargs["validate"] = ssl.CERT_REQUIRED

            tls_config = Tls(**tls_kwargs)

        server_address = self.cfg.LDAP_SERVER
        port = self.cfg.LDAP_PORT
        use_ssl = bool(self.cfg.LDAP_USE_SSL)

        # Automatically adjust port if standard ldaps scheme is passed without explicit port
        if server_address.startswith("ldaps://") and port == 389:
            port = 636
            use_ssl = True

        return Server(
            host=server_address,
            port=port,
            use_ssl=use_ssl,
            tls=tls_config,
            connect_timeout=self.cfg.LDAP_TIMEOUT,
            get_info=ALL
        )

    def _get_service_connection(self) -> Optional[Connection]:
        """
        Binds to the directory using service account credentials.
        Returns active Connection or None if binding fails.
        """
        server = self._get_server()
        try:
            if self.cfg.LDAP_BIND_DN and self.cfg.LDAP_BIND_PASSWORD:
                conn = Connection(
                    server,
                    user=self.cfg.LDAP_BIND_DN,
                    password=self.cfg.LDAP_BIND_PASSWORD,
                    auto_bind=True,
                    receive_timeout=self.cfg.LDAP_TIMEOUT
                )
            else:
                # Anonymous bind if no bind DN specified
                conn = Connection(
                    server,
                    auto_bind=True,
                    receive_timeout=self.cfg.LDAP_TIMEOUT
                )

            if self.cfg.LDAP_USE_TLS and not self.cfg.LDAP_USE_SSL:
                conn.start_tls()

            return conn
        except (LDAPSocketOpenError, LDAPCommunicationError, LDAPResponseTimeoutError) as err:
            logger.error(f"LDAP server connection failure to {self.cfg.LDAP_SERVER}:{self.cfg.LDAP_PORT}: {err}")
            return None
        except LDAPBindError as err:
            logger.error(f"LDAP service account bind failure: {err}")
            return None
        except Exception as err:
            logger.error(f"Unexpected error establishing LDAP service connection: {err}")
            return None

    def find_user(self, username_or_email: str) -> Optional[Dict[str, Any]]:
        """
        Searches the LDAP/AD directory for a user matching username, sAMAccountName, or email.
        Returns normalized user profile dict or None.
        """
        if not self.is_enabled():
            return None

        clean_id = (username_or_email or "").strip()
        if not clean_id:
            return None

        # Sanitize LDAP search filter input (prevent LDAP injection)
        sanitized_id = clean_id.replace("\\", "\\5c") \
                               .replace("*", "\\2a") \
                               .replace("(", "\\28") \
                               .replace(")", "\\29") \
                               .replace("\x00", "\\00")

        conn = self._get_service_connection()
        if not conn:
            return None

        try:
            # Build search filter from template or fallback
            filter_template = self.cfg.LDAP_USER_SEARCH_FILTER
            if "{username}" in filter_template:
                search_filter = filter_template.replace("{username}", sanitized_id)
            else:
                search_filter = f"(&(objectClass=user)(|(sAMAccountName={sanitized_id})(mail={sanitized_id})))"

            search_base = self.cfg.LDAP_USER_SEARCH_BASE or self.cfg.LDAP_BASE_DN

            attributes = [
                "sAMAccountName", "uid", "mail", "userPrincipalName",
                "displayName", "cn", "givenName", "sn",
                "department", "telephoneNumber", "mobile", "memberOf"
            ]

            success = conn.search(
                search_base=search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes
            )

            if not success or not conn.entries:
                logger.info(f"LDAP user not found for query '{sanitized_id}' in base '{search_base}'")
                return None

            entry = conn.entries[0]
            return self._normalize_entry(entry)
        except Exception as err:
            logger.error(f"Error searching LDAP user '{sanitized_id}': {err}")
            return None
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

    def _normalize_entry(self, entry) -> Dict[str, Any]:
        """Normalizes an ldap3 entry into a standard dictionary."""
        def get_val(attr_name: str, default: str = "") -> str:
            if hasattr(entry, attr_name) and entry[attr_name]:
                val = entry[attr_name].value
                if isinstance(val, list):
                    return str(val[0]) if val else default
                return str(val)
            return default

        # Extract email
        email = get_val("mail")
        if not email:
            upn = get_val("userPrincipalName")
            if "@" in upn:
                email = upn
        if not email:
            # Fallback construct email if missing
            username = get_val("sAMAccountName") or get_val("uid") or get_val("cn")
            domain = self.cfg.LDAP_BASE_DN.replace("dc=", "").replace(",", ".").lower()
            email = f"{username}@{domain}" if domain else f"{username}@geiser.internal"

        # Extract username
        username = get_val("sAMAccountName") or get_val("uid") or email.split("@")[0]

        # Extract display/full name
        full_name = get_val("displayName")
        if not full_name:
            first = get_val("givenName")
            last = get_val("sn")
            if first or last:
                full_name = f"{first} {last}".strip()
            else:
                full_name = get_val("cn") or username

        # Extract department & phone
        department = get_val("department")
        phone = get_val("telephoneNumber") or get_val("mobile")

        # Extract groups (memberOf)
        raw_groups = []
        if hasattr(entry, "memberOf") and entry.memberOf:
            member_of = entry.memberOf.values
            if isinstance(member_of, list):
                raw_groups = [str(g) for g in member_of]
            else:
                raw_groups = [str(member_of)]

        # Extract clean group CNs
        clean_groups = []
        for g in raw_groups:
            # e.g., "CN=Helpdesk-Admins,OU=Groups,DC=geiser,DC=internal"
            if g.upper().startswith("CN="):
                parts = g.split(",")
                cn_part = parts[0][3:].strip()
                clean_groups.append(cn_part)
            else:
                clean_groups.append(g.strip())

        return {
            "dn": entry.entry_dn,
            "username": username.lower(),
            "email": email.lower(),
            "full_name": full_name,
            "department": department,
            "phone_number": phone or None,
            "groups": clean_groups,
            "raw_groups": raw_groups
        }

    async def authenticate_user(
        self,
        username_or_email: str,
        password: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Attempts full authentication for a user against LDAP / Active Directory.
        Returns:
            (True, user_info_dict, None) on successful authentication.
            (False, None, "Invalid credentials") if credentials mismatch.
            (False, None, "User not found in directory") if user cannot be located.
            (False, None, "LDAP connection failure: ...") on connectivity issues.
        """
        if not self.is_enabled():
            return False, None, "LDAP authentication is disabled"

        clean_id = (username_or_email or "").strip()
        if not clean_id or not password:
            return False, None, "Missing username or password"

        # Step 1: Locate user to get full Distinguished Name (DN) & attributes
        user_info = self.find_user(clean_id)
        if not user_info:
            return False, None, "User not found in directory"

        user_dn = user_info["dn"]

        # Step 2: Attempt bind with user DN and provided password
        server = self._get_server()
        user_conn = None
        try:
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=False,
                receive_timeout=self.cfg.LDAP_TIMEOUT
            )

            if self.cfg.LDAP_USE_TLS and not self.cfg.LDAP_USE_SSL:
                user_conn.start_tls()

            bind_success = user_conn.bind()
            if not bind_success:
                logger.warning(f"LDAP bind failed for user DN: {user_dn}")
                return False, None, "Invalid credentials"

            # Re-fetch groups if possible through authenticated connection
            return True, user_info, None

        except (LDAPInvalidCredentialsResult, LDAPBindError) as err:
            logger.warning(f"LDAP invalid credentials for user DN '{user_dn}'")
            return False, None, "Invalid credentials"
        except (LDAPSocketOpenError, LDAPCommunicationError, LDAPResponseTimeoutError) as err:
            logger.error(f"LDAP connection failure during user bind: {err}")
            return False, None, f"LDAP server connection failure: {err}"
        except Exception as err:
            logger.error(f"Unexpected error during LDAP user authentication: {err}")
            return False, None, "LDAP authentication error"
        finally:
            if user_conn:
                try:
                    user_conn.unbind()
                except Exception:
                    pass

    def get_role_from_groups(self, groups: List[str]) -> UserRole:
        """
        Maps directory groups to application RBAC roles.
        Hierarchy: ADMIN > SUPERVISOR > AGENT > DEFAULT_ROLE (USER).
        """
        if not groups:
            return self._parse_default_role()

        groups_lower = [g.lower() for g in groups]

        # 1. Admin Groups
        admin_groups = [g.strip().lower() for g in self.cfg.LDAP_ROLE_GROUP_ADMIN.split(",") if g.strip()]
        for ag in admin_groups:
            if ag in groups_lower:
                return UserRole.ADMIN

        # 2. Supervisor Groups
        supervisor_groups = [g.strip().lower() for g in self.cfg.LDAP_ROLE_GROUP_SUPERVISOR.split(",") if g.strip()]
        for sg in supervisor_groups:
            if sg in groups_lower:
                return UserRole.SUPERVISOR

        # 3. Agent Groups
        agent_groups = [g.strip().lower() for g in self.cfg.LDAP_ROLE_GROUP_AGENT.split(",") if g.strip()]
        for ag in agent_groups:
            if ag in groups_lower:
                return UserRole.AGENT

        return self._parse_default_role()

    def _parse_default_role(self) -> UserRole:
        default_str = (self.cfg.LDAP_DEFAULT_ROLE or "USER").upper()
        try:
            return UserRole(default_str)
        except ValueError:
            return UserRole.USER

    async def sync_user_to_db(self, ldap_info: Dict[str, Any], db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """
        Synchronizes an authenticated LDAP user into the local MongoDB database.
        - If user already exists by email, ldap_username, or ldap_dn: updates profile and groups.
        - If user does not exist: creates a new local user with auth_provider='ldap'.
        - Never stores passwords for LDAP users.
        """
        users_col = db.users
        email = ldap_info["email"].lower()
        username = ldap_info["username"].lower()
        dn = ldap_info["dn"]
        role = self.get_role_from_groups(ldap_info.get("groups", []))

        # Look up existing user
        query = {
            "$or": [
                {"email": email},
                {"ldap_username": username},
                {"ldap_dn": dn}
            ]
        }
        existing_user = await users_col.find_one(query)

        now = datetime.utcnow()

        if existing_user:
            # Update existing user profile from LDAP
            update_fields = {
                "full_name": ldap_info.get("full_name") or existing_user.get("full_name"),
                "department": ldap_info.get("department") or existing_user.get("department"),
                "phone_number": ldap_info.get("phone_number") or existing_user.get("phone_number"),
                "auth_provider": "ldap",
                "ldap_dn": dn,
                "ldap_username": username,
                "ldap_groups": ldap_info.get("groups", []),
                "last_ldap_sync": now,
                "is_active": True,
            }
            # Only update role if role mapping resolves to non-default or admin
            if role != UserRole.USER or existing_user.get("role") == UserRole.USER:
                update_fields["role"] = role.value

            await users_col.update_one(
                {"_id": existing_user["_id"]},
                {"$set": update_fields}
            )
            updated_user = await users_col.find_one({"_id": existing_user["_id"]})
            return MongoModel.format_id(updated_user)

        else:
            # Create new user in local MongoDB
            new_user_doc = {
                "email": email,
                "full_name": ldap_info.get("full_name") or username,
                "phone_number": ldap_info.get("phone_number"),
                "department": ldap_info.get("department"),
                "role": role.value,
                "is_active": True,
                "two_factor_enabled": False,
                "auth_provider": "ldap",
                "ldap_dn": dn,
                "ldap_username": username,
                "ldap_groups": ldap_info.get("groups", []),
                "hashed_password": "!LDAP_NO_LOCAL_PASSWORD!",
                "created_at": now,
                "last_ldap_sync": now
            }
            result = await users_col.insert_one(new_user_doc)
            new_user_doc["_id"] = result.inserted_id
            return MongoModel.format_id(new_user_doc)
