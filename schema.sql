-- ============================================================
-- rAÍz — Schema de base de datos v001
-- Target: Supabase (PostgreSQL 15+)
-- SQLite fallback: gestionado en database.py — no ejecutar aquí
--
-- Jerarquía: municipio → institución → sede → estudiante
-- ============================================================


-- ─── 1. MUNICIPIOS ────────────────────────────────────────
-- Tabla seed de solo lectura. Los códigos forman el prefijo
-- del estudiante_id (ej. ALC-9-2026-0042).

CREATE TABLE IF NOT EXISTS municipios (
    id      SERIAL       PRIMARY KEY,
    codigo  VARCHAR(5)   UNIQUE NOT NULL,
    nombre  VARCHAR(100) NOT NULL
);


-- ─── 2. INSTITUCIONES ─────────────────────────────────────
-- orientador_email es nullable: sedes sin email configurado
-- simplemente no reciben alertas, pero el sistema funciona igual.

CREATE TABLE IF NOT EXISTS instituciones (
    id                  SERIAL       PRIMARY KEY,
    municipio_id        INTEGER      NOT NULL REFERENCES municipios(id),
    nombre              VARCHAR(200) NOT NULL,
    orientador_nombre   VARCHAR(200),
    orientador_email    VARCHAR(200),
    orientador_telefono VARCHAR(20)
);


-- ─── 3. SEDES ─────────────────────────────────────────────
-- Una institución puede tener varias sedes (rural/urbana).
-- El estudiante se vincula a su sede específica.

CREATE TABLE IF NOT EXISTS sedes (
    id                SERIAL       PRIMARY KEY,
    institucion_id    INTEGER      NOT NULL REFERENCES instituciones(id),
    nombre            VARCHAR(200) NOT NULL,
    es_sede_principal BOOLEAN      DEFAULT FALSE
);


-- ─── 4. ADMINS_SEDE ───────────────────────────────────────
-- Schema listo para fase futura del dashboard del orientador/rector.
-- No construir vista /admin aún.

CREATE TABLE IF NOT EXISTS admins_sede (
    id             SERIAL      PRIMARY KEY,
    sede_id        INTEGER     NOT NULL REFERENCES sedes(id),
    email_rector   VARCHAR(200),
    codigo_admin   VARCHAR(20) UNIQUE NOT NULL,
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
);


-- ─── 5. ESTUDIANTES ───────────────────────────────────────
-- Datos personales mínimos (protección de menores):
--   nombre, apellido, grado, email, sede_id.
-- El email cumple doble función: recuperación de ID + envío de reporte PDF.
-- La constraint habeas_data_consistente garantiza que si se marca
-- consentimiento, se registra también la fecha exacta (Ley 1581/2012).

CREATE TABLE IF NOT EXISTS estudiantes (
    id                         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id              VARCHAR(25) UNIQUE NOT NULL,
    nombre                     VARCHAR(100) NOT NULL,
    apellido                   VARCHAR(100) NOT NULL,
    grado                      INTEGER      NOT NULL CHECK (grado BETWEEN 9 AND 11),
    email                      VARCHAR(200) UNIQUE NOT NULL,
    sede_id                    INTEGER      NOT NULL REFERENCES sedes(id),
    consentimiento_habeas_data BOOLEAN      DEFAULT FALSE,
    fecha_consentimiento       TIMESTAMPTZ,
    fecha_registro             TIMESTAMPTZ  DEFAULT NOW(),
    sesion_actual              INTEGER      DEFAULT 1 CHECK (sesion_actual BETWEEN 1 AND 4),
    momento_actual             INTEGER      DEFAULT 1 CHECK (momento_actual BETWEEN 1 AND 5),
    perfil_riesgo              VARCHAR(20)  DEFAULT 'sin_evaluar'
                                   CHECK (perfil_riesgo IN ('sin_evaluar', 'bajo', 'medio', 'alto')),
    mentoria_completada        BOOLEAN      DEFAULT FALSE,

    CONSTRAINT habeas_data_consistente CHECK (
        (consentimiento_habeas_data = FALSE AND fecha_consentimiento IS NULL)
        OR
        (consentimiento_habeas_data = TRUE  AND fecha_consentimiento IS NOT NULL)
    )
);


-- ─── 6. MENSAJES ──────────────────────────────────────────
-- contenido se guarda CON etiquetas internas ([RIESGO_ALTO], etc.)
-- sin pasar por limpiar_etiquetas(). Al recargar la sesión de Gemini,
-- el SDK necesita el historial completo para mantener coherencia del modelo.
-- limpiar_etiquetas() solo se aplica en pantalla (app.py).

CREATE TABLE IF NOT EXISTS mensajes (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id UUID        NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    sesion_numero INTEGER     NOT NULL CHECK (sesion_numero BETWEEN 1 AND 4),
    rol           VARCHAR(10) NOT NULL CHECK (rol IN ('user', 'model')),
    contenido     TEXT        NOT NULL,
    timestamp     TIMESTAMPTZ DEFAULT NOW(),
    tiene_alerta  BOOLEAN     DEFAULT FALSE
);


