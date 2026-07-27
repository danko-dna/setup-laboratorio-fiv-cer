from fpdf import FPDF
from utils_clinica import add_time, get_max_follicles, calculate_plates, is_receptor, is_donor_vitri, calc_placa_g_ivf, calc_placa_icsi, calc_placa_embryoscope, calc_placa_cultivo_trad, calc_wp_ts
import io
import pandas as pd
import re

class PDF_Robustecido(FPDF):
    def __init__(self, fecha_doc):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.set_margins(8, 8, 8)
        self.fecha_doc = fecha_doc
        self.set_auto_page_break(auto=True, margin=8)
        self.add_page()

    def header(self):
        self.set_font('Helvetica', 'B', 14)
        # Asegurar que la fecha siempre se renderice limpiando caracteres problemáticos
        fecha_safe = str(self.fecha_doc)
        try:
            fecha_safe.encode('latin-1')
        except (UnicodeEncodeError, UnicodeDecodeError):
            fecha_safe = fecha_safe.encode('latin-1', errors='replace').decode('latin-1')
        self.cell(0, 10, fecha_safe, border=0, ln=1, align='C')
        self.ln(5)

def sanitize_text(text):
    """Reemplaza caracteres Unicode no soportados por FPDF (latin-1) por sus equivalentes ASCII y normaliza espacios."""
    if text is None: return ""
    text_str = str(text)
    replacements = {
        '\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u02da': '°',
        '\u200b': '', '\u00a0': ' ', '\u2022': '*', '\xad': '-'
    }
    for k, v in replacements.items():
        text_str = text_str.replace(k, v)
    text_str = re.sub(r'[ \t]+', ' ', text_str)
    return text_str

def sanitize_dataframe(df):
    """Aplica sanitize_text a todas las celdas y columnas de un DataFrame."""
    if df.empty: return df
    df_clean = df.copy()
    
    # Deduplicar columnas vacías o duplicadas (evita error DataFrame vs Series)
    cols = list(df_clean.columns)
    seen = {}
    new_cols = []
    for c in cols:
        c_str = str(c).strip()
        if c_str == '' or c_str == 'nan':
            c_str = '_vacio'
        if c_str in seen:
            seen[c_str] += 1
            c_str = f"{c_str}_{seen[c_str]}"
        else:
            seen[c_str] = 0
        new_cols.append(c_str)
    df_clean.columns = new_cols
    
    # Eliminar columnas vacías
    df_clean = df_clean[[c for c in df_clean.columns if not c.startswith('_vacio')]]
    
    # Eliminar filas completamente vacías
    df_clean = df_clean.dropna(how='all').reset_index(drop=True)
    # Eliminar filas donde todas las celdas son string vacío
    df_clean = df_clean[~df_clean.apply(lambda row: all(str(v).strip() == '' or str(v).strip() == 'nan' for v in row), axis=1)].reset_index(drop=True)
    
    # Sanitizar nombres de columnas
    new_columns = {col: sanitize_text(col) for col in df_clean.columns}
    df_clean.rename(columns=new_columns, inplace=True)
    
    # Sanitizar contenido
    for col in df_clean.columns:
        try:
            if df_clean[col].dtype == object or str(df_clean[col].dtype) == 'string':
                df_clean[col] = df_clean[col].apply(lambda x: sanitize_text(x) if pd.notnull(x) else x)
        except Exception:
            pass  # Saltar columnas problemáticas
    return df_clean

