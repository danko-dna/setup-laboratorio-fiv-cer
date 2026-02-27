from docx_parser import parse_docx
with open("Tabla LUNES 23-02-2026 .docx", "rb") as f:
    fecha, p, t = parse_docx(f)
    print("Fecha:", fecha)
    print("\n--- Punciones ---")
    print(p)
    print("\n--- Transferencias ---")
    print(t)
