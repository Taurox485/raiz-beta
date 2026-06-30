-- Migración 010: Políticas RLS faltantes para sedes e instituciones
-- Ejecutar en el SQL Editor de Supabase.
--
-- Contexto: La migración 008 habilitó RLS en sedes e instituciones
-- pero no definió políticas de SELECT. En PostgreSQL, RLS sin políticas
-- bloquea todo acceso a usuarios autenticados (anon/authenticated).
-- Esto no afecta el backend (usa service_role_key que bypassa RLS),
-- pero bloquearía cualquier acceso futuro vía JWT de administrador.

-- INSTITUCIONES: todos los administradores activos pueden ver todas las instituciones.
-- Son datos de catálogo público dentro del sistema — no hay información sensible aquí.
CREATE POLICY "Admins_select_instituciones" ON instituciones
    FOR SELECT
    USING (get_user_rol() IS NOT NULL);

-- SEDES: acceso según rol.
-- fcc y secretaria ven todas las sedes (scope global).
-- orientador y rector solo ven las sedes de su propia institución.
CREATE POLICY "Admins_select_sedes" ON sedes
    FOR SELECT
    USING (
        get_user_rol() IN ('fcc', 'secretaria')
        OR (
            get_user_rol() IN ('orientador', 'rector')
            AND institucion_id = get_user_institucion()
        )
    );
