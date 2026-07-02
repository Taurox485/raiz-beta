# rAÍz — Contexto del Proyecto para Claude Code

## Qué es rAÍz
Chatbot de orientación vocacional para estudiantes de **grado 9° (14-16 años)** en municipios del valle geográfico del Río Cauca, Colombia. Es un mentor de proyecto de vida impulsado por IA que acompaña al estudiante a través de 4 sesiones estructuradas de autoconocimiento.

El ecosistema económico gira en torno a la caña de azúcar y la agricultura. Muchos estudiantes trabajan para ayudar a sus familias y podrían ser la primera generación con acceso a educación post-secundaria. El tono debe ser cálido, cercano, en español colombiano del Valle del Cauca.

## Stack técnico actual
- `app.py` — Streamlit + Google GenAI SDK (`google-genai`)
- `instrucciones.txt` — system prompt pedagógico, cargado en tiempo de ejecución
- Modelo: `gemini-3.1-flash-lite`
- API key via `st.secrets["GEMINI_API_KEY"]`
- Base de datos: Supabase (prod) / SQLite (dev offline)
  - Supabase URL: `https://doihxpicgfvmrcntzykl.supabase.co`
  - Credenciales en `.streamlit/secrets.toml` (gitignored) y en Streamlit Cloud → Settings → Secrets
- WhatsApp: Twilio WhatsApp API (`whatsapp_service.py`) — `twilio>=9.0.0`
- UI Ronda Relámpago: `streamlit-sortables>=0.3.0`

## Deploy
- **URL producción:** https://raiz-piloto.streamlit.app/
- **Dashboard admin:** https://raiz-piloto.streamlit.app/?admin=1
- **Branch de deploy:** `main` (desarrollo en `master`)
- **Flujo de push:**
  ```bash
  git push origin master          # push normal
  git push origin master:main     # activa redeploy en Streamlit Cloud
  ```
  Streamlit Cloud redespliega automáticamente en 2-3 minutos tras el push a `main`.
  *Nota: Al requerir `streamlit-sortables>=0.3.0`, el proceso de build en Streamlit Cloud tomará tiempo adicional para instalar el componente externo.*

## Arquitectura pedagógica (leer instrucciones.txt completo)
- 4 sesiones × 5 momentos, avance estrictamente secuencial
- 1 sola pregunta por turno — regla crítica
- Metodologías camufladas: Holland, Ikigai, Covey adaptado, SCCT, Ubuntu
- Etiquetas internas que el estudiante nunca ve: `[FIN_CONSEJERIA]`, `[RIESGO_BAJO/MEDIO/ALTO]`, `[ALERTA_ORIENTADOR_REQUERIDA]`, `[ALERTA_PSICOLOGICA_CRITICA]`
- `limpiar_etiquetas()` en app.py filtra estas etiquetas antes de mostrar en pantalla

## Guardrails críticos (no negociables)
- PROHIBIDO recomendar carreras universitarias, instituciones o programas de educación superior
- PROHIBIDO juzgar estructura familiar, trabajo infantil, bajo rendimiento o dificultades económicas
- Habeas data colombiano (Ley 1581/2012) — consentimiento en dos niveles (acudiente + asentimiento estudiante)

---

## Estado actual del código

### Implementado y funcional

**Auth y flujo de acceso (Ley 1581/2012):**
- Admin crea el estudiante en el dashboard → genera `estudiante_id`
- Admin certifica que el acudiente firmó la autorización física (`consentimiento_acudiente_verificado`)
- Estudiante inicia sesión con su ID → ve asentimiento informado (2 checkboxes: general + datos sensibles) → accede al chat
- Recuperación de ID por email (`auth.py`)
- Autenticación de administradores migrada a Supabase Auth por usuario (email + contraseña individual, PENDIENTE 10) con pestaña de gestión de accesos (Tab 6, fcc)

**Dashboard administrador (`admin_dashboard.py`):**
- Acceso vía `/?admin=1`, protegido con login de usuario Supabase Auth (desarrollo local mantiene fallback con ADMIN_PASSWORD)
- Tres roles: `fcc` (todas las instituciones), `orientador`/`rector` (su institución), `secretaria` (jurisdicción regional, PENDIENTE 11)
- Tabs (rol fcc): Registrar estudiante · Estudiantes registrados · Alertas pendientes · Instituciones · WhatsApp · Gestión Admins
- Tabs (orientador/rector/secretaria): Registrar estudiante · Estudiantes registrados · Alertas pendientes
- Admin de prueba en Supabase: `admin@fcc.edu.co`
- Tabla de estudiantes rediseñada con `st.columns` (reemplaza `st.dataframe`)
- Columna "Progreso": `S1 M3` / `✅ Completada` (reemplaza columna "Sesión")
- Columna "Ficha orientador": botón Descargar + estado email (✅ fecha / ⚠️ Error / 📧 Pendiente)
- `layout="wide"` en `set_page_config` con CSS override en chat del estudiante para centrar contenido
- `momento_actual` añadido al SELECT de `get_estudiantes_por_admin()`

