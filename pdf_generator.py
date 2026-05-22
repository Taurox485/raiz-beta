"""
pdf_generator.py — Generación de PDFs de cierre para rAÍz

Genera dos PDFs al detectar [FIN_CONSEJERIA]:
  - PDF Estudiante: "Mi Mapa rAÍz" — cálido, motivacional, para llevar a casa
  - PDF Orientador: "Ficha de Acompañamiento" — profesional, basado en evidencia

Flujo:
  1. _extraer_datos_estudiante() / _extraer_datos_orientador()
     → Llamada a Gemini con el historial completo → dict estructurado
  2. _render_pdf_estudiante() / _render_pdf_orientador()
     → fpdf2 dibuja el PDF con diseño visual → bytes

API pública:
  generar_pdfs(estudiante, historial, client, model, system_instruction)
  → tuple[bytes, bytes]  (pdf_estudiante, pdf_orientador)
"""

import json
import re
from datetime import datetime
from io import BytesIO

import streamlit as st
from fpdf import FPDF
from google.genai import types

# ── Paleta de colores (del poster de rAÍz) ────────────────────────────────────
VERDE_OSCURO  = (45,  80,  22)   # #2D5016 — headers, títulos
VERDE_MEDIO   = (74, 124,  47)   # #4A7C2F — acentos, bullets
OCRE          = (200, 150,  12)  # #C8960C — highlights
CREMA         = (245, 240, 232)  # #F5F0E8 — fondos alternos
BLANCO        = (255, 255, 255)
GRIS_TEXTO    = (51,  51,  51)   # #333333
GRIS_CLARO    = (180, 180, 180)
ROJO_RIESGO   = (200,  60,  60)
AMARILLO_RIESGO = (220, 160,  20)
VERDE_RIESGO  = (60, 160,  60)


# ══════════════════════════════════════════════════════════════════════════════
# PASO 1 — Extracción estructurada vía Gemini
# ══════════════════════════════════════════════════════════════════════════════

def _historial_a_texto(historial: list[dict]) -> str:
    """Convierte mensajes de DB a texto plano para el prompt de síntesis."""
    lineas = []
    for msg in historial:
        rol = "rAÍz" if msg["rol"] == "model" else "Estudiante"
        lineas.append(f"[{rol}]: {msg['contenido']}")
    return "\n".join(lineas)


def _llamar_gemini_json(
    prompt: str,
    client,
    model: str,
    system: str,
    intentos: int = 3,
) -> dict:
    """
    Llama a Gemini y extrae JSON de la respuesta.
    Reintenta hasta `intentos` veces si falla el parseo.
    """
    for intento in range(intentos):
        try:
            resp = client.models.generate_content(
                model=model,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.3,
                ),
                contents=prompt,
            )
            texto = resp.text.strip()
            # Limpiar posibles bloques markdown ```json ... ```
            texto = re.sub(r"^```json\s*", "", texto)
            texto = re.sub(r"\s*```$", "", texto)
            return json.loads(texto)
        except Exception as e:
            if intento == intentos - 1:
                raise RuntimeError(
                    f"No se pudo obtener JSON de Gemini tras {intentos} intentos: {e}"
                )
    return {}


