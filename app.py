import streamlit as st
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import pypdf
from docx import Document
from fpdf import FPDF
from pptx import Presentation 
from pptx.util import Inches, Pt
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import os
import time
import datetime
from langchain_community.tools import DuckDuckGoSearchRun

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="StratIntel V13 (Grand Strategy)", page_icon="♟️", layout="wide")

# ==========================================
# 🔐 SISTEMA DE LOGIN
# ==========================================
def check_password():
    def password_entered():
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("## ♟️ StratIntel: Acceso Restringido")
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
# 🧠 BASE DE DATOS DE CONOCIMIENTO
# ==========================================
DB_CONOCIMIENTO = {
    "✨ RECOMENDACIÓN AUTOMÁTICA": {
        "desc": "La IA decide la mejor estrategia.",
        "preguntas": ["Identifica los hallazgos estratégicos más críticos.", "Realiza una evaluación integral de riesgos.", "Genera un Resumen Ejecutivo (BLUF).", "¿Cuáles son las anomalías o patrones ocultos más relevantes?"]
    },
    "Niveles de Análisis (Barry Buzan)": {
        "desc": "Seguridad Multisectorial (Militar, Política, Económica, Societal, Ambiental).",
        "preguntas": [
            "Nivel Sistémico: ¿Cómo influye la anarquía internacional o la polaridad en el conflicto?",
            "Nivel Estatal: ¿Qué presiones burocráticas o nacionales limitan al Estado?",
            "Nivel Individual: ¿El perfil psicológico de los líderes altera la toma de decisiones?",
            "Seguridad Societal: ¿Está amenazada la identidad colectiva (religión, etnia, cultura)?"
        ]
    },
    "Evolución de la Cooperación (Axelrod)": {
        "desc": "Teoría de Juegos.",
        "preguntas": [
            "Sombra del Futuro: ¿Tienen los actores expectativas de interactuar nuevamente?",
            "Reciprocidad: ¿Está el actor respondiendo proporcionalmente (Tit-for-Tat)?",
            "Detección de Trampas: ¿Qué mecanismos de verificación existen?",
            "Estructura de Pagos: ¿Cómo alterar los incentivos para fomentar la cooperación?"
        ]
    },
    "Análisis FODA (SWOT) Intel": {
        "desc": "Enfoque de Inteligencia.",
        "preguntas": ["Vulnerabilidades internas críticas (Debilidades).", "Amenazas externas inminentes.", "Estrategia 'Maxi-Mini' (Defensiva).", "Cruce Fortalezas vs Oportunidades (Ofensiva)."]
    },
    "Análisis Geopolítico (PMESII-PT)": {
        "desc": "Variables del entorno operativo.",
        "preguntas": ["Interacción Política-Militar.", "Vulnerabilidad de Infraestructura crítica.", "Impacto Social y Cultural.", "Desglose completo PMESII-PT."]
    },
    "Análisis DIME (Poder Nacional)": {
        "desc": "Diplomático, Informacional, Militar, Económico.",
        "preguntas": ["Capacidad de proyección Económica (Sanciones/Ayudas).", "Aislamiento o alianzas Diplomáticas.", "Guerra de Información y Narrativa.", "Capacidad Militar real vs disuasoria."]
    },
    "Análisis de Hipótesis (ACH)": {
        "desc": "Validación de Hipótesis.",
        "preguntas": ["Generación de 4 Hipótesis concurrentes.", "Evidencia diagnóstica (que desmiente hipótesis).", "Intelligence Gaps (lo que no sabemos).", "Indicadores de Decepción (Engaño)."]
    },
    "Abogado del Diablo": {
        "desc": "Pensamiento crítico.",
        "preguntas": ["Desafío frontal a la conclusión más probable.", "Defensa lógica de la postura 'irracional' del adversario."]
    },
    "Escenarios Prospectivos": {
        "desc": "Cono de Plausibilidad.",
        "preguntas": ["Escenario Mejor Caso.", "Escenario Peor Caso.", "Escenario Cisne Negro (Wild Card).", "Drivers (Motores de cambio) clave."]
    },
    "Centro de Gravedad (COG)": {
        "desc": "Clausewitz.",
        "preguntas": ["Identificación del COG Estratégico.", "Capacidades Críticas (Requerimientos).", "Vulnerabilidades Críticas (Puntos débiles)."]
    },
    "Matriz CARVER": {
        "desc": "Selección de Objetivos.",
        "preguntas": ["Evaluación de Criticidad vs Vulnerabilidad.", "Efecto sistémico del objetivo.", "Recuperabilidad del activo."]
    }
}

