"""
email_service.py — Emails transaccionales de rAÍz

Usa SMTP de Gmail con contraseña de aplicación (ver secrets.toml para instrucciones).
Ambas funciones públicas lanzan excepción si el envío falla — auth.py captura
esa excepción y activa el fallback de mostrar el ID directamente en pantalla.
"""

import smtplib
import threading
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import streamlit as st

_COLOMBIA = timezone(timedelta(hours=-5))


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
    msg["Subject"] = Header(asunto, "utf-8")
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


def enviar_alerta_critica(
    orientador_email: Optional[str],
    rector_email: Optional[str],
    peas_email: Optional[str],
    nombre_estudiante: str,
    estudiante_id: str,
) -> dict:
    """
    Envía la alerta psicológica crítica simultáneamente a tres destinatarios
    usando hilos paralelos (threading). Máximo 15 segundos de espera por hilo.

    Retorna {"orientador": bool, "rector": bool, "peas": bool}.
    Si un email es None o vacío, ese destinatario se marca False sin intentar el envío.
    Nunca lanza excepción — los fallos quedan registrados en el dict de retorno
    para que app.py pueda persistirlos en la tabla alertas vía update_notificaciones_alerta().
    """
    ahora = datetime.now(_COLOMBIA).strftime("%d/%m/%Y a las %H:%M (hora Colombia)")
    asunto = f"🔴 Alerta crítica rAÍz — {nombre_estudiante} ({estudiante_id})"
    cuerpo = f"""\
ALERTA CRÍTICA — rAÍz Orientación Vocacional
{'=' * 56}

Estudiante : {nombre_estudiante}
ID         : {estudiante_id}
Fecha      : {ahora}

{'=' * 56}
ACCIÓN REQUERIDA

Este estudiante requiere atención inmediata.
Por favor comuníquese con él/ella en las próximas 24 horas
y active los protocolos institucionales correspondientes.

{'=' * 56}
LÍNEAS DE CRISIS (disponibles las 24 horas)

  • Línea 106 — Salud mental y apoyo emocional
  • Línea 141 — ICBF, protección de niñas, niños y adolescentes

{'=' * 56}
CONFIDENCIALIDAD

Este mensaje contiene información sensible sobre un menor de edad.
Comparta su contenido únicamente con las personas autorizadas
según los protocolos de su institución.

Este mensaje fue generado automáticamente por el sistema rAÍz.
No responda a este correo.
"""

    resultados: dict = {"orientador": False, "rector": False, "peas": False}

    def _intentar(clave: str, email: Optional[str]) -> None:
        if not email or not str(email).strip():
            return
        try:
            _enviar(str(email).strip(), asunto, cuerpo)
            resultados[clave] = True
        except Exception:
            pass  # resultados[clave] permanece False

    hilos = [
        threading.Thread(target=_intentar, args=("orientador", orientador_email), daemon=True),
        threading.Thread(target=_intentar, args=("rector",     rector_email),     daemon=True),
        threading.Thread(target=_intentar, args=("peas",       peas_email),       daemon=True),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=15)

    return resultados
