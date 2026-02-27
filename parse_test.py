import pdfplumber

with pdfplumber.open("SETUP LAB FIV CER - Hoja 1.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"--- Page {i+1} Text ---")
        text = page.extract_text()
        print(text)
        print("\n--- Page {i+1} Tables ---")
        tables = page.extract_tables()
        for t_idx, t in enumerate(tables):
            print(f"Table {t_idx+1}:")
            for row in t:
                print(row)
        print("="*40)
