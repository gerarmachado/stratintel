import streamlit as st
import google.generativeai as genai
import pypdf
from docx import Document
from fpdf import FPDF
from io import BytesIO
import os
import time
import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="StratIntel Beta", page_icon="♟️", layout="wide")

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

MODELO_ACTUAL = "gemini-2.5-flash"  

# ==========================================
# 🧠 BASE DE DATOS MAESTRA (V15 - ENFOQUES INTEGRALES)
# ==========================================
DB_CONOCIMIENTO = {
    "✨ RECOMENDACIÓN AUTOMÁTICA": {
        "desc": "La IA decide la mejor estrategia basándose en el contenido.",
        "preguntas": ["Identifica los hallazgos estratégicos más críticos.", "Realiza una evaluación integral de riesgos.", "Genera un Resumen Ejecutivo (BLUF).", "¿Cuáles son las anomalías o patrones ocultos más relevantes?"]
    },

    # -------------------------------------------------------------------------
    # 🏛️ ESCUELA REALISTA (PODER Y ESTRUCTURA)
    # -------------------------------------------------------------------------
    "--- REALISMO Y PODER ---": { "desc": "", "preguntas": [] },

    "Hans Morgenthau (Realismo Clásico Integral)": {
        "desc": "Los 6 Principios del Realismo Político y el Interés como Poder.",
        "preguntas": [
            "Leyes Objetivas: ¿Qué fuerzas inherentes a la naturaleza humana (egoísmo, dominio) están impulsando este conflicto?",
            "Interés y Poder: Define el 'Interés Nacional' de los actores en términos de poder, no de moralidad.",
            "Supervivencia del Estado: ¿Está la integridad territorial o política del Estado en riesgo directo?",
            "Autonomía de la Esfera Política: Analiza la decisión desde una lógica puramente política, ignorando consideraciones económicas o legales secundarias."
        ]
    },
    "Kenneth Waltz (Neorrealismo / Imágenes)": {
        "desc": "Las Tres Imágenes (Hombre, Estado, Sistema) y la Estructura Anárquica.",
        "preguntas": [
            "Tercera Imagen (Sistémica): ¿Cómo la anarquía internacional y la distribución de poder (polaridad) obligan al actor a actuar así?", 
            "Polaridad: ¿Cómo afecta la distribución de capacidades (unipolar/multipolar)?",
            "Segunda Imagen (Estatal): ¿Es el régimen político interno irrelevante para la política exterior en este caso?",
            "Equilibrio de Poder: ¿Está el actor haciendo 'Balancing' (aliarse contra el fuerte) o 'Bandwagoning' (unirse al fuerte)?",
            "Principio de Autoayuda: ¿Qué medidas unilaterales está tomando el actor para garantizar su propia seguridad? ¿El comportamiento es defensivo (seguridad) u ofensivo (poder)?"
        ]
    },
    "John Mearsheimer (Realismo Ofensivo)": {
        "desc": "La Tragedia de las Grandes Potencias y la Hegemonía.",
        "preguntas": [
            "Búsqueda de Hegemonía: ¿Está el actor intentando convertirse en el Hegemon regional para asegurar su supervivencia? ¿Está aprovechando oportunidades para alterar el status quo?",
            "Poder Detenedor del Agua: ¿Cómo la geografía (océanos, montañas) limita la proyección de poder del actor? Evalúa el potencial de poder latente (economía/población) vs poder militar actual.",
            "Maximizador de Poder: ¿Está el actor aprovechando cada oportunidad para debilitar a sus rivales potenciales? ¿Cómo está maximizando su poder relativo a expensas de sus vecinos?",
            "Estrategia de 'Buck-Passing': ¿Está intentando que otro estado asuma el costo de contener al agresor?"
        ]
    },
    "Stephen Walt & Robert Jervis (Realismo Defensivo)": {
        "desc": "Equilibrio de Amenazas y Dilema de Seguridad.",
        "preguntas": [
            "Teoría del Equilibrio de Amenazas: Evalúa la amenaza combinando: 1) Poder Agregado, 2) Geografía, 3) Capacidad Ofensiva, 4) Intenciones Agresivas. ¿Quién es percibido como el más amenazante (no solo el más fuerte)?",
            "Dilema de Seguridad: ¿Las medidas defensivas de un actor están siendo malinterpretadas como ofensivas por el otro?",
            "Espiral de Conflicto: ¿Cómo una acción defensiva ha provocado una reacción hostil involuntaria? ¿Las intenciones agresivas son reales o producto de la incertidumbre sistémica?"
        ]
    },
    "Realismo Neoclásico (Schweller)": {
        "desc": "El sistema presiona, pero la política interna decide.",
        "preguntas": [
            "¿Qué variables domésticas están filtrando o bloqueando la respuesta al sistema internacional?",
            "¿Es el estado 'coherente' o están las élites fragmentadas?",
            "¿Tiene el gobierno la capacidad extractiva para movilizar recursos ante la amenaza?"
        ]
    },
    "Realismo Periférico (Carlos Escudé)": {
        "desc": "Estrategia de supervivencia para estados dependientes (Sur Global).",
        "preguntas": [
            "Costo-Beneficio de la Soberanía: ¿El costo de confrontar al Hegemon supera los beneficios para el bienestar ciudadano?",
            "Política de Alineamiento: ¿Debería el estado adoptar un perfil bajo o alinearse para obtener recursos y evitar sanciones?",
            "Evaluación de Autonomía: ¿Se está sacrificando el desarrollo económico por una retórica nacionalista vacía?"
        ]
    },

    # -------------------------------------------------------------------------
    # 🤝 ESCUELA LIBERAL Y CONSTRUCTIVISTA (INSTITUCIONES E IDENTIDAD)
    # -------------------------------------------------------------------------
    "--- LIBERALISMO, IDENTIDAD Y COOPERACIÓN ---": { "desc": "", "preguntas": [] },

    "Joseph Nye (Poder Multidimensional 3D)": {
        "desc": "Soft Power, Smart Power y el Tablero de Ajedrez Tridimensional.",
        "preguntas": [
            "Dimensión Soft Power: ¿Qué activos de cultura, valores o políticas otorgan atracción y legitimidad al actor?",
            "Dimensión Smart Power: ¿Está combinando eficazmente la coerción (Hard) con la persuasión (Soft)?",
            "Tablero Superior (Militar): Analiza la distribución de poder militar (¿Unipolar?).",
            "Tablero Medio (Económico): Analiza la distribución económica (¿Multipolar?).",
            "Tablero Inferior (Transnacional): ¿Qué actores no estatales (Hackers, ONGs, Terrorismo) actúan fuera del control estatal?"
        ]
    },
    "Robert Axelrod (Complejidad de la Cooperación)": {
        "desc": "Teoría de Juegos, Evolución de la Cooperación y Normas.",
        "preguntas": [
            "El Dilema del Prisionero: ¿Existen incentivos estructurales que hacen racional la traición individual?",
            "Estrategia Tit-for-Tat: ¿Está el actor respondiendo con reciprocidad estricta? ¿Está respondiendo proporcionalmente o escalando?",
            "La Sombra del Futuro: ¿Es la interacción lo suficientemente duradera para fomentar la cooperación? ¿Tienen expectativas de interactuar nuevamente?",
            "Meta-Normas: ¿Existe presión social o sanciones de terceros para castigar a los desertores?",
            "Detección de Trampas: ¿Qué mecanismos de verificación existen para asegurar el cumplimiento?",
            "Estructura de Pagos: ¿Cómo alterar los incentivos para que cooperar sea más rentable que traicionar?"
        ]
    },
    "Immanuel Kant (Triángulo de la Paz Liberal)": {
        "desc": "Paz Democrática, Interdependencia Económica e Instituciones.",
        "preguntas": [
            "Paz Democrática: ¿Son los actores democracias? (Si lo son, la probabilidad de guerra disminuye drásticamente).",
            "Interdependencia Económica: ¿El nivel de comercio mutuo hace que la guerra sea demasiado costosa?",
            "Organizaciones Internacionales: ¿Pertenecen a instituciones comunes que medien el conflicto?",
            "Derecho Cosmopolita: ¿Existe un respeto supranacional por los derechos de los ciudadanos?"
        ]
    },
    "Keohane & Nye (Neoliberalismo Institucional)": {
        "desc": "Interdependencia Compleja y Regímenes Internacionales.",
        "preguntas": [
            "Canales Múltiples: ¿Existen conexiones entre sociedades (no solo entre gobiernos)? ¿Qué instituciones facilitan la cooperación?",
            "Ausencia de Jerarquía: ¿Están los temas militares subordinados a temas económicos o ecológicos en esta crisis?",
            "Interdependencia Compleja: ¿Los vínculos económicos hacen la guerra irracional?",
            "Regímenes Internacionales: ¿Qué normas o reglas implícitas gobiernan las expectativas? ¿Existe un régimen internacional que regule este conflicto?"
        ]
    },
    "Alexander Wendt (Constructivismo Social)": {
        "desc": "La anarquía es lo que los estados hacen de ella.",
        "preguntas": [
            "Culturas de la Anarquía: ¿El sistema es Hobbesiano (Enemigos), Lockeano (Rivales) o Kantiano (Amigos)?",
            "Estructura Ideacional: ¿Cómo las identidades históricas y normas sociales definen el interés nacional?",
            "Ciclo de Refuerzo: ¿Cómo las interacciones pasadas han construido la percepción actual de 'amenaza'?",
            "Normas Internacionales: ¿Qué normas están constriñendo o habilitando la acción?"
        ]
    },
    "Samuel Huntington (Choque de Civilizaciones)": {
        "desc": "Conflictos de identidad cultural y religiosa.",
        "preguntas": [
            "Líneas de Falla: ¿Ocurre el conflicto en la frontera entre dos civilizaciones distintas?",
            "Núcleo Identitario: ¿Es el núcleo del conflicto la identidad religiosa o cultural?",
            "Síndrome del País Pariente (Kin-Country): ¿Están otros estados interviniendo por lealtad cultural/religiosa?",
            "Occidente vs El Resto: ¿Es una reacción contra la imposición de valores occidentales?"
        ]
    },

    # -------------------------------------------------------------------------
    # 🧠 TOMA DE DECISIONES Y ANÁLISIS ESTRATÉGICO
    # -------------------------------------------------------------------------
    "--- TOMA DE DECISIONES Y SEGURIDAD ---": { "desc": "", "preguntas": [] },

    "Graham Allison (Los 3 Modelos de Decisión)": {
        "desc": "Análisis de la crisis desde múltiples lentes (La Esencia de la Decisión).",
        "preguntas": [
            "Modelo I (Actor Racional): ¿Cuál es la opción lógica que maximiza beneficios y minimiza costos estratégicos?",
            "Modelo II (Proceso Organizacional): ¿Qué procedimientos estándar (SOPs) y rutinas limitan la flexibilidad del gobierno?",
            "Modelo III (Política Burocrática): ¿Qué agencias o individuos internos están luchando por el poder y cómo afecta esto la decisión final?"
        ]
    },
    "Barry Buzan (Seguridad Integral y Securitización)": {
        "desc": "Los 5 Sectores de Seguridad y la Teoría de la Securitización.",
        "preguntas": [
            "Análisis Multisectorial: Evalúa amenazas en los 5 sectores: Militar, Político, Económico, Societal y Ambiental.",
            "Nivel Sistémico: ¿Cómo influye la anarquía internacional o la polaridad en el conflicto?",
            "Nivel Estatal: ¿Qué presiones burocráticas o nacionales limitan al Estado?",
            "Nivel Individual: ¿El perfil psicológico de los líderes altera la toma de decisiones?",
            "Seguridad Societal: ¿Está amenazada la identidad colectiva (religión, etnia, cultura)?",
            "Actor Securitizador: ¿Quién está declarando el asunto como una 'amenaza existencial'?",
            "Objeto Referente: ¿Qué es exactamente lo que se intenta proteger (El Estado, la Nación, la Economía)?",
            "Medidas Extraordinarias: ¿Se está usando la retórica de seguridad para justificar acciones fuera de la política normal?"
        ]
    },
    "John Boyd (Ciclo OODA)": {
        "desc": "Velocidad de decisión en conflicto (Observar, Orientar, Decidir, Actuar).",
        "preguntas": [
            "Velocidad del Ciclo: ¿Quién está completando su ciclo OODA más rápido?",
            "Fase de Orientación: ¿Cómo los sesgos culturales y la herencia genética moldean la percepción del adversario?",
            "Colapso del Adversario: ¿Cómo podemos generar ambigüedad para aislar al enemigo de su entorno?"
        ]
    },

    # -------------------------------------------------------------------------
    # 🌪️ TEORÍA DE LA COMPLEJIDAD Y CAOS (DETECTAR LO INVISIBLE)
    # -------------------------------------------------------------------------
    "--- COMPLEJIDAD Y SEÑALES DÉBILES ---": { "desc": "", "preguntas": [] },

    "Análisis de Señales Débiles (Weak Signals)": {
        "desc": "Detección temprana del 'Efecto Mariposa' y anomalías marginales.",
        "preguntas": [
            "Detección de Ruido: Identifica datos, eventos o anécdotas marginales que los expertos están descartando como 'irrelevantes'.",
            "Patrón de Rareza: ¿Existe algún evento extraño que haya ocurrido más de una vez en contextos diferentes (coincidencia sospechosa)?",
            "Filtro de Amplificación: Si esta pequeña señal marginal creciera exponencialmente, ¿qué sistema colapsaría primero?",
            "Voz Disidente: Busca en el texto la opinión más impopular o ridícula y analízala como si fuera la única verdad."
        ]
    },
    "Ventana de Johari (Unknown Unknowns)": {
        "desc": "Exploración de puntos ciegos y vacíos ontológicos.",
        "preguntas": [
            "Unknown Unknowns (Desconocidos-Desconocidos): ¿Qué es lo que NI SIQUIERA sabemos que no sabemos sobre este tema?",
            "El Elefante en la Habitación: ¿Qué tema obvio está siendo sistemáticamente evitado u omitido en la información disponible?",
            "Sesgo de Espejo: ¿Estamos asumiendo que el adversario piensa como nosotros? Rompe esa asunción.",
            "Hipótesis Silenciosa: Genera una hipótesis basada en la ausencia de evidencia (lo que NO está pasando)."
        ]
    },
    "Análisis de Redes Ocultas (Rizoma)": {
        "desc": "Conexiones no lineales entre eventos dispares.",
        "preguntas": [
            "Mapeo de Vínculos Invisibles: Encuentra una conexión lógica entre dos eventos del texto que parezcan no tener relación alguna.",
            "Nodos Ocultos: ¿Existe un tercer actor o factor (no mencionado) que podría estar moviendo los hilos de ambos bandos?",
            "Efecto de Segundo y Tercer Orden: Si ocurre el evento principal, ¿qué efecto dominó inesperado ocurrirá en un sector ajeno (ej. impacto de una guerra en la moda o el clima)?",
            "Análisis de Casualidad: Convierte una 'casualidad' mencionada en el texto en una causalidad intencional. ¿Cómo cambia la historia?"
        ]
    },
    
    # -------------------------------------------------------------------------
    # 🛠️ TÉCNICAS ESTRUCTURADAS (SATs)
    # -------------------------------------------------------------------------
    "--- TÉCNICAS ESTRUCTURADAS (SATs) ---": { "desc": "", "preguntas": [] },

    "Análisis de Actores (Stakeholder Mapping)": {
        "desc": "Mapeo de intereses, poder y posturas.",
        "preguntas": [
            "Matriz Poder vs Interés: Clasifica a todos los actores relevantes.",
            "Identificación de Vetadores: ¿Quién tiene la capacidad de bloquear cualquier acuerdo?",
            "Aliados y Spoilers: ¿Quién gana con la resolución y quién gana con la continuación del conflicto?"
        ]
    },
    "Análisis Geopolítico (PMESII-PT)": {
        "desc": "Variables del entorno operativo: Político, Militar, Económico, Social, Info, Infraestructura, Físico, Tiempo.",
        "preguntas": ["Interacción Política-Militar.", "Vulnerabilidad de Infraestructura crítica.", "Impacto Social y Cultural.", "Desglose completo PMESII-PT."]
    },
    "Análisis DIME (Poder Nacional)": {
        "desc": "Diplomático, Informacional, Militar, Económico.",
        "preguntas": ["Capacidad de proyección Económica (Sanciones/Ayudas).", "Aislamiento o alianzas Diplomáticas.", "Guerra de Información y Narrativa.", "Capacidad Militar real vs disuasoria."]
    },
    "Análisis de Hipótesis en Competencia (ACH)": {
        "desc": "Matriz para evitar sesgos de confirmación.",
        "preguntas": [
            "Generación: Formula al menos 4 hipótesis exclusivas sobre lo que está ocurriendo.",
            "Diagnóstico: Identifica la evidencia que sea consistente con una hipótesis pero inconsistente con las otras.",
            "Engaño (Decepción): ¿Alguna evidencia podría haber sido plantada para engañarnos?"
        ]
    },
    "Abogado del Diablo": {
        "desc": "Pensamiento crítico.",
        "preguntas": ["Desafío frontal a la conclusión más probable.", "Defensa lógica de la postura 'irracional' del adversario."]
    },
    "Análisis de Cisne Negro (Nassim Taleb)": {
        "desc": "Eventos altamente improbables de impacto masivo.",
        "preguntas": [
            "Lo Impensable: Describe un evento 'imposible' que haría colapsar toda la estrategia actual.",
            "Fragilidad vs Antifragilidad: ¿El sistema se rompe con el estrés o se fortalece?",
            "Falacia Narrativa: ¿Estamos inventando una historia coherente para explicar datos que son puro azar?"
        ]
    },
    "Análisis FODA (SWOT) de Inteligencia": {
        "desc": "Enfoque estratégico ofensivo/defensivo.",
        "preguntas": [
            "Vulnerabilidades Críticas (Debilidades internas).",
            "Amenazas Inminentes (Externas).",
            "Estrategia de Supervivencia (Mini-Maxi): Minimizar debilidades para evitar amenazas.",
            "Ventana de Oportunidad: ¿Cómo usar las fortalezas actuales para explotar una oportunidad temporal?"
        ]
    },
    "Técnica de los 5 Porqués": {
        "desc": "Búsqueda de la Causa Raíz.",
        "preguntas": [
            "Define el problema visible.",
            "Pregunta 1: ¿Por qué ocurre esto?",
            "Pregunta 2: ¿Por qué ocurre lo anterior? (Repetir hasta 5 veces)",
            "Identifica la falla sistémica original, no el síntoma."
        ]
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
        "desc": "Selección y priorización de objetivos.",
        "preguntas": [
            "Criticidad: ¿Qué tan vital es este objetivo para la misión enemiga?",
            "Vulnerabilidad: ¿Qué tan fácil es atacarlo?",
            "Recuperabilidad: ¿Cuánto tiempo tardarían en reemplazarlo?",
            "Efecto: ¿Cuál es el impacto sistémico de su neutralización?"
        ]
    }
}

