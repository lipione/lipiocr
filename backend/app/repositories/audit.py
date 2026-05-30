from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Engine, select

from app.db.models import AuditEventRecord
from app.db.session import session_scope


def _canonical_payload(
    *,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    note: str,
    metadata: dict,
    previous_hash: str,
    created_at: datetime,
    case_id: Optional[str] = None,
) -> str:
    return json.dumps(
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "note": note,
            "metadata": metadata,
            "previous_hash": previous_hash,
            "created_at": created_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class AuditRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def append_event(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        note: str,
        metadata: dict,
        case_id: Optional[str] = None,
    ) -> AuditEventRecord:
        with session_scope(self.engine) as session:
            previous = session.execute(
                select(AuditEventRecord)
                .where(AuditEventRecord.tenant_id == tenant_id)
                .where(AuditEventRecord.entity_type == entity_type)
                .where(AuditEventRecord.entity_id == entity_id)
                .order_by(AuditEventRecord.created_at.desc())
            ).scalars().first()
            created_at = datetime.utcnow()
            previous_hash = previous.record_hash if previous else ""
            payload = _canonical_payload(
                tenant_id=tenant_id,
                case_id=case_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=actor,
                note=note,
                metadata=metadata,
                previous_hash=previous_hash,
                created_at=created_at,
            )
            record = AuditEventRecord(
                id=f"audit_{uuid4().hex}",
                tenant_id=tenant_id,
                case_id=case_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=actor,
                note=note,
                metadata_json=metadata,
                previous_hash=previous_hash,
                record_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                created_at=created_at,
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def list_events(self, tenant_id: str, entity_type: str, entity_id: str) -> list[AuditEventRecord]:
        with session_scope(self.engine) as session:
            return list(
                session.execute(
                    select(AuditEventRecord)
                    .where(AuditEventRecord.tenant_id == tenant_id)
                    .where(AuditEventRecord.entity_type == entity_type)
                    .where(AuditEventRecord.entity_id == entity_id)
                    .order_by(AuditEventRecord.created_at.asc())
                ).scalars()
            )


__all__ = ["AuditRepository"]
