from app.models import DocumentType, FinancialDocument, OcrBlock, OcrPage
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_intelligence import analyze_document
from app.services.nepal_locations import location_registry, resolve_nepal_location

client = TestClient(app)


def test_location_registry_loads_nepal_administrative_units():
    registry = location_registry()

    assert len(registry.provinces) == 7
    assert len(registry.districts) == 77
    assert len(registry.local_levels) == 753


def test_resolve_location_matches_district_municipality_and_ward():
    resolution = resolve_nepal_location("District: Kathmandu Metropolitan : Kathmandu Ward No.:26")

    assert resolution.status == "matched"
    assert resolution.province_name == "Bagmati Pradesh"
    assert resolution.district_name == "Kathmandu"
    assert resolution.local_level_key == "Kathmandu"
    assert resolution.local_level_type == "Mahanagarpalika"
    assert resolution.ward == "26"
    assert resolution.confidence >= 0.90


def test_resolve_location_fills_district_from_municipality_alias_and_old_napa_wording():
    resolution = resolve_nepal_location("मध्यपुर थिमी न.पा. वडा नं. ९")

    assert resolution.status == "matched"
    assert resolution.province_name == "Bagmati Pradesh"
    assert resolution.district_name == "Bhaktapur"
    assert resolution.local_level_key == "Madhyapur Thimi"
    assert resolution.ward == "9"
    assert "district_inferred_from_local_level" in resolution.reasons


def test_resolve_location_flags_district_local_level_mismatch():
    resolution = resolve_nepal_location("District: Chitwan Kathmandu Metropolitan Ward No.:26")

    assert resolution.status == "needs_review"
    assert resolution.district_name == "Chitwan"
    assert resolution.local_level_key == "Kathmandu"
    assert "district_local_level_mismatch" in resolution.warnings


def test_resolve_location_accepts_legacy_vdc_wording():
    resolution = resolve_nepal_location("District: Jhapa Kamal VDC Ward No. 5")

    assert resolution.status == "matched"
    assert resolution.province_name == "Koshi Pradesh"
    assert resolution.district_name == "Jhapa"
    assert resolution.local_level_key == "Kamal"
    assert resolution.local_level_type == "Gaunpalika"
    assert resolution.ward == "5"
    assert "legacy_vdc_term_detected" in resolution.reasons


def test_document_intelligence_enriches_citizenship_locations():
    document = FinancialDocument(
        filename="citizenship-location.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.88,
                blocks=[
                    OcrBlock(text="नेपाली नागरिकताको प्रमाणपत्र", bbox=[80, 80, 800, 120], confidence=0.92),
                    OcrBlock(
                        text="स्थायी वासस्थान: जिल्ला: काठमाडौं म.न.पा.: काठमाडौं वडा नं.: २६",
                        bbox=[80, 180, 900, 220],
                        confidence=0.88,
                        language="ne",
                    ),
                ],
            )
        ],
        page_count=1,
    )

    analysis = analyze_document(document)
    canonical = analysis["canonical_fields"]

    assert canonical["permanent_address_province"] == "Bagmati Pradesh"
    assert canonical["permanent_address_district"] == "Kathmandu"
    assert canonical["permanent_address_local_level"] == "Kathmandu"
    assert canonical["permanent_address_local_level_type"] == "Mahanagarpalika"
    assert canonical["permanent_address_ward"] == "26"
    assert analysis["location_resolutions"][0]["status"] == "matched"
    assert any(check["key"] == "permanent_address_location_registry" for check in analysis["cross_checks"])


def test_location_reference_api_returns_counts_and_search_results():
    response = client.get("/api/reference/nepal-locations?q=madhyapur")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {"provinces": 7, "districts": 77, "local_levels": 753}
    assert payload["results"][0]["local_level_key"] == "Madhyapur Thimi"
    assert payload["results"][0]["district_name"] == "Bhaktapur"
    assert payload["results"][0]["province_name"] == "Bagmati Pradesh"


def test_location_reference_api_resolves_free_text_address():
    response = client.post(
        "/api/reference/nepal-locations/resolve",
        json={"text": "स्थायी ठेगाना मध्यपुर थिमी न.पा. वडा नं. ९"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "matched"
    assert payload["district_name"] == "Bhaktapur"
    assert payload["local_level_key"] == "Madhyapur Thimi"
    assert payload["ward"] == "9"
