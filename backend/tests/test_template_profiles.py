from app.models import DocumentType, EvidenceRef, ExtractedField, OcrBlock, TemplateProfilePage
from app.services.template_profiles import create_template_draft


def test_template_draft_prefers_printed_label_anchors_over_extracted_value_boxes():
    page = TemplateProfilePage(
        page_number=1,
        filename="ipo.jpg",
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(text="शेयर खरिद दरखास्त फारम", bbox=[250, 140, 530, 160], confidence=0.97),
            OcrBlock(text="बैंकको नाम :", bbox=[50, 625, 100, 640], confidence=0.98),
            OcrBlock(text="बैंक खाता नं :", bbox=[50, 645, 100, 660], confidence=0.98),
            OcrBlock(text="Applicant's Name", bbox=[50, 870, 150, 885], confidence=0.98),
            OcrBlock(text="Company's Name", bbox=[50, 890, 150, 905], confidence=0.98),
            OcrBlock(text="No. of Share Applied", bbox=[50, 910, 150, 925], confidence=0.98),
            OcrBlock(text="Amount Deposited", bbox=[680, 910, 790, 925], confidence=0.98),
        ],
    )
    extracted_fields = [
        ExtractedField(
            key="name_en",
            label="Name En",
            value="ASHISH SINGH",
            confidence=0.90,
            source="document_intelligence",
            evidence=EvidenceRef(source_page=1, bbox=[80, 100, 420, 140], evidence_text="Derived name_en: ASHISH SINGH"),
        ),
        ExtractedField(
            key="email",
            label="Email",
            value="kifax@gmail.com",
            confidence=0.97,
            source="gemma_reasoning",
            evidence=EvidenceRef(source_page=1, bbox=[350, 340, 500, 355], evidence_text="E-mail: kifax@gmail.com"),
        ),
        ExtractedField(
            key="dp_id",
            label="Dp Id",
            value="011908",
            confidence=0.97,
            source="gemma_reasoning",
            evidence=EvidenceRef(source_page=1, bbox=[750, 400, 850, 420], evidence_text="Dp Id: 011908"),
        ),
    ]

    draft = create_template_draft(
        name="IPO",
        document_type=DocumentType.unknown,
        pages=[page],
        extracted_fields=extracted_fields,
    )
    fields = {field.key: field for field in draft.fields}

    assert draft.document_type == DocumentType.ipo_application
    assert {"bank_name", "bank_account_number", "applicant_name", "company_name", "applied_units", "amount"}.issubset(fields)
    assert {"name_en", "email", "dp_id"}.isdisjoint(fields)
    assert all(field.detection_source == "label_intelligence" for field in draft.fields)
    assert fields["applicant_name"].bbox == [162, 864, 502, 898]


def test_template_draft_uses_asba_layout_preset_when_ocr_labels_are_weak():
    page = TemplateProfilePage(
        page_number=1,
        filename="NIC-BANK-714x1024.jpg",
        width=714,
        height=1024,
        blocks=[
            OcrBlock(text="NIC ASIA", bbox=[30, 25, 130, 60], confidence=0.95),
            OcrBlock(text="हितग्राही खरिद दरखास्त फारम", bbox=[170, 85, 540, 108], confidence=0.78),
            OcrBlock(text="noisy unreadable row", bbox=[40, 200, 660, 230], confidence=0.30),
        ],
    )

    draft = create_template_draft(
        name="NIC ASBA",
        document_type=DocumentType.unknown,
        pages=[page],
        extracted_fields=[],
    )
    fields = {field.key: field for field in draft.fields}

    assert draft.document_type == DocumentType.asba_application
    assert fields["dp_id"].detection_source == "layout_preset"
    assert fields["client_id"].bbox == [536, 199, 609, 223]
    assert fields["full_name_en"].bbox == [150, 295, 526, 323]
    assert fields["mobile"].bbox == [281, 573, 408, 599]
    assert fields["signature"].bbox == [568, 688, 678, 745]


def test_template_draft_uses_asba_layout_preset_from_known_filename_when_ocr_fails():
    page = TemplateProfilePage(
        page_number=1,
        filename="NIC-BANK-714x1024.jpg",
        width=714,
        height=1024,
        blocks=[
            OcrBlock(
                text="OCR provider gemma_vision unavailable: timed out",
                bbox=[80, 100, 640, 134],
                confidence=0.10,
            )
        ],
    )

    draft = create_template_draft(
        name="NIC ASBA",
        document_type=DocumentType.unknown,
        pages=[page],
        extracted_fields=[],
    )
    fields = {field.key: field for field in draft.fields}

    assert draft.document_type == DocumentType.asba_application
    assert fields["dp_id"].detection_source == "layout_preset"
    assert fields["full_name_en"].bbox == [150, 295, 526, 323]


def test_template_draft_prefers_asba_preset_over_synthetic_wide_label_boxes():
    page = TemplateProfilePage(
        page_number=1,
        filename="NIC-BANK-714x1024.jpg",
        width=714,
        height=1024,
        blocks=[
            OcrBlock(text="NIC ASIA", bbox=[80, 100, 650, 130], confidence=0.45),
            OcrBlock(text="DP ID", bbox=[80, 520, 650, 550], confidence=0.45),
            OcrBlock(text="Client ID", bbox=[80, 620, 650, 650], confidence=0.45),
        ],
    )

    draft = create_template_draft(
        name="NIC ASBA",
        document_type=DocumentType.unknown,
        pages=[page],
        extracted_fields=[],
    )
    fields = {field.key: field for field in draft.fields}

    assert fields["dp_id"].detection_source == "layout_preset"
    assert fields["dp_id"].bbox == [536, 174, 609, 199]
    assert fields["client_id"].bbox == [536, 199, 609, 223]


def test_template_draft_uses_extracted_fields_when_no_label_anchors_exist():
    extracted_field = ExtractedField(
        key="invoice_number",
        label="Invoice Number",
        value="INV-100",
        confidence=0.80,
        source="gemma_reasoning",
        evidence=EvidenceRef(source_page=1, bbox=[100, 180, 260, 210], evidence_text="INV-100"),
    )

    draft = create_template_draft(
        name="Unknown",
        document_type=DocumentType.unknown,
        pages=[
            TemplateProfilePage(
                page_number=1,
                filename="unknown.jpg",
                width=1000,
                height=1400,
                blocks=[OcrBlock(text="INV-100", bbox=[100, 180, 260, 210], confidence=0.80)],
            )
        ],
        extracted_fields=[extracted_field],
    )

    assert [field.key for field in draft.fields] == ["invoice_number"]
    assert draft.fields[0].detection_source == "extraction"
