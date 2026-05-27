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
     → WeasyPrint convierte el HTML a PDF bytes

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
import os

import database as db
from def_esquemas_pdf_gen import EsquemaMapaEstudiante, EsquemaFichaOrientador

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ══════════════════════════════════════════════════════════════════════════════
# Catálogos cerrados — fuente de verdad para la extracción
# Viven aquí (en el extractor) y no en el prompt de chat.
# ══════════════════════════════════════════════════════════════════════════════

CATALOGO_FORTALEZAS = """
CATÁLOGO CERRADO DE FORTALEZAS VIA (12 opciones):
1. Creatividad / Ingenio: Resuelve problemas con lo que tiene, se inventa soluciones, piensa diferente.
2. Perseverancia / Persistencia: Sigue adelante a pesar de los obstáculos, termina lo que empieza, no se rinde.
3. Valentía: Actúa y enfrenta retos aunque tenga miedo o el panorama sea difícil.
4. Liderazgo: Toma la iniciativa, organiza a otros, guía a su grupo o a sus hermanos.
5. Trabajo en equipo / Ciudadanía: Sabe colaborar, pone su parte para que el grupo o la familia funcione.
6. Bondad / Generosidad: Ayuda a otros sin esperar nada a cambio, cuida a los más vulnerables.
7. Inteligencia Social: Sabe leer a la gente, entiende cómo se sienten los demás y sabe cómo tratarlos.
8. Prudencia / Autorregulación: Piensa antes de actuar, no se deja llevar por la rabia, controla sus impulsos.
9. Esperanza / Optimismo: Mantiene la visión de que el futuro puede ser mejor y trabaja para eso.
10. Curiosidad: Tiene ganas genuinas de aprender cosas nuevas, pregunta, investiga por su cuenta.
11. Gratitud: Sabe reconocer y agradecer lo que otros hacen por él/ella.
12. Perspectiva / Sabiduría: Sabe dar buenos consejos, entiende el cuadro completo de los problemas.
REGLA: Solo puedes usar nombres de este catálogo. No inventar otros.
"""

CATALOGO_VALORES = """
CATÁLOGO CERRADO DE VALORES (9 opciones):
1. Lealtad Familiar: Su motor principal es proteger, cuidar, aportar o devolverle a su núcleo.
2. Solidaridad / Apoyo Comunitario: Le mueve ayudar a su barrio, a sus vecinos o a quienes sufren.
3. Justicia / Equidad: Le mueve hacer lo correcto, defender a alguien de un trato injusto.
4. Responsabilidad: Le mueve cumplir con lo que le toca, hacerse cargo de sus deberes sin que lo obliguen.
5. Honestidad / Integridad: Le mueve la transparencia, hacer las cosas por la vía derecha, no engañar.
6. Esfuerzo / Trabajo Duro: Valora ganarse las cosas con el sudor de la frente, no le gusta lo regalado.
7. Autonomía / Independencia: Su motor es querer valerse por sí mismo, no depender de nadie.
8. Respeto: Le mueve el trato digno hacia los mayores, hacia sus pares o hacia su entorno.
9. Empatía: Le mueve no querer que otros pasen por el sufrimiento que él/ella ha visto o vivido.
REGLA: Solo puedes usar nombres de este catálogo. No inventar otros.
"""

# ══════════════════════════════════════════════════════════════════════════════
# Disclaimers
# ══════════════════════════════════════════════════════════════════════════════

DISCLAIMER_ESTUDIANTE = (
    "<strong>Este documento es tuyo.</strong> "
    "Fue generado por rAÍz, una inteligencia artificial, a partir de las "
    "conversaciones que tuviste durante tu proceso de mentoría. "
    "Es una síntesis de lo que vos mismo/a contaste y compartiste — "
    "no es un diagnóstico ni una evaluación psicológica, y puede no reflejar "
    "todo lo que sos. Los perfiles de intereses y las fortalezas son puntos "
    "de partida para explorar, no etiquetas definitivas: es completamente "
    "normal que cambien con el tiempo. "
    "Guardalo, compártilo con quien confíes, y usalo como una brújula — "
    "no como un mapa cerrado — para seguir construyendo tu proyecto de vida. "
    "Si querés que borremos tu información, podés pedírselo a tu orientador/a "
    "de acuerdo con la Ley 1581/2012 de Habeas Data."
)

