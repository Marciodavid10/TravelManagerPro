import sqlite3

DATABASE = "travelmanager.db"


def conectar():
    return sqlite3.connect(DATABASE)


def criar_tabelas():

    db = conectar()
    cursor = db.cursor()


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


    db.commit()
    db.close()