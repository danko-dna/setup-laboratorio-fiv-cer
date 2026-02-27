from docx_parser import parse_docx
from pdf_generator import generar_tabla_optimizada, generar_setup_fiv

with open("Tabla MARTES 24-02-26.docx", "rb") as f:
    fecha, p, u, t = parse_docx(f)

buf = generar_tabla_optimizada(fecha, p, u, t)
with open("Salida_Test.pdf", "wb") as out:
    out.write(buf.getbuffer())

buf_setup = generar_setup_fiv(fecha, p, u, t, "Embriologo Local", [])
with open("Salida_SetupFIV.pdf", "wb") as out:
    out.write(buf_setup.getbuffer())

print("PDF test generado exitosamente. (Optimizada + Setup)")
