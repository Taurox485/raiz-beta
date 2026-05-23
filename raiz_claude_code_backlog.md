# rAÍz — Backlog técnico para Claude Code
**Preparado por:** Juan C. Reyes  
**Fecha:** Mayo 2026  
**Contexto:** Este documento consolida todos los cambios de arquitectura, schema y código derivados de la revisión del system prompt (instrucciones.txt), los comentarios de la coach psicóloga, la Política PEAS de Corpoeducación y la Ley 1581 de 2012. Debe leerse junto con CLAUDE.md antes de iniciar cualquier implementación.

---

## PRIORIDAD CRÍTICA — Cambios que bloquean el piloto

### PENDIENTE 1 — Rediseño completo del flujo de registro

**Contexto legal:**
La Ley 1581 de 2012 establece que los menores de edad no pueden otorgar consentimiento autónomo para el tratamiento de sus datos personales. El flujo actual (el estudiante se registra solo y acepta el habeas data) es legalmente inválido. El registro debe ser gestionado por un administrador autorizado que certifique que el acudiente firmó la autorización previa.

**Nuevo flujo aprobado:**

**Fase 0 — Pre-registro presencial (fuera de la app)**
El orientador, personal de FCC o la Secretaría de Educación recopila la autorización firmada del acudiente en papel. Solo después de tener esa firma física, el administrador puede crear el registro del estudiante en el sistema.

**Fase 1 — Registro por administrador (en la app)**
Un usuario con rol de administrador crea el registro del estudiante: nombre, apellido, grado, municipio, institución. El sistema genera el `estudiante_id` automáticamente. El administrador marca `consentimiento_acudiente_verificado = TRUE`, certificando que la firma física fue recopilada.

**Fase 2 — Primer acceso del estudiante**
El estudiante llega a la app con su `estudiante_id` ya creado por el administrador. No se registra — solo inicia sesión. En ese primer acceso ve el asentimiento informado propio (lenguaje simple, adaptado a su edad) y lo acepta. Solo entonces accede al chat.

**Roles de administrador definidos — tres perfiles:**
1. **FCC (Fundación Corazón de Caña)** — acceso global a todas las instituciones
2. **Docentes orientadores / psicoorientadores** — acceso restringido a su propia institución
3. **Secretaría de Educación** — acceso de supervisión (lectura) a instituciones de su jurisdicción

**Cambios requeridos en schema (migrations/002_roles_y_consentimiento.sql):**

```sql
-- Tabla de administradores
CREATE TABLE administradores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    rol VARCHAR(30) NOT NULL CHECK (rol IN ('fcc', 'orientador', 'secretaria')),
    institucion_id INTEGER REFERENCES instituciones(id), -- NULL para fcc y secretaria
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW()
);

-- Cambios en tabla estudiantes
ALTER TABLE estudiantes
    ADD COLUMN consentimiento_acudiente_verificado BOOLEAN DEFAULT FALSE,
    ADD COLUMN fecha_verificacion_acudiente TIMESTAMPTZ,
    ADD COLUMN administrador_registro_id UUID REFERENCES administradores(id),
    ADD COLUMN consentimiento_datos_sensibles BOOLEAN DEFAULT FALSE,
    ADD COLUMN fecha_consentimiento_sensibles TIMESTAMPTZ;

-- El campo consentimiento_habeas_data existente pasa a ser
-- el asentimiento informado del propio estudiante (complementario)
-- Renombrar para claridad:
ALTER TABLE estudiantes
    RENAME COLUMN consentimiento_habeas_data TO asentimiento_estudiante;
ALTER TABLE estudiantes
    RENAME COLUMN fecha_consentimiento TO fecha_asentimiento_estudiante;
```

**Cambios requeridos en app.py y auth.py:**
- Crear vista/pantalla de administrador separada del flujo de estudiante
- La pantalla de administrador requiere autenticación propia (email + contraseña, gestionada por Supabase Auth — solo para administradores, no para estudiantes)
- Formulario de registro de estudiante accesible solo desde sesión de administrador
- El flujo de registro actual del estudiante desaparece completamente
- El asentimiento informado del estudiante se muestra en el primer login (cuando `asentimiento_estudiante = FALSE`), no en el registro
- Validar que `consentimiento_acudiente_verificado = TRUE` antes de permitir cualquier acceso al chat

