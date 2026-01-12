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
st.set_page_config(page_title="StratIntel V10 (Heavy Duty)", page_icon="🛡️", layout="wide")

# ==========================================
# 🔐 SISTEMA DE LOGIN
# ==========================================
def check_password():
    """Retorna `True` si el usuario tiene la contraseña correcta."""
    def password_entered():
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("## 🛡️ StratIntel: Acceso Restringido")
    st.text_input("Usuario", key="username")
    st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Credenciales inválidas")
    return False

if not check_password():
    st.stop()

# ==========================================
# ⚙️ CONFIGURACIÓN Y MODELO
# ==========================================
API_KEY_FIJA = "" 
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY_FIJA = st.secrets["GOOGLE_API_KEY"]

MODELO_ACTUAL = "gemini-3-flash-preview"  

# ==========================================
# 🧠 BASE DE DATOS DE CONOCIMIENTO (ACTUALIZADA V10)
# ==========================================
DB_CONOCIMIENTO = {
    "✨ RECOMENDACIÓN AUTOMÁTICA (IA)": {
        "desc": "La IA analiza todos los documentos y decide la mejor estrategia.",
        "preguntas": ["Identifica los hallazgos estratégicos más críticos y sus implicaciones.", "Realiza una evaluación integral de riesgos y oportunidades.", "Genera un Resumen Ejecutivo (BLUF) para la toma de decisiones.", "¿Cuáles son las anomalías o patrones ocultos más relevantes?"]
    },
    "--- NUEVOS ENFOQUES TEÓRICOS ---": { "desc": "", "preguntas": [] },
    "Niveles de Análisis (Barry Buzan)": {
        "desc": "Seguridad Multisectorial: Militar, Política, Económica, Societal y Ambiental.",
        "preguntas": [
            "Nivel Sistémico: ¿Cómo influye la anarquía internacional o la polaridad en el conflicto?",
            "Nivel Estatal: ¿Qué presiones burocráticas o nacionales limitan al Estado?",
            "Nivel Individual: ¿El perfil psicológico de los líderes altera la toma de decisiones?",
            "Seguridad Societal: ¿Está amenazada la identidad colectiva (religión, etnia, cultura)?"
        ]
    },
    "Evolución de la Cooperación (Robert Axelrod)": {
        "desc": "Teoría de Juegos: Dilema del Prisionero y Tit-for-Tat.",
        "preguntas": [
            "Sombra del Futuro: ¿Tienen los actores expectativas de interactuar nuevamente? (Clave para cooperar).",
            "Reciprocidad: ¿Está el actor respondiendo proporcionalmente (Tit-for-Tat) o escalando?",
            "Detección de Trampas: ¿Qué mecanismos de verificación existen para asegurar el cumplimiento?",
            "Estructura de Pagos: ¿Cómo alterar los incentivos para que cooperar sea más rentable que traicionar?"
        ]
    },
    "--- TÉCNICAS DIAGNÓSTICAS ---": { "desc": "", "preguntas": [] },
    "Análisis FODA (SWOT) Estratégico": {
        "desc": "Fortalezas, Oportunidades, Debilidades y Amenazas (Enfoque Intel).",
        "preguntas": ["Identifica las vulnerabilidades internas críticas (Debilidades) explotables.", "¿Qué amenazas externas inminentes ponen en riesgo la estabilidad?", "Estrategia 'Maxi-Mini': Usar fortalezas para minimizar amenazas."]
    },
    "Análisis Geopolítico (PMESII-PT)": {
        "desc": "Político, Militar, Económico, Social, Infraestructura, Info.",
        "preguntas": ["Analiza la interacción de variables Políticas y Militares.", "Evalúa la vulnerabilidad de la Infraestructura crítica.", "Desglosa la situación utilizando las 8 variables PMESII-PT."]
    },
    "Análisis DIME (Instrumentos de Poder)": {
        "desc": "Diplomático, Informacional, Militar, Económico.",
        "preguntas": ["Evalúa la proyección de poder Económico.", "¿Cómo se usan los canales Diplomáticos para aislar al adversario?", "Analiza la campaña de Información (Guerra Psicológica)."]
    },
    "--- CONTRASTE Y PROSPECTIVA ---": { "desc": "", "preguntas": [] },
    "Análisis de Hipótesis en Competencia (ACH)": {
        "desc": "Evaluar múltiples explicaciones para reducir sesgos.",
        "preguntas": ["Genera 4 hipótesis y puntúa la evidencia.", "¿Qué información faltante (Intelligence Gap) confirmaría las Hipótesis?", "Evalúa la posibilidad de 'Decepción' (engaño)."]
    },
    "Abogado del Diablo": {
        "desc": "Cuestionar la premisa dominante.",
        "preguntas": ["Desafía la conclusión obvia: ¿Por qué podría ser falsa?", "Defiende la postura del actor 'irracional' como si fuera lógica."]
    },
    "Escenarios Prospectivos": {
        "desc": "Cono de Plausibilidad.",
        "preguntas": ["Desarrolla 4 escenarios: Mejor, Peor, Wild Card e Híbrido.", "Identifica los 'Drivers' (motores de cambio) clave."]
    },
    "Centro de Gravedad (COG)": {
        "desc": "Fuente de poder (Clausewitz).",
        "preguntas": ["Identifica el COG Estratégico y sus Capacidades Críticas.", "Define las Vulnerabilidades Críticas para anular el COG."]
    }
}