# ==========================================
# 📘 TEXTO DEL MANUAL (CONTENIDO ESTÁTICO)
# ==========================================
MANUAL_USUARIO = """
# 📘 MANUAL DE OPERACIONES | SISTEMA STRATINTEL

## 1. INTRODUCCIÓN
**StratIntel** es un Sistema de Soporte a la Decisión (DSS) diseñado para analistas de inteligencia.

## 2. VERSIONES DEL SISTEMA
* **🛡️ Versión Beta:** Solo documentos locales. Sin conexión externa.
* **🌐 Versión Master:** Conexión Web y YouTube (si está habilitada).

## 3. FLUJO DE TRABAJO
1. **Ingesta:** Suba sus PDFs, DOCXs o pegue texto en la pestaña correspondiente.
2. **Configuración:** Ingrese su API Key en el menú lateral.
3. **Misión:** Seleccione las técnicas de análisis (Ej: Realismo, Prospectiva).
4. **Profundidad:**
    * *Estratégico:* Resumen ejecutivo.
    * *Táctico:* Responde todas las preguntas.
    * *Operacional:* Selección manual de preguntas.

## 4. HERRAMIENTAS ESPECIALES
* **🎨 Visualización:** Genere mapas de actores al final del reporte.
* **🕵️ Contrainteligencia:** Cargue 2+ documentos y use la técnica "Triangulación" para hallar contradicciones.

## 5. EXPORTACIÓN
Use los botones al final para descargar el informe en Word o PDF.
"""

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

