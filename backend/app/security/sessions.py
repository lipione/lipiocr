from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Dict, Optional


@dataclass(frozen=True)
class SessionPrincipal:
    user_id: str
    role: str
    tenant_id: str
    branch_code: Optional[str]
    auth_method: str = "session"


@dataclass
class SessionRecord:
    token: str
    principal: SessionPrincipal
    issued_at: datetime
    expires_at: datetime


class InMemorySessionStore:
    def __init__(self, *, secret: str, ttl_seconds: int) -> None:
        self.secret = secret or "lipiocr-dev-session-secret"
        self.ttl_seconds = max(60, int(ttl_seconds or 3600))
        self._sessions: Dict[str, SessionRecord] = {}

    def create(self, principal: SessionPrincipal) -> str:
        issued_at = datetime.utcnow()
        nonce = secrets.token_urlsafe(32)
        signature = hmac.new(self.secret.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{nonce}.{signature}"
        self._sessions[token] = SessionRecord(
            token=token,
            principal=principal,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(seconds=self.ttl_seconds),
        )
        return token

    def verify(self, token: str | None) -> Optional[SessionPrincipal]:
        if not token:
            return None
        record = self._sessions.get(token)
        if record is None:
            return None
        if record.expires_at < datetime.utcnow():
            self._sessions.pop(token, None)
            return None
        return record.principal

    def revoke(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)


_stores: dict[tuple[str, int], InMemorySessionStore] = {}


def session_store_from_settings(settings) -> InMemorySessionStore:
    key = (str(getattr(settings, "session_secret", "")), int(getattr(settings, "session_ttl_seconds", 3600)))
    if key not in _stores:
        _stores[key] = InMemorySessionStore(secret=key[0], ttl_seconds=key[1])
    return _stores[key]
