"""
database.py — Capa de acceso a datos para rAÍz

Detecta el backend automáticamente:
  - Supabase  si SUPABASE_URL está en .streamlit/secrets.toml
  - SQLite    (raiz_local.db) como fallback offline

Ambos backends exponen la misma API pública, por lo que app.py
y auth.py son completamente agnósticos al backend activo.
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import streamlit as st


# ── Detección de backend ───────────────────────────────────────────────────────

def _use_supabase() -> bool:
    try:
        return bool(st.secrets.get("SUPABASE_URL", ""))
    except Exception:
        return False


# ── Cliente Supabase (singleton cacheado) ──────────────────────────────────────

@st.cache_resource
def _get_supabase():
    from supabase import create_client
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )


# ── SQLite: DDL ────────────────────────────────────────────────────────────────
# Esquema equivalente al de schema.sql, adaptado a tipos nativos de SQLite.
# Los tipos TEXT/INTEGER/REAL son los únicos que SQLite reconoce internamente.

SQLITE_PATH = "raiz_local.db"

_DDL = """
CREATE TABLE IF NOT EXISTS municipios (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT    UNIQUE NOT NULL,
    nombre TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS instituciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    municipio_id        INTEGER NOT NULL REFERENCES municipios(id),
    nombre              TEXT    NOT NULL,
    orientador_nombre   TEXT,
    orientador_email    TEXT,
    orientador_telefono TEXT
);
CREATE TABLE IF NOT EXISTS sedes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    institucion_id    INTEGER NOT NULL REFERENCES instituciones(id),
    nombre            TEXT    NOT NULL,
    es_sede_principal INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS admins_sede (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sede_id        INTEGER NOT NULL REFERENCES sedes(id),
    email_rector   TEXT,
    codigo_admin   TEXT UNIQUE NOT NULL,
    fecha_registro TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS estudiantes (
    id                         TEXT    PRIMARY KEY,
    estudiante_id              TEXT    UNIQUE NOT NULL,
    nombre                     TEXT    NOT NULL,
    apellido                   TEXT    NOT NULL,
    grado                      INTEGER NOT NULL,
    email                      TEXT    UNIQUE NOT NULL,
    sede_id                    INTEGER NOT NULL REFERENCES sedes(id),
    consentimiento_habeas_data INTEGER DEFAULT 0,
    fecha_consentimiento       TEXT,
    fecha_registro             TEXT    DEFAULT (datetime('now')),
    sesion_actual              INTEGER DEFAULT 1,
    momento_actual             INTEGER DEFAULT 1,
    perfil_riesgo              TEXT    DEFAULT 'sin_evaluar',
    mentoria_completada        INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mensajes (
    id            TEXT    PRIMARY KEY,
    estudiante_id TEXT    NOT NULL REFERENCES estudiantes(id),
    sesion_numero INTEGER NOT NULL,
    rol           TEXT    NOT NULL,
    contenido     TEXT    NOT NULL,
    timestamp     TEXT    DEFAULT (datetime('now')),
    tiene_alerta  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alertas (
    id               TEXT    PRIMARY KEY,
    estudiante_id    TEXT    NOT NULL REFERENCES estudiantes(id),
    sede_id          INTEGER NOT NULL REFERENCES sedes(id),
    tipo             TEXT    NOT NULL,
    estado           TEXT    DEFAULT 'pendiente',
    timestamp        TEXT    DEFAULT (datetime('now')),
    nota_resolucion  TEXT
);
"""

# ── SQLite: datos seed ─────────────────────────────────────────────────────────
# Idénticos a los de schema.sql. Instituciones y sedes reales del piloto.

_SEED_MUNICIPIOS = [
    ("ALC", "Alcalá"),        ("ANS", "Ansermanuevo"), ("CAN", "Candelaria"),
    ("CER", "Cerrito"),       ("CAI", "El Cairo"),     ("AGU", "El Águila"),
    ("GUA", "Guacarí"),       ("OBA", "Obando"),       ("SPE", "San Pedro"),
    ("TOR", "Toro"),          ("VIJ", "Vijes"),
]

_SEED_INSTITUCIONES = [
    # Alcalá
    ("ALC", "IE Arturo Gómez Jaramillo", [
        ("Principal",            True),
        ("José Ignacio Rengifo", False),
    ]),
    ("ALC", "IE San José", [("Principal", True)]),
    # Ansermanuevo
    ("ANS", "IE El Placer",                    [("Principal", True)]),
    ("ANS", "IE Jorge Isaacs",                 [("Principal", True)]),
    ("ANS", "IE Santa Ana De Los Caballeros",  [("Principal", True)]),
    ("ANS", "IE Santa Inés",                   [("Principal", True)]),
    # Candelaria
    ("CAN", "Nuestra Señora De La Candelaria", [("Principal", True)]),
    # Cerrito
    ("CER", "IE Jorge Isaacs - El Placer",     [("Principal", True)]),
    # El Águila
    ("AGU", "IE El Águila",                    [("Principal", True)]),
    ("AGU", "IE Justiniano Echavarría", [
        ("Principal",        True),
        ("Sede Santa Isabel", False),
    ]),
    ("AGU", "IE Santa Marta", [
        ("Principal",      True),
        ("Dionisio Cortez", False),
    ]),
    # El Cairo
    ("CAI", "IE Gilberto Alzate Avendaño", [
        ("Principal", True),
        ("Alban",     False),
    ]),
    ("CAI", "IE La Presentación",              [("Principal", True)]),
    # Guacarí
    ("GUA", "IE Normal Superior Miguel De Cervantes Saavedra", [("Principal", True)]),
    # Obando
    ("OBA", "IE María Analía Ortiz Hormaza",   [("Principal", True)]),
    ("OBA", "IE Policarpa Salavarrieta",        [("Principal", True)]),
    ("OBA", "IE San José",                     [("Principal", True)]),
    # San Pedro
    ("SPE", "IE José Antonio Aguilera",        [("Principal", True)]),
    ("SPE", "IE Julio Caicedo Téllez",         [("Principal", True)]),
    ("SPE", "IE Miguel Antonio Caro", [
        ("Principal",       True),
        ("Gabriela Mistral", False),
    ]),
    # Toro
    ("TOR", "IE Fray José Joaquín Escobar",        [("Principal", True)]),
    ("TOR", "IE Nuestra Señora De La Consolación", [("Principal", True)]),
    ("TOR", "IE Técnica Agropecuaria Toro", [
        ("Principal",                True),
        ("Nuestra Señora de Fátima", False),
    ]),
    # Vijes
    ("VIJ", "IE Antonio José De Sucre", [
        ("Principal",              True),
        ("Sede Atanasio Girardot", False),
    ]),
    ("VIJ", "IE Jorge Robledo",                [("Principal", True)]),
    ("VIJ", "IE 20 De Julio", [
        ("Principal",           True),
        ("Sede Manuela Beltrán", False),
    ]),
]

_sqlite_ready = False


# ── SQLite: helpers internos ───────────────────────────────────────────────────

@contextmanager
def _conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_sqlite():
    global _sqlite_ready
    if _sqlite_ready:
        return
    with _conn() as conn:
        conn.executescript(_DDL)
        if conn.execute("SELECT COUNT(*) FROM municipios").fetchone()[0] == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO municipios (codigo, nombre) VALUES (?, ?)",
                _SEED_MUNICIPIOS,
            )
            for mun_codigo, inst_nombre, sedes in _SEED_INSTITUCIONES:
                mun_id = conn.execute(
                    "SELECT id FROM municipios WHERE codigo = ?", (mun_codigo,)
                ).fetchone()[0]
                cur = conn.execute(
                    "INSERT INTO instituciones (municipio_id, nombre) VALUES (?, ?)",
                    (mun_id, inst_nombre),
                )
                conn.executemany(
                    "INSERT INTO sedes (institucion_id, nombre, es_sede_principal) VALUES (?, ?, ?)",
                    [(cur.lastrowid, nombre, int(principal)) for nombre, principal in sedes],
                )
    _sqlite_ready = True


def _generar_id_sqlite(conn, sede_id: int, grado: int) -> str:
    """Equivalente Python de la función generar_estudiante_id() de PostgreSQL."""
    year = datetime.now().year
    row = conn.execute(
        """
        SELECT m.codigo, m.id AS municipio_id
        FROM   sedes        s
        JOIN   instituciones i ON s.institucion_id = i.id
        JOIN   municipios    m ON i.municipio_id   = m.id
        WHERE  s.id = ?
        """,
        (sede_id,),
    ).fetchone()

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM   estudiantes   e
        JOIN   sedes         s  ON e.sede_id         = s.id
        JOIN   instituciones i  ON s.institucion_id  = i.id
        WHERE  i.municipio_id = ?
          AND  e.grado        = ?
          AND  strftime('%Y', e.fecha_registro) = ?
        """,
        (row["municipio_id"], grado, str(year)),
    ).fetchone()[0]

    return f"{row['codigo']}-{grado}-{year}-{count + 1:04d}"


# ── API pública: dropdowns para el formulario de registro ─────────────────────

def get_municipios() -> list[dict]:
    if _use_supabase():
        r = _get_supabase().table("municipios").select("id, codigo, nombre").order("nombre").execute()
        return r.data
    _ensure_sqlite()
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, codigo, nombre FROM municipios ORDER BY nombre"
        ).fetchall()]


