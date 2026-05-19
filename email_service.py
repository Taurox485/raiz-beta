"""
email_service.py — Emails transaccionales de rAÍz

Usa SMTP de Gmail con contraseña de aplicación (ver secrets.toml para instrucciones).
Ambas funciones públicas lanzan excepción si el envío falla — auth.py captura
esa excepción y activa el fallback de mostrar el ID directamente en pantalla.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st


def _config() -> dict:
    return {
        "host":     "smtp.gmail.com",
        "port":     587,
        "user":     st.secrets["SMTP_EMAIL"],
        "password": st.secrets["SMTP_APP_PASSWORD"],
    }


def _enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    cfg = _config()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"rAÍz <{cfg['user']}>"
    msg["To"]      = destinatario
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    with smtplib.SMTP(cfg["host"], cfg["port"]) as servidor:
        servidor.starttls()
        servidor.login(cfg["user"], cfg["password"])
        servidor.sendmail(cfg["user"], destinatario, msg.as_string())


def enviar_id_registro(email: str, nombre: str, estudiante_id: str) -> None:
    """
    Envía el ID recién generado al correo del estudiante tras el registro exitoso.
    Si falla, lanza la excepción para que auth.py muestre el ID en pantalla.
    """
    cuerpo = f"""\
¡Hola, {nombre}!

Bienvenido/a a rAÍz, tu guía de proyecto de vida.

Tu ID de rAÍz es:

    {estudiante_id}

Guárdalo bien — lo necesitarás cada vez que quieras retomar
tu proceso de orientación.

¡Nos vemos adentro!
El equipo rAÍz
"""
    _enviar(email, "Tu ID de rAÍz — guárdalo", cuerpo)


def enviar_id_recuperacion(email: str, nombre: str, estudiante_id: str) -> None:
    """
    Envía el ID al correo del estudiante en el flujo 'Olvidé mi ID'.
    Si falla, lanza la excepción para que auth.py muestre el ID en pantalla.
    """
    cuerpo = f"""\
¡Hola, {nombre}!

Pediste recuperar tu ID de rAÍz. Aquí está:

    {estudiante_id}

Úsalo para continuar tu proceso de orientación.

Si tú no pediste esto, ignora este mensaje.

El equipo rAÍz
"""
    _enviar(email, "Recuperación de ID — rAÍz", cuerpo)
