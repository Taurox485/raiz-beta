"""
pdf_generator.py — Generación de PDFs de cierre para rAÍz

Genera dos PDFs al detectar [FIN_CONSEJERIA]:
  - PDF Estudiante: "Mi Mapa rAÍz" — cálido, motivacional, para llevar a casa
  - PDF Orientador: "Ficha de Acompañamiento" — profesional, basado en evidencia

Flujo:
  1. _extraer_datos_estudiante() / _extraer_datos_orientador()
     → Llamada a Gemini con el historial completo → dict estructurado
  2. _renderizar_plantilla()
     → Jinja2 rellena la plantilla HTML con los datos
  3. _html_a_pdf()
     → Playwright convierte el HTML a PDF bytes

API pública:
  generar_pdfs(estudiante, historial, client, model, system_instruction)
  → tuple[bytes, bytes]  (pdf_estudiante, pdf_orientador)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from google.genai import types
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

import database as db

TEMPLATES_DIR = Path(__file__).parent / "templates"

DISCLAIMER_ESTUDIANTE = (
    "<strong>Este documento es tuyo.</strong> Fue generado por rAÍz, "
    "una inteligencia artificial, a partir de las conversaciones que tuviste "
    "durante tu proceso de mentoría. Es una síntesis de lo que tú mismo/a contaste: "
    "no reemplaza ninguna evaluación psicológica ni orientación profesional. "
    "Guardalo, compártelo con quien confíes y usalo para seguir construyendo "
    "tu proyecto de vida. Si querés que borremos tu información, podés "
    "pedírselo a tu orientador/a."
)

DISCLAIMER_ORIENTADOR = (
    "<strong>Documento confidencial — uso exclusivo del equipo docente.</strong> "
    "Generado por rAÍz (IA) a partir del diálogo con el estudiante. "
    "Esta síntesis no reemplaza la valoración profesional del orientador/a ni del "
    "psicólogo/a escolar. Los niveles de riesgo son indicadores de seguimiento, "
    "no diagnósticos clínicos. Tratamiento de datos sujeto a la Ley 1581/2012 "
    "(Habeas Data, Colombia). No compartir fuera del equipo docente."
)

PIE = "rAÍz · Mentoría de proyecto de vida · Piloto Valle del Cauca 2026"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════════════════════

def _historial_a_texto(historial: list[dict]) -> str:
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
            texto = re.sub(r"^```json\s*", "", texto)
            texto = re.sub(r"\s*```$", "", texto)
            return json.loads(texto)
        except Exception as e:
            if intento == intentos - 1:
                raise RuntimeError(
                    f"No se pudo obtener JSON de Gemini tras {intentos} intentos: {e}"
                )
    return {}


def _html_a_pdf(html_content: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "0mm",
                "bottom": "0mm",
                "left": "0mm",
                "right": "0mm",
            }
        )
        browser.close()
    return pdf_bytes


def _renderizar_plantilla(nombre_template: str, contexto: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )
    template = env.get_template(nombre_template)
    return template.render(**contexto)


# ══════════════════════════════════════════════════════════════════════════════
# Extracción de datos vía Gemini
# ══════════════════════════════════════════════════════════════════════════════

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

Extrae la siguiente información y devuelve SOLO este JSON:

{{
  "cuadrante_nombre": "Nombre del cuadrante Holland dominante en español. Ej: 'El Creador', 'El Explorador Social', 'El Investigador'. Máx 4 palabras.",
  "cuadrante_icono": "Un solo emoji que represente visualmente este cuadrante. Ej: 🎨 artístico, 🔬 investigador, 🤝 social, 🛠️ realista, 💼 emprendedor, 📋 convencional.",
  "cuadrante_descripcion": "Descripción cálida y cercana del perfil en 2-3 oraciones, en español colombiano, usando 'vos' o 'tú'. Sin jerga técnica.",
  "fortalezas": [
    {{"nombre": "Nombre corto de la fortaleza (2-4 palabras)", "evidencia": "Una oración de lo que el estudiante dijo o demostró que evidencia esta fortaleza."}},
    {{"nombre": "Fortaleza 2", "evidencia": "Evidencia 2"}},
    {{"nombre": "Fortaleza 3", "evidencia": "Evidencia 3"}}
  ],
  "valor_central": "El valor más importante que guía a este estudiante. Una palabra o frase corta. Ej: 'Familia', 'Crear cosas nuevas', 'Ayudar a otros'.",
  "valor_icono": "Emoji que represente ese valor.",
  "valor_descripcion": "Una oración que explique cómo ese valor aparece en la vida del estudiante, basada en lo que contó.",
  "proposito": "Frase de propósito en primera persona, 1-2 oraciones. Ej: 'Quiero usar mis manos y mi creatividad para construir cosas que mejoren mi comunidad.' Puede ser null si el historial no tiene suficiente información.",
  "reflexiones": [
    "Primera reflexión hacia el futuro, empezando con un verbo. Ej: 'Explorar talleres o actividades donde puedas...'",
    "Segunda reflexión",
    "Tercera reflexión"
  ]
}}

Nombre del estudiante: {nombre}
IMPORTANTE: Solo JSON, nada más."""

    return _llamar_gemini_json(prompt, client, model, system)


