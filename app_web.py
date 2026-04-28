import os
import streamlit as st
from google import genai
from pydantic import BaseModel
from typing import List
import pandas as pd
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Extractor de Ingeniería TNG", page_icon="⚙️", layout="wide")

# --- 2. MANEJO INTELIGENTE DE LA API KEY (Local vs Nube) ---
# Intentamos cargar el .env local si existe
load_dotenv()

# Función segura para buscar la llave
def obtener_api_key():
    # 1. Intentamos leer desde las variables de entorno (Local .env)
    llave = os.environ.get("GEMINI_API_KEY")
    
    # 2. Si no hay llave local, intentamos leer desde Streamlit Secrets (Nube)
    if not llave:
        try:
            # st.secrets a veces requiere que el diccionario exista, usemos .get
            llave = st.secrets.get("GEMINI_API_KEY") 
        except Exception: # Atrapamos cualquier error si la carpeta .streamlit no existe
            pass
            
    return llave

api_key = obtener_api_key()

if not api_key:
    st.error("❌ No se encontró la API Key de Gemini. Verifica tu archivo .env o los Secrets de Streamlit.")
    st.stop() # Detiene la app si no hay llave

# Iniciamos el motor de Airi
client = genai.Client(api_key=api_key)

# --- 3. ESQUEMA DE DATOS (El Molde de Titanio) ---
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
    resumen_ejecutivo: str # Airi opinando sobre el documento

# --- 4. DISEÑO DE LA APLICACIÓN WEB ---
st.title("🤖 Asistente Airi: Extracción y Análisis de Acero")
st.markdown("Arquitectura de IA Generativa para la automatización del área de Costos e Ingeniería.")

# El cargador de archivos
archivo_subido = st.file_uploader("Arrastra una cotización o factura (PDF, JPG, PNG)", type=['pdf', 'png', 'jpg', 'jpeg'])

if archivo_subido is not None:
    # Mensaje de espera
    with st.spinner('⚙️ Airi está analizando el documento y construyendo el dashboard...'):
        
        # Guardamos temporalmente el archivo subido para que Gemini lo procese
        ruta_temporal = f"temp_{archivo_subido.name}"
        with open(ruta_temporal, "wb") as f:
            f.write(archivo_subido.getbuffer())
        
        # Subimos el archivo al núcleo
        archivo_gemini = client.files.upload(file=ruta_temporal)

        # Instrucciones de nivel superior
        prompt = """
        Analiza este documento de ingeniería. 
        1. Extrae los datos técnicos y el número de folio.
        2. Pon especial atención al ACERO (grados y normas ASTM, ISO). 
        3. Escribe un 'resumen_ejecutivo' muy breve (máximo 2 líneas) indicando qué tipo de materiales se están cobrando y si notas que falta algún dato importante como la norma del acero.
        """

        # Procesamiento
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, archivo_gemini],
            config={
                'response_mime_type': 'application/json',
                'response_schema': FacturaIngenieria,
            }
        )

        datos = response.parsed
        
        # Limpieza: borramos el archivo temporal
        os.remove(ruta_temporal)

    # --- 5. ZONA DEL GERENTE (EL EFECTO WOW) ---
    st.success("✅ Análisis Completado en Segundos")
    
    # El Resumen Ejecutivo
    st.info(f"**🧠 Análisis de Airi:** {datos.resumen_ejecutivo}")
    
    # Tarjetas de datos rápidos
    col1, col2, col3 = st.columns(3)
    col1.metric("Folio del Documento", datos.folio)
    col2.metric("Proveedor", datos.proveedor)
    col3.metric("Monto Total", f"${datos.total:,.2f} {datos.moneda}")

    # Convertimos los items a una tabla de pandas
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
    
    # Creamos pestañas para mostrar diferentes vistas (El gran final)
    tab1, tab2, tab3 = st.tabs(["📊 Gráfico de Costos", "📦 Datos Tabulares", "⚙️ Integración JSON"])
    
    with tab1:
        st.write("### Distribución de Costos por Material")
        if not df.empty and "Importe" in df.columns:
            df_grafico = df.groupby("Descripción")["Importe"].sum()
            st.bar_chart(df_grafico)
            
    with tab2:
        st.write("### Base de Datos Extraída")
        st.dataframe(df, use_container_width=True)
        # Botón de Descarga
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar a Excel (CSV)",
            data=csv,
            file_name=f'factura_{datos.folio}.csv',
            mime='text/csv',
        )
        
    with tab3:
        st.write("### Código Puro (Listo para API/ERP)")
        st.json(response.text) # Mostramos el JSON en crudo