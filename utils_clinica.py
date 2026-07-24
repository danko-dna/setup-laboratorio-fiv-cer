import re
import pandas as pd
from datetime import datetime, timedelta

def get_max_follicles(folic_str):
    """
    Extrae el número máximo de un texto como "10/20", "4/5", etc.
    Por lo general, el más grande está después del slash, pero se extraen todos los números
    y se devuelve el mayor. Si no hay números, devuelve 0.
    """
    if pd.isna(folic_str) or not str(folic_str).strip():
        return 0
    
    numeros = re.findall(r'\d+', str(folic_str))
    if not numeros:
        return 0
    
    return max([int(n) for n in numeros])

def calculate_plates(max_follicles):
    """
    SOP: 
    - Si Foli <= 20 -> 1 placa.
    - Si Foli > 20 y <= 40 -> 2 placas.
    - y así sucesivamente. (Por cada 20 ovocitos, 1 placa nueva).
    """
    if max_follicles <= 0:
        return 0
    from math import ceil
    return ceil(max_follicles / 20.0)

def add_time(hora_str, minutos):
    """
    Suma minutos a una hora en formato HH:MM o HH.MM.
    Ej: add_time("08:00", 130) -> "10:10", add_time("09.00", 180) -> "12:00"
    """
    if pd.isna(hora_str) or not str(hora_str).strip():
        return ""
    s = str(hora_str).strip()
    s = re.sub(r'(\d{1,2})[.,](\d{2})', r'\1:\2', s)
    match = re.search(r'\b(\d{1,2}):(\d{2})\b', s)
    if not match:
        return ""
    
    try:
        h, m = int(match.group(1)), int(match.group(2))
        dt = datetime(2026, 1, 1, h, m) + timedelta(minutes=minutos)
        return dt.strftime("%H:%M")
    except:
        return ""

import math

def is_receptor(proc_str, diag_str="", is_uso_interno=False):
    """Detecta si la paciente es receptora de óvulos (frescos o vitrificados), desvitrificación o uso interno.
    Revisa tanto el campo PROC como el campo de diagnóstico/observaciones."""
    text = (str(proc_str) + " " + str(diag_str)).upper()
    
    # 1. Keywords directas de receptora (frescos o congelados)
    recept_direct = [
        "OVO-R", "OVOR", "OVO R", "OVOS PROPIOS", "RECEPTORA", "OVORECEPTORA",
        "RECEPCION", "RECEPCIÓN", "DESV", "DESVITRI", "DESCONGELAC", "DESVITRIFIC",
        "DESCONGEL", "OVO FRESCO", "OVOS FRESCOS", "OVOS FRESCO", "OVO EN FRESCO",
        "OVOS EN FRESCO", "TED"
    ]
    if any(k in text for k in recept_direct):
        return True
        
    # 2. Si es vitrificación / preservación pura (sin receptora), no es receptora
    vitri_pure = ["VITRIFIC", "PRESERV", "OVO-D", "OVO D", "OVODONANTE"]
    if any(k in text for k in vitri_pure):
        return False
        
    # 3. Si viene de Uso Interno y no es Culdocentesis, es receptora por defecto
    if is_uso_interno and "CULDO" not in text and "CULDOCENTESIS" not in text:
        return True
        
    return False

def is_donor_vitri(proc_str, diag_str=""):
    """Detecta si la paciente es donante o caso de vitrificación/preservación pura.
    Estas pacientes NO deben llevar hora ICSI/FIV."""
    text = (str(proc_str) + " " + str(diag_str)).upper()
    recept_direct = [
        "OVO-R", "OVOR", "OVO R", "OVOS PROPIOS", "RECEPTORA", "OVORECEPTORA",
        "DESV OVO", "DESVITRI", "OVO FRESCO", "OVOS FRESCOS", "OVOS FRESCO",
        "OVO EN FRESCO", "OVOS EN FRESCO", "RECEPCION", "RECEPCIÓN", "DESCONGEL"
    ]
    if any(k in text for k in recept_direct):
        return False
    donor_keywords = ["OVO-D", "OVO D", "OVODONANTE", "OVO DONANTE", "VITRIFIC", "PRESERV", "VITRI OVOS"]
    return any(k in text for k in donor_keywords)

