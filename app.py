import os
import re
import urllib.parse
from datetime import datetime, date

from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, FloatField, DateField, SelectField
from wtforms.validators import DataRequired, Email, Length, NumberRange, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db

FREE_INVOICE_LIMIT = 5

# --- App setup -------------------------------------------------------------

app = Flask(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Only acceptable for local dev. In production this MUST come from an
    # environment variable set on the host (Render/Railway secrets, etc.)
    SECRET_KEY = os.urandom(32).hex()
    app.logger.warning(
        "SECRET_KEY absente de l'environnement : clé générée aléatoirement "
        "pour cette session uniquement. Définissez SECRET_KEY en production."
    )

app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# En production derrière HTTPS (Render/Railway le font automatiquement),
# décommentez la ligne suivante :
# app.config["SESSION_COOKIE_SECURE"] = True

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Connecte-toi pour accéder à cette page."

STAGES = [
    (3, "poli"),
    (10, "ferme"),
    (20, "final"),
]

MESSAGES = {
    "poli": (
        "Bonjour {name}, petit rappel amical : la facture \"{desc}\" de "
        "{amount} {currency} était due le {due}. Merci de me confirmer le "
        "règlement quand vous pourrez !"
    ),
    "ferme": (
        "Bonjour {name}, la facture \"{desc}\" de {amount} {currency} est "
        "en retard depuis plusieurs jours (échéance le {due}). Pourriez-vous "
        "régulariser rapidement ? Merci."
    ),
    "final": (
        "Bonjour {name}, ceci est un dernier rappel concernant la facture "
        "\"{desc}\" de {amount} {currency}, échue le {due}. Merci de "
        "procéder au règlement sous peu afin d'éviter toute complication."
    ),
}


# --- Models ------------------------------------------------------------

class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.subscription_status = row["subscription_status"]


@login_manager.user_loader
def load_user(user_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row) if row else None


# --- Forms (CSRF-protected automatically via FlaskForm) --------------------

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=8, message="8 caractères minimum.")])
    confirm = PasswordField("Confirmer", validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas.")])


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])


class ClientForm(FlaskForm):
    name = StringField("Nom du client", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Téléphone WhatsApp (format international, ex: 22890000000)", validators=[DataRequired(), Length(max=20)])
    email = StringField("Email (optionnel)", validators=[Length(max=255)])


class InvoiceForm(FlaskForm):
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    description = StringField("Description", validators=[DataRequired(), Length(max=255)])
    amount = FloatField("Montant", validators=[DataRequired(), NumberRange(min=0.01)])
    currency = SelectField("Devise", choices=[("XOF", "XOF"), ("USD", "USD"), ("EUR", "EUR")])
    due_date = DateField("Date d'échéance", validators=[DataRequired()])


# --- Helpers -----------------------------------------------------------

def sanitize_phone(phone):
    """Keep only digits for wa.me links."""
    return re.sub(r"[^0-9]", "", phone)


def reminder_stage_for(due_date_str):
    """Return the reminder stage key for an unpaid invoice, or None."""
    due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    days_late = (date.today() - due).days
    if days_late < STAGES[0][0]:
        return None
    stage = None
    for threshold, name in STAGES:
        if days_late >= threshold:
            stage = name
    return stage


def build_whatsapp_link(client_name, client_phone, invoice, stage):
    template = MESSAGES[stage]
    text = template.format(
        name=client_name,
        desc=invoice["description"],
        amount=f"{invoice['amount']:.2f}",
        currency=invoice["currency"],
        due=invoice["due_date"],
    )
    phone = sanitize_phone(client_phone)
    return f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"


# --- Auth routes ---------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (form.email.data.lower(),)
            ).fetchone()
            if existing:
                flash("Un compte existe déjà avec cet email.", "error")
                return render_template("register.html", form=form)
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (form.email.data.lower(), generate_password_hash(form.password.data)),
            )
        flash("Compte créé. Connecte-toi.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (form.email.data.lower(),)
            ).fetchone()
        if row and check_password_hash(row["password_hash"], form.password.data):
            login_user(User(row))
            return redirect(url_for("dashboard"))
        flash("Email ou mot de passe incorrect.", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- Core app routes -------------------------------------------------------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        invoices = conn.execute(
            """
            SELECT invoices.*, clients.name AS client_name, clients.phone AS client_phone
            FROM invoices
            JOIN clients ON clients.id = invoices.client_id
            WHERE invoices.user_id = ?
            ORDER BY invoices.status ASC, invoices.due_date ASC
            """,
            (current_user.id,),
        ).fetchall()

    enriched = []
    for inv in invoices:
        stage = None
        wa_link = None
        if inv["status"] == "unpaid":
            stage = reminder_stage_for(inv["due_date"])
            if stage:
                wa_link = build_whatsapp_link(inv["client_name"], inv["client_phone"], inv, stage)
        enriched.append({**dict(inv), "stage": stage, "wa_link": wa_link})

    unpaid_count = sum(1 for i in enriched if i["status"] == "unpaid")
    return render_template(
        "dashboard.html",
        invoices=enriched,
        unpaid_count=unpaid_count,
        subscription_status=current_user.subscription_status,
        free_limit=FREE_INVOICE_LIMIT,
    )


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    form = ClientForm()
    if form.validate_on_submit():
        with get_db() as conn:
            conn.execute(
                "INSERT INTO clients (user_id, name, phone, email) VALUES (?, ?, ?, ?)",
                (current_user.id, form.name.data.strip(), form.phone.data.strip(), form.email.data.strip() or None),
            )
        flash("Client ajouté.", "success")
        return redirect(url_for("clients"))

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE user_id = ? ORDER BY name ASC", (current_user.id,)
        ).fetchall()
    return render_template("clients.html", form=form, clients=rows)