-- ─── 7. ALERTAS ───────────────────────────────────────────
-- Reemplaza el print() actual de app.py.
-- sede_id desnormalizado aquí para lookup directo del email del orientador
-- sin tener que joinear a través del estudiante.

CREATE TABLE IF NOT EXISTS alertas (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id    UUID        NOT NULL REFERENCES estudiantes(id),
    sede_id          INTEGER     NOT NULL REFERENCES sedes(id),
    tipo             VARCHAR(40) NOT NULL
                         CHECK (tipo IN ('orientador_requerida', 'psicologica_critica')),
    estado           VARCHAR(20) DEFAULT 'pendiente'
                         CHECK (estado IN ('pendiente', 'vista', 'resuelta')),
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    nota_resolucion  TEXT
);


-- ─── ÍNDICES ──────────────────────────────────────────────
-- Los campos UNIQUE ya tienen índice implícito (estudiante_id, email).
-- Estos cubren los patrones de acceso más frecuentes.

CREATE INDEX IF NOT EXISTS idx_mensajes_estudiante
    ON mensajes (estudiante_id);

CREATE INDEX IF NOT EXISTS idx_mensajes_sesion
    ON mensajes (estudiante_id, sesion_numero);

CREATE INDEX IF NOT EXISTS idx_alertas_sede_pendiente
    ON alertas (sede_id) WHERE estado = 'pendiente';

CREATE INDEX IF NOT EXISTS idx_alertas_estudiante
    ON alertas (estudiante_id);

CREATE INDEX IF NOT EXISTS idx_estudiantes_sede
    ON estudiantes (sede_id);


-- ─── FUNCIÓN: generar_estudiante_id() ─────────────────────
-- Solo PostgreSQL/Supabase. El equivalente para SQLite vive en auth.py.
-- Calcula el correlativo contando estudiantes del mismo municipio + grado + año.
-- Se llama desde auth.py en el momento del INSERT de un nuevo estudiante.

CREATE OR REPLACE FUNCTION generar_estudiante_id(
    p_sede_id INTEGER,
    p_grado   INTEGER
) RETURNS VARCHAR AS $$
DECLARE
    v_codigo       VARCHAR(5);
    v_municipio_id INTEGER;
    v_year         INTEGER;
    v_correlativo  INTEGER;
