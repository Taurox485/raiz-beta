"""
auth.py — Flujos de autenticación para rAÍz

Flujo estudiante (post-migración 002):
  _inicio
      → _login → _verificar_y_autenticar
                      ↓ acudiente no verificado  → error bloqueante (pide al orientador)
                      ↓ asentimiento pendiente   → _asentimiento_estudiante → _autenticar
                      ↓ todo OK                  → _autenticar

El registro de estudiantes ya no existe en este flujo.
Lo realiza un administrador autorizado desde el dashboard (Fase 2 / PENDIENTE 6).

API pública:
  esta_autenticado() → bool
  mostrar_pantalla_auth() → None

Cuando el estudiante se autentica exitosamente, escribe
st.session_state.estudiante (dict completo del estudiante).
app.py solo necesita llamar estas dos funciones.
"""

import re
import streamlit as st
import database as db


# ── Helpers ────────────────────────────────────────────────────────────────────

def _email_valido(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def _vista() -> str:
    return st.session_state.get("auth_vista", "inicio")


def _ir_a(vista: str, **datos):
    """Cambia la pantalla activa y persiste datos de formulario entre pasos."""
    st.session_state.auth_vista = vista
    for k, v in datos.items():
        st.session_state[f"auth_{k}"] = v
    st.rerun()


# ── Pantalla: inicio ───────────────────────────────────────────────────────────

def _inicio():
    st.markdown("## Bienvenido/a a rAÍz 🌱")
    st.markdown("Tu guía de proyecto de vida.")
    st.info(
        "Tu orientador/a o el equipo de tu colegio te entregó un **ID de rAÍz**. "
        "Con ese código podés ingresar directamente.",
        icon="ℹ️",
    )
    st.markdown("")

    if st.button("🔑 Ingresar con mi ID", use_container_width=True, type="primary"):
        _ir_a("login")

    st.markdown("---")
    if st.button("¿Olvidaste tu ID? Recupéralo aquí"):
        _ir_a("olvide_id")


# ── Pantalla: login ────────────────────────────────────────────────────────────

def _login():
    st.markdown("## Ingresá con tu ID")

    est_id_input = st.text_input(
        "Tu ID de rAÍz",
        placeholder="Ej: ALC-9-2026-0042",
        help="El ID que te entregó tu orientador/a o el equipo de tu colegio",
        key="login_id_input",
    )

    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="login_volver"):
            _ir_a("inicio")
    with c_next:
        if st.button("Entrar →", type="primary", use_container_width=True, key="login_submit"):
            if not est_id_input.strip():
                st.error("Escribí tu ID para continuar.")
                return

            estudiante = db.login_estudiante(est_id_input.strip())

            if estudiante is None:
                st.error(
                    f"No encontré el ID **{est_id_input.strip().upper()}**. "
                    "Revisá que esté escrito exactamente igual a como lo recibiste."
                )
            else:
                _verificar_y_autenticar(estudiante)

    st.markdown("---")
    if st.button("No recuerdo mi ID — recupéralo aquí", key="login_olvide"):
        _ir_a("olvide_id")


# ── Lógica: verificar condiciones previas al chat ─────────────────────────────

def _verificar_y_autenticar(estudiante: dict):
    """
    Punto único de control entre el login y el chat.
    Evalúa en orden:
      1. consentimiento_acudiente_verificado — si False, bloquea con mensaje al orientador
      2. asentimiento_estudiante             — si False, lleva a la pantalla de asentimiento
      3. Todo OK                             — autentica directamente
    """
    if not estudiante.get("consentimiento_acudiente_verificado"):
        st.error(
            "Tu perfil todavía no está habilitado. "
            "Pedile a tu orientador/a que active tu acceso antes de ingresar."
        )
        st.caption(
            "Cuando el orientador/a certifique que tu acudiente firmó la autorización, "
            "podrás entrar con este mismo ID."
        )
        return

    if not estudiante.get("asentimiento_estudiante"):
        _ir_a("asentimiento", estudiante=estudiante)
    else:
        _autenticar(estudiante)


# ── Pantalla: asentimiento informado del estudiante ───────────────────────────

