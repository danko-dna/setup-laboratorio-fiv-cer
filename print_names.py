import sys
from docx_parser import parse_docx
with open("Tabla MARTES 24-02-26.docx", "rb") as f:
    fecha, p, u, t = parse_docx(f)
    print("Transferencias Nombres:")
    print(t['NOMBRE'].tolist() if 'NOMBRE' in t.columns else "No NOMBRE column")