def aplicar_sop_columnas_punciones(df, is_uso_interno_table=False):
    df_mod = df.copy()
    if df_mod.empty: return df_mod
    
    col_hora = next((c for c in df_mod.columns if 'hora' in c.lower()), None)
    col_folic = next((c for c in df_mod.columns if any(k in c.lower() for k in ['fol', 'desvitri', 'ovo']) and 'decu' not in c.lower()), None)
    col_semen = next((c for c in df_mod.columns if 'semen' in c.lower()), None)
    
    idx_insert_decu = df_mod.columns.get_loc(col_folic) + 1 if col_folic else len(df_mod.columns)
    if 'DECU OVO' not in df_mod.columns:
        df_mod.insert(idx_insert_decu, 'DECU OVO', "")
        
    if 'ICSI/FIV' not in df_mod.columns:
        df_mod['ICSI/FIV'] = ""
        
    for idx, row in df_mod.iterrows():
        proc = str(row.get('PROC', '')).upper()
        diag = str(row.get('MÉTODO/OBS', '')) + " " + str(row.get('DIAGNOSTICO', '')) + " " + str(row.get('OBSERVACIONES', ''))
        diag = diag.upper()
        hora_str = str(row[col_hora]) if col_hora else ""
        semen_str = str(row[col_semen]) if col_semen else ""
        
        # Detección ampliada: revisar PROC + diagnóstico/observaciones
        is_recept = is_receptor(proc, diag, is_uso_interno=is_uso_interno_table)
        is_donor = is_donor_vitri(proc, diag)
        
        # Abreviar CULDOCENTESIS a CULDO a pedimento del usuario para ahorrar espacio
        if 'CULDOCENTESIS' in proc:
            df_mod.at[idx, 'PROC'] = str(row.get('PROC', '')).upper().replace('CULDOCENTESIS', 'CULDO')
            
        if 'BIOPSIA' in proc:
            proc = proc.replace('BIOPSIA', 'Bx')
            df_mod.at[idx, 'PROC'] = proc
            
        if ('CULDOCENTESIS' in proc or 'CULDO' in proc) and not is_recept:
            if hora_str:
                df_mod.at[idx, 'DECU OVO'] = add_time(hora_str, 110)
                
            vitri_keywords = ["VITRIFIC", "PRESERV", "OVO-D", "OVO D", "DONANTE", "OVODONANTE", "OVO DONANTE"]
            is_vitri = any(k in diag for k in vitri_keywords) or any(k in proc for k in vitri_keywords)
            
            if col_semen and hora_str and semen_str.strip() and semen_str != "--" and not is_vitri:
                if not re.search(r'\(\d{1,2}:\d{2}\)', semen_str):
                    df_mod.at[idx, col_semen] = f"{semen_str}\n({add_time(hora_str, 130)})"
            
            if not is_vitri and hora_str:
                df_mod.at[idx, 'ICSI/FIV'] = f"{add_time(hora_str, 240)} - {add_time(hora_str, 360)}"
                
        elif is_recept or is_uso_interno_table:
            if is_donor:
                df_mod.at[idx, 'ICSI/FIV'] = ""
            else:
                # Receptora / Desvitrificación (OVO-R, OVO-R CRIO, etc.): Semen 1h antes, ICSI/FIV rango 3-4h
                if col_semen and hora_str and semen_str.strip() and semen_str != "--":
                    if not re.search(r'\(\d{1,2}:\d{2}\)', semen_str):
                        df_mod.at[idx, col_semen] = f"{semen_str}\n({add_time(hora_str, -60)})"
                if hora_str:
                    time_start = add_time(hora_str, 180)
                    time_end = add_time(hora_str, 240)
                    if time_start and time_end:
                        df_mod.at[idx, 'ICSI/FIV'] = f"{time_start} - {time_end}"
                    elif time_start:
                        df_mod.at[idx, 'ICSI/FIV'] = time_start
        
        # Regla general: Donantes/Vitrificación NUNCA llevan ICSI/FIV
        if is_donor:
            df_mod.at[idx, 'ICSI/FIV'] = ""

    return df_mod

def aplicar_sop_columnas_transferencias(df):
    df_mod = df.copy()
    if df_mod.empty: return df_mod
    
    col_hora = next((c for c in df_mod.columns if 'hora' in c.lower()), None)
    col_proc = next((c for c in df_mod.columns if 'proc' in c.lower()), None)
    
    if 'HORA DESC' not in df_mod.columns:
        idx_insert = df_mod.columns.get_loc(col_proc) + 1 if col_proc else len(df_mod.columns)
        df_mod.insert(idx_insert, 'HORA DESC', "")
        
    for idx, row in df_mod.iterrows():
        hora_str = str(row[col_hora]) if col_hora else ""
        if hora_str:
            df_mod.at[idx, 'HORA DESC'] = add_time(hora_str, -120)
            
    return df_mod

def calcular_anchos(headers_list):
    # Estrechando al máximo PGD, N FOL, SEMEN, PROC, DECU OVO para donar a Nombre y Diag
    width_map = {
        'hora': 11, 'nombre': 46, 'edad': 11, 'proc': 18, 'método/obs': 17,
        'diagnóstico': 40, 'diagnostico': 40, 'pgt': 6, 'n° folic': 11, 'n° fol': 11, 'ovos desvitri': 15,
        'decu ovo': 16, 'semen': 15, 'magenta': 18, 'observaciones': 12,
        'obs': 12, 'médico tte': 14, 'médico pool': 14, 'icsi/fiv': 19, 
        'hora desc': 24, 'detalle': 14, 'médico': 14, 'embryoglue': 14, 'glue': 14
    }
    widths = []
    for h in headers_list:
        hl = h.lower()
        w = 18
        # Ordenar por longitud descendente para que 'hora desc' se pruebe antes que 'hora', evitando falsos positivos
        for k in sorted(width_map.keys(), key=len, reverse=True):
            if k in hl:
                w = width_map[k]
                break
        widths.append(w)
    
    total = sum(widths)
    if total > 275:
        scale = 275 / total
        widths = [w * scale for w in widths]
    elif total < 275 and len(headers_list) > 0:
        diff = 275 - total
        for i, h in enumerate(headers_list):
            if 'nombre' in h.lower() or 'detalle' in h.lower() or 'semen' in h.lower():
                widths[i] += diff / 2.0
                if diff > 1:
                   # Try to distribute difference
                   pass
    return widths

