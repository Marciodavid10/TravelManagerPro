import mysql.connector
import sqlite3
import tempfile
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from pathlib import Path


class SqliteConnection(sqlite3.Connection):
    """SQLite connection subclass that allows setting custom attributes."""
    pass


def _fallback_to_sqlite():
    project_db_path = Path(__file__).resolve().parent / "data" / "local_dev.db"
    try:
        project_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(project_db_path), factory=SqliteConnection)
    except Exception:
        fallback_db_path = Path(tempfile.gettempdir()) / "travelmanagerpro_local_dev.db"
        try:
            conn = sqlite3.connect(str(fallback_db_path), factory=SqliteConnection)
        except Exception:
            conn = sqlite3.connect(":memory:", factory=SqliteConnection)

    conn.row_factory = sqlite3.Row
    conn._is_sqlite = True
    return conn

def conectar():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connection_timeout=10
    )

def rows_to_dicts(cursor, rows):
    """Normalize fetched rows to list of dicts for both MySQL and SQLite.

    - For MySQL connector rows (tuples) use `cursor.column_names` if available
    - For sqlite3.Row convert to dict
    - For already-dict rows, return as-is
    """
    if not rows:
        return []
    # sqlite3.Row supports mapping protocol
    first = rows[0]
    if isinstance(first, dict):
        return list(rows)
    if hasattr(first, "keys"):
        return [dict(r) for r in rows]
    # fallback: use cursor description or column_names
    cols = None
    if hasattr(cursor, "column_names"):
        cols = cursor.column_names
    elif getattr(cursor, "description", None):
        cols = [d[0] for d in cursor.description]
    if cols:
        return [dict(zip(cols, r)) for r in rows]
    # final fallback: return rows as-is
    return [r for r in rows]


def criar_tabelas():
    db = conectar()
    cursor = db.cursor()

    is_sqlite = getattr(db, '_is_sqlite', False)

    if is_sqlite:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE,
            telefone TEXT,
            passaporte TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS viagens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destino TEXT,
            data_inicio TEXT,
            data_fim TEXT,
            cliente_id INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            ficheiro TEXT,
            cliente_id INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valor REAL,
            estado TEXT,
            cliente_id INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS itinerarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            detalhes TEXT,
            data TEXT,
            cliente_id INTEGER
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE,
            telefone VARCHAR(50),
            passaporte VARCHAR(100)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS viagens(
            id INT AUTO_INCREMENT PRIMARY KEY,
            destino VARCHAR(100),
            data_inicio VARCHAR(50),
            data_fim VARCHAR(50),
            cliente_id INT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos(
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100),
            ficheiro VARCHAR(255),
            cliente_id INT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos(
            id INT AUTO_INCREMENT PRIMARY KEY,
            valor FLOAT,
            estado VARCHAR(50),
            cliente_id INT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS itinerarios(
            id INT AUTO_INCREMENT PRIMARY KEY,
            titulo VARCHAR(200),
            detalhes TEXT,
            data VARCHAR(50),
            cliente_id INT
        )
        """)

    db.commit()
    db.close()