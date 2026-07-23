"""
AUDITORÍA COMPLETA Y PROFUNDA DEL SISTEMA
=========================================
Este script genera los PDFs reales de Tabla Optimizada y Setup FIV
para TODOS los archivos de la carpeta y extrae con pdfplumber el texto
y tablas de los PDFs GENERADOS para verificar físicamente qué se renderizó.
"""
import os, io, re
import pdfplumber
import pandas as pd

from docx_parser import parse_docx
from pdf_parser import parse_pdf
from doc_parser import parse_doc
from pdf_generator import generar_tabla_optimizada, generar_setup_fiv
from utils_clinica import is_receptor, is_donor_vitri

files = [f for f in sorted(os.listdir('.')) if (f.endswith('.docx') or f.endswith('.pdf')) and not f.startswith(('Salida_', 'Tabla_Optimizada', 'SETUP'))]

print(f"Total archivos a auditar: {len(files)}\n")

reporte = []

for f in files:
    res = {"archivo": f, "status": "OK", "errores": [], "detalles": []}
    try:
        if f.endswith('.docx'):
            fecha, df_p, df_ui, df_t = parse_docx(f, f)
        else:
            fecha, df_p, df_ui, df_t = parse_pdf(f, f)
            
        res["fecha_extraida"] = fecha
        
        # 1. Generar PDF Tabla
        buf_tabla = generar_tabla_optimizada(fecha, df_p, df_ui, df_t)
        
        # 2. Generar PDF Setup
        buf_setup = generar_setup_fiv(fecha, df_p, df_ui, df_t, "Auditor Test", [])
        
        # --- EXAMINAR FÍSICAMENTE EL PDF DE TABLA GENERADO ---
        pdf_t = pdfplumber.open(buf_tabla)
        texto_t = "\n".join([p.extract_text() or "" for p in pdf_t.pages])
        tablas_t = []
        for p in pdf_t.pages:
            t_page = p.extract_tables()
            if t_page:
                tablas_t.extend(t_page)
        pdf_t.close()
        
        # Verificar Fecha en Header de Tabla
        primera_linea_t = texto_t.split('\n')[0] if texto_t else ""
        if fecha.upper() not in primera_linea_t.upper() and fecha.upper() not in texto_t.upper():
            res["errores"].append(f"FECHA TABLA NO VISIBLE: Esperado '{fecha}' en header, primera linea: '{primera_linea_t}'")
            
        # Verificar Uso Interno ICSI/FIV en Tabla si hay Uso Interno
        if not df_ui.empty:
            found_ui_icsi = False
            for tbl in tablas_t:
                if tbl and len(tbl) > 1:
                    headers = [str(h).upper() for h in tbl[0] if h]
                    if any("ICSI" in h or "FIV" in h for h in headers):
                        # Buscar si hay celdas de ICSI/FIV con horario
                        for row in tbl[1:]:
                            row_str = " ".join(str(c) for c in row if c)
                            if re.search(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', row_str):
                                found_ui_icsi = True
                                break
            if not found_ui_icsi:
                # Comprobar si todas las filas eran donantes
                all_donors = all(is_donor_vitri(r.get('PROC',''), str(r.get('DIAGNOSTICO',''))) for _,r in df_ui.iterrows())
                if not all_donors:
                    res["errores"].append("USO INTERNO ICSI/FIV VACÍO en PDF generado!")
                else:
                    res["detalles"].append("Uso Interno todas son donantes (ICSI/FIV vacio es correcto)")
                    
        # --- EXAMINAR FÍSICAMENTE EL PDF DE SETUP GENERADO ---
        pdf_s = pdfplumber.open(buf_setup)
        texto_s = "\n".join([p.extract_text() or "" for p in pdf_s.pages])
        tablas_s = []
        for p in pdf_s.pages:
            t_page = p.extract_tables()
            if t_page:
                tablas_s.extend(t_page)
        pdf_s.close()
        
        # Verificar Fecha en Título de Setup
        if fecha.upper() not in texto_s.upper():
            res["errores"].append(f"FECHA SETUP NO VISIBLE: '{fecha}' no encontrada en el PDF del Setup")
            
        # Verificar Placa ICSI y Placa Embryo en Setup para Ovoreceptoras
        df_dia0 = pd.concat([df_p, df_ui], ignore_index=True)
        has_receptors = False
        if not df_dia0.empty:
            for _, r in df_dia0.iterrows():
                proc = str(r.get('PROC',''))
                diag = str(r.get('DIAGNOSTICO','')) + ' ' + str(r.get('MÉTODO/OBS',''))
                has_ovo_col = any('ovo' in str(c).lower() and 'decu' not in str(c).lower() for c in r.index)
                if is_receptor(proc, diag, is_uso_interno=has_ovo_col):
                    has_receptors = True
                    break
        
        if has_receptors:
            found_icsi_count = False
            found_embryo_count = False
            for tbl in tablas_s:
                if tbl and len(tbl) > 1:
                    headers = [str(h).upper() for h in tbl[0] if h]
                    if any("ICSI" in h for h in headers) and any("EMBRYO" in h for h in headers):
                        # Encontrar índice de columna Placa ICSI y Placa Embryo
                        idx_icsi = next((i for i,h in enumerate(headers) if "ICSI" in h), None)
                        idx_emb = next((i for i,h in enumerate(headers) if "EMBRYO" in h), None)
                        if idx_icsi is not None and idx_emb is not None:
                            for row in tbl[1:]:
                                if len(row) > max(idx_icsi, idx_emb):
                                    val_icsi = str(row[idx_icsi]).strip()
                                    val_emb = str(row[idx_emb]).strip()
                                    if val_icsi and val_icsi != "0": found_icsi_count = True
                                    if val_emb and val_emb != "0": found_embryo_count = True
            
            if not found_icsi_count:
                res["errores"].append("SETUP PLACA ICSI VACÍA PARA RECEPTORA!")
            if not found_embryo_count:
                res["errores"].append("SETUP PLACA EMBRYO VACÍA PARA RECEPTORA!")
                
        # Verificar Destacado de Biopsia Testicular en Setup si aplica
        has_bt = False
        keywords_bt = ['BIOPSIA TESTICULAR', 'BX TESTICULAR', 'BX TEST', 'BIOPSIA', 'TESTICULAR', 'ASPIRACIÓN DE EPIDÍDIMO', 'ASPIRACION DE EPIDIDIMO']
        for check_df in [df_p, df_ui]:
            if check_df is not None and not check_df.empty:
                for _, r_check in check_df.iterrows():
                    r_text = " ".join(str(v).upper() for v in r_check.values if v is not None and str(v) != 'nan')
                    if any(kw in r_text for kw in keywords_bt) or re.search(r'\bBT\b', r_text):
                        has_bt = True
                        break
                if has_bt: break
                
        if has_bt:
            if "REQUERIDO" in texto_s or "Material Biopsia Testicular" in texto_s:
                res["detalles"].append("BT detectada -> Destacado en checklist presente ✅")
            else:
                res["errores"].append("BT presente en tabla pero NO destacada en checklist de Setup!")

    except Exception as e:
        res["status"] = "ERROR"
        res["errores"].append(f"Excepción: {str(e)}")
        
    reporte.append(res)

print("=" * 80)
print("RESULTADOS DE LA AUDITORÍA FÍSICA DE PDFs")
print("=" * 80)
total_err = 0
for r in reporte:
    err_str = " | ".join(r["errores"]) if r["errores"] else "OK"
    det_str = (" (" + ", ".join(r["detalles"]) + ")") if r["detalles"] else ""
    if r["errores"]:
        total_err += len(r["errores"])
        print(f"❌ {r['archivo']:35} -> Fecha: [{r.get('fecha_extraida','')}] -> ERRORES: {err_str}")
    else:
        print(f"✅ {r['archivo']:35} -> Fecha: [{r.get('fecha_extraida','')}] -> {err_str}{det_str}")

print("=" * 80)
print(f"TOTAL ARCHIVOS: {len(reporte)} | ERRORES ENCONTRADOS: {total_err}")
print("=" * 80)
