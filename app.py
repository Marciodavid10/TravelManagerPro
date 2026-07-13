from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from pathlib import Path
import json
import smtplib
from email.message import EmailMessage
from functools import wraps
from database import criar_tabelas,conectar,rows_to_dicts
from werkzeug.utils import secure_filename
from flask import send_from_directory
import os
import uuid
import io

app = Flask(__name__)
app.secret_key = "naturviagens-secret-key"

EMAIL_SENDER = "noreply@naturviagens.traveltool.pt"
EMAIL_RECIPIENTS = ["davidmarcio455@gmail.com", "suporte@naturviagens.traveltool.pt"]
SMTP_SERVER = "localhost"
SMTP_PORT = 25

data_path = Path(__file__).resolve().parent / "data"
users_file = data_path / "users.json"
notifications_file = data_path / "notifications.log"


def ensure_users_file():
    data_path.mkdir(exist_ok=True)
    if not users_file.exists():
        admin_user = {
            "id": 1,
            "nome": "Administrador",
            "email": "admin@naturviagens.pt",
            "telefone": "",
            "password": "1234",
            "role": "admin",
        }
        users_file.write_text(json.dumps([admin_user], indent=2, ensure_ascii=False), encoding="utf-8")


def load_users():
    ensure_users_file()
    with users_file.open("r", encoding="utf-8") as f:
        users = json.load(f)

    changed = False
    for user in users:
        changed |= ensure_user_profile(user)

    if changed:
        save_users(users)

    return users


def save_users(users):
    ensure_users_file()
    with users_file.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def ensure_user_profile(user):
    changed = False
    if "documentos" not in user:
        user["documentos"] = {
            "Passaporte": "Pendente",
            "Seguro de viagem": "Pendente",
            "Voucher": "Pendente",
        }
        changed = True
    if "viagens" not in user:
        user["viagens"] = [
            {"destino": "Lisboa", "data": "15/05/2026", "status": "Confirmada"}
        ]
        changed = True
    if "hoteis" not in user:
        user["hoteis"] = [
            {"hotel": "Algarve Beach", "checkin": "15/05/2026", "status": "Confirmado"}
        ]
        changed = True
    if "pagamentos" not in user:
        user["pagamentos"] = [
            {"descricao": "Pacote viagem", "valor": "750", "status": "Pago"},
            {"descricao": "Depósito final", "valor": "250", "status": "Pendente"},
        ]
        changed = True
    if "itinerario" not in user:
        user["itinerario"] = [
            "Dia 1: City tour e receção.",
            "Dia 2: Praia e experiências locais.",
            "Dia 3: Passeio cultural e descanso.",
        ]
        changed = True
    if "restaurantes" not in user:
        user["restaurantes"] = [
            {"local": "Mar Azul", "data": "16/05/2026", "status": "Confirmado"}
        ]
        changed = True
    return changed


def send_notification_email(subject, message):
    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = EMAIL_SENDER
    email["To"] = ", ".join(EMAIL_RECIPIENTS)
    email.set_content(message)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(email)
            print("Email notification enviado:", subject)
            return True
    except Exception as exc:
        print("Falha ao enviar email:", exc)
        log_notification(subject, message)
        return False


def log_notification(subject, message):
    notifications_file.parent.mkdir(exist_ok=True)
    with notifications_file.open("a", encoding="utf-8") as f:
        f.write(f"SUBJECT: {subject}\n")
        f.write(f"{message}\n")
        f.write("---\n")


def find_user_by_identifier(identifier):
    if not identifier:
        return None
    identifier = identifier.strip().lower()
    for user in load_users():
        if identifier == user["email"].lower() or identifier == user["telefone"].strip().lower() or identifier == user["nome"].strip().lower():
            return user
    return None


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    for user in load_users():
        if user["id"] == user_id:
            return user
    return None


def get_client_by_id(client_id):
    for user in load_users():
        if user["id"] == client_id and user["role"] == "client":
            return user
    return None


def is_strong_password(password):
    if len(password) < 8:
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password):
        return False
    return True


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def exec_db(cursor, db, query, params=None):
    """Execute query replacing %s with ? for sqlite3 when needed."""
    if params is None:
        return cursor.execute(query)
    if getattr(db, "_is_sqlite", False):
        query = query.replace("%s", "?")
    return cursor.execute(query, params)


