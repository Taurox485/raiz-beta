import streamlit as st 
from google import genai 
from google.genai import types 

st.set_page_config(page_title="rAÍz - Guía de Proyecto de Vida", page_icon="🌱", layout="centered")
st.title("🌱 rAÍz")
st.subheader("Tu Guía de Proyecto de Vida")

# --- SEGURIDAD: LEYENDO DE LA BÓVEDA ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("Falta configurar la API KEY en .streamlit/secrets.toml")
    st.stop()

@st.cache_resource
def obtener_cliente():
    return genai.Client(api_key=API_KEY)

client = obtener_cliente()

# --- INYECCIÓN DEL CEREBRO ---
def load_instructions():
    try:
        with open("instrucciones.txt", "r", encoding="utf-8") as file:
            content = file.read().strip() 
            if not content: 
                return "Eres un asistente útil. (Nota: Archivo vacío)."
            return content
    except FileNotFoundError:
        return "Eres un asistente útil. (Nota: Archivo no encontrado)."

system_instruction = load_instructions()

# --- MEMORIA DEL CHAT Y VARIABLES DE ESTADO ---
if "chat_session" not in st.session_state:
    st.session_state.chat_session = client.chats.create(
        model="gemini-3.1-pro-preview",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.5,
        )
    )
    # Saludo actualizado para coincidir con la Sesión 1, Momento 1 de tus nuevas instrucciones
    mensaje_inicial = "¡Hola! Soy rAÍz. Para irnos conociendo, cuéntame: un día normal tuyo, de lunes a viernes después de que suena la campana de salida, ¿cómo es? ¿Qué es lo primero que haces al llegar a la casa?"
    st.session_state.history_ui = [{"role": "model", "text": mensaje_inicial}]

if "fin_consejeria" not in st.session_state:
    st.session_state.fin_consejeria = False

# --- FUNCIÓN LIMPIADORA DE ETIQUETAS ---
# Logic: This function "vacuums" hidden tags so the student never sees them.
# It now includes the new "Nota interna" variations and removes empty parentheses.
def limpiar_etiquetas(texto):
    etiquetas_ocultas = [
        "[FIN_CONSEJERIA]", 
        "[RIESGO_BAJO]", "[RIESGO_MEDIO]", "[RIESGO_ALTO]", 
        "[ALERTA_ORIENTADOR_REQUERIDA]", "[ALERTA_PSICOLOGICA_CRITICA]",
        "(Nota interna de rAÍz: )", "(Nota interna de rAÍz:)", "Nota interna:"
    ]
    
    # Loop through the list of tags and replace them with nothing (empty string)
    for etiqueta in etiquetas_ocultas:
        texto = texto.replace(etiqueta, "")
        
    # Final cleanup: Remove any leftover empty parentheses and trim extra spaces
    texto = texto.replace("()", "").strip()
    return texto

# Logic: Loop through the visual history and draw each message on the screen,
# passing the model's text through the vacuum function first.
for message in st.session_state.history_ui:
    with st.chat_message("assistant" if message["role"] == "model" else "user"):
        st.markdown(limpiar_etiquetas(message["text"]))

        
# --- INTERACCIÓN ---
user_input = st.chat_input("Escribe tu respuesta aquí...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.history_ui.append({"role": "user", "text": user_input}) 

    with st.chat_message("assistant"):
        try:
            response = st.session_state.chat_session.send_message(user_input)
            
            # --- MANEJO DE ALERTAS (BACKEND / POWERSHELL) ---
            # Las nuevas alertas configuradas en tu prompt
            if "[ALERTA_ORIENTADOR_REQUERIDA]" in response.text:
                print("\n" + "="*50)
                print("🚨 [SISTEMA BACKEND] ALERTA DE DESERCIÓN DETECTADA")
                print("🚨 El estudiante expresó intención inminente de abandono escolar.")
                print("="*50 + "\n")
                
            if "[ALERTA_PSICOLOGICA_CRITICA]" in response.text:
                print("\n" + "="*50)
                print("🚨 [SISTEMA BACKEND] ALERTA PSICOLÓGICA CRÍTICA DETECTADA")
                print("🚨 Posible mención de abuso, violencia o crisis de salud mental.")
                print("="*50 + "\n")

            if "[FIN_CONSEJERIA]" in response.text:
                st.session_state.fin_consejeria = True

            # Limpieza visual y renderizado en pantalla
            display_response = limpiar_etiquetas(response.text)
            st.markdown(display_response)
            st.session_state.history_ui.append({"role": "model", "text": response.text}) 

        except Exception as e:
            st.error(f"Error de conexión. Detalles: {e}")

# --- RENDERIZADO SEGURO DE BOTONES ---
if st.session_state.fin_consejeria:
    st.success("¡Has completado tu mapa de exploración rAÍz!")
    if st.button("📥 Descargar Mis Reportes"):
        st.info("Conectando con el motor de generación de PDFs...")