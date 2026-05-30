import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Dict, List, Optional, Protocol

import httpx

from app.core.config import Settings
from app.models import DocumentType


class OcrObservation(Dict[str, object]):
    pass


class OcrProvider(Protocol):
    name: str

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        ...


JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
JSON_TEXT_VALUE_RE = re.compile(r'"(?:text|value)"\s*:\s*"((?:\\.|[^"\\])*)"')


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    cleaned = JSON_FENCE_RE.sub("", cleaned).strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    return cleaned


def _as_float(value: object, fallback: float = 0.55) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return fallback


def _block_type(raw: Dict[str, object]) -> str:
    marker = str(raw.get("script") or raw.get("block_type") or raw.get("type") or "").lower()
    return "handwriting" if "hand" in marker else "text"


def _valid_bbox(value: object) -> Optional[List[int]]:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [int(coordinate) for coordinate in value]
    except (TypeError, ValueError):
        return None


def _decode_json_string(value: str) -> str:
    try:
        return str(json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return value


def _fallback_observations_from_content(content: str) -> List[OcrObservation]:
    cleaned = _clean_json_content(content)
    observations = [
        OcrObservation(
            field_key="raw_text",
            text=_decode_json_string(match.group(1)).strip(),
            confidence=0.45,
            block_type="text",
            language="mixed",
        )
        for match in JSON_TEXT_VALUE_RE.finditer(cleaned)
        if _decode_json_string(match.group(1)).strip()
    ]
    if observations:
        return observations

    return [
        OcrObservation(
            field_key="raw_text",
            text=line.strip(),
            confidence=0.35,
            block_type="text",
            language="mixed",
        )
        for line in cleaned.splitlines()[:80]
        if line.strip()
    ]


def parse_gemma_ocr_content(content: str) -> List[OcrObservation]:
    try:
        payload = json.loads(_clean_json_content(content))
    except json.JSONDecodeError:
        return _fallback_observations_from_content(content)
    raw_lines = payload.get("lines") or payload.get("ocr_lines") or payload.get("blocks") or []
    if isinstance(payload.get("text"), str) and not raw_lines:
        raw_lines = [{"text": line} for line in payload["text"].splitlines()]

    observations: List[OcrObservation] = []
    for raw in raw_lines:
        if isinstance(raw, str):
            raw = {"text": raw}
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or raw.get("value") or "").strip()
        if not text:
            continue
        observation = OcrObservation(
            field_key="raw_text",
            text=text,
            confidence=_as_float(raw.get("confidence")),
            block_type=_block_type(raw),
            language=str(raw.get("language") or raw.get("lang") or "mixed"),
        )
        bbox = _valid_bbox(raw.get("bbox"))
        if bbox is not None:
            observation["bbox"] = bbox
        observations.append(observation)

    raw_fields = payload.get("fields") or payload.get("extracted_fields") or payload.get("field_candidates") or []
    for raw in raw_fields:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or raw.get("field") or "").strip()
        value = str(raw.get("value") or raw.get("text") or "").strip()
        if not key or not value:
            continue
        observation = OcrObservation(
            field_key=key,
            text=value,
            confidence=_as_float(raw.get("confidence"), 0.62),
            block_type=_block_type(raw),
            language=str(raw.get("language") or raw.get("lang") or "mixed"),
        )
        bbox = _valid_bbox(raw.get("bbox"))
        if bbox is not None:
            observation["bbox"] = bbox
        observations.append(observation)
    return observations


