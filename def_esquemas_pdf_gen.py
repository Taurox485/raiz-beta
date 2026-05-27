"""
def_esquemas_pdf_gen.py — Esquemas Pydantic para Structured Outputs de Gemini

Estos esquemas definen el contrato entre el extractor (pdf_generator.py)
y los templates HTML (mapa_estudiante.html, ficha_orientador.html).

REGLA CRÍTICA: Los nombres de campo aquí deben coincidir exactamente con
las claves que usan los templates Jinja2. No renombrar sin actualizar los templates.

Arquitectura de catálogos:
- Los catálogos cerrados (VIA, Valores) NO se encodean aquí como Enum.
- Se inyectan como texto en el prompt de extracción con instrucción explícita
  de ceñirse al catálogo. Pydantic valida estructura; el prompt valida vocabulario.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ESQUEMAS COMPARTIDOS
# ══════════════════════════════════════════════════════════════════════════════

class PoloInfo(BaseModel):
    """
    Representa un polo de Prediger (Personas, Cosas, Datos, Ideas).
    Usado tanto en el PDF del estudiante como en la ficha del orientador.
    Los campos opcionales se usan según el documento destino.
    """
    nombre: str = Field(
        description="Exactamente uno de: Personas, Cosas, Datos, Ideas"
    )
    icono: str = Field(
        description="Emoji representativo del polo"
    )
    descripcion_positiva: Optional[str] = Field(
        default=None,
        description=(
            "Solo para PDF estudiante. 2-3 oraciones en tono cálido "
            "describiendo qué le gusta y en qué tiende a ser buena "
            "la persona con este perfil. En español colombiano con vos/tú. "
            "Sin jerga técnica."
        )
    )
    descripcion_donotham: Optional[str] = Field(
        default=None,
        description=(
            "Para polos de menor preferencia. 1-2 oraciones neutras. "
            "NUNCA usar 'débil', 'malo', 'no sirve para'. "
            "Ej: 'tiende a preferir otras actividades por ahora'."
        )
    )
    descripcion_pedagogica: Optional[str] = Field(
        default=None,
        description=(
            "Solo para ficha orientador. 2-3 oraciones técnicas para "
            "el docente describiendo qué implica este polo en términos "
            "de aprendizaje y motivación escolar."
        )
    )


class FortalezaItem(BaseModel):
    """Fortaleza VIA con evidencia narrativa de la conversación."""
    nombre: str = Field(
        description=(
            "Nombre EXACTO del catálogo VIA cerrado de 12 opciones. "
            "No inventar ni usar sinónimos."
        )
    )
    descripcion_catalogo: str = Field(
        description="Descripción del catálogo, copiada textualmente."
    )
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Evidencia concreta y específica observada en la conversación. "
            "Para el PDF estudiante: redactar en segunda persona empoderaora, "
            "ej: 'Porque nos contaste cómo arreglaste la bomba de agua...'. "
            "Para la ficha orientador: redactar en tercera persona técnica."
        )
    )


class ValorItem(BaseModel):
    """Valor central con evidencia narrativa de la conversación."""
    nombre: str = Field(
        description=(
            "Nombre EXACTO del catálogo de Valores cerrado de 9 opciones. "
            "No inventar ni usar sinónimos."
        )
    )
    descripcion_catalogo: str = Field(
        description="Descripción del catálogo, copiada textualmente."
    )
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Evidencia concreta de cómo emergió este valor en la conversación. "
            "Para el PDF estudiante: tono cálido, segunda persona. "
            "Para la ficha orientador: tono técnico, tercera persona."
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# ESQUEMA 1 — PDF ESTUDIANTE: "Mi Mapa rAÍz"
# ══════════════════════════════════════════════════════════════════════════════

class EsquemaMapaEstudiante(BaseModel):
    """
    Datos para generar el PDF del estudiante.
    Tono: empoderador, cálido, segunda persona (vos/tú).
    """

    # Sección 1: Inclinaciones naturales (Prediger)
    polos_dominantes: List[PoloInfo] = Field(
        description=(
            "Los 2 polos de mayor interés. Cada uno DEBE tener "
            "descripcion_positiva. Si la Ronda Relámpago ocurrió, "
            "usarla como fuente primaria."
        )
    )
    polos_debiles: List[PoloInfo] = Field(
        description=(
            "Los 2 polos de menor interés. Cada uno DEBE tener "
            "descripcion_donotham. Lenguaje do-no-harm obligatorio."
        )
    )

    # Sección 2: ADN de carácter
    fortalezas: List[FortalezaItem] = Field(
        description=(
            "Exactamente 3 fortalezas del catálogo VIA cerrado. "
            "Cada una DEBE incluir evidencia en segunda persona empoderaora."
        )
    )
    valores: List[ValorItem] = Field(
        description=(
            "Exactamente 3 valores del catálogo cerrado. "
            "La evidencia es opcional para el PDF del estudiante."
        )
    )

    # Sección 3: Talento oculto en acción
    talento_oculto_narrativa: str = Field(
        description=(
            "Párrafo de 3-4 oraciones en segunda persona empoderaora "
            "sobre un problema concreto que el/la estudiante resolvió "
            "y el talento que demostró. "
            "Ej: 'Cuando nos contaste sobre el día que arreglaste la bomba "
            "de agua de tu casa usando solo herramientas básicas...'. "
            "Si no emergió un episodio concreto, construir desde sus "
            "fortalezas más evidentes."
        )
    )

    # Sección 4: El espejo del entorno
    modelo_rol_nombre: str = Field(
        description=(
            "Nombre o parentesco de la persona local que el/la estudiante admira. "
            "Ej: 'tu tío Carlos', 'la profe de matemáticas'. "
            "Si no emergió un modelo de rol claro, usar 'alguien de tu entorno'."
        )
    )
    modelo_rol_cualidad: str = Field(
        description=(
            "La cualidad específica que el/la estudiante admira de esa persona. "
            "En las propias palabras del estudiante o muy cerca de ellas."
        )
    )
    ancla_ubuntu: str = Field(
        description=(
            "Su propósito de retorno familiar o comunitario, redactado de forma "
            "cálida y motivadora. "
            "Ej: 'Lo que te conecta con los tuyos es tu deseo de ser el primero "
            "en graduarse y demostrarles que sí se puede.'"
        )
    )

    # Sección 5: Sueño y camino
    sueno_principal: Optional[str] = Field(
        default=None,
        description=(
            "El sueño o deseo principal del/la estudiante, en sus propias "
            "palabras o muy cerca de ellas. Null si no emergió con claridad."
        )
    )
    nota_sueno: str = Field(
        description=(
            "Frase corta y cálida que acompañe el sueño. "
            "Ej: 'Recuerda que los sueños pueden cambiar — lo importante "
            "es que hoy ya sabés en qué dirección mirás.'"
        )
    )
    tips: List[str] = Field(
        description=(
            "Exactamente 5 recomendaciones de vida accionables, positivas "
            "y personalizadas según los polos dominantes y fortalezas. "
            "Relevantes para un adolescente de 14-16 años del Valle del Cauca. "
            "Basadas en VIA, SCCT, Covey adaptado y Ubuntu."
        )
    )
    metafora_cierre: str = Field(
        description=(
            "Una sola oración de cierre con metáfora adaptada al territorio: "
            "caña de azúcar, café, río, ladera, cultivo, cosecha, semilla, raíz. "
            "Ej: 'Como la caña que dobla con el viento pero nunca pierde su raíz, "
            "vos también sabés cómo mantenerte firme.'"
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# ESQUEMA 2 — FICHA ORIENTADOR: "Ficha de Acompañamiento en Orientación"
# ══════════════════════════════════════════════════════════════════════════════

class DimensionContexto(BaseModel):
    """Una dimensión del semáforo de contexto de vida."""
    nivel: str = Field(
        description=(
            "Para carga_familiar: 'alta', 'media' o 'baja'. "
            "Para red_apoyo: 'fuerte', 'moderada' o 'débil'. "
            "Para respaldo_estudio: 'alto', 'medio' o 'bajo'."
        )
    )
    descripcion: str = Field(
        description=(
            "Descripción concreta de lo observado en la conversación. "
            "Sin datos sensibles identificables. "
            "Lenguaje de condiciones estructurales, nunca adjetivos sobre la persona."
        )
    )
    evidencia_investigacion: str = Field(
        description=(
            "Una frase que explique qué dice la evidencia sobre el impacto "
            "de este nivel en la continuidad educativa. "
            "Ej: 'La investigación muestra que cargas laborales superiores "
            "a 4 horas diarias en días escolares están asociadas con mayor "
            "riesgo de deserción (DANE, 2023).'"
        )
    )


class ContextoVida(BaseModel):
    carga_familiar: DimensionContexto
    red_apoyo: DimensionContexto
    respaldo_estudio: DimensionContexto


class AlertaCritica(BaseModel):
    tipo: str = Field(
        description=(
            "Exactamente uno de: 'psicológica_crítica', "
            "'situación_familiar_grave', 'otro'."
        )
    )
    descripcion: str = Field(
        description=(
            "Descripción concreta del riesgo observado, sin información "
            "que identifique negativamente al estudiante."
        )
    )


class EsquemaFichaOrientador(BaseModel):
    """
    Datos para generar la ficha del orientador.
    Tono: profesional, técnico, lenguaje de condiciones estructurales.
    NUNCA adjetivar al estudiante. NUNCA términos como 'caso difícil'.
    """

    # Bloque B: Perfil de intereses Prediger
    polos_dominantes: List[PoloInfo] = Field(
        description=(
            "Los 2 polos de mayor interés. Cada uno DEBE tener "
            "descripcion_pedagogica para el docente. "
            "Si la Ronda Relámpago ocurrió, usarla como fuente primaria."
        )
    )
    polos_debiles: List[PoloInfo] = Field(
        description=(
            "Los 2 polos de menor interés. Cada uno DEBE tener "
            "descripcion_donotham en lenguaje neutro."
        )
    )
    prediger_evidencia: str = Field(
        description=(
            "Una actividad específica mencionada por el/la estudiante "
            "que justifica los polos dominantes identificados. "
            "Ej: 'Reportó que le apasiona desarmar y limpiar motores "
            "con su tío en el taller de la vereda.'"
        )
    )

    # Bloque C: Fortalezas y factores protectores
    fortalezas: List[FortalezaItem] = Field(
        description=(
            "Exactamente 3 fortalezas del catálogo VIA cerrado. "
            "Cada una DEBE incluir evidencia en tono técnico, tercera persona."
        )
    )
    valores: List[ValorItem] = Field(
        description=(
            "Exactamente 3 valores del catálogo cerrado. "
            "Cada uno DEBE incluir evidencia en tono técnico."
        )
    )
    factores_protectores: List[str] = Field(
        description=(
            "Lista de 2-4 factores que funcionan como anclas positivas: "
            "personas concretas, relaciones, actividades, creencias. "
            "Lenguaje estructural: 'Cuenta con figura adulta de apoyo activa (tío)' "
            "no 'Es afortunado de tener tío'."
        )
    )

    # Bloque A: Contexto de vida
    contexto_vida: ContextoVida

    # Bloque D: Variables SCCT
    scct_metas_proyectadas: str = Field(
        description=(
            "Qué visualiza o espera lograr el/la estudiante a corto/mediano "
            "plazo post-colegio, en sus propias palabras o muy cerca."
        )
    )
    scct_expectativas_negativas: List[str] = Field(
        description=(
            "Lista de 2-4 barreras, miedos o creencias limitantes expresadas "
            "por el/la estudiante. Lenguaje estructural. "
            "Ej: 'Percibe que el costo económico de estudiar fuera hace "
            "inviable la continuidad post-media.'"
        )
    )
    scct_oportunidades_percibidas: List[str] = Field(
        description=(
            "Lista de 1-3 opciones formativas o técnicas locales que "
            "el/la estudiante reconoce en su territorio. "
            "Ej: 'Conoce el SENA del municipio como alternativa concreta.'"
        )
    )

    # Sección 5: Engagement
    estilo_interaccion: str = Field(
        description=(
            "Evaluación del engagement conversacional. "
            "Ej: 'Participación activa desde la primera sesión, respuestas "
            "elaboradas, mostró apertura emocional progresiva.' "
            "O: 'Respuestas monosilábicas al inicio, requirió alta validación "
            "narrativa y preguntas de andamiaje en sesión 2 para soltarse.'"
        )
    )

    # Semáforo de seguimiento
    nivel_alerta: str = Field(
        description=(
            "Exactamente uno de: 'regular', 'activo', 'prioritario'. "
            "Mapeo desde el motor de inferencia: "
            "RIESGO_BAJO → regular | RIESGO_MEDIO → activo | RIESGO_ALTO → prioritario."
        )
    )
    descripcion_nivel_alerta: str = Field(
        description=(
            "Párrafo que justifica el nivel usando lenguaje de condiciones "
            "estructurales. NUNCA adjetivar al estudiante. "
            "CORRECTO: 'El/la estudiante enfrenta una carga laboral que compite "
            "con el estudio y una red de apoyo adulto limitada.' "
            "INCORRECTO: 'Estudiante en riesgo', 'caso difícil'."
        )
    )
    factores_alerta: List[str] = Field(
        description=(
            "Lista de 2-4 condiciones estructurales que fundamentan el nivel. "
            "Solo si nivel_alerta es 'activo' o 'prioritario'. "
            "Vacío [] si es 'regular'."
        )
    )
    mostrar_espacio_seguimiento: bool = Field(
        description=(
            "True solo cuando nivel_alerta es 'activo' o 'prioritario'. "
            "False cuando es 'regular'."
        )
    )
    alerta_critica: Optional[AlertaCritica] = Field(
        default=None,
        description=(
            "Solo si hay indicios de riesgo psicológico grave "
            "(ideación suicida, maltrato, abuso, abandono). "
            "Null en todos los demás casos."
        )
    )
