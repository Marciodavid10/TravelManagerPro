from flask import Flask, render_template, request, redirect, url_for, session, flash
from pathlib import Path
import json
import smtplib
print("APP INICIOU")
from email.message import EmailMessage
from functools import wraps
from database import criar_tabelas, conectar
from config import SECRET_KEY

app = Flask(__name__)
print("APP INICIOU")
app.secret_key = SECRET_KEY

EMAIL_SENDER = "noreply@naturviagens.traveltool.pt"
EMAIL_RECIPIENTS = ["davidmarcio455@gmail.com", "suporte@naturviagens.traveltool.pt"]
SMTP_SERVER = "localhost"
SMTP_PORT = 25

data_path = Path(__file__).resolve().parent / "data"
users_file = data_path / "users.json"
notifications_file = data_path / "notifications.log"


def ensure_users_file():
    data_path.mkdir(exist_ok=True)
    admin_user = {
        "id": 1,
        "nome": "Administrador",
        "email": "admin@naturviagens.pt",
        "telefone": "",
        "password": "1234",
        "role": "admin",
    }

    if not users_file.exists():
        users_file.write_text(json.dumps([admin_user], indent=2, ensure_ascii=False), encoding="utf-8")
        return

    try:
        users = json.loads(users_file.read_text(encoding="utf-8") or "[]")
    except ValueError:
        users = []

    if not any(u.get("email", "").strip().lower() == admin_user["email"] for u in users):
        users.insert(0, admin_user)
        users_file.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")


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
        email = user.get("email", "").strip().lower()
        telefone = user.get("telefone", "").strip().lower()
        nome = user.get("nome", "").strip().lower()
        if identifier == email or identifier == telefone or identifier == nome:
            return user
    return None


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    for user in load_users():
        if str(user.get("id")) == str(user_id):
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


def _process_login(identifier, password):
    user = find_user_by_identifier(identifier)
    if user and user.get("password") == password:
        session["user_id"] = int(user["id"])
        session["user_role"] = user.get("role")
        if user.get("role") == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("area_cliente"))
    return render_template("login.html", error="Credenciais inválidas. Tente novamente.")


@app.route("/")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return _process_login(request.form.get("identifier"), request.form.get("password"))

    user = current_user()
    if user is not None:
        if user.get("role") == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("area_cliente"))
    return render_template("login.html")


@app.route("/entrar", methods=["POST"])
def entrar():
    return _process_login(request.form.get("identifier"), request.form.get("password"))


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

    clients = [u for u in load_users() if u["role"] == "client"]
    total_clients = len(clients)
    total_trips = sum(len(u.get("viagens", [])) for u in clients)
    pending_payments = sum(
        1
        for u in clients
        for payment in u.get("pagamentos", [])
        if payment.get("status", "").lower() != "pago"
    )
    documents_pending = sum(
        1
        for u in clients
        for status in u.get("documentos", {}).values()
        if "pendente" in status.lower()
    )

    stats = {
        "total_clients": total_clients,
        "total_trips": total_trips,
        "pending_payments": pending_payments,
        "documents_pending": documents_pending,
    }

    return render_template("dashboard.html", user=user, stats=stats)

@app.route("/clientes")
@login_required
def clientes():
    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

    try:
        db = conectar()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM clientes")

        clients = cursor.fetchall()

        print("CLIENTES ENCONTRADOS:", clients)

        cursor.close()
        db.close()

    except Exception as e:
        print("ERRO CLIENTES:", e)
        clients = []

    return render_template("clientes.html", clients=clients)


@app.route("/clientes/<int:client_id>")
@login_required
def cliente_detalhes(client_id):
    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

    client = None

    try:
        db = conectar()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, nome, email, telefone, passaporte
            FROM clientes
            WHERE id = %s
        """, (client_id,))

        client = cursor.fetchone()

        cursor.close()
        db.close()

    except Exception as e:
        print("Erro ao buscar cliente:", e)

    if client is None:
        return redirect(url_for("clientes"))

    return render_template("cliente_detalhes.html", client=client)

@app.route("/novo_cliente", methods=["GET", "POST"])
@login_required
def novo_cliente():

    user = current_user()

    if user["role"] != "admin":
        return redirect(url_for("login"))

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

        db = None

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO clientes
                (nome, email, telefone, passaporte)
                VALUES (%s, %s, %s, %s)
            """,
            (nome, email, telefone, passaporte))

            db.commit()

            return render_template(
                "novo_cliente.html",
                success="Cliente criado com sucesso."
            )

        except Exception as exc:
            print("Erro ao guardar cliente:", exc)

            return render_template(
                "novo_cliente.html",
                error="Não foi possível guardar o cliente.",
                nome=nome,
                email=email,
                telefone=telefone,
                passaporte=passaporte,
            )

        finally:
            if db:
                db.close()

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
    return render_template("viagens.html", user=user)


@app.route("/hoteis")
@login_required
def hoteis():
    user = current_user()
    return render_template("hoteis.html", user=user)


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
    return render_template("relatorios.html")




if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")