from database import conectar, criar_tabelas


def seed_client():
    criar_tabelas()
    db = conectar()
    cursor = db.cursor()

    # detect parameter style for placeholders
    is_sqlite = getattr(db, "_is_sqlite", False)
    placeholder = "?" if is_sqlite else "%s"

    email = "testclient@example.com"

    # check if exists
    cursor.execute(f"SELECT id FROM clientes WHERE email = {placeholder}", (email,))
    row = cursor.fetchone()
    if row:
        print("Cliente já existe com id:", row[0] if not is_sqlite else row[0])
    else:
        cursor.execute(f"INSERT INTO clientes (nome, email, telefone, passaporte) VALUES ({placeholder},{placeholder},{placeholder},{placeholder})", ("Cliente Teste", email, "+351912345678", "P1234567"))
        db.commit()
        # fetch inserted id (sqlite: lastrowid, mysql: cursor.lastrowid)
        inserted_id = cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
        try:
            inserted_id = inserted_id or cursor.lastrowid
        except Exception:
            pass
        print("Cliente inserido, id aproximado:", inserted_id)

    try:
        cursor.close()
        db.close()
    except Exception:
        pass


if __name__ == '__main__':
    seed_client()
