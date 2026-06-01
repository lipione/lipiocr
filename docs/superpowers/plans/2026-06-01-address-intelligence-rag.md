# Address Intelligence RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production slice of Nepal address intelligence: structured address evidence, fuzzy retrieval, reviewer-safe address correction candidates, reference APIs, and review/admin UI.

**Architecture:** Keep the Nepal administrative registry as the authority, add an address evidence store for roads/tole/street aliases, and generate deterministic candidates with score breakdowns. LipiCore remains the explanation layer; no address is silently overwritten or learned from raw OCR.

**Tech Stack:** Python FastAPI, Pydantic, JSON-backed local storage compatible with future PostgreSQL, existing React/Next.js frontend, existing `apiJson` client, existing document review workflow.

---

## File Structure

Create:
- `backend/app/data/address_evidence_seed.json`: small safe seed records for development and tests.
- `backend/app/services/address_evidence_store.py`: address evidence model, load/search/upsert/delete/import helpers.
- `backend/app/services/address_intelligence.py`: normalization, retrieval, scoring, candidate generation.
- `backend/tests/test_address_evidence_store.py`: evidence store unit tests.
- `backend/tests/test_address_intelligence.py`: resolver and document-intelligence integration tests.
- `backend/tests/test_address_evidence_api.py`: FastAPI reference API tests.
- `frontend/src/lib/address-evidence.ts`: typed API helpers for address dataset controls.

Modify:
- `backend/app/core/config.py`: add `LIPIOCR_ADDRESS_EVIDENCE_PATH`.
- `.gitignore`: ignore generated local address evidence files.
- `backend/app/services/document_intelligence.py`: add `address_candidates` analysis and attach them to address fields.
- `backend/app/main.py`: expose address evidence search, resolve, create, import, patch, and delete APIs.
- `frontend/src/types/workspace.ts`: add address candidate and address evidence API types.
- `frontend/src/components/enterprise-workspace.tsx`: render address candidates in review and add Admin address dataset controls.
- `frontend/scripts/workspace-types.test.mjs`: verify address candidate constants/types exported for tests.
- `README.md`, `docs/configuration.md`, `docs/developer-onboarding.md`, `docs/api-reference.md`: document address intelligence setup and APIs.

---

## Task 1: Address Evidence Store

**Files:**
- Create: `backend/app/services/address_evidence_store.py`
- Create: `backend/app/data/address_evidence_seed.json`
- Create: `backend/tests/test_address_evidence_store.py`
- Modify: `backend/app/core/config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing store tests**

Create `backend/tests/test_address_evidence_store.py`:

```python
from pathlib import Path

from app.services.address_evidence_store import (
    AddressEvidenceRecord,
    AddressEvidenceStore,
    import_address_evidence_csv,
)


def test_store_searches_aliases_and_respects_tenant_scope(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_seed_samakhusi",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Samakhusi",
                name_np="",
                aliases_en=["Samakushi", "Samakhusi Chowk"],
                aliases_np=[],
                source="manual_seed",
                confidence_weight=0.86,
            ),
            AddressEvidenceRecord(
                id="addr_other_tenant",
                tenant_id="other-bank",
                visibility="tenant_private",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Private Area",
                aliases_en=["Samakushi"],
                aliases_np=[],
                source="reviewer_approved",
            ),
        ],
    )

    results = store.search("Samakushi", tenant_id="demo-institution")

    assert [item["id"] for item in results] == ["addr_seed_samakhusi"]
    assert results[0]["name_en"] == "Samakhusi"
    assert results[0]["matched_alias"] == "Samakushi"


def test_store_upserts_and_persists_reviewer_approved_evidence(tmp_path: Path):
    path = tmp_path / "address_evidence.json"
    store = AddressEvidenceStore(path=path, seed_records=[])

    record = store.upsert(
        AddressEvidenceRecord(
            id="addr_reviewed_01",
            tenant_id="demo-institution",
            visibility="tenant_private",
            kind="street_or_road",
            district_name="Kathmandu",
            local_level_name="Kathmandu Metropolitan City",
            ward="26",
            name_en="Tokha Road",
            aliases_en=["Tokha Rd"],
            aliases_np=[],
            source="reviewer_approved",
            approved_by="reviewer-1",
            created_from_document_id="doc_1",
        )
    )

    reloaded = AddressEvidenceStore(path=path, seed_records=[])

    assert record["id"] == "addr_reviewed_01"
    assert reloaded.search("Tokha Rd", tenant_id="demo-institution")[0]["name_en"] == "Tokha Road"


