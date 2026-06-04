# LipiOCR Model Training Strategy

LipiOCR should train its own Nepal-specific model family, but not as one giant all-purpose model. The production path is a layered system where OCR reads, vision models understand document structure, and LipiCore verifies, normalizes, and explains corrections.

## Recommended Model Split

| Layer | Train or fine-tune | Purpose |
| --- | --- | --- |
| Printed OCR | Fine-tune PaddleOCR | Read Nepali, English, digits, dates, IDs, and form text from cropped lines and full pages. |
| Handwriting OCR/ICR | Fine-tune TrOCR or a PaddleOCR recognition model | Read handwritten Nepali/English line crops, especially names, addresses, phone numbers, and ASBA/KYC form fields. |
| Region detection | Train YOLO/RT-DETR style detector | Locate photos, fingerprints/thumbprints, signatures, stamps, tables, text blocks, field labels, and field values. |
| Document classifier | Train lightweight classifier or VLM adapter | Identify citizenship front/back/combined, National ID, passport, license, ASBA, KYC forms, cheques, and unknown packets. |
| Document understanding | Fine-tune Gemma-style vision model with LoRA/QLoRA | Map OCR evidence and page images into structured Nepal KYC JSON with bilingual fields and uncertainty reasons. |
| Correction ranking | Train small ranker plus deterministic reference rules | Suggest reviewer-safe corrections using Nepali names, locations, address evidence, bilingual pairs, and date patterns. |

Gemma vision should not replace OCR. It should become LipiVision, the document-understanding layer that reasons over the image, OCR evidence, layout, and Nepal reference intelligence.

## Target Architecture

```text
Document image or PDF
  ↓
Image quality and preprocessing
  ↓
Region detector
  - photo
  - fingerprint/thumbprint
  - signature
  - stamp
  - table
  - printed text
  - handwritten text
  ↓
OCR ensemble
  - fine-tuned PaddleOCR for printed Nepali/English
  - handwriting recognizer for line crops
  - Tesseract or external provider fallback for comparison
  ↓
LipiVision
  - document type
  - side or combined photocopy detection
  - field mapping
  - table and form understanding
  - structured JSON proposal
  ↓
LipiCore
  - bilingual normalization
  - Nepali/English name reconciliation
  - BS/AD date conversion
  - Nepal location and address matching
  - confidence repair with audit reasons
  ↓
Reviewer
  - approve
  - correct
  - draw boxes
  - save ground truth
  ↓
Training dataset exports
```

## Datasets To Build

Training data must come from approved documents, reviewer corrections, and manually labeled regions. Do not train on raw OCR guesses as ground truth.

### Document Classification Dataset

Each page receives a document class, variant, side, language profile, and image-quality tags.

```json
{
  "image": "pages/doc_0001_page_1.jpg",
  "label": "nepali_citizenship_front",
  "variant": "old_format",
  "surface": "front",
  "quality": "mobile_photo",
  "languages": ["ne", "en"]
}
```

Initial classes:

- `citizenship_front`
- `citizenship_back`
- `citizenship_combined_front_back`
- `national_id_front`
- `national_id_back`
- `passport`
- `driving_license`
- `asba_form`
- `kyc_form`
- `cheque`
- `unknown_financial_document`

### OCR Text Crop Dataset

Line and word crops power printed and handwritten OCR fine-tuning.

```json
{
  "image": "crops/text_0001.jpg",
  "text": "राजेश घले",
  "script": "devanagari",
  "kind": "printed",
  "field_hint": "name_ne"
}
```

Handwriting samples should be separate from printed samples:

```json
{
  "image": "crops/hand_0001.jpg",
  "text": "रुद्रमान इसुवा",
  "script": "devanagari",
  "kind": "handwritten",
  "field_hint": "applicant_name_ne"
}
```

### Region Detection Dataset

Use YOLO or COCO exports for visual regions.

```text
class x_center y_center width height
```

Initial classes:

- `photo`
- `fingerprint`
- `thumbprint`
- `signature`
- `stamp`
- `table`
- `printed_text`
- `handwritten_text`
- `field_label`
- `field_value`
- `date_region`
- `address_region`
- `citizenship_number_region`

### Field Extraction Dataset

Document-level JSON teaches LipiVision how to return complete KYC records.

```json
{
  "image": "pages/citizenship_0001.jpg",
  "document_type": "nepali_citizenship",
  "fields": {
    "citizenship_number": "२४८/३६१६३",
    "name_ne": "राजेश घले",
    "name_en": "Rajesh Ghale",
    "dob_bs": "२०३७-०१-२८",
    "dob_ad": "1980-05-10",
    "father_name_ne": "प्रसाद घले",
    "birth_district_ne": "काठमाडौं",
    "photo_present": true,
    "fingerprint_present": true
  }
}
```

