from pathlib import Path
from typing import Dict, List, Protocol

from app.models import DocumentType


class OcrObservation(Dict[str, object]):
    pass


class OcrProvider(Protocol):
    name: str

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        ...


class MockOcrProvider:
    name = "mock"

    def read(self, file_path: Path, document_type: DocumentType) -> List[OcrObservation]:
        samples = {
            DocumentType.citizenship: [
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
                self._field("national_id_number", "023-456-2130", 0.92),
                self._field("full_name", "Bhagawati Kumari", 0.90),
                self._field("dob", "1978-02-05", 0.87),
                self._field("gender", "F", 0.83),
                self._field("issue_date", "2017-01-01", 0.81),
            ],
            DocumentType.passport: [
                self._field("passport_number", "05232944", 0.92),
                self._field("surname", "Ghimire", 0.89),
                self._field("given_name", "Ram", 0.88),
                self._field("nationality", "Nepalese", 0.90),
                self._field("dob", "1964-03-17", 0.86),
                self._field("expiry_date", "2021-04-16", 0.86),
                self._field("mrz_line_1", "P<NPLGHIMIRE<<RAM<<<<<<<<<<<<<<<<<<<<<<<<", 0.82),
            ],
            DocumentType.driving_license: [
                self._field("license_number", "03-06-00354234", 0.91),
                self._field("full_name", "Kiran Lama", 0.90),
                self._field("blood_group", "AB+", 0.86),
                self._field("dob", "1993-11-10", 0.86),
                self._field("citizenship_number", "251059/6599", 0.84),
                self._field("category", "A", 0.87),
            ],
            DocumentType.ipo_application: [
                self._field("company_name", "Kisan Micro Finance Bittiya Sanstha Ltd", 0.88),
                self._field("application_number", "011908", 0.90),
                self._field("applicant_name", "Ashish Singh", 0.88),
                self._field("applied_units", "500", 0.85),
                self._field("amount", "50000", 0.84),
                self._field("boid", "13013700007004469", 0.82),
            ],
            DocumentType.asba_application: [
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


def get_ocr_provider(name: str = "mock") -> OcrProvider:
    providers = {
        "mock": MockOcrProvider,
        "tesseract": TesseractOcrProvider,
        "paddleocr": PaddleOcrProvider,
    }
    provider_cls = providers.get(name)
    if provider_cls is None:
        raise ValueError(f"Unsupported OCR provider: {name}")
    return provider_cls()
