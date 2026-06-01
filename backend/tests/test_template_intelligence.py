from app.models import DocumentType, OcrBlock, TemplateProfilePage
from app.services.template_intelligence import infer_template_document_type, suggest_label_fields


def test_ipo_template_intelligence_maps_receipt_labels_after_bbox_normalization():
    page = TemplateProfilePage(
        page_number=1,
        filename="ipo.jpg",
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(text="शेयर खरिद दरखास्त फारम", bbox=[250, 140, 530, 160], confidence=0.97),
            OcrBlock(text="यो सेयर रोक्का दर्ताका लागि फर्म", bbox=[350, 150, 550, 170], confidence=0.97),
            OcrBlock(
                text="मेरो विवरण अनुसारको सेयर १०० कित्ता सेयर रु. १०,०००/-",
                bbox=[50, 550, 900, 575],
                confidence=0.92,
                block_type="handwriting",
            ),
            OcrBlock(text="Applicant's Name", bbox=[50, 850, 150, 870], confidence=0.97),
            OcrBlock(text="Company's Name", bbox=[50, 870, 150, 890], confidence=0.97),
            OcrBlock(text="No. of Share Applied", bbox=[50, 890, 150, 910], confidence=0.96),
            OcrBlock(text="Amount in Words", bbox=[50, 910, 150, 930], confidence=0.96),
            OcrBlock(text="PAN No.", bbox=[50, 940, 150, 960], confidence=0.96),
            OcrBlock(text="नाम (English)", bbox=[50, 960, 150, 980], confidence=0.96),
            OcrBlock(text="हजुरबुवाको नाम (English)", bbox=[50, 980, 150, 1000], confidence=0.96),
            OcrBlock(text="पति/पत्नीको नाम (English)", bbox=[50, 1000, 150, 1020], confidence=0.96),
        ],
    )

    document_type, confidence, reason = infer_template_document_type([page], DocumentType.unknown)
    fields = {field.key: field for field in suggest_label_fields([page])}

    assert document_type == DocumentType.ipo_application
    assert confidence >= 0.7
    assert "शेयर" in reason or "share" in reason
    assert {
        "applicant_name",
        "company_name",
        "applied_units",
        "amount_words",
        "pan",
        "full_name_en",
        "grandfather_name_en",
        "spouse_name_en",
    }.issubset(fields)
    assert fields["applicant_name"].bbox == [162, 844, 502, 880]
    assert fields["applied_units"].bbox[3] - fields["applied_units"].bbox[1] == 36
    assert fields["applied_units"].bbox[0] == 162


def test_template_intelligence_ignores_header_contacts_and_field_candidate_blocks():
    page = TemplateProfilePage(
        page_number=1,
        filename="ipo.jpg",
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(text="E-mail: kifax@gmail.com", bbox=[350, 340, 500, 355], confidence=0.99),
            OcrBlock(text="Dp Id: 011908", bbox=[750, 400, 850, 420], confidence=0.97, block_type="field_candidate"),
            OcrBlock(text="Applicant's Name", bbox=[50, 870, 150, 885], confidence=0.98),
        ],
    )

    fields = {field.key: field for field in suggest_label_fields([page])}

    assert "applicant_name" in fields
    assert "email" not in fields
    assert "dp_id" not in fields


def test_template_intelligence_links_labels_to_nearby_writable_regions():
    page = TemplateProfilePage(
        page_number=1,
        filename="ipo-filled.jpg",
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(text="मेरो नाम", bbox=[50, 570, 100, 585], confidence=0.98),
            OcrBlock(text="ASHISH SINGH", bbox=[150, 570, 350, 585], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="नि. व. ०११९०८", bbox=[750, 570, 850, 585], confidence=0.95),
            OcrBlock(text="स्थायी ठेगाना", bbox=[50, 615, 150, 630], confidence=0.98),
            OcrBlock(text="222", bbox=[210, 615, 260, 630], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="Kathmandu", bbox=[510, 615, 650, 630], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="Kathmandu", bbox=[810, 615, 950, 630], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="PAN No.", bbox=[50, 660, 150, 675], confidence=0.98),
            OcrBlock(text="924444", bbox=[550, 660, 650, 675], confidence=0.95, block_type="handwriting"),
            OcrBlock(text="Mobile No.", bbox=[750, 660, 850, 675], confidence=0.98),
            OcrBlock(text="9841000000", bbox=[860, 660, 950, 675], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="No. of Share Applied", bbox=[50, 960, 150, 975], confidence=0.98),
            OcrBlock(text="500", bbox=[150, 960, 250, 975], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="Call Money Per Share Rs", bbox=[350, 960, 500, 975], confidence=0.98),
            OcrBlock(text="Amount Deposited", bbox=[650, 960, 780, 975], confidence=0.98),
            OcrBlock(text="50000", bbox=[790, 960, 890, 975], confidence=0.98, block_type="handwriting"),
        ],
    )

    fields = {field.key: field for field in suggest_label_fields([page])}

    assert fields["name_ne"].bbox == [150, 566, 742, 589]
    assert fields["address_ne"].bbox == [162, 611, 950, 634]
    assert fields["pan"].bbox == [162, 656, 742, 679]
    assert fields["mobile"].bbox == [860, 656, 950, 679]
    assert fields["applied_units"].bbox == [150, 956, 342, 979]
    assert fields["amount"].bbox == [790, 956, 890, 979]


def test_template_intelligence_does_not_spill_into_adjacent_rows_or_generic_number_labels():
    page = TemplateProfilePage(
        page_number=1,
        filename="financial-form.jpg",
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(text="फोन नं.", bbox=[60, 300, 120, 318], confidence=0.98),
            OcrBlock(text="01-4444000", bbox=[160, 300, 260, 318], confidence=0.95, block_type="handwriting"),
            OcrBlock(text="PAN No.", bbox=[50, 660, 150, 675], confidence=0.98),
            OcrBlock(text="924444", bbox=[550, 660, 650, 675], confidence=0.95, block_type="handwriting"),
            OcrBlock(text="Mobile No.", bbox=[750, 660, 850, 675], confidence=0.98),
            OcrBlock(text="9841000000", bbox=[860, 660, 950, 675], confidence=0.98, block_type="handwriting"),
            OcrBlock(text="Current Address", bbox=[50, 705, 150, 720], confidence=0.98),
            OcrBlock(text="Kathmandu", bbox=[210, 705, 350, 720], confidence=0.98, block_type="handwriting"),
        ],
    )

    fields = {field.key: field for field in suggest_label_fields([page])}

    assert "application_number" not in fields
    assert fields["pan"].bbox == [162, 656, 742, 679]
    assert fields["mobile"].bbox == [860, 656, 950, 679]
    assert fields["pan"].bbox[3] < fields["address_en"].bbox[1]
