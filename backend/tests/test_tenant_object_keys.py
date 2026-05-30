from app.tenancy.object_keys import object_key_belongs_to_tenant, tenant_object_key


def test_tenant_object_keys_are_namespaced_and_sanitized():
    key = tenant_object_key(
        tenant_id="NIC Asia / Kathmandu",
        category="documents",
        object_id="doc_123",
        filename="../citizenship.jpg",
    )

    assert key.startswith("tenants/NIC-Asia-Kathmandu/documents/doc_123/")
    assert ".." not in key
    assert object_key_belongs_to_tenant(key, "NIC Asia / Kathmandu")
    assert not object_key_belongs_to_tenant(key, "other-tenant")