# --- FUNCIONES DE REPORTE ---
def limpiar_texto(t):
    if not t: return ""
    reps = {"✨": "", "🚀": "", "⚠️": "[!]", "✅": "[OK]", "🛡️": "", "🔒": "", "🎖️": "", "♟️": "", "⚖️": ""}
    for k,v in reps.items(): t = t.replace(k,v)
    return t.encode('latin-1', 'replace').decode('latin-1')

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'StratIntel Report V16', 0, 1, 'C')
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
    doc.add_heading('StratIntel Intelligence Report', 0)
    doc.add_paragraph(f"Fuente: {fuente}").bold = True
    doc.add_paragraph(f"Técnicas: {tecnicas}").bold = True
    for l in texto.split('\n'):
        if l.startswith('#'): doc.add_heading(l.replace('#','').strip(), level=2)
        else: doc.add_paragraph(l)
    
    aviso = doc.add_paragraph()
    aviso.add_run("\n\n------------------\nAVISO: Generado por IA. Verificar datos.").font.size = 8
    b = BytesIO(); doc.save(b); b.seek(0)
    return b

# --- INTERFAZ ---
st.sidebar.title("♟️ StratIntel")
st.sidebar.caption("Master Edition | Ops Mode")
st.sidebar.markdown("---")

if API_KEY_FIJA:
    st.session_state['api_key'] = API_KEY_FIJA
    genai.configure(api_key=API_KEY_FIJA)
    st.sidebar.success(f"✅ Conectado ({MODELO_ACTUAL})")
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
st.markdown("**Sistema de Inteligencia Estratégica (DSS)**")