def _extraer_datos_estudiante(
    historial_texto: str,
    nombre: str,
    client,
    model: str,
) -> dict:
    system = (
        "Eres un extractor de datos estructurados. "
        "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
        "sin bloques de código markdown, sin explicaciones."
    )

    prompt = f"""Analiza esta conversación de orientación vocacional entre rAÍz (IA) y un estudiante colombiano de grado 9°.

CONVERSACIÓN:
{historial_texto}

Extrae la siguiente información y devuelve SOLO este JSON (sin texto adicional):

{{
  "tipo_holland": "Una de estas letras o combinación: R (Realista), I (Investigador), A (Artístico), S (Social), E (Emprendedor), C (Convencional). Máx 2 letras.",
  "nombre_explorador": "Nombre creativo y motivador para el tipo Holland en español colombiano coloquial. Ej: 'El Constructor de Ideas', 'La Mente Curiosa'. Máx 5 palabras.",
  "descripcion_holland": "Descripción de 2-3 oraciones del perfil en lenguaje cálido y cercano, sin jerga técnica, usando 'tú'. Basada en lo que dijo el estudiante.",
  "fortalezas": ["Fortaleza concreta 1", "Fortaleza concreta 2", "Fortaleza concreta 3", "Fortaleza concreta 4"],
  "frase_clave": "La frase más poderosa o reveladora que dijo el estudiante durante la conversación. Citar textualmente si es posible.",
  "misiones_completadas": ["Descripción breve misión 1", "Descripción breve misión 2", "Descripción breve misión 3"],
  "nudges": [
    "Invitación de comportamiento concreta 1, empezando con un verbo. Ej: 'Busca un espacio esta semana para...'",
    "Invitación de comportamiento concreta 2",
    "Invitación de comportamiento concreta 3"
  ],
  "mensaje_cierre": "Mensaje cálido y empoderador de rAÍz al estudiante. 3-4 oraciones. Tono: mentor joven que cree en él/ella. En español colombiano cercano."
}}

Nombre del estudiante: {nombre}
IMPORTANTE: Solo JSON, nada más."""

    return _llamar_gemini_json(prompt, client, model, system)


def _extraer_datos_orientador(
    historial_texto: str,
    estudiante: dict,
    client,
    model: str,
) -> dict:
    system = (
        "Eres un extractor de datos estructurados para reportes pedagógicos. "
        "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
        "sin bloques de código markdown, sin explicaciones."
    )

    nivel_riesgo_db = estudiante.get("perfil_riesgo", "sin_evaluar")

    prompt = f"""Analiza esta conversación de orientación entre rAÍz (IA) y un estudiante de grado 9° en el Valle del Cauca, Colombia.

CONVERSACIÓN:
{historial_texto}

DATOS DEL ESTUDIANTE:
- Nivel de riesgo detectado por el sistema: {nivel_riesgo_db}
- Grado: {estudiante.get('grado', 9)}

Extrae información para el reporte del docente orientador. Devuelve SOLO este JSON:

{{
  "tipo_holland": "Letras Holland identificadas (máx 2). Ej: RS, IA, SE",
  "descripcion_holland_tecnica": "Descripción técnica del perfil Holland en 2 oraciones. Para docente, puede usar terminología pedagógica.",
  "intereses_dominantes": ["Área de interés 1", "Área de interés 2", "Área de interés 3"],
  "nivel_riesgo": "{nivel_riesgo_db}",
  "indicadores_riesgo": ["Indicador observado 1 (sin datos personales sensibles)", "Indicador observado 2", "Indicador observado 3"],
  "factores_protectores": ["Factor protector 1", "Factor protector 2"],
  "recomendaciones_orientador": [
    "Acción concreta recomendada al docente orientador 1",
    "Acción concreta recomendada al docente orientador 2",
    "Acción concreta recomendada al docente orientador 3"
  ],
  "recomendaciones_docentes_area": [
    "Estrategia de aula basada en el perfil Holland de este estudiante 1",
    "Estrategia de aula basada en el perfil Holland de este estudiante 2"
  ],
  "capsula_neurociencias": "Párrafo de 4-5 oraciones sobre lo que la neurociencia y la psicología educativa dice sobre estudiantes con este perfil Holland y nivel socioeconómico similar. Citar evidencia general (no inventar estudios específicos). Orientado a transformar prácticas docentes. Tono: educativo pero accesible."
}}

IMPORTANTE: No incluyas datos familiares sensibles, situaciones económicas específicas ni información que pueda identificar negativamente al estudiante. Solo JSON, nada más."""

    return _llamar_gemini_json(prompt, client, model, system)


# ══════════════════════════════════════════════════════════════════════════════
# PASO 2 — Renderizado con fpdf2
# ══════════════════════════════════════════════════════════════════════════════

