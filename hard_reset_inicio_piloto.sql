-- ==============================================================================
-- SCRIPT DE HARD RESET PARA INICIO DE PILOTO
-- ==============================================================================
-- Este script borra todos los datos de prueba (estudiantes, chats, alertas)
-- respetando la estructura base de municipios, instituciones y sedes.
-- 
-- ADVERTENCIA: Esta acción es irreversible. Ejecutar solo en el SQL Editor 
-- de Supabase justo antes de iniciar el piloto real.
-- ==============================================================================

-- 1. Vaciar datos de interacción (El orden importa por las llaves foráneas)
DELETE FROM whatsapp_mensajes;
DELETE FROM envios_ficha;
DELETE FROM mensajes;
DELETE FROM alertas;

-- 2. Vaciar tabla de estudiantes
DELETE FROM estudiantes;

-- 3. (Opcional) Vaciar TODOS los administradores EXCEPTO a ti mismo
-- Reemplaza 'tu-correo@ejemplo.com' por tu correo real de FCC antes de ejecutarlo.
-- Esto borra a los demás administradores de la tabla pública.
-- 
-- IMPORTANTE: Para que el borrado de administradores sea total, 
-- debes ir a Supabase -> Authentication -> Users y eliminar allí 
-- a los demás usuarios a mano, ya que SQL no tiene permisos para 
-- borrar de auth.users directamente sin funciones avanzadas.

-- DELETE FROM administradores WHERE email != 'tu-correo@ejemplo.com';
