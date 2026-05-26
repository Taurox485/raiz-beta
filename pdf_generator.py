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
from weasyprint import HTML as WeasyHTML

import database as db

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
) -> dict:
    """
    Llama a Gemini y garantiza retorno JSON válido.

    Fix 1 — JSON nativo: response_mime_type="application/json" obliga al modelo
    a retornar solo JSON sin texto introductorio ni bloques markdown.
    Se mantiene el strip de backticks como fallback por si el SDK no lo respeta.

    Fix 2 — Inyección accidental: el historial ya viene envuelto en <conversacion>
    desde los prompts de extracción, separando datos de instrucciones.
    """
    for intento in range(intentos):
        try:
            resp = client.models.generate_content(
                model=model,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
                contents=prompt,
            )
            texto = resp.text.strip()
            # Fallback: limpiar backticks por si el SDK ignora response_mime_type
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
    base_url = str(Path(__file__).parent)
    return WeasyHTML(string=html_content, base_url=base_url).write_pdf()


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

    prompt = f"""Analiza esta conversación de mentoría entre rAÍz (IA) y un estudiante colombiano de grado 9° del Valle del Cauca.

<conversacion>
{historial_texto}
</conversacion>

{CATALOGO_FORTALEZAS}

{CATALOGO_VALORES}

INSTRUCCIONES DE EXTRACCIÓN PARA EL REPORTE DEL ESTUDIANTE:

1. PERFIL DE INTERESES (Holland): Identifica los DOS cuadrantes más presentes (dominantes) y los DOS menos presentes (débiles) en la conversación. Los cuadrantes son exactamente estos cuatro: Personas, Ideas, Datos, Cosas. Si la Ronda Relámpago ocurrió, úsala como fuente primaria; si no, infiere desde la conversación.

2. FORTALEZAS: Identifica exactamente 3 fortalezas usando SOLO los nombres del Catálogo Cerrado VIA. Basa cada una en evidencia concreta de la conversación.

3. VALORES: Identifica exactamente 3 valores usando SOLO los nombres del Catálogo Cerrado de Valores. Basa cada uno en evidencia concreta.

4. SUEÑO PRINCIPAL: Extrae el sueño o deseo principal del estudiante en sus propias palabras o parafraseando muy de cerca lo que dijo. Si no emergió un sueño claro, devuelve null.

5. TIPS: Genera 5 recomendaciones de vida personalizadas según los cuadrantes dominantes. Deben ser accionables, positivas, basadas en los marcos teóricos (VIA, SCCT, Covey, Ubuntu) y relevantes para un adolescente de 14-16 años del Valle del Cauca.

Devuelve SOLO este JSON:

{{
  "cuadrantes_dominantes": [
    {{
      "nombre": "Nombre exacto del cuadrante (Personas | Ideas | Datos | Cosas)",
      "icono": "Emoji representativo",
      "descripcion_positiva": "2-3 oraciones en tono cálido describiendo qué le gusta y en qué tiende a ser bueno alguien con este perfil. En español colombiano, usando 'vos' o 'tú'. Sin jerga técnica."
    }},
    {{
      "nombre": "Segundo cuadrante dominante",
      "icono": "Emoji",
      "descripcion_positiva": "Descripción"
    }}
  ],
  "cuadrantes_debiles": [
    {{
      "nombre": "Nombre exacto del cuadrante menos presente",
      "icono": "Emoji",
      "descripcion_donotharm": "1-2 oraciones usando lenguaje do-no-harm: 'tiende a preferir otras actividades', 'no es lo que más le llama la atención por ahora'. NUNCA usar 'débil', 'malo', 'no sirve para'. Tono neutro y respetuoso."
    }},
    {{
      "nombre": "Cuarto cuadrante",
      "icono": "Emoji",
      "descripcion_donotham": "Descripción"
    }}
  ],
  "fortalezas": [
    {{
      "nombre": "Nombre EXACTO del catálogo VIA",
      "descripcion_catalogo": "Descripción corta del catálogo para este nombre (copiada textualmente del catálogo)"
    }},
    {{"nombre": "Fortaleza 2 del catálogo", "descripcion_catalogo": "Descripción del catálogo"}},
    {{"nombre": "Fortaleza 3 del catálogo", "descripcion_catalogo": "Descripción del catálogo"}}
  ],
  "valores": [
    {{
      "nombre": "Nombre EXACTO del catálogo de Valores",
      "descripcion_catalogo": "Descripción corta del catálogo para este nombre (copiada textualmente del catálogo)"
    }},
    {{"nombre": "Valor 2 del catálogo", "descripcion_catalogo": "Descripción del catálogo"}},
    {{"nombre": "Valor 3 del catálogo", "descripcion_catalogo": "Descripción del catálogo"}}
  ],
  "sueno_principal": "El sueño o deseo principal del estudiante en sus propias palabras o muy cercano a ellas. Null si no emergió.",
  "nota_sueno": "Una frase corta y cálida que acompañe el sueño: 'Recuerda que los sueños pueden cambiar — lo importante es que hoy ya sabés en qué dirección mirás.'",
  "tips": [
    "Tip 1: consejo de vida accionable y positivo personalizado para este perfil Holland dominante",
    "Tip 2",
    "Tip 3",
    "Tip 4",
    "Tip 5"
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
        "Eres un extractor de datos estructurados para reportes pedagógicos "
        "de orientación vocacional en Colombia. "
        "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
        "sin bloques de código markdown, sin explicaciones."
    )

    nivel_riesgo_db = estudiante.get("perfil_riesgo", "sin_evaluar")

    prompt = f"""Analiza esta conversación de mentoría entre rAÍz (IA) y un estudiante de grado 9° en el Valle del Cauca, Colombia.