@app.route("/")
@app.route("/login", methods=["GET","POST"])
def login():
    user = current_user()
    if user is not None:
        if user["role"] == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("area_cliente"))
    return render_template("login.html")


@app.route("/entrar", methods=["POST"])
def entrar():
    identifier = request.form.get("identifier")
    password = request.form.get("password")
    user = find_user_by_identifier(identifier)
    if user and user["password"] == password:
        session["user_id"] = user["id"]
        session["user_role"] = user["role"]
        if user["role"] == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("area_cliente"))
    return render_template("login.html", error="Credenciais inválidas. Tente novamente.")


@app.route("/registrar", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        telefone = request.form.get("telefone", "").strip()
        password = request.form.get("password", "").strip()

        if not nome or not email or not telefone or not password:
            return render_template("registrar.html", error="Por favor preencha todos os campos.")

        if not is_strong_password(password):
            return render_template(
                "registrar.html",
                error="A senha deve ter pelo menos 8 caracteres, letras maiúsculas, minúsculas, números e um símbolo.",
            )

        users = load_users()
        if any(u["email"].lower() == email.lower() for u in users):
            return render_template("registrar.html", error="Email já registado.")
        if any(u["telefone"].strip().lower() == telefone.lower() for u in users if u["telefone"]):
            return render_template("registrar.html", error="Telefone já registado.")

        next_id = max((u["id"] for u in users), default=0) + 1
        users.append({
            "id": next_id,
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "password": password,
            "role": "client",
        })
        save_users(users)
        flash("Conta criada com sucesso. Faça login para continuar.", "success")
        return redirect(url_for("login"))

    return render_template("registrar.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM clientes")
    clients = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        clients=clients
    )


@app.route("/clientes")
@login_required
def clientes():

    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM clientes")

    clients = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "clientes.html",
        clients=clients
    )


