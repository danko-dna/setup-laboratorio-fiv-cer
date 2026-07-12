"""
Parser para archivos .doc (formato binario Word 97-2003).
Usa olefile para abrir el contenedor OLE2 y extrae el texto crudo del stream 'WordDocument'.
Luego intenta reconstruir las tablas a partir del texto extraído.
Si falla, retorna DataFrames vacíos y un mensaje informativo.
"""
import struct
import re
import pandas as pd

def _extract_text_from_doc(file_stream):
    """
    Extrae texto plano de un archivo .doc usando parsing directo del stream OLE2.
    Funciona sin dependencias externas pesadas (antiword, libreoffice).
    """
    try:
        import olefile
    except ImportError:
        return None
    
    try:
        ole = olefile.OleFileIO(file_stream)
        
        # El texto del documento Word está en el stream 'WordDocument'
        # Pero el texto real suele estar en '1Table' o '0Table' combinado con 'WordDocument'
        # Método simplificado: extraer todos los caracteres legibles
        
        text_parts = []
        
        # Intentar extraer del stream principal
        if ole.exists('WordDocument'):
            word_stream = ole.openstream('WordDocument').read()
            # Extraer texto ASCII/Latin-1 legible
            text = word_stream.decode('latin-1', errors='replace')
            # Filtrar caracteres de control, mantener solo legibles
            clean = []
            for ch in text:
                if ch in '\n\r\t' or (32 <= ord(ch) < 127) or (160 <= ord(ch) <= 255):
                    clean.append(ch)
                else:
                    clean.append(' ')
            text_parts.append(''.join(clean))
        
        ole.close()
        
        full_text = '\n'.join(text_parts)
        # Limpiar espacios múltiples
        full_text = re.sub(r'[ ]{3,}', '\t', full_text)  # múltiples espacios → tab (separador de tabla)
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        
        return full_text
        
    except Exception as e:
        return None


def parse_doc(file_stream, filename_fallback=""):
    """
    Intenta extraer datos de un archivo .doc.
    Retorna (fecha_str, df_punciones, df_uso_interno, df_transferencias)
    Si no puede extraer las tablas correctamente, retorna DataFrames vacíos.
    """
    fecha_str = "Fecha No Encontrada"
    df_punciones = pd.DataFrame()
    df_uso_interno = pd.DataFrame()
    df_transferencias = pd.DataFrame()
    
    # Intentar extraer texto
    text = _extract_text_from_doc(file_stream)
    
    if text is None:
        # Fallback: intentar leer como si fuera docx (algunos .doc son en realidad .docx renombrados)
        try:
            file_stream.seek(0)
            from docx_parser import parse_docx
            return parse_docx(file_stream, filename_fallback)
        except:
            pass
        
        # Si todo falla, usar nombre de archivo como fecha
        if filename_fallback:
            fecha_str = re.sub(r'\.doc$', '', filename_fallback, flags=re.IGNORECASE)
        return fecha_str, df_punciones, df_uso_interno, df_transferencias
    
    # Buscar fecha en el texto
    meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
             'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    
    for line in text.split('\n'):
        line = line.strip()
        if len(line) > 5 and len(line) < 80:
            line_upper = line.upper()
            has_month = any(m in line_upper for m in meses)
            has_year = '202' in line_upper
            if has_month and has_year:
                fecha_str = line.strip()
                break
    
    if fecha_str == "Fecha No Encontrada" and filename_fallback:
        fecha_str = re.sub(r'\.doc$', '', filename_fallback, flags=re.IGNORECASE)
    
    # Nota: La extracción de tablas desde .doc binario es limitada.
    # Se retornan DataFrames vacíos - el usuario verá un mensaje informativo.
    
    return fecha_str, df_punciones, df_uso_interno, df_transferencias
