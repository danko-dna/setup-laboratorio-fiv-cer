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
    Suma minutos a una hora en formato HH:MM.
    Ej: add_time("08:00", 130) -> "10:10"
    """
    # Intentar limpiar el texto primero
    match = re.search(r'\d{1,2}:\d{2}', str(hora_str))
    if not match:
        return ""
    
    try:
        dt = datetime.strptime(match.group(), "%H:%M")
        nuevo_dt = dt + timedelta(minutes=minutos)
        return nuevo_dt.strftime("%H:%M")
    except:
        return ""

import math

def is_receptor(proc_str):
    text = str(proc_str).upper()
    keywords = ["OVO-R", "OVOR", "OVOS PROPIOS", "RECEPTORA"]
    return any(k in text for k in keywords)

def calc_placa_g_ivf(max_folic, is_recept):
    if is_recept:
        return "1"
    # Por cada culdocentesis ingresada, como mínimo 1 placa G-IVF
    return str(max(1, math.ceil(max_folic / 20.0)))

def calc_placa_icsi(max_folic, semen_str):
    keywords = ["CRIO BT", "SEMEN BT", "BT", "BIOPSIA TESTICULAR", "ASPIRACIÓN DE EPIDÍDIMO", "ASPIRACION DE EPIDIDIMO", "EPIDÍDIMO", "EPIDIDIMO"]
    semen_upper = str(semen_str).upper()
    if any(k in semen_upper for k in keywords):
        return "Medio Tamponado/Pentoxifilina"
    if max_folic <= 0:
        return ""
    return str(math.ceil(max_folic / 4.0))

def calc_placa_embryoscope(proc_str, diag_str, max_folic, is_recept):
    if max_folic <= 0:
        return ""
        
    # Salida directa y garantizada para receptoras y ovos desvitri (sobrepasa filtros de exclusión)
    if is_recept:
        return "1"
        
    text = str(proc_str).upper() + " " + str(diag_str).upper()
    # Si la OBTENCIÓN es fresca para guardar futuras, no inyecta
    # Nota: Excluimos las Descongelaciones (OVO-R, OVOS DESVITRI) de la restricción, pues ELLAS SÍ INYECTAN
    freeze_keywords = ["VITRIFICACIÓN", "VITRIFICACION", "PRESERVACIÓN", "PRESERVACION", "OVO-D", "DONANTE", "OVODONANTE"]
    
    # Check para Freeze-Alls
    if any(k in text for k in freeze_keywords):
        # Excepción: Si es una Ovodonante o Preservación, no usa Embryoscope
        # (Sin embargo, las receptoras u ovos desvitri sí deberían caer al default de abajo)
        return ""
        
    return "1"

def calc_placa_cultivo_trad(max_folic):
    if max_folic <= 16:
        return ""
    
    # 17-26: 1, 27-36: 2, 37-46: 3, etc.
    placas = 1 + math.floor((max_folic - 17) / 10.0)
    return str(placas)

def calc_wp_ts(ovos_desvitri_str, is_recept):
    if not is_recept:
        return ""
    max_ovos = get_max_follicles(ovos_desvitri_str)
    if max_ovos <= 0:
        return ""
    return str(math.ceil(max_ovos / 4.0))
