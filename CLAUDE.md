# rAÍz — Contexto del Proyecto para Claude Code

## Qué es rAÍz
Chatbot de orientación vocacional para estudiantes de **grado 9° (14-16 años)** en municipios del valle geográfico del Río Cauca, Colombia. Es un mentor de proyecto de vida impulsado por IA que acompaña al estudiante a través de 4 sesiones estructuradas de autoconocimiento.

El ecosistema económico gira en torno a la caña de azúcar y la agricultura. Muchos estudiantes trabajan para ayudar a sus familias y podrían ser la primera generación con acceso a educación post-secundaria. El tono debe ser cálido, cercano, en español colombiano del Valle del Cauca.

## Stack técnico actual
- `app.py` — Streamlit + Google GenAI SDK (`google-genai`)
- `instrucciones.txt` — system prompt pedagógico, cargado en tiempo de ejecución
- Modelo: `gemini-3.1-flash-lite`
- API key via `st.secrets["GEMINI_API_KEY"]`

## Arquitectura pedagógica (leer instrucciones.txt completo)
- 4 sesiones × 5 momentos, avance estrictamente secuencial
- 1 sola pregunta por turno — regla crítica
- Metodologías camufladas: Holland, Ikigai, Covey adaptado, SCCT, Ubuntu
- Etiquetas internas que el estudiante nunca ve: `[FIN_CONSEJERIA]`, `[RIESGO_BAJO/MEDIO/ALTO]`, `[ALERTA_ORIENTADOR_REQUERIDA]`, `[ALERTA_PSICOLOGICA_CRITICA]`
- `limpiar_etiquetas()` en app.py filtra estas etiquetas antes de mostrar en pantalla

## Guardrails críticos (no negociables)
- PROHIBIDO recomendar carreras universitarias, instituciones o programas de educación superior
- PROHIBIDO juzgar estructura familiar, trabajo infantil, bajo rendimiento o dificultades económicas
- Habeas data colombiano (Ley 1581/2012) — consentimiento explícito obligatorio en primer registro

## Estado actual del código

### Implementado y funcional
- Auth completa: registro, login, consentimiento habeas data, recuperación de ID por email
- Base de datos: `database.py` con adapter SQLite (dev) / Supabase (prod)
- Schema SQL en `schema.sql`, seed data real de 11 municipios y ~25 instituciones del Valle del Cauca
- Chat con historial persistente; retoma de sesión reconstruyendo contexto Gemini desde DB
- Alertas al orientador guardadas en DB (`alertas` table) al detectar etiquetas internas
- Perfil de riesgo actualizado en DB por turno
- **Generación de PDFs (`pdf_generator.py`):** implementada con `fpdf2`
  - `generar_pdfs(estudiante, historial, client, model, system_instruction) → (bytes, bytes)`
  - Llama a Gemini para extraer datos estructurados (Holland, fortalezas, nudges, riesgo)
  - Genera PDF estudiante ("Mi Mapa rAÍz") y PDF orientador ("Ficha de Acompañamiento")
  - Se activa en `app.py` al detectar `[FIN_CONSEJERIA]`; botón "Descargar mi Perfil"
  - `test_pdf.py` en raíz para pruebas manuales con estudiante `ALC-9-2026-0001`

### Pendiente
- **SMTP:** envío de PDFs por email al estudiante y al orientador (secrets configurados, lógica no conectada a pdf_generator)
- **Marca de agua** en PDFs antes de producción
- **Deploy** a Streamlit Cloud

---

## FASE 1 — Completada: Supabase + Autenticación

### Schema de base de datos aprobado (5 tablas)

#### `municipios` (seed, solo lectura)
```
id          SERIAL PK
codigo      VARCHAR(5) UNIQUE   -- ej: ALC, CAN, VIJ (parte del estudiante_id)
nombre      VARCHAR(100)
```

#### `instituciones` (seed, administrada por el equipo rAÍz)
```
id                  SERIAL PK
nombre              VARCHAR(200)
municipio_id        FK → municipios
orientador_nombre   VARCHAR(200)
orientador_email    VARCHAR(200)    -- destino de alertas y reportes
orientador_telefono VARCHAR(20)     -- opcional
```