class MockOcrProvider:
    name = "mock"

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        samples = {
            DocumentType.citizenship: [
                self._raw(
                    "नेपाल सरकार\n"
                    "गृह मन्त्रालय\n"
                    "नेपाली नागरिकताको प्रमाणपत्र\n"
                    "ना.प्र.नं.: 27-01-78-12345\n"
                    "नाम थर: सीता शर्मा\n"
                    "जन्म मिति: २०४९-०१-०१\n"
                    "स्थायी वासस्थान: काठमाडौं-१०\n"
                    "बाबुको नाम थर: हरि शर्मा\n"
                    "वडा नं.: १०",
                    0.74,
                ),
                self._field("name", "Sita Sharma", 0.96),
                self._field("dob", "1992-04-13", 0.92),
                self._field("citizenship_number", "27-01-78-12345", 0.91),
                self._field("address", "Kathmandu-10", 0.93),
                self._field("father_mother_name", "Hari Sharma", 0.84),
            ],
            DocumentType.account_opening: [
                self._field("customer_name", "Sita Sharma", 0.94),
                self._field("mobile", "98410O0000", 0.77),
                self._field("address", "Kathmandu-10", 0.91),
                self._field("account_type", "Savings", 0.93),
                self._field("pan", "123456789", 0.89),
                self._field("email", "sita.sharma at example.com", 0.62),
            ],
            DocumentType.cheque: [
                self._field("cheque_number", "00124578", 0.93),
                self._field("date", "2026-05-27", 0.86),
                self._field("amount", "25000.00", 0.82),
                self._field("payee", "Sita Sharma", 0.80),
            ],
            DocumentType.national_id: [
                self._raw(
                    "नेपाल सरकार\n"
                    "राष्ट्रिय परिचयपत्र\n"
                    "परिचयपत्र नं: ०२३-४५६-२१३०\n"
                    "नाम थर: भगवती कुमारी\n"
                    "Given Name: Bhagawati Kumari\n"
                    "जन्म मिति: 1978-02-05\n"
                    "आमाको नाम: सरिता कुमारी पोखरेल\n"
                    "बाबुको नाम: विष्णु प्रसाद पोखरेल\n"
                    "जारी मिति: 01-01-2017",
                    0.75,
                ),
                self._field("national_id_number", "023-456-2130", 0.92),
                self._field("full_name", "Bhagawati Kumari", 0.90),
                self._field("dob", "1978-02-05", 0.87),
                self._field("gender", "F", 0.83),
                self._field("issue_date", "2017-01-01", 0.81),
            ],
            DocumentType.passport: [
                self._raw(
                    "नेपाल NEPAL\n"
                    "राहदानी Passport\n"
                    "Type: P\n"
                    "Country Code: NPL\n"
                    "Passport No: 05232944\n"
                    "Surname: Ghimire\n"
                    "Given Name: Ram\n"
                    "Nationality: Nepalese\n"
                    "Date of Birth: 1964-03-17\n"
                    "Place of Birth: Tanahun\n"
                    "Date of Issue: 2011-04-17\n"
                    "Date of Expiry: 2021-04-16\n"
                    "P<NPLGHIMIRE<<RAM<<<<<<<<<<<<<<<<<<<<<<<<",
                    0.76,
                ),
                self._field("passport_number", "05232944", 0.92),
                self._field("surname", "Ghimire", 0.89),
                self._field("given_name", "Ram", 0.88),
                self._field("nationality", "Nepalese", 0.90),
                self._field("dob", "1964-03-17", 0.86),
                self._field("expiry_date", "2021-04-16", 0.86),
                self._field("mrz_line_1", "P<NPLGHIMIRE<<RAM<<<<<<<<<<<<<<<<<<<<<<<<", 0.82),
            ],
            DocumentType.driving_license: [
                self._raw(
                    "Government of Nepal\n"
                    "Driving License\n"
                    "D.L.No.: 03-06-00354234\n"
                    "Name: Kiran Lama\n"
                    "Address: Kakani-08, Nuwakot, Bagmati, Nepal\n"
                    "ठेगाना: ककनी-०८, नुवाकोट\n"
                    "B.G.: AB+\n"
                    "D.O.B.: 1993-11-10\n"
                    "D.O.I.: 2017-12-31\n"
                    "D.O.E.: 2022-12-30\n"
                    "Citizenship No.: 251059/6599\n"
                    "Phone No.: 9869061498\n"
                    "Category: A",
                    0.77,
                ),
                self._field("license_number", "03-06-00354234", 0.91),
                self._field("full_name", "Kiran Lama", 0.90),
                self._field("blood_group", "AB+", 0.86),
                self._field("dob", "1993-11-10", 0.86),
                self._field("citizenship_number", "251059/6599", 0.84),
                self._field("category", "A", 0.87),
            ],
            DocumentType.ipo_application: [
                self._raw(
                    "किसान माइक्रोफाइनान्स वित्तीय संस्था लिमिटेड\n"
                    "शेयर खरिद दरखास्त फारम\n"
                    "Application No: 011908\n"
                    "Applicant Name: Ashish Singh\n"
                    "No. of Share Applied: 500\n"
                    "Amount Deposited: 50000\n"
                    "BOID: 13013700007004469\n"
                    "Bank Name: Nepal Bank Limited\n"
                    "Father's Name: Fathers Name\n"
                    "Grandfather's Name: Grandfathers Name\n"
                    "Permanent Address: Kathmandu\n"
                    "Mobile No: 9841000000",
                    0.72,
                ),
                self._field("company_name", "Kisan Micro Finance Bittiya Sanstha Ltd", 0.88),
                self._field("application_number", "011908", 0.90),
                self._field("applicant_name", "Ashish Singh", 0.88),
                self._field("applied_units", "500", 0.85),
                self._field("amount", "50000", 0.84),
                self._field("boid", "13013700007004469", 0.82),
            ],
            DocumentType.asba_application: [
                self._raw(
                    "NMB BANK LIMITED\n"
                    "हितोपत्र खरिद सार्वजनिक निष्कासन दरखास्त फारम\n"
                    "Applicant Name: Rudra Man Isuwa\n"
                    "Permanent Address (in English): Bagmati, Kathmandu-22\n"
                    "Current Address (in English): Bagmati, Kathmandu\n"
                    "Father Name: Guru Man Isuwa\n"
                    "Grandfather Name: Krishna Man Isuwa\n"
                    "DP ID: 13013700\n"
                    "Client ID: 00151978\n"
                    "Bank Account No: 007004469105\n"
                    "Applied Units: 400\n"
                    "Amount: 40000\n"
                    "मोबाइल नं: 9808525464\n"
                    "इमेल ठेगाना: rudraman@gmail.com",
                    0.73,
                ),
                self._field("bank_name", "NMB Bank Limited", 0.91),
                self._field("applicant_name", "Rudra Man Isuwa", 0.87),
                self._field("dp_id", "13013700", 0.86),
                self._field("client_id", "00151978", 0.86),
                self._field("account_number", "007004469105", 0.84),
                self._field("amount", "40000", 0.84),
            ],
        }
        return samples.get(document_type, [])

    def _field(self, key: str, value: str, confidence: float) -> OcrObservation:
        return OcrObservation(field_key=key, text=value, confidence=confidence)

    def _raw(self, text: str, confidence: float) -> OcrObservation:
        return OcrObservation(field_key="raw_text", text=text, confidence=confidence)


