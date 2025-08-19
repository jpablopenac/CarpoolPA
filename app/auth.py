from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User
from . import db
import os

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        if not name or not email or not password:
            flash("Completa todos los campos", "warning")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(email=email).first():
            flash("El correo ya está registrado", "danger")
            return redirect(url_for("auth.register"))
        u = User(name=name, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("Cuenta creada, ahora inicia sesión", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(password):
            flash("Credenciales inválidas", "danger")
            return redirect(url_for("auth.login"))
        login_user(u)
        return redirect(url_for("main.index"))
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/make-admin")
def make_admin():
    # Dev helper: only if ALLOW_MAKE_ADMIN=1
    if os.environ.get("ALLOW_MAKE_ADMIN") == "1":
        u = User.query.first()
        if u:
            u.is_admin = True
            db.session.commit()
            return "Admin granted to first user"
        return "No users"
    return "Forbidden", 403
