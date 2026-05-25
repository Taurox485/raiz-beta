-- migrations/004_supresion_retencion.sql
-- P3: Derecho de supresión de datos (Ley 1581/2012)
-- P4: Tiempo de retención de datos (1 año calendario tras el año escolar)
--
-- Aplicar en Supabase SQL Editor antes del deploy.
-- SQLite: _ensure_sqlite() en database.py aplica el equivalente automáticamente.

ALTER TABLE estudiantes
    ADD COLUMN IF NOT EXISTS suprimido             BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fecha_supresion       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS motivo_supresion      TEXT,
    ADD COLUMN IF NOT EXISTS fecha_retencion_hasta DATE;