<conversacion>
{historial_texto}
</conversacion>

DATOS DEL SISTEMA:
- Nivel de seguimiento detectado por el motor de inferencia: {nivel_riesgo_db}
- Grado: {estudiante.get('grado', 9)}

{CATALOGO_FORTALEZAS}

{CATALOGO_VALORES}

INSTRUCCIONES DE EXTRACCIÓN PARA LA FICHA DEL ORIENTADOR:

LENGUAJE OBLIGATORIO — RIESGO ALTO:
Cuando el nivel sea "alto" o "prioritario", describe SIEMPRE las condiciones estructurales observadas, nunca características de la persona. 
CORRECTO: "El/la estudiante enfrenta una carga laboral que compite con el estudio y una red de apoyo adulto limitada."
INCORRECTO: "Estudiante en riesgo", "caso difícil", "perfil problemático".

PERFIL HOLLAND:
Los cuadrantes son exactamente: Personas, Ideas, Datos, Cosas.
Si la Ronda Relámpago ocurrió en la conversación, úsala como fuente primaria para identificar dominantes y débiles.

Devuelve SOLO este JSON:

{{
  "cuadrantes_dominantes": [
    {{
      "nombre": "Nombre exacto (Personas | Ideas | Datos | Cosas)",
      "icono": "Emoji",
      "descripcion_pedagogica": "2-3 oraciones técnicas para el docente describiendo qué implica este perfil en términos de aprendizaje y motivación escolar."
    }},
    {{
      "nombre": "Segundo cuadrante dominante",
      "icono": "Emoji",
      "descripcion_pedagogica": "Descripción técnica"
    }}
  ],
  "cuadrantes_debiles": [
    {{
      "nombre": "Cuadrante menos presente",
      "icono": "Emoji",
      "descripcion_donotham": "1 oración neutra: 'Muestra menor afinidad hacia actividades de tipo [X] en el momento actual.'"
    }},
    {{
      "nombre": "Cuarto cuadrante",
      "icono": "Emoji",
      "descripcion_donotham": "Descripción neutra"
    }}
  ],
  "fortalezas": [
    {{
      "nombre": "Nombre EXACTO del catálogo VIA",
      "descripcion_catalogo": "Descripción del catálogo (copiada textualmente)",
      "evidencia": "Una oración de evidencia concreta observada en la conversación."
    }},
    {{"nombre": "Fortaleza 2", "descripcion_catalogo": "Descripción", "evidencia": "Evidencia"}},
    {{"nombre": "Fortaleza 3", "descripcion_catalogo": "Descripción", "evidencia": "Evidencia"}}
  ],
  "valores": [
    {{
      "nombre": "Nombre EXACTO del catálogo de Valores",
      "descripcion_catalogo": "Descripción del catálogo (copiada textualmente)",
      "evidencia": "Evidencia concreta de cómo apareció este valor en la conversación."
    }},
    {{"nombre": "Valor 2", "descripcion_catalogo": "Descripción", "evidencia": "Evidencia"}},
    {{"nombre": "Valor 3", "descripcion_catalogo": "Descripción", "evidencia": "Evidencia"}}
  ],
  "contexto_vida": {{
    "carga_familiar": {{
      "nivel": "alta | media | baja",
      "descripcion": "Descripción concreta de lo observado en la conversación (sin datos sensibles identificables).",
      "evidencia_investigacion": "Una frase que explique qué dice la evidencia sobre el impacto de este nivel de carga en la continuidad educativa. Ej: 'La investigación muestra que cargas laborales superiores a 4 horas diarias en días escolares están asociadas con mayor riesgo de deserción (DANE, 2023).'"
    }},
    "red_apoyo": {{
      "nivel": "fuerte | moderada | débil",
      "descripcion": "Descripción de la red de apoyo observada.",
      "evidencia_investigacion": "Frase con respaldo en evidencia sobre el rol de la red de apoyo en la continuidad escolar."
    }},
    "respaldo_estudio": {{
      "nivel": "alto | medio | bajo",
      "descripcion": "Nivel de respaldo del entorno para continuar estudiando.",
      "evidencia_investigacion": "Frase con respaldo en evidencia sobre el impacto del respaldo familiar en las trayectorias educativas."
    }}
  }},
  "expectativa_corto_plazo": "Lo que el/la estudiante imagina para sí mismo/a al terminar el colegio, en sus propias palabras o muy cerca de ellas.",
  "barreras": [
    "Barrera estructural 1 (sin datos sensibles identificables)",
    "Barrera 2",
    "Barrera 3"
  ],
  "nivel_alerta": "regular | activo | prioritario",
  "descripcion_nivel_alerta": "Una oración que describa las condiciones estructurales que fundamentan este nivel, usando lenguaje de condiciones observadas, no de etiquetas sobre la persona.",
  "factores_alerta": [
    "Condición estructural observada 1",
    "Condición estructural observada 2"
  ],
  "factores_protectores": [
    "Factor protector identificado 1",
    "Factor protector identificado 2"
  ],
  "mostrar_espacio_seguimiento": true,
  "alerta_critica": null
}}

