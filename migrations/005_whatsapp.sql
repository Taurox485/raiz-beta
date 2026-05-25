-- migrations/005_whatsapp.sql
-- P14: Módulo WhatsApp re-engagement
--
-- Aplicar en Supabase SQL Editor antes del deploy.
-- SQLite: _ensure_sqlite() en database.py aplica el equivalente automáticamente.

-- Columna celular en texto plano (Opción B del piloto — ver DEUDA TÉCNICA 1 en backlog)
ALTER TABLE estudiantes
    ADD COLUMN IF NOT EXISTS celular TEXT;

-- Historial de mensajes WhatsApp enviados (evita duplicados, registra estado)
CREATE TABLE IF NOT EXISTS whatsapp_mensajes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id   UUID NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    mensaje_numero  INTEGER NOT NULL CHECK (mensaje_numero BETWEEN 1 AND 5),
    enviado_at      TIMESTAMPTZ DEFAULT NOW(),
    estado          VARCHAR(20) DEFAULT 'enviado'  -- enviado / fallido
);
