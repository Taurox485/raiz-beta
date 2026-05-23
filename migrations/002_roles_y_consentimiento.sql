-- migrations/002_roles_y_consentimiento.sql
-- Prioridad Crítica: PENDIENTE 1 + PENDIENTE 2 del backlog técnico rAÍz
--
-- Aplicar en Supabase cuando el esquema v001 (schema.sql) esté en producción.
-- NO aplicar en SQLite — _ensure_sqlite() en database.py maneja el fallback offline.
--
-- Contexto legal:
--   PENDIENTE 1: Ley 1581/2012 — menores no pueden otorgar consentimiento autónomo.
--                El registro pasa a ser responsabilidad del administrador autorizado.
--   PENDIENTE 2: Política PEAS Corpoeducación — alertas críticas notifican a tres
--                destinatarios simultáneos para evitar conflicto de interés.


-- ──────────────────────────────────────────────────────────────────────────────
-- PENDIENTE 1 — Roles de administrador y nuevo flujo de consentimiento
-- ──────────────────────────────────────────────────────────────────────────────

-- Tabla de administradores (tres perfiles: fcc, orientador, secretaria)
CREATE TABLE administradores (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre         VARCHAR(200) NOT NULL,
    email          VARCHAR(200) UNIQUE NOT NULL,
    rol            VARCHAR(30)  NOT NULL CHECK (rol IN ('fcc', 'orientador', 'secretaria')),
    institucion_id INTEGER      REFERENCES instituciones(id), -- NULL para fcc y secretaria
    activo         BOOLEAN      DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ  DEFAULT NOW()
);

-- Cambios en tabla estudiantes
ALTER TABLE estudiantes
    ADD COLUMN consentimiento_acudiente_verificado BOOLEAN     DEFAULT FALSE,
    ADD COLUMN fecha_verificacion_acudiente        TIMESTAMPTZ,
    ADD COLUMN administrador_registro_id           UUID        REFERENCES administradores(id),
    ADD COLUMN consentimiento_datos_sensibles      BOOLEAN     DEFAULT FALSE,
    ADD COLUMN fecha_consentimiento_sensibles      TIMESTAMPTZ;

-- El campo consentimiento_habeas_data existente pasa a ser el asentimiento
-- informado del propio estudiante (complementario al consentimiento del acudiente).
-- Nota: PostgreSQL 10+ actualiza automáticamente la expresión del CHECK constraint
-- habeas_data_consistente al renombrar las columnas referenciadas.
ALTER TABLE estudiantes
    RENAME COLUMN consentimiento_habeas_data TO asentimiento_estudiante;
ALTER TABLE estudiantes
    RENAME COLUMN fecha_consentimiento TO fecha_asentimiento_estudiante;


-- ──────────────────────────────────────────────────────────────────────────────
-- PENDIENTE 2 — Tres niveles de notificación en alertas críticas
-- ──────────────────────────────────────────────────────────────────────────────

-- Añadir rector a tabla instituciones
ALTER TABLE instituciones
    ADD COLUMN rector_nombre VARCHAR(200),
    ADD COLUMN rector_email  VARCHAR(200);

-- Registrar a quién se notificó y cuándo en cada alerta
ALTER TABLE alertas
    ADD COLUMN notificado_orientador  BOOLEAN     DEFAULT FALSE,
    ADD COLUMN notificado_rector      BOOLEAN     DEFAULT FALSE,
    ADD COLUMN notificado_peas        BOOLEAN     DEFAULT FALSE,
    ADD COLUMN timestamp_notificacion TIMESTAMPTZ;


-- ──────────────────────────────────────────────────────────────────────────────
-- AJUSTE DE PILOTO — Medio de contacto flexible (email o celular, al menos uno)
-- ──────────────────────────────────────────────────────────────────────────────
-- Contexto: ~7% de estudiantes no tiene teléfono pero casi todos tienen email.
-- La regla es: al menos uno de los dos es obligatorio, no necesariamente ambos.
-- whatsapp_service.py filtra: WHERE celular_hash IS NOT NULL
-- Estudiantes con solo email recibirán recordatorios por email (implementación futura).

ALTER TABLE estudiantes
    ADD COLUMN celular_hash VARCHAR(64);

-- Email pasa a ser NULLable (ya no es NOT NULL UNIQUE — sigue siendo UNIQUE)
ALTER TABLE estudiantes
    ALTER COLUMN email DROP NOT NULL;

-- Restricción: al menos uno de los dos debe estar presente
ALTER TABLE estudiantes
    ADD CONSTRAINT check_contacto_requerido
    CHECK (email IS NOT NULL OR celular_hash IS NOT NULL);
