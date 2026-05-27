"""
whatsapp_service.py — Módulo de re-engagement por WhatsApp (P14)

Envía mensajes automáticos a estudiantes que abandonaron su proceso de
orientación vocacional, usando Twilio WhatsApp API.

Requiere en secrets.toml:
    TWILIO_ACCOUNT_SID     = "..."
    TWILIO_AUTH_TOKEN      = "..."
    TWILIO_WHATSAPP_NUMBER = "whatsapp:+57XXXXXXXXXX"
    APP_URL                = "https://raiz-piloto.streamlit.app"

Reglas de activación (backlog PENDIENTE 14):
  MSG0 — Mensaje de bienvenida inmediata al registro
  MSG1 — día 1 tras registro, nunca entró al chat
  MSG2 — 2 días tras completar S1 sin iniciar S2
  MSG3 — 2 días tras completar S2 sin iniciar S3
  MSG4 — 2 días tras completar S3 sin iniciar S4
  MSG5 — 5 días sin actividad en cualquier punto, último intento
"""

import logging
import re

import streamlit as st

MENSAJES = {
    0: "¡Hola, {nombre}! Soy rAÍz, tu mentor de proyecto de vida. Ya dejamos tu cuenta lista para que empecemos este viaje. Vamos a tener 4 charlas para descubrir qué te mueve, en qué sos bueno/a y qué imaginás para tu futuro. Tu código de acceso único es: {codigo} ¿Listo/a para arrancar? Entrá acá: {link}",
    1: "Hola {nombre} Ya tienes tu cuenta en rAÍz lista. Ingresa con tu código {codigo} en {link} y empieza a explorar tu proyecto de vida. ¡Te esperamos!",
    2: "¡Hola, {nombre}! La última vez hablamos de tu día a día y de las cosas que te mueven. Me quedé con ganas de seguir conociéndote En la próxima charla vamos a seguir conversando sobre ti. ¡Quiero saber más de ti! Tu código: {codigo} ¿Seguimos? Entrá acá: {link}",
    3: "¡Hola, {nombre}! Ya descubriste cosas importantes sobre vos. Ahora sigue otra parte muy interesante: hablar de lo que imaginás para tu futuro Tu código: {codigo} ¿Le damos? Entrá acá: {link}",
    4: "Hola {nombre}, ¡ya casi terminás! Solo falta una sesión en rAÍz. Entrá con {codigo} en {link} y obtén tu Mapa rAÍz personalizado.",
    5: "Hola {nombre}, tu recorrido en rAÍz te espera Ingresá cuando puedas con tu código {codigo} en {link}. Tu orientador/a también está pendiente de ti.",
}


def _normalizar_celular(celular: str) -> str:
    """Normaliza el número a formato E.164 asumiendo Colombia (+57)."""
    digits = re.sub(r"\D", "", celular)
    if len(digits) == 10 and digits.startswith("3"):
        return f"+57{digits}"
    if len(digits) == 12 and digits.startswith("57"):
        return f"+{digits}"
    return celular


def _enviar_mensaje(celular: str, texto: str, media_url: str = None) -> bool:
    """Envía un mensaje WhatsApp vía Twilio. Retorna True si fue exitoso."""
    try:
        account_sid   = st.secrets["TWILIO_ACCOUNT_SID"]
        auth_token    = st.secrets["TWILIO_AUTH_TOKEN"]
        from_whatsapp = st.secrets["TWILIO_WHATSAPP_NUMBER"]
    except KeyError as e:
        logging.error("WhatsApp: secret faltante — %s", e)
        return False

    try:
        from twilio.rest import Client
        celular_norm = _normalizar_celular(celular)
        client = Client(account_sid, auth_token)
        kwargs = {
            "from_": from_whatsapp,
            "to": f"whatsapp:{celular_norm}",
            "body": texto,
        }
        if media_url:
            kwargs["media_url"] = [media_url]
            
        client.messages.create(**kwargs)
        return True
    except Exception as e:
        logging.error("WhatsApp: error al enviar a %s*** — %s", celular[:4], e)
        return False


def _formatear(template: str, nombre: str, codigo: str) -> str:
    try:
        link = st.secrets.get("APP_URL", "https://raiz-piloto.streamlit.app")
    except Exception:
        link = "https://raiz-piloto.streamlit.app"
    return template.format(nombre=nombre.split()[0], codigo=codigo, link=link)


def enviar_bienvenida(celular: str, nombre: str, codigo: str) -> bool:
    """Envía el Mensaje Cero (Bienvenida Inmediata) tras el registro."""
    texto = _formatear(MENSAJES[0], nombre, codigo)
    return _enviar_mensaje(celular, texto)


def preview_reengagement(database) -> list[dict]:
    """
    Retorna los mensajes que se enviarían sin enviar ni registrar nada.
    Cada dict: nombre, estudiante_id, celular (parcial), mensaje_numero, texto
    """
    candidatos = database.get_estudiantes_para_reengagement()
    result = []
    for c in candidatos:
        texto = _formatear(MENSAJES[c["mensaje_numero"]], c["nombre"], c["estudiante_id"])
        cel = c["celular"]
        result.append({
            "nombre":         c["nombre"],
            "estudiante_id":  c["estudiante_id"],
            "celular":        cel[:4] + "***" + cel[-2:] if len(cel) >= 6 else "***",
            "mensaje_numero": c["mensaje_numero"],
            "texto":          texto,
        })
    return result


def procesar_reengagement(database) -> dict:
    """
    Envía mensajes de re-engagement a todos los candidatos elegibles.
    Registra cada envío (exitoso o fallido) en whatsapp_mensajes.
    Retorna: {enviados, fallidos, total}
    """
    candidatos = database.get_estudiantes_para_reengagement()
    enviados = 0
    fallidos = 0

    for c in candidatos:
        texto = _formatear(MENSAJES[c["mensaje_numero"]], c["nombre"], c["estudiante_id"])
        ok = _enviar_mensaje(c["celular"], texto)
        estado = "enviado" if ok else "fallido"
        database.registrar_whatsapp_mensaje(c["id"], c["mensaje_numero"], estado)
        if ok:
            enviados += 1
        else:
            fallidos += 1

    return {"enviados": enviados, "fallidos": fallidos, "total": len(candidatos)}


def enviar_mapa_estudiante(celular: str, nombre_estudiante: str, url_pdf: str) -> bool:
    """Envía el Mapa rAÍz (URL del PDF temporal) al estudiante vía WhatsApp."""
    texto = f"¡Felicitaciones, {nombre_estudiante.split()[0]}! \n\nHas completado tu proceso de mentoría con rAÍz Aquí te compartimos tu Mapa rAÍz con el resumen de todo lo que descubrimos juntos.\n\n¡Mucho éxito en tu camino!"
    return _enviar_mensaje(celular, texto, media_url=url_pdf)