Mapeado obligatorio de nivel_riesgo_db a nivel_alerta:
  bajo → regular
  medio → activo
  alto → prioritario
  sin_evaluar → regular

mostrar_espacio_seguimiento: true solo cuando nivel_alerta es "activo" o "prioritario". False cuando es "regular".

alerta_critica: Si hay indicios de riesgo psicológico grave (ideación suicida, maltrato, abuso, abandono), devolver:
  {{"tipo": "psicológica_crítica | situación_familiar_grave | otro", "descripcion": "Descripción concreta del riesgo observado, sin información que identifique negativamente al estudiante."}}
De lo contrario, null.

IMPORTANTE: No incluir datos familiares sensibles ni información que pueda estigmatizar al estudiante. Solo JSON, nada más."""

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

    # Garantizar que tips siempre sea lista — si el modelo devuelve un string
    # (alucinación), Jinja iteraría sobre cada letra y rompería el diseño.
    tips_raw = datos_est.get("tips", [])
    tips_safe = tips_raw if isinstance(tips_raw, list) else [tips_raw] if tips_raw else []

    # ── Contexto para el PDF del estudiante ───────────────────────────────────
    ctx_est = {
        "nombre_completo":        nombre_completo,
        "institucion":            sede_info.get("institucion", ""),
        "municipio":              sede_info.get("municipio", ""),
        "fecha":                  fecha,
        # Perfil Holland
        "cuadrantes_dominantes":  datos_est.get("cuadrantes_dominantes", []),
        "cuadrantes_debiles":     datos_est.get("cuadrantes_debiles", []),
        # Fortalezas y valores (catálogo cerrado)
        "fortalezas":             datos_est.get("fortalezas", []),
        "valores":                datos_est.get("valores", []),
        # Sueño principal
        "sueno_principal":        datos_est.get("sueno_principal"),
        "nota_sueno":             datos_est.get("nota_sueno", ""),
        # Tips personalizados (type-safe)
        "tips":                   tips_safe,
        # Pie y disclaimer
        "disclaimer":             DISCLAIMER_ESTUDIANTE,
        "pie":                    PIE,
    }

    # ── Contexto para la ficha del orientador ─────────────────────────────────
    ctx_ori = {
        "nombre_completo":             nombre_completo,
        "institucion":                 sede_info.get("institucion", ""),
        "municipio":                   sede_info.get("municipio", ""),
        "fecha":                       fecha,
        "orientador_nombre":           sede_info.get("orientador_nombre", "N/D"),
        "sesiones_analizadas":         sesiones_count,
        # Perfil Holland
        "cuadrantes_dominantes":       datos_ori.get("cuadrantes_dominantes", []),
        "cuadrantes_debiles":          datos_ori.get("cuadrantes_debiles", []),
        # Fortalezas y valores (catálogo cerrado con evidencia)
        "fortalezas":                  datos_ori.get("fortalezas", []),
        "valores":                     datos_ori.get("valores", []),
        # Contexto de vida con semáforo y evidencia
        "contexto_vida":               datos_ori.get("contexto_vida", {}),
        # Expectativa e imagen de futuro
        "expectativa_corto_plazo":     datos_ori.get("expectativa_corto_plazo", ""),
        "barreras":                    datos_ori.get("barreras", []),
        # Alertas
        "nivel_alerta":                datos_ori.get("nivel_alerta", "regular"),
        "descripcion_nivel_alerta":    datos_ori.get("descripcion_nivel_alerta", ""),
        "factores_alerta":             datos_ori.get("factores_alerta", []),
        "factores_protectores":        datos_ori.get("factores_protectores", []),
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
