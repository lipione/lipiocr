from app.db.models import Base, TENANT_SCOPED_TABLES, all_domain_tables


REQUIRED_TABLES = {
    "tenants",
    "cases",
    "documents",
    "document_versions",
    "document_pages",
    "ocr_blocks",
    "extracted_fields",
    "field_corrections",
    "reviews",
    "exports",
    "jobs",
    "audit_events",
    "template_profiles",
    "template_versions",
    "integration_events",
}


def test_production_domain_tables_are_declared():
    assert REQUIRED_TABLES.issubset(set(all_domain_tables()))
    assert REQUIRED_TABLES.issubset(set(Base.metadata.tables))


def test_tenant_scoped_tables_have_tenant_id():
    for table_name in TENANT_SCOPED_TABLES:
        table = Base.metadata.tables[table_name]
        assert "tenant_id" in table.c, table_name
        assert table.c.tenant_id.index is True


def test_audit_table_supports_immutable_hash_chain():
    audit = Base.metadata.tables["audit_events"]
    for column_name in [
        "id",
        "tenant_id",
        "entity_type",
        "entity_id",
        "action",
        "actor",
        "previous_hash",
        "record_hash",
    ]:
        assert column_name in audit.c