#### `estudiantes` (tabla core)
```
id                          UUID PK (gen_random_uuid())
estudiante_id               VARCHAR(25) UNIQUE   -- ej: ALC-9-2026-0042
nombre                      VARCHAR(100)
apellido                    VARCHAR(100)
grado                       INTEGER CHECK(9-11)
celular_hash                VARCHAR(64)          -- SHA-256, nunca texto plano
municipio_id                FK → municipios
institucion_id              FK → instituciones
consentimiento_habeas_data  BOOLEAN DEFAULT FALSE
fecha_consentimiento        TIMESTAMPTZ          -- registro legal obligatorio
fecha_registro              TIMESTAMPTZ DEFAULT NOW()
sesion_actual               INTEGER DEFAULT 1    -- 1-4, para retomar sesión
momento_actual              INTEGER DEFAULT 1    -- 1-5, granularidad de momento
perfil_riesgo               VARCHAR(20) DEFAULT 'sin_evaluar'  -- bajo/medio/alto
mentoria_completada         BOOLEAN DEFAULT FALSE
```

#### `mensajes` (historial de chat)
```
id              UUID PK
estudiante_id   UUID FK → estudiantes (CASCADE)
sesion_numero   INTEGER
rol             VARCHAR(10)   -- 'user' o 'model' (vocabulario del SDK de Gemini)
contenido       TEXT          -- texto crudo CON etiquetas internas (no limpiado)
timestamp       TIMESTAMPTZ DEFAULT NOW()
tiene_alerta    BOOLEAN DEFAULT FALSE
```
> El contenido se guarda crudo (con etiquetas) porque al reconstruir la sesión de Gemini en el reingreso, el SDK necesita el historial completo para mantener coherencia del modelo.

#### `alertas` (canal al orientador)
```
id                UUID PK
estudiante_id     UUID FK → estudiantes
institucion_id    FK → instituciones
tipo              VARCHAR(40)   -- 'orientador_requerida' | 'psicologica_critica'
estado            VARCHAR(20) DEFAULT 'pendiente'   -- pendiente/vista/resuelta
timestamp         TIMESTAMPTZ DEFAULT NOW()
nota_resolucion   TEXT
```

### Decisiones de arquitectura aprobadas

1. **Auth sin email:** Los estudiantes no usan Supabase Auth. Login = `SELECT * FROM estudiantes WHERE estudiante_id = ?`. Backend usa `service_role_key`. RLS desactivado en esta fase.

2. **Generación del ID:** `MUNICIPIO-GRADO-AÑO-XXXX` donde XXXX es correlativo por `(municipio_id, grado, año)`, calculado con `COUNT(*) + 1` en la misma transacción, zero-padded a 4 dígitos.

3. **Fallback SQLite:** `database.py` detecta si `SUPABASE_URL` está configurado. Si no, usa SQLite con el mismo schema. Mismo API, distinto backend. Permite desarrollar offline sin cambiar nada en `app.py`.

4. **Habeas data:** Pantalla de consentimiento en primer registro con checkbox explícito. Sin consentimiento = sin acceso al chat. `fecha_consentimiento` se graba con timestamp preciso.

5. **Celular:** SHA-256 hash. No se usa para login. Se hashea para cumplimiento legal y eventual recuperación de ID.

### Migraciones
Los cambios de schema se manejan con archivos SQL numerados en `migrations/`:
```
migrations/
├── 001_schema_inicial.sql    ← aún por crear
└── 002_...                   ← cambios futuros
```

### Archivos creados (Fase 1)
```
raiz/
├── app.py                    auth gate + chat + PDF download + alertas → DB
├── database.py               Supabase + SQLite adapter
├── auth.py                   registro, login, consentimiento, recuperación de ID
├── pdf_generator.py          generación de PDFs con fpdf2 + Gemini
├── email_service.py          SMTP Gmail (envío de ID; PDF pendiente de conectar)
├── test_pdf.py               prueba manual de pdf_generator
├── requirements.txt
├── schema.sql                schema PostgreSQL + seed data para Supabase
└── .streamlit/
    └── secrets.toml          plantilla (GEMINI_API_KEY real, SMTP pendiente)
```

---

## Fases futuras

- **Fase 2:** Dashboard del orientador (alertas pendientes + lista de estudiantes)
- **Fase 4:** Canal de alertas en tiempo real (email/WhatsApp al orientador)
