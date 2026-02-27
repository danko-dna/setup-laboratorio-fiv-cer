from docx_parser import parse_docx
fecha, p, u, t = parse_docx("Tabla 23-12-25.docx")
headers = p.columns.tolist()
print("Headers:", headers)
import re
for r_index, row in p.iterrows():
    for col_name in headers:
        texto = str(row[col_name]).strip()
        col_name_lower = col_name.lower()
        if 'médico' in col_name_lower or 'medico' in col_name_lower:
            clean_text = re.sub(r'(?i)\b(?:Dr\.|Dra\.|Dr|Dra)\b', '', texto)
            parts = re.split(r'[\n/]', clean_text)
            cleaned_parts = []
            for p_part in parts:
                p_part = p_part.strip()
                if p_part:
                    apellido = p_part.split()[0] if p_part.split() else ""
                    if apellido:
                        cleaned_parts.append(apellido)
            texto_final = " / ".join(cleaned_parts)
            print("ORIGINAL:", repr(texto), "FINAL:", repr(texto_final))

    break # just one row
    
head_strs = []
for header in headers:
    try:
        head_str = str(header).replace('°', '.')[:20]
    except: head_str = str(header)[:20]
    
    if "OBSERVACIONES" in head_str.upper():
        head_str = "OBS" 
    elif "N. FOLIC" in head_str.upper() or "N° FOLIC" in head_str.upper():
        head_str = "N° FOL"
    elif "MÉDICO TTE" in head_str.upper() or "MEDICO TTE" in head_str.upper() or "MÉDICO POOL" in head_str.upper():
        head_str = "Tte/Pool"
        
    head_strs.append(head_str)

print("PARSED HEADERS:", head_strs)
