import os
import streamlit as st
from google import genai
from pydantic import BaseModel
from typing import List
import pandas as pd
from dotenv import load_dotenv
import plotly.express as px # 🟢 NUEVO: Librería para gráficos profesionales

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Extractor de Ingeniería TNG", page_icon="⚙️", layout="wide")

# --- 2. SISTEMA DE SEGURIDAD Y LOGIN ---
# Inicializar variables de sesión si no existen
if "acceso_concedido" not in st.session_state:
    st.session_state.acceso_concedido = False
if "usos_sesion" not in st.session_state:
    st.session_state.usos_sesion = 0

# Pantalla de Login
if not st.session_state.acceso_concedido:
    st.title("🔒 Acceso Restringido")
    st.markdown("Por favor, ingresa el código de acceso corporativo de TNG para continuar.")
    
    pwd_ingresada = st.text_input("Código de Acceso", type="password")
    
    # Aquí definimos la contraseña (puedes cambiarla a lo que gustes)
    PASSWORD_CORRECTA = "TNG2026" 
    
    if st.button("Ingresar"):
        if pwd_ingresada == PASSWORD_CORRECTA:
            st.session_state.acceso_concedido = True
            st.rerun() # Recarga la página para mostrar la app
        else:
            st.error("❌ Código incorrecto. Acceso denegado.")
    st.stop() # Detiene la ejecución del resto del código si no hay acceso

# --- 3. MANEJO DE LA API KEY ---
load_dotenv()
def obtener_api_key():
    llave = os.environ.get("GEMINI_API_KEY")
    if not llave:
        try:
            llave = st.secrets.get("GEMINI_API_KEY") 
        except Exception:
            pass
    return llave

api_key = obtener_api_key()

if not api_key:
    st.error("❌ No se encontró la API Key de Gemini.")
    st.stop()

client = genai.Client(api_key=api_key)

# --- 4. ESQUEMA DE DATOS ---
class ItemFactura(BaseModel):
    cantidad: float
    unidad: str
    descripcion_base: str
    especificacion_tecnica: str 
    precio_unitario: float
    importe: float

class FacturaIngenieria(BaseModel):
    proveedor: str
    folio: str  
    fecha: str
    moneda: str
    items: List[ItemFactura]
    total: float
    resumen_ejecutivo: str

# --- 5. DISEÑO DE LA APLICACIÓN WEB ---
st.title("🤖 Asistente Airi: Extracción y Análisis de Acero")

# Mostrar contador de usos
st.info(f"📊 Usos en esta sesión: {st.session_state.usos_sesion} / 10")

# Límite de 10 usos
if st.session_state.usos_sesion >= 10:
    st.error("🛑 Has alcanzado el límite máximo de extracciones por sesión. Contacta al administrador.")
    st.stop()

archivo_subido = st.file_uploader("Arrastra una cotización o factura (PDF, JPG, PNG) Máx. 5MB", type=['pdf', 'png', 'jpg', 'jpeg'])

if archivo_subido is not None:
    
    # 🟢 NUEVO: Límite de Peso (5 MB)
    MAX_SIZE = 5 * 1024 * 1024 # 5 MB en bytes
    if archivo_subido.size > MAX_SIZE:
        st.error(f"❌ El archivo pesa {archivo_subido.size / (1024*1024):.2f} MB. El límite es de 5 MB por motivos de seguridad.")
        st.stop()

    with st.spinner('⚙️ Airi está analizando el documento y construyendo el dashboard...'):
        
        ruta_temporal = f"temp_{archivo_subido.name}"
        with open(ruta_temporal, "wb") as f:
            f.write(archivo_subido.getbuffer())
        
        archivo_gemini = client.files.upload(file=ruta_temporal)

        prompt = """
        Analiza este documento de ingeniería. 
        1. Extrae los datos técnicos y el número de folio.
        2. Pon especial atención al ACERO (grados y normas ASTM, ISO). 
        3. Escribe un 'resumen_ejecutivo' muy breve (máximo 2 líneas).
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, archivo_gemini],
            config={
                'response_mime_type': 'application/json',
                'response_schema': FacturaIngenieria,
            }
        )

        datos = response.parsed
        os.remove(ruta_temporal)
        
        # Aumentar el contador de uso
        st.session_state.usos_sesion += 1

    # --- ZONA DEL GERENTE ---
    st.success("✅ Análisis Completado en Segundos")
    st.info(f"**🧠 Análisis de Airi:** {datos.resumen_ejecutivo}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Folio del Documento", datos.folio)
    col2.metric("Proveedor", datos.proveedor)
    col3.metric("Monto Total", f"${datos.total:,.2f} {datos.moneda}")

    filas = []
    for item in datos.items:
        filas.append({
            "Cantidad": item.cantidad,
            "Unidad": item.unidad,
            "Descripción": item.descripcion_base,
            "Especificación Acero": item.especificacion_tecnica,
            "Precio Unitario": item.precio_unitario,
            "Importe": item.importe
        })
    
    df = pd.DataFrame(filas)
    
    tab1, tab2, tab3 = st.tabs(["📊 Gráfico de Costos", "📦 Datos Tabulares", "⚙️ Integración JSON"])
    
    with tab1:
        st.write("### Distribución de Costos por Material")
        if not df.empty and "Importe" in df.columns:
            # 🟢 NUEVO: Gráfico de Pastel Interactivo y hermoso con Plotly
            df_grafico = df.groupby("Descripción")["Importe"].sum().reset_index()
            fig = px.pie(df_grafico, values='Importe', names='Descripción', hole=0.4)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            
    with tab2:
        st.write("### Base de Datos Extraída")
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar a Excel (CSV)",
            data=csv,
            file_name=f'factura_{datos.folio}.csv',
            mime='text/csv',
        )
        
    with tab3:
        st.write("### Código Puro (Listo para API/ERP)")
        st.json(response.text)