# --- GESTIÓN DE ESTADO ---
if 'api_key' not in st.session_state: st.session_state['api_key'] = ""
if 'texto_analisis' not in st.session_state: st.session_state['texto_analisis'] = ""
if 'origen_dato' not in st.session_state: st.session_state['origen_dato'] = "Ninguno"

# --- FUNCIONES DE PROCESAMIENTO ---

def procesar_archivos_pdf(archivos):
    texto_total = ""
    nombres = []
    for archivo in archivos:
        reader = pypdf.PdfReader(archivo)
        texto_pdf = "".join([p.extract_text() for p in reader.pages])
        texto_total += f"\n--- INICIO ARCHIVO: {archivo.name} ---\n{texto_pdf}\n--- FIN ARCHIVO ---\n"
        nombres.append(archivo.name)
    return texto_total, ", ".join(nombres)

def procesar_archivos_docx(archivos):
    texto_total = ""
    nombres = []
    for archivo in archivos:
        doc = Document(archivo)
        texto_doc = "\n".join([para.text for para in doc.paragraphs])
        texto_total += f"\n--- INICIO ARCHIVO: {archivo.name} ---\n{texto_doc}\n--- FIN ARCHIVO ---\n"
        nombres.append(archivo.name)
    return texto_total, ", ".join(nombres)

def obtener_texto_web(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        return soup.get_text(separator='\n')
    except Exception as e: return f"Error: {e}"

def procesar_youtube(url, api_key):
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en'])
        return " ".join([i['text'] for i in transcript]), "Subtítulos"
    except:
        st.info(f"Usando {MODELO_ACTUAL} para escuchar el video (Multimodal)...")
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': '%(id)s.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = f"{info['id']}.mp3"
            genai.configure(api_key=api_key)
            myfile = genai.upload_file(filename)
            while myfile.state.name == "PROCESSING": time.sleep(2); myfile = genai.get_file(myfile.name)
            model = genai.GenerativeModel(MODELO_ACTUAL)
            res = model.generate_content([myfile, "Transcribe el audio."])
            if os.path.exists(filename): os.remove(filename)
            myfile.delete()
            return res.text, "Audio IA"
        except Exception as e: return f"Error: {e}", "Error"

# --- FUNCIONES DE REPORTE (BLINDADAS) ---

def limpiar_texto_pdf(texto):
    if not texto: return ""
    reemplazos = {"✨": "", "🚀": "", "⚠️": "[!]", "✅": "[OK]", "🛡️": "", "🔒": ""}
    for k, v in reemplazos.items(): texto = texto.replace(k, v)
    return texto.encode('latin-1', 'replace').decode('latin-1')

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Informe StratIntel V10', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-25) # Subimos un poco para que quepa el texto
        self.set_font('Arial', 'I', 7)
        legal_text = (
            "AVISO LEGAL: Este informe ha sido generado mediante sistemas de Inteligencia Artificial (IA) "
            "con fines de análisis preliminar. La información contenida puede no ser exacta o completa. "
            "El usuario asume toda la responsabilidad por el uso de estos datos para la toma de decisiones. "
            "RESERVADO - PROPIEDAD DEL USUARIO."
        )
        self.multi_cell(0, 3, legal_text, align='C')

def crear_pdf(texto, tecnica, fuente):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 10)
    pdf.multi_cell(0, 5, limpiar_texto_pdf(f"Fuente(s): {fuente}"))
    pdf.ln(2)
    pdf.cell(0, 10, limpiar_texto_pdf(f"Metodología: {tecnica}"), ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, limpiar_texto_pdf(texto))
    return pdf.output(dest='S').encode('latin-1', 'replace')

