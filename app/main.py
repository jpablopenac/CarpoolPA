from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from .models import db, DAYS, IDA_SLOTS, VUELTA_SLOTS, Preference, get_or_create_week, User
from .forms import PreferenceForm
from .services import build_usuarios_from_db, build_conductores_from_db, persist_assignments
from .optimizers import modelo_densidad, modelo_conductores, fill_pasajeros

bp = Blueprint("main", __name__)


def monday_of_week(dt: date) -> date:
    return dt - timedelta(days=dt.weekday())


def next_week_monday(dt: date) -> date:
    return monday_of_week(dt) + timedelta(days=7)


@bp.route("/")
@login_required
def index():
    # Horario Actual (solo semana actual)
    cur_mon = monday_of_week(date.today())
    cur_week = get_or_create_week(cur_mon)
    # Build assignment grids for all users
    def build_grid(week_id: int):
        grid_ida = {d: {s: [] for s in IDA_SLOTS} for d in DAYS}
        grid_vuelta = {d: {s: [] for s in VUELTA_SLOTS} for d in DAYS}
        prefs = Preference.query.filter_by(week_id=week_id).all()
        users = {u.id: u for u in User.query.all()}
        
        for p in prefs:
            user = users.get(p.user_id)
            name = user.name if user else str(p.user_id)
            
            if p.assigned_ida_slot:
                if p.role_ida == "conductor":
                    label = f"🚗 {name}"
                elif p.role_ida == "pasajero":
                    label = f"👤 {name}"
                else:
                    label = f"❓ {name}"
                grid_ida[p.day][p.assigned_ida_slot].append(label)
                
            if p.assigned_vuelta_slot:
                if p.role_vuelta == "conductor":
                    label = f"🚗 {name}"
                elif p.role_vuelta == "pasajero":
                    label = f"👤 {name}"
                else:
                    label = f"❓ {name}"
                grid_vuelta[p.day][p.assigned_vuelta_slot].append(label)
                
        return grid_ida, grid_vuelta

    grid_ida, grid_vuelta = build_grid(cur_week.id)

    return render_template(
        "index.html",
        days=DAYS,
        ida=IDA_SLOTS,
        vuelta=VUELTA_SLOTS,
        cur_week=cur_week,
        grid_ida=grid_ida,
        grid_vuelta=grid_vuelta,
    )


@bp.route("/usuario", methods=["GET", "POST"])
@login_required
def usuario():
    # Allow user to edit preferences for current week
    mon = monday_of_week(date.today())
    week = get_or_create_week(mon)

    if request.method == "POST":
        # Global volunteer flag
        current_user.volunteer_second_day = bool(request.form.get("global_volunteer"))
        any_can_drive = False
        for d in DAYS:
            ida = request.form.get(f"{d}_ida") or None
            vuelta = request.form.get(f"{d}_vuelta") or None
            flex_ida = bool(request.form.get(f"{d}_flex_ida"))
            flex_vuelta = bool(request.form.get(f"{d}_flex_vuelta"))
            can_drive = bool(request.form.get(f"{d}_can_drive"))
            can_drive_allowed = bool(ida and vuelta)
            if not can_drive_allowed:
                can_drive = False

            pref = Preference.query.filter_by(user_id=current_user.id, week_id=week.id, day=d).first()
            if not pref:
                pref = Preference(user_id=current_user.id, week_id=week.id, day=d)
                db.session.add(pref)
            pref.ida_slot = ida
            pref.vuelta_slot = vuelta
            pref.flex_ida = flex_ida
            pref.flex_vuelta = flex_vuelta
            pref.can_drive = can_drive
            any_can_drive = any_can_drive or can_drive
        if not any_can_drive:
            db.session.rollback()
            flash("Debes marcar al menos un día en que puedes conducir.", "danger")
            return redirect(url_for("main.usuario"))
        db.session.commit()
        flash("Preferencias guardadas", "success")
        return redirect(url_for("main.usuario"))

    # GET: build current prefs
    prefs = {p.day: p for p in Preference.query.filter_by(user_id=current_user.id, week_id=week.id).all()}
    return render_template("usuario.html", days=DAYS, ida=IDA_SLOTS, vuelta=VUELTA_SLOTS, prefs=prefs)


@bp.route("/optimize")
@login_required
def optimize_when():
    if not current_user.is_admin:
        flash("Solo admin", "danger")
        return redirect(url_for("main.index"))

    mon = monday_of_week(date.today())
    week = get_or_create_week(mon)

    usuarios = build_usuarios_from_db(week.id)
    if not usuarios:
        flash("No hay usuarios para optimizar", "warning")
        return redirect(url_for("main.index"))

    y, status1 = modelo_densidad(usuarios)
    if status1 != "Optimal":
        flash(f"Densidad no óptima: {status1}", "danger")
        return redirect(url_for("main.index"))

    conductores = build_conductores_from_db(week.id, usuarios)
    x, N_t, D_t, status2 = modelo_conductores(conductores, y)
    if status2 != "Optimal":
        flash(f"Conductores no óptimo: {status2}", "danger")
        return redirect(url_for("main.index"))

    pasajeros = fill_pasajeros(y, x)

    persist_assignments(week.id, y, x, pasajeros)

    flash("Optimización completada", "success")
    return redirect(url_for("main.index"))
