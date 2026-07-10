import streamlit as st
import os
from docx_parser import parse_docx
from pdf_parser import parse_pdf
from pdf_generator import generar_tabla_optimizada, generar_setup_fiv
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import io
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LIMS Laboratorio FIV", layout="wide")

# --- FUNCIONES DE LÓGICA CLÍNICA ---
def ajustar_hora(hora_str, minutos):
    try:
        # Limpiar formatos extraños
        hora_str = re.findall(r'\d{1,2}:\d{2}', str(hora_str))[0]
        dt = datetime.strptime(hora_str, "%H:%M")
        nuevo_dt = dt + timedelta(minutes=minutos)
        return nuevo_dt.strftime("%H:%M")
    except:
        return ""

def redondear_arriba(n):
    return int(n) + (1 if n % 1 > 0 else 0)

# --- CLASE PARA GENERACIÓN DE PDF (SIMETRÍA Y COLOR) ---
class PDF_Robustecido(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        if hasattr(self, 'fecha_doc'):
            self.cell(0, 10, f'TABLA OPERATORIA OPTIMIZADA - {self.fecha_doc}', 0, 1, 'C')

# --- ESTILOS CSS MINIMALISTAS Y ALTO CONTRASTE ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Aumentar contraste de las preguntas (Labels) */
    .stTextInput label, .stNumberInput label, .stCheckbox label, div[data-testid="stCheckbox"] label p {
        font-weight: 800 !important;
        font-size: 1.1rem !important;
        color: #1E3A8A !important; /* Azul marino oscuro para máximo contraste */
        margin-bottom: 0.2rem;
    }
    
    /* Dar un fondo sutil y borde fuerte a las cajas de texto/números para que destaquen */
    div[data-baseweb="input"] {
        background-color: #F8FAFC !important;
        border: 2px solid #94A3B8 !important;
        border-radius: 6px !important;
        transition: all 0.3s ease;
    }
    
    /* Efecto Focus cuando el usuario hace clic en la caja */
    div[data-baseweb="input"]:focus-within {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 2px rgba(37,99,235,0.2) !important;
        background-color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- PROTECCIÓN CON CONTRASEÑA ---
def check_password():
    """Verifica la contraseña antes de permitir acceso a la app."""
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    if st.session_state['authenticated']:
        return True
    
    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>🔒 Acceso Restringido</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Ingresa la contraseña para acceder al sistema</p>", unsafe_allow_html=True)
    
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        password = st.text_input("Contraseña", type="password", placeholder="Ingresa la contraseña")
        if st.button("Ingresar", type="primary", use_container_width=True):
            if password == st.secrets.get("app_password", "fiv26"):
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
    return False

if not check_password():
    st.stop()

if os.path.exists("logo.png"):
    # Se recomienda usar columnas para centrar o alinear bonito
    col_logo, _ = st.columns([1, 4])
    with col_logo:
        st.image("logo.png", use_container_width=True)
else:
    st.caption("(Para ver tu logo aquí, guarda la imagen que subiste con el nombre 'logo.png' en esta carpeta)")

# --- INTERFAZ DE USUARIO ---
st.title("Procesamiento de Tabla Operatoria y Setup Lab")

archivo_subido = st.file_uploader("Sube la Tabla Operatoria (DOCX, PDF o DOC)", type=["docx", "pdf", "doc"])

if archivo_subido:
    # Determinar tipo de archivo
    nombre_archivo = archivo_subido.name.lower()
    
    if nombre_archivo.endswith('.doc') and not nombre_archivo.endswith('.docx'):
        st.error("⚠️ El formato .doc (Word antiguo) no es compatible directamente. "
                 "Por favor convierte tu archivo a .docx o .pdf antes de subirlo.\n\n"
                 "**¿Cómo convertir?** Abre el archivo en Word → Archivo → Guardar como → "
                 "selecciona 'Documento de Word (.docx)' y guárdalo.")
        st.stop()
    
    # 1. EXTRACCIÓN DE DATOS
    if nombre_archivo.endswith('.pdf'):
        fecha_str, df_punciones, df_uso_interno, df_transferencias = parse_pdf(archivo_subido, archivo_subido.name)
    else:
        fecha_str, df_punciones, df_uso_interno, df_transferencias = parse_docx(archivo_subido, archivo_subido.name)
        
    st.success(f"Documento detectado para la fecha: {fecha_str}")
    
    # 2. RESPONSABLE Y EDICIÓN (OCULTA POR DEFECTO MÁS MINIMALISTA)
    col1, col2 = st.columns(2)
    with col1:
        responsable = st.text_input("Responsable del Laboratorio", placeholder="Nombre del embriólogo")
    
    with st.expander("Hacer clic aquí para inspeccionar o editar la tabla extraída (Opcional)", expanded=False):
        st.subheader("Validación de Punciones")
        if not df_punciones.empty:
            df_editado_p = st.data_editor(df_punciones, num_rows="dynamic", key="edit_p")
        else:
            st.warning("No se encontraron registros de punciones.")
            df_editado_p = pd.DataFrame()
            
        st.subheader("Validación de Uso Interno Lab FIV")
        if not df_uso_interno.empty:
            df_editado_ui = st.data_editor(df_uso_interno, num_rows="dynamic", key="edit_ui")
        else:
            st.info("No se encontraron registros de uso interno lab.")
            df_editado_ui = pd.DataFrame()
            
        st.subheader("Validación de Transferencias (TED)")
        if not df_transferencias.empty:
            df_editado_t = st.data_editor(df_transferencias, num_rows="dynamic", key="edit_t")
        else:
            st.info("No se encontraron registros de transferencias.")
            df_editado_t = pd.DataFrame()

    # 3. CUESTIONARIO DINÁMICO (PACIENTES PGD)
    st.subheader("Pacientes PGD")
    activar_dia5 = st.checkbox("¿Hay pacientes PGD?")
    datos_dia5 = []
    if activar_dia5:
        n_pacientes_d5 = st.number_input("Cantidad de pacientes PGD", min_value=1, step=1)
        for i in range(int(n_pacientes_d5)):
            c1, c2 = st.columns([1, 1])
            with c1: nom = st.text_input(f"Apellido Paciente {i+1}")
            with c2: emb = st.number_input(f"N° Embriones {i+1}", min_value=1)
            datos_dia5.append({"Paciente": nom, "PGD": "SI", "Embriones": emb})

    # 4. VALIDACIÓN DE RESPONSABLE Y GENERACIÓN
    if not responsable or not responsable.strip():
        st.warning("⚠️ Debes ingresar el nombre del Responsable del Laboratorio antes de generar los documentos.")
    
    generar_disabled = not responsable or not responsable.strip()
    if st.button("Generar Documentos Finales", type="primary", disabled=generar_disabled):
        with st.spinner("Compilando y dibujando PDFs optimizados..."):
            buf_tabla = generar_tabla_optimizada(fecha_str, df_editado_p, df_editado_ui, df_editado_t)
            buf_setup = generar_setup_fiv(fecha_str, df_editado_p, df_editado_ui, df_editado_t, responsable, datos_dia5)
            
            # Guardamos en session_state para que los botones de descarga no desaparezcan
            st.session_state['docs_generados'] = True
            st.session_state['buf_tabla'] = buf_tabla
            st.session_state['buf_setup'] = buf_setup
            st.session_state['fecha_str'] = fecha_str
            
    if st.session_state.get('docs_generados', False):
        st.success("¡Documentos generados exitosamente de acuerdo al SOP!")
        col_dl1, col_dl2 = st.columns(2)
        
        with col_dl1:
            # Extraer fecha limpia para nombrar el archivo
            import re
            file_date = re.sub(r'[\\/*?:"<>|]', "", st.session_state['fecha_str']).replace(" ", "_")
            if not file_date:
                file_date = "Fecha_Desconocida"
                
            st.download_button(
                label="📄 Descargar Tabla Laboratorio",
                data=st.session_state['buf_tabla'],
                file_name=f"Tabla {file_date}.pdf",
                mime="application/pdf"
            )
            
        with col_dl2:
            st.download_button(
                label="📋 Descargar Setup FIV",
                data=st.session_state['buf_setup'],
                file_name=f"Setup_FIV_{file_date}.pdf",
                mime="application/pdf"
            )