**Base de datos (`database.py`):**
- Adapter dual: Supabase (prod) / SQLite (dev offline, `raiz_local.db`)
- Detección automática por `SUPABASE_URL` en secrets
- Schema en `schema.sql` + todas las 9 SQL migrations aplicadas en Supabase
- Tablas: `municipios`, `instituciones`, `sedes`, `estudiantes`, `mensajes`, `alertas`, `administradores`, `whatsapp_mensajes`
- Seed data: 11 municipios y ~25 instituciones reales del Valle del Cauca
- Row Level Security (RLS) habilitado y políticas de acceso configuradas en Supabase (estudiantes, mensajes, alertas, sedes, instituciones - PENDIENTE 5)
- Firmas digitales temporales (Signed URLs) para la descarga segura de archivos de consentimiento (PENDIENTE 13)

**Selector en cascada (registro de estudiantes):**
- Selectboxes Municipio → Institución → Sede fuera del form en `_tab_registrar_estudiante()`
- Respeta rol: orientador solo ve su institución; fcc/secretaria ven todo

**Supresión y retención de datos (Ley 1581/2012):**
- Derecho de supresión: anonimiza nombre/email/celular, elimina mensajes y alertas (solo rol fcc)
- Retención automática: banner de alerta al cargar el dashboard cuando `fecha_retencion_hasta < hoy`
- `fecha_retencion_hasta` = 31 diciembre del año siguiente al registro
- Búsqueda por nombre, código, institución o municipio dentro del expander de supresión

**Gestión de instituciones (solo fcc):**
- Tab "⚙️ Instituciones": edita orientador_nombre/email/telefono y rector_nombre/email por institución
- Icono ✅/⚠️ según si los emails están configurados

**WhatsApp re-engagement (`whatsapp_service.py`):**
- Twilio WhatsApp API real (`from twilio.rest import Client`)
- 5 mensajes según punto de abandono (ver tabla de reglas más abajo)
- `preview_reengagement(db)` — vista previa sin enviar
- `procesar_reengagement(db)` — envía y registra en `whatsapp_mensajes`
- Tab "📱 WhatsApp" en dashboard (solo fcc): botón de vista previa + envío manual
- Muestra aviso si faltan secrets de Twilio
- Normalización E.164: números de 10 dígitos colombianos se convierten a `+57XXXXXXXXXX`

**Chat y sesiones:**
- Historial persistente en tabla `mensajes` (contenido crudo con etiquetas internas)
- Retoma de sesión reconstruyendo contexto Gemini desde DB
- `sesion_actual` y `momento_actual` actualizados por turno

**Alertas:**
- `[ALERTA_ORIENTADOR_REQUERIDA]` → notifica solo al orientador (email)
- `[ALERTA_PSICOLOGICA_CRITICA]` → notifica simultáneamente a orientador + rector + PEAS (threading paralelo, 15s timeout)
- Resultados de notificación persistidos en tabla `alertas` (`notificado_orientador`, `notificado_rector`, `notificado_peas`)
- Alertas pendientes visibles en el dashboard admin con "Marcar como vista"

**Generación de PDFs (`pdf_generator.py`):**
- Revertido de WeasyPrint a Playwright (`playwright.sync_api` con Chromium) por dependencias externas complejas (GTK3 en Windows). Playwright maneja sin problemas el layout avanzado.
- Script de prueba `test_pdf.py` modificado con historial mockeado offline para iteración visual rápida.
- Diseño visual mejorado en los PDFs (Actualizado Junio 2026):
  - Ficha Orientador (3 páginas): Disclaimer "CONFIDENCIAL E IMPORTANTE" resaltado en pág 1, eliminación de cuarta página, eliminación de polos de menor interés y diseño compactado.
  - Mapa Estudiante (2 páginas): Márgenes ajustados, "Espejo de tu entorno" trasladado a pág 1, ajustes de texto para feedback.
- Logo rAÍz rediseñado para uniformidad y simetría.
- Fuentes DM Sans y DM Serif Display gestionadas de forma local vía `@font-face`.
- Layout de encabezados en flexbox.
- Handler del botón `[FIN_CONSEJERIA]` completado en `app.py`.
- `generar_pdfs(estudiante, historial, client, model, system_instruction) → (bytes, bytes)`
- PDF estudiante: "Mi Mapa rAÍz" descargable desde la app. También enviado automáticamente por Email o WhatsApp (Twilio) al terminar el proceso.
- PDF orientador: "Ficha de Acompañamiento" enviado automáticamente por email.
- Dependencias OS (Debian) manejadas con `packages.txt` (`chromium`) para evitar conflictos t64 en Streamlit Cloud.

