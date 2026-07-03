"""
whatsapp_service.py — Módulo de re-engagement por WhatsApp (P14)

Envía mensajes automáticos a estudiantes que abandonaron su proceso de
orientación vocacional, usando Twilio WhatsApp API con plantillas aprobadas por Meta.

Requiere en secrets.toml:
    TWILIO_ACCOUNT_SID      = "..."
    TWILIO_AUTH_TOKEN       = "..."
    TWILIO_WHATSAPP_NUMBER  = "whatsapp:+57XXXXXXXXXX"
    APP_URL                 = "https://raiz-piloto.streamlit.app"

Reglas de activación (backlog PENDIENTE 14):
  MSG0 — Mensaje de bienvenida inmediata al registro
  MSG1 — día 1 tras registro, nunca entró al chat
  MSG2 — 2 días tras completar S1 sin iniciar S2
  MSG3 — 2 días tras completar S2 sin iniciar S3
  MSG4 — 2 días tras completar S3 sin iniciar S4
  MSG5 — 5 días sin actividad en cualquier punto, último intento
"""

import json
import logging
import re

import streamlit as st

# ── Content SIDs de plantillas aprobadas por Meta vía Twilio ─────────────────
# Variables: {{1}} = nombre, {{2}} = código de acceso, {{3}} = link
# raiz_cierre_mapa solo usa {{1}} = nombre (PDF va como media_url)

TEMPLATE_SIDS = {
    0: "HXf5921f1897d41091afa4bd56b4b13a9e",  # raiz_bienvenida
    1: "HXeef0228726a06013218e54b82f1e2f52",  # raiz_reengagement_1
    2: "HX54610034a30b26b0cd6945aff4f36f75",  # raiz_reengagement_2
    3: "HXaefd218a9d891ac92478f5b886af7f9c",  # raiz_reengagement_3
    4: "HX5e411595d949aa60525ed3a7180a1076",  # raiz_reengagement_4
    5: "HX3294acccd38d0b383b17b900769cb225",  # raiz_reengagement_5
    6: "HXcc6b4a10f5547921324aabde2079249a",  # raiz_cierre_mapa
}


def _normalizar_celular(celular: str) -> str:
    """Normaliza el número a formato E.164 asumiendo Colombia (+57)."""
    digits = re.sub(r"\D", "", celular)
    if len(digits) == 10 and digits.startswith("3"):
        return f"+57{digits}"
    if len(digits) == 12 and digits.startswith("57"):
        return f"+{digits}"
    return celular


def _get_link() -> str:
    """Retorna el link de la plataforma desde secrets o el default."""
    try:
        return st.secrets.get("APP_URL", "https://raiz-piloto.streamlit.app")
    except Exception:
        return "https://raiz-piloto.streamlit.app"


def _enviar_plantilla(
    celular: str,
    content_sid: str,
    variables: dict,
    media_url: str = None,
) -> bool:
    """
    Envía un mensaje WhatsApp vía Twilio usando una plantilla aprobada por Meta.
    variables: dict con keys "1", "2", "3" según las variables de la plantilla.
    Retorna True si fue exitoso.
    """
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
            "from_":             from_whatsapp,
            "to":                f"whatsapp:{celular_norm}",
            "content_sid":       content_sid,
            "content_variables": json.dumps(variables),
        }
        if media_url:
            kwargs["media_url"] = [media_url]

        client.messages.create(**kwargs)
        return True
    except Exception as e:
        logging.error("WhatsApp: error al enviar a %s*** — %s", celular[:4], e)
        return False


def enviar_bienvenida(celular: str, nombre: str, codigo: str) -> bool:
    """Envía el Mensaje Cero (Bienvenida Inmediata) tras el registro."""
    return _enviar_plantilla(
        celular=celular,
        content_sid=TEMPLATE_SIDS[0],
        variables={"1": nombre.split()[0], "2": codigo, "3": _get_link()},
    )


def preview_reengagement(database) -> list[dict]:
    """
    Retorna los mensajes que se enviarían sin enviar ni registrar nada.
    Cada dict: nombre, estudiante_id, celular (parcial), mensaje_numero, texto
    """
    candidatos = database.get_estudiantes_para_reengagement()
    result = []
    for c in candidatos:
        msg_num = c["mensaje_numero"]
        cel = c["celular"]
        result.append({
            "nombre":         c["nombre"],
            "estudiante_id":  c["estudiante_id"],
            "celular":        cel[:4] + "***" + cel[-2:] if len(cel) >= 6 else "***",
            "mensaje_numero": msg_num,
            "texto":          f"[Plantilla {msg_num}] → nombre={c['nombre'].split()[0]}, codigo={c['estudiante_id']}, link={_get_link()}",
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
        msg_num = c["mensaje_numero"]
        ok = _enviar_plantilla(
            celular=c["celular"],
            content_sid=TEMPLATE_SIDS[msg_num],
            variables={"1": c["nombre"].split()[0], "2": c["estudiante_id"], "3": _get_link()},
        )
        estado = "enviado" if ok else "fallido"
        database.registrar_whatsapp_mensaje(c["id"], msg_num, estado)
        if ok:
            enviados += 1
        else:
            fallidos += 1

    return {"enviados": enviados, "fallidos": fallidos, "total": len(candidatos)}


def enviar_mapa_estudiante(celular: str, nombre_estudiante: str, url_pdf: str) -> bool:
    """Envía el Mapa rAÍz (URL del PDF temporal) al estudiante vía WhatsApp."""
    return _enviar_plantilla(
        celular=celular,
        content_sid=TEMPLATE_SIDS[6],
        variables={"1": nombre_estudiante.split()[0]},
        media_url=url_pdf,
    )