# CARGA
t1, t2, t3, t_ayuda = st.tabs(["📂 PDFs", "📝 DOCXs", "✍️ Manual", "ℹ️ Ayuda"])
with t1:
    f = st.file_uploader("PDFs", type="pdf", accept_multiple_files=True)
    if f and st.button("Procesar PDF"):
        t, n = procesar_archivos_pdf(f); st.session_state['texto_analisis']=t; st.session_state['origen_dato']=f"PDFs: {n}"; st.success(f"✅ {len(f)}")
with t2:
    f = st.file_uploader("DOCXs", type="docx", accept_multiple_files=True)
    if f and st.button("Procesar DOCX"):
        t, n = procesar_archivos_docx(f); st.session_state['texto_analisis']=t; st.session_state['origen_dato']=f"DOCXs: {n}"; st.success(f"✅ {len(f)}")
with t3:
    m = st.text_area("Manual")
    if st.button("Fijar"): st.session_state['texto_analisis']=m; st.session_state['origen_dato']="Manual"; st.success("OK")

with t_ayuda:
    st.markdown(MANUAL_USUARIO)
    
    # Botón para descargar el Manual en PDF (Generado al vuelo)
    st.markdown("---")
    if st.button("💾 Descargar Manual en PDF"):
        # Usamos tu misma función de crear_pdf
        pdf_bytes = crear_pdf(MANUAL_USUARIO, "Documentación Oficial", "Sistema StratIntel")
        st.download_button(
            label="Confirmar Descarga",
            data=bytes(pdf_bytes),
            file_name="Manual_Operaciones_StratIntel.pdf",
            mime="application/pdf")