# --- GESTIÓN DE ESTADO ---
if 'api_key' not in st.session_state: st.session_state['api_key'] = ""
if 'texto_analisis' not in st.session_state: st.session_state['texto_analisis'] = ""
if 'origen_dato' not in st.session_state: st.session_state['origen_dato'] = "Ninguno"

# --- FUNCIONES DE PROCESAMIENTO ---
def buscar_en_web(query):
    try:
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as e: return f"Error web: {e}"

def procesar_archivos_pdf(archivos):
    texto_total = ""
    nombres = []
    for archivo in archivos:
        reader = pypdf.PdfReader(archivo)
        texto_pdf = "".join([p.extract_text() for p in reader.pages])
        texto_total += f"\n--- ARCHIVO: {archivo.name} ---\n{texto_pdf}\n"
        nombres.append(archivo.name)
    return texto_total, str(nombres)

def procesar_archivos_docx(archivos):
    texto_total = ""
    nombres = []
    for archivo in archivos:
        doc = Document(archivo)
        texto_doc = "\n".join([para.text for para in doc.paragraphs])
        texto_total += f"\n--- ARCHIVO: {archivo.name} ---\n{texto_doc}\n"
        nombres.append(archivo.name)
    return texto_total, str(nombres)

def obtener_texto_web(url):
    try:
        h = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=h, timeout=15)
        s = BeautifulSoup(r.content, 'html.parser')
        for script in s(["script", "style"]): script.extract()
        return s.get_text(separator='\n')
    except Exception as e: return f"Error: {e}"

def procesar_youtube(url, api_key):
    vid = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    try:
        t = YouTubeTranscriptApi.get_transcript(vid, languages=['es', 'en'])
        return " ".join([i['text'] for i in t]), "Subtítulos"
    except:
        st.info(f"Multimodal (Audio)...")
        opts = {'format': 'bestaudio/best', 'outtmpl': '%(id)s.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                fname = f"{info['id']}.mp3"
            genai.configure(api_key=api_key)
            myfile = genai.upload_file(fname)
            while myfile.state.name == "PROCESSING": time.sleep(10); myfile = genai.get_file(myfile.name)
            model = genai.GenerativeModel(MODELO_ACTUAL)
            res = model.generate_content([myfile, "Transcribe el audio."])
            if os.path.exists(fname): os.remove(fname)
            myfile.delete()
            return res.text, "Audio IA"
        except Exception as e: return f"Error: {e}", "Error"

# --- FUNCIONES DE REPORTE ---
def limpiar_texto(t):
    if not t: return ""
    reps = {"✨": "", "🚀": "", "⚠️": "[!]", "✅": "[OK]", "🛡️": "", "🔒": "", "🎖️": "", "♟️": ""}
    for k,v in reps.items(): t = t.replace(k,v)
    return t.encode('latin-1', 'replace').decode('latin-1')

def crear_pptx(texto, tecnicas, fuente):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Informe de Inteligencia V13"
    slide.placeholders[1].text = f"Fuente: {fuente}\nGenerado por IA"

    secciones = texto.split("## 📌")
    for seccion in secciones:
        if not seccion.strip(): continue
        lineas = seccion.strip().split("\n")
        titulo = lineas[0].strip()
        contenido = "\n".join(lineas[1:])[:1500] 
        
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = titulo
        slide.shapes.placeholders[1].text_frame.text = contenido

    b = BytesIO(); prs.save(b); b.seek(0)
    return b

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'StratIntel Report V13', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 7)
        self.cell(0, 10, 'Generado por IA. Uso Confidencial.', 0, 0, 'C')

