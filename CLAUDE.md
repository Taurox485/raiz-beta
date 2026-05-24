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

**Dashboard administrador (`admin_dashboard.py`):**
- Acceso vía `/?admin=1`, protegido con email + `ADMIN_PASSWORD` en secrets
- Tres roles: `fcc` (todas las instituciones), `orientador` (su institución), `secretaria` (todas — lectura)
- Tabs: registrar estudiante (con upload de autorización firmada), lista de estudiantes, alertas pendientes
- Admin de prueba en Supabase: `admin@fcc.edu.co` / contraseña en `ADMIN_PASSWORD`

**Base de datos (`database.py`):**
- Adapter dual: Supabase (prod) / SQLite (dev offline, `raiz_local.db`)
- Detección automática por `SUPABASE_URL` en secrets
- Schema en `schema.sql` + migración `migrations/002_roles_y_consentimiento.sql` (aplicados en Supabase)
- Tablas: `municipios`, `instituciones`, `sedes`, `estudiantes`, `mensajes`, `alertas`, `administradores`
- Seed data: 11 municipios y ~25 instituciones reales del Valle del Cauca

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
- Implementada con Playwright + plantillas HTML/CSS (`templates/`)
- `generar_pdfs(estudiante, historial, client, model, system_instruction) → (bytes, bytes)`
- Llama a Gemini para extraer datos estructurados (Holland, fortalezas, nudges, riesgo)
- PDF estudiante: "Mi Mapa rAÍz" | PDF orientador: "Ficha de Acompañamiento"
- Incluye marca de agua de piloto
- Se activa en `app.py` al detectar `[FIN_CONSEJERIA]`; botón "Descargar mi Perfil"
- Envío por email al completar mentoría conectado vía `email_service.py`

**Email (`email_service.py`):**
- SMTP Gmail con contraseña de aplicación
- `enviar_id_registro()`, `enviar_id_recuperacion()`, `enviar_alerta_critica()`

### Pendiente (ver `raiz_claude_code_backlog.md` para detalle)
- **PENDIENTE 3** — Derecho de supresión de datos (Ley 1581)
- **PENDIENTE 4** — Tiempo de retención de datos (1 año calendario)
- **PENDIENTE 5** — Row Level Security (RLS) en Supabase
- **PENDIENTE 10** — Migrar auth admin a Supabase Auth (hoy: contraseña compartida)
- **PENDIENTE 11** — Campo `jurisdiccion` para rol `secretaria`
- **PENDIENTE 12** — Signed URLs para archivos de consentimiento
- **PENDIENTE 13** — Crear bucket `consentimientos` en Supabase (paso manual pre-deploy)

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
celular_hash                      VARCHAR(64)  -- SHA-256
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

### Migraciones aplicadas
```
migrations/
└── 002_roles_y_consentimiento.sql  ← aplicado en Supabase
```

### Decisiones de arquitectura
1. **Auth sin email:** Los estudiantes no usan Supabase Auth. Login = `SELECT * FROM estudiantes WHERE estudiante_id = ?`. Backend usa `service_role_key`. RLS desactivado en esta fase.
2. **Generación del ID:** `MUNICIPIO-GRADO-AÑO-XXXX`, correlativo por `(municipio_id, grado, año)`.
3. **Fallback SQLite:** `database.py` detecta si `SUPABASE_URL` está configurado. Si no, usa SQLite. Mismo API, distinto backend.
4. **Celular:** SHA-256 hash. No se usa para login.
5. **Contacto flexible:** Al menos uno de email o celular_hash es obligatorio (CHECK constraint).

---

## Archivos del proyecto
```
raiz/
├── app.py                    gate admin + auth gate + chat + PDF download + alertas
├── admin_dashboard.py        dashboard admin (login, registro est., lista, alertas)
├── auth.py                   login estudiante, asentimiento, recuperación de ID
├── database.py               Supabase + SQLite adapter
├── email_service.py          SMTP Gmail (ID, recuperación, alerta crítica 3 destinatarios)
├── pdf_generator.py          PDFs con Playwright + HTML/CSS
├── instrucciones.txt         system prompt pedagógico
├── schema.sql                schema PostgreSQL + seed data
├── requirements.txt
├── templates/
│   ├── mapa_estudiante.html  plantilla PDF estudiante
│   └── ficha_orientador.html plantilla PDF orientador
├── migrations/
│   └── 002_roles_y_consentimiento.sql
└── .streamlit/
    └── secrets.toml          (gitignored — credenciales reales locales)
```

---

## Secrets requeridos (Streamlit Cloud → Settings → Secrets)
```toml
GEMINI_API_KEY       = "..."
SUPABASE_URL         = "https://doihxpicgfvmrcntzykl.supabase.co"
SUPABASE_SERVICE_KEY = "..."
SMTP_EMAIL           = "..."
SMTP_APP_PASSWORD    = "..."
GRADOS_HABILITADOS   = "9"
PEAS_EMAIL           = ""
ADMIN_PASSWORD       = "raiz2026"
```
