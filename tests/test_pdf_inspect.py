import fitz

from consolidated_state.pdf_inspect import inspect_and_extract_pdf


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_pdf_inspection_extracts_text_and_stable_hash():
    data = make_pdf("Synthetic statement text only")
    first, first_text = inspect_and_extract_pdf(data, "a.pdf")
    second, _ = inspect_and_extract_pdf(data, "b.pdf")

    assert first.status == "TEXT_READY"
    assert first.page_count == 1
    assert "Synthetic statement" in first_text
    assert first.sha256 == second.sha256
