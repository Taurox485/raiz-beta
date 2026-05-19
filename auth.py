"""
auth.py — Flujos de autenticación para rAÍz

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


# ── Feature flag: grados habilitados ──────────────────────────────────────────

def _grados_habilitados() -> list[int]:
    """
    Lee GRADOS_HABILITADOS de secrets.toml.
    Acepta "9", "9,10" o "9,10,11". Default seguro: [9].
    Cambiar el valor en secrets.toml abre nuevos grados sin tocar código.
    """
    try:
        raw = st.secrets.get("GRADOS_HABILITADOS", "9")
        return sorted(int(g.strip()) for g in str(raw).split(","))
    except Exception:
        return [9]


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
    st.markdown("Tu guía de proyecto de vida. ¿Qué quieres hacer?")
    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "🌱 Empezar por primera vez",
            use_container_width=True,
            type="primary",
        ):
            _ir_a("registro")
    with c2:
        if st.button("🔑 Ya tengo mi ID", use_container_width=True):
            _ir_a("login")

    st.markdown("---")
    if st.button("¿Olvidaste tu ID? Recupéralo aquí"):
        _ir_a("olvide_id")


# ── Pantalla: registro — formulario ───────────────────────────────────────────

def _registro():
    st.markdown("## Registro nuevo estudiante")

    # ── Dropdowns en cascada: municipio → institución → sede ──────────────────
    municipios = db.get_municipios()
    if not municipios:
        st.error("No hay municipios configurados. Contacta al equipo rAÍz.")
        return

    mun_map = {m["nombre"]: m["id"] for m in municipios}
    mun_nombre = st.selectbox("¿De qué municipio eres?", list(mun_map.keys()), key="reg_municipio")
    mun_id = mun_map[mun_nombre]

    instituciones = db.get_instituciones(mun_id)
    if not instituciones:
        st.warning(
            f"Aún no hay colegios configurados para {mun_nombre}. "
            "Habla con tu orientador/a."
        )
        if st.button("← Volver", key="reg_volver_sin_inst"):
            _ir_a("inicio")
        return

    inst_map = {i["nombre"]: i["id"] for i in instituciones}
    inst_nombre = st.selectbox("¿En qué colegio estudias?", list(inst_map.keys()), key="reg_inst")
    inst_id = inst_map[inst_nombre]

    sedes = db.get_sedes(inst_id)
    if not sedes:
        st.warning(
            "No hay sedes configuradas para este colegio. "
            "Habla con tu orientador/a."
        )
        if st.button("← Volver", key="reg_volver_sin_sede"):
            _ir_a("inicio")
        return

    if len(sedes) == 1:
        sede_id = sedes[0]["id"]
        st.caption(f"Sede: {sedes[0]['nombre']}")
    else:
        sede_map = {s["nombre"]: s["id"] for s in sedes}
        sede_nombre = st.selectbox("¿Cuál es tu sede?", list(sede_map.keys()), key="reg_sede")
        sede_id = sede_map[sede_nombre]

    st.markdown("---")

    # ── Datos personales ───────────────────────────────────────────────────────
    nombre = st.text_input("Tu(s) nombre(s)", key="reg_nombre")

    apellido = st.text_input(
        "Tu apellido",
        key="reg_apellido",
    )

    grados = _grados_habilitados()
    grado_sel = st.selectbox(
        "¿En qué grado estás?",
        options=[f"Grado {g}°" for g in grados],
        key="reg_grado",
    )
    grado = int(grado_sel.replace("Grado ", "").replace("°", ""))

    # Email ingresado dos veces para evitar errores de tipeo
    email = st.text_input("Tu correo electrónico personal", key="reg_email")
    email_confirmar = st.text_input(
        "Confirma tu correo electrónico",
        key="reg_email_confirm",
        help="Escríbelo de nuevo para asegurarnos de que esté bien",
    )

    st.markdown("")
    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="reg_volver"):
            _ir_a("inicio")
    with c_next:
        if st.button("Continuar →", type="primary", use_container_width=True, key="reg_submit"):
            errores = _validar_datos_registro(nombre, apellido, grado, email, email_confirmar)
            if errores:
                for msg in errores:
                    st.error(msg)
            else:
                _ir_a(
                    "consentimiento",
                    nombre=nombre.strip(),
                    apellido=apellido.strip(),
                    grado=grado,
                    email=email.lower().strip(),
                    sede_id=sede_id,
                )


def _validar_datos_registro(
    nombre: str,
    apellido: str,
    grado: int,
    email: str,
    email_confirmar: str,
) -> list[str]:
    errores = []

    if len(nombre.strip()) < 2:
        errores.append("Escribe tu nombre (al menos 2 letras).")

    if len(apellido.strip()) < 2:
        errores.append("Escribe tu apellido.")

    # Chequeo explícito del feature flag — aunque el selectbox ya limita las opciones,
    # esta validación actúa como barrera de seguridad adicional.
    habilitados = _grados_habilitados()
    if grado not in habilitados:
        grados_texto = "°, ".join(str(g) for g in habilitados) + "°"
        errores.append(
            "Este programa está disponible actualmente solo para estudiantes de "
            f"grado {grados_texto}. Si estás en otro grado, pronto podrás participar."
        )

    if not _email_valido(email):
        errores.append("El correo electrónico no parece válido (ej: nombre@correo.com).")
    elif email.lower().strip() != email_confirmar.lower().strip():
        errores.append("Los dos correos no coinciden. Revísalos con cuidado.")

    return errores


# ── Pantalla: consentimiento habeas data ───────────────────────────────────────

def _consentimiento():
    nombre = st.session_state.get("auth_nombre", "")
    st.markdown(f"## Antes de empezar, {nombre}...")

    st.markdown(
        "Para acompañarte en este proceso, rAÍz necesita guardar "
        "información sobre tus conversaciones."
    )

    with st.expander("📄 ¿Qué información guardamos y para qué? (léelo antes de aceptar)"):
        st.markdown(
            """