---

### PENDIENTE 2 — Tres niveles de notificación en alertas críticas

**Contexto:**
La Política PEAS de Corpoeducación establece que ante cualquier sospecha de abuso o violencia, la notificación no debe limitarse a una sola persona — el presunto agresor podría ser alguien del entorno escolar inmediato, incluyendo el orientador. La arquitectura actual solo notifica al orientador.

**Nuevo comportamiento requerido:**
La etiqueta `[ALERTA_PSICOLOGICA_CRITICA]` debe disparar notificación simultánea e inmediata a tres destinatarios:
1. `orientador_email` — campo ya existente en tabla `instituciones`
2. `rector_email` — campo nuevo, ver schema abajo
3. Email fijo de punto focal PEAS de Corpoeducación/FCC — configurable en `secrets.toml`

**Cambios requeridos en schema:**

```sql
-- Añadir rector a tabla instituciones
ALTER TABLE instituciones
    ADD COLUMN rector_nombre VARCHAR(200),
    ADD COLUMN rector_email VARCHAR(200);
```

**Cambios requeridos en tabla alertas:**

```sql
-- Registrar a quién se notificó y cuándo
ALTER TABLE alertas
    ADD COLUMN notificado_orientador BOOLEAN DEFAULT FALSE,
    ADD COLUMN notificado_rector BOOLEAN DEFAULT FALSE,
    ADD COLUMN notificado_peas BOOLEAN DEFAULT FALSE,
    ADD COLUMN timestamp_notificacion TIMESTAMPTZ;
```

**Cambios requeridos en app.py:**
- La lógica de detección de `[ALERTA_PSICOLOGICA_CRITICA]` debe llamar a `email_service.py` con tres destinatarios en paralelo, no secuencialmente
- Si alguna notificación falla, registrar el fallo en la tabla `alertas` y reintentar
- Añadir a `secrets.toml`: `PEAS_EMAIL = "email_punto_focal_corpoeducacion"` (a definir con Corpoeducación)

**Nota:** `[ALERTA_ORIENTADOR_REQUERIDA]` (riesgo de deserción, no crisis aguda) mantiene notificación solo al orientador — no requiere escalamiento a rector ni PEAS.

---

## PRIORIDAD ALTA — Cambios importantes antes de producción

### PENDIENTE 3 — Derecho de supresión de datos (Ley 1581)

**Contexto:**
La Ley 1581 garantiza al titular (o su representante legal) el derecho a solicitar la eliminación de sus datos. El sistema actual no tiene mecanismo para esto.

**Cambios requeridos en schema:**

```sql
ALTER TABLE estudiantes
    ADD COLUMN suprimido BOOLEAN DEFAULT FALSE,
    ADD COLUMN fecha_supresion TIMESTAMPTZ,
    ADD COLUMN motivo_supresion TEXT;
```

**Comportamiento requerido:**
- Cuando `suprimido = TRUE`, anonimizar todos los datos personales identificables: nombre → 'SUPRIMIDO', apellido → 'SUPRIMIDO', celular_hash → NULL
- Los mensajes asociados deben eliminarse de la tabla `mensajes`
- Las alertas asociadas deben eliminarse de la tabla `alertas`
- Mantener solo el registro anonimizado para estadísticas agregadas (municipio, grado, sesion_actual, perfil_riesgo)
- El canal de solicitud de supresión es el orientador → escala a FCC → FCC ejecuta en el sistema

### PENDIENTE 4 — Tiempo de retención de datos

**Contexto:**
La Ley 1581 exige definir el período máximo de retención. Definición aprobada: un año calendario después de que el estudiante termine el año escolar en que usó rAÍz.

**Cambios requeridos en schema:**

```sql
ALTER TABLE estudiantes
    ADD COLUMN fecha_retencion_hasta DATE; -- calculada al registro: 31-dic del año siguiente
```

**Cambios requeridos en app.py o script separado:**
- Proceso periódico (cron o trigger de Supabase) que identifique registros con `fecha_retencion_hasta < NOW()` y ejecute la supresión automática
- Notificar a FCC antes de ejecutar supresiones masivas

### PENDIENTE 5 — Row Level Security (RLS) en Supabase para datos sensibles

