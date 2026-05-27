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


def enviar_bienvenida(email: str, nombre: str, estudiante_id: str) -> None:
    """
    Envía el email de bienvenida inmediata (Mensaje Cero) tras el registro.
    Tono alineado con el mensaje de WhatsApp.
    """
    try:
        link = st.secrets.get("APP_URL", "https://raiz-piloto.streamlit.app")
    except Exception:
        link = "https://raiz-piloto.streamlit.app"

    cuerpo = f"""\
¡Hola, {nombre.split()[0]}! 🌱

Soy rAÍz, tu mentor de proyecto de vida. Tu orientador/a ya dejó tu cuenta lista para que empecemos este viaje.

Vamos a tener 4 charlas cortitas para descubrir qué te mueve, en qué sos bueno/a y qué imaginás para tu futuro. No hay respuestas correctas o incorrectas, solo queremos conocerte mejor.

Tu código de acceso único es:

    {estudiante_id}

¿Listo/a para arrancar? Entrá acá:
{link}

¡Nos vemos adentro!
El equipo rAÍz
"""
    _enviar(email, "🌱 ¡Bienvenido/a a rAÍz! — Tu código de acceso", cuerpo)


def enviar_id_registro(email: str, nombre: str, estudiante_id: str) -> None:
    """
    Wrapper de enviar_bienvenida para mantener compatibilidad con llamadas existentes.
    """
    enviar_bienvenida(email, nombre, estudiante_id)


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


def enviar_ficha_orientador(destinatario: str, nombre_estudiante: str, pdf_bytes: bytes) -> bool:
    """Envía la ficha de acompañamiento al orientador como adjunto PDF."""
    try:
        from email.mime.application import MIMEApplication
        cfg = _config()

        msg = MIMEMultipart()
        msg["From"] = f"rAÍz <{cfg['user']}>"
        msg["To"] = destinatario
        msg["Subject"] = f"rAÍz — Ficha de Acompañamiento: {nombre_estudiante}"

        cuerpo = f"""\
Estimado/a docente orientador/a,

{nombre_estudiante} ha completado su proceso de mentoría con rAÍz.

Adjunto encontrará la Ficha de Acompañamiento con el perfil de intereses,
fortalezas identificadas, contexto de vida y acciones sugeridas para su
acompañamiento.

Este documento es confidencial y de uso exclusivo del equipo docente.

— rAÍz · Mentoría de proyecto de vida · Piloto Valle del Cauca 2026"""

        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        filename = f"ficha_orientador_{nombre_estudiante.replace(' ', '_').lower()}.pdf"
        adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
        adjunto.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(adjunto)

        with smtplib.SMTP(cfg["host"], cfg["port"]) as servidor:
            servidor.starttls()
            servidor.login(cfg["user"], cfg["password"])
            servidor.sendmail(cfg["user"], destinatario, msg.as_string())

        return True
    except Exception as e:
        print(f"ERROR ENVIANDO FICHA ORIENTADOR: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return False
