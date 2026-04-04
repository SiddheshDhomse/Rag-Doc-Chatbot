import pandas as pd

def extract_text_from_excel(file_path):
    xl = pd.ExcelFile(file_path)
    full_text = ""

    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name)
        full_text += f"\n--- Sheet: {sheet_name} ---\n"
        # CSV keeps all rows/columns and preserves row boundaries for chunking/retrieval.
        full_text += df.to_csv(index=False)

    return full_text