### Bilingual Correction Dataset

This powers reviewer-safe candidate correction, not silent overwrite.

```json
{
  "ocr_value": "काकी",
  "suggested_value": "कार्की",
  "english_pair": "Karki",
  "field": "last_name",
  "sources": ["nepali_name_lexicon", "english_transliteration_pair"],
  "reviewer_approved": true
}
```

### Address Intelligence Dataset

Address data must avoid personal home-address leakage. Promote only approved non-personal road, tole, area, municipality, VDC, ward, and district evidence.

```json
{
  "raw": "का.म.न.पा वडा नं २९ काठमाडौं",
  "normalized": {
    "province": "Bagmati",
    "district": "Kathmandu",
    "local_level": "Kathmandu Metropolitan City",
    "ward": "29"
  },
  "evidence_scope": "shared_reference"
}
```

## Dataset Capture Inside The Product

Every approved review should create training artifacts:

1. Original uploaded file.
2. Rendered page images.
3. Cleaned/preprocessed images.
4. OCR text with boxes and confidence.
5. Reviewer-corrected fields.
6. Field-level crop images.
7. Region boxes for photo, fingerprint, signature, stamp, tables, labels, and values.
8. Original value, normalized value, corrected value, confidence, source, and audit reason.
9. Approval status and reviewer identity for governance.

Suggested internal tables:

- `training_documents`
- `training_pages`
- `training_regions`
- `training_text_crops`
- `training_field_labels`
- `training_corrections`
- `training_exports`
- `training_runs`
- `training_metrics`

## Export Formats

LipiOCR should export standard training formats:

| Export | Used for |
| --- | --- |
| PaddleOCR detection | Text box detector training. |
| PaddleOCR recognition | Printed Nepali/English text recognition. |
| YOLO | Photo, fingerprint, signature, stamp, table, and region detection. |
| COCO | More detailed region/layout detection training. |
| Gemma/LipiVision JSONL | Image-to-structured-JSON instruction tuning. |
| Benchmark CSV/JSON | Field-level accuracy reports by document type and variant. |

Example PaddleOCR recognition export:

```text
crops/name_0001.jpg	राजेश घले
crops/date_0002.jpg	२०३७-०१-२८
```

Example LipiVision JSONL export:

```json
{"image":"pages/citizenship_0001.jpg","messages":[{"role":"user","content":"Extract all KYC fields as strict JSON. Preserve Nepali and English values separately."},{"role":"assistant","content":"{\"document_type\":\"citizenship\",\"name_ne\":\"राजेश घले\",\"name_en\":\"Rajesh Ghale\"}"}]}
```

## Data Volume Targets

| Dataset | First useful target | Strong production target |
| --- | ---: | ---: |
| Document classification pages | 1,000 | 10,000+ |
| Region-labeled pages | 2,000 | 20,000+ |
| Printed OCR text crops | 50,000 | 500,000+ |
| Handwriting line crops | 25,000 | 100,000+ |
| Fully labeled KYC documents | 2,000 | 20,000+ |
| Reviewer-approved corrections | 10,000 | 250,000+ |

## Training Difficulty

| Component | Difficulty | Notes |
| --- | --- | --- |
| Document classifier | Medium | Fast to train once labels exist. |
| Region detector | Medium | Bounding boxes are straightforward to label and verify. |
| Printed OCR fine-tune | Medium-hard | Exact text labels are required. |
| Handwritten Nepali OCR | Hard | Needs many line crops and careful benchmark reporting. |
| LipiVision field extraction | Hard | Needs complete document-level JSON and strict evaluation. |
| 99% field-level accuracy | Very hard | Requires benchmark governance, reviewer feedback, and validation rules. |

## Training Roadmap

1. Add training-data capture to review approval.
2. Add canvas labeling for fields and visual regions.
3. Export PaddleOCR, YOLO/COCO, LipiVision JSONL, and benchmark files.
4. Train a region detector for photo, fingerprint, signature, stamp, table, printed text, and handwriting.
5. Fine-tune PaddleOCR on printed Nepali/English crops.
6. Fine-tune handwriting OCR on approved line crops.
7. Fine-tune LipiVision with LoRA/QLoRA for document-to-JSON extraction.
8. Add model registry, versioning, benchmark reports, and rollback.
9. Use reviewer corrections as continuous-learning candidates after approval.

## Production Rules

- Do not train on unapproved raw OCR output.
- Do not commit real KYC images, raw names, home addresses, or customer documents to Git.
- Keep institution datasets tenant-private unless anonymized and contractually approved.
- Keep benchmark sets frozen and versioned so accuracy claims are repeatable.
- Report field-level accuracy by document type, layout variant, language, and handwriting/printed status.
- Keep human review in the loop until a field and document type has measured accuracy good enough for auto-approval.
