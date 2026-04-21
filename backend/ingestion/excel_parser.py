import pandas as pd

def extract_text_from_excel(file_path):
    sheet_texts = []

    with pd.ExcelFile(file_path, engine="openpyxl") as xl:
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name, dtype=str).fillna("")
            if df.empty and len(df.columns) == 0:
                continue

            columns = [str(column).strip() for column in df.columns]
            rows = [" | ".join(columns)] if columns else []

            for row in df.itertuples(index=False, name=None):
                row_values = [str(value).strip() for value in row]
                if any(row_values):
                    rows.append(" | ".join(row_values))

            if rows:
                sheet_texts.append(f"--- Sheet: {sheet_name} ---\n" + "\n".join(rows))

    return "\n\n".join(sheet_texts)