class PDFBase(FPDF):
    """Clase base con utilidades compartidas."""

    _LATIN1_MAP = {
        "—": "-",    # em dash
        "–": "-",    # en dash
        "‘": "'",    # comilla izquierda simple
        "’": "'",    # comilla derecha simple
        "“": '"',    # comilla izquierda doble
        "”": '"',    # comilla derecha doble
        "•": "-",    # bullet
        "…": "...",  # elipsis
        "→": "->",   # flecha derecha
        "←": "<-",   # flecha izquierda
        "✓": "+",    # check mark
        "✔": "+",    # heavy check mark
        "·": "-",    # middle dot
    }

    def normalize_text(self, text: str) -> str:
        for src, dst in self._LATIN1_MAP.items():
            text = text.replace(src, dst)
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def set_color_fill(self, rgb: tuple):
        self.set_fill_color(*rgb)

    def set_color_text(self, rgb: tuple):
        self.set_text_color(*rgb)

    def set_color_draw(self, rgb: tuple):
        self.set_draw_color(*rgb)

    def linea_divisora(self, color=VERDE_MEDIO, grosor=0.4):
        self.set_color_draw(color)
        self.set_line_width(grosor)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def titulo_seccion(self, texto: str):
        self.set_font("Helvetica", "B", 9)
        self.set_color_text(VERDE_OSCURO)
        self.cell(0, 6, texto.upper(), ln=True)
        self.linea_divisora()
        self.set_color_text(GRIS_TEXTO)

    def caja_destacada(self, texto: str, ancho: float = 0):
        if ancho == 0:
            ancho = self.w - self.l_margin - self.r_margin
        self.set_color_fill(CREMA)
        self.set_color_draw(OCRE)
        self.set_line_width(0.5)
        x = self.get_x()
        y = self.get_y()
        # Calcular altura necesaria
        self.set_font("Helvetica", "I", 9)
        lines = self.multi_cell(ancho - 8, 5, texto, dry_run=True, output="LINES")
        altura = len(lines) * 5 + 8
        self.rect(x, y, ancho, altura, style="FD")
        self.set_xy(x + 4, y + 4)
        self.set_color_text(GRIS_TEXTO)
        self.multi_cell(ancho - 8, 5, texto)
        self.set_xy(x, y + altura + 2)

    def bullet_item(self, texto: str, simbolo: str = "•", indent: float = 4):
        self.set_font("Helvetica", "B", 9)
        self.set_color_text(VERDE_MEDIO)
        self.cell(indent + 4, 5, simbolo)
        self.set_font("Helvetica", "", 9)
        self.set_color_text(GRIS_TEXTO)
        ancho = self.w - self.l_margin - self.r_margin - indent - 4
        self.multi_cell(ancho, 5, texto)


# ── PDF ESTUDIANTE ─────────────────────────────────────────────────────────────

