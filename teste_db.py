from database import conectar

try:
    db = conectar()
    print("Ligação realizada com sucesso!")

    cursor = db.cursor()
    cursor.execute("SELECT DATABASE();")

    print(cursor.fetchone())

    cursor.close()
    db.close()

except Exception as erro:
    print("Erro:", erro)