**Email orientador (`email_service.py`):**
- SMTP Gmail con contraseña de aplicación
- `enviar_id_registro()`, `enviar_id_recuperacion()`, `enviar_alerta_critica()`
- `enviar_ficha_orientador()` implementada — adjunta PDF orientador como attachment
- `enviar_mapa_estudiante()` implementada — adjunta PDF estudiante
- `get_sede_info()` corregida para incluir `orientador_email`, `orientador_telefono`, `rector_email`
- Tabla `envios_ficha` registra cada intento de envío (exitoso o fallido) por estudiante
- Migración 006 aplicada en Supabase

**Infraestructura:**
- Supabase conectado y activo en producción (`doihxpicgfvmrcntzykl.supabase.co`)
- Bucket `consentimientos` creado en Supabase Storage (subida de archivos de autorización activa)

### Pendiente (ver `raiz_claude_code_backlog.md` para detalle)

**Verificación pendiente:**
- Twilio WhatsApp: módulo de re-engagement implementado pero envío real no verificado en producción con número Twilio final. Hacer prueba manual desde tab "📱 WhatsApp" en dashboard y confirmar recepción cuando la cuenta de Twilio esté vinculada a Facebook Business.

**Supresión de datos (Ley 1581/2012):**
- El check constraint `check_contacto_requerido` en la tabla `estudiantes` fue eliminado de Supabase (bloqueaba la anonimización al poner celular/email en NULL). Ejecutado: `ALTER TABLE estudiantes DROP CONSTRAINT check_contacto_requerido;`
- `suprimir_estudiante()` en `database.py` ya incluye DELETE de `envios_ficha` y `whatsapp_mensajes` antes de `mensajes` y `alertas` (orden correcto para FKs)

**Deuda técnica registrada (backlog — sección DEUDAS TÉCNICAS PARA ESCALADA):**
- ~~**DEUDA TÉCNICA 1**~~ — ✅ Migrar columna `celular` a AES-128 (Completado)

---

## Schema de base de datos (estado actual)

### Tablas principales

#### `administradores`
```
id             UUID PK
nombre         VARCHAR(200)
email          VARCHAR(200) UNIQUE
rol            VARCHAR(30)  CHECK IN ('fcc', 'orientador', 'secretaria')
institucion_id INTEGER FK → instituciones (NULL para fcc/secretaria)
activo         BOOLEAN DEFAULT TRUE
```

#### `estudiantes` (columnas clave)
```
id                                UUID PK
estudiante_id                     VARCHAR(25) UNIQUE  -- ej: ALC-9-2026-0042
nombre, apellido                  VARCHAR
grado                             INTEGER CHECK(9-11)
email                             VARCHAR UNIQUE (nullable)
celular_hash                      VARCHAR(64)  -- SHA-256, no reversible
celular                           TEXT         -- texto plano para Twilio (Opción B piloto)
sede_id                           FK → sedes
asentimiento_estudiante           BOOLEAN  -- checkbox propio del estudiante
fecha_asentimiento_estudiante     TIMESTAMPTZ
consentimiento_datos_sensibles    BOOLEAN  -- checkbox datos sensibles
consentimiento_acudiente_verificado BOOLEAN  -- certificado por admin
administrador_registro_id         UUID FK → administradores
consentimiento_archivo_url        VARCHAR(500)  -- URL del doc firmado (opcional)
sesion_actual                     INTEGER DEFAULT 1
momento_actual                    INTEGER DEFAULT 1
perfil_riesgo                     VARCHAR(20) DEFAULT 'sin_evaluar'
mentoria_completada               BOOLEAN DEFAULT FALSE
suprimido                         BOOLEAN DEFAULT FALSE
fecha_supresion                   TIMESTAMPTZ
motivo_supresion                  TEXT
fecha_retencion_hasta             DATE
CONSTRAINT check_contacto_requerido CHECK (email IS NOT NULL OR celular_hash IS NOT NULL)
```

#### `alertas` (columnas clave)
```
id, estudiante_id, sede_id, tipo, estado, timestamp, nota_resolucion
notificado_orientador   BOOLEAN DEFAULT FALSE
notificado_rector       BOOLEAN DEFAULT FALSE
notificado_peas         BOOLEAN DEFAULT FALSE
timestamp_notificacion  TIMESTAMPTZ
```

#### `instituciones` (columnas clave)
```
id, municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono
rector_nombre  VARCHAR(200)
rector_email   VARCHAR(200)
```

#### `whatsapp_mensajes`
```
id              UUID PK
estudiante_id   UUID FK → estudiantes
mensaje_numero  INTEGER CHECK(1-5)
enviado_at      TIMESTAMPTZ
estado          VARCHAR(20)  -- 'enviado' / 'fallido'
```