def _extraer_datos_orientador(
    historial_texto: str,
    estudiante: dict,
    sede_info: dict,
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
  "cuadrante_nombre": "Nombre del cuadrante Holland dominante (igual que en el PDF del estudiante).",
  "cuadrante_icono": "Emoji del cuadrante.",
  "cuadrante_descripcion_pedagogica": "Descripción técnica del perfil Holland en 2-3 oraciones para el docente. Puede usar terminología pedagógica.",
  "fortalezas": [
    {{
      "nombre": "Nombre de la fortaleza",
      "evidencia": "Evidencia observada en la conversación",
      "sugerencia": "Sugerencia pedagógica concreta para desarrollar esta fortaleza en el aula."
    }},
    {{"nombre": "Fortaleza 2", "evidencia": "Evidencia 2", "sugerencia": "Sugerencia 2"}},
    {{"nombre": "Fortaleza 3", "evidencia": "Evidencia 3", "sugerencia": "Sugerencia 3"}}
  ],
  "contexto_vida": {{
    "carga_familiar": {{
      "nivel": "alta | media | baja",
      "descripcion": "Descripción breve de la carga familiar observada.",
      "nota": "Nota orientativa para el docente sobre cómo abordar esto."
    }},
    "red_apoyo": {{
      "nivel": "fuerte | moderada | débil",
      "descripcion": "Descripción de la red de apoyo (familia, pares, comunidad).",
      "nota": "Recomendación para fortalecer la red."
    }},
    "respaldo_estudio": {{
      "nivel": "alto | medio | bajo",
      "descripcion": "Nivel de respaldo para continuar estudios post-secundarios.",
      "nota": "Acción sugerida para el orientador."
    }}
  }},
  "expectativa_corto_plazo": "Lo que el estudiante espera lograr en los próximos 1-2 años, según la conversación.",
  "barreras": [
    "Barrera 1 identificada (evitar datos personales sensibles)",
    "Barrera 2",
    "Barrera 3"
  ],
  "nivel_alerta": "regular | activo | prioritario",
  "factores_alerta": [
    "Factor de alerta observado 1",
    "Factor de alerta observado 2"
  ],
  "acciones_sugeridas": [
    "Acción concreta para el orientador 1",
    "Acción concreta 2",
    "Acción concreta 3",
    "Acción concreta 4"
  ],
  "alerta_critica": null
}}

Mapeado de nivel_riesgo a nivel_alerta: bajo → regular, medio → activo, alto → prioritario, sin_evaluar → regular.
Si hay indicios de riesgo psicológico grave (ideación, maltrato, situación de calle), alerta_critica debe ser:
  {{"tipo": "psicológica_crítica | situación_familiar_grave | otro", "descripcion": "Descripción breve del riesgo observado."}}
De lo contrario, alerta_critica es null.

IMPORTANTE: No incluyas datos familiares sensibles ni información que identifique negativamente al estudiante. Solo JSON, nada más."""

    return _llamar_gemini_json(prompt, client, model, system)


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
        model:      nombre del modelo (ej. "gemini-3.1-flash-lite")
        system_instruction: system prompt de rAÍz (para contexto en extracción)

    Returns:
        (pdf_estudiante_bytes, pdf_orientador_bytes)
    """
    historial_texto = _historial_a_texto(historial)
    nombre_completo = f"{estudiante.get('nombre', '')} {estudiante.get('apellido', '')}".strip()
    sede_info = db.get_sede_info(estudiante.get("sede_id", 0))
    fecha = datetime.now().strftime("%d de %B de %Y")

    datos_est = _extraer_datos_estudiante(historial_texto, nombre_completo, client, model)
    datos_ori = _extraer_datos_orientador(historial_texto, estudiante, sede_info, client, model)

    ctx_est = {
        "nombre_completo":       nombre_completo,
        "institucion":           sede_info.get("institucion", ""),
        "municipio":             sede_info.get("municipio", ""),
        "fecha":                 fecha,
        "cuadrante_icono":       datos_est.get("cuadrante_icono", "🌱"),
        "cuadrante_nombre":      datos_est.get("cuadrante_nombre", ""),
        "cuadrante_descripcion": datos_est.get("cuadrante_descripcion", ""),
        "fortalezas":            datos_est.get("fortalezas", []),
        "valor_central":         datos_est.get("valor_central", ""),
        "valor_icono":           datos_est.get("valor_icono", "⭐"),
        "valor_descripcion":     datos_est.get("valor_descripcion", ""),
        "proposito":             datos_est.get("proposito"),
        "reflexiones":           datos_est.get("reflexiones", []),
        "disclaimer":            DISCLAIMER_ESTUDIANTE,
        "pie":                   PIE,
    }

    ctx_ori = {
        "nombre_completo":              nombre_completo,
        "institucion":                  sede_info.get("institucion", ""),
        "municipio":                    sede_info.get("municipio", ""),
        "fecha":                        fecha,
        "orientador_nombre":            sede_info.get("orientador_nombre", ""),
        "cuadrante_icono":              datos_ori.get("cuadrante_icono", "🌱"),
        "cuadrante_nombre":             datos_ori.get("cuadrante_nombre", ""),
        "cuadrante_descripcion_pedagogica": datos_ori.get("cuadrante_descripcion_pedagogica", ""),
        "fortalezas":                   datos_ori.get("fortalezas", []),
        "contexto_vida":                datos_ori.get("contexto_vida", {}),
        "expectativa_corto_plazo":      datos_ori.get("expectativa_corto_plazo", ""),
        "barreras":                     datos_ori.get("barreras", []),
        "nivel_alerta":                 datos_ori.get("nivel_alerta", "regular"),
        "factores_alerta":              datos_ori.get("factores_alerta", []),
        "acciones_sugeridas":           datos_ori.get("acciones_sugeridas", []),
        "alerta_critica":               datos_ori.get("alerta_critica"),
        "disclaimer":                   DISCLAIMER_ORIENTADOR,
        "pie":                          PIE,
    }

    html_est = _renderizar_plantilla("mapa_estudiante.html", ctx_est)
    html_ori = _renderizar_plantilla("ficha_orientador.html", ctx_ori)

    pdf_est = _html_a_pdf(html_est)
    pdf_ori = _html_a_pdf(html_ori)

    return pdf_est, pdf_ori
