from pathlib import Path

from app.db.session import build_engine, create_schema
from app.repositories.audit import AuditRepository


def test_audit_repository_appends_hash_chain(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    create_schema(engine)
    repository = AuditRepository(engine)

    first = repository.append_event(
        tenant_id="tenant_1",
        entity_type="case",
        entity_id="case_1",
        action="case_created",
        actor="maker.one",
        note="Created case",
        metadata={"branch": "KTM"},
    )
    second = repository.append_event(
        tenant_id="tenant_1",
        entity_type="case",
        entity_id="case_1",
        action="review_saved",
        actor="checker.one",
        note="Reviewed",
        metadata={},
    )

    assert first.previous_hash == ""
    assert len(first.record_hash) == 64
    assert second.previous_hash == first.record_hash
    assert second.record_hash != first.record_hash

    events = repository.list_events(tenant_id="tenant_1", entity_type="case", entity_id="case_1")
    assert [event.action for event in events] == ["case_created", "review_saved"]


def test_audit_repository_scopes_by_tenant(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    create_schema(engine)
    repository = AuditRepository(engine)
    repository.append_event("tenant_1", "case", "case_1", "case_created", "maker.one", "", {})
    repository.append_event("tenant_2", "case", "case_1", "case_created", "maker.two", "", {})

    events = repository.list_events("tenant_1", "case", "case_1")
    assert len(events) == 1
    assert events[0].actor == "maker.one"