DISCLAIMER_ORIENTADOR = (
    "<strong>Documento confidencial — uso exclusivo del equipo docente.</strong> "
    "Generado por rAÍz (IA) a partir del diálogo con el/la estudiante. "
    "<br><br>"
    "Esta ficha es una síntesis orientativa construida a partir de respuestas "
    "conversacionales, no de instrumentos psicométricos estandarizados. "
    "Los perfiles de intereses (Holland), las fortalezas (VIA) y los niveles de "
    "seguimiento son indicadores de aproximación — no diagnósticos clínicos ni "
    "etiquetas definitivas sobre el/la estudiante. El criterio profesional del "
    "orientador/a y del psicólogo/a escolar siempre prevalece sobre lo que "
    "aquí se presenta. "
    "<br><br>"
    "Los niveles de seguimiento (Regular / Acompañamiento Activo / Prioritario) "
    "son señales de atención estructurada para priorizar el acompañamiento "
    "presencial. No reemplazan una valoración clínica ni deben comunicarse "
    "al/la estudiante bajo ninguna circunstancia. "
    "<br><br>"
    "Tratamiento de datos sujeto a la Ley 1581/2012 (Habeas Data, Colombia). "
    "No compartir fuera del equipo docente autorizado."
)

PIE = "rAÍz · Mentoría de proyecto de vida · Piloto Valle del Cauca 2026"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════════════════════

# Patrón idéntico al de app.py — fuente de verdad única para limpieza de etiquetas.
# Incluye etiquetas de sistema, notas internas y paréntesis vacíos residuales.
_PATRON_LIMPIEZA_HISTORIAL = re.compile(
    r"\[\s*(?:FIN_CONSEJERIA|RIESGO_BAJO|RIESGO_MEDIO|RIESGO_ALTO"
    r"|ALERTA_ORIENTADOR_REQUERIDA|ALERTA_PSICOLOGICA_CRITICA"
    r"|INICIAR_RONDA_RELAMPAGO)\s*\]"
    r"|Nota interna de rAÍz\s*:?[^\n]*"
    r"|Nota interna\s*:[^\n]*"
    r"|\(\)",
    re.IGNORECASE,
)


def _historial_a_texto(historial: list[dict]) -> str:
    """
    Convierte el historial de DB a texto plano limpio para el extractor.
    Elimina todas las etiquetas internas del sistema y notas internas
    antes de pasarlas al modelo extractor — son ruido para el parseo
    y un vector potencial de prompt injection accidental.
    """
    lineas = []
    for msg in historial:
        rol = "rAÍz" if msg["rol"] == "model" else "Estudiante"
        contenido = _PATRON_LIMPIEZA_HISTORIAL.sub("", msg["contenido"]).strip()
        if contenido:
            lineas.append(f"[{rol}]: {contenido}")
    return "\n".join(lineas)


