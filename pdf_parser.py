import pdfplumber
import pandas as pd
import re

def parse_pdf(file_stream, filename_fallback=""):
    """
    Lee un archivo PDF aportado por el usuario y extrae sus tablas a DataFrames.
    Usa la misma lógica de clasificación que parse_docx.
    Retorna (fecha_str, df_punciones, df_uso_interno, df_transferencias)
    """
    pdf = pdfplumber.open(file_stream)
    
    # Helper para identificar si un string parece una fecha
    def is_date_string(s):
        if not s or len(str(s).strip()) < 4:
            return False
        s_upper = str(s).upper().strip()
        if s_upper in ['TABLA PABELLON', 'TABLA PABELLÓN', 'USO INTERNO LAB FIV', 'SALA TRANSFER']:
            return False
        import re
        if re.search(r'\b\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}\b', s_upper):
            return True
        meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
        dias = ['LUNES', 'MARTES', 'MIERCOLES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'SÁBADO', 'DOMINGO']
        has_month = any(m in s_upper for m in meses)
        has_day = any(d in s_upper for d in dias)
        has_year = '202' in s_upper or '201' in s_upper
        return (has_month and (has_year or has_day)) or (has_day and (has_month or re.search(r'\d{1,2}', s_upper)))

    def clean_date_string(s):
        if not s: return ""
        s_clean = str(s).strip()
        import re
        m = re.search(r'(?:FECHA|TABLA\s+PABELL[OÓ]N(?:\s+DE\s+FECHA)?)\s*:?\s*(.+)', s_clean, re.IGNORECASE)
        if m and is_date_string(m.group(1)):
            return m.group(1).strip()
        return s_clean
    
    fecha_str = "Fecha No Encontrada"
    candidates = []
    
    df_punciones = pd.DataFrame()
    df_uso_interno = pd.DataFrame()
    df_transferencias = pd.DataFrame()
    
    all_tables_data = []
    
    for page in pdf.pages:
        # 1. Buscar fecha en el texto de la página
        page_text = page.extract_text() or ""
        for line in page_text.split('\n'):
            line = line.strip()
            if len(line) > 5:
                candidates.append(line)
        
        # 2. Extraer tablas de la página
        tables = page.extract_tables()
        if tables:
            for table in tables:
                if table and len(table) > 1:
                    all_tables_data.append(table)
    
    pdf.close()
    
    # Evaluar candidatos y elegir el primero que parezca fecha
    for cand in candidates:
        if is_date_string(cand):
            fecha_str = clean_date_string(cand)
            break
    
    # Fallback al nombre de archivo si no encontramos fecha formal
    if (fecha_str == "Fecha No Encontrada" or not is_date_string(fecha_str)) and filename_fallback:
        import re
        fname = re.sub(r'\.docx$|\.pdf$|\.doc$', '', filename_fallback, flags=re.IGNORECASE)
        fname_clean = re.sub(r'^(tabla|setup|uso_interno|optimizada)[_\s]*', '', fname, flags=re.IGNORECASE).strip()
        if fname_clean:
            fecha_str = fname_clean.replace('_', ' ')
    
    # Clasificar las tablas extraídas
    for table_data in all_tables_data:
        if not table_data or len(table_data) < 2:
            continue
        
        # Limpiar celdas None
        headers = [str(h).strip() if h else "" for h in table_data[0]]
        rows = []
        for row in table_data[1:]:
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            # Asegurar que la fila tenga el mismo número de columnas que headers
            while len(cleaned_row) < len(headers):
                cleaned_row.append("")
            cleaned_row = cleaned_row[:len(headers)]
            rows.append(cleaned_row)
        
        if not rows:
            continue
        
        headers_lower = [h.lower() for h in headers]
        
        # Misma lógica de clasificación que docx_parser
        if 'hora' in headers_lower[0] and any('n° fol' in h or 'fol' in h for h in headers_lower):
            df_punciones = pd.DataFrame(rows, columns=headers)
        elif 'hora' in headers_lower[0] and any('desvitri' in h or 'ovos' in h for h in headers_lower):
            df_uso_interno = pd.DataFrame(rows, columns=headers)
        elif len(headers) >= 5 and 'hora' in headers_lower[0] and not any('semen' in h for h in headers_lower) and not any('magenta' in h for h in headers_lower):
            df_transferencias = pd.DataFrame(rows, columns=headers)
    
    # Post-Procesamiento: Remover DECU OVO de la tabla de Uso Interno Lab
    if not df_uso_interno.empty:
        cols_drop = [c for c in df_uso_interno.columns if 'decu' in str(c).lower() and 'ovo' in str(c).lower()]
        if cols_drop:
            df_uso_interno = df_uso_interno.drop(columns=cols_drop)
    
    return fecha_str, df_punciones, df_uso_interno, df_transferencias