def calc_placa_g_ivf(max_folic, is_recept):
    if is_recept:
        return "1"
    # Por cada culdocentesis ingresada, como mínimo 1 placa G-IVF
    return str(max(1, math.ceil(max_folic / 20.0)))

def calc_placa_icsi(max_folic, semen_str, is_recept=False):
    keywords = ["CRIO BT", "SEMEN BT", "BT", "BIOPSIA TESTICULAR", "ASPIRACIÓN DE EPIDÍDIMO", "ASPIRACION DE EPIDIDIMO", "EPIDÍDIMO", "EPIDIDIMO"]
    semen_upper = str(semen_str).upper()
    if any(k in semen_upper for k in keywords):
        return "Medio Tamponado/Pentoxifilina"
    if max_folic <= 0:
        if is_recept:
            return "1"
        return ""
    return str(math.ceil(max_folic / 4.0))

def calc_placa_embryoscope(proc_str, diag_str, max_folic, is_recept):
    # Salida directa y garantizada para receptoras y ovos desvitri (sobrepasa filtros de exclusión)
    if is_recept:
        return "1"
    if max_folic <= 0:
        return ""
        
    text = str(proc_str).upper() + " " + str(diag_str).upper()
    freeze_keywords = ["VITRIFICACIÓN", "VITRIFICACION", "PRESERVACIÓN", "PRESERVACION", "OVO-D", "DONANTE", "OVODONANTE"]
    
    # Check para Freeze-Alls
    if any(k in text for k in freeze_keywords):
        return ""
        
    return "1"

def calc_placa_cultivo_trad(max_folic):
    if max_folic <= 16:
        return ""
    
    # 17-26: 1, 27-36: 2, 37-46: 3, etc.
    placas = 1 + math.floor((max_folic - 17) / 10.0)
    return str(placas)

def calc_wp_ts(folic_str, is_recept, proc_str="", diag_str=""):
    """
    SOP para WP y TS:
    1. Si es OVO FRESCO / OVOR FRESCO / OVO-R FRESCO (Receptora en fresco), NO lleva WP ni TS (vacío "").
    2. Si es Desvitrificación / Descongelación de Ovocitos (CRIO / DESV / DESVITRI):
       - 3/4 ovocitos -> 1 WP y 1 TS.
       - 8/10 ovocitos -> 3 WP y 3 TS.
       - 12/14 ovocitos -> 4 WP y 4 TS.
       - Por cada ~3.5 ovocitos adicionales -> +1 WP y +1 TS.
    3. Si es Punción de Pabellón normal:
       - Si max_folic >= 16 -> 2 WP y 2 TS.
       - Si max_folic >= 8 -> 1 WP y 1 TS.
       - Si max_folic < 8 -> vacíos.
    """
    text = (str(proc_str) + " " + str(diag_str)).upper()
    
    # Check Receptora en Fresco (NO desvitrificación)
    fresco_keywords = ["OVO FRESCO", "OVOR FRESCO", "OVO-R FRESCO", "OVOS FRESCOS", "OVOS FRESCO", "OVO EN FRESCO", "OVOS EN FRESCO"]
    is_fresco = any(k in text for k in fresco_keywords)
    
    if is_fresco:
        return ""
        
    # Check Desvitrificación / Descongelación
    desv_keywords = ["DESV", "DESVITRI", "CRIO", "DESCONGEL"]
    is_desvitri = any(k in text for k in desv_keywords) or (is_recept and not is_fresco)
    
    max_f = get_max_follicles(folic_str)
    
    if is_desvitri:
        if max_f <= 0:
            return "1"
        elif max_f <= 4:
            return "1"
        elif max_f <= 7:
            return "2"
        elif max_f <= 10:
            return "3"
        elif max_f <= 14:
            return "4"
        else:
            return str(math.ceil(max_f / 3.5))
            
    # Punción normal (Pabellón)
    if max_f >= 16:
        return "2"
    elif max_f >= 8:
        return "1"
        
    return ""