st.markdown("---")
if st.session_state['texto_analisis']:
    with st.expander(f"Fuente Activa: {st.session_state['origen_dato']}"): st.write(st.session_state['texto_analisis'][:1000])

# EJECUCIÓN
st.header("Generación de Informe")

if not st.session_state['api_key'] or not st.session_state['texto_analisis']:
    st.warning("⚠️ Carga datos para comenzar.")
else:
    c1, c2 = st.columns([1, 2])
    with c1:
        if not tecnicas_seleccionadas: st.info("👈 Selecciona técnicas.")
        
        # --- SELECTOR DE PROFUNDIDAD CON MODO OPERACIONAL ---
        profundidad = st.radio(
            "Nivel de Profundidad:", 
            ["🔍 Estratégico (Resumen)", "🎯 Táctico (Todas las preguntas)", "⚙️ Operacional (Selección Específica)"],
            help="Estratégico: Visión general. Táctico: Todas las preguntas del marco. Operacional: Selecciona preguntas manualmente."
        )
        
        # --- LÓGICA DE SELECCIÓN MANUAL (OPERACIONAL) ---
        preguntas_manuales = {}
        if "Operacional" in profundidad and tecnicas_seleccionadas:
            st.info("👇 Selecciona los vectores de análisis:")
            for tec in tecnicas_seleccionadas:
                # Obtenemos las preguntas de TU base de datos exacta
                qs = DB_CONOCIMIENTO.get(tec, {}).get("preguntas", [])
                if qs:
                    sel = st.multiselect(f"Preguntas para {tec}:", qs)
                    preguntas_manuales[tec] = sel
                else:
                    st.warning(f"{tec} no tiene preguntas predefinidas.")
        
        pir = st.text_area("PIR (Opcional):", height=100)

    with c2:
        if st.button("🚀 EJECUTAR MISIÓN", type="primary", use_container_width=True, disabled=len(tecnicas_seleccionadas)==0):
            try:
                genai.configure(api_key=st.session_state['api_key'])
                model = genai.GenerativeModel(MODELO_ACTUAL)
                ctx = st.session_state['texto_analisis']
                         
                # BUCLE DE ANÁLISIS
                informe_final = f"# INFORME\nFECHA: {datetime.datetime.now().strftime('%d/%m/%Y')}\nFUENTE: {st.session_state['origen_dato']}\n\n"
                progreso = st.progress(0)
                
                for i, tec in enumerate(tecnicas_seleccionadas):
                    st.caption(f"Analizando: {tec}...")
                    
                    # LÓGICA DE INYECCIÓN DE PREGUNTAS
                    instruccion_preguntas = ""
                    
                    if "Táctico" in profundidad:
                        qs = DB_CONOCIMIENTO.get(tec, {}).get("preguntas", [])
                        if qs:
                            lista = "\n".join([f"- {p}" for p in qs])
                            instruccion_preguntas = f"\n\nOBLIGATORIO: Responde DETALLADAMENTE a TODAS estas preguntas del marco teórico:\n{lista}"
                        else:
                            instruccion_preguntas = "\n\nINSTRUCCIÓN: Realiza un análisis táctico detallado."

                    elif "Operacional" in profundidad:
                        qs_selec = preguntas_manuales.get(tec, [])
                        if qs_selec:
                            lista = "\n".join([f"- {p}" for p in qs_selec])
                            instruccion_preguntas = f"\n\nOBLIGATORIO: Centra el análisis EXCLUSIVAMENTE en responder estas preguntas seleccionadas:\n{lista}"
                        else:
                            instruccion_preguntas = "\n\n(NOTA: El usuario no seleccionó preguntas específicas. Realiza un análisis general de la técnica)."

                    else: # Estratégico
                        instruccion_preguntas = "\n\nINSTRUCCIÓN: Realiza un análisis estratégico general, fluido y ejecutivo (Resumen Global)."

                    prompt = f"""
                    ACTÚA COMO: Analista de Inteligencia Senior y Experto en Relaciones Internacionales.
                    METODOLOGÍA: {tec}
                    PIR (Requerimiento de Inteligencia): {pir}
                    
                    {instruccion_preguntas}
                    
                    CONTEXTO DOCUMENTAL:
                    {ctx}
                                        
                    FORMATO: Académico, riguroso, citar fuentes del texto.
                    """
                    
                    # RETRY LOGIC
                    intentos = 0
                    exito = False
                    while intentos < 3 and not exito:
                        try:
                            res = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=temp))
                            informe_final += f"\n\n## 📌 {tec}\n{res.text}\n\n---\n"
                            exito = True
                        except Exception as e:
                            if "429" in str(e):
                                st.warning(f"⚠️ Tráfico alto (429). Esperando 30s... (Intento {intentos+1})")
                                time.sleep(30)
                                intentos += 1
                            else:
                                st.error(f"Error: {e}")
                                break

                    progreso.progress((i + 1) / len(tecnicas_seleccionadas))
                    time.sleep(5) 
                
                st.session_state['res'] = informe_final
                st.session_state['tecnicas_usadas'] = ", ".join(tecnicas_seleccionadas)
                st.success("✅ Misión Completada")
                st.markdown(informe_final)

            except Exception as e: st.error(f"Error: {e}")

if 'res' in st.session_state:
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.download_button("Descargar Word", crear_word(st.session_state['res'], st.session_state['tecnicas_usadas'], st.session_state['origen_dato']), "Reporte.docx")
    try: c2.download_button("Descargar PDF", bytes(crear_pdf(st.session_state['res'], st.session_state['tecnicas_usadas'], st.session_state['origen_dato'])), "Reporte.pdf")
    except: pass