def _render_pdf_estudiante(datos: dict, estudiante: dict) -> bytes:
    pdf = PDFBase(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    ancho_util = pdf.w - 30  # 180mm para A4 con márgenes 15

    # ── HEADER ────────────────────────────────────────────────────────────────
    pdf.set_color_fill(VERDE_OSCURO)
    pdf.rect(0, 0, pdf.w, 32, style="F")

    pdf.set_xy(15, 6)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_color_text(BLANCO)
    pdf.cell(0, 8, "Mi Mapa rAIz", ln=True)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 10)
    nombre_completo = f"{estudiante.get('nombre', '')} {estudiante.get('apellido', '')}"
    fecha = datetime.now().strftime("%B %Y")
    pdf.cell(0, 5, f"{nombre_completo}  |  Grado {estudiante.get('grado', 9)}  |  {fecha}", ln=True)

    pdf.set_xy(15, 35)
    pdf.set_color_text(GRIS_TEXTO)

    # ── FILA 1: dos columnas ──────────────────────────────────────────────────
    ancho_izq = ancho_util * 0.57
    ancho_der = ancho_util * 0.40
    gap = ancho_util * 0.03
    x_izq = pdf.l_margin
    x_der = x_izq + ancho_izq + gap
    y_inicio_col = pdf.get_y() + 4

    # Columna izquierda — Tipo de explorador
    pdf.set_xy(x_izq, y_inicio_col)
    pdf.titulo_seccion("Tu tipo de explorador")

    pdf.set_xy(x_izq, pdf.get_y())
    pdf.set_color_fill(OCRE)
    pdf.set_color_text(BLANCO)
    pdf.set_font("Helvetica", "B", 11)
    nombre_explorador = datos.get("nombre_explorador", "Explorador")
    pdf.cell(ancho_izq, 8, f"  {nombre_explorador}", fill=True, ln=True)
    pdf.ln(2)

    pdf.set_xy(x_izq, pdf.get_y())
    pdf.set_font("Helvetica", "", 9)
    pdf.set_color_text(GRIS_TEXTO)
    pdf.multi_cell(ancho_izq, 5, datos.get("descripcion_holland", ""))

    y_tras_izq = pdf.get_y()

    # Columna derecha — Fortalezas
    pdf.set_xy(x_der, y_inicio_col)
    pdf.titulo_seccion("Tus fortalezas")
    y_tras_titulo_der = pdf.get_y()

    for f in datos.get("fortalezas", []):
        pdf.set_xy(x_der, pdf.get_y())
        # Mini bullet con fondo crema
        pdf.set_color_fill(CREMA)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_color_text(VERDE_MEDIO)
        pdf.cell(4, 5, "")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_color_text(GRIS_TEXTO)
        lines = pdf.multi_cell(ancho_der - 4, 5, f"+ {f}", dry_run=True, output="LINES")
        pdf.multi_cell(ancho_der, 5, f"+ {f}")
        pdf.set_x(x_der)

    y_tras_der = pdf.get_y()
    pdf.set_y(max(y_tras_izq, y_tras_der) + 4)

    pdf.linea_divisora(color=GRIS_CLARO, grosor=0.2)

    # ── FRASE CLAVE ───────────────────────────────────────────────────────────
    pdf.ln(2)
    pdf.titulo_seccion("Lo que tú mismo dijiste")
    frase = datos.get("frase_clave", "")
    if frase:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_color_text(VERDE_OSCURO)
        pdf.multi_cell(0, 6, f'"{frase}"')
        pdf.ln(2)
    pdf.set_color_text(GRIS_TEXTO)

    pdf.linea_divisora(color=GRIS_CLARO, grosor=0.2)
    pdf.ln(2)

    # ── FILA 2: dos columnas ──────────────────────────────────────────────────
    y_fila2 = pdf.get_y()

    # Columna izquierda — Misiones
    pdf.set_xy(x_izq, y_fila2)
    pdf.titulo_seccion("Misiones que completaste")
    for m in datos.get("misiones_completadas", []):
        pdf.set_xy(x_izq, pdf.get_y())
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_color_text(VERDE_MEDIO)
        pdf.cell(6, 5, "+")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(ancho_izq - 6, 5, m)
        pdf.set_x(x_izq)
    y_tras_misiones = pdf.get_y()

    # Columna derecha — Nudges
    pdf.set_xy(x_der, y_fila2)
    pdf.titulo_seccion("Para seguir creciendo")
    for n in datos.get("nudges", []):
        pdf.set_xy(x_der, pdf.get_y())
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_color_text(OCRE)
        pdf.cell(6, 5, "->")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(ancho_der - 6, 5, n)
        pdf.set_x(x_der)
    y_tras_nudges = pdf.get_y()

    pdf.set_y(max(y_tras_misiones, y_tras_nudges) + 4)

    # ── MENSAJE DE CIERRE ─────────────────────────────────────────────────────
    pdf.set_color_fill((230, 242, 224))  # verde muy claro
    y_cierre = pdf.get_y()
    mensaje = datos.get("mensaje_cierre", "")
    pdf.set_font("Helvetica", "", 9)
    lines = pdf.multi_cell(ancho_util, 5, mensaje, dry_run=True, output="LINES")
    altura_cierre = len(lines) * 5 + 10
    pdf.rect(pdf.l_margin, y_cierre, ancho_util, altura_cierre, style="F")
    pdf.set_xy(pdf.l_margin + 4, y_cierre + 5)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(ancho_util - 8, 5, mensaje)

    pdf.set_y(y_cierre + altura_cierre + 3)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    pdf.set_color_fill(VERDE_OSCURO)
    pdf.rect(0, pdf.h - 12, pdf.w, 12, style="F")
    pdf.set_xy(15, pdf.h - 9)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_color_text(BLANCO)
    pdf.cell(
        0, 5,
        "Este perfil es tuyo. Guardalo, compártelo con quien confíes y usalo para seguir construyendo tu proyecto de vida.",
        align="C",
    )

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ── PDF ORIENTADOR ─────────────────────────────────────────────────────────────