def get_row_height(pdf, col_widths, row_data, line_height=4, fonts=None, padding=2):
    """Calcula la altura máxima necesaria para una fila simulando word wrap como FPDF"""
    max_h = line_height
    for i, (w, text) in enumerate(zip(col_widths, row_data)):
        if fonts and i < len(fonts):
            pdf.set_font(*fonts[i])
        usable_w = w - 2 if w > 2 else w
        
        lines_count = 0
        for paragraph in text.split('\n'):
            if not paragraph:
                lines_count += 1
                continue
            words = paragraph.split(' ')
            cur_line_w = 0
            space_w = pdf.get_string_width(' ')
            for word in words:
                word_w = pdf.get_string_width(word)
                if cur_line_w + word_w > usable_w and cur_line_w > 0:
                    lines_count += 1
                    cur_line_w = word_w + space_w
                else:
                    cur_line_w += word_w + space_w
            if cur_line_w > 0:
                lines_count += 1
                
        h = max(1, lines_count) * line_height + padding
        if h > max_h:
            max_h = h
    return max_h

def draw_multiline_row(pdf, col_widths, row_data, fill_colors, min_line_height=4, fonts=None):
    """Dibuja una fila con alturas automáticas manejando saltos de línea sin desfasar X/Y"""
    # 1. OPTIMIZAR FUENTES PARA QUE NINGUNA PALABRA DESBORDE HORIZONTALMENTE LA CASILLA (Bug Edad / Nombre)
    #    Y PARA QUE TEXTOS LARGOS (OBS/PROC) CUBRAN MENOS DE 4 LÍNEAS.
    opt_fonts = []
    for i, (w, text) in enumerate(zip(col_widths, row_data)):
        if not fonts or i >= len(fonts):
            # Fallback seguro si no se pasaron fuentes explícitas
            opt_fonts.append(None)
            continue
            
        family, style, size = fonts[i]
        usable_w = w - 2 if w > 2 else w
        
        best_size = size
        # Probar reduciendo el tamaño en tramos de 0.5 hasta llegar a tamaño 4.0
        for s in range(int(size * 2), 7, -1):
            curr_s = s / 2.0
            pdf.set_font(family, style, curr_s)
            too_wide = False
            lines_count = 0
            
            for paragraph in text.split('\n'):
                if not paragraph:
                    lines_count += 1
                    continue
                p_words = paragraph.split(' ')
                cur_line_w = 0
                space_w = pdf.get_string_width(' ')
                for word in p_words:
                    word_w = pdf.get_string_width(word)
                    if word_w > usable_w:
                        too_wide = True
                        break
                    
                    if cur_line_w + word_w > usable_w and cur_line_w > 0:
                        lines_count += 1
                        cur_line_w = word_w + space_w
                    else:
                        cur_line_w += word_w + space_w
                
                if too_wide:
                    break
                if cur_line_w > 0:
                    lines_count += 1
            
            if too_wide:
                continue
                
            # Limitar la densidad vertical pero darle un respiro más natural a columnas de puro texto
            if lines_count > 4:
                continue
                
            best_size = curr_s
            break
            
        opt_fonts.append((family, style, best_size))

    # 2. CALCULAR ALTURA DE FILA USANDO LAS FUENTES OPTIMIZADAS
    row_h = get_row_height(pdf, col_widths, row_data, min_line_height, fonts=opt_fonts, padding=4)
    
    # Manejar salto de página manual si la fila no cabe
    if pdf.get_y() + row_h > pdf.page_break_trigger:
        pdf.add_page()
        
    x_start_row = pdf.get_x()
    y_start = pdf.get_y()
    
    x_curr = x_start_row
    
    for i, (w, text, color) in enumerate(zip(col_widths, row_data, fill_colors)):
        cur_font = opt_fonts[i] if opt_fonts else None
        if cur_font:
            pdf.set_font(*cur_font)
        pdf.set_fill_color(*color)
        pdf.set_xy(x_curr, y_start)
        
        # Dibujar rectangulo de fondo
        pdf.rect(x_curr, y_start, w, row_h, 'DF')
        
        # Dibujar el texto (MultiCell auto-baja el Y pero lo corregimos)
        inner_h = get_row_height(pdf, [w], [text], min_line_height, fonts=[cur_font] if cur_font else None, padding=0)
        pdf.set_xy(x_curr, y_start + (row_h - inner_h) / 2) # Centrado vertical aprox
        pdf.multi_cell(w, min_line_height, text, border=0, align='C')
        
        x_curr += w
        
    # CRÍTICO PARA EVITAR TABLAS "CORRIDAS": Restaurar X al comienzo de la fila
    pdf.set_xy(x_start_row, y_start + row_h)