**Guardamos:**
- Tu nombre y apellido
- Tu grado y correo electrónico
- Las conversaciones del proceso (para retomar donde quedaste)
- Un perfil general de orientación basado en tus respuestas

**No guardamos:**
- Tu número de celular
- Información detallada sobre tu familia o situación económica
- Nada que indique tu dirección o ubicación exacta

**¿Para qué se usa?**
- Para que puedas retomar el proceso si cierras la página
- Para que tu orientador/a te apoye mejor en 10° y 11°
- Para generar tu Perfil de Talentos al final del proceso

**Tus derechos (Ley 1581 de 2012):**
Tienes derecho a conocer, actualizar y solicitar la eliminación de tus datos.
Para ejercer estos derechos, contacta al equipo rAÍz a través de tu colegio.
            """
        )

    acepta = st.checkbox(
        "Acepto que rAÍz guarde mis datos para el proceso de orientación vocacional, "
        "según lo explicado arriba.",
        key="consent_checkbox",
    )

    st.markdown("")
    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="consent_volver"):
            _ir_a("registro")
    with c_next:
        if st.button(
            "Registrarme →",
            type="primary",
            use_container_width=True,
            disabled=not acepta,
            key="consent_submit",
        ):
            est_id = db.crear_estudiante(
                nombre=st.session_state["auth_nombre"],
                apellido=st.session_state["auth_apellido"],
                grado=st.session_state["auth_grado"],
                email=st.session_state["auth_email"],
                sede_id=st.session_state["auth_sede_id"],
            )

            if est_id is None:
                st.error(
                    "Este correo ya tiene un registro en rAÍz. "
                    "Si ya participaste antes, usa la opción '🔑 Ya tengo mi ID'."
                )
                return

            # Grabar consentimiento con timestamp preciso (Ley 1581/2012).
            # Se hace en dos pasos: crear estudiante primero (sin consent) para obtener
            # el UUID, luego marcar consent con el timestamp exacto de aceptación.
            estudiante = db.login_estudiante(est_id)
            db.set_consentimiento(estudiante["id"])
            estudiante = db.login_estudiante(est_id)  # recargar con consent=True

            _ir_a("exito_registro", estudiante_id=est_id, estudiante=estudiante)


# ── Pantalla: éxito del registro ───────────────────────────────────────────────

def _exito_registro():
    est_id = st.session_state.get("auth_estudiante_id", "")
    nombre = st.session_state.get("auth_nombre", "")
    email = st.session_state.get("auth_email", "")

    st.success(f"¡Listo, {nombre}! Ya estás en el sistema. 🌱")

    st.markdown("#### Este es tu ID de rAÍz:")
    st.code(est_id, language=None)

    st.warning(
        "⚠️ **Guarda este ID.** Lo necesitarás cada vez que quieras retomar tu proceso. "
        "También te lo enviamos a tu correo."
    )

    # Envío de email (email_service.py — stub hasta implementación completa)
    try:
        import email_service
        email_service.enviar_id_registro(
            email=email,
            nombre=nombre,
            estudiante_id=est_id,
        )
    except Exception:
        pass  # El registro no debe fallar si el email no está listo

    st.markdown("")
    if st.button("Empezar mi proceso rAÍz →", type="primary", use_container_width=True):
        # Fallback a DB por si session_state se limpió (recarga de página en este paso)
        estudiante = st.session_state.get("auth_estudiante") or db.login_estudiante(est_id)
        if not estudiante:
            st.error("No pudimos cargar tu perfil. Intenta ingresar con tu ID.")
            return
        _autenticar(estudiante)


# ── Pantalla: login ────────────────────────────────────────────────────────────

def _login():
    st.markdown("## Ingresa con tu ID")

    est_id_input = st.text_input(
        "Tu ID de rAÍz",
        placeholder="Ej: ALC-9-2026-0042",
        help="El ID que recibiste cuando te registraste",
        key="login_id_input",
    )

    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="login_volver"):
            _ir_a("inicio")
    with c_next:
        if st.button("Entrar →", type="primary", use_container_width=True, key="login_submit"):
            if not est_id_input.strip():
                st.error("Escribe tu ID para continuar.")
                return

            estudiante = db.login_estudiante(est_id_input.strip())

            if estudiante is None:
                st.error(
                    f"No encontré el ID **{est_id_input.strip().upper()}**. "
                    "Revisa que esté escrito exactamente igual a como lo recibiste."
                )
            else:
                _autenticar(estudiante)

    st.markdown("---")
    if st.button("No recuerdo mi ID — recupéralo aquí", key="login_olvide"):
        _ir_a("olvide_id")


# ── Pantalla: olvidé mi ID ─────────────────────────────────────────────────────

def _olvide_id():
    st.markdown("## Recuperar tu ID")
    st.markdown(
        "Escribe el correo que usaste cuando te registraste "
        "y te enviamos tu ID."
    )

    email = st.text_input("Tu correo electrónico", key="olvide_email")

    c_back, c_next = st.columns([1, 2])
    with c_back:
        if st.button("← Volver", key="olvide_volver"):
            _ir_a("inicio")
    with c_next:
        if st.button("Enviar mi ID →", type="primary", use_container_width=True, key="olvide_submit"):
            if not _email_valido(email):
                st.error("Escribe un correo electrónico válido.")
                return

            estudiante = db.get_estudiante_por_email(email)

            if estudiante is None:
                st.info(
                    "No encontramos un registro con ese correo. "
                    "Si aún no te has registrado, usa la opción "
                    "'🌱 Empezar por primera vez'."
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
            "Revisa también la carpeta de spam si no lo ves pronto."
        )
    except Exception:
        # Fallback: mostrar en pantalla hasta que email_service esté implementado
        st.success("Encontramos tu cuenta. Tu ID es:")
        st.code(est_id, language=None)
        st.info("Guárdalo para entrar la próxima vez.")


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
        "inicio":          _inicio,
        "registro":        _registro,
        "consentimiento":  _consentimiento,
        "exito_registro":  _exito_registro,
        "login":           _login,
        "olvide_id":       _olvide_id,
    }
    pantallas.get(_vista(), _inicio)()