def _llamar_gemini_json(
    prompt: str,
    client,
    model: str,
    system: str,
    intentos: int = 3,
    schema=None,
) -> dict:
    """
    Llama a Gemini y garantiza retorno JSON válido.

    - response_mime_type="application/json": obliga al modelo a retornar
      solo JSON sin texto introductorio ni bloques markdown.
    - response_schema: cuando se provee, activa Structured Outputs de Gemini,
      eliminando el riesgo de JSON malformado.
    - Strip de backticks como fallback por si el SDK no respeta mime_type.
    - El historial viene envuelto en <conversacion> en los prompts,
      separando datos de instrucciones (anti-injection).
    """
    for intento in range(intentos):
        try:
            config_kwargs = dict(
                system_instruction=system,
                temperature=0.2,
                response_mime_type="application/json",
            )
            if schema is not None:
                config_kwargs["response_schema"] = schema

            resp = client.models.generate_content(
                model=model,
                config=types.GenerateContentConfig(**config_kwargs),
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


_playwright_installed = False

def _html_a_pdf(html_content: str) -> bytes:
    """
    Convierte HTML a PDF usando Playwright + Chromium.
    Reemplaza WeasyPrint que requiere GTK3 (no disponible en Windows sin instalación manual).
    """
    global _playwright_installed
    if not _playwright_installed:
        # Asegurar que los binarios del navegador estén instalados en entornos Cloud
        os.system("playwright install chromium")
        _playwright_installed = True
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
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
        "Eres un extractor de datos estructurados para reportes de orientación "
        "vocacional en Colombia. "
        "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
        "sin bloques de código markdown, sin explicaciones."
    )

    prompt = f"""Analiza esta conversación de mentoría entre rAÍz (IA) y un/a estudiante colombiano/a de grado 9° del Valle del Cauca.

<conversacion>
{historial_texto}
</conversacion>

{CATALOGO_FORTALEZAS}

{CATALOGO_VALORES}

INSTRUCCIONES DE EXTRACCIÓN — PDF DEL ESTUDIANTE "Mi Mapa rAÍz":
Tono general: empoderador, cálido, segunda persona (vos/tú). Como un espejo positivo.
Nombre del/la estudiante: {nombre}

1. POLOS DE PREDIGER (polos_dominantes y polos_debiles):
   Los cuatro polos son exactamente: Personas, Cosas, Datos, Ideas.
   Identifica los 2 con mayor presencia (dominantes) y los 2 con menor presencia (débiles).
   Si la Ronda Relámpago ocurrió en la conversación, úsala como fuente primaria.
   — Para dominantes: incluir descripcion_positiva (cálida, en vos/tú, sin jerga técnica).
   — Para débiles: incluir descripcion_donotham (neutra, NUNCA "débil", "malo", "no sirve para").

2. FORTALEZAS (exactamente 3):
   SOLO nombres del Catálogo VIA cerrado. No inventar, no usar sinónimos.
   Incluir evidencia en segunda persona empoderaora:
   Ej: "Porque nos contaste cómo resolviste [situación concreta de la conversación]..."

3. VALORES (exactamente 3):
   SOLO nombres del Catálogo de Valores cerrado. No inventar, no usar sinónimos.

4. TALENTO OCULTO EN ACCIÓN (talento_oculto_narrativa):
   Párrafo de 3-4 oraciones en segunda persona sobre un problema concreto que
   el/la estudiante resolvió y el talento que demostró ahí.
   Anclado en algo que dijo en la conversación.
   Si no hay episodio concreto, construir desde sus fortalezas más evidentes.

5. ESPEJO DEL ENTORNO:
   — modelo_rol_nombre: nombre o parentesco de quien admira (ej: "tu tío Carlos").
     Si no emergió, usar "alguien de tu entorno".
   — modelo_rol_cualidad: la cualidad específica que admira.
   — ancla_ubuntu: su propósito de retorno familiar/comunitario, redactado con calidez.

6. SUEÑO PRINCIPAL (sueno_principal): en sus palabras o muy cerca. Null si no emergió.

7. NOTA_SUEÑO: frase corta y cálida que acompañe el sueño.

8. TIPS (exactamente 5): recomendaciones accionables, positivas, personalizadas según
   sus polos dominantes y fortalezas. Para adolescente de 14-16 años del Valle del Cauca.
   Basadas en VIA, SCCT, Covey adaptado y Ubuntu.
   REGLA ESTRICTA: NO mencionar ni recomendar cursos, estudios técnicos (SENA), universitarios ni ninguna educación formal fuera de la escuela. Enfocarse únicamente en actitudes, exploración personal de intereses diarios y conversaciones con su entorno.

9. METÁFORA DE CIERRE (metafora_cierre): una sola oración con metáfora territorial
   (caña, café, río, ladera, semilla, cosecha, raíz). Cálida y memorable.

IMPORTANTE: Solo JSON válido, nada más."""

    return _llamar_gemini_json(
        prompt, client, model, system, schema=EsquemaMapaEstudiante
    )


