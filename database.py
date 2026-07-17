import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


DB_HOST = "projetos.epcjc.net"
DB_PORT = 3306
DB_USER = "i253669"
DB_PASSWORD = "69oD#We$"
DB_NAME = "i253669_travelmanagerpro"
SECRET_KEY = os.getenv("SECRET_KEY", "naturviagens-secret-key")


def criar_tabelas():
    db = conectar()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes(
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        email VARCHAR(100),
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
    cursor.close()
    db.close()