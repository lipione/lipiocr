import base64
import io
import json
import mimetypes
import re
from collections import defaultdict
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


def _asset_block_type(raw: Dict[str, object]) -> str:
    marker = str(raw.get("asset_type") or raw.get("type") or raw.get("block_type") or "").lower().strip()
    if marker in {"photo", "portrait", "face"}:
        return "photo"
    if marker in {"fingerprint", "thumbprint", "left_thumbprint", "right_thumbprint"}:
        return "fingerprint"
    if marker in {"signature", "sign"}:
        return "signature"
    if marker in {"stamp", "seal"}:
        return "stamp"
    if marker in {"chip", "card_chip"}:
        return "chip"
    return "visual_asset"


def _valid_bbox(value: object) -> Optional[List[int]]:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [int(coordinate) for coordinate in value]
    except (TypeError, ValueError):
        return None


def _bbox_size(bbox: List[int]) -> tuple[int, int]:
    return abs(int(bbox[2]) - int(bbox[0])), abs(int(bbox[3]) - int(bbox[1]))


def _text_weight(value: object) -> int:
    return len(re.sub(r"\s+", "", str(value or "")))


def looks_like_transposed_bbox(bbox: List[int], text: object = "") -> bool:
    width, height = _bbox_size(bbox)
    if width <= 0 or height <= 0:
        return False
    if _text_weight(text) < 2:
        return False
    return width <= 80 and height >= max(50, width * 2)


def normalize_bbox_orientation(bbox: List[int], text: object = "") -> List[int]:
    if looks_like_transposed_bbox(bbox, text):
        return [bbox[1], bbox[0], bbox[3], bbox[2]]
    return bbox


def normalize_gemma_observation_bboxes(observations: List[OcrObservation]) -> List[OcrObservation]:
    normalized: List[OcrObservation] = []
    for observation in observations:
        bbox = observation.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            observation = OcrObservation(observation)
            observation["bbox"] = normalize_bbox_orientation([int(value) for value in bbox], observation.get("text"))
        normalized.append(observation)
    return normalized


