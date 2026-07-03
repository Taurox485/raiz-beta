-- ============================================================
-- Migración 011: Reset datos de prueba + Datos reales piloto
-- Ejecutado en Supabase SQL Editor — Julio 2026
-- Limpia datos de prueba e inserta instituciones y sedes reales
-- del piloto rAÍz Valle del Cauca 2026
-- ============================================================

-- ─── PASO 1: LIMPIEZA ──────────────────────────────────────
DROP POLICY IF EXISTS "Admins_select_instituciones" ON instituciones;
DROP POLICY IF EXISTS "Admins_select_sedes" ON sedes;

DELETE FROM whatsapp_mensajes;
DELETE FROM envios_ficha;
DELETE FROM alertas;
DELETE FROM mensajes;
DELETE FROM estudiantes;
DELETE FROM administradores WHERE rol IN ('orientador', 'rector');
DELETE FROM sedes;
DELETE FROM instituciones;

-- ─── PASO 2: INSTITUCIONES Y SEDES REALES DEL PILOTO ───────

-- Ansermanuevo
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'El Placer', 'Adriana Libreros', 'nanalc9791@gmail.com', '3155762277'
FROM municipios WHERE codigo = 'ANS';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Concentración Desarrollo Rural', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'El Placer' AND m.codigo = 'ANS';

-- Candelaria
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'Nuestra Señora de la Candelaria', 'Viviana Toro', 'coorvivianatoro@iensecan.edu.co', '3168284873'
FROM municipios WHERE codigo = 'CAN';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Antonio Nariño', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'Nuestra Señora de la Candelaria' AND m.codigo = 'CAN';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Sagrada Familia', FALSE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'Nuestra Señora de la Candelaria' AND m.codigo = 'CAN';

-- El Cerrito
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'Jorge Isaacs', 'Paula Quintero', 'paulaquintero@jorgeplacer.edu.co', '3164459397'
FROM municipios WHERE codigo = 'CER';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'El Placer', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'Jorge Isaacs' AND m.codigo = 'CER';

-- Guacarí
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'Normal Superior Miguel de Cervantes Saavedra', 'José Adolfo Acevedo', 'alinekerace@gmail.com', '3164226740'
FROM municipios WHERE codigo = 'GUA';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Central', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'Normal Superior Miguel de Cervantes Saavedra' AND m.codigo = 'GUA';

-- Obando
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'San José', 'Carlos Andrés Cruz', 'orientacionescolarsanjose1@gmail.com', '3137057056'
FROM municipios WHERE codigo = 'OBA';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Principal', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'San José' AND m.codigo = 'OBA';

-- San Pedro — José Antonio Aguilera
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'José Antonio Aguilera', 'Ángela Rodriguez', 'docenteorientadora2023@gmail.com', '3185893844'
FROM municipios WHERE codigo = 'SPE';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Principal', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'José Antonio Aguilera' AND m.codigo = 'SPE';

-- San Pedro — Miguel Antonio Caro
INSERT INTO instituciones (municipio_id, nombre, orientador_nombre, orientador_email, orientador_telefono)
SELECT id, 'Miguel Antonio Caro', 'Edgar Bastidas', 'edgarpsiedu@gmail.com', '3043955156'
FROM municipios WHERE codigo = 'SPE';

INSERT INTO sedes (institucion_id, nombre, es_sede_principal)
SELECT i.id, 'Presidente', TRUE
FROM instituciones i JOIN municipios m ON i.municipio_id = m.id
WHERE i.nombre = 'Miguel Antonio Caro' AND m.codigo = 'SPE';

-- ─── PASO 3: RESTAURAR POLÍTICAS RLS ───────────────────────
CREATE POLICY "Admins_select_instituciones" ON instituciones
    FOR SELECT
    USING (get_user_rol() IS NOT NULL);

CREATE POLICY "Admins_select_sedes" ON sedes
    FOR SELECT
    USING (
        get_user_rol() IN ('fcc', 'secretaria')
        OR (
            get_user_rol() IN ('orientador', 'rector')
            AND institucion_id = get_user_institucion()
        )
    );