def crear_word(texto, tecnica, fuente):
    doc = Document()
    doc.add_heading('Informe StratIntel V10', 0)
    doc.add_paragraph(f"Fuente: {fuente}").bold = True
    doc.add_paragraph(f"Metodología: {tecnica}").bold = True
    doc.add_heading('Análisis', level=1)
    for linea in texto.split('\n'):
        if linea.startswith('#'): doc.add_heading(linea.replace('#', '').strip(), level=2)
        else: doc.add_paragraph(linea)
    # ... código anterior ...
    
    # DISCLAIMER ROBUSTO
    aviso = doc.add_paragraph()
    aviso_runner = aviso.add_run(
        "\n\n------------------------------------------------------------\n"
        "AVISO DE RESPONSABILIDAD:\n"
        "Este documento fue generado asistido por Inteligencia Artificial Avanzada. "
        "El análisis presentado se basa en los datos suministrados y patrones probabilísticos. "
        "No constituye asesoramiento legal, financiero ni militar vinculante. "
        "El operador humano debe verificar los hallazgos críticos antes de ejecutar acciones."
    )
    aviso_runner.font.size = 8
    aviso_runner.italic = True
    
    b = BytesIO(); doc.save(b); b.seek(0)
    return b

# --- INTERFAZ ---
st.sidebar.title("🛡️ StratIntel V10")
st.sidebar.caption("SaaS Edition | Multi-Target")
st.sidebar.markdown("---")

if API_KEY_FIJA:
    st.session_state['api_key'] = API_KEY_FIJA
    genai.configure(api_key=API_KEY_FIJA)
    st.sidebar.success(f"✅ Conectado ({MODELO_ACTUAL})")
else:
    if not st.session_state['api_key']:
        k = st.sidebar.text_input("🔑 API KEY:", type="password")
        if k: st.session_state['api_key'] = k; genai.configure(api_key=k); st.rerun()

tecnica = st.sidebar.selectbox("Marco Metodológico:", list(DB_CONOCIMIENTO.keys()))
if DB_CONOCIMIENTO[tecnica]["desc"]: st.sidebar.info(DB_CONOCIMIENTO[tecnica]["desc"])
temp = st.sidebar.slider("Creatividad", 0.0, 1.0, 0.4)

if st.sidebar.button("🔒 Salir"):
    del st.session_state["password_correct"]
    st.rerun()

st.title("🛡️ StratIntel | División de Análisis")
st.markdown("**Sistema de Apoyo a la Decisión (DSS) v10.0**")

# --- TABS CON CARGA MÚLTIPLE ---
t1, t2, t3, t4, t5 = st.tabs(["📂 Multi-PDF", "📝 Multi-DOCX", "🌐 Web", "📺 YouTube", "✍️ Manual"])

with t1:
    pdfs = st.file_uploader("Subir PDFs (Permite Múltiples)", type="pdf", accept_multiple_files=True)
    if pdfs and st.button("Procesar Lote PDF"):
        txt, nombres = procesar_archivos_pdf(pdfs)
        st.session_state['texto_analisis'] = txt
        st.session_state['origen_dato'] = f"Lote PDF: {nombres}"
        st.success(f"✅ Procesados {len(pdfs)} archivos.")

with t2:
    docs = st.file_uploader("Subir Words (Permite Múltiples)", type="docx", accept_multiple_files=True)
    if docs and st.button("Procesar Lote DOCX"):
        txt, nombres = procesar_archivos_docx(docs)
        st.session_state['texto_analisis'] = txt
        st.session_state['origen_dato'] = f"Lote DOCX: {nombres}"
        st.success(f"✅ Procesados {len(docs)} archivos.")

with t3:
    url = st.text_input("URL Noticia:")
    if st.button("Extraer"):
        st.session_state['texto_analisis'] = obtener_texto_web(url)
        st.session_state['origen_dato'] = f"Web: {url}"
        st.success("Web Cargada")

