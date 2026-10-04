"""
websocket/manager.py
====================
STEP 5 — WebSocket Real-Time Communication & Live Notifications

In-memory ConnectionManager for concurrent WebSocket clients.
Responsibilities:
1. Support multiple simultaneous connections per user (multiple browser tabs, mobile apps).
2. Maintain active connection registries with thread-safe / asyncio-safe operations.
3. Track user metadata (role, email, team_id) for instantaneous in-memory RBAC evaluation.
4. Auto-prune dead/disconnected sockets without disrupting ongoing broadcasts.
5. Provide fine-grained dispatching: user, multi-users, team, role, or filtered broadcast.
6. Guarantee error isolation: send failures NEVER crash the application or the caller.
"""

import asyncio
import logging
from typing import Dict, Set, Optional, Any, Callable, Iterable
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active authenticated WebSocket connections across the application.
    Supports multiple concurrent connections per user.
    """

    def __init__(self):
        # Map: user_id (str) -> Set[WebSocket]
        self._active_connections: Dict[str, Set[WebSocket]] = {}
        # Reverse map: WebSocket -> user_id (str)
        self._ws_to_user: Dict[WebSocket, str] = {}
        # Cached user metadata: user_id -> dict(role, team_id, email, full_name)
        self._user_metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user: Dict[str, Any]) -> None:
        """
        Registers an accepted WebSocket connection with its authenticated user.
        Supports multiple sockets per user ID.
        """
        user_id = str(user.get("id") or user.get("_id") or "")
        if not user_id:
            logger.warning("Attempted to register WebSocket without valid user_id")
            return

        role = user.get("role")
        role_str = role.value if hasattr(role, "value") else str(role)

        async with self._lock:
            if user_id not in self._active_connections:
                self._active_connections[user_id] = set()

            self._active_connections[user_id].add(websocket)
            self._ws_to_user[websocket] = user_id
            self._user_metadata[user_id] = {
                "user_id": user_id,
                "role": role_str,
                "team_id": str(user.get("team_id")) if user.get("team_id") else None,
                "email": user.get("email"),
                "full_name": user.get("full_name"),
            }

        logger.info(f"[WS] Client connected: user={user_id} ({role_str}). Total sockets for user: {len(self._active_connections[user_id])}")

    async def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """
        Removes a WebSocket connection cleanly when closed by the client or error.
        Prunes empty user sets.
        """
        user_id: Optional[str] = None
        async with self._lock:
            user_id = self._ws_to_user.pop(websocket, None)
            if user_id and user_id in self._active_connections:
                self._active_connections[user_id].discard(websocket)
                if not self._active_connections[user_id]:
                    del self._active_connections[user_id]
                    self._user_metadata.pop(user_id, None)

        if user_id:
            logger.info(f"[WS] Client disconnected: user={user_id}. Active sockets: {len(self._active_connections.get(user_id, set()))}")
        return user_id

    def get_user_metadata(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached metadata for an active user."""
        return self._user_metadata.get(user_id)

    async def _safe_send(self, websocket: WebSocket, event: Dict[str, Any], user_id: str) -> bool:
        """
        Sends an event to a single WebSocket. If dead or closed, schedules cleanup.
        Never raises exceptions to the caller.
        """
        try:
            await websocket.send_json(event)
            return True
        except Exception as e:
            logger.debug(f"[WS] Failed to send event to user {user_id}: {e}. Evicting dead socket.")
            # Disconnect dead socket asynchronously
            asyncio.create_task(self.disconnect(websocket))
            return False

    async def send_to_user(self, user_id: str, event: Dict[str, Any]) -> int:
        """
        Sends an event to all open connections of a specific user.
        Returns the number of successful socket deliveries.
        """
        sockets: Set[WebSocket] = set()
        async with self._lock:
            sockets = set(self._active_connections.get(user_id, set()))

        if not sockets:
            return 0

        tasks = [self._safe_send(ws, event, user_id) for ws in sockets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)

    async def send_to_users(self, user_ids: Iterable[str], event: Dict[str, Any]) -> int:
        """Sends an event to multiple users concurrently."""
        total = 0
        tasks = [self.send_to_user(uid, event) for uid in set(user_ids) if uid]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, int):
                    total += r
        return total

    async def send_to_role(self, role: str, event: Dict[str, Any]) -> int:
        """
        Sends an event to all connected users possessing the specified role
        (e.g., 'ADMIN', 'SUPERVISOR', 'AGENT').
        """
        target_uids = []
        async with self._lock:
            for uid, meta in self._user_metadata.items():
                if meta.get("role") == role:
                    target_uids.append(uid)

        return await self.send_to_users(target_uids, event)

    async def send_to_team(self, team_id: str, event: Dict[str, Any]) -> int:
        """Sends an event to all connected users belonging to a specific team."""
        target_uids = []
        async with self._lock:
            for uid, meta in self._user_metadata.items():
                if meta.get("team_id") == str(team_id):
                    target_uids.append(uid)

        return await self.send_to_users(target_uids, event)

    async def broadcast(self, event: Dict[str, Any]) -> int:
        """Broadcasts an event to all currently connected clients across the application."""
        async with self._lock:
            all_users = list(self._active_connections.keys())
        return await self.send_to_users(all_users, event)

    async def broadcast_authorized(
        self,
        event: Dict[str, Any],
        filter_fn: Callable[[Dict[str, Any]], bool]
    ) -> int:
        """
        Broadcasts an event only to connected users who satisfy the authorization filter.
        `filter_fn` receives the user metadata dict and returns True if authorized.
        """
        authorized_uids = []
        async with self._lock:
            for uid, meta in self._user_metadata.items():
                try:
                    if filter_fn(meta):
                        authorized_uids.append(uid)
                except Exception as e:
                    logger.warning(f"Error in broadcast_authorized filter for user {uid}: {e}")

        return await self.send_to_users(authorized_uids, event)

    def get_stats(self) -> Dict[str, Any]:
        """Returns live statistics of connected WebSocket clients."""
        total_sockets = sum(len(s) for s in self._active_connections.values())
        return {
            "active_users": len(self._active_connections),
            "active_connections": total_sockets,
            "roles_connected": {
                role: sum(1 for m in self._user_metadata.values() if m.get("role") == role)
                for role in ["ADMIN", "SUPERVISOR", "AGENT", "USER"]
            }
        }


# Global singleton manager instance
connection_manager = ConnectionManager()
