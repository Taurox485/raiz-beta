-- Migración 007: Permitir mensaje_numero = 0 para Bienvenida Inmediata (Mensaje Cero)

-- Para PostgreSQL (Supabase):
-- Necesitamos identificar el nombre del constraint. Generalmente es 'whatsapp_mensajes_mensaje_numero_check'
DO $$
BEGIN
    ALTER TABLE whatsapp_mensajes DROP CONSTRAINT IF EXISTS whatsapp_mensajes_mensaje_numero_check;
    ALTER TABLE whatsapp_mensajes ADD CONSTRAINT whatsapp_mensajes_mensaje_numero_check CHECK (mensaje_numero BETWEEN 0 AND 5);
END $$;

-- Para SQLite:
-- SQLite no permite ALTER TABLE DROP CONSTRAINT. Se debe recrear la tabla.
-- Este script es ilustrativo para SQLite, pero database.py ya maneja la creación inicial.
/*
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE whatsapp_mensajes_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id   INTEGER NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    mensaje_numero  INTEGER NOT NULL CHECK (mensaje_numero BETWEEN 0 AND 5),
    estado          TEXT NOT NULL CHECK (estado IN ('pendiente', 'enviado', 'fallido')),
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO whatsapp_mensajes_new SELECT * FROM whatsapp_mensajes;
DROP TABLE whatsapp_mensajes;
ALTER TABLE whatsapp_mensajes_new RENAME TO whatsapp_mensajes;
COMMIT;
PRAGMA foreign_keys=ON;
*/
