from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from .models import db, User, Preference, DAYS, IDA_SLOTS, VUELTA_SLOTS, Week
from .main import monday_of_week, next_week_monday

bp = Blueprint("admin", __name__)


@bp.before_request
def check_admin():
    if request.endpoint and request.endpoint.startswith("admin."):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for("auth.login"))


@bp.route("/")
@login_required
def dashboard():
    users = User.query.all()
    weeks = Week.query.order_by(Week.start_date.desc()).all()
    return render_template("admin_dashboard.html", users=users, days=DAYS, ida=IDA_SLOTS, vuelta=VUELTA_SLOTS, weeks=weeks)


@bp.post("/user/<int:user_id>/delete")
@login_required
def delete_user(user_id: int):
    u = User.query.get_or_404(user_id)
    db.session.delete(u)
    db.session.commit()
    flash("Usuario eliminado", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/cleanup_weeks")
@login_required
def cleanup_weeks():
    # Keep only current and next week; delete others to free DB
    today = date.today()
    cur_mon = today - timedelta(days=today.weekday())
    next_mon = cur_mon + timedelta(days=7)
    keep = {cur_mon, next_mon}
    to_delete = Week.query.filter(~Week.start_date.in_(keep)).all()
    cnt = 0
    for w in to_delete:
        db.session.delete(w)
        cnt += 1
    db.session.commit()
    flash(f"Semanas eliminadas: {cnt}", "info")
    return redirect(url_for("admin.dashboard"))


@bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id: int):
    if not current_user.is_admin:
        return redirect(url_for("main.index"))
    u = User.query.get_or_404(user_id)
    when = request.args.get("when", "current")
    mon = monday_of_week(date.today()) if when == "current" else next_week_monday(date.today())
    week = Week.query.filter_by(start_date=mon).first()
    if not week:
        week = Week(start_date=mon)
        db.session.add(week)
        db.session.commit()
    if request.method == "POST":
        u.volunteer_second_day = bool(request.form.get("global_volunteer"))
        for d in DAYS:
            ida = request.form.get(f"{d}_ida") or None
            vuelta = request.form.get(f"{d}_vuelta") or None
            flex_ida = bool(request.form.get(f"{d}_flex_ida"))
            flex_vuelta = bool(request.form.get(f"{d}_flex_vuelta"))
            can_drive = bool(request.form.get(f"{d}_can_drive"))
            pref = Preference.query.filter_by(user_id=u.id, week_id=week.id, day=d).first()
            if not pref:
                pref = Preference(user_id=u.id, week_id=week.id, day=d)
                db.session.add(pref)
            pref.ida_slot = ida
            pref.vuelta_slot = vuelta
            pref.flex_ida = flex_ida
            pref.flex_vuelta = flex_vuelta
            pref.can_drive = can_drive
        db.session.commit()
        flash("Preferencias actualizadas", "success")
        return redirect(url_for("admin.dashboard"))
    prefs = {p.day: p for p in Preference.query.filter_by(user_id=u.id, week_id=week.id).all()}
    return render_template("admin_edit_user.html", user=u, days=DAYS, ida=IDA_SLOTS, vuelta=VUELTA_SLOTS, prefs=prefs, when=when)