**Contexto:**
RLS está actualmente desactivado. En producción, los datos sensibles (perfil_riesgo, contenido de mensajes con alertas) deben tener acceso restringido por rol.

**Políticas RLS requeridas:**
- Estudiantes: cada estudiante solo puede leer sus propios mensajes
- Orientadores: pueden leer datos de estudiantes de su institución únicamente
- FCC: acceso completo a todas las instituciones
- Secretaría: acceso de solo lectura, sin acceso a contenido de mensajes
- Tabla alertas: solo orientador de la institución, rector, y FCC

---

## PRIORIDAD MEDIA — Mejoras para el piloto

### PENDIENTE 6 — Vista de administrador (dashboard básico)

**Funcionalidades mínimas requeridas:**
- Login de administrador (Supabase Auth, separado del flujo de estudiante)
- Registro de nuevo estudiante con confirmación de consentimiento de acudiente
- Lista de estudiantes de la institución con estado: sesión actual, perfil de riesgo, alertas pendientes
- Visualización de alertas pendientes con indicador de urgencia
- Descarga de PDF del reporte del orientador desde el dashboard (sin necesidad de que el estudiante lo genere)

**Nota de diseño:**
El dashboard del orientador era la Fase 2 definida en CLAUDE.md. Este pendiente lo adelanta parcialmente porque el flujo de registro lo hace necesario antes del piloto.

### PENDIENTE 7 — Consentimiento diferenciado para datos sensibles

**Contexto:**
El asentimiento informado del estudiante en el primer login debe incluir consentimiento explícito diferenciado para datos sensibles (Ley 1581, Art. 6), separado del consentimiento general.

**Implementación:**
- Dos checkboxes en el asentimiento del estudiante:
  1. Consentimiento general de tratamiento de datos → `asentimiento_estudiante`
  2. Consentimiento específico para datos sensibles (salud, situación socioeconómica) → `consentimiento_datos_sensibles`
- Ambos son requeridos para acceder al chat
- El lenguaje debe ser simple y comprensible para un adolescente de 14-16 años

### PENDIENTE 8 — Marca de agua en PDFs

*(Ya estaba identificado en CLAUDE.md)*

Añadir marca de agua "PILOTO — MAYO 2026" en todos los PDFs generados por `pdf_generator.py`. Usar fpdf2 para overlay de texto diagonal semitransparente en cada página.

### PENDIENTE 9 — Envío de PDFs por email al completar mentoría

*(Ya estaba identificado en CLAUDE.md)*

Conectar `pdf_generator.py` con `email_service.py`:
- Al detectar `[FIN_CONSEJERIA]`, generar ambos PDFs
- Enviar PDF estudiante a... (pendiente: ¿a qué email? el estudiante no tiene email verificado — revisar canal alternativo, posiblemente WhatsApp)
- Enviar PDF orientador a `orientador_email` de la tabla `instituciones`
- Con el nuevo esquema de alertas: copiar al rector si hay alertas activas

---

## PENDIENTES DE DEFINICIÓN — Requieren decisión antes de implementar

### DECISIÓN 1 — Canal de entrega del PDF al estudiante
El estudiante no tiene email verificado y la penetración de email en la población objetivo es baja. Opciones:
- A) Descarga directa desde la app al finalizar la mentoría (ya implementado el botón)
- B) Envío por WhatsApp (requiere integración con WhatsApp Business API — complejidad alta)
- C) El orientador imprime y entrega el PDF al estudiante en la reunión presencial

**Recomendación:** Opción C para el piloto, A como respaldo digital. B para versión futura.

### DECISIÓN 2 — ¿Quién crea los registros de administradores?
¿FCC crea las cuentas de orientadores manualmente, o hay un flujo de auto-registro de orientadores con validación por FCC? Para el piloto: FCC crea manualmente. Para escala: flujo de invitación por email.

### DECISIÓN 3 — Formato físico de autorización de acudientes
Debe ser diseñado por Corpoeducación y/o FCC en coordinación con las instituciones educativas, antes del inicio del piloto. rAÍz no puede operar legalmente con ningún estudiante cuyo acudiente no haya firmado este documento.

---

## Resumen de cambios por archivo