def crear_pdf(texto, tecnicas, fuente):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 10)
    pdf.multi_cell(0, 5, limpiar_texto(f"Fuente: {fuente}\nTécnicas: {tecnicas}"))
    pdf.ln(5)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, limpiar_texto(texto))
    return pdf.output(dest='S').encode('latin-1', 'replace')

def crear_word(texto, tecnicas, fuente):
    doc = Document()
    doc.add_heading('StratIntel Intelligence Report V13', 0)
    doc.add_paragraph(f"Fuente: {fuente}").bold = True
    doc.add_paragraph(f"Técnicas: {tecnicas}").bold = True
    for l in texto.split('\n'):
        if l.startswith('#'): doc.add_heading(l.replace('#','').strip(), level=2)
        else: doc.add_paragraph(l)
    
    aviso = doc.add_paragraph()
    aviso.add_run("\n\n------------------\nAVISO: Generado por IA. Verificar datos.").font.size = Pt(8)
    b = BytesIO(); doc.save(b); b.seek(0)
    return b

# --- INTERFAZ ---
st.sidebar.title("♟️ StratIntel V13")
st.sidebar.caption("Grand Strategy Edition")
st.sidebar.markdown("---")

if API_KEY_FIJA:
    st.session_state['api_key'] = API_KEY_FIJA
    genai.configure(api_key=API_KEY_FIJA)
    st.sidebar.success(f"✅ Conectado")
else:
    if not st.session_state['api_key']:
        k = st.sidebar.text_input("🔑 API KEY:", type="password")
        if k: st.session_state['api_key'] = k; genai.configure(api_key=k); st.rerun()

# SELECTOR MULTI-TECNICA
st.sidebar.subheader("🎯 Misión")
tecnicas_seleccionadas = st.sidebar.multiselect(
    "Técnicas (Máx 3):",
    options=list(DB_CONOCIMIENTO.keys()),
    max_selections=3
)

temp = st.sidebar.slider("Creatividad", 0.0, 1.0, 0.4)
if st.sidebar.button("🔒 Salir"): del st.session_state["password_correct"]; st.rerun()

st.title("♟️ StratIntel | División de Análisis")
st.markdown("**Sistema de Apoyo a la Decisión (DSS) v13.0**")

# CARGA
t1, t2, t3, t4, t5 = st.tabs(["📂 PDFs", "📝 DOCXs", "🌐 Web", "📺 YouTube", "✍️ Manual"])
with t1:
    f = st.file_uploader("PDFs", type="pdf", accept_multiple_files=True)
    if f and st.button("Procesar PDF"):
        t, n = procesar_archivos_pdf(f); st.session_state['texto_analisis']=t; st.session_state['origen_dato']=f"PDFs: {n}"; st.success(f"✅ {len(f)}")
with t2:
    f = st.file_uploader("DOCXs", type="docx", accept_multiple_files=True)
    if f and st.button("Procesar DOCX"):
        t, n = procesar_archivos_docx(f); st.session_state['texto_analisis']=t; st.session_state['origen_dato']=f"DOCXs: {n}"; st.success(f"✅ {len(f)}")
with t3:
    u = st.text_input("URL"); 
    if st.button("Web"): st.session_state['texto_analisis']=obtener_texto_web(u); st.session_state['origen_dato']=f"Web: {u}"; st.success("OK")
with t4:
    y = st.text_input("YouTube")
    if st.button("Video"):
        with st.spinner("..."):
            t,m=procesar_youtube(y,st.session_state['api_key'])
            if m!="Error": st.session_state['texto_analisis']=t; st.session_state['origen_dato']=f"YT: {y}"; st.success("OK")
            else: st.error(t)
with t5:
    m = st.text_area("Manual")
    if st.button("Fijar"): st.session_state['texto_analisis']=m; st.session_state['origen_dato']="Manual"; st.success("OK")

st.markdown("---")
if st.session_state['texto_analisis']:
    with st.expander(f"Fuente Activa: {st.session_state['origen_dato']}"): st.write(st.session_state['texto_analisis'][:1000])

# EJECUCIÓN
st.header("Generación de Inteligencia")

if not st.session_state['api_key'] or not st.session_state['texto_analisis']:
    st.warning("⚠️ Carga datos para comenzar.")
