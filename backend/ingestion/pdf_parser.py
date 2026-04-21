import fitz  # PyMuPDF

def extract_text_from_pdf(file_path):
    pages = []
    with fitz.open(file_path) as doc:
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text", sort=True).strip()
            if not page_text:
                continue
            pages.append(f"--- Page {page_num + 1} ---\n{page_text}")
    return "\n\n".join(pages)
