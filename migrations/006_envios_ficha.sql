-- Migración 006: tabla de envíos de ficha de acompañamiento al orientador
-- Aplicar en: Supabase SQL Editor → New query → Run
-- Idempotente: usa IF NOT EXISTS

CREATE TABLE IF NOT EXISTS envios_ficha (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id    UUID        NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    orientador_email VARCHAR(200) NOT NULL,
    exito            BOOLEAN     NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_envios_ficha_estudiante
    ON envios_ficha (estudiante_id, timestamp DESC);