def _asentimiento_estudiante():
    """
    Primera vez que el estudiante ingresa: muestra el asentimiento informado
    en lenguaje simple (14-16 años) antes de dar acceso al chat.
    Implementa dos checkboxes diferenciados (Ley 1581 Art. 6 + PENDIENTE 7).
    """
    estudiante = st.session_state.get("auth_estudiante")
    if not estudiante:
        _ir_a("login")
        return

    nombre = estudiante.get("nombre", "")
    st.markdown(f"## Hola, {nombre} 👋")
    st.markdown(
        "Antes de empezar tu proceso en rAÍz, leé esto con calma "
        "y decinos si estás de acuerdo."
    )

    with st.expander("📄 ¿Qué va a pasar con tu información? (leé antes de aceptar)"):
        st.markdown(
            """
**¿Qué guardamos?**
- Tu nombre y los datos de tu colegio y grado
- Las conversaciones del proceso (para que puedas retomarlo donde lo dejaste)
- Un perfil de orientación basado en lo que hablemos: intereses, fortalezas, ideas de futuro

**¿Para qué se usa?**
- Para que puedas continuar el proceso si cerrás la página
- Para que tu orientador/a pueda acompañarte mejor en los próximos años
- Para que, al finalizar, tengás un resumen tuyo de fortalezas e intereses

**¿Qué NO guardamos?**
- Tu dirección o ubicación exacta
- Información de tu familia más allá de lo que vos decidás contar

**Tus derechos:**
Podés pedir que borremos toda tu información cuando quieras.
Solo tenés que pedírselo a tu orientador/a y ellos se encargan.
Tu acudiente ya autorizó este proceso — esta pantalla es tu propia decisión.
            """
        )

    st.markdown("---")
    st.markdown("**Para continuar, necesitamos que aceptes las dos opciones de abajo:**")
    st.markdown("")

    acepta_general = st.checkbox(
        "✅ Acepto que rAÍz guarde la información de mi proceso de orientación "
        "(conversaciones, perfil de intereses y fortalezas).",
        key="asent_general",
    )
    acepta_sensibles = st.checkbox(
        "✅ Acepto que, si lo menciono durante el proceso, rAÍz pueda guardar "
        "información sobre mi situación personal (estado de ánimo, situación económica). "
        "Esta información solo la ve mi orientador/a si hay algo importante que atender.",
        key="asent_sensibles",
    )

    ambos_aceptados = acepta_general and acepta_sensibles

    if not ambos_aceptados:
        st.caption("Necesitás marcar las dos opciones para poder continuar.")

    st.markdown("")
    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("No soy yo — cambiar ID", key="asent_volver"):
            _ir_a("login")
    with c_next:
        if st.button(
            "Empezar mi proceso →",
            type="primary",
            use_container_width=True,
            disabled=not ambos_aceptados,
            key="asent_submit",
        ):
            db.set_consentimiento(estudiante["id"], incluye_datos_sensibles=True)
            # Recargar desde DB para obtener el estado actualizado antes de autenticar
            estudiante_ok = db.login_estudiante(estudiante["estudiante_id"])
            _autenticar(estudiante_ok)


# ── Pantalla: olvidé mi ID ─────────────────────────────────────────────────────

def _olvide_id():
    st.markdown("## Recuperar tu ID")
    st.markdown(
        "Escribí el correo que usaste cuando te registraron "
        "y te mostramos tu ID."
    )

    email = st.text_input("Tu correo electrónico", key="olvide_email")

    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="olvide_volver"):
            _ir_a("inicio")
    with c_next:
        if st.button("Buscar mi ID →", type="primary", use_container_width=True, key="olvide_submit"):
            if not _email_valido(email):
                st.error("Escribí un correo electrónico válido.")
                return

            estudiante = db.get_estudiante_por_email(email)

            if estudiante is None:
                st.info(
                    "No encontramos un registro con ese correo. "
                    "Si no tenés correo registrado, pedile tu ID directamente "
                    "a tu orientador/a."
                )
            else:
                _enviar_id_por_email(
                    email=email.lower().strip(),
                    nombre=estudiante["nombre"],
                    est_id=estudiante["estudiante_id"],
                )


def _enviar_id_por_email(email: str, nombre: str, est_id: str):
    """Intenta enviar el ID por correo. Si falla, lo muestra en pantalla."""
    try:
        import email_service
        email_service.enviar_id_recuperacion(
            email=email,
            nombre=nombre,
            estudiante_id=est_id,
        )
        st.success(
            f"¡Listo! Te enviamos tu ID al correo **{email}**. "
            "Revisá también la carpeta de spam si no lo ves pronto."
        )
    except Exception:
        st.success("Encontramos tu cuenta. Tu ID es:")
        st.code(est_id, language=None)
        st.info("Guardalo para entrar la próxima vez.")


# ── Autenticación exitosa ──────────────────────────────────────────────────────

def _autenticar(estudiante: dict):
    """Fija el estudiante en session_state y limpia todo el estado temporal de auth."""
    st.session_state.estudiante = estudiante
    claves_auth = [k for k in st.session_state if k.startswith("auth_")]
    for k in claves_auth:
        del st.session_state[k]
    st.rerun()


# ── API pública ────────────────────────────────────────────────────────────────

def esta_autenticado() -> bool:
    return "estudiante" in st.session_state


def mostrar_pantalla_auth():
    """
    Renderiza la pantalla activa del flujo de auth.
    Llamar desde app.py cuando not esta_autenticado().
    """
    pantallas = {
        "inicio":       _inicio,
        "login":        _login,
        "asentimiento": _asentimiento_estudiante,
        "olvide_id":    _olvide_id,
    }
    pantallas.get(_vista(), _inicio)()