def test_csv_import_builds_records_with_aliases(tmp_path: Path):
    csv_path = tmp_path / "addresses.csv"
    csv_path.write_text(
        "district,local_level,ward,kind,name_en,aliases_en\\n"
        "Kathmandu,Kathmandu Metropolitan City,26,area_or_tole,Samakhusi,Samakushi|Samakhusi Chowk\\n",
        encoding="utf-8",
    )

    records = import_address_evidence_csv(csv_path, tenant_id="demo-institution", source="manual_seed")

    assert len(records) == 1
    assert records[0].name_en == "Samakhusi"
    assert records[0].aliases_en == ["Samakushi", "Samakhusi Chowk"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_evidence_store.py -q
```

Expected: failure because `app.services.address_evidence_store` does not exist.

- [ ] **Step 3: Add config and storage ignore**

Modify `backend/app/core/config.py` inside `Settings`:

```python
address_evidence_path: str = Field(
    default_factory=lambda: os.getenv(
        "LIPIOCR_ADDRESS_EVIDENCE_PATH",
        "storage/address-evidence/address_evidence.json",
    )
)
```

Modify `.gitignore`:

```gitignore
backend/storage/address-evidence/*
!backend/storage/address-evidence/.gitkeep
```

Create the directory marker:

```bash
mkdir -p backend/storage/address-evidence
touch backend/storage/address-evidence/.gitkeep
```

- [ ] **Step 4: Add seed data**

Create `backend/app/data/address_evidence_seed.json`:

```json
{
  "metadata": {
    "version": 1,
    "description": "Development seed for Nepal address intelligence. Tenant-private records should be stored outside Git."
  },
  "records": [
    {
      "id": "addr_seed_samakhusi",
      "tenant_id": "system",
      "visibility": "shared_reference",
      "kind": "area_or_tole",
      "province_name": "Bagmati Pradesh",
      "district_name": "Kathmandu",
      "local_level_name": "Kathmandu Metropolitan City",
      "local_level_type": "Mahanagarpalika",
      "ward": "26",
      "name_en": "Samakhusi",
      "name_np": "",
      "aliases_en": ["Samakushi", "Samakhusi Chowk"],
      "aliases_np": [],
      "legacy_aliases": [],
      "source": "manual_seed",
      "confidence_weight": 0.84
    },
    {
      "id": "addr_seed_tokha_road",
      "tenant_id": "system",
      "visibility": "shared_reference",
      "kind": "street_or_road",
      "province_name": "Bagmati Pradesh",
      "district_name": "Kathmandu",
      "local_level_name": "Kathmandu Metropolitan City",
      "local_level_type": "Mahanagarpalika",
      "ward": "26",
      "name_en": "Tokha Road",
      "name_np": "",
      "aliases_en": ["Tokha Rd", "Tokha Road Kathmandu"],
      "aliases_np": [],
      "legacy_aliases": [],
      "source": "manual_seed",
      "confidence_weight": 0.82
    }
  ]
}
```

- [ ] **Step 5: Implement the evidence store**

Create `backend/app/services/address_evidence_store.py` with these public names:

```python
from __future__ import annotations

import csv
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.config import get_settings
from app.services.calendar_intelligence import normalize_nepali_digits


SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "address_evidence_seed.json"


def normalize_address_text(value: str) -> str:
    normalized = normalize_nepali_digits(str(value or "")).lower()
    normalized = re.sub(r"[|,/;:()\\[\\]{}]+", " ", normalized)
    normalized = re.sub(r"\\bmetropolitian\\b", "metropolitan", normalized)
    normalized = re.sub(r"\\bkathmadu\\b", "kathmandu", normalized)
    normalized = re.sub(r"\\bsamakushi\\b", "samakhusi", normalized)
    return re.sub(r"\\s+", " ", normalized).strip()


@dataclass
class AddressEvidenceRecord:
    id: str = field(default_factory=lambda: f"addr_{uuid.uuid4().hex[:12]}")
    tenant_id: str = "system"
    visibility: str = "shared_reference"
    kind: str = "area_or_tole"
    province_code: str = ""
    province_name: str = ""
    district_code: str = ""
    district_name: str = ""
    local_level_code: str = ""
    local_level_name: str = ""
    local_level_type: str = ""
    ward: str = ""
    name_en: str = ""
    name_np: str = ""
    aliases_en: list[str] = field(default_factory=list)
    aliases_np: list[str] = field(default_factory=list)
    legacy_aliases: list[str] = field(default_factory=list)
    source: str = "manual_seed"
    confidence_weight: float = 0.75
    approved_by: Optional[str] = None
    created_from_document_id: Optional[str] = None
    disabled: bool = False

    def all_aliases(self) -> list[str]:
        aliases = [self.name_en, self.name_np, *self.aliases_en, *self.aliases_np, *self.legacy_aliases]
        seen: set[str] = set()
        output: list[str] = []
        for alias in aliases:
            clean = str(alias or "").strip()
            key = normalize_address_text(clean)
            if clean and key not in seen:
                seen.add(key)
                output.append(clean)
        return output

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)
```

Also implement `AddressEvidenceStore.search`, `AddressEvidenceStore.upsert`, `AddressEvidenceStore.delete`, `load_address_evidence_store`, and `import_address_evidence_csv`. Search must:
- include `shared_reference` records for every tenant
- include `tenant_private` records only when `record.tenant_id == tenant_id`
- return dictionaries with `matched_alias` and `match_score`
- sort by score, confidence weight, then name

- [ ] **Step 6: Run store tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_evidence_store.py -q
```

Expected: 3 passed.

- [ ] **Step 7: Commit Task 1**

```bash
git add .gitignore backend/app/core/config.py backend/app/data/address_evidence_seed.json backend/app/services/address_evidence_store.py backend/storage/address-evidence/.gitkeep backend/tests/test_address_evidence_store.py
git commit -m "feat: add address evidence store"
```

---

## Task 2: Address Candidate Engine

**Files:**
- Create: `backend/app/services/address_intelligence.py`
- Create: `backend/tests/test_address_intelligence.py`

- [ ] **Step 1: Write failing resolver tests**

Create `backend/tests/test_address_intelligence.py`:

```python
from pathlib import Path

from app.models import FinancialDocument, OcrBlock, OcrPage
from app.services.address_evidence_store import AddressEvidenceRecord, AddressEvidenceStore
from app.services.address_intelligence import suggest_address_corrections


def _store(tmp_path: Path) -> AddressEvidenceStore:
    return AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_seed_samakhusi",
                tenant_id="system",
                visibility="shared_reference",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Samakhusi",
                aliases_en=["Samakushi", "Samakhusi Chowk"],
                aliases_np=[],
                source="manual_seed",
                confidence_weight=0.84,
            )
        ],
    )


def test_address_candidate_corrects_misspelled_kathmandu_address(tmp_path: Path):
    candidates = suggest_address_corrections(
        "Kathmadu Metropolitian ward 26 Samakushi",
        target_field="permanent_address",
        tenant_id="demo-institution",
        store=_store(tmp_path),
    )

    assert candidates
    top = candidates[0]
    assert top["target_field"] == "permanent_address"
    assert top["suggested_value"] == "Kathmandu Metropolitan City, Ward 26, Samakhusi"
    assert top["structured"]["district"] == "Kathmandu"
    assert top["structured"]["local_level"] == "Kathmandu Metropolitan City"
    assert top["structured"]["ward"] == "26"
    assert top["structured"]["area_or_tole"] == "Samakhusi"
    assert top["confidence"] >= 0.80
    assert "address_evidence_store" in top["sources"]
    assert "score_breakdown" in top


def test_low_context_street_match_does_not_overstate_confidence(tmp_path: Path):
    candidates = suggest_address_corrections(
        "Samakushi",
        target_field="address",
        tenant_id="demo-institution",
        store=_store(tmp_path),
    )

    assert candidates
    assert candidates[0]["confidence"] < 0.80
    assert candidates[0]["status"] == "needs_review"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_intelligence.py -q
```

Expected: failure because `app.services.address_intelligence` does not exist.

- [ ] **Step 3: Implement deterministic address candidate scoring**

Create `backend/app/services/address_intelligence.py`:

```python
from __future__ import annotations

from typing import Optional

from app.services.address_evidence_store import AddressEvidenceStore, load_address_evidence_store, normalize_address_text
from app.services.nepal_locations import resolve_nepal_location


ADDRESS_FIELD_KEYS = {
    "address",
    "address_en",
    "address_np",
    "address_ne",
    "permanent_address",
    "permanent_address_en",
    "permanent_address_np",
    "permanent_address_ne",
    "temporary_address",
    "contact_address",
    "birth_place",
}


def is_address_field_key(key: str) -> bool:
    normalized = str(key or "").lower()
    return normalized in ADDRESS_FIELD_KEYS or any(part in normalized for part in ("address", "ठेगाना", "birth_place"))


def suggest_address_corrections(
    value: str,
    *,
    target_field: str,
    tenant_id: str = "demo-institution",
    store: Optional[AddressEvidenceStore] = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    text = str(value or "").strip()
    if not text:
        return []

    evidence_store = store or load_address_evidence_store()
    location = resolve_nepal_location(text)
    evidence_results = evidence_store.search(text, tenant_id=tenant_id, limit=limit)
    candidates = [
        _candidate_from_evidence(
            text,
            target_field=target_field,
            location=location.model_dump(),
            evidence=evidence,
        )
        for evidence in evidence_results
    ]
    if not candidates and location.status != "unresolved":
        candidates.append(_candidate_from_location(text, target_field=target_field, location=location.model_dump()))

    return sorted(candidates, key=lambda item: float(item["confidence"]), reverse=True)[:limit]
```

Implement `_candidate_from_evidence`, `_candidate_from_location`, `_score_breakdown`, and `_format_address`. Required behavior:
- Use district/local-level/ward from administrative resolution when available.
- Use evidence district/local-level/ward/name when administrative resolution is partial.
- Set `status` to `suggested` when confidence is at least `0.80`; otherwise `needs_review`.
- Include `sources`, `score_breakdown`, `original_ocr_value`, `suggested_value`, `structured`, and `audit_reason`.
- Normalize common OCR spellings using `normalize_address_text`.

- [ ] **Step 4: Run candidate tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_intelligence.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/services/address_intelligence.py backend/tests/test_address_intelligence.py
git commit -m "feat: add address correction candidates"
```

---

## Task 3: Integrate Address Candidates Into Document Intelligence

**Files:**
- Modify: `backend/app/services/document_intelligence.py`
- Modify: `backend/tests/test_address_intelligence.py`

- [ ] **Step 1: Add failing document integration tests**

Append to `backend/tests/test_address_intelligence.py`:

```python
from app.models import ExtractedField, ValidationStatus
from app.services.document_intelligence import analyze_document, apply_document_intelligence


def _document_with_address() -> FinancialDocument:
    return FinancialDocument(
        filename="address-form.txt",
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=700,
                blocks=[
                    OcrBlock(
                        text="Permanent Address: Kathmadu Metropolitian ward 26 Samakushi",
                        bbox=[80, 120, 700, 160],
                        confidence=0.74,
                        block_type="field_candidate",
                    )
                ],
            )
        ],
    )


def test_document_intelligence_exposes_address_candidates():
    document = _document_with_address()

    analysis = analyze_document(document)

    assert analysis["address_candidates"]
    candidate = analysis["address_candidates"][0]
    assert candidate["target_field"] in {"permanent_address", "address_en", "address"}
    assert candidate["structured"]["district"] == "Kathmandu"
    assert "address_evidence_store" in candidate["sources"]


def test_apply_document_intelligence_attaches_address_candidates_to_review_field():
    document = _document_with_address()
    field = ExtractedField(
        key="permanent_address",
        label="Permanent Address",
        value="Kathmadu Metropolitian ward 26 Samakushi",
        confidence=0.74,
        validation_status=ValidationStatus.warning,
        validation_message="Needs review",
    )

    analysis = apply_document_intelligence(document, [field])

    assert analysis["address_candidates"]
    assert field.correction_candidates
    assert field.correction_candidates[0]["suggested_value"].startswith("Kathmandu Metropolitan City")
    assert field.original_ocr_value == "Kathmadu Metropolitian ward 26 Samakushi"
```

- [ ] **Step 2: Run integration tests and verify failure**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_intelligence.py -q
```

Expected: failure because `address_candidates` is not returned or not attached.

- [ ] **Step 3: Add address candidate generation**

Modify `backend/app/services/document_intelligence.py`:

```python
from app.services.address_intelligence import is_address_field_key, suggest_address_corrections
```

Add helper near `_name_candidates`:

```python
def _address_candidates(observations: list[FieldObservation], *, tenant_id: str = "demo-institution") -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for observation in observations:
        if not is_address_field_key(observation.output_key) and not is_address_field_key(observation.canonical_key):
            continue
        for suggestion in suggest_address_corrections(
            observation.value,
            target_field=observation.output_key,
            tenant_id=tenant_id,
        ):
            candidates.append(
                {
                    **suggestion,
                    "canonical_key": observation.canonical_key,
                    "target_field": observation.output_key,
                    "source_field_used": "address_intelligence",
                    "original_confidence": observation.confidence,
                }
            )
    return sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)
```

Update `analyze_document`:

```python
address_candidates = _address_candidates(observations)
```

Return:

```python
"address_candidates": address_candidates,
```

- [ ] **Step 4: Attach address candidates to fields**

In `apply_document_intelligence`, after name candidate attachment, add a generic attachment block:

```python
grouped_address_candidates: dict[str, list[dict[str, object]]] = defaultdict(list)
for candidate in analysis.get("address_candidates", []):
    if isinstance(candidate, dict):
        grouped_address_candidates[str(candidate.get("target_field") or "")].append(candidate)

for target_key, candidates in grouped_address_candidates.items():
    field = fields_by_key.get(target_key)
    if field is None or field.source.startswith("reviewer"):
        continue
    ordered = sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)
    field.correction_candidates = [*field.correction_candidates, *ordered[:5]][:5]
    top = ordered[0]
    candidate_confidence = float(top.get("confidence") or field.confidence)
    if candidate_confidence < 0.80:
        continue
    field.original_ocr_value = str(top.get("original_ocr_value") or field.original_ocr_value or field.value)
    field.corrected_value = str(top.get("suggested_value") or field.corrected_value or "")
    field.source_field_used = str(top.get("source_field_used") or "address_intelligence")
    field.correction_confidence = round(max(field.correction_confidence or 0, candidate_confidence), 2)
    field.audit_reason = str(top.get("audit_reason") or field.audit_reason or "")
    field.validation_message = field.audit_reason or field.validation_message
```

- [ ] **Step 5: Run backend integration tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_intelligence.py tests/test_document_intelligence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add backend/app/services/document_intelligence.py backend/tests/test_address_intelligence.py
git commit -m "feat: attach address candidates to document intelligence"
```

---

## Task 4: Address Evidence Reference APIs

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_address_evidence_api.py`
- Modify: `docs/api-reference.md`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_address_evidence_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_address_evidence_search_returns_reference_results():
    response = client.get("/api/reference/address-evidence?q=Samakushi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Samakushi"
    assert payload["results"]
    assert payload["results"][0]["name_en"] == "Samakhusi"


def test_address_evidence_resolve_returns_candidates():
    response = client.post(
        "/api/reference/address-evidence/resolve",
        json={"text": "Kathmadu Metropolitian ward 26 Samakushi", "target_field": "permanent_address"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"]
    assert payload["candidates"][0]["structured"]["district"] == "Kathmandu"


def test_address_evidence_create_and_delete_roundtrip():
    create = client.post(
        "/api/reference/address-evidence",
        json={
            "tenant_id": "demo-institution",
            "visibility": "tenant_private",
            "kind": "area_or_tole",
            "district_name": "Kathmandu",
            "local_level_name": "Kathmandu Metropolitan City",
            "ward": "26",
            "name_en": "Naya Bazaar",
            "aliases_en": ["Nayabazar"],
            "source": "manual_seed",
        },
    )

    assert create.status_code == 201
    record_id = create.json()["record"]["id"]

    search = client.get("/api/reference/address-evidence?q=Nayabazar")
    assert search.status_code == 200
    assert any(item["id"] == record_id for item in search.json()["results"])

    deleted = client.delete(f"/api/reference/address-evidence/{record_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "disabled"
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_evidence_api.py -q
```

Expected: 404 for address evidence endpoints.

- [ ] **Step 3: Add endpoints**

Modify `backend/app/main.py` near the existing `/api/reference/nepal-locations` endpoints:

```python
@app.get("/api/reference/address-evidence")
def address_evidence_reference(
    http_request: Request,
    q: str = "",
    district: str = "",
    local_level: str = "",
    ward: str = "",
    limit: int = 25,
):
    from app.services.address_evidence_store import load_address_evidence_store

    principal = resolve_principal(settings, http_request)
    require_permission(settings, http_request, "view_case")
    store = load_address_evidence_store()
    return {
        "query": q,
        "results": store.search(
            q,
            tenant_id=principal.tenant_id,
            district=district,
            local_level=local_level,
            ward=ward,
            limit=limit,
        ),
    }
```

Add `POST /resolve`, `POST /api/reference/address-evidence`, `POST /import`, `PATCH /{record_id}`, and `DELETE /{record_id}`. Mutating endpoints must call:

```python
require_permission(settings, http_request, "manage_templates")
```

- [ ] **Step 4: Document APIs**

Update `docs/api-reference.md` with:

```markdown
| `GET` | `/api/reference/address-evidence?q={query}` | Search approved address evidence records for area, tole, road, and street aliases. |
| `POST` | `/api/reference/address-evidence/resolve` | Resolve free-text OCR address text into scored, auditable address candidates. |
| `POST` | `/api/reference/address-evidence` | Create a Super Admin approved address evidence record. |
| `POST` | `/api/reference/address-evidence/import` | Import address evidence records from CSV. |
| `PATCH` | `/api/reference/address-evidence/{id}` | Update address evidence metadata or aliases. |
| `DELETE` | `/api/reference/address-evidence/{id}` | Disable an incorrect address evidence record. |
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_address_evidence_api.py tests/test_nepal_location_intelligence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add backend/app/main.py backend/tests/test_address_evidence_api.py docs/api-reference.md
git commit -m "feat: expose address evidence APIs"
```

---

## Task 5: Frontend Types and Review Candidate UI

**Files:**
- Modify: `frontend/src/types/workspace.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Modify: `frontend/scripts/workspace-types.test.mjs`

- [ ] **Step 1: Write failing frontend type test**

Modify `frontend/scripts/workspace-types.test.mjs` import:

```js
import {
  addressCandidateSources,
  documentAssetTypes,
  documentSectionSides,
  jobStatuses,
  workspaceSections,
} from "../src/types/workspace.ts";
```

Append:

```js
test("addressCandidateSources exposes auditable address evidence sources", () => {
  assert.deepEqual(addressCandidateSources, [
    "nepal_location_registry",
    "address_evidence_store",
    "fuzzy_alias_match",
    "reviewer_approved",
  ]);
});
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd frontend
npm run test
```

Expected: failure because `addressCandidateSources` is not exported.

- [ ] **Step 3: Add frontend types**

Modify `frontend/src/types/workspace.ts`:

```ts
export const addressCandidateSources = [
  "nepal_location_registry",
  "address_evidence_store",
  "fuzzy_alias_match",
  "reviewer_approved",
] as const;

export type AddressCandidateSource = (typeof addressCandidateSources)[number];

export type AddressCandidate = {
  target_field: string;
  original_ocr_value: string;
  suggested_value: string;
  structured?: {
    province?: string;
    district?: string;
    local_level?: string;
    ward?: string;
    area_or_tole?: string;
    street_or_road?: string;
  };
  confidence: number;
  status: "suggested" | "needs_review";
  sources?: string[];
  score_breakdown?: Record<string, number>;
  audit_reason?: string;
};
```

Extend existing types:

```ts
export type DocumentIntelligence = {
  address_candidates?: AddressCandidate[];
};
```

Do this by adding `address_candidates?: AddressCandidate[];` to the existing `DocumentIntelligence` shape, not by replacing it.

- [ ] **Step 4: Render address candidate cards in review fields**

In `frontend/src/components/enterprise-workspace.tsx`, inside the existing correction candidate UI, branch by candidate sources:

```tsx
const isAddressCandidate = candidateOptions.some((candidate) =>
  (candidate.sources || []).some((source) =>
    ["nepal_location_registry", "address_evidence_store", "fuzzy_alias_match", "reviewer_approved"].includes(source),
  ),
);
```

Change the heading text:

```tsx
{isAddressCandidate ? "Possible address matches" : "Possible name matches"}
```

For address candidates, show score details when available:

```tsx
{"score_breakdown" in candidate && candidate.score_breakdown ? (
  <span className="text-[11px] font-semibold text-slate-500">
    {Object.entries(candidate.score_breakdown)
      .filter(([, score]) => Number(score) > 0)
      .map(([key]) => labelize(key))
      .slice(0, 4)
      .join(" + ")}
  </span>
) : null}
```

Keep the interaction as buttons, not native dropdowns.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend
npm run test
npm run lint
```

Expected: tests and lint pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add frontend/src/types/workspace.ts frontend/src/components/enterprise-workspace.tsx frontend/scripts/workspace-types.test.mjs
git commit -m "feat: show address correction candidates"
```

---

## Task 6: Super Admin Address Dataset Controls

**Files:**
- Create: `frontend/src/lib/address-evidence.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Modify: `backend/tests/test_address_evidence_api.py`

- [ ] **Step 1: Add API helper**

Create `frontend/src/lib/address-evidence.ts`:

```ts
import { apiJson } from "./api-client";
import type { AddressCandidate } from "../types/workspace";

export type AddressEvidenceRecord = {
  id: string;
  tenant_id?: string;
  visibility?: string;
  kind: string;
  province_name?: string;
  district_name?: string;
  local_level_name?: string;
  local_level_type?: string;
  ward?: string;
  name_en: string;
  name_np?: string;
  aliases_en?: string[];
  aliases_np?: string[];
  source?: string;
  confidence_weight?: number;
  disabled?: boolean;
};

export async function searchAddressEvidence(query: string) {
  return apiJson<{ query: string; results: AddressEvidenceRecord[] }>(
    `/api/reference/address-evidence?q=${encodeURIComponent(query)}`,
    { cache: "no-store" },
  );
}

export async function resolveAddressEvidence(text: string, targetField = "address") {
  return apiJson<{ candidates: AddressCandidate[] }>("/api/reference/address-evidence/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_field: targetField }),
  });
}

export async function createAddressEvidence(record: Partial<AddressEvidenceRecord>) {
  return apiJson<{ record: AddressEvidenceRecord }>("/api/reference/address-evidence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
}
```

- [ ] **Step 2: Add admin panel state**

In `frontend/src/components/enterprise-workspace.tsx`, add state near other admin/template state:

```tsx
const [addressQuery, setAddressQuery] = useState("Samakhusi");
const [addressResults, setAddressResults] = useState<AddressEvidenceRecord[]>([]);
const [addressDraft, setAddressDraft] = useState({
  district_name: "Kathmandu",
  local_level_name: "Kathmandu Metropolitan City",
  ward: "26",
  kind: "area_or_tole",
  name_en: "",
  aliases_en: "",
});
```

Add handlers:

```tsx
async function handleSearchAddressEvidence() {
  setError(null);
  const data = await searchAddressEvidence(addressQuery);
  setAddressResults(data.results);
}

async function handleCreateAddressEvidence() {
  setError(null);
  const data = await createAddressEvidence({
    ...addressDraft,
    aliases_en: addressDraft.aliases_en
      .split("|")
      .map((item) => item.trim())
      .filter(Boolean),
    visibility: "tenant_private",
    source: "manual_seed",
  });
  setAddressResults((current) => [data.record, ...current]);
}
```

- [ ] **Step 3: Add Admin UI section**

In the Admin workspace section, add a compact panel titled `Address Dataset` with:
- search input
- search button
- add area/tole/street fields
- result list with district, local level, ward, aliases, and source

Use existing page styles and button patterns. Keep it dense and operational, not a marketing card.

- [ ] **Step 4: Run frontend verification**

Run:

```bash
cd frontend
npm run test
npm run lint
npm run build
```

Expected: test/lint/build pass.

- [ ] **Step 5: Browser verify Admin and Documents**

Use the Browser plugin against `http://localhost:3000/documents`:
- confirm Documents still renders
- navigate to Admin
- confirm `Address Dataset` is visible
- search `Samakushi`
- confirm `Samakhusi` appears

- [ ] **Step 6: Commit Task 6**

```bash
git add frontend/src/lib/address-evidence.ts frontend/src/components/enterprise-workspace.tsx backend/tests/test_address_evidence_api.py
git commit -m "feat: add address dataset admin controls"
```

---

## Task 7: Documentation and Deployment Notes

**Files:**
- Modify: `README.md`
- Modify: `docs/configuration.md`
- Modify: `docs/developer-onboarding.md`
- Modify: `docs/api-reference.md`

- [ ] **Step 1: Update README feature list**

Add:

```markdown
- Address intelligence RAG for Nepal KYC: administrative registry matching, road/tole evidence, fuzzy address suggestions, and reviewer-approved learning.
```

- [ ] **Step 2: Update configuration docs**

Add to `docs/configuration.md`:

```markdown
| `LIPIOCR_ADDRESS_EVIDENCE_PATH` | `storage/address-evidence/address_evidence.json` | Local JSON store for tenant-approved address evidence. Use a mounted path for on-prem deployments. |
```

- [ ] **Step 3: Update developer onboarding**

Add this section:

````markdown
## Address Evidence Dataset

LipiOCR ships with a small safe development seed in `backend/app/data/address_evidence_seed.json`.
Tenant-approved evidence is stored outside Git by default:

```bash
export LIPIOCR_ADDRESS_EVIDENCE_PATH=storage/address-evidence/address_evidence.json
```

Use the Super Admin Address Dataset panel or `/api/reference/address-evidence/import` to add institution-approved road, street, and tole records.
Reviewer-corrected full home addresses must remain tenant-private. Convert only non-personal area, tole, road, or street names into reusable evidence.
````

- [ ] **Step 4: Run docs grep**

Run:

```bash
rg -n "LIPIOCR_ADDRESS_EVIDENCE_PATH|address-evidence|Address Dataset" README.md docs
```

Expected: new config, API, and onboarding references appear.

- [ ] **Step 5: Commit Task 7**

```bash
git add README.md docs/configuration.md docs/developer-onboarding.md docs/api-reference.md
git commit -m "docs: document address intelligence dataset"
```

---

## Task 8: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd backend
.venv/bin/pytest tests -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests and build**

Run:

```bash
cd frontend
npm run test
npm run lint
npm run build
```

Expected: frontend tests, lint, and production build pass.

- [ ] **Step 3: Restart local backend if needed**

If backend code changed and the server is running on `8010`, restart it with the same environment used by the project:

```bash
cd backend
env LIPIOCR_OCR_PROVIDER=gemma_vision \
  LIPIOCR_GEMMA_ENABLED=true \
  LIPIOCR_GEMMA_API_BASE=http://127.0.0.1:8003/v1 \
  LIPIOCR_GEMMA_MODEL=gemma-4-26b-4bit \
  LIPIOCR_GEMMA_TIMEOUT_SECONDS=180 \
  LIPIOCR_GEMMA_MAX_TOKENS=2000 \
  LIPIOCR_API_AUTH_ENABLED=false \
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
```

- [ ] **Step 4: Browser verify end-to-end**

Use Browser plugin:
- open `http://localhost:3000/documents`
- confirm Documents workspace renders
- upload or use a sample document with address text
- confirm address candidate cards appear under address fields
- confirm choosing a candidate updates the draft value
- open Admin and confirm Address Dataset search/create controls render

- [ ] **Step 5: Final status**

Run:

```bash
git status --short
```

Expected: only intentional uncommitted local artifacts remain, such as ignored generated storage files. Report any unrelated pre-existing dirty files separately.

---

## Self-Review Checklist

Spec coverage:
- Structured administrative registry: Task 2 and Task 3.
- Area/tole/street evidence store: Task 1 and Task 4.
- Reviewer-safe candidate UI: Task 5.
- Super Admin dataset management: Task 6.
- API design: Task 4.
- Privacy/on-prem/SaaS docs: Task 7.
- Tests and verification: Task 8.

Intentional deferral:
- Full embedding/vector index is not implemented in this first slice. The store and candidate interfaces are shaped so a vector provider can be added behind `AddressEvidenceStore.search` without changing document intelligence or frontend review contracts.
