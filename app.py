import streamlit as st

# ── Configuración de página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="rAÍz - Guía de Proyecto de Vida",
    page_icon="🌱",
    layout="wide",
)

# ── Admin gate ─────────────────────────────────────────────────────────────────
# Evaluar antes de cualquier import pesado para evitar efectos secundarios
# en el primer render de Streamlit Cloud.
# query_params puede retornar str o list según versión — normalizamos.
_admin_val = st.query_params.get("admin", "")
if isinstance(_admin_val, list):
    _admin_val = _admin_val[0] if _admin_val else ""
if _admin_val == "1":
    from admin_dashboard import mostrar_dashboard_admin
    mostrar_dashboard_admin()
    st.stop()

from google import genai
from google.genai import types

import auth
import database as db

# ── Cliente Gemini ─────────────────────────────────────────────────────────────
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("Falta configurar GEMINI_API_KEY en .streamlit/secrets.toml")
    st.stop()

MODEL = "gemini-3.1-flash-lite"

@st.cache_resource
def obtener_cliente():
    return genai.Client(api_key=API_KEY)

client = obtener_cliente()

# ── System prompt ──────────────────────────────────────────────────────────────
@st.cache_data
def load_instructions() -> str:
    try:
        with open("instrucciones.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
            return content if content else "Eres un asistente útil. (Nota: Archivo vacío)."
    except FileNotFoundError:
        return "Eres un asistente útil. (Nota: Archivo no encontrado)."

system_instruction = load_instructions()

# ── Autenticación ──────────────────────────────────────────────────────────────
# Si el estudiante no está autenticado, mostrar pantallas de auth y detener el render.
if not auth.esta_autenticado():
    st.title("🌱 rAÍz")
    st.subheader("Tu Guía de Proyecto de Vida")
    auth.mostrar_pantalla_auth()
    st.stop()

# ── A partir de aquí: estudiante autenticado ──────────────────────────────────
estudiante = st.session_state.estudiante

# Guard de acudiente: auth.py ya bloquea esto, pero lo verificamos aquí también
# por si el registro viene de una sesión anterior al piloto.
if not estudiante.get("consentimiento_acudiente_verificado"):
    st.error(
        "Tu perfil está pendiente de activación por parte de tu institución. "
        "Pedile a tu orientador/a que habilite tu acceso."
    )
    st.stop()

st.markdown(
    "<style>.block-container{max-width:800px !important;padding-left:2rem !important;"
    "padding-right:2rem !important;}</style>",
    unsafe_allow_html=True,
)
st.title("🌱 rAÍz")
st.caption(f"**{estudiante['nombre']}** · ID: `{estudiante['estudiante_id']}`")

# ── Limpiador de etiquetas internas ───────────────────────────────────────────
# Las etiquetas se eliminan solo en pantalla. En DB se guarda el texto crudo
# para que Gemini pueda reconstruir coherentemente el contexto al retomar.
def limpiar_etiquetas(texto: str) -> str:
    for etiqueta in [
        "[FIN_CONSEJERIA]",
        "[RIESGO_BAJO]", "[RIESGO_MEDIO]", "[RIESGO_ALTO]",
        "[ALERTA_ORIENTADOR_REQUERIDA]", "[ALERTA_PSICOLOGICA_CRITICA]",
        "(Nota interna de rAÍz: )", "(Nota interna de rAÍz:)", "Nota interna:",
    ]:
        texto = texto.replace(etiqueta, "")
    return texto.replace("()", "").strip()

# ── Inicialización del chat ────────────────────────────────────────────────────
# Keyed por UUID del estudiante para que dos usuarios distintos en la misma
# instancia Streamlit no compartan sesión de Gemini.
CHAT_KEY = f"chat_{estudiante['id']}"

SALUDO_INICIAL = (
    "¡Hola! Soy rAÍz, tu mentor de proyecto de vida 🌱 "
    "Soy una inteligencia artificial — un programa diseñado para acompañarte — "
    "pero estoy aquí para escucharte de verdad. "
    "Vamos a tener 4 conversaciones — cortitas, sin afán — "
    "donde vamos a ir descubriendo juntos quién sos: "
    "qué te gusta, qué se te da bien, cómo es tu mundo. "
    "No hay respuestas buenas ni malas. "
    "Lo que hablemos queda guardado de forma segura. "
    "Tu profe orientador/a va a recibir un resumen de tus fortalezas e intereses — "
    "no una copia de toda la conversación. "
    "Lo que sea muy personal queda entre nosotros. "
    "Y si algún día querés que borremos todo, podés pedírselo a tu orientador/a. "
    "¿Listo/a para arrancar?"
)

if CHAT_KEY not in st.session_state:
    historial_db = db.get_historial(estudiante["id"])

    if historial_db:
        # Retoma de sesión: reconstruir el contexto completo de Gemini.
        # Se pasa el historial crudo (con etiquetas internas) para que el modelo
        # mantenga coherencia sobre perfil de riesgo y avance pedagógico.
        gemini_history = [
            types.Content(
                role=msg["rol"],
                parts=[types.Part(text=msg["contenido"])],
            )
            for msg in historial_db
        ]
        st.session_state[CHAT_KEY] = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.5,
            ),
            history=gemini_history,
        )
        st.session_state.history_ui = [
            {"role": msg["rol"], "text": msg["contenido"]}
            for msg in historial_db
        ]
    else:
        # Primera sesión: chat limpio y saludo inicial guardado en DB.
        st.session_state[CHAT_KEY] = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.5,
            ),
        )
        st.session_state.history_ui = [{"role": "model", "text": SALUDO_INICIAL}]
        db.guardar_mensaje(
            estudiante_uuid=estudiante["id"],
            sesion=estudiante.get("sesion_actual", 1),
            rol="model",
            contenido=SALUDO_INICIAL,
        )