BEGIN
    SELECT m.codigo, m.id
    INTO   v_codigo, v_municipio_id
    FROM   sedes s
    JOIN   instituciones i ON s.institucion_id = i.id
    JOIN   municipios    m ON i.municipio_id   = m.id
    WHERE  s.id = p_sede_id;

    v_year := EXTRACT(YEAR FROM NOW())::INTEGER;

    SELECT COUNT(*) + 1
    INTO   v_correlativo
    FROM   estudiantes  e
    JOIN   sedes        s ON e.sede_id          = s.id
    JOIN   instituciones i ON s.institucion_id  = i.id
    WHERE  i.municipio_id = v_municipio_id
      AND  e.grado        = p_grado
      AND  EXTRACT(YEAR FROM e.fecha_registro)::INTEGER = v_year;

    RETURN v_codigo
           || '-' || p_grado::TEXT
           || '-' || v_year::TEXT
           || '-' || LPAD(v_correlativo::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;


-- ─── DATOS SEED ───────────────────────────────────────────
-- Municipios del piloto Valle del Cauca.
-- Instituciones y sedes reales del piloto (orientador_email se agrega luego).

INSERT INTO municipios (codigo, nombre) VALUES
    ('ALC', 'Alcalá'),        ('ANS', 'Ansermanuevo'), ('CAN', 'Candelaria'),
    ('CER', 'Cerrito'),       ('AGU', 'El Águila'),    ('CAI', 'El Cairo'),
    ('GUA', 'Guacarí'),       ('OBA', 'Obando'),       ('SPE', 'San Pedro'),
    ('TOR', 'Toro'),          ('VIJ', 'Vijes')
ON CONFLICT (codigo) DO NOTHING;

-- Patrón usado en toda esta sección:
--   inst  → INSERT INTO instituciones ... SELECT id FROM municipios WHERE codigo = '...'
--   sede  → INSERT INTO sedes ... SELECT i.id FROM instituciones i JOIN municipios m ...
--           WHERE i.nombre = '...' AND m.codigo = '...'   (evita ambigüedad entre IEs
--           homónimas en distintos municipios, p.ej. "IE San José" en ALC y OBA)

-- ── Alcalá ────────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Arturo Gómez Jaramillo' FROM municipios WHERE codigo = 'ALC';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',            TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Arturo Gómez Jaramillo' AND m.codigo='ALC';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'José Ignacio Rengifo', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Arturo Gómez Jaramillo' AND m.codigo='ALC';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE San José' FROM municipios WHERE codigo = 'ALC';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE San José' AND m.codigo='ALC';

-- ── Ansermanuevo ──────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE El Placer'                  FROM municipios WHERE codigo = 'ANS';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE El Placer' AND m.codigo='ANS';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Jorge Isaacs'               FROM municipios WHERE codigo = 'ANS';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Jorge Isaacs' AND m.codigo='ANS';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Santa Ana De Los Caballeros' FROM municipios WHERE codigo = 'ANS';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Santa Ana De Los Caballeros' AND m.codigo='ANS';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Santa Inés'                 FROM municipios WHERE codigo = 'ANS';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Santa Inés' AND m.codigo='ANS';

-- ── Candelaria ────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'Nuestra Señora De La Candelaria' FROM municipios WHERE codigo = 'CAN';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='Nuestra Señora De La Candelaria' AND m.codigo='CAN';

-- ── Cerrito ───────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Jorge Isaacs - El Placer' FROM municipios WHERE codigo = 'CER';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Jorge Isaacs - El Placer' AND m.codigo='CER';

-- ── El Águila ─────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE El Águila' FROM municipios WHERE codigo = 'AGU';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE El Águila' AND m.codigo='AGU';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Justiniano Echavarría' FROM municipios WHERE codigo = 'AGU';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',        TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Justiniano Echavarría' AND m.codigo='AGU';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Sede Santa Isabel', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Justiniano Echavarría' AND m.codigo='AGU';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Santa Marta' FROM municipios WHERE codigo = 'AGU';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',     TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Santa Marta' AND m.codigo='AGU';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Dionisio Cortez', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Santa Marta' AND m.codigo='AGU';

-- ── El Cairo ──────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Gilberto Alzate Avendaño' FROM municipios WHERE codigo = 'CAI';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Gilberto Alzate Avendaño' AND m.codigo='CAI';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Alban',     FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Gilberto Alzate Avendaño' AND m.codigo='CAI';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE La Presentación' FROM municipios WHERE codigo = 'CAI';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE La Presentación' AND m.codigo='CAI';

-- ── Guacarí ───────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Normal Superior Miguel De Cervantes Saavedra' FROM municipios WHERE codigo = 'GUA';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Normal Superior Miguel De Cervantes Saavedra' AND m.codigo='GUA';

-- ── Obando ────────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE María Analía Ortiz Hormaza' FROM municipios WHERE codigo = 'OBA';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE María Analía Ortiz Hormaza' AND m.codigo='OBA';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Policarpa Salavarrieta' FROM municipios WHERE codigo = 'OBA';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Policarpa Salavarrieta' AND m.codigo='OBA';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE San José' FROM municipios WHERE codigo = 'OBA';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE San José' AND m.codigo='OBA';

-- ── San Pedro ─────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE José Antonio Aguilera' FROM municipios WHERE codigo = 'SPE';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE José Antonio Aguilera' AND m.codigo='SPE';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Julio Caicedo Téllez' FROM municipios WHERE codigo = 'SPE';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Julio Caicedo Téllez' AND m.codigo='SPE';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Miguel Antonio Caro' FROM municipios WHERE codigo = 'SPE';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',       TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Miguel Antonio Caro' AND m.codigo='SPE';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Gabriela Mistral', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Miguel Antonio Caro' AND m.codigo='SPE';

-- ── Toro ──────────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Fray José Joaquín Escobar' FROM municipios WHERE codigo = 'TOR';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Fray José Joaquín Escobar' AND m.codigo='TOR';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Nuestra Señora De La Consolación' FROM municipios WHERE codigo = 'TOR';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Nuestra Señora De La Consolación' AND m.codigo='TOR';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Técnica Agropecuaria Toro' FROM municipios WHERE codigo = 'TOR';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',                TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Técnica Agropecuaria Toro' AND m.codigo='TOR';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Nuestra Señora de Fátima', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Técnica Agropecuaria Toro' AND m.codigo='TOR';

-- ── Vijes ─────────────────────────────────────────────────
INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Antonio José De Sucre' FROM municipios WHERE codigo = 'VIJ';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',             TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Antonio José De Sucre' AND m.codigo='VIJ';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Sede Atanasio Girardot', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Antonio José De Sucre' AND m.codigo='VIJ';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE Jorge Robledo' FROM municipios WHERE codigo = 'VIJ';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal', TRUE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE Jorge Robledo' AND m.codigo='VIJ';

INSERT INTO instituciones (municipio_id, nombre) SELECT id, 'IE 20 De Julio' FROM municipios WHERE codigo = 'VIJ';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Principal',           TRUE  FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE 20 De Julio' AND m.codigo='VIJ';
INSERT INTO sedes (institucion_id, nombre, es_sede_principal) SELECT i.id, 'Sede Manuela Beltrán', FALSE FROM instituciones i JOIN municipios m ON i.municipio_id=m.id WHERE i.nombre='IE 20 De Julio' AND m.codigo='VIJ';