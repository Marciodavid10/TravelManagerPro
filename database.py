import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def conectar():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def criar_tabelas():

    db = conectar()
    cursor = db.cursor()

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

    db.commit()
    db.close()