def _extraer_datos_orientador(
    historial_texto: str,
    estudiante: dict,
    sede_info: dict,
    client,
    model: str,
) -> dict:
    system = (
        "Eres un extractor de datos estructurados para reportes pedagógicos "
        "de orientación vocacional en Colombia. "
        "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
        "sin bloques de código markdown, sin explicaciones."
    )

    nivel_riesgo_db = estudiante.get("perfil_riesgo", "sin_evaluar")

    # Mapeo explícito para evitar ambigüedad al modelo
    mapeo_alerta = {
        "bajo": "regular",
        "medio": "activo",
        "alto": "prioritario",
        "sin_evaluar": "regular",
    }
    nivel_alerta_mapeado = mapeo_alerta.get(nivel_riesgo_db, "regular")

    prompt = f"""Analiza esta conversación de mentoría entre rAÍz (IA) y un/a estudiante de grado 9° en el Valle del Cauca, Colombia.

<conversacion>
{historial_texto}
</conversacion>

DATOS DEL SISTEMA:
- Nivel de seguimiento detectado por el motor de inferencia: {nivel_riesgo_db}
- Nivel de alerta para el reporte (ya mapeado): {nivel_alerta_mapeado}
- Grado: {estudiante.get('grado', 9)}

{CATALOGO_FORTALEZAS}

{CATALOGO_VALORES}

INSTRUCCIONES DE EXTRACCIÓN — FICHA DEL ORIENTADOR:
Tono general: profesional, técnico, empático. Lenguaje de condiciones estructurales.
PROHIBIDO adjetivar al estudiante. PROHIBIDO: "caso difícil", "estudiante en riesgo",
"perfil problemático". CORRECTO: "el/la estudiante enfrenta condiciones estructurales que...".

1. POLOS DE PREDIGER (polos_dominantes y polos_debiles):
   Los cuatro polos son: Personas, Cosas, Datos, Ideas.
   — Para dominantes: incluir descripcion_pedagogica (técnica, para el docente).
   — Para débiles: incluir descripcion_donotham (neutro).
   — prediger_evidencia: actividad específica mencionada que justifica los dominantes.
   Si la Ronda Relámpago ocurrió, usarla como fuente primaria.

2. FORTALEZAS (exactamente 3):
   SOLO nombres del Catálogo VIA cerrado.
   Evidencia en tercera persona técnica: "Demostró [fortaleza] cuando describió [situación]."

3. VALORES (exactamente 3):
   SOLO nombres del Catálogo de Valores cerrado.
   Evidencia en tercera persona técnica.

4. FACTORES PROTECTORES (factores_protectores):
   2-4 factores que funcionan como anclas positivas.
   Lenguaje estructural: "Cuenta con figura adulta de apoyo activa (tío)" no "tiene suerte".

5. CONTEXTO DE VIDA (contexto_vida) — semáforo de tres dimensiones:
   — carga_familiar: nivel alta/media/baja + descripción + evidencia investigación
   — red_apoyo: nivel fuerte/moderada/débil + descripción + evidencia investigación
   — respaldo_estudio: nivel alto/medio/bajo + descripción + evidencia investigación

6. VARIABLES SCCT (Bloque D):
   — scct_metas_proyectadas: qué visualiza para sí mismo/a post-colegio.
   — scct_expectativas_negativas: 2-4 barreras/creencias limitantes expresadas.
   — scct_oportunidades_percibidas: 1-3 opciones que el/la estudiante reconoce en su territorio.

7. ESTILO DE INTERACCIÓN (estilo_interaccion):
   Evaluación del engagement conversacional a lo largo de las sesiones.

8. SEMÁFORO DE SEGUIMIENTO:
   — nivel_alerta: usar EXACTAMENTE "{nivel_alerta_mapeado}" (ya determinado por el motor).
   — descripcion_nivel_alerta: justificación con condiciones estructurales observadas.
   — factores_alerta: condiciones que fundamentan el nivel (vacío [] si es "regular").
   — mostrar_espacio_seguimiento: true si nivel es "activo" o "prioritario", false si "regular".

9. ALERTA CRÍTICA (alerta_critica):
   Solo si hay indicios de riesgo psicológico grave (ideación suicida, maltrato, abuso,
   abandono grave). Null en todos los demás casos.

IMPORTANTE: Solo JSON válido, nada más."""

    return _llamar_gemini_json(
        prompt, client, model, system, schema=EsquemaFichaOrientador
    )


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
        estudiante:         dict completo del estudiante (de DB)
        historial:          lista de mensajes tal como los devuelve db.get_historial()
        client:             instancia del cliente Gemini (ya inicializado en app.py)
        model:              nombre del modelo (ej. "gemini-3.1-flash-lite")
        system_instruction: system prompt de rAÍz (no usado en extracción,
                            conservado para compatibilidad de firma)

    Returns:
        (pdf_estudiante_bytes, pdf_orientador_bytes)
    """
    historial_texto = _historial_a_texto(historial)
    nombre_completo = f"{estudiante.get('nombre', '')} {estudiante.get('apellido', '')}".strip()
    sede_info = db.get_sede_info(estudiante.get("sede_id", 0)) or {}
    fecha = datetime.now().strftime("%d de %B de %Y")
    sesiones_count = len({m.get("sesion_numero", 1) for m in historial})

    datos_est = _extraer_datos_estudiante(historial_texto, nombre_completo, client, model)
    datos_ori = _extraer_datos_orientador(historial_texto, estudiante, sede_info, client, model)

    # Type-safety: garantizar que listas críticas sean listas
    def safe_list(val):
        if isinstance(val, list):
            return val
        return [val] if val else []

    # ── Contexto para el PDF del estudiante ───────────────────────────────────
    ctx_est = {
        "nombre_completo":          nombre_completo,
        "institucion":              sede_info.get("institucion", ""),
        "municipio":                sede_info.get("municipio", ""),
        "fecha":                    fecha,
        # Prediger
        "polos_dominantes":         safe_list(datos_est.get("polos_dominantes", [])),
        "polos_debiles":            safe_list(datos_est.get("polos_debiles", [])),
        # ADN de carácter
        "fortalezas":               safe_list(datos_est.get("fortalezas", [])),
        "valores":                  safe_list(datos_est.get("valores", [])),
        # Talento oculto
        "talento_oculto_narrativa": datos_est.get("talento_oculto_narrativa", ""),
        # Espejo del entorno
        "modelo_rol_nombre":        datos_est.get("modelo_rol_nombre", "alguien de tu entorno"),
        "modelo_rol_cualidad":      datos_est.get("modelo_rol_cualidad", ""),
        "ancla_ubuntu":             datos_est.get("ancla_ubuntu", ""),
        # Sueño y camino
        "sueno_principal":          datos_est.get("sueno_principal"),
        "nota_sueno":               datos_est.get("nota_sueno", ""),
        "tips":                     safe_list(datos_est.get("tips", [])),
        "metafora_cierre":          datos_est.get("metafora_cierre", ""),
        # Pie y disclaimer
        "disclaimer":               DISCLAIMER_ESTUDIANTE,
        "pie":                      PIE,
    }

    # ── Contexto para la ficha del orientador ─────────────────────────────────
    ctx_ori = {
        "nombre_completo":             nombre_completo,
        "institucion":                 sede_info.get("institucion", ""),
        "municipio":                   sede_info.get("municipio", ""),
        "fecha":                       fecha,
        "orientador_nombre":           sede_info.get("orientador_nombre", "N/D"),
        "sesiones_analizadas":         sesiones_count,
        # Prediger
        "polos_dominantes":            safe_list(datos_ori.get("polos_dominantes", [])),
        "polos_debiles":               safe_list(datos_ori.get("polos_debiles", [])),
        "prediger_evidencia":          datos_ori.get("prediger_evidencia", ""),
        # Fortalezas, valores y factores protectores
        "fortalezas":                  safe_list(datos_ori.get("fortalezas", [])),
        "valores":                     safe_list(datos_ori.get("valores", [])),
        "factores_protectores":        safe_list(datos_ori.get("factores_protectores", [])),
        # Contexto de vida (semáforo)
        "contexto_vida":               datos_ori.get("contexto_vida", {}),
        # SCCT
        "scct_metas_proyectadas":      datos_ori.get("scct_metas_proyectadas", ""),
        "scct_expectativas_negativas": safe_list(datos_ori.get("scct_expectativas_negativas", [])),
        "scct_oportunidades_percibidas": safe_list(datos_ori.get("scct_oportunidades_percibidas", [])),
        # Engagement
        "estilo_interaccion":          datos_ori.get("estilo_interaccion", ""),
        # Semáforo de seguimiento
        "nivel_alerta":                datos_ori.get("nivel_alerta", "regular"),
        "descripcion_nivel_alerta":    datos_ori.get("descripcion_nivel_alerta", ""),
        "factores_alerta":             safe_list(datos_ori.get("factores_alerta", [])),
        "factores_protectores_ori":    safe_list(datos_ori.get("factores_protectores", [])),
        "mostrar_espacio_seguimiento": datos_ori.get("mostrar_espacio_seguimiento", False),
        "alerta_critica":              datos_ori.get("alerta_critica"),
        # Pie y disclaimer
        "disclaimer":                  DISCLAIMER_ORIENTADOR,
        "pie":                         PIE,
    }

    html_est = _renderizar_plantilla("mapa_estudiante.html", ctx_est)
    html_ori = _renderizar_plantilla("ficha_orientador.html", ctx_ori)

    pdf_est = _html_a_pdf(html_est)
    pdf_ori = _html_a_pdf(html_ori)

    return pdf_est, pdf_ori