def get_instituciones(municipio_id: int) -> list[dict]:
    if _use_supabase():
        r = (
            _get_supabase().table("instituciones")
            .select("id, nombre")
            .eq("municipio_id", municipio_id)
            .order("nombre")
            .execute()
        )
        return r.data
    _ensure_sqlite()
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, nombre FROM instituciones WHERE municipio_id = ? ORDER BY nombre",
            (municipio_id,),
        ).fetchall()]


def get_sedes(institucion_id: int) -> list[dict]:
    if _use_supabase():
        r = (
            _get_supabase().table("sedes")
            .select("id, nombre, es_sede_principal")
            .eq("institucion_id", institucion_id)
            .order("es_sede_principal", desc=True)
            .execute()
        )
        return r.data
    _ensure_sqlite()
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            """
            SELECT id, nombre, es_sede_principal
            FROM   sedes
            WHERE  institucion_id = ?
            ORDER  BY es_sede_principal DESC, nombre
            """,
            (institucion_id,),
        ).fetchall()]


# ── API pública: ciclo de vida del estudiante ──────────────────────────────────

def crear_estudiante(
    nombre: str,
    apellido: str,
    grado: int,
    email: str,
    sede_id: int,
) -> Optional[str]:
    """
    Crea un nuevo estudiante y retorna su estudiante_id generado (ej. 'ALC-9-2026-0042').
    Retorna None si el email ya está registrado.
    El consentimiento habeas data se registra por separado con set_consentimiento().
    """
    email = email.lower().strip()
    new_uuid = str(uuid.uuid4())

    if _use_supabase():
        sb = _get_supabase()
        est_id = sb.rpc(
            "generar_estudiante_id", {"p_sede_id": sede_id, "p_grado": grado}
        ).execute().data
        try:
            sb.table("estudiantes").insert({
                "id":               new_uuid,
                "estudiante_id":    est_id,
                "nombre":           nombre,
                "apellido":         apellido,
                "grado":            grado,
                "email":            email,
                "sede_id":          sede_id,
            }).execute()
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                return None
            raise
        return est_id

    _ensure_sqlite()
    with _conn() as conn:
        if conn.execute(
            "SELECT id FROM estudiantes WHERE email = ?", (email,)
        ).fetchone():
            return None
        est_id = _generar_id_sqlite(conn, sede_id, grado)
        conn.execute(
            """
            INSERT INTO estudiantes
                (id, estudiante_id, nombre, apellido, grado, email, sede_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_uuid, est_id, nombre, apellido, grado, email, sede_id),
        )
    return est_id


def login_estudiante(estudiante_id: str) -> Optional[dict]:
    """Retorna el dict completo del estudiante o None si el ID no existe."""
    eid = estudiante_id.strip().upper()

    if _use_supabase():
        r = (
            _get_supabase().table("estudiantes")
            .select("*")
            .eq("estudiante_id", eid)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    _ensure_sqlite()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM estudiantes WHERE estudiante_id = ?", (eid,)
        ).fetchone()
        return dict(row) if row else None


def get_estudiante_por_email(email: str) -> Optional[dict]:
    """
    Flujo 'Olvidé mi ID': busca por email y retorna estudiante_id + nombre.
    Retorna None si el email no está registrado.
    """
    email = email.lower().strip()

    if _use_supabase():
        r = (
            _get_supabase().table("estudiantes")
            .select("estudiante_id, nombre, email")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    _ensure_sqlite()
    with _conn() as conn:
        row = conn.execute(
            "SELECT estudiante_id, nombre, email FROM estudiantes WHERE email = ?",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def set_consentimiento(estudiante_uuid: str) -> None:
    """
    Graba consentimiento habeas data con timestamp preciso (Ley 1581/2012).
    Debe llamarse justo después de que el estudiante marca el checkbox.
    """
    now = datetime.now(timezone.utc).isoformat()

    if _use_supabase():
        _get_supabase().table("estudiantes").update({
            "consentimiento_habeas_data": True,
            "fecha_consentimiento":       now,
        }).eq("id", estudiante_uuid).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE estudiantes
            SET    consentimiento_habeas_data = 1,
                   fecha_consentimiento       = ?
            WHERE  id = ?
            """,
            (now, estudiante_uuid),
        )