with t4:
    yt = st.text_input("URL YouTube:")
    st.caption("Si no tiene subs, descarga y escucha el audio.")
    if st.button("Analizar Video"):
        if not st.session_state['api_key']: st.error("Falta API Key")
        else:
            with st.spinner("Procesando..."):
                txt, met = procesar_youtube(yt, st.session_state['api_key'])
                if met != "Error":
                    st.session_state['texto_analisis'] = txt
                    st.session_state['origen_dato'] = f"YT: {yt}"
                    st.success(f"Video ({met}) Cargado")
                else: st.error(txt)

with t5:
    man = st.text_area("Texto Manual")
    if st.button("Fijar"):
        st.session_state['texto_analisis'] = man
        st.session_state['origen_dato'] = "Manual"

st.markdown("---")
if st.session_state['texto_analisis']:
    st.info(f"📂 Fuente Activa: **{st.session_state['origen_dato']}**")
    with st.expander("Ver Datos Cargados"): st.write(st.session_state['texto_analisis'][:2000] + "...")

# --- EJECUCIÓN ---
st.header("Generación de Informe")
c1, c2 = st.columns([1, 2])

with c1:
    pregs = DB_CONOCIMIENTO.get(tecnica, {}).get("preguntas", [])
    mode = st.radio("Modo:", ["Personalizado", "AUTO: Responder TODO"] + pregs)

with c2:
    pir = st.text_area("Requerimiento (PIR):", value="" if "AUTO" in mode or mode in pregs else "", height=150)
    
    if st.button("🚀 EJECUTAR ANÁLISIS PROFUNDO", type="primary", use_container_width=True):
        if not st.session_state['api_key'] or not st.session_state['texto_analisis']:
            st.error("Datos insuficientes")
        else:
            try:
                genai.configure(api_key=st.session_state['api_key'])
                model = genai.GenerativeModel(MODELO_ACTUAL)
                ctx = st.session_state['texto_analisis']
                
                # PROMPT V10: INGENIERÍA PARA EXTENSIÓN Y PROFUNDIDAD
                instruccion_base = f"""
                ACTÚA COMO: Especialista en Derecho y Política Internacional y Analista de Inteligencia Estratégica Senior (Nivel Gubernamental).
                TAREA: Generar un informe de inteligencia exhaustivo y detallado.
                METODOLOGÍA: {tecnica}
                
                INSTRUCCIONES DE FORMATO Y PROFUNDIDAD:
                1. NO RESUMAS. Tu objetivo es la profundidad y el detalle.
                2. Cada punto analizado debe tener al menos 2-3 párrafos de desarrollo.
                3. Usa un tono académico, objetivo y formal.
                4. Cita textualmente las fuentes proporcionadas cuando sea relevante.
                5. Estructura la respuesta con encabezados Markdown claros.
                """

                if "AUTO: Responder TODO" in mode:
                    lista_p = "\n".join([f"- {p}" for p in pregs])
                    full_prompt = f"{instruccion_base}\n\nResponde DETALLADAMENTE a cada una de estas preguntas:\n{lista_p}\n\nCONTEXTO:\n{ctx}"
                elif mode in pregs:
                    full_prompt = f"{instruccion_base}\n\nPREGUNTA ESPECÍFICA:\n{mode}\n\nCONTEXTO:\n{ctx}"
                else:
                    full_prompt = f"{instruccion_base}\n\nREQUERIMIENTO (PIR):\n{pir}\n\nCONTEXTO:\n{ctx}"
                
                with st.spinner(f"Analizando a profundidad con {MODELO_ACTUAL}..."):
                    res = model.generate_content(full_prompt, generation_config=genai.types.GenerationConfig(temperature=temp))
                    st.session_state['res'] = res.text
                    st.markdown("### 📡 Informe Generado")
                    st.write(res.text)
            except Exception as e: st.error(f"Error: {e}")

if 'res' in st.session_state:
    st.markdown("---")
    cd1, cd2 = st.columns(2)
    cd1.download_button("Descargar WORD", crear_word(st.session_state['res'], tecnica, st.session_state['origen_dato']), "Informe_V10.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    try: cd2.download_button("Descargar PDF", bytes(crear_pdf(st.session_state['res'], tecnica, st.session_state['origen_dato'])), "Informe_V10.pdf", "application/pdf")
    except Exception as e: cd2.error(f"Error PDF: {e}")