if "fin_consejeria" not in st.session_state:
    # Inicializar desde DB por si la mentoría fue completada en una sesión anterior.
    st.session_state.fin_consejeria = bool(estudiante.get("mentoria_completada", False))

# ── Render del historial ───────────────────────────────────────────────────────
for message in st.session_state.history_ui:
    with st.chat_message("assistant" if message["role"] == "model" else "user"):
        st.markdown(limpiar_etiquetas(message["text"]))

# ── Interacción ───────────────────────────────────────────────────────────────
user_input = st.chat_input("Escribe tu respuesta aquí...")

if user_input and not st.session_state.fin_consejeria:
    sesion_actual = st.session_state.estudiante.get("sesion_actual", 1)

    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.history_ui.append({"role": "user", "text": user_input})
    db.guardar_mensaje(
        estudiante_uuid=estudiante["id"],
        sesion=sesion_actual,
        rol="user",
        contenido=user_input,
    )

    with st.chat_message("assistant"):
        try:
            response = st.session_state[CHAT_KEY].send_message(user_input)
            raw = response.text
            tiene_alerta = False

            # ── Alertas → DB ───────────────────────────────────────────────
            # Reemplaza los print() del código original. El orientador consulta
            # estas alertas desde su futuro dashboard (Fase 2).
            if "[ALERTA_ORIENTADOR_REQUERIDA]" in raw:
                tiene_alerta = True
                db.crear_alerta(
                    estudiante_uuid=estudiante["id"],
                    sede_id=estudiante["sede_id"],
                    tipo="orientador_requerida",
                )
            if "[ALERTA_PSICOLOGICA_CRITICA]" in raw:
                tiene_alerta = True
                alerta_id = db.crear_alerta(
                    estudiante_uuid=estudiante["id"],
                    sede_id=estudiante["sede_id"],
                    tipo="psicologica_critica",
                )
                # Tres destinatarios simultáneos (PENDIENTE 2 — Política PEAS)
                orientador_email = db.get_orientador_email(estudiante["sede_id"])
                rector_email     = db.get_rector_email(estudiante["sede_id"])
                peas_email       = st.secrets.get("PEAS_EMAIL", "")
                try:
                    import email_service
                    resultados = email_service.enviar_alerta_critica(
                        orientador_email=orientador_email,
                        rector_email=rector_email,
                        peas_email=peas_email,
                        nombre_estudiante=(
                            f"{estudiante['nombre']} {estudiante['apellido']}"
                        ),
                        estudiante_id=estudiante["estudiante_id"],
                    )
                    db.update_notificaciones_alerta(alerta_id, **resultados)
                except Exception:
                    pass  # La alerta quedó en DB; el reintento es responsabilidad del dashboard

            # ── Perfil de riesgo → DB ──────────────────────────────────────
            # El motor de inferencia del prompt emite a lo sumo una etiqueta
            # de riesgo por turno. Se evalúa de mayor a menor para capturar
            # siempre el nivel más grave si aparecen varias.
            for tag, nivel in [
                ("[RIESGO_ALTO]",  "alto"),
                ("[RIESGO_MEDIO]", "medio"),
                ("[RIESGO_BAJO]",  "bajo"),
            ]:
                if tag in raw:
                    db.update_perfil_riesgo(estudiante["id"], nivel)
                    st.session_state.estudiante["perfil_riesgo"] = nivel
                    break

            # ── Fin de mentoría → DB ───────────────────────────────────────
            if "[FIN_CONSEJERIA]" in raw:
                st.session_state.fin_consejeria = True
                db.set_mentoria_completada(estudiante["id"])
                st.session_state.estudiante["mentoria_completada"] = True

            # ── Guardar respuesta y renderizar ─────────────────────────────
            db.guardar_mensaje(
                estudiante_uuid=estudiante["id"],
                sesion=sesion_actual,
                rol="model",
                contenido=raw,
                tiene_alerta=tiene_alerta,
            )
            st.session_state.history_ui.append({"role": "model", "text": raw})
            st.markdown(limpiar_etiquetas(raw))

        except Exception as e:
            st.error(f"Error de conexión. Detalles: {e}")