def update_progreso(estudiante_uuid: str, sesion: int, momento: int) -> None:
    """Actualiza el puntero de avance pedagógico para permitir retomar la sesión."""
    if _use_supabase():
        _get_supabase().table("estudiantes").update({
            "sesion_actual":  sesion,
            "momento_actual": momento,
        }).eq("id", estudiante_uuid).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            "UPDATE estudiantes SET sesion_actual = ?, momento_actual = ? WHERE id = ?",
            (sesion, momento, estudiante_uuid),
        )


def update_perfil_riesgo(estudiante_uuid: str, perfil: str) -> None:
    """perfil: 'bajo' | 'medio' | 'alto' — inferido del motor de riesgo del prompt."""
    if _use_supabase():
        _get_supabase().table("estudiantes").update(
            {"perfil_riesgo": perfil}
        ).eq("id", estudiante_uuid).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            "UPDATE estudiantes SET perfil_riesgo = ? WHERE id = ?",
            (perfil, estudiante_uuid),
        )


def set_mentoria_completada(estudiante_uuid: str) -> None:
    """Marca la mentoría como completada cuando el modelo emite [FIN_CONSEJERIA]."""
    if _use_supabase():
        _get_supabase().table("estudiantes").update(
            {"mentoria_completada": True}
        ).eq("id", estudiante_uuid).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            "UPDATE estudiantes SET mentoria_completada = 1 WHERE id = ?",
            (estudiante_uuid,),
        )