def _as_int(value: object, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def observations_from_tesseract_data(data: Dict[str, List[object]], *, page_width: int, page_height: int) -> List[OcrObservation]:
    grouped: Dict[tuple[object, object, object, object], list[dict[str, object]]] = defaultdict(list)
    texts = data.get("text", [])
    for index, raw_text in enumerate(texts):
        text = str(raw_text or "").strip()
        if not text:
            continue
        confidence = _as_float((data.get("conf") or [])[index] if index < len(data.get("conf", [])) else None, -1)
        left = _as_int((data.get("left") or [])[index] if index < len(data.get("left", [])) else None)
        top = _as_int((data.get("top") or [])[index] if index < len(data.get("top", [])) else None)
        width = _as_int((data.get("width") or [])[index] if index < len(data.get("width", [])) else None)
        height = _as_int((data.get("height") or [])[index] if index < len(data.get("height", [])) else None)
        if width <= 0 or height <= 0:
            continue
        key = (
            (data.get("page_num") or [1])[index] if index < len(data.get("page_num", [])) else 1,
            (data.get("block_num") or [1])[index] if index < len(data.get("block_num", [])) else 1,
            (data.get("par_num") or [1])[index] if index < len(data.get("par_num", [])) else 1,
            (data.get("line_num") or [index])[index] if index < len(data.get("line_num", [])) else index,
        )
        grouped[key].append(
            {
                "text": text,
                "confidence": confidence,
                "bbox": [left, top, left + width, top + height],
            }
        )

    observations: List[OcrObservation] = []
    for _key, words in sorted(grouped.items(), key=lambda item: (min(word["bbox"][1] for word in item[1]), min(word["bbox"][0] for word in item[1]))):
        text = " ".join(str(word["text"]) for word in words)
        confidences = [float(word["confidence"]) for word in words if float(word["confidence"]) >= 0]
        bbox = [
            min(int(word["bbox"][0]) for word in words),
            min(int(word["bbox"][1]) for word in words),
            max(int(word["bbox"][2]) for word in words),
            max(int(word["bbox"][3]) for word in words),
        ]
        observations.append(
            OcrObservation(
                field_key="raw_text",
                text=text,
                confidence=round((sum(confidences) / len(confidences)) / 100, 2) if confidences else 0.45,
                block_type="text",
                language="mixed",
                bbox=bbox,
                page_width=page_width,
                page_height=page_height,
            )
        )
    return observations


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

    raw_assets = payload.get("asset_regions") or payload.get("assets") or payload.get("visual_regions") or []
    for raw in raw_assets:
        if not isinstance(raw, dict):
            continue
        block_type = _asset_block_type(raw)
        label = str(raw.get("label") or raw.get("asset_type") or raw.get("type") or block_type).strip()
        if not label:
            continue
        observation = OcrObservation(
            field_key="raw_text",
            text=label,
            confidence=_as_float(raw.get("confidence"), 0.68),
            block_type=block_type,
            language=str(raw.get("language") or raw.get("lang") or "visual"),
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

        image = Image.open(file_path)
        data = pytesseract.image_to_data(image, lang="eng+nep", output_type=pytesseract.Output.DICT)
        observations = observations_from_tesseract_data(data, page_width=image.width, page_height=image.height)
        if observations:
            return observations
        text = pytesseract.image_to_string(image, lang="eng+nep")
        return [OcrObservation(field_key="raw_text", text=text.strip(), confidence=0.50)]


class PaddleOcrProvider:
    name = "paddleocr"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._engine = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("Install backend optional dependency group: pip install -e '.[ocr]'") from exc

        options = {
            "use_angle_cls": True,
            "lang": self.settings.paddle_lang,
        }
        if self.settings.paddle_det_model_dir:
            options["det_model_dir"] = self.settings.paddle_det_model_dir
        if self.settings.paddle_rec_model_dir:
            options["rec_model_dir"] = self.settings.paddle_rec_model_dir
        if self.settings.paddle_cls_model_dir:
            options["cls_model_dir"] = self.settings.paddle_cls_model_dir
        if self.settings.paddle_rec_char_dict_path:
            options["rec_char_dict_path"] = self.settings.paddle_rec_char_dict_path
        self._engine = PaddleOCR(**options)
        return self._engine

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        engine = self._get_engine()
        result = engine.ocr(str(file_path), cls=True)
        observations: List[OcrObservation] = []
        for page in result or []:
            for item in page or []:
                text = item[1][0]
                confidence = float(item[1][1])
                bbox = item[0] if item and len(item) > 0 else None
                observation = OcrObservation(
                    field_key="raw_text",
                    text=text,
                    confidence=confidence,
                    block_type="text",
                    language=self.settings.paddle_lang,
                )
                if isinstance(bbox, list) and len(bbox) == 4:
                    xs = [point[0] for point in bbox if isinstance(point, list) and len(point) >= 2]
                    ys = [point[1] for point in bbox if isinstance(point, list) and len(point) >= 2]
                    if xs and ys:
                        observation["bbox"] = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
                observations.append(observation)
        return observations


class GemmaVisionOcrProvider:
    name = "gemma_vision"

    def __init__(self, settings: Settings, http_client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        self.http_client = http_client or httpx.Client(timeout=settings.gemma_timeout_seconds)

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        full_page_error: Optional[Exception] = None
        observations: List[OcrObservation] = []
        try:
            observations = self._read_image_bytes(
                file_path.read_bytes(),
                mimetypes.guess_type(file_path.name)[0] or "image/jpeg",
                document_type,
            )
        except (httpx.TimeoutException, RuntimeError) as exc:
            full_page_error = exc

        if self._should_run_tiled_pass(file_path, observations, full_page_error):
            tiled_observations = self._read_tiled(file_path, document_type)
            if tiled_observations and (
                full_page_error
                or self._ocr_quality_score(tiled_observations) > self._ocr_quality_score(observations)
            ):
                observations = tiled_observations

        if full_page_error and not observations:
            raise full_page_error
        if not observations:
            raise RuntimeError("Gemma vision OCR returned no text lines")
        return normalize_gemma_observation_bboxes(observations)

    def _prompt(self, document_type: DocumentType, *, tile_context: str = "") -> str:
        tile_instruction = ""
        if tile_context:
            tile_instruction = (
                f" {tile_context} Return bbox coordinates relative to this tile image, not the full page. "
                "Do not mention that this is a tile in extracted text."
            )
        prompt = (
            "You are LipiCore Vision 12B OCR/ICR for Nepal financial institution documents. "
            "First act as a strict OCR engine: transcribe every visible word, label, filled value, table cell, "
            "stamp text, seal text, and handwritten mark from the image. Include printed Nepali Devanagari, English, "
            "numbers, and handwritten Nepali or English. Preserve original script and numerals. "
            "Do not paraphrase visible text, rewrite it as sentences, or infer values that are not visible. "
            "Do not skip uncertain handwriting; return it with lower confidence. "
            "For table or form layouts, preserve row order from top-to-bottom and left-to-right. "
            "When a printed label and handwritten value are on the same line, return both in lines and also return "
            "the handwritten value as a structured field candidate when possible. "
            "Mark handwritten lines with script='handwriting' and printed lines with script='printed'. "
            "Also extract structured field candidates for financial onboarding and KYC forms, and asset regions for "
            "photos, fingerprints/thumbprints, signatures, stamps/seals, chips, QR codes, and barcodes. "
            "Use canonical keys when visible: full_name, full_name_np, full_name_en, applicant_name, applicant_name_np, "
            "applicant_name_en, bank_name, dp_id, client_id, boid, account_number, amount, applied_units, mobile, email, "
            "citizenship_number, dob, dob_bs, dob_ad, issue_date, issue_date_bs, issue_date_ad, gender, citizenship_type, "
            "birth_place, permanent_address, father_name, father_name_np, mother_name, mother_name_np, spouse_name, "
            "issuing_office, issuing_authority_name, issuing_authority_designation, grandfather_name. "
            "For Nepali citizenship, capture both front and back/English summary fields when visible, including "
            "birth-place and permanent-address components, parent names, citizenship kind, copy type, issuing office, "
            "issuing officer, photo, holder signature, and left/right thumbprints. "
            "For C-ASBA/IPO forms, read the filled handwriting inside boxes and rows, not only the printed labels. "
            "All bbox coordinates must use [left, top, right, bottom] pixel order. "
            f"{tile_instruction} "
            "Return JSON only with schema: "
            "{document_type,lines:[{text,confidence,script,language,bbox}],"
            "fields:[{key,value,confidence,script,language,bbox}],"
            "asset_regions:[{type,label,confidence,bbox}]}. "
            f"Expected document type: {document_type.value}."
        )
        return prompt

    def _read_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str,
        document_type: DocumentType,
        *,
        tile_context: str = "",
        max_tokens: Optional[int] = None,
    ) -> List[OcrObservation]:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        token_limit = max_tokens if max_tokens is not None else self.settings.gemma_max_tokens
        payload = {
            "model": self.settings.gemma_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt(document_type, tile_context=tile_context)},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": max(500, min(token_limit, 3000)),
        }
        if self.settings.gemma_require_json:
            payload["response_format"] = {"type": "json_object"}

        response = self.http_client.post(
            f"{self.settings.gemma_api_base.rstrip('/')}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        observations = normalize_gemma_observation_bboxes(parse_gemma_ocr_content(content))
        if not observations:
            raise RuntimeError("Gemma vision OCR returned no text lines")
        return observations

    def _should_run_tiled_pass(
        self,
        file_path: Path,
        observations: List[OcrObservation],
        full_page_error: Optional[Exception],
    ) -> bool:
        if not self.settings.gemma_vision_tiling_enabled:
            return False
        if full_page_error is not None:
            return True
        if self._text_line_count(observations) >= max(1, self.settings.gemma_vision_tile_min_lines) and self._unique_text_line_count(
            observations
        ) >= max(4, self.settings.gemma_vision_tile_min_lines // 2):
            return False
        try:
            from PIL import Image

            with Image.open(file_path) as image:
                width, height = image.size
        except Exception:
            return False
        return max(width, height) >= 1200

    def _read_tiled(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise RuntimeError("Install Pillow to use LipiCore Vision tiled OCR") from exc

        with Image.open(file_path) as raw_image:
            image = ImageOps.exif_transpose(raw_image).convert("RGB")

        width, height = image.size
        tile_count = max(2, min(self.settings.gemma_vision_tile_count, 8))
        overlap = max(0, min(self.settings.gemma_vision_tile_overlap_px, max(0, height // 4)))
        base_step = max(1, height // tile_count)
        merged: List[OcrObservation] = []
        seen: set[tuple[str, str, str]] = set()

        for index in range(tile_count):
            top = max(0, index * base_step - (overlap if index else 0))
            bottom = height if index == tile_count - 1 else min(height, (index + 1) * base_step + overlap)
            if bottom <= top:
                continue
            tile = image.crop((0, top, width, bottom))
            buffer = io.BytesIO()
            tile.save(buffer, format="JPEG", quality=88, optimize=True)
            try:
                tile_observations = self._read_image_bytes(
                    buffer.getvalue(),
                    "image/jpeg",
                    document_type,
                    tile_context=f"This is vertical page region {index + 1} of {tile_count}, y={top}..{bottom}.",
                    max_tokens=min(self.settings.gemma_max_tokens, 1400),
                )
            except (httpx.HTTPError, RuntimeError):
                continue
            for observation in tile_observations:
                adjusted = self._offset_observation_bbox(observation, y_offset=top)
                key = (
                    str(adjusted.get("field_key") or ""),
                    str(adjusted.get("text") or "").strip(),
                    str(adjusted.get("bbox") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(adjusted)

        return normalize_gemma_observation_bboxes(merged)

    def _offset_observation_bbox(self, observation: OcrObservation, *, y_offset: int) -> OcrObservation:
        adjusted = OcrObservation(observation)
        bbox = _valid_bbox(adjusted.get("bbox"))
        if bbox:
            adjusted["bbox"] = [bbox[0], bbox[1] + y_offset, bbox[2], bbox[3] + y_offset]
        return adjusted

    def _text_line_count(self, observations: List[OcrObservation]) -> int:
        return len(
            [
                observation
                for observation in observations
                if observation.get("field_key") == "raw_text"
                and str(observation.get("text") or "").strip()
                and observation.get("block_type") not in {"photo", "fingerprint", "signature", "stamp", "chip", "visual_asset"}
            ]
        )

    def _unique_text_line_count(self, observations: List[OcrObservation]) -> int:
        normalized_lines = {
            re.sub(r"\s+", " ", str(observation.get("text") or "").strip()).lower()
            for observation in observations
            if observation.get("field_key") == "raw_text"
            and str(observation.get("text") or "").strip()
            and observation.get("block_type") not in {"photo", "fingerprint", "signature", "stamp", "chip", "visual_asset"}
        }
        return len(normalized_lines)

    def _ocr_quality_score(self, observations: List[OcrObservation]) -> float:
        text_chars = sum(
            len(re.sub(r"\s+", "", str(observation.get("text") or "")))
            for observation in observations
            if str(observation.get("text") or "").strip()
        )
        structured_count = len(
            [
                observation
                for observation in observations
                if observation.get("field_key") != "raw_text"
                or observation.get("block_type") in {"photo", "fingerprint", "signature", "stamp", "chip", "visual_asset"}
            ]
        )
        return (self._unique_text_line_count(observations) * 4.0) + (structured_count * 3.0) + (text_chars / 50.0)


def get_ocr_provider(name: str = "mock", *, settings: Optional[Settings] = None) -> OcrProvider:
    active_settings = settings or Settings()
    providers = {
        "mock": MockOcrProvider,
        "tesseract": TesseractOcrProvider,
    }
    if name in {"gemma_vision", "gemma-vision", "gemma"}:
        return GemmaVisionOcrProvider(active_settings)
    if name in {"paddleocr", "paddle", "paddle_gemma", "paddle-gemma"}:
        return PaddleOcrProvider(active_settings)
    provider_cls = providers.get(name)
    if provider_cls is None:
        raise ValueError(f"Unsupported OCR provider: {name}")
    return provider_cls()
