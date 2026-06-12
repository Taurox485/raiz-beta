-- Agregar campo municipio_id a administradores para limitar jurisdicción de la Secretaría
ALTER TABLE administradores ADD COLUMN municipio_id BIGINT REFERENCES municipios(id);

-- Actualizar política de administradores para que la Secretaría solo pueda ver administradores de su jurisdicción?
-- No, la secretaría solo lee estudiantes y alertas. Vamos a ajustar las vistas/políticas si existen.

-- Como las políticas de RLS dependen de esto, necesitamos redefinir las políticas para Secretaría.
-- La tabla `mensajes` ya está bloqueada para secretaria.
-- La tabla `estudiantes` tiene RLS (si se aplica 008). 
-- Actualmente 008 le daba a secretaria "Lectura global en estudiantes".
-- Si la secretaría tiene un municipio_id, debe ser de ese municipio.
-- Modificamos la política de lectura de estudiantes:

DROP POLICY IF EXISTS "Lectura de estudiantes basada en rol y jurisdiccion" ON estudiantes;

CREATE POLICY "Lectura de estudiantes basada en rol y jurisdiccion"
ON estudiantes FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM administradores a
        WHERE a.id = auth.uid()
          AND (
              a.rol = 'fcc' 
              OR (
                  a.rol = 'secretaria' 
                  AND (
                      a.municipio_id IS NULL 
                      OR a.municipio_id = (SELECT municipio_id FROM instituciones i JOIN sedes s ON s.institucion_id = i.id WHERE s.id = estudiantes.sede_id)
                  )
              )
              OR (
                  a.rol IN ('rector', 'orientador')
                  AND a.institucion_id = (SELECT institucion_id FROM sedes WHERE id = estudiantes.sede_id)
              )
          )
    )
);

DROP POLICY IF EXISTS "Lectura de alertas basada en rol y jurisdiccion" ON alertas;

CREATE POLICY "Lectura de alertas basada en rol y jurisdiccion"
ON alertas FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM administradores a
        WHERE a.id = auth.uid()
          AND (
              a.rol = 'fcc' 
              OR (
                  a.rol = 'secretaria' 
                  AND (
                      a.municipio_id IS NULL 
                      OR a.municipio_id = (
                          SELECT i.municipio_id FROM instituciones i 
                          JOIN sedes s ON s.institucion_id = i.id 
                          JOIN estudiantes e ON e.sede_id = s.id 
                          WHERE e.estudiante_id = alertas.estudiante_id
                      )
                  )
              )
              OR (
                  a.rol IN ('rector', 'orientador')
                  AND a.institucion_id = (
                      SELECT s.institucion_id FROM sedes s 
                      JOIN estudiantes e ON e.sede_id = s.id 
                      WHERE e.estudiante_id = alertas.estudiante_id
                  )
              )
          )
    )
);
