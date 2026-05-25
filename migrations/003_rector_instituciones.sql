-- migrations/003_rector_instituciones.sql
-- Correctivo: las columnas rector_nombre y rector_email de la migración 002
-- no se aplicaron en la tabla instituciones de Supabase.
-- Requeridas por PENDIENTE 16 (módulo gestión instituciones FCC).

ALTER TABLE instituciones
    ADD COLUMN IF NOT EXISTS rector_nombre VARCHAR(200),
    ADD COLUMN IF NOT EXISTS rector_email  VARCHAR(200);
