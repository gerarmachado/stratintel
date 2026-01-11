import streamlit as st
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import pypdf
from docx import Document
from fpdf import FPDF
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import os
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="StratIntel OSINT V9.0 (Secure)", page_icon="🔐", layout="wide")

# ==========================================
# 🔐 SISTEMA DE LOGIN (NUEVO)
# ==========================================
def check_password():
    """Retorna `True` si el usuario tiene la contraseña correcta."""

    def password_entered():
        """Verifica si la contraseña ingresada coincide con los secretos."""
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # No guardar contraseña en memoria
        else:
            st.session_state["password_correct"] = False

    # Si ya está validado, retornar True
    if st.session_state.get("password_correct", False):
        return True

    # Interfaz de Login
    st.markdown("## 🔒 Acceso Restringido")
    st.text_input("Usuario", key="username")
    st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Usuario o contraseña incorrectos")

    return False

if not check_password():
    st.stop()  # 🛑 AQUÍ SE DETIENE TODO SI NO HAY LOGIN

# ==========================================
# ⚙️ CONFIGURACIÓN CENTRAL
# ==========================================
# Intentamos leer API KEY de secrets primero (Nube), luego local
API_KEY_FIJA = "" 
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY_FIJA = st.secrets["GOOGLE_API_KEY"]

MODELO_ACTUAL = "gemini-3-flash-preview"  
# ==========================================

