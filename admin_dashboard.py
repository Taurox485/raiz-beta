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
    celular_plain = celular.strip() or None
    celular_hash  = _hash_celular(celular) if celular.strip() else None
    email_norm    = email_est.lower().strip() or None

    try:
        est_id = db.crear_estudiante_admin(
            nombre=nombre.strip(),
            apellido=apellido.strip(),
            grado=grado,
            sede_id=sede_id,
            admin_uuid=admin["id"],
            email=email_norm,
            celular_hash=celular_hash,
            celular=celular_plain,
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

    # ── Banner de retención vencida (solo fcc) ─────────────────────────────────
    if admin["rol"] == "fcc":
        vencidos = db.get_estudiantes_vencidos()
        if vencidos:
            st.error(
                f"⚠️ **{len(vencidos)} estudiante(s) con período de retención vencido** — "
                "la supresión es obligatoria por Ley 1581/2012. "
                "Usá la sección de supresión más abajo."
            )

    # Pre-fetch envíos de ficha para todos los estudiantes
    envios_ficha = {e["id"]: db.get_envio_ficha(e["id"]) for e in estudiantes}

    # ── Tabla de estudiantes ──────────────────────────────────────────────────
    cols = st.columns([1.5, 1.8, 0.6, 2.2, 1.2, 1.0, 1.0, 1.8])
    headers = ["Código", "Nombre", "Grado", "Sede", "Progreso",
               "Riesgo", "Autorización", "Ficha orientador"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    for e in estudiantes:
        cols = st.columns([1.5, 1.8, 0.6, 2.2, 1.2, 1.0, 1.0, 1.8])

        cols[0].caption(e["estudiante_id"])
        cols[1].write(f"{e['nombre']} {e['apellido']}")
        cols[2].write(f"{e['grado']}°")
        cols[3].write(f"{e['sede_nombre']} — {e['municipio']}")

        if e.get("mentoria_completada"):
            cols[4].write("✅ Completada")
        else:
            cols[4].write(f"S{e['sesion_actual']} M{e['momento_actual']}")

        cols[5].write(e["perfil_riesgo"])
        cols[6].write("✅" if e["consentimiento_acudiente_verificado"] else "⏳")

        with cols[7]:
            if not e.get("mentoria_completada"):
                st.write("—")
            else:
                pdf_key = f"pdf_ficha_{e['id']}"
                if st.button("📄 Descargar", key=f"btn_ficha_{e['id']}"):
                    with st.spinner("Generando ficha..."):
                        try:
                            from google import genai as _genai
                            import pdf_generator as _pdf_gen
                            _client = _genai.Client(
                                api_key=st.secrets["GEMINI_API_KEY"]
                            )
                            try:
                                with open("instrucciones.txt", "r", encoding="utf-8") as _f:
                                    _sys = _f.read().strip()
                            except FileNotFoundError:
                                _sys = ""
                            historial = db.get_historial(e["id"])
                            _, pdf_ori = _pdf_gen.generar_pdfs(
                                estudiante=e,
                                historial=historial,
                                client=_client,
                                model="gemini-3.1-flash-lite",
                                system_instruction=_sys,
                            )
                            st.session_state[pdf_key] = pdf_ori
                        except Exception as e_pdf:
                            st.error(f"Error: {e_pdf}")

                envio = envios_ficha.get(e["id"])
                if envio:
                    if envio["exito"]:
                        try:
                            from datetime import datetime as _dt
                            fecha = _dt.fromisoformat(envio["timestamp"]).strftime("%d/%m/%Y")
                        except Exception:
                            fecha = str(envio["timestamp"])[:10]
                        st.caption(f"✅ {fecha}")
                    else:
                        st.caption("⚠️ Error")
                else:
                    st.caption("📧 Pendiente")

                if pdf_key in st.session_state:
                    nombre_f = f"{e.get('nombre','')}_{e.get('apellido','')}".lower().replace(" ", "_")
                    st.download_button(
                        label="⬇️ Guardar PDF",
                        data=st.session_state[pdf_key],
                        file_name=f"ficha_orientador_{nombre_f}.pdf",
                        mime="application/pdf",
                        key=f"dl_ficha_{e['id']}",
                    )

    st.caption(f"{len(estudiantes)} estudiante(s) registrado(s).")

    # ── Supresión de datos (solo fcc) ─────────────────────────────────────────
    if admin["rol"] != "fcc":
        return

    with st.expander("🗑️ Supresión de datos (Ley 1581/2012)", expanded=False):
        st.caption(
            "Acción irreversible. Anonimiza nombre, email y celular; elimina mensajes y alertas. "
            "Conserva municipio, grado y perfil de riesgo para estadísticas."
        )

        # Excluir estudiantes ya suprimidos de la lista
        no_suprimidos = [e for e in estudiantes if e["nombre"] != "SUPRIMIDO"]
        if not no_suprimidos:
            st.info("No hay estudiantes activos para suprimir.")
            return

        busqueda = st.text_input(
            "🔍 Buscar estudiante",
            placeholder="Nombre, apellido, código, institución o municipio",
        )
        total = len(no_suprimidos)
        if busqueda.strip():
            q = busqueda.strip().lower()
            no_suprimidos = [
                e for e in no_suprimidos
                if q in e["estudiante_id"].lower()
                or q in e["nombre"].lower()
                or q in e["apellido"].lower()
                or q in e["municipio"].lower()
                or q in e["sede_nombre"].lower()
                or q in e["institucion"].lower()
            ]
        st.caption(f"{len(no_suprimidos)} de {total} estudiante(s)")

        for e in no_suprimidos:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"`{e['estudiante_id']}` — {e['nombre']} {e['apellido']} "
                    f"({e['grado']}°, {e['municipio']})"
                )
            with c2:
                if st.button(
                    "🗑️",
                    key=f"sup_btn_{e['estudiante_id']}",
                    help="Suprimir datos de este estudiante",
                    use_container_width=True,
                ):
                    st.session_state["suprimiendo"] = e["estudiante_id"]

        if "suprimiendo" not in st.session_state:
            return

        est_id_sup = st.session_state["suprimiendo"]
        st.warning(
            f"⚠️ Estás a punto de suprimir los datos de **`{est_id_sup}`**. "
            "Esta acción no se puede deshacer."
        )

        with st.form("form_confirmacion_supresion"):
            motivo    = st.text_input("Motivo de la supresión *", placeholder="Solicitud del acudiente")
            confirmar = st.text_input("Escribí CONFIRMAR para continuar")
            c1, c2 = st.columns(2)
            with c1:
                ejecutar = st.form_submit_button(
                    "🗑️ Ejecutar supresión", type="primary", use_container_width=True
                )
            with c2:
                cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if cancelar:
            del st.session_state["suprimiendo"]
            st.rerun()

        if ejecutar:
            if not motivo.strip():
                st.error("El motivo es obligatorio.")
            elif confirmar != "CONFIRMAR":
                st.error("Escribí exactamente CONFIRMAR (en mayúsculas) para continuar.")
            else:
                est_data = db.login_estudiante(est_id_sup)
                if est_data:
                    db.suprimir_estudiante(est_data["id"], motivo.strip())
                    del st.session_state["suprimiendo"]
                    st.success(f"Datos de `{est_id_sup}` suprimidos correctamente.")
                    st.rerun()
                else:
                    st.error(f"No se encontró el estudiante {est_id_sup}.")


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


# ── Tab 5: WhatsApp re-engagement (solo fcc) ──────────────────────────────────

def _tab_whatsapp(admin: dict):
    import whatsapp_service as wa

    st.markdown("### Re-engagement por WhatsApp")
    st.caption(
        "Envía recordatorios a estudiantes que abandonaron su proceso. "
        "Solo reciben mensajes los que tienen número de celular registrado."
    )

    tiene_twilio = bool(
        st.secrets.get("TWILIO_ACCOUNT_SID", "")
        and st.secrets.get("TWILIO_AUTH_TOKEN", "")
        and st.secrets.get("TWILIO_WHATSAPP_NUMBER", "")
    )
    if not tiene_twilio:
        st.warning(
            "⚠️ Credenciales de Twilio no configuradas. "
            "Agregá TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_NUMBER "
            "en Settings → Secrets de Streamlit Cloud."
        )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("👁 Vista previa", use_container_width=True):
            with st.spinner("Calculando candidatos..."):
                candidatos = wa.preview_reengagement(db)
            st.session_state["wa_preview"] = candidatos

    with c2:
        if st.button(
            "📤 Enviar ahora",
            type="primary",
            use_container_width=True,
            disabled=not tiene_twilio,
        ):
            with st.spinner("Enviando mensajes..."):
                resultado = wa.procesar_reengagement(db)
            st.success(
                f"Proceso completado: **{resultado['enviados']}** enviados, "
                f"**{resultado['fallidos']}** fallidos "
                f"de **{resultado['total']}** candidatos."
            )
            if "wa_preview" in st.session_state:
                del st.session_state["wa_preview"]
            st.rerun()

    if "wa_preview" in st.session_state:
        preview = st.session_state["wa_preview"]
        if not preview:
            st.info("No hay candidatos elegibles para re-engagement en este momento.")
        else:
            st.markdown(f"**{len(preview)} mensaje(s) a enviar:**")
            for item in preview:
                with st.container(border=True):
                    st.markdown(
                        f"**{item['nombre']}** — `{item['estudiante_id']}` — "
                        f"MSG{item['mensaje_numero']} — `{item['celular']}`"
                    )
                    st.caption(item["texto"])


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
        tab_labels += ["⚙️ Instituciones", "📱 WhatsApp"]

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
        with tabs[4]:
            _tab_whatsapp(admin)