| Archivo | Cambios |
|---|---|
| `schema.sql` | Tabla `administradores`, campos nuevos en `estudiantes`, `instituciones`, `alertas` |
| `migrations/002_*.sql` | Migración con todos los ALTER TABLE |
| `app.py` | Vista administrador, flujo de primer login con asentimiento, tres niveles de notificación |
| `auth.py` | Eliminar flujo de registro de estudiante, añadir auth de administrador |
| `database.py` | Métodos para CRUD de administradores, supresión de datos, retención |
| `email_service.py` | Notificación a tres destinatarios en alertas críticas |
| `pdf_generator.py` | Marca de agua |
| `secrets.toml` | Añadir `PEAS_EMAIL` |
| `CLAUDE.md` | Actualizar estado con estos pendientes |

---

*Documento generado en sesión de revisión del system prompt — Mayo 2026*  
*Próxima acción: implementar en Claude Code en el orden de prioridad indicado*

---

## MÓDULO WHATSAPP — Re-engagement automatizado

### Contexto
Sistema de mensajes automáticos por WhatsApp para reactivar estudiantes que iniciaron el proceso pero no han avanzado. Canal: Twilio WhatsApp API. Volumen piloto: 300 estudiantes × 5 mensajes = 1,500 mensajes (~$75 USD).

### Configuración requerida en secrets.toml
```toml
TWILIO_ACCOUNT_SID = "..."
TWILIO_AUTH_TOKEN = "..."
TWILIO_WHATSAPP_NUMBER = "whatsapp:+57XXXXXXXXXX"  # número prepago registrado en Twilio
APP_URL = "https://raiz-beta-5kpec9cahh2dpgw56vpxsj.streamlit.app"
```

### Schema — cambios requeridos

```sql
-- Tabla de mensajes WhatsApp enviados (evita duplicados y registra historial)
CREATE TABLE whatsapp_mensajes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id   UUID REFERENCES estudiantes(id),
    tipo_mensaje    INTEGER CHECK (tipo_mensaje BETWEEN 1 AND 5),
    enviado_at      TIMESTAMPTZ DEFAULT NOW(),
    estado          VARCHAR(20) DEFAULT 'enviado'  -- enviado / fallido
);
```

### Los 5 mensajes — variables: {nombre}, {codigo}, {link}

**Mensaje 1** — Día 1 después del registro, nunca entró al chat:
> ¡Hola, {nombre}! 🌱 Soy rAÍz, tu mentor de proyecto de vida. Ya tenés tu cuenta lista — solo falta que arranquemos. Vamos a tener 4 conversaciones donde vas a descubrir cosas importantes sobre vos: tus intereses, tus fortalezas y lo que querés para tu futuro. Tu código de ingreso es: *{codigo}* ¿Le entramos? Entrá acá: {link}

**Mensaje 2** — 2 días después de completar S1 sin entrar a S2:
> ¡Hola, {nombre}! La última vez hablamos de tu día a día y de las cosas que te mueven. Me quedé con ganas de seguir conociéndote 🌿 En la próxima charla vamos a descubrir para qué sos realmente bueno/a. Tu código: *{codigo}* ¿Seguimos? Entrá acá: {link}

**Mensaje 3** — 2 días después de completar S2 sin entrar a S3:
> ¡Hola, {nombre}! Ya descubriste cosas importantes sobre vos — tus intereses y tus fortalezas. Ahora viene la parte más interesante: hablar de lo que imaginás para tu futuro 🌱 Tu código: *{codigo}* ¿Le damos? Entrá acá: {link}

**Mensaje 4** — 2 días después de completar S3 sin entrar a S4:
> ¡Hola, {nombre}! Ya estás en la última charla — ¡casi terminás! 🎯 En esta sesión te voy a mostrar todo lo que descubrimos juntos sobre vos. Tu código: *{codigo}* Entrá acá: {link}

**Mensaje 5** — 7 días sin actividad en cualquier punto, último intento:
> ¡Hola, {nombre}! Sé que el tiempo a veces no alcanza para todo 😊 Pero tu proceso de rAÍz te está esperando — podés retomarlo exactamente donde lo dejaste, sin empezar de cero. Tu código: *{codigo}* ¿Le damos una última oportunidad? Entrá acá: {link}

### Lógica del proceso periódico (whatsapp_service.py)

