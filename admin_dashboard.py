"""
admin_dashboard.py — Dashboard del administrador rAÍz

Acceso: https://[url]/?admin=1

Auth: email en DB de administradores + contraseña fija en secrets.toml (ADMIN_PASSWORD).
Esta solución es válida para el piloto. En producción usar Supabase Auth.

API pública:
  esta_autenticado_admin() → bool
  mostrar_dashboard_admin() → None

Sesión: st.session_state["admin"] = dict del administrador de la DB.
"""

import hashlib

import streamlit as st

import database as db


# ── Helpers internos ───────────────────────────────────────────────────────────

def _hash_celular(celular: str) -> str:
    return hashlib.sha256(celular.strip().encode("utf-8")).hexdigest()


# ── Auth de admin ─────────────────────────────────────────────────────────────

def esta_autenticado_admin() -> bool:
    return "admin" in st.session_state


def _mostrar_login():
    st.title("🌱 rAÍz — Administración")
    st.markdown("Ingresá con tu email y la contraseña del equipo rAÍz.")
    st.markdown("")

    with st.form("form_login_admin"):
        email    = st.text_input("Email", placeholder="orientador@colegio.edu.co")
        password = st.text_input("Contraseña", type="password")
        submit   = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

    if not submit:
        return

    if not email.strip():
        st.error("Ingresá tu email.")
        return

    admin_pw = st.secrets.get("ADMIN_PASSWORD", "")
    if not admin_pw or password != admin_pw:
        st.error("Contraseña incorrecta.")
        return

    admin = db.get_administrador_por_email(email.strip())
    if admin is None:
        st.error("Email no autorizado. Contactá al equipo rAÍz para que creen tu acceso.")
        return

    st.session_state["admin"] = admin
    st.rerun()


# ── Tab 1: Registrar estudiante ────────────────────────────────────────────────