def generar_tabla_optimizada(fecha_str, df_punciones_orig, df_uso_interno_orig, df_transferencias_orig):
    fecha_clean = str(fecha_str).strip()
    if not fecha_clean or fecha_clean.upper() in ['TABLA PABELLON', 'TABLA PABELLÓN', 'FECHA NO ENCONTRADA', 'TABLA']:
        fecha_clean = "Fecha No Especificada"
    pdf = PDF_Robustecido(fecha_clean)
    
    # Pre-procesar y Sanitizar DataFrames
    df_punciones = aplicar_sop_columnas_punciones(sanitize_dataframe(df_punciones_orig), is_uso_interno_table=False)
    df_uso_interno = aplicar_sop_columnas_punciones(sanitize_dataframe(df_uso_interno_orig), is_uso_interno_table=True)
    df_transferencias = aplicar_sop_columnas_transferencias(sanitize_dataframe(df_transferencias_orig))
    
    # --- FUNCIÓN AUXILIAR PARA DIBUJAR TABLAS (DRY) ---
    def dibujar_tabla(pdf, df, titulo):
        if df.empty:
            return
            
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 4, titulo, 0, 1, 'L')
        
        line_height = 8
        pdf.set_fill_color(220, 220, 220)
        pdf.set_font('Arial', 'B', 8) # Aumento de fuente en encabezados a 8
        headers = df.columns.tolist()
        col_widths = calcular_anchos(headers)
        
        header_texts = []
        for i, header in enumerate(headers):
            try:
                head_str = str(header).replace('°', '.')[:20]
            except: head_str = str(header)[:20]
            
            # Acortamientos explícitos de títulos
            if "OBSERVACIONES" in head_str.upper():
                head_str = "OBS" 
            elif "N. FOLIC" in head_str.upper() or "N° FOLIC" in head_str.upper():
                head_str = "N° FOL"
            elif "MÉDICO TTE" in head_str.upper() or "MEDICO TTE" in head_str.upper() or "MÉDICO POOL" in head_str.upper():
                head_str = "Tte/Pool"
                
            # Limpiar posible salto de linea que venga del word para Magenta
            if "MAGENTA" in head_str.upper():
                head_str = head_str.replace("/", "/").replace("\n", "").strip()
                
            header_texts.append(head_str)
            
        header_colors = [(220, 220, 220)] * len(headers)
        header_fonts = [('Arial', 'B', 8)] * len(headers)
        draw_multiline_row(pdf, col_widths, header_texts, header_colors, min_line_height=5, fonts=header_fonts)

        pdf.set_font('Arial', '', 7) # Aumento de fuente en filas a 7
        for r_index, row in df.iterrows():
            proc_val = str(row.get('PROC', '')).upper()
            is_uso_interno_row = is_receptor(proc_val)
            is_even = (r_index % 2 == 0)
            
            row_data = []
            row_colors = []
            row_fonts = []
            
            for i, col_name in enumerate(headers):
                texto = str(row[col_name]).strip()
                col_name_lower = col_name.lower()
                
                # Fuente más grande para el Nombre de la Paciente
                if 'nombre' in col_name_lower:
                    row_fonts.append(('Arial', 'B', 8))
                # Resaltar y agrandar las Horas para mejor lectura visual rápida
                elif 'hora' in col_name_lower:
                    row_fonts.append(('Arial', 'B', 8))
                # Forzar letra pequeña nativa para OBS y PROC evitando sangrías visuales
                elif 'obs' in col_name_lower or 'proc' in col_name_lower:
                    row_fonts.append(('Arial', '', 5.5))
                else:
                    row_fonts.append(('Arial', '', 7))
                
                # Limpieza de Nombres de Médicos (quitar Dr. Dra. y dejar solo apellidos separados por /)
                if 'médico' in col_name_lower or 'medico' in col_name_lower:
                    # Quitar prefijos y puntos con regex seguro (soporta "DRA.")
                    clean_text = re.sub(r'(?i)\bDr[a]?\b\.?\s*', '', texto)
                    # Separar por enters o slashes
                    parts = re.split(r'[\n/]', clean_text)
                    cleaned_parts = []
                    for p in parts:
                        p = p.strip()
                        if p:
                            # Tomar solo la primera palabra (apellido)
                            apellido = p.split()[0] if p.split() else ""
                            if apellido:
                                cleaned_parts.append(apellido)
                    texto = " / ".join(cleaned_parts)
                
                # Default Logic Colors
                fill_color = (255, 255, 255)
                
                if 'hora desc' in col_name_lower:
                    fill_color = (173, 216, 230)
                elif 'hora' in col_name_lower:
                    if titulo == 'SALA TRANSFER':
                        fill_color = (255, 228, 196)
                    else:
                        fill_color = (173, 216, 230) if is_uso_interno_row or titulo == 'USO INTERNO LAB FIV' else (144, 238, 144)
                elif 'semen' in col_name_lower:
                    fill_color = (255, 165, 0)
                elif 'decu ovo' in col_name_lower:
                    fill_color = (255, 255, 102)
                elif 'icsi' in col_name_lower or 'fiv' in col_name_lower:
                    if texto: fill_color = (255, 102, 102)
                else:
                    if titulo == 'SALA TRANSFER':
                        fill_color = (240, 240, 240) if is_even else (255, 255, 255)
                        
                row_data.append(texto)
                row_colors.append(fill_color)
                
            draw_multiline_row(pdf, col_widths, row_data, row_colors, min_line_height=3, fonts=row_fonts)
            
        pdf.ln(1)  # Espaciado mínimo entre tablas

    # --- RENDERIZAR TABLAS ---
    dibujar_tabla(pdf, df_punciones, 'TABLA PABELLÓN')
    
    # Remover columna 'DECU OVO' de df_uso_interno antes de renderizarla
    if not df_uso_interno.empty and 'DECU OVO' in df_uso_interno.columns:
        df_uso_interno_render = df_uso_interno.drop(columns=['DECU OVO'])
    else:
        df_uso_interno_render = df_uso_interno.copy()
        
    dibujar_tabla(pdf, df_uso_interno_render, 'USO INTERNO LAB FIV')

    dibujar_tabla(pdf, df_transferencias, 'SALA TRANSFER')

    pdf_output = pdf.output()
    return io.BytesIO(pdf_output)