```python
# Reglas de activación — evaluar en este orden:
# 1. sesion_actual == 1 AND momento_actual == 1 AND nunca tuvo mensajes
#    AND fecha_registro < NOW() - INTERVAL '1 day'
#    → Mensaje 1

# 2. sesion_actual == 2 AND momento_actual == 1
#    AND ultimo_mensaje_whatsapp tipo != 2
#    AND ultimo_mensaje_chat < NOW() - INTERVAL '2 days'
#    → Mensaje 2

# 3. sesion_actual == 3 AND momento_actual == 1
#    AND ultimo_mensaje_whatsapp tipo != 3
#    AND ultimo_mensaje_chat < NOW() - INTERVAL '2 days'
#    → Mensaje 3

# 4. sesion_actual == 4 AND momento_actual == 1
#    AND ultimo_mensaje_whatsapp tipo != 4
#    AND ultimo_mensaje_chat < NOW() - INTERVAL '2 days'
#    → Mensaje 4

# 5. mentoria_completada == FALSE
#    AND ultimo_mensaje_chat < NOW() - INTERVAL '7 days'
#    AND ultimo_mensaje_whatsapp tipo != 5
#    → Mensaje 5

# NUNCA enviar más de 1 mensaje por tipo por estudiante
# NUNCA enviar si mentoria_completada == TRUE
# Horario de envío: entre 16:00 y 18:00 hora Colombia (UTC-5)
```

### Archivos a crear/modificar
- `whatsapp_service.py` — nuevo archivo con lógica de envío y proceso periódico
- `database.py` — métodos para consultar estudiantes elegibles y registrar envíos
- `schema.sql` — tabla whatsapp_mensajes
- `migrations/003_whatsapp.sql` — ALTER/CREATE para producción
- `secrets.toml` — añadir credenciales Twilio
- `requirements.txt` — añadir `twilio`

### Ejecución del proceso periódico
Para el piloto: correr manualmente o con un cron job simple.
Para producción: Supabase Edge Functions o un scheduler externo.

### Instalación
```bash
pip install twilio
```

---

## PENDIENTES DE PRODUCCIÓN — Surgidos del dashboard admin

### PENDIENTE 10 — Migrar auth de admin a Supabase Auth por usuario
**Contexto:** Para el piloto se usa una contraseña compartida (`ADMIN_PASSWORD` en secrets.toml) para todos los administradores. Esto es aceptable para 300 estudiantes en un piloto controlado, pero no escala.
**Para producción:** Cada administrador debe tener su propia cuenta en Supabase Auth con email + contraseña individual. El login de admin_dashboard.py debe autenticar contra Supabase Auth en lugar de la contraseña hardcodeada.
**Archivos a modificar:** `admin_dashboard.py`, `secrets.toml`

### PENDIENTE 11 — Campo jurisdiccion para scope regional de Secretaría
**Contexto:** El rol `secretaria` actualmente ve todas las instituciones igual que `fcc`. El campo `jurisdiccion` no existe en el schema.
**Para producción:** Agregar campo `jurisdiccion` a la tabla `administradores` para limitar el scope de la Secretaría de Educación del Valle a sus instituciones y municipios específicos.
**Archivos a modificar:** `schema.sql`, `migrations/003_...sql`, `database.py`

### PENDIENTE 12 — Crear bucket 'consentimientos' en Supabase antes del deploy
**Contexto:** El dashboard admin sube archivos de consentimiento al bucket `consentimientos` en Supabase Storage. Este bucket debe crearse manualmente antes del primer deploy a Streamlit Cloud.
**Acción manual requerida:** En el dashboard de Supabase → Storage → New bucket → nombre: `consentimientos` → público (por ahora).
**Bloqueante para:** Subida de archivos de consentimiento en producción. No bloqueante para desarrollo local (guarda en carpeta `consentimientos/`).

### PENDIENTE 13 — Migrar URLs de consentimiento a signed URLs
**Contexto:** Los archivos de consentimiento de menores de edad se guardan en un bucket público de Supabase Storage. Las URLs son accesibles por cualquiera que tenga el link.
**Para producción:** Cambiar el bucket a privado y usar signed URLs con expiración para acceder a los archivos. Esto protege datos de menores conforme a la Ley 1581/2012.
**Archivos a modificar:** `admin_dashboard.py`, `database.py`
**Impacto:** Las URLs guardadas en `consentimiento_archivo_url` deberán generarse dinámicamente en lugar de almacenarse estáticas.
