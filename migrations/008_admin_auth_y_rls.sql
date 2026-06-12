-- Migración 008: RLS (Row Level Security) y actualización de roles
-- Ejecutar en el SQL Editor de Supabase.

-- 1. Actualizar el CHECK constraint de roles para incluir 'rector'
ALTER TABLE administradores DROP CONSTRAINT IF EXISTS administradores_rol_check;
ALTER TABLE administradores ADD CONSTRAINT administradores_rol_check 
    CHECK (rol IN ('fcc', 'orientador', 'secretaria', 'rector'));

-- 2. Habilitar RLS en las tablas sensibles
ALTER TABLE estudiantes ENABLE ROW LEVEL SECURITY;
ALTER TABLE mensajes ENABLE ROW LEVEL SECURITY;
ALTER TABLE alertas ENABLE ROW LEVEL SECURITY;
ALTER TABLE instituciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE sedes ENABLE ROW LEVEL SECURITY;

-- Nota de arquitectura:
-- El rol 'fcc' equivale a un super-admin y debe tener acceso a todo.
-- La 'secretaria' tiene acceso de lectura global, pero NO al contenido de los mensajes.
-- El 'orientador' y 'rector' solo tienen acceso a datos de su institución.

-- Función auxiliar para obtener el rol del usuario autenticado (desde la tabla administradores)
CREATE OR REPLACE FUNCTION get_user_rol()
RETURNS TEXT AS $$
  SELECT rol FROM administradores WHERE id = auth.uid() AND activo = TRUE;
$$ LANGUAGE sql SECURITY DEFINER;

-- Función auxiliar para obtener la institución del usuario autenticado
CREATE OR REPLACE FUNCTION get_user_institucion()
RETURNS INTEGER AS $$
  SELECT institucion_id FROM administradores WHERE id = auth.uid() AND activo = TRUE;
$$ LANGUAGE sql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- POLÍTICAS PARA ESTUDIANTES
-- -----------------------------------------------------------------------------

-- FCC puede ver y modificar todos
CREATE POLICY "FCC_all_estudiantes" ON estudiantes
    FOR ALL
    USING (get_user_rol() = 'fcc');

-- Secretaría puede VER todos
CREATE POLICY "Secretaria_select_estudiantes" ON estudiantes
    FOR SELECT
    USING (get_user_rol() = 'secretaria');

-- Orientador y Rector pueden ver y modificar estudiantes de sus sedes
CREATE POLICY "Institucion_all_estudiantes" ON estudiantes
    FOR ALL
    USING (
        get_user_rol() IN ('orientador', 'rector') AND 
        sede_id IN (SELECT id FROM sedes WHERE institucion_id = get_user_institucion())
    );

-- -----------------------------------------------------------------------------
-- POLÍTICAS PARA MENSAJES (El chat)
-- -----------------------------------------------------------------------------

-- FCC puede ver todos los mensajes
CREATE POLICY "FCC_select_mensajes" ON mensajes
    FOR SELECT
    USING (get_user_rol() = 'fcc');

-- Orientador y Rector pueden ver mensajes de estudiantes de sus sedes
CREATE POLICY "Institucion_select_mensajes" ON mensajes
    FOR SELECT
    USING (
        get_user_rol() IN ('orientador', 'rector') AND 
        estudiante_id IN (
            SELECT id FROM estudiantes WHERE sede_id IN (
                SELECT id FROM sedes WHERE institucion_id = get_user_institucion()
            )
        )
    );

-- (La Secretaría NO tiene política en la tabla 'mensajes', por lo tanto NO puede verlos)

-- -----------------------------------------------------------------------------
-- POLÍTICAS PARA ALERTAS
-- -----------------------------------------------------------------------------

-- FCC puede ver y resolver alertas de todas las instituciones
CREATE POLICY "FCC_all_alertas" ON alertas
    FOR ALL
    USING (get_user_rol() = 'fcc');

-- Orientador y Rector pueden ver y resolver alertas de su institución
CREATE POLICY "Institucion_all_alertas" ON alertas
    FOR ALL
    USING (
        get_user_rol() IN ('orientador', 'rector') AND 
        sede_id IN (SELECT id FROM sedes WHERE institucion_id = get_user_institucion())
    );

-- Secretaría puede VER todas las alertas
CREATE POLICY "Secretaria_select_alertas" ON alertas
    FOR SELECT
    USING (get_user_rol() = 'secretaria');