def generar_setup_fiv(fecha_str, df_punciones, df_uso_interno, df_transferencias, responsable, datos_dia5):
    """
    Genera el PDF emulando "SETUP LAB FIV CER - Hoja 1.pdf".
    Combina Punciones y Uso Interno para iterar Día 0.
    """
    fecha_clean = str(fecha_str).strip()
    if not fecha_clean or fecha_clean.upper() in ['TABLA PABELLON', 'TABLA PABELLÓN', 'FECHA NO ENCONTRADA', 'TABLA']:
        fecha_clean = "Fecha No Especificada"
        
    responsable = sanitize_text(responsable)
    
    df_punciones = sanitize_dataframe(df_punciones)
    df_uso_interno = sanitize_dataframe(df_uso_interno)
    df_transferencias = sanitize_dataframe(df_transferencias)
    
    # Sanitizar explícitamente el diccionario manual de datos_dia5
    if datos_dia5:
        sanitized_dia5 = []
        for d in datos_dia5:
            sanitized_dia5.append({k: sanitize_text(v) for k, v in d.items()})
        datos_dia5 = sanitized_dia5
    
    # Detectar si hay Biopsia Testicular en las punciones o uso interno
    has_biopsia_testicular = False
    keywords_bt = ['BIOPSIA TESTICULAR', 'BX TESTICULAR', 'BX TEST', 'BIOPSIA', 'TESTICULAR', 'ASPIRACIÓN DE EPIDÍDIMO', 'ASPIRACION DE EPIDIDIMO']
    for check_df in [df_punciones, df_uso_interno]:
        if check_df is not None and not check_df.empty:
            for _, r_check in check_df.iterrows():
                r_text = " ".join(str(v).upper() for v in r_check.values if v is not None and str(v) != 'nan')
                if any(kw in r_text for kw in keywords_bt) or re.search(r'\bBT\b', r_text):
                    has_biopsia_testicular = True
                    break
            if has_biopsia_testicular: break

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # --- ENCABEZADO ---
    import os
    if os.path.exists('logo.png'):
        pdf.image('logo.png', x=160, y=10, w=35) # Esquina superior derecha
        
    pdf.set_font('Arial', 'B', 12)
    # Centrar el título de la hoja Setup incluyendo la fecha del documento
    titulo_setup = f"SETUP LABORATORIO FIV CER - {fecha_clean.upper()}"
    pdf.cell(0, 8, titulo_setup, ln=1, align='C')
    pdf.ln(5) # Añadir espacio de aire bajo el gran título central
    
    pdf.set_font('Arial', '', 9) # Letra más reducida para cabecera de Fecha para ganar aire
    pdf.cell(25, 5, 'Fecha:', border=1)
    
    # Fecha capitalizada estilo Título (Primera letra mayúscula de cada palabra)
    pdf.cell(50, 5, fecha_clean.title(), border=1, ln=1)
    
    pdf.cell(25, 5, 'Responsable:', border=1)
    pdf.cell(50, 5, str(responsable)[:20], border=1, ln=1)
    pdf.cell(25, 5, 'Testigo:', border=1)
    pdf.cell(50, 5, '', border=1, ln=1)
    pdf.ln(5)

    def draw_table_header(title, cols, widths):
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, title, ln=1)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(220, 220, 220)
        for w, c in zip(widths, cols):
            pdf.cell(w, 6, c, 1, 0, 'C', True)
        pdf.ln(6)
        pdf.set_font('Arial', '', 8)

    # --- HELPERS PARA NOMBRES Y DUPES ---
    def clean_person_name(text):
        if not text: return ""
        lines = [l.strip() for l in str(text).split('\n') if l.strip()]
        if not lines: return ""
        first_line = lines[0]
        
        # Eliminar RUTs / Cédulas / DNI / Pasaportes / Números
        first_line = re.sub(r'^\s*\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?[kK0-9]\s*', '', first_line)
        first_line = re.sub(r'\b\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?[kK0-9]\b', '', first_line)
        first_line = re.sub(r'\b\d{6,9}[-\s]?[kK0-9]\b', '', first_line)
        first_line = re.sub(r'\bPASS\s+[A-Z0-9]+\b', '', first_line, flags=re.IGNORECASE)
        first_line = re.sub(r'\bAK\s+\d+\b', '', first_line, flags=re.IGNORECASE)
        first_line = re.sub(r'\b\d{1,3}\b', '', first_line)
        first_line = re.sub(r'\([^\)]*\)', '', first_line)
        first_line = re.sub(r'\b(DR|DRA|DOCTOR|DOCTORA|DONANTE|RECEPTORA|OVO-R|OVOR)\b', '', first_line, flags=re.IGNORECASE)
        
        parts = re.split(r'/|\s+y\s+|\s+Y\s+', first_line)
        return parts[0].strip()

    def extraer_primer_apellido(nombre_completo):
        clean = clean_person_name(nombre_completo)
        if not clean: return ""
        
        if ',' in clean:
            pre_coma = clean.split(',')[0].strip().split()
            if pre_coma:
                return pre_coma[0].upper()
                
        clean_alpha = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', ' ', clean)
        words = clean_alpha.split()
        
        if not words: return ""
        if len(words) == 1:
            return words[0].upper()
        if len(words) == 2:
            return words[1].upper()
        if len(words) == 3:
            return words[1].upper()
            
        return words[-2].upper()

    def get_surname_counts(names_list):
        from collections import Counter
        first_surnames = [extraer_primer_apellido(n) for n in names_list]
        return Counter(first_surnames)
        
    def get_paciente_name(nombre_completo, surname_counts):
        surname1 = extraer_primer_apellido(nombre_completo)
        if not surname1:
            return str(nombre_completo)[:20].upper()
            
        # Si el primer apellido se repite en esta misma tabla, intentamos sacar el segundo
        if surname_counts.get(surname1, 0) > 1:
            clean = clean_person_name(nombre_completo)
            words = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', ' ', clean).split()
            if len(words) >= 3:
                surname2 = words[-1].upper()
                if surname2 != surname1:
                    return f"{surname1} {surname2}"
        return surname1

    # --- TABLA 1: DÍA 0 ---
    cols_d0 = ['#', 'Paciente', 'Foli (F/DV)', 'Placa G-IVF', 'Placa de ICSI', 'Placa Embryo.', 'Pl. Cultivo Trad.', 'WP', 'TS']
    widths_d0 = [8, 45, 17, 18, 26, 28, 28, 12, 12] # Sum: 194mm (Portrait A4)
    
    import pandas as pd
    df_dia0 = pd.concat([df_punciones, df_uso_interno], ignore_index=True)
    
    # Filtrar pacientes que correspondan a Biopsia Testicular o PRP
    def is_biopsia_or_prp(row):
        proc = str(row.get('PROC', '')).upper()
        diag = str(row.get('MÉTODO/OBS', '')).upper() + " " + str(row.get('DIAGNOSTICO', '')).upper()
        texto_busqueda = proc + " " + diag
        
        keywords = ['BX TEST', 'BIOPSIA TESTICULAR', 'BX TESTICULAR', ' BT ', ' BT-', '-BT', 'PRP', 'PLASMA RICO']
        
        # Coincidencia exacta de BT, ya que "BT" podría ser parte de otra palabra (ej: OBTENER)
        if re.search(r'\bBT\b', texto_busqueda):
            return True
            
        for kw in keywords:
            if kw != ' BT ' and kw != ' BT-' and kw != '-BT' and kw in texto_busqueda:
                return True
        return False

    if not df_dia0.empty:
        # Aplicamos el filtro a los registros del Día 0
        df_dia0 = df_dia0[~df_dia0.apply(is_biopsia_or_prp, axis=1)]
        df_dia0 = df_dia0.reset_index(drop=True)
        
    if not df_dia0.empty:
        draw_table_header('Día 0', cols_d0, widths_d0)
        n_punciones_count = len(df_punciones) if df_punciones is not None else 0
        surname_counts_d0 = get_surname_counts(df_dia0.get('NOMBRE', []))
        count = 1
        for idx_row, row in df_dia0.iterrows():
            nombre_completo = str(row.get('NOMBRE', '')).strip()
            paciente = get_paciente_name(nombre_completo, surname_counts_d0)
            is_pabellon_row = (idx_row < n_punciones_count)
            
            # Buscar dinámicamente columnas de Ovos / Folículos
            folic_str = ""
            matching_cols = [c for c in row.index if any(k in str(c).lower() for k in ['fol', 'ovo', 'desvitri', 'cant']) and 'decu' not in str(c).lower()]
            for col in matching_cols:
                val = str(row[col]).strip() if pd.notna(row[col]) else ""
                if val and val != 'nan':
                    folic_str = val
                    break
            
            # Columnas del Dataframe (dependiendo si es Punción o Ovos Desvitri)
            diagnostico = str(row.get('MÉTODO/OBS', '')) # o DIAGNOSTICO en la otra tabla
            if 'DIAGNOSTICO' in row:
                diagnostico += " " + str(row.get('DIAGNOSTICO', ''))
            if 'OBSERVACIONES' in row:
                diagnostico += " " + str(row.get('OBSERVACIONES', ''))
            
            if not folic_str:
                text_to_search = str(row.get('PROC', '')) + " " + str(diagnostico)
                nums = re.findall(r'\b(\d{1,2})\b', text_to_search)
                if nums:
                    valid_nums = [n for n in nums if 1 <= int(n) <= 40]
                    if valid_nums:
                        folic_str = valid_nums[0]
                        
            if folic_str == 'nan': folic_str = ""
            
            # Detección ampliada: revisar PROC + diagnóstico para detectar OVO-R CRIO y variantes
            has_ovo_col = any('ovo' in str(c).lower() and 'decu' not in str(c).lower() for c in row.index)
            es_receptor = is_receptor(row.get('PROC', ''), diagnostico, is_uso_interno=has_ovo_col)
            semen = str(row.get('SEMEN', ''))
                
            max_f = get_max_follicles(folic_str)
            
            # Cálculos SOP:
            val_g_ivf = calc_placa_g_ivf(max_f, es_receptor)
            val_icsi = calc_placa_icsi(max_f, semen, is_recept=es_receptor)
            
            # Usar is_donor_vitri centralizada para detectar Preservación / Criopreservación / Donante / Vitrificación
            is_vitri = is_donor_vitri(row.get('PROC', ''), diagnostico) and not es_receptor
            
            if is_vitri:
                val_icsi = ""
                val_embryoscope = ""
                val_cultivo_trad = ""
                val_wp_ts = ""
            else:
                val_embryoscope = calc_placa_embryoscope(row.get('PROC', ''), diagnostico, max_f, es_receptor)
                val_cultivo_trad = calc_placa_cultivo_trad(max_f)
                val_wp_ts = calc_wp_ts(folic_str, es_receptor, proc_str=row.get('PROC', ''), diag_str=diagnostico, is_pabellon=is_pabellon_row)
            
            pdf.cell(widths_d0[0], 6, str(count), 1, 0, 'C')
            pdf.cell(widths_d0[1], 6, paciente[:40], 1)
            pdf.cell(widths_d0[2], 6, folic_str, 1, 0, 'C')
            
            # Insertar los cálculos
            pdf.cell(widths_d0[3], 6, val_g_ivf, 1, 0, 'C')
            pdf.set_font('Arial', '', 6) if len(val_icsi) > 5 else pdf.set_font('Arial', '', 8)
            pdf.cell(widths_d0[4], 6, val_icsi, 1, 0, 'C')
            pdf.set_font('Arial', '', 8)
            pdf.cell(widths_d0[5], 6, val_embryoscope, 1, 0, 'C')
            pdf.cell(widths_d0[6], 6, val_cultivo_trad, 1, 0, 'C')
            pdf.cell(widths_d0[7], 6, val_wp_ts, 1, 0, 'C')
            pdf.cell(widths_d0[8], 6, val_wp_ts, 1, 0, 'C')
            pdf.ln(6)
            count += 1
            
    pdf.ln(5)

    # --- TABLA 2: PACIENTES PGD ---
    cols_d5 = ['#', 'Paciente', 'Embriones', 'Placa de BX', 'Placa Cultivo Tradicional']
    widths_d5 = [10, 75, 30, 34, 45] # Sum: 194mm
    
    if datos_dia5:
        draw_table_header('Pacientes PGD', cols_d5, widths_d5)
        surname_counts_d5 = get_surname_counts([d.get("Paciente", "") for d in datos_dia5])
        
        count = 1
        for d5_pac in datos_dia5:
            pac = str(d5_pac.get("Paciente", "")).strip()
            
            # Bloqueador de filas Fantasma: Si el usuario dio a + pacientes pero no escribió nombre, lo saltamos
            if not pac:
                continue
                
            paciente = get_paciente_name(pac, surname_counts_d5)
            pdf.cell(widths_d5[0], 6, str(count), 1, 0, 'C')
            pdf.cell(widths_d5[1], 6, paciente[:40], 1, 0, 'L')
            
            embriones = d5_pac.get("Embriones", 0)
            pdf.cell(widths_d5[2], 6, str(embriones), 1, 0, 'C')
            
            import math
            try:
                embriones_num = float(embriones) if embriones else 0
                if embriones_num > 0:
                    placas_emb = math.ceil((embriones_num * 0.5) / 3.0)
                else:
                    placas_emb = 0
            except ValueError:
                placas_emb = 0
                
            str_placas_emb = str(placas_emb) if placas_emb > 0 else ""
            
            pdf.cell(widths_d5[3], 6, str_placas_emb, 1, 0, 'C')
            
            # Lógica corregida: Como todos son PGD, siempre llevan 1 Placa
            pdf.cell(widths_d5[4], 6, "1", 1, 0, 'C')
            
            pdf.ln(6)
            count += 1
            
        pdf.ln(5)

    # --- TABLA 3: TRANSFERENCIAS ---
    cols_t = ['#', 'Paciente', 'Placa Cultivo', 'Placa Doble Pocillo', 'Medio Gx-TL', 'Suero (20 mL)', 'EmbryoGlue']
    widths_t = [8, 48, 22, 32, 26, 28, 30] # Sum: 194mm
    
    if not df_transferencias.empty:
        draw_table_header('Transferencias', cols_t, widths_t)
        surname_counts_t = get_surname_counts(df_transferencias.get('NOMBRE', []))
        
        count = 1
        for r_index, row in df_transferencias.iterrows():
            nombre_completo = str(row.get('NOMBRE', ''))
            paciente = get_paciente_name(nombre_completo, surname_counts_t)
            
            is_even = (r_index % 2 == 0)
            if is_even:
                pdf.set_fill_color(240, 240, 240)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            pdf.cell(widths_t[0], 6, str(count), 1, 0, 'C', fill=True)
            pdf.cell(widths_t[1], 6, paciente[:40], 1, 0, 'L', fill=True)
            # Para transfers suele ser 1 placa/medio por defecto a excepción de EmbryoGlue
            for w in widths_t[2:6]:
                pdf.cell(w, 6, "1", 1, 0, 'C', fill=True)
            
            # Búsqueda dinámica de EmbryoGlue
            glue_val = "NO"
            row_str = " ".join(str(v).upper() for v in row.values)
            if "GLUE" in row_str:
                glue_val = "SI"
            for col_name in row.index:
                if 'embryoglue' in str(col_name).lower() or 'glue' in str(col_name).lower():
                    val = str(row[col_name]).strip().upper()
                    if val in ["SI", "SÍ", "1", "YES", "X", "TRUE"]:
                        glue_val = "SI"
                    elif val in ["NO", "0", "FALSE"]:
                        glue_val = "NO"
            
            pdf.cell(widths_t[6], 6, glue_val, 1, 0, 'C', fill=True)
            pdf.ln(6)
            count += 1
            
        pdf.ln(10)

    # Añadir sección de checklist de Material Extra
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(80, 6, 'Material Extra Revisado', 1, 1, 'L', True)
    pdf.set_font('Arial', '', 8)
    items = ["Placa pH", "Placa pH Embryoscope", "Placas 60mm aireando", "Placas Doble pocillo aireando",
             "Placas Vitri aireando", "Material Biopsia Testicular", "Goblets armados", "Gx-IVF gaseando",
             "Gx-TL gaseando", "PBS/Aspiration temperando", "Aceite abierto/cerrado"]
    for item in items:
        if item == "Material Biopsia Testicular" and has_biopsia_testicular:
            pdf.set_fill_color(255, 255, 102) # Amarillo destacado
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(65, 5, f"* {item} (REQUERIDO)", 1, 0, 'L', True)
            pdf.cell(15, 5, "[  ]", 1, 1, 'C', True)
            pdf.set_font('Arial', '', 8)
            pdf.set_fill_color(255, 255, 255)
        else:
            pdf.cell(65, 5, item, 1)
            pdf.cell(15, 5, "", 1, 1)

    pdf_output = pdf.output()
    return io.BytesIO(pdf_output)