@app.route("/invoices/new", methods=["GET", "POST"])
@login_required
def new_invoice():
    with get_db() as conn:
        client_rows = conn.execute(
            "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name ASC", (current_user.id,)
        ).fetchall()

    if not client_rows:
        flash("Ajoute d'abord un client avant de créer une facture.", "error")
        return redirect(url_for("clients"))

    form = InvoiceForm()
    form.client_id.choices = [(c["id"], c["name"]) for c in client_rows]

    # Enforce the free-tier limit server-side (never trust the client).
    if current_user.subscription_status != "active":
        with get_db() as conn:
            month_start = date.today().replace(day=1).isoformat()
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM invoices WHERE user_id = ? AND created_at >= ?",
                (current_user.id, month_start),
            ).fetchone()["n"]
        if count >= FREE_INVOICE_LIMIT:
            flash(
                f"Limite du plan gratuit atteinte ({FREE_INVOICE_LIMIT} factures/mois). "
                "Passe au plan payant pour continuer.", "error"
            )
            return redirect(url_for("upgrade"))

    if form.validate_on_submit():
        # Verify the client actually belongs to this user (avoid IDOR).
        owned = any(c["id"] == form.client_id.data for c in client_rows)
        if not owned:
            abort(403)
        with get_db() as conn:
            conn.execute(
                """INSERT INTO invoices (user_id, client_id, description, amount, currency, due_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    current_user.id, form.client_id.data, form.description.data.strip(),
                    form.amount.data, form.currency.data, form.due_date.data.isoformat(),
                ),
            )
        flash("Facture créée.", "success")
        return redirect(url_for("dashboard"))

    return render_template("invoice_form.html", form=form)


@app.route("/invoices/<int:invoice_id>/mark-paid", methods=["POST"])
@login_required
def mark_paid(invoice_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, current_user.id)
        ).fetchone()
        if not row:
            abort(404)
        conn.execute(
            "UPDATE invoices SET status = 'paid', paid_at = datetime('now') WHERE id = ?",
            (invoice_id,),
        )
    flash("Facture marquée comme payée.", "success")
    return redirect(url_for("dashboard"))


@app.route("/upgrade")
@login_required
def upgrade():
    payment_link = os.environ.get("STRIPE_PAYMENT_LINK", "")
    return render_template("upgrade.html", payment_link=payment_link)


# --- Error handlers ----------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Accès refusé."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page introuvable."), 404


if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug)
