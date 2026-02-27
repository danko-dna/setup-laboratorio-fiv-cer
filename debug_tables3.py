import docx
doc = docx.Document("Tabla 23-12-25.docx")
from pdf_generator import generar_tabla_optimizada
from docx_parser import parse_docx
fecha, p, u, t = parse_docx("Tabla 23-12-25.docx")
print("PUNCIONES:", p.columns if not p.empty else "EMPTY")
print("USO INTERNO:", u.columns if not u.empty else "EMPTY")
print("TRANSFERENCIAS:", t.columns if not t.empty else "EMPTY")