else:
    c1, c2 = st.columns([1, 2])
    with c1:
        if not tecnicas_seleccionadas: st.info("👈 Selecciona técnicas.")
        
        # --- NUEVO: SELECTOR DE PROFUNDIDAD ---
        profundidad = st.radio(
            "Nivel de Profundidad:", 
            ["🔍 Estratégico (Resumen General)", "🎯 Táctico (Responder TODAS las preguntas predefinidas)"],
            help="Estratégico: Análisis libre de la técnica. Táctico: Obliga a la IA a responder la lista de preguntas de la base de datos."
        )
        
        usar_internet = st.checkbox("🌐 Búsqueda Web")
        pir = st.text_area("PIR (Opcional):", height=100)

    with c2:
        if st.button("🚀 EJECUTAR MISIÓN", type="primary", use_container_width=True, disabled=len(tecnicas_seleccionadas)==0):
            try:
                genai.configure(api_key=st.session_state['api_key'])
                model = genai.GenerativeModel(MODELO_ACTUAL)
                ctx = st.session_state['texto_analisis']
                
                # BÚSQUEDA WEB
                contexto_web = ""
                if usar_internet:
                    with st.status("🌐 Buscando...", expanded=True) as s:
                        q = f"{pir} {st.session_state['origen_dato']}" if pir else f"Análisis {st.session_state['origen_dato']}"
                        res_web = buscar_en_web(q)
                        contexto_web = f"\nINFO WEB:\n{res_web}\n"
                        s.update(label="✅ Hecho", state="complete", expanded=False)
                
                # BUCLE DE ANÁLISIS
                informe_final = f"# INFORME V13\nFECHA: {datetime.datetime.now().strftime('%d/%m/%Y')}\nFUENTE: {st.session_state['origen_dato']}\n\n"
                progreso = st.progress(0)
                
                for i, tec in enumerate(tecnicas_seleccionadas):
                    st.caption(f"Analizando: {tec}...")
                    
                    # --- LÓGICA DE INYECCIÓN DE PREGUNTAS (AQUÍ ESTÁ LA MAGIA) ---
                    preguntas_base = DB_CONOCIMIENTO.get(tec, {}).get("preguntas", [])
                    
                    instruccion_preguntas = ""
                    if "Táctico" in profundidad and preguntas_base:
                        lista_formateada = "\n".join([f"- {p}" for p in preguntas_base])
                        instruccion_preguntas = f"\n\nOBLIGATORIO: Debes responder DETALLADAMENTE a cada una de las siguientes preguntas propias de esta metodología:\n{lista_formateada}"
                    else:
                        instruccion_preguntas = "\n\nINSTRUCCIÓN: Realiza un análisis general profundo aplicando los principios de esta metodología."

                    prompt = f"""
                    ACTÚA COMO: Analista de Inteligencia Senior.
                    METODOLOGÍA: {tec}
                    PIR: {pir}
                    
                    {instruccion_preguntas}
                    
                    CONTEXTO DOCUMENTAL:
                    {ctx}
                    {contexto_web}
                    
                    FORMATO: Académico, riguroso, citar fuentes.
                    """
                    
                    res = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=temp))
                    informe_final += f"\n\n## 📌 {tec}\n{res.text}\n\n---\n"
                    progreso.progress((i + 1) / len(tecnicas_seleccionadas))
                    time.sleep(2)
                
                st.session_state['res'] = informe_final
                st.session_state['tecnicas_usadas'] = ", ".join(tecnicas_seleccionadas)
                st.success("✅ Misión Completada")
                st.markdown(informe_final)

            except Exception as e: st.error(f"Error: {e}")

if 'res' in st.session_state:
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Word", crear_word(st.session_state['res'], st.session_state['tecnicas_usadas'], st.session_state['origen_dato']), "Reporte.docx")
    try: c2.download_button("PDF", bytes(crear_pdf(st.session_state['res'], st.session_state['tecnicas_usadas'], st.session_state['origen_dato'])), "Reporte.pdf")
    except: pass
    try: c3.download_button("PowerPoint", crear_pptx(st.session_state['res'], st.session_state['tecnicas_usadas'], st.session_state['origen_dato']), "Slides.pptx")
    except: pass

