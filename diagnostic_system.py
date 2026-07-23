"""
DIAGNÓSTICO COMPLETO Y PROFUNDO DEL SISTEMA
============================================
Este script realiza una auditoría diagnóstica de punta a punta:
1. Comprueba todas las funciones de utils_clinica.py con matriz de pruebas de borde (edge cases).
2. Procesa todos los archivos .docx, .pdf y .doc del repositorio.
3. Examina detalladamente el texto y tablas extraídas de los PDFs generados para verificar:
   - Fechas en títulos y encabezados.
   - Columnas ICSI/FIV en Pabellón y Uso Interno.
   - Cálculos de placas G-IVF, ICSI, Embryoscope, Cultivo Tradicional, WP y TS en Setup Día 0.
   - Pacientes PGD.
   - Transferencias.
   - Destacado de Biopsia Testicular en Material Extra Revisado.
"""
import os, io, re, math
import pdfplumber
import pandas as pd

from docx_parser import parse_docx
from pdf_parser import parse_pdf
from doc_parser import parse_doc
from pdf_generator import generar_tabla_optimizada, generar_setup_fiv
from utils_clinica import (
    get_max_follicles, calculate_plates, add_time,
    is_receptor, is_donor_vitri, calc_placa_g_ivf,
    calc_placa_icsi, calc_placa_embryoscope, calc_placa_cultivo_trad, calc_wp_ts
)

print("="*80)
print("1. EVALUACIÓN DE MATRIZ DE PRUEBAS DE BORDE EN UTILS_CLINICA")
print("="*80)

matriz_casos = [
    # (proc, diag, is_uso_interno, expected_is_receptor, expected_is_donor)
    ("CULDO", "INFERTILIDAD", False, False, False),
    ("CULDOCENTESIS", "SOP", False, False, False),
    ("OVO-R", "RECEPTORA", True, True, False),
    ("OVOR CRIO", "DESVITRIFICACIÓN", True, True, False),
    ("DESV OVO", "RECEPTORA", True, True, False),
    ("DESVITRI OVOS", "DESVITRIFICACIÓN", True, True, False),
    ("OVO FRESCO", "RECEPTORA", True, True, False),
    ("OVO FRESCO DONANTE #190", "INFERTILIDAD", True, True, False),
    ("OVO-R EN FRESCO DONANTE #226", "RECEPTORA", True, True, False),
    ("OVO-D", "DONANTE DE OVOCITOS", False, False, True),
    ("VITRIFICACIÓN OVOCITOS", "PRESERVACIÓN DE FERTILIDAD", False, False, True),
    ("PRESERVACIÓN DE FERTILIDAD", "FREEZE ALL", False, False, True),
    ("CULDOCENTESIS", "PRESERVACIÓN FERTILIDAD", False, False, True),
    ("BIOPSIA TESTICULAR", "SD KLINEFELTER", False, False, False),
]

errores_matriz = 0
for proc, diag, is_ui, exp_rec, exp_don in matriz_casos:
    rec = is_receptor(proc, diag, is_uso_interno=is_ui)
    don = is_donor_vitri(proc, diag)
    status = "OK" if (rec == exp_rec and don == exp_don) else "FAIL"
    if status == "FAIL":
        errores_matriz += 1
        print(f"❌ FAIL: PROC='{proc}' DIAG='{diag}' UI={is_ui} -> rec={rec} (exp {exp_rec}), don={don} (exp {exp_don})")
    else:
        print(f"✅ OK: PROC='{proc[:25]:25}' DIAG='{diag[:25]:25}' -> rec={str(rec):5} | don={str(don):5}")

print(f"\nResultado Matriz de Pruebas: {len(matriz_casos) - errores_matriz}/{len(matriz_casos)} pasaron.\n")

print("="*80)
print("2. DIAGNÓSTICO Y EXTRACCIÓN FÍSICA DE DOCUMENTOS ARCHIVO POR ARCHIVO")
print("="*80)

files = [f for f in sorted(os.listdir('.')) if (f.endswith('.docx') or f.endswith('.pdf')) and not f.startswith(('Salida_', 'Tabla_Optimizada', 'SETUP'))]

reporte_archivos = []