# ── Pantalla de cierre ─────────────────────────────────────────────────────────
if st.session_state.fin_consejeria:
    st.success("¡Has completado tu mapa de exploración rAÍz!")
    if st.button("📥 Descargar mi Perfil de Talentos"):
        with st.spinner("Generando tu Mapa rAÍz... esto toma unos segundos ⏳"):
            try:
                import pdf_generator
                pdf_est, pdf_ori = pdf_generator.generar_pdfs(
                    estudiante=st.session_state.estudiante,
                    historial=db.get_historial(st.session_state.estudiante["id"]),
                    client=client,
                    model=MODEL,
                    system_instruction=system_instruction,
                )
                nombre = f"{st.session_state.estudiante.get('nombre', 'estudiante')}".lower().replace(' ', '_')
                st.download_button(
                    label="📄 Descargar Mi Mapa rAÍz (PDF)",
                    data=pdf_est,
                    file_name=f"mapa_raiz_{nombre}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success("¡Tu Mapa rAÍz está listo! Descárgalo arriba.")
                st.session_state["pdf_orientador"] = pdf_ori

                # Enviar ficha al orientador por email
                orientador_email = None
                try:
                    from email_service import enviar_ficha_orientador
                    sede_info = db.get_sede_info(st.session_state.estudiante.get("sede_id", 0))
                    orientador_email = sede_info.get("orientador_email") if sede_info else None
                    if orientador_email:
                        nombre_est = f"{st.session_state.estudiante.get('nombre','')} {st.session_state.estudiante.get('apellido','')}".strip()
                        exito = enviar_ficha_orientador(
                            destinatario=orientador_email,
                            nombre_estudiante=nombre_est,
                            pdf_bytes=pdf_ori,
                        )
                        db.registrar_envio_ficha(
                            estudiante_id=st.session_state.estudiante["id"],
                            orientador_email=orientador_email,
                            exito=exito,
                        )
                except Exception as e_email:
                    st.warning(f"DEBUG email error: {e_email}")
                    try:
                        db.registrar_envio_ficha(
                            estudiante_id=st.session_state.estudiante["id"],
                            orientador_email=orientador_email if orientador_email else "desconocido",
                            exito=False,
                        )
                    except Exception:
                        pass
            except Exception as e:
                st.error(f"Hubo un problema generando el PDF. Intenta de nuevo o pídele ayuda a tu orientador/a. ({e})")