def _render_pdf_orientador(datos: dict, estudiante: dict) -> bytes:
    pdf = PDFBase(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    ancho_util = pdf.w - 30

    # ── HEADER ────────────────────────────────────────────────────────────────
    pdf.set_color_fill(VERDE_OSCURO)
    pdf.rect(0, 0, pdf.w, 28, style="F")

    pdf.set_xy(15, 5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_color_text(BLANCO)
    pdf.cell(0, 7, "Ficha de Acompanamiento Pedagogico rAIz", ln=True)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 8)
    nombre = f"{estudiante.get('nombre', '')} {estudiante.get('apellido', '')}"
    est_id = estudiante.get("estudiante_id", "")
    fecha = datetime.now().strftime("%d/%m/%Y")
    pdf.cell(
        0, 5,
        f"Estudiante: {nombre}  |  ID: {est_id}  |  Grado {estudiante.get('grado', 9)}  |  Generado: {fecha}",
        ln=True,
    )

    pdf.set_xy(15, 32)
    pdf.set_color_text(GRIS_TEXTO)

    ancho_izq = ancho_util * 0.57
    ancho_der = ancho_util * 0.40
    gap = ancho_util * 0.03
    x_izq = pdf.l_margin
    x_der = x_izq + ancho_izq + gap
    y_inicio = pdf.get_y() + 3

    # ── FILA 1: Perfil Holland | Nivel de riesgo ──────────────────────────────

    # Columna izquierda — Perfil Holland
    pdf.set_xy(x_izq, y_inicio)
    pdf.titulo_seccion("Perfil de Exploracion")

    tipo = datos.get("tipo_holland", "NE")
    pdf.set_xy(x_izq, pdf.get_y())
    pdf.set_color_fill(VERDE_OSCURO)
    pdf.set_color_text(BLANCO)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(14, 10, tipo, fill=True, align="C")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.set_x(x_izq + 16)
    pdf.cell(ancho_izq - 16, 10, "Tipo Holland identificado", ln=True)

    pdf.set_xy(x_izq, pdf.get_y() + 1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_color_text(GRIS_TEXTO)
    pdf.multi_cell(ancho_izq, 5, datos.get("descripcion_holland_tecnica", ""))

    pdf.ln(2)
    pdf.set_xy(x_izq, pdf.get_y())
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.cell(ancho_izq, 4, "Areas de interes dominantes:", ln=True)
    pdf.set_x(x_izq)
    for interes in datos.get("intereses_dominantes", []):
        pdf.set_xy(x_izq, pdf.get_y())
        pdf.set_font("Helvetica", "", 8)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(ancho_izq, 4, f"  • {interes}")
        pdf.set_x(x_izq)

    y_tras_izq = pdf.get_y()

    # Columna derecha — Semáforo de riesgo
    pdf.set_xy(x_der, y_inicio)
    pdf.titulo_seccion("Nivel de Riesgo de Desercion")

    nivel = datos.get("nivel_riesgo", "sin_evaluar").lower()
    color_semaforo = {
        "alto":  ROJO_RIESGO,
        "medio": AMARILLO_RIESGO,
        "bajo":  VERDE_RIESGO,
    }.get(nivel, GRIS_CLARO)

    label_nivel = {
        "alto":  "ALTO",
        "medio": "MEDIO",
        "bajo":  "BAJO",
    }.get(nivel, "SIN EVALUAR")

    # Círculo de semáforo (usando rect redondeado simulado)
    cx = x_der + 10
    cy = pdf.get_y() + 5
    pdf.set_color_fill(color_semaforo)
    pdf.ellipse(cx, cy, 16, 10, style="F")
    pdf.set_xy(x_der, cy - 1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(BLANCO)
    pdf.cell(36, 10, label_nivel, align="C")
    pdf.ln(2)

    pdf.set_xy(x_der, cy + 12)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.cell(ancho_der, 4, "Indicadores observados:", ln=True)
    pdf.set_x(x_der)
    for ind in datos.get("indicadores_riesgo", []):
        pdf.set_xy(x_der, pdf.get_y())
        pdf.set_font("Helvetica", "", 8)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(ancho_der, 4, f"  - {ind}")
        pdf.set_x(x_der)

    pdf.ln(1)
    pdf.set_xy(x_der, pdf.get_y())
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.cell(ancho_der, 4, "Factores protectores:", ln=True)
    pdf.set_x(x_der)
    for fp in datos.get("factores_protectores", []):
        pdf.set_xy(x_der, pdf.get_y())
        pdf.set_font("Helvetica", "", 8)
        pdf.set_color_text(VERDE_MEDIO)
        pdf.multi_cell(ancho_der, 4, f"  + {fp}")
        pdf.set_x(x_der)

    y_tras_der = pdf.get_y()
    pdf.set_y(max(y_tras_izq, y_tras_der) + 4)
    pdf.linea_divisora(color=GRIS_CLARO, grosor=0.2)

    # ── RECOMENDACIONES PEDAGÓGICAS ───────────────────────────────────────────
    pdf.ln(2)
    pdf.titulo_seccion("Recomendaciones Pedagogicas")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.cell(0, 5, "Para el docente orientador:", ln=True)
    for r in datos.get("recomendaciones_orientador", []):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(0, 4, f"  -> {r}")

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_color_text(VERDE_OSCURO)
    pdf.cell(0, 5, "Para docentes de area (estrategias de aula):", ln=True)
    for r in datos.get("recomendaciones_docentes_area", []):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(0, 4, f"  -> {r}")

    pdf.ln(3)
    pdf.linea_divisora(color=GRIS_CLARO, grosor=0.2)

    # ── CÁPSULA DE NEUROCIENCIAS ──────────────────────────────────────────────
    pdf.ln(2)
    pdf.titulo_seccion("Capsula de Neurociencias y Evidencia Educativa")

    capsula = datos.get("capsula_neurociencias", "")
    if capsula:
        y_cap = pdf.get_y()
        pdf.set_font("Helvetica", "", 8)
        lines = pdf.multi_cell(ancho_util - 8, 4.5, capsula, dry_run=True, output="LINES")
        altura_cap = len(lines) * 4.5 + 8
        pdf.set_color_fill(CREMA)
        pdf.set_color_draw(VERDE_MEDIO)
        pdf.set_line_width(0.3)
        pdf.rect(pdf.l_margin, y_cap, ancho_util, altura_cap, style="FD")
        pdf.set_xy(pdf.l_margin + 4, y_cap + 4)
        pdf.set_color_text(GRIS_TEXTO)
        pdf.multi_cell(ancho_util - 8, 4.5, capsula)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    pdf.set_color_fill(VERDE_OSCURO)
    pdf.rect(0, pdf.h - 14, pdf.w, 14, style="F")
    pdf.set_xy(15, pdf.h - 11)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_color_text(OCRE)
    pdf.cell(0, 4, "CONFIDENCIAL — Uso exclusivo del equipo docente.", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_color_text(BLANCO)
    pdf.cell(
        0, 4,
        f"Generado por rAIz | ID: {estudiante.get('estudiante_id', '')} | "
        f"Este reporte no incluye informacion personal sensible del estudiante.",
    )

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ══════════════════════════════════════════════════════════════════════════════

def generar_pdfs(
    estudiante: dict,
    historial: list[dict],
    client,
    model: str,
    system_instruction: str,
) -> tuple[bytes, bytes]:
    """
    Genera ambos PDFs a partir del historial completo de la mentoría.

    Args:
        estudiante: dict completo del estudiante (de DB)
        historial:  lista de mensajes tal como los devuelve db.get_historial()
        client:     instancia del cliente Gemini (ya inicializado en app.py)
        model:      nombre del modelo (ej. "gemini-2.5-flash")
        system_instruction: system prompt de rAÍz (para contexto en extracción)

    Returns:
        (pdf_estudiante_bytes, pdf_orientador_bytes)
    """
    historial_texto = _historial_a_texto(historial)
    nombre = f"{estudiante.get('nombre', '')} {estudiante.get('apellido', '')}".strip()

    datos_est = _extraer_datos_estudiante(
        historial_texto, nombre, client, model
    )
    datos_ori = _extraer_datos_orientador(
        historial_texto, estudiante, client, model
    )

    pdf_est = _render_pdf_estudiante(datos_est, estudiante)
    pdf_ori = _render_pdf_orientador(datos_ori, estudiante)

    return pdf_est, pdf_ori