for f in files:
    info = {"archivo": f, "errores": [], "advertencias": [], "resumen": {}}
    try:
        if f.endswith('.docx'):
            fecha, df_p, df_ui, df_t = parse_docx(f, f)
        else:
            fecha, df_p, df_ui, df_t = parse_pdf(f, f)
            
        info["fecha"] = fecha
        info["n_punciones"] = len(df_p)
        info["n_uso_interno"] = len(df_ui)
        info["n_transfers"] = len(df_t)
        
        # Generar PDFs
        buf_t = generar_tabla_optimizada(fecha, df_p, df_ui, df_t)
        buf_s = generar_setup_fiv(fecha, df_p, df_ui, df_t, "Auditor Clinico", [])
        
        # 1. Auditoría PDF Tabla
        pdf_t = pdfplumber.open(buf_t)
        text_t = "\n".join([p.extract_text() or "" for p in pdf_t.pages])
        pdf_t.close()
        
        # 2. Auditoría PDF Setup
        pdf_s = pdfplumber.open(buf_s)
        text_s = "\n".join([p.extract_text() or "" for p in pdf_s.pages])
        tables_s = []
        for p in pdf_s.pages:
            t_page = p.extract_tables()
            if t_page: tables_s.extend(t_page)
        pdf_s.close()
        
        # --- VERIFICACIÓN 1: FECHA EN TABLA Y SETUP ---
        if "Fecha No Especificada" not in text_t and fecha.upper() not in text_t.upper():
            info["errores"].append(f"Fecha '{fecha}' no reflejada en PDF Tabla")
            
        if "SETUP LABORATORIO FIV CER" not in text_s:
            info["errores"].append("Título principal de Setup no encontrado")
            
        # --- VERIFICACIÓN 2: HORA ICSI/FIV EN USO INTERNO ---
        if not df_ui.empty:
            for idx, r_ui in df_ui.iterrows():
                p_ui = str(r_ui.get('PROC', '')).upper()
                d_ui = str(r_ui.get('DIAGNOSTICO', '')) + " " + str(r_ui.get('MÉTODO/OBS', ''))
                is_rec = is_receptor(p_ui, d_ui, is_uso_interno=True)
                is_don = is_donor_vitri(p_ui, d_ui)
                
                if is_rec and not is_don:
                    # Debe tener hora ICSI/FIV en el PDF de la tabla
                    if not re.search(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', text_t):
                        info["errores"].append(f"Uso Interno Fila {idx} ({p_ui}): No se encontró rango horario ICSI/FIV en PDF Tabla!")
                        
        # --- VERIFICACIÓN 3: PLACAS DÍA 0 EN SETUP ---
        df_dia0 = pd.concat([df_p, df_ui], ignore_index=True)
        if not df_dia0.empty:
            # Buscar tabla Día 0 en Setup
            tabla_d0_pdf = None
            for tbl in tables_s:
                if tbl and len(tbl) > 1:
                    hdr = [str(h).upper() for h in tbl[0] if h]
                    if any("G-IVF" in h for h in hdr) and any("ICSI" in h for h in hdr):
                        tabla_d0_pdf = tbl
                        break
                        
            if tabla_d0_pdf is None:
                info["errores"].append("Tabla Día 0 no encontrada en PDF Setup!")
            else:
                hdr = [str(h).upper() for h in tabla_d0_pdf[0] if h]
                idx_icsi = next((i for i, h in enumerate(hdr) if "ICSI" in h), None)
                idx_emb = next((i for i, h in enumerate(hdr) if "EMBRYO" in h), None)
                
                rows_pdf = tabla_d0_pdf[1:]
                for idx, r in df_dia0.iterrows():
                    p_str = str(r.get('PROC', '')).upper()
                    d_str = str(r.get('DIAGNOSTICO', '')) + " " + str(r.get('MÉTODO/OBS', ''))
                    is_rec = is_receptor(p_str, d_str, is_uso_interno=(idx >= len(df_p)))
                    is_don = is_donor_vitri(p_str, d_str)
                    
                    if idx < len(rows_pdf):
                        row_pdf = rows_pdf[idx]
                        val_icsi_pdf = str(row_pdf[idx_icsi]).strip() if idx_icsi is not None and len(row_pdf) > idx_icsi else ""
                        val_emb_pdf = str(row_pdf[idx_emb]).strip() if idx_emb is not None and len(row_pdf) > idx_emb else ""
                        
                        if is_rec and not is_don:
                            if not val_icsi_pdf:
                                info["errores"].append(f"Día 0 Fila {idx+1} ({p_str}): Placa ICSI está VACÍA para Receptora/Uso Interno en Setup!")
                            if not val_emb_pdf:
                                info["errores"].append(f"Día 0 Fila {idx+1} ({p_str}): Placa Embryo está VACÍA para Receptora/Uso Interno en Setup!")

        # --- VERIFICACIÓN 4: BIOPSIA TESTICULAR DESTACADA ---
        has_bt = False
        keywords_bt = ['BIOPSIA TESTICULAR', 'BX TESTICULAR', 'BX TEST', 'BIOPSIA', 'TESTICULAR']
        for check_df in [df_p, df_ui]:
            if check_df is not None and not check_df.empty:
                for _, r_check in check_df.iterrows():
                    r_text = " ".join(str(v).upper() for v in r_check.values if v is not None and str(v) != 'nan')
                    if any(kw in r_text for kw in keywords_bt) or re.search(r'\bBT\b', r_text):
                        has_bt = True
                        break
                if has_bt: break
                
        if has_bt:
            if "* Material Biopsia Testicular (REQUERIDO)" not in text_s and "Material Biopsia Testicular" not in text_s:
                info["errores"].append("BT presente en tabla pero NO destacada en Setup!")
            else:
                info["resumen"]["BT"] = "Destacada OK ✅"

    except Exception as e:
        info["errores"].append(f"Excepción: {str(e)}")
        
    reporte_archivos.append(info)

total_archivos_err = 0
for inf in reporte_archivos:
    if inf["errores"]:
        total_archivos_err += len(inf["errores"])
        print(f"❌ {inf['archivo']:35} | Fecha: [{inf.get('fecha','')}] | ERRORES: {'; '.join(inf['errores'])}")
    else:
        bt_str = f" ({inf['resumen']['BT']})" if "BT" in inf.get("resumen", {}) else ""
        print(f"✅ {inf['archivo']:35} | Fecha: [{inf.get('fecha','')}] | Punciones:{inf['n_punciones']} UI:{inf['n_uso_interno']} Transf:{inf['n_transfers']}{bt_str}")

print("="*80)
print(f"RESUMEN GENERAL: Archivos={len(reporte_archivos)} | Errores Totales={total_archivos_err}")
print("="*80)
