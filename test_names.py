import docx
doc = docx.Document('Tabla 25-02-26.docx')
for i,t in enumerate(doc.tables):
    print(f"Table {i}")
    for row in t.rows[1:3]:
        print("-", row.cells[1].text.replace('\n',' ').strip())
