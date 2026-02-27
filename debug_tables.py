import docx
import sys

doc = docx.Document("Tabla 23-12-25.docx")
for i, table in enumerate(doc.tables):
    if not table.rows:
        continue
    headers = [c.text.strip().replace('\n', ' ') for c in table.rows[0].cells]
    print(f"Table {i+1} headers: {headers}")