class TesseractOcrProvider:
    name = "tesseract"

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Install backend optional dependency group: pip install -e '.[ocr]'") from exc

        text = pytesseract.image_to_string(Image.open(file_path), lang="eng+nep")
        return [OcrObservation(field_key="raw_text", text=text.strip(), confidence=0.50)]


class PaddleOcrProvider:
    name = "paddleocr"

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("Install backend optional dependency group: pip install -e '.[ocr]'") from exc

        engine = PaddleOCR(use_angle_cls=True, lang="en")
        result = engine.ocr(str(file_path), cls=True)
        observations: List[OcrObservation] = []
        for page in result or []:
            for item in page or []:
                text = item[1][0]
                confidence = float(item[1][1])
                observations.append(OcrObservation(field_key="raw_text", text=text, confidence=confidence))
        return observations


class GemmaVisionOcrProvider:
    name = "gemma_vision"

    def __init__(self, settings: Settings, http_client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        self.http_client = http_client or httpx.Client(timeout=settings.gemma_timeout_seconds)

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        mime_type = mimetypes.guess_type(file_path.name)[0] or "image/jpeg"
        image_b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
        prompt = (
            "You are LipiOCR OCR/ICR for Nepal financial institution documents. "
            "Transcribe every visible line from the image, including printed Nepali Devanagari, English, numbers, "
            "and handwritten Nepali or English. Preserve original script and numerals. "
            "Do not skip uncertain handwriting; return it with lower confidence. "
            "Mark handwritten lines with script='handwriting' and printed lines with script='printed'. "
            "Also extract structured field candidates for financial onboarding and KYC forms. "
            "Use canonical keys when visible: full_name, full_name_np, full_name_en, applicant_name, applicant_name_np, "
            "applicant_name_en, bank_name, dp_id, client_id, boid, account_number, amount, applied_units, "
            "mobile, email, citizenship_number, dob, issue_date, expiry_date, address, father_name, grandfather_name. "
            "For C-ASBA/IPO forms, read the filled handwriting inside boxes and rows, not only the printed labels. "
            "Return JSON only with schema: "
            "{document_type,lines:[{text,confidence,script,language,bbox}],"
            "fields:[{key,value,confidence,script,language,bbox}]}. "
            f"Expected document type: {document_type.value}."
        )
        payload = {
            "model": self.settings.gemma_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": max(self.settings.gemma_max_tokens, 6000),
        }
        if self.settings.gemma_require_json:
            payload["response_format"] = {"type": "json_object"}

        response = self.http_client.post(
            f"{self.settings.gemma_api_base.rstrip('/')}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        observations = parse_gemma_ocr_content(content)
        if not observations:
            raise RuntimeError("Gemma vision OCR returned no text lines")
        return observations


def get_ocr_provider(name: str = "mock", *, settings: Optional[Settings] = None) -> OcrProvider:
    providers = {
        "mock": MockOcrProvider,
        "tesseract": TesseractOcrProvider,
        "paddleocr": PaddleOcrProvider,
    }
    if name in {"gemma_vision", "gemma-vision", "gemma"}:
        return GemmaVisionOcrProvider(settings or Settings())
    provider_cls = providers.get(name)
    if provider_cls is None:
        raise ValueError(f"Unsupported OCR provider: {name}")
    return provider_cls()
