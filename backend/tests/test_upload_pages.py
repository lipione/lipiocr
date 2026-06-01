import fitz

from app.services.upload_pages import expand_template_upload_pages


def test_expand_template_upload_pages_renders_each_pdf_page(tmp_path):
    pdf_path = tmp_path / "packet.pdf"
    document = fitz.open()
    try:
        for index in range(2):
            page = document.new_page(width=320, height=480)
            page.insert_text((36, 72), f"Template page {index + 1}")
        document.save(str(pdf_path))
    finally:
        document.close()

    pages = expand_template_upload_pages(
        pdf_path,
        original_filename="packet.pdf",
        content_type="application/pdf",
    )

    assert [page.filename for page in pages] == ["packet.pdf page 1", "packet.pdf page 2"]
    assert all(page.content_type == "image/png" for page in pages)
    assert all(page.stored_path.exists() for page in pages)
    assert all(page.content.startswith(b"\x89PNG") for page in pages)