### Migraciones aplicadas
```
migrations/
├── 002_roles_y_consentimiento.sql   ← aplicado en Supabase
├── 003_rector_instituciones.sql     ← aplicado en Supabase
├── 004_supresion_retencion.sql      ← aplicado en Supabase
├── 005_whatsapp.sql                 ← aplicado en Supabase
├── 006_envios_ficha.sql             ← aplicado en Supabase
├── 007_mensaje_cero.sql             ← aplicado en Supabase
├── 008_admin_auth_y_rls.sql         ← aplicado en Supabase
├── 009_admin_municipio_id.sql       ← aplicado en Supabase
└── 010_rls_sedes_instituciones.sql  ← aplicado en Supabase
```

### Reglas de activación WhatsApp (5 mensajes)
| MSG | Condición |
|-----|-----------|
| 1 | `sesion=1, momento=1`, sin mensajes de chat, registrado hace >1 día |
| 2 | `sesion=2, momento=1`, último chat hace >2 días |
| 3 | `sesion=3, momento=1`, último chat hace >2 días |
| 4 | `sesion=4, momento=1`, último chat hace >2 días |
| 5 | `mentoria_completada=FALSE`, sin actividad hace >5 días (último intento) |

Reglas invariables: máximo 1 mensaje por tipo por estudiante · nunca si `mentoria_completada=TRUE` · solo estudiantes con `celular IS NOT NULL`.

### Decisiones de arquitectura
1. **Auth sin email:** Los estudiantes no usan Supabase Auth. Login = `SELECT * FROM estudiantes WHERE estudiante_id = ?`. Backend usa `service_role_key`. RLS desactivado en esta fase (PENDIENTE 5).
2. **Generación del ID:** `MUNICIPIO-GRADO-AÑO-XXXX`, correlativo por `(municipio_id, grado, año)`.
3. **Fallback SQLite:** `database.py` detecta si `SUPABASE_URL` está configurado. Si no, usa SQLite. Mismo API, distinto backend.
4. **Celular dual:** `celular_hash` (SHA-256) + `celular` encriptado (AES-128 en BD, manejado en backend para Twilio).
5. **Contacto flexible:** Al menos uno de email o celular_hash es obligatorio (CHECK constraint).
6. **Cascading selectors:** Los selectboxes Municipio→Institución→Sede van **fuera** del `st.form` en Streamlit para actualización dinámica sin submit.

---

## Archivos del proyecto
```
raiz/
├── app.py                    gate admin + auth gate + chat + PDF download + alertas
├── admin_dashboard.py        dashboard admin (5 tabs para fcc, 3 para orientador/secretaria)
├── auth.py                   login estudiante, asentimiento, recuperación de ID
├── database.py               Supabase + SQLite adapter
├── email_service.py          SMTP Gmail (ID, recuperación, alerta crítica 3 destinatarios)
├── pdf_generator.py          PDFs con WeasyPrint + HTML/CSS  ← NO TOCAR
├── whatsapp_service.py       re-engagement por WhatsApp con Twilio real
├── instrucciones.txt         system prompt pedagógico  ← NO TOCAR
├── schema.sql                schema PostgreSQL + seed data  ← NO TOCAR
├── requirements.txt
├── packages.txt              dependencias apt para WeasyPrint en Streamlit Cloud
├── templates/
│   ├── mapa_estudiante.html  plantilla PDF estudiante
│   └── ficha_orientador.html plantilla PDF orientador
├── static/fonts/             fuentes woff2 locales (DM Sans, DM Serif Display)
├── migrations/
│   ├── 002_roles_y_consentimiento.sql
│   ├── 003_rector_instituciones.sql
│   ├── 004_supresion_retencion.sql
│   ├── 005_whatsapp.sql
│   └── 006_envios_ficha.sql  tabla de registro de envíos al orientador
└── .streamlit/
    └── secrets.toml          (gitignored — credenciales reales locales)
```

---

## Secrets requeridos (Streamlit Cloud → Settings → Secrets)
```toml
GEMINI_API_KEY         = "..."
SUPABASE_URL           = "https://doihxpicgfvmrcntzykl.supabase.co"
SUPABASE_SERVICE_KEY   = "..."
SMTP_EMAIL             = "..."
SMTP_APP_PASSWORD      = "..."
GRADOS_HABILITADOS     = "9"
PEAS_EMAIL             = ""
ADMIN_PASSWORD         = "raiz2026"
TWILIO_ACCOUNT_SID     = "..."
TWILIO_AUTH_TOKEN      = "..."
TWILIO_WHATSAPP_NUMBER = "whatsapp:+57XXXXXXXXXX"
APP_URL                = "https://raiz-piloto.streamlit.app"
```