@app.route("/clientes/<int:client_id>")
@login_required
def cliente_detalhes(client_id):
    user = current_user()
    if user["role"] != "admin":
        return redirect(url_for("login"))

    client = None
    viagens = []
    documentos = []
    pagamentos = []
    itinerarios = []

    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT * FROM clientes WHERE id=%s", (client_id,))
        row = cursor.fetchone()
        if row:
            client = rows_to_dicts(cursor, [row])[0]

        exec_db(cursor, db, "SELECT * FROM viagens WHERE cliente_id = %s ORDER BY id DESC", (client_id,))
        viagens = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, "SELECT * FROM documentos WHERE cliente_id = %s ORDER BY id DESC", (client_id,))
        documentos = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, "SELECT * FROM pagamentos WHERE cliente_id = %s ORDER BY id DESC", (client_id,))
        pagamentos = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, "SELECT * FROM itinerarios WHERE cliente_id = %s ORDER BY id DESC", (client_id,))
        itinerarios = rows_to_dicts(cursor, cursor.fetchall())

        cursor.close()
    except Exception as exc:
        print("Erro ao buscar cliente/dados relacionados:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if client is None:
        return redirect(url_for("clientes"))

    return render_template("cliente_detalhes.html", client=client, viagens=viagens, documentos=documentos, pagamentos=pagamentos, itinerarios=itinerarios)

@app.route("/editar_cliente/<int:client_id>", methods=["GET","POST"])
@login_required
def editar_cliente(client_id):

    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor()

    if request.method == "POST":

        nome = request.form.get("nome")
        email = request.form.get("email")
        telefone = request.form.get("telefone")
        passaporte = request.form.get("passaporte")

        exec_db(cursor, db, """
            UPDATE clientes
            SET nome=%s,
                email=%s,
                telefone=%s,
                passaporte=%s
            WHERE id=%s
        """, (nome, email, telefone, passaporte, client_id))

        db.commit()

        cursor.close()
        try:
            db.close()
        except Exception:
            pass

        return redirect(url_for("clientes"))

    exec_db(cursor, db, "SELECT * FROM clientes WHERE id=%s", (client_id,))
    cliente = cursor.fetchone()
    if cliente:
        cliente = rows_to_dicts(cursor, [cliente])[0]

    cursor.close()
    try:
        db.close()
    except Exception:
        pass

    return render_template(
        "editar_cliente.html",
        cliente=cliente
    )

@app.route("/novo_cliente", methods=["GET","POST"])
def novo_cliente():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        telefone = request.form.get("telefone", "").strip()
        passaporte = request.form.get("passaporte", "").strip()

        if not nome or not email or not telefone or not passaporte:
            return render_template(
                "novo_cliente.html",
                error="Por favor preencha todos os campos.",
                nome=nome,
                email=email,
                telefone=telefone,
                passaporte=passaporte,
            )

        try:
            print("Novo cliente enviado:", nome, email, telefone, passaporte)
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, """
            INSERT INTO clientes
            (nome,email,telefone,passaporte)
            VALUES (%s,%s,%s,%s)
            """, (nome, email, telefone, passaporte))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao guardar cliente:", exc)
            return render_template(
                "novo_cliente.html",
                error="Não foi possível guardar o cliente. Verifique a base de dados e tente novamente.",
                nome=nome,
                email=email,
                telefone=telefone,
                passaporte=passaporte,
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

        return render_template("novo_cliente.html", success="Cliente criado com sucesso.")

    return render_template("novo_cliente.html")

@app.route("/area-cliente")
@login_required
def area_cliente():
    user = current_user()
    return render_template("cliente_area.html", user=user)


@app.route("/viagens")
@login_required
def viagens():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    # For regular users, show a simple view (their viagens managed elsewhere)
    return render_template("viagens.html", user=user)


# --- Admin viagens CRUD ---
def fetch_db_clients():
    """Return list of clients from DB as dicts with id and nome/email if available."""
    clients = []
    try:
        db = conectar()
        cursor = db.cursor()
        cursor.execute("SELECT id, nome, email FROM clientes ORDER BY nome ASC")
        clients = cursor.fetchall()
        clients = rows_to_dicts(cursor, clients)
        cursor.close()
    except Exception as exc:
        print("Erro a buscar clientes do DB:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass
    return clients


@app.route("/admin/viagens")
@login_required
def admin_viagens():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))
    viagens = []
    try:
        db = conectar()
        cursor = db.cursor()
        cursor.execute("SELECT v.id, v.destino, v.data_inicio, v.data_fim, v.cliente_id, c.nome AS cliente_nome FROM viagens v LEFT JOIN clientes c ON v.cliente_id = c.id ORDER BY v.id DESC")
        viagens = cursor.fetchall()
        viagens = rows_to_dicts(cursor, viagens)
        cursor.close()
    except Exception as exc:
        print("Erro a listar viagens:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return render_template("admin_viagens.html", viagens=viagens)


@app.route("/admin/viagens/novo", methods=["GET", "POST"])
@login_required
def admin_viagem_novo():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()

    if request.method == "POST":
        destino = request.form.get("destino", "").strip()
        data_inicio = request.form.get("data_inicio", "").strip()
        data_fim = request.form.get("data_fim", "").strip()
        cliente_id = request.form.get("cliente_id") or None

        if not destino or not data_inicio or not cliente_id:
            return render_template("admin_viagem_form.html", error="Preencha os campos obrigatórios.", clients=clients, destino=destino, data_inicio=data_inicio, data_fim=data_fim, cliente_id=cliente_id)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "INSERT INTO viagens (destino, data_inicio, data_fim, cliente_id) VALUES (%s,%s,%s,%s)", (destino, data_inicio, data_fim, cliente_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao criar viagem:", exc)
            return render_template("admin_viagem_form.html", error="Erro ao criar viagem.", clients=clients, destino=destino, data_inicio=data_inicio, data_fim=data_fim, cliente_id=cliente_id)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_viagens"))

    return render_template("admin_viagem_form.html", clients=clients)


@app.route("/admin/viagens/<int:viagem_id>/editar", methods=["GET", "POST"])
@login_required
def admin_viagem_editar(viagem_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()
    viagem = None
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT * FROM viagens WHERE id = %s", (viagem_id,))
        viagem = cursor.fetchone()
        if viagem:
            viagem = rows_to_dicts(cursor, [viagem])[0]
        cursor.close()
    except Exception as exc:
        print("Erro ao buscar viagem:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if viagem is None:
        return redirect(url_for("admin_viagens"))

    if request.method == "POST":
        destino = request.form.get("destino", "").strip()
        data_inicio = request.form.get("data_inicio", "").strip()
        data_fim = request.form.get("data_fim", "").strip()
        cliente_id = request.form.get("cliente_id") or None

        if not destino or not data_inicio or not cliente_id:
            return render_template("admin_viagem_form.html", error="Preencha os campos obrigatórios.", clients=clients, viagem=viagem)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "UPDATE viagens SET destino=%s, data_inicio=%s, data_fim=%s, cliente_id=%s WHERE id=%s", (destino, data_inicio, data_fim, cliente_id, viagem_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao atualizar viagem:", exc)
            return render_template("admin_viagem_form.html", error="Erro ao actualizar viagem.", clients=clients, viagem=viagem)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_viagens"))

    return render_template("admin_viagem_form.html", clients=clients, viagem=viagem)


@app.route("/admin/viagens/<int:viagem_id>/delete", methods=["POST"])
@login_required
def admin_viagem_delete(viagem_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "DELETE FROM viagens WHERE id = %s", (viagem_id,))
        db.commit()
        cursor.close()
    except Exception as exc:
        print("Erro ao apagar viagem:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for("admin_viagens"))


@app.route("/hoteis")
@login_required
def hoteis():
    user = current_user()
    return render_template("hoteis.html", user=user)


# --- Admin documentos CRUD ---
@app.route("/admin/documentos")
@login_required
def admin_documentos():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    documentos = []
    try:
        db = conectar()
        cursor = db.cursor()
        cursor.execute("SELECT d.id, d.nome, d.ficheiro, d.cliente_id, c.nome AS cliente_nome FROM documentos d LEFT JOIN clientes c ON d.cliente_id = c.id ORDER BY d.id DESC")
        documentos = cursor.fetchall()
        documentos = rows_to_dicts(cursor, documentos)
        cursor.close()
    except Exception as exc:
        print("Erro a listar documentos:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return render_template("admin_documentos.html", documentos=documentos)


@app.route("/admin/documentos/novo", methods=["GET", "POST"])
@login_required
def admin_documento_novo():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cliente_id = request.form.get("cliente_id") or None
        ficheiro = request.files.get("ficheiro")

        if not nome or not ficheiro or not cliente_id:
            return render_template("admin_documento_form.html", error="Preencha todos os campos e selecione um ficheiro.", clients=clients, nome=nome, cliente_id=cliente_id)

        uploads_dir = data_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        filename = secure_filename(ficheiro.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        target_path = uploads_dir / unique_name
        ficheiro.save(str(target_path))

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "INSERT INTO documentos (nome, ficheiro, cliente_id) VALUES (%s,%s,%s)", (nome, unique_name, cliente_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao criar documento:", exc)
            return render_template("admin_documento_form.html", error="Erro ao guardar documento.", clients=clients, nome=nome, cliente_id=cliente_id)
        finally:
            try:
                db.close()
            except Exception:
                pass

        # redirect to provided 'next' if present (e.g., return to cliente_detalhes)
        next_url = request.form.get('next') or request.args.get('next')
        if next_url:
            return redirect(next_url)

        return redirect(url_for("admin_documentos"))

    return render_template("admin_documento_form.html", clients=clients)


@app.route("/admin/documentos/<int:doc_id>/download")
@login_required
def admin_documento_download(doc_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT ficheiro FROM documentos WHERE id = %s", (doc_id,))
        row = cursor.fetchone()
        cursor.close()
    except Exception as exc:
        print("Erro ao obter documento:", exc)
        row = None
    finally:
        try:
            db.close()
        except Exception:
            pass

    if not row:
        return redirect(url_for("admin_documentos"))

    filename = row[0] if not isinstance(row, dict) else row.get("ficheiro")
    uploads_dir = data_path / "uploads"
    return send_from_directory(str(uploads_dir), filename, as_attachment=True)


@app.route("/admin/documentos/<int:doc_id>/delete", methods=["POST"])
@login_required
def admin_documento_delete(doc_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT ficheiro FROM documentos WHERE id = %s", (doc_id,))
        row = cursor.fetchone()
        filename = None
        if row:
            filename = row[0] if not isinstance(row, dict) else row.get("ficheiro")
        exec_db(cursor, db, "DELETE FROM documentos WHERE id = %s", (doc_id,))
        db.commit()
        cursor.close()
        if filename:
            try:
                (data_path / "uploads" / filename).unlink()
            except Exception:
                pass
    except Exception as exc:
        print("Erro ao apagar documento:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for("admin_documentos"))


# --- Admin pagamentos CRUD ---
@app.route("/admin/pagamentos")
@login_required
def admin_pagamentos():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    pagamentos = []
    try:
        db = conectar()
        cursor = db.cursor()
        cursor.execute("SELECT p.id, p.valor, p.estado, p.cliente_id, c.nome AS cliente_nome FROM pagamentos p LEFT JOIN clientes c ON p.cliente_id = c.id ORDER BY p.id DESC")
        pagamentos = cursor.fetchall()
        pagamentos = rows_to_dicts(cursor, pagamentos)
        cursor.close()
    except Exception as exc:
        print("Erro a listar pagamentos:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return render_template("admin_pagamentos.html", pagamentos=pagamentos)


@app.route("/admin/pagamentos/novo", methods=["GET", "POST"])
@login_required
def admin_pagamento_novo():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id") or None
        valor = request.form.get("valor") or "0"
        estado = request.form.get("estado") or "Pendente"

        if not cliente_id:
            return render_template("admin_pagamento_form.html", error="Selecione o cliente.", clients=clients, valor=valor, estado=estado, cliente_id=cliente_id)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "INSERT INTO pagamentos (valor, estado, cliente_id) VALUES (%s,%s,%s)", (valor, estado, cliente_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao criar pagamento:", exc)
            return render_template("admin_pagamento_form.html", error="Erro ao criar pagamento.", clients=clients, valor=valor, estado=estado, cliente_id=cliente_id)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_pagamentos"))

    return render_template("admin_pagamento_form.html", clients=clients)


@app.route("/admin/pagamentos/<int:pag_id>/editar", methods=["GET", "POST"])
@login_required
def admin_pagamento_editar(pag_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()
    pagamento = None
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT * FROM pagamentos WHERE id = %s", (pag_id,))
        pagamento = cursor.fetchone()
        if pagamento:
            pagamento = rows_to_dicts(cursor, [pagamento])[0]
        cursor.close()
    except Exception as exc:
        print("Erro ao buscar pagamento:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if pagamento is None:
        return redirect(url_for("admin_pagamentos"))

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id") or None
        valor = request.form.get("valor") or "0"
        estado = request.form.get("estado") or "Pendente"

        if not cliente_id:
            return render_template("admin_pagamento_form.html", error="Selecione o cliente.", clients=clients, pagamento=pagamento)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "UPDATE pagamentos SET valor=%s, estado=%s, cliente_id=%s WHERE id=%s", (valor, estado, cliente_id, pag_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao atualizar pagamento:", exc)
            return render_template("admin_pagamento_form.html", error="Erro ao actualizar pagamento.", clients=clients, pagamento=pagamento)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_pagamentos"))

    return render_template("admin_pagamento_form.html", clients=clients, pagamento=pagamento)


@app.route("/admin/pagamentos/<int:pag_id>/delete", methods=["POST"])
@login_required
def admin_pagamento_delete(pag_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "DELETE FROM pagamentos WHERE id = %s", (pag_id,))
        db.commit()
        cursor.close()
    except Exception as exc:
        print("Erro ao apagar pagamento:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for("admin_pagamentos"))


# --- Admin itinerario CRUD ---
@app.route("/admin/itinerarios")
@login_required
def admin_itinerarios():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    itens = []
    try:
        db = conectar()
        cursor = db.cursor()
        cursor.execute("SELECT it.id, it.titulo, it.detalhes, it.data, it.cliente_id, c.nome AS cliente_nome FROM itinerarios it LEFT JOIN clientes c ON it.cliente_id = c.id ORDER BY it.id DESC")
        itens = cursor.fetchall()
        itens = rows_to_dicts(cursor, itens)
        cursor.close()
    except Exception as exc:
        print("Erro a listar itinerarios:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return render_template("admin_itinerarios.html", itens=itens)


@app.route("/admin/itinerarios/novo", methods=["GET", "POST"])
@login_required
def admin_itinerario_novo():
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        detalhes = request.form.get("detalhes", "").strip()
        data_field = request.form.get("data", "").strip()
        cliente_id = request.form.get("cliente_id") or None

        if not titulo or not cliente_id:
            return render_template("admin_itinerario_form.html", error="Preencha os campos obrigatórios.", clients=clients, titulo=titulo, detalhes=detalhes, data=data_field, cliente_id=cliente_id)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "INSERT INTO itinerarios (titulo, detalhes, data, cliente_id) VALUES (%s,%s,%s,%s)", (titulo, detalhes, data_field, cliente_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao criar itinerario:", exc)
            return render_template("admin_itinerario_form.html", error="Erro ao guardar itinerario.", clients=clients, titulo=titulo, detalhes=detalhes, data=data_field, cliente_id=cliente_id)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_itinerarios"))

    return render_template("admin_itinerario_form.html", clients=clients)


@app.route("/admin/itinerarios/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def admin_itinerario_editar(item_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))

    clients = fetch_db_clients()
    item = None
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "SELECT * FROM itinerarios WHERE id = %s", (item_id,))
        item = cursor.fetchone()
        if item:
            item = rows_to_dicts(cursor, [item])[0]
        cursor.close()
    except Exception as exc:
        print("Erro ao buscar itinerario:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if item is None:
        return redirect(url_for("admin_itinerarios"))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        detalhes = request.form.get("detalhes", "").strip()
        data_field = request.form.get("data", "").strip()
        cliente_id = request.form.get("cliente_id") or None

        if not titulo or not cliente_id:
            return render_template("admin_itinerario_form.html", error="Preencha os campos obrigatórios.", clients=clients, item=item)

        try:
            db = conectar()
            cursor = db.cursor()
            exec_db(cursor, db, "UPDATE itinerarios SET titulo=%s, detalhes=%s, data=%s, cliente_id=%s WHERE id=%s", (titulo, detalhes, data_field, cliente_id, item_id))
            db.commit()
            cursor.close()
        except Exception as exc:
            print("Erro ao atualizar itinerario:", exc)
            return render_template("admin_itinerario_form.html", error="Erro ao actualizar itinerario.", clients=clients, item=item)
        finally:
            try:
                db.close()
            except Exception:
                pass

        return redirect(url_for("admin_itinerarios"))

    return render_template("admin_itinerario_form.html", clients=clients, item=item)


@app.route("/admin/itinerarios/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_itinerario_delete(item_id):
    user = current_user()
    if user is None or user.get("role") != "admin":
        return redirect(url_for("login"))
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, "DELETE FROM itinerarios WHERE id = %s", (item_id,))
        db.commit()
        cursor.close()
    except Exception as exc:
        print("Erro ao apagar itinerario:", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for("admin_itinerarios"))


@app.route('/admin/clientes/<int:client_id>/pagamentos/quick_add', methods=['POST'])
@login_required
def admin_cliente_pagamento_quick_add(client_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return redirect(url_for('login'))

    valor = request.form.get('valor') or '0'
    estado = request.form.get('estado') or 'Pendente'
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'INSERT INTO pagamentos (valor, estado, cliente_id) VALUES (%s,%s,%s)', (valor, estado, client_id))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao adicionar pagamento rápido:', exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for('cliente_detalhes', client_id=client_id))


@app.route('/admin/clientes/<int:client_id>/itinerarios/quick_add', methods=['POST'])
@login_required
def admin_cliente_itinerario_quick_add(client_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return redirect(url_for('login'))

    titulo = request.form.get('titulo', '').strip()
    detalhes = request.form.get('detalhes', '').strip()
    data_field = request.form.get('data', '').strip()
    if not titulo:
        return redirect(url_for('cliente_detalhes', client_id=client_id))
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'INSERT INTO itinerarios (titulo, detalhes, data, cliente_id) VALUES (%s,%s,%s,%s)', (titulo, detalhes, data_field, client_id))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao adicionar itinerario rápido:', exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return redirect(url_for('cliente_detalhes', client_id=client_id))


@app.route('/admin/pagamentos/<int:pag_id>/ajax_update', methods=['POST'])
@login_required
def admin_pagamento_ajax_update(pag_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return {'ok': False, 'error': 'unauthorized'}, 403

    data = request.get_json() or {}
    valor = data.get('valor')
    estado = data.get('estado')
    # validate valor
    try:
        if valor is not None:
            float(valor)
    except Exception:
        return {'ok': False, 'error': 'valor inválido'}, 400

    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'UPDATE pagamentos SET valor=%s, estado=%s WHERE id=%s', (valor, estado, pag_id))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao actualizar pagamento ajax:', exc)
        return {'ok': False, 'error': 'db error'}, 500
    finally:
        try:
            db.close()
        except Exception:
            pass

    return {'ok': True}


@app.route('/admin/pagamentos/<int:pag_id>/ajax_delete', methods=['POST'])
@login_required
def admin_pagamento_ajax_delete(pag_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return {'ok': False, 'error': 'unauthorized'}, 403
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'DELETE FROM pagamentos WHERE id = %s', (pag_id,))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao apagar pagamento ajax:', exc)
        return {'ok': False, 'error': 'db error'}, 500
    finally:
        try:
            db.close()
        except Exception:
            pass

    return {'ok': True}


@app.route('/admin/itinerarios/<int:item_id>/ajax_update', methods=['POST'])
@login_required
def admin_itinerario_ajax_update(item_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return {'ok': False, 'error': 'unauthorized'}, 403
    data = request.get_json() or {}
    titulo = data.get('titulo', '').strip()
    detalhes = data.get('detalhes', '').strip()
    data_field = data.get('data', '').strip()
    if not titulo:
        return {'ok': False, 'error': 'titulo obrigatório'}, 400
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'UPDATE itinerarios SET titulo=%s, detalhes=%s, data=%s WHERE id=%s', (titulo, detalhes, data_field, item_id))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao actualizar itinerario ajax:', exc)
        return {'ok': False, 'error': 'db error'}, 500
    finally:
        try:
            db.close()
        except Exception:
            pass

    return {'ok': True}


@app.route('/admin/itinerarios/<int:item_id>/ajax_delete', methods=['POST'])
@login_required
def admin_itinerario_ajax_delete(item_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return {'ok': False, 'error': 'unauthorized'}, 403
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'DELETE FROM itinerarios WHERE id = %s', (item_id,))
        db.commit()
        cursor.close()
    except Exception as exc:
        print('Erro ao apagar itinerario ajax:', exc)
        return {'ok': False, 'error': 'db error'}, 500
    finally:
        try:
            db.close()
        except Exception:
            pass

    return {'ok': True}


@app.route('/admin/clientes/<int:client_id>/download_all_pdf')
@login_required
def admin_cliente_download_all_pdf(client_id):
    user = current_user()
    if user is None or user.get('role') != 'admin':
        return redirect(url_for('login'))

    # fetch client and related data
    client = None
    viagens = []
    documentos = []
    pagamentos = []
    itinerarios = []
    try:
        db = conectar()
        cursor = db.cursor()
        exec_db(cursor, db, 'SELECT * FROM clientes WHERE id=%s', (client_id,))
        row = cursor.fetchone()
        if row:
            client = rows_to_dicts(cursor, [row])[0]

        exec_db(cursor, db, 'SELECT * FROM viagens WHERE cliente_id = %s ORDER BY id DESC', (client_id,))
        viagens = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, 'SELECT * FROM documentos WHERE cliente_id = %s ORDER BY id DESC', (client_id,))
        documentos = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, 'SELECT * FROM pagamentos WHERE cliente_id = %s ORDER BY id DESC', (client_id,))
        pagamentos = rows_to_dicts(cursor, cursor.fetchall())

        exec_db(cursor, db, 'SELECT * FROM itinerarios WHERE cliente_id = %s ORDER BY id DESC', (client_id,))
        itinerarios = rows_to_dicts(cursor, cursor.fetchall())

        cursor.close()
    except Exception as exc:
        print('Erro ao gerar PDF, falha ao ler DB:', exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if client is None:
        return redirect(url_for('clientes'))

    # generate PDF in-memory using reportlab (install via pip install reportlab)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except Exception as exc:
        print('reportlab não instalado:', exc)
        return render_template('cliente_detalhes.html', client=client, viagens=viagens, documentos=documentos, pagamentos=pagamentos, itinerarios=itinerarios, error='Instale reportlab (pip install reportlab) para gerar PDFs.')

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    def newline(space=14):
        nonlocal y
        y -= space
        if y < 60:
            c.showPage()
            y = height - 40

    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, y, f"Dados do Cliente: {client.get('nome','')} (ID: {client.get('id')})")
    newline(20)

    c.setFont('Helvetica', 11)
    c.drawString(40, y, f"Email: {client.get('email','')}")
    newline()
    c.drawString(40, y, f"Telefone: {client.get('telefone','')}")
    newline()
    c.drawString(40, y, f"Passaporte: {client.get('passaporte','')}")
    newline(18)

    # Viagens
    c.setFont('Helvetica-Bold', 13)
    c.drawString(40, y, 'Viagens:')
    newline(16)
    c.setFont('Helvetica', 10)
    if viagens:
        for v in viagens:
            c.drawString(48, y, f"- {v.get('destino','')} | {v.get('data_inicio','')} - {v.get('data_fim','')}")
            newline(12)
    else:
        c.drawString(48, y, 'Nenhuma')
        newline(12)

    # Itinerarios
    c.setFont('Helvetica-Bold', 13)
    c.drawString(40, y, 'Itinerários:')
    newline(16)
    c.setFont('Helvetica', 10)
    if itinerarios:
        for it in itinerarios:
            c.drawString(48, y, f"- {it.get('titulo','')} | {it.get('data','')}")
            newline(12)
            if it.get('detalhes'):
                c.drawString(60, y, it.get('detalhes'))
                newline(12)
    else:
        c.drawString(48, y, 'Nenhum')
        newline(12)

    # Pagamentos
    c.setFont('Helvetica-Bold', 13)
    c.drawString(40, y, 'Pagamentos:')
    newline(16)
    c.setFont('Helvetica', 10)
    if pagamentos:
        for p in pagamentos:
            c.drawString(48, y, f"- {p.get('valor','')} | {p.get('estado','')}")
            newline(12)
    else:
        c.drawString(48, y, 'Nenhum')
        newline(12)

    # Documentos
    c.setFont('Helvetica-Bold', 13)
    c.drawString(40, y, 'Documentos:')
    newline(16)
    c.setFont('Helvetica', 10)
    if documentos:
        for d in documentos:
            c.drawString(48, y, f"- {d.get('nome','')} -> {d.get('ficheiro','')}")
            newline(12)
    else:
        c.drawString(48, y, 'Nenhum')
        newline(12)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"{client.get('nome','cliente')}_dados.pdf".replace(' ', '_')
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route("/documentos", methods=["GET", "POST"])
@login_required
def documentos():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    message = None
    if request.method == "POST":
        old_documents = dict(user.get("documentos", {}))
        updated_documents = {}
        for key in old_documents:
            updated_documents[key] = request.form.get(key, "").strip() or "Pendente"

        user["documentos"] = updated_documents

        users = load_users()
        for index, u in enumerate(users):
            if u["id"] == user["id"]:
                users[index] = user
                break
        save_users(users)

        changes = []
        for key, new_value in updated_documents.items():
            old_value = old_documents.get(key, "")
            if new_value != old_value:
                changes.append(f"{key}: {old_value} -> {new_value}")

        if changes:
            subject = f"Documento atualizado - {user['nome']}"
            message_body = (
                f"O cliente {user['nome']} ({user['email']}) atualizou os documentos no painel do cliente NaturViagens.\n\n"
                + "Alterações realizadas:\n"
                + "\n".join(changes)
                + "\n\nAceda a https://naturviagens.traveltool.pt/ para rever o histórico." 
            )
            send_notification_email(subject, message_body)
            message = "Documentos atualizados com sucesso. Notificação enviada."
        else:
            message = "Nenhuma alteração detectada nos documentos."

    return render_template("documentos.html", user=user, message=message)


@app.route("/pagamentos")
@login_required
def pagamentos():
    user = current_user()
    return render_template("pagamentos.html", user=user)


@app.route("/itinerario")
@login_required
def itinerario():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("itinerario.html", user=user)


@app.route("/restaurantes")
@login_required
def restaurantes():
    user = current_user()
    return render_template("restaurantes.html", user=user)


@app.route("/relatorios")
@login_required
def relatorios():
    user = current_user()
    if user["role"] != "admin":
        return redirect(url_for("login"))
    return render_template("relatorios.html", user=user)

@app.route("/admin")
def admin():
    return render_template("admin.html")

if __name__ == "__main__":
    try:
        criar_tabelas()
    except Exception as exc:
        print("Aviso: não foi possível executar criar_tabelas():", exc)
        print("Continuando sem inicializar tabelas (útil em ambiente de desenvolvimento sem DB).")
    app.run(debug=True, host="0.0.0.0")