def _tab_registrar_estudiante(admin: dict):
    st.markdown("### Registrar nuevo estudiante")
    st.caption(
        "El acudiente debe haber firmado la autorización física antes de registrar al estudiante."
    )

    sedes_all = db.get_sedes_disponibles(admin["id"], admin["rol"])
    if not sedes_all:
        st.warning("No hay sedes disponibles para tu perfil. Contactá al equipo rAÍz.")
        return

    # ── Selector en cascada (fuera del form para actualización dinámica) ──────
    municipios = sorted({s["municipio"] for s in sedes_all})
    mun_sel = st.selectbox("Municipio *", municipios, key="reg_municipio")

    instituciones = sorted({
        s["institucion"] for s in sedes_all if s["municipio"] == mun_sel
    })
    inst_sel = st.selectbox("Institución educativa *", instituciones, key="reg_institucion")

    sedes_inst = [
        s for s in sedes_all
        if s["municipio"] == mun_sel and s["institucion"] == inst_sel
    ]
    sede_nombres = [s["nombre"] for s in sedes_inst]
    sede_sel = st.selectbox("Sede *", sede_nombres, key="reg_sede")
    sede_id = sedes_inst[sede_nombres.index(sede_sel)]["id"]

    st.markdown("---")

    with st.form("form_registro_est", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre(s) *")
        with c2:
            apellido = st.text_input("Apellido(s) *")

        grado = st.selectbox("Grado *", [9, 10, 11])

        st.markdown("**Contacto del estudiante** *(al menos uno)*")
        c5, c6 = st.columns(2)
        with c5:
            email_est = st.text_input("Email del estudiante", placeholder="nombre@correo.com")
        with c6:
            celular = st.text_input("Celular", placeholder="3001234567")

        st.markdown("---")
        checkbox_consent = st.checkbox(
            "✅ Declaro que recibí la autorización firmada del acudiente de este estudiante "
            "y que la custodia del documento físico está a cargo de la institución."
        )
        archivo = st.file_uploader(
            "📎 Subir foto o PDF del documento firmado (opcional pero recomendado)",
            type=["jpg", "jpeg", "png", "pdf"],
        )

        submit = st.form_submit_button("Registrar estudiante", type="primary", use_container_width=True)

    if not submit:
        return

    # ── Validaciones ──────────────────────────────────────────────────────────
    errores = []
    if len(nombre.strip()) < 2:
        errores.append("El nombre debe tener al menos 2 caracteres.")
    if len(apellido.strip()) < 2:
        errores.append("El apellido debe tener al menos 2 caracteres.")
    if not email_est.strip() and not celular.strip():
        errores.append("Ingresá al menos un medio de contacto: email o número de celular.")
    if not checkbox_consent:
        errores.append(
            "Debés declarar que recibiste la autorización firmada del acudiente "
            "antes de registrar al estudiante."
        )

    if errores:
        for e in errores:
            st.error(e)
        return

    # ── Registro ──────────────────────────────────────────────────────────────
    celular_hash = _hash_celular(celular) if celular.strip() else None
    email_norm   = email_est.lower().strip() or None

    try:
        est_id = db.crear_estudiante_admin(
            nombre=nombre.strip(),
            apellido=apellido.strip(),
            grado=grado,
            sede_id=sede_id,
            admin_uuid=admin["id"],
            email=email_norm,
            celular_hash=celular_hash,
        )
        est = db.login_estudiante(est_id)
        db.set_consentimiento_acudiente(est["id"])

        if archivo is not None:
            ext = archivo.name.rsplit(".", 1)[-1].lower()
            url = db.guardar_archivo_consentimiento(est_id, sede_id, ext, archivo.read())
            db.update_consentimiento_url(est["id"], url)

        st.success(
            f"**Estudiante registrado correctamente.**\n\n"
            f"Código de acceso: **`{est_id}`**\n\n"
            f"Compartí este código con el estudiante para que pueda acceder a rAÍz."
        )

    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Error al registrar el estudiante. Detalle: {exc}")


# ── Tab 2: Lista de estudiantes ────────────────────────────────────────────────

def _tab_lista_estudiantes(admin: dict):
    if st.button("🔄 Actualizar lista"):
        st.rerun()

    estudiantes = db.get_estudiantes_por_admin(admin["id"], admin["rol"])

    if not estudiantes:
        st.info("No hay estudiantes registrados aún en tu institución.")
        return

    filas = [
        {
            "Código":        e["estudiante_id"],
            "Nombre":        f"{e['nombre']} {e['apellido']}",
            "Grado":         f"{e['grado']}°",
            "Sede":          f"{e['sede_nombre']} — {e['municipio']}",
            "Sesión":        e["sesion_actual"],
            "Riesgo":        e["perfil_riesgo"],
            "Autorización":  "✅" if e["consentimiento_acudiente_verificado"] else "⏳",
            "Archivo":       "📎" if e["tiene_archivo_consentimiento"] else "—",
        }
        for e in estudiantes
    ]

    st.dataframe(filas, use_container_width=True, hide_index=True)
    st.caption(f"{len(estudiantes)} estudiante(s) registrado(s).")


# ── Tab 3: Alertas pendientes ─────────────────────────────────────────────────

_TIPOS_ALERTA = {
    "psicologica_critica":  ("⚠️ Atención psicológica urgente",    "error"),
    "orientador_requerida": ("📋 Seguimiento requerido",            "warning"),
}


def _tab_alertas(admin: dict):
    if st.button("🔄 Actualizar alertas"):
        st.rerun()

    alertas = db.get_alertas_pendientes(admin["id"], admin["rol"])

    if not alertas:
        st.success("Sin alertas pendientes.")
        return

    for alerta in alertas:
        titulo, nivel = _TIPOS_ALERTA.get(alerta["tipo"], ("Alerta", "warning"))

        with st.container(border=True):
            if nivel == "error":
                st.error(f"**{titulo}**")
            else:
                st.warning(f"**{titulo}**")

            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(
                    f"**Estudiante:** {alerta['nombre_estudiante']}  \n"
                    f"**Código:** `{alerta['estudiante_codigo']}`  \n"
                    f"**Fecha:** {alerta['timestamp']}"
                )
            with c2:
                if st.button(
                    "Marcar como vista",
                    key=f"alerta_{alerta['id']}",
                    use_container_width=True,
                ):
                    db.marcar_alerta_vista(alerta["id"])
                    st.rerun()


# ── Tab 4: Instituciones (solo fcc) ───────────────────────────────────────────

def _tab_instituciones(admin: dict):
    st.markdown("### Gestión de instituciones educativas")
    st.info(
        "Los emails de orientador/a y rector/a son críticos: se usan para enviar alertas "
        "automáticas cuando un estudiante necesita atención. Sin estos datos, las "
        "notificaciones no llegan."
    )

    if st.button("🔄 Actualizar lista", key="refresh_instituciones"):
        st.rerun()

    instituciones = db.get_todas_instituciones()

    if not instituciones:
        st.warning("No hay instituciones registradas.")
        return

    st.caption(f"{len(instituciones)} institución(es) registrada(s).")

    for inst in instituciones:
        sedes_str   = ", ".join(inst["sedes"]) if inst["sedes"] else "—"
        tiene_emails = bool(inst["orientador_email"]) and bool(inst["rector_email"])
        icono        = "✅" if tiene_emails else "⚠️"

        with st.expander(
            f"{icono} {inst['nombre']} — {inst['municipio_nombre']}",
            expanded=False,
        ):
            st.caption(f"Sedes: {sedes_str}")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Orientador/a actual**")
                st.markdown(f"Nombre: {inst['orientador_nombre'] or '—'}")
                if inst["orientador_email"]:
                    st.markdown(f"Email: `{inst['orientador_email']}`")
                else:
                    st.warning("Email: no configurado — necesario para alertas")
                st.markdown(f"Tel: {inst['orientador_telefono'] or '—'}")
            with col_b:
                st.markdown("**Rector/a actual**")
                st.markdown(f"Nombre: {inst['rector_nombre'] or '—'}")
                if inst["rector_email"]:
                    st.markdown(f"Email: `{inst['rector_email']}`")
                else:
                    st.warning("Email: no configurado — necesario para alertas críticas")

            st.markdown("---")

            with st.form(f"form_inst_{inst['id']}"):
                st.markdown("**Actualizar datos de contacto**")
                c1, c2 = st.columns(2)
                with c1:
                    ori_nombre = st.text_input(
                        "Nombre orientador/a",
                        value=inst["orientador_nombre"],
                    )
                    ori_email = st.text_input(
                        "Email orientador/a ✉️",
                        value=inst["orientador_email"],
                        placeholder="orientador@colegio.edu.co",
                    )
                    ori_tel = st.text_input(
                        "Teléfono orientador/a",
                        value=inst["orientador_telefono"],
                        placeholder="3001234567",
                    )
                with c2:
                    rec_nombre = st.text_input(
                        "Nombre rector/a",
                        value=inst["rector_nombre"],
                    )
                    rec_email = st.text_input(
                        "Email rector/a ✉️",
                        value=inst["rector_email"],
                        placeholder="rector@colegio.edu.co",
                    )

                if st.form_submit_button("💾 Guardar cambios", type="primary"):
                    errores = []
                    if ori_email.strip() and "@" not in ori_email:
                        errores.append("El email del orientador/a no parece válido.")
                    if rec_email.strip() and "@" not in rec_email:
                        errores.append("El email del rector/a no parece válido.")
                    if errores:
                        for e in errores:
                            st.error(e)
                    else:
                        db.update_institucion(inst["id"], {
                            "orientador_nombre":   ori_nombre.strip() or None,
                            "orientador_email":    ori_email.strip().lower() or None,
                            "orientador_telefono": ori_tel.strip() or None,
                            "rector_nombre":       rec_nombre.strip() or None,
                            "rector_email":        rec_email.strip().lower() or None,
                        })
                        st.success(f"Datos de **{inst['nombre']}** actualizados.")
                        st.rerun()


# ── API pública ────────────────────────────────────────────────────────────────

def mostrar_dashboard_admin():
    if not esta_autenticado_admin():
        _mostrar_login()
        return

    admin = st.session_state["admin"]

    # ── Sidebar ───────────────────────────────────────────────────────────────
    roles = {"fcc": "FCC", "orientador": "Orientador/a", "secretaria": "Secretaría de Educación"}
    with st.sidebar:
        st.markdown(f"**{admin['nombre']}**")
        st.caption(roles.get(admin["rol"], admin["rol"]))
        st.markdown("---")
        if st.button("Cerrar sesión", use_container_width=True):
            del st.session_state["admin"]
            st.rerun()

    # ── Contenido ─────────────────────────────────────────────────────────────
    st.title("🌱 rAÍz — Administración")

    tab_labels = [
        "➕ Registrar estudiante",
        "👥 Estudiantes registrados",
        "🔔 Alertas pendientes",
    ]
    if admin["rol"] == "fcc":
        tab_labels.append("⚙️ Instituciones")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _tab_registrar_estudiante(admin)
    with tabs[1]:
        _tab_lista_estudiantes(admin)
    with tabs[2]:
        _tab_alertas(admin)
    if admin["rol"] == "fcc":
        with tabs[3]:
            _tab_instituciones(admin)
