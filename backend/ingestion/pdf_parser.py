import fitz  # PyMuPDF

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            text += f"\n--- Page {page_num+1} ---\n"
            text += page_text
    return text