# ── API pública: historial de chat ─────────────────────────────────────────────

def guardar_mensaje(
    estudiante_uuid: str,
    sesion: int,
    rol: str,
    contenido: str,
    tiene_alerta: bool = False,
) -> None:
    """
    Guarda el mensaje con su contenido RAW (con etiquetas internas como [RIESGO_ALTO]).
    No llamar a limpiar_etiquetas() aquí — el SDK de Gemini necesita el historial
    completo con etiquetas para reconstruir coherentemente la sesión al reingresar.
    """
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    if _use_supabase():
        _get_supabase().table("mensajes").insert({
            "id":            msg_id,
            "estudiante_id": estudiante_uuid,
            "sesion_numero": sesion,
            "rol":           rol,
            "contenido":     contenido,
            "timestamp":     now,
            "tiene_alerta":  tiene_alerta,
        }).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO mensajes
                (id, estudiante_id, sesion_numero, rol, contenido, timestamp, tiene_alerta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, estudiante_uuid, sesion, rol, contenido, now, int(tiene_alerta)),
        )


def get_historial(
    estudiante_uuid: str,
    sesion: Optional[int] = None,
) -> list[dict]:
    """
    Retorna los mensajes ordenados por timestamp para reconstruir el historial en Gemini.
    sesion=None  → todas las sesiones (para reconstruir todo el contexto)
    sesion=N     → solo esa sesión
    """
    if _use_supabase():
        sb = _get_supabase()
        q = (
            sb.table("mensajes")
            .select("rol, contenido, sesion_numero, timestamp")
            .eq("estudiante_id", estudiante_uuid)
            .order("timestamp")
        )
        if sesion is not None:
            q = q.eq("sesion_numero", sesion)
        return q.execute().data

    _ensure_sqlite()
    with _conn() as conn:
        if sesion is not None:
            rows = conn.execute(
                """
                SELECT rol, contenido, sesion_numero, timestamp
                FROM   mensajes
                WHERE  estudiante_id = ? AND sesion_numero = ?
                ORDER  BY timestamp
                """,
                (estudiante_uuid, sesion),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT rol, contenido, sesion_numero, timestamp
                FROM   mensajes
                WHERE  estudiante_id = ?
                ORDER  BY timestamp
                """,
                (estudiante_uuid,),
            ).fetchall()
        return [dict(r) for r in rows]


# ── API pública: alertas ───────────────────────────────────────────────────────

def crear_alerta(estudiante_uuid: str, sede_id: int, tipo: str) -> None:
    """
    Reemplaza el print() actual de app.py.
    tipo: 'orientador_requerida' | 'psicologica_critica'
    El orientador consulta alertas pendientes desde su futuro dashboard (Fase 2).
    """
    alert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    if _use_supabase():
        _get_supabase().table("alertas").insert({
            "id":            alert_id,
            "estudiante_id": estudiante_uuid,
            "sede_id":       sede_id,
            "tipo":          tipo,
            "timestamp":     now,
        }).execute()
        return

    _ensure_sqlite()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO alertas (id, estudiante_id, sede_id, tipo, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (alert_id, estudiante_uuid, sede_id, tipo, now),
        )


def get_sede_info(sede_id: int) -> dict:
    """
    Retorna {institucion, municipio, orientador_nombre} para una sede.
    Usado por pdf_generator para poblar los encabezados de los PDFs.
    """
    if _use_supabase():
        r = (
            _get_supabase()
            .table("sedes")
            .select("nombre, instituciones(nombre, orientador_nombre, municipios(nombre))")
            .eq("id", sede_id)
            .limit(1)
            .execute()
        )
        if not r.data:
            return {"institucion": "", "municipio": "", "orientador_nombre": ""}
        row = r.data[0]
        inst = row.get("instituciones") or {}
        mun = inst.get("municipios") or {}
        return {
            "institucion":      inst.get("nombre", ""),
            "municipio":        mun.get("nombre", ""),
            "orientador_nombre": inst.get("orientador_nombre", ""),
        }

    _ensure_sqlite()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT i.nombre  AS institucion,
                   m.nombre  AS municipio,
                   i.orientador_nombre
            FROM   sedes         s
            JOIN   instituciones i ON s.institucion_id = i.id
            JOIN   municipios    m ON i.municipio_id   = m.id
            WHERE  s.id = ?
            """,
            (sede_id,),
        ).fetchone()
        if row is None:
            return {"institucion": "", "municipio": "", "orientador_nombre": ""}
        return dict(row)