# --- BASE DE DATOS DE CONOCIMIENTO ---
DB_CONOCIMIENTO = {
    "✨ RECOMENDACIÓN AUTOMÁTICA (IA)": {
        "desc": "La IA analiza el documento y decide la mejor estrategia metodológica.",
        "preguntas": ["Identifica los hallazgos estratégicos más críticos y sus implicaciones.", "Realiza una evaluación integral de riesgos y oportunidades.", "Genera un Resumen Ejecutivo (BLUF) para la toma de decisiones.", "¿Cuáles son las anomalías o patrones ocultos más relevantes?"]
    },
    "--- TÉCNICAS DIAGNÓSTICAS ---": { "desc": "", "preguntas": [] },
    "Análisis FODA (SWOT) Estratégico": {
        "desc": "Fortalezas, Oportunidades, Debilidades y Amenazas (Enfoque Intel, no Marketing).",
        "preguntas": ["Identifica las vulnerabilidades internas críticas (Debilidades) que el adversario podría explotar.", "¿Qué amenazas externas inminentes ponen en riesgo la estabilidad del objetivo?", "Cruza Fortalezas con Oportunidades: ¿Cómo podemos maximizar nuestra ventaja estratégica?", "Estrategia 'Maxi-Mini': Usar fortalezas para minimizar amenazas."]
    },
    "Análisis Geopolítico (PMESII-PT)": {
        "desc": "Análisis del Entorno: Político, Militar, Económico, Social, Infraestructura, Info.",
        "preguntas": ["Analiza cómo las variables Políticas y Militares interactúan en este conflicto.", "Evalúa la vulnerabilidad de la Infraestructura crítica y su impacto Social.", "Desglosa la situación utilizando las 8 variables del marco PMESII-PT.", "¿Qué ventajas asimétricas posee el actor en el dominio de la Información?."]
    },
    "Análisis DIME (Instrumentos de Poder)": {
        "desc": "Diplomático, Informacional, Militar, Económico. (Estándar de Seguridad Nacional).",
        "preguntas": ["Evalúa la capacidad del actor para proyectar poder mediante instrumentos Económicos.", "¿Cómo se están utilizando los canales Diplomáticos para aislar al adversario?.", "Analiza la eficacia de la campaña de Información (Guerra Psicológica/Propaganda)", "¿Existe una opción Militar viable o es puramente disuasoria?"]
    },
    "Análisis Redefinición del Asunto (Redefinición)": {
        "desc": "Replantear la Pregunta, Preguntar el Porqué, Extender el Enfoque, Limitar el Enfoque, Redirigir el Enfoque, Dar vuelta 180 grados el Enfoque.",
        "preguntas": [
            "Volver a denominar el Asunto sin perder el significado original.", "Pregunte una serie de porqué o cómo sobre la definición del Asunto.", "¿Con qué está conectado el asunto?.", "¿se puede desglosar aún más el asunto?.", "¿qué fuerzas exteriores influyen en este asunto? ¿juega un papel el engaño?.", "Ponga el asunto cabeza abajo. Dicho asunto ¿es el que se pregunta o el contrario?."
        ]
    },
    "--- TÉCNICAS DE CONTRASTE Y DESAFÍO ---": { "desc": "", "preguntas": [] },
    "Análisis de Hipótesis en Competencia (ACH)": {
        "desc": "Matriz rigurosa para evaluar múltiples explicaciones y reducir el sesgo.",
        "preguntas": ["Genera 4 hipótesis y puntúa la evidencia para cada una.", "¿Qué evidencia es consistente con todas las hipótesis (y por tanto no tiene valor diagnóstico)?", "Identifica qué pieza de información faltante (Intelligence Gap) confirmaría las Hipótesis", "Evalúa la posibilidad de 'Decepción' (engaño) en la evidencia actual."]
    },
    "Abogado del Diablo": {
        "desc": "Cuestionar la premisa dominante para evitar el pensamiento de grupo.",
        "preguntas": ["Desafía la conclusión más obvia: Provee argumentos sólidos de por qué podría ser falsa.", "¿Qué evidencia estamos ignorando porque no encaja con nuestra teoría principal?", "Defiende la postura del actor que consideramos 'irracional' como si fuera lógica."]
    },
    "Red Team (Simulación Adversario)": {
        "desc": "Pensar y atacar como el enemigo.",
        "preguntas": ["Actuando como el adversario: ¿Cómo atacarías nuestra posición actual?", "Identifica las vulnerabilidades críticas en nuestro plan que un enemigo podría explotar", "Diseña el 'Curso de Acción Más Peligroso' (MDCOA) del enemigo."]
    },
    "--- PROSPECTIVA ---": { "desc": "", "preguntas": [] },
    "Análisis Premortem": {
        "desc": "Imaginar que la estrategia YA falló en el futuro y explicar por qué.",
        "preguntas": ["Estamos en el futuro y el plan fue un desastre: Lista las causas cronológicas del fallo.", "Identifica los 'Cisnes Negros' (eventos improbables) que causaron el colapso", "¿Qué señales de advertencia temprana estamos viendo hoy y decidiendo ignorar?."]
    },
    "Escenarios Prospectivos": {
        "desc": "Cono de Plausibilidad.",
        "preguntas": ["Desarrolla 4 escenarios: El Mejor Caso, El Peor Caso, el 'Wild Card' (Caso Inesperado) y El Caso Híbrido (elementos más probables de cada Caso).", "Identifica los 'Drivers' (motores de cambio) clave que nos empujan hacia el escenario negativo", "Redacta un escenario narrativo del año 2040 basado en las tendencias actuales."]
    },
    "Centro de Gravedad (COG)": {
        "desc": "Identificar la fuente de poder (moral o física) que permite al actor luchar.",
        "preguntas": ["Identifica el Centro de Gravedad Estratégico (la fuente de todo su poder) del adversario", "¿Cuáles son las 'Capacidades Críticas' necesarias para que el COG funcione?", "Define las 'Vulnerabilidades Críticas': ¿Dónde podemos golpear para anular su COG?."]
    },
    "Matriz CARVER": {
        "desc": "Criticality, Accessibility, Recuperability, Vulnerability, Effect, Recognizability (Selección de objetivos).",
        "preguntas": ["Evalúa los objetivos potenciales puntuando su Criticidad y Vulnerabilidad", "¿Qué nodo del sistema tiene el mayor 'Efecto' si es neutralizado?", "Clasifica los activos según su Recuperabilidad: ¿Cuánto tardarían en reemplazarlo?."]
    }
}

