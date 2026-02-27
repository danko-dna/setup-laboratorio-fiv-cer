import docx
doc = docx.Document("Tabla 23-12-25.docx")
for row in doc.tables[0].rows:
    print(repr(row.cells[-1].text))