# --- GESTIÓN DE ESTADO (SESSION STATE) ---
if 'api_key' not in st.session_state: st.session_state['api_key'] = ""
if 'texto_analisis' not in st.session_state: st.session_state['texto_analisis'] = ""
if 'origen_dato' not in st.session_state: st.session_state['origen_dato'] = "Ninguno"

# --- FUNCIONES DE EXTRACCIÓN ---

def obtener_texto_web(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style"]): script.extract()
        texto_limpio = soup.get_text(separator='\n')
        lines = (line.strip() for line in texto_limpio.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        texto_final = '\n'.join(chunk for chunk in chunks if chunk)
        if len(texto_final) < 200:
            return "ADVERTENCIA: Se extrajo muy poco texto. Web bloqueada o contenido multimedia."
        return texto_final
    except Exception as e:
        return f"Error al leer la web: {e}"

def procesar_youtube(url, api_key):
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    # 1. Intentar Transcripción Directa (Subtítulos)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en'])
        texto_completo = " ".join([i['text'] for i in transcript_list])
        return f"[TRANSCRIPCIÓN SUBTÍTULOS]:\n{texto_completo}", "Subtítulos"
    except Exception as e_trans:
        # 2. Si falla, Multimodal (Audio -> Gemini)
        st.info(f"Subtítulos no disponibles. Iniciando modo Multimodal con {MODELO_ACTUAL}...")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192',}],
            'outtmpl': '%(id)s.%(ext)s',
            'quiet': True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = f"{info['id']}.mp3"
            
            genai.configure(api_key=api_key)
            myfile = genai.upload_file(filename)
            
            with st.spinner("Procesando audio en la nube de Google..."):
                while myfile.state.name == "PROCESSING":
                    time.sleep(2)
                    myfile = genai.get_file(myfile.name)
            
            if myfile.state.name == "FAILED":
                return "Error: Falló el procesamiento del audio en Gemini.", "Error"

            model = genai.GenerativeModel(MODELO_ACTUAL)
            result = model.generate_content([myfile, "Transcribe detalladamente todo el contenido hablado de este audio."])
            
            if os.path.exists(filename): os.remove(filename)
            myfile.delete()
            
            return f"[TRANSCRIPCIÓN AUDIO IA]:\n{result.text}", "Audio Multimodal"

        except Exception as e_audio:
            return f"Error crítico procesando video: {e_audio}. Verifica: 1) FFmpeg instalado. 2) pip install -U google-generativeai", "Error"

def leer_docx(file):
    doc = Document(file)
    texto = "\n".join([para.text for para in doc.paragraphs])
    return texto

# --- FUNCIONES DE REPORTE (SOLUCIÓN DEFINITIVA PDF) ---

def limpiar_texto_pdf(texto):
    """
    Elimina caracteres que rompen la generación de PDF (Emojis, símbolos raros).
    """
    if not texto: return ""
    
    # FORMATO VERTICAL SEGURO
    reemplazos = {
        "✨": "", 
        "🚀": "", 
        "⚠️": "[!]", 
        "✅": "[OK]", 
        "❌": "[X]", 
        "📡": "",
        "–": "-", 
        "—": "-", 
        "“": '"', 
        "”": '"', 
        "’": "'", 
        "🧠": "", 
        "📂": "",
        "📥": "", 
        "📄": "", 
        "📝": "", 
        "🔗": "", 
        "📺": "", 
        "✍️": ""
    }
    
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    
    # Forzar codificación Latin-1
    return texto.encode('latin-1', 'replace').decode('latin-1')

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Informe de Inteligencia StratIntel', 0, 1, 'C')
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        body_limpio = limpiar_texto_pdf(body)
        self.multi_cell(0, 5, body_limpio)
        self.ln()

def crear_pdf(texto, tecnica, fuente):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 10)
    
    f_limpio = limpiar_texto_pdf(f"Fuente: {fuente}")
    t_limpio = limpiar_texto_pdf(f"Metodología: {tecnica}")
    
    pdf.cell(0, 10, f_limpio, ln=True)
    pdf.cell(0, 10, t_limpio, ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 10)
    pdf.chapter_body(texto)
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

def crear_word(texto, tecnica, fuente):
    doc = Document()
    doc.add_heading('Informe de Inteligencia StratIntel', 0)
    p = doc.add_paragraph()
    p.add_run('Fuente Analizada: ').bold = True; p.add_run(fuente + '\n')
    p.add_run('Metodología Aplicada: ').bold = True; p.add_run(tecnica + '\n')
    doc.add_heading('Resultados del Análisis', level=1)
    for linea in texto.split('\n'):
        if linea.strip(): 
            if linea.startswith('#'): 
                doc.add_heading(linea.replace('#', '').strip(), level=2)
            else:
                doc.add_paragraph(linea)
    
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- INTERFAZ DE USUARIO ---

st.sidebar.title("🌐 StratIntel OSINT V9.0")
st.sidebar.markdown(f"**Motor:** {MODELO_ACTUAL}")
st.sidebar.markdown("---")

# LÓGICA DE CONEXIÓN (Ya autenticado por el login arriba)
if API_KEY_FIJA:
    st.session_state['api_key'] = API_KEY_FIJA
    genai.configure(api_key=API_KEY_FIJA)
    st.sidebar.success(f"✅ Conectado y Autenticado")
else:
    # Si no hay clave en secrets, pedir manual (por si acaso)
    if not st.session_state['api_key']:
        api_input = st.sidebar.text_input("🔑 API KEY (Admin):", type="password")
        if api_input:
            st.session_state['api_key'] = api_input
            genai.configure(api_key=api_input)
            st.rerun()

st.sidebar.markdown("---")
tecnica_seleccionada = st.sidebar.selectbox("1. Marco Metodológico:", list(DB_CONOCIMIENTO.keys()))

if DB_CONOCIMIENTO.get(tecnica_seleccionada):
    desc = DB_CONOCIMIENTO[tecnica_seleccionada].get("desc", "")
    if desc: st.sidebar.info(desc)

temperatura = st.sidebar.slider("Creatividad", 0.0, 1.0, 0.3)

# Botón de Cerrar Sesión
if st.sidebar.button("🔒 Cerrar Sesión"):
    del st.session_state["password_correct"]
    st.rerun()

st.title(f"Sistema de Inteligencia Híbrida")

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📄 PDF", "📝 DOCX", "🔗 Web Scraper", "📺 YouTube (AI)", "✍️ Manual"])

with tab1:
    pdf_file = st.file_uploader("Cargar PDF", type="pdf")
    if pdf_file and st.button("Procesar PDF"):
        reader = pypdf.PdfReader(pdf_file)
        text = "".join([p.extract_text() for p in reader.pages])
        st.session_state['texto_analisis'] = text
        st.session_state['origen_dato'] = f"PDF: {pdf_file.name}"
        st.success(f"PDF Cargado ({len(reader.pages)} págs)")

with tab2:
    docx_file = st.file_uploader("Cargar DOCX", type="docx")
    if docx_file and st.button("Procesar DOCX"):
        text = leer_docx(docx_file)
        st.session_state['texto_analisis'] = text
        st.session_state['origen_dato'] = f"DOCX: {docx_file.name}"
        st.success("Documento Word Cargado")

with tab3:
    url_web = st.text_input("URL de Noticia/Artículo:")
    if st.button("Extraer Web"):
        with st.spinner("Scrapeando sitio..."):
            text = obtener_texto_web(url_web)
            st.session_state['texto_analisis'] = text
            st.session_state['origen_dato'] = f"Web: {url_web}"
            st.success("Contenido Web Cargado")

with tab4:
    url_yt = st.text_input("URL de YouTube:")
    st.caption(f"Si no hay subtítulos, usaremos {MODELO_ACTUAL} para escuchar y transcribir el audio.")
    if st.button("Analizar Video"):
        if not st.session_state['api_key']:
            st.error("Necesitas API Key")
        else:
            with st.spinner("Procesando video..."):
                text, metodo = procesar_youtube(url_yt, st.session_state['api_key'])
                if metodo != "Error":
                    st.session_state['texto_analisis'] = text
                    st.session_state['origen_dato'] = f"YouTube ({metodo}): {url_yt}"
                    st.success(f"Video Procesado vía {metodo}")
                else:
                    st.error(text)

with tab5:
    manual_text = st.text_area("Texto manual", height=200)
    if st.button("Fijar Texto"):
        st.session_state['texto_analisis'] = manual_text
        st.session_state['origen_dato'] = "Entrada Manual"
        st.success("Texto manual fijado")

st.markdown("---")

# VISOR
if st.session_state['texto_analisis']:
    st.info(f"📂 Fuente Activa: **{st.session_state['origen_dato']}**")
    with st.expander("Ver contenido cargado"):
        st.write(st.session_state['texto_analisis'][:5000])

# ANÁLISIS
st.header("Ejecución de Inteligencia")
col1, col2 = st.columns([1, 2])

with col1:
    preguntas_disponibles = DB_CONOCIMIENTO.get(tecnica_seleccionada, {}).get("preguntas", [])
    if preguntas_disponibles:
        opcion_pregunta = st.radio("Enfoque:", ["Personalizada", "Responder TODAS automáticamente"] + preguntas_disponibles)
    else:
        opcion_pregunta = "Personalizada"

with col2:
    prompt_final = ""
    if opcion_pregunta == "Personalizada":
        prompt_final = st.text_area("Requerimiento (PIR):", height=150)
    elif opcion_pregunta == "Responder TODAS automáticamente":
        prompt_final = "RESPONDER TODO"
    else:
        prompt_final = st.text_area("PIR Seleccionado:", value=opcion_pregunta, height=150)

    if st.button("🚀 EJECUTAR MISIÓN", type="primary", use_container_width=True):
        if not st.session_state['api_key'] or not st.session_state['texto_analisis']:
            st.error("Faltan datos o API Key")
        else:
            try:
                genai.configure(api_key=st.session_state['api_key'])
                # USAR MODELO CONFIGURADO
                model = genai.GenerativeModel(MODELO_ACTUAL)
                contexto = st.session_state['texto_analisis']
                
                full_prompt = ""
                if prompt_final == "RESPONDER TODO":
                    lista_p = "\n".join([f"- {p}" for p in preguntas_disponibles])
                    full_prompt = f"""
                    ACTÚA COMO: Analista de Inteligencia Estratégica Senior.
                    TAREA: Informe completo. Metodología: '{tecnica_seleccionada}'.
                    Responde exhaustivamente a CADA UNA de estas preguntas usando el texto:
                    {lista_p}
                    FUENTE: {contexto}
                    FORMATO: Markdown profesional.
                    """
                else:
                    full_prompt = f"""
                    ACTÚA COMO: Analista de Inteligencia. Metodología: {tecnica_seleccionada}
                    PIR: {prompt_final}
                    FUENTE: {contexto}
                    """
                
                with st.spinner(f"Analizando con {MODELO_ACTUAL}..."):
                    response = model.generate_content(full_prompt, generation_config=genai.types.GenerationConfig(temperature=temperatura))
                    st.session_state['resultado_reciente'] = response.text
                    st.markdown("### 📡 Informe Generado")
                    st.write(response.text)
            
            except Exception as e:
                st.error(f"Error en la ejecución: {e}")

# DESCARGAS
if 'resultado_reciente' in st.session_state and st.session_state['resultado_reciente']:
    st.markdown("---")
    st.subheader("📥 Exportar Informe")
    col_d1, col_d2 = st.columns(2)
    
    docx_bytes = crear_word(st.session_state['resultado_reciente'], tecnica_seleccionada, st.session_state['origen_dato'])
    col_d1.download_button("Descargar WORD", docx_bytes, "Informe.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    
    try:
        pdf_bytes = crear_pdf(st.session_state['resultado_reciente'], tecnica_seleccionada, st.session_state['origen_dato'])
        col_d2.download_button("Descargar PDF", bytes(pdf_bytes), "Informe.pdf", "application/pdf")
    except Exception as e:
        col_d2.error(f"Error PDF: {e}")


