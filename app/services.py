from collections import defaultdict
from typing import Dict, List, Tuple
from .models import db, User, Preference, DAYS, IDA_SLOTS, VUELTA_SLOTS

Turno = Tuple[str, str, str]


def build_usuarios_from_db(week_id: int) -> List[dict]:
    users = User.query.all()
    # Build turns
    turnos: List[Turno] = []
    for d in DAYS:
        for s in IDA_SLOTS:
            turnos.append((d, s, "ida"))
        for s in VUELTA_SLOTS:
            turnos.append((d, s, "vuelta"))

    usuarios = []
    for u in users:
        prefs = {p.day: p for p in Preference.query.filter_by(user_id=u.id, week_id=week_id).all()}
        demanda = {}
        flex = {}
        for d in DAYS:
            p = prefs.get(d)
            if p and p.ida_slot:
                demanda[(d, p.ida_slot, "ida")] = 1
                if p.flex_ida:
                    # Only adjacent slots around chosen slot
                    idx = IDA_SLOTS.index(p.ida_slot)
                    for j in (idx - 1, idx, idx + 1):
                        if 0 <= j < len(IDA_SLOTS):
                            flex[(d, IDA_SLOTS[j], "ida")] = 1
            if p and p.vuelta_slot:
                demanda[(d, p.vuelta_slot, "vuelta")] = 1
                if p.flex_vuelta:
                    idx = VUELTA_SLOTS.index(p.vuelta_slot)
                    for j in (idx - 1, idx, idx + 1):
                        if 0 <= j < len(VUELTA_SLOTS):
                            flex[(d, VUELTA_SLOTS[j], "vuelta")] = 1
        usuarios.append({
            "id": u.id,
            "demanda_original": demanda,
            "flexibilidad": flex,
        })
    return usuarios


def build_conductores_from_db(week_id: int, usuarios: List[dict]) -> List[dict]:
    users = User.query.all()
    prefs_by_user = {
        u.id: {p.day: p for p in Preference.query.filter_by(user_id=u.id, week_id=week_id).all()}
        for u in users
    }

    conductores = []
    for u in users:
        prefs = prefs_by_user.get(u.id, {})
        m = {}
        v = 1 if u.volunteer_second_day else 0
        days_can_drive = 0
        for d in DAYS:
            p = prefs.get(d)
            if p and p.can_drive and p.ida_slot and p.vuelta_slot:
                for s in IDA_SLOTS:
                    m[(d, s, "ida")] = 1  # allow selection by optimizer
                for s in VUELTA_SLOTS:
                    m[(d, s, "vuelta")] = 1
                days_can_drive += 1
            else:
                for s in IDA_SLOTS:
                    m[(d, s, "ida")] = 0
                for s in VUELTA_SLOTS:
                    m[(d, s, "vuelta")] = 0
        # Priority score
        p_score = 5.0 + (2.0 if v else 0.0) + 0.5 * days_can_drive
        if days_can_drive < 2:
            p_score -= 1.0
        conductores.append({"id": u.id, "m": m, "v": v, "p": p_score})
    return conductores


def persist_assignments(week_id: int, y, x, pasajeros):
    # Reset roles and assigned slots
    prefs = Preference.query.filter_by(week_id=week_id).all()
    for p in prefs:
        p.role_ida = None
        p.role_vuelta = None
        p.assigned_ida_slot = None
        p.assigned_vuelta_slot = None

    # Apply y assignments
    for uid, tu in y.items():
        for (d, s, tipo), v in tu.items():
            pref = Preference.query.filter_by(user_id=uid, week_id=week_id, day=d).first()
            if not pref:
                # create if missing
                pref = Preference(user_id=uid, week_id=week_id, day=d)
                db.session.add(pref)
            if tipo == "ida":
                pref.assigned_ida_slot = s
            else:
                pref.assigned_vuelta_slot = s

    # Apply x (conductores)
    for uid, tu in x.items():
        for (d, s, tipo), v in tu.items():
            if v:
                pref = Preference.query.filter_by(user_id=uid, week_id=week_id, day=d).first()
                if tipo == "ida":
                    pref.role_ida = "conductor"
                    pref.assigned_ida_slot = s
                else:
                    pref.role_vuelta = "conductor"
                    pref.assigned_vuelta_slot = s

    # Apply pasajeros
    for uid, tu in pasajeros.items():
        for (d, s, tipo), v in tu.items():
            pref = Preference.query.filter_by(user_id=uid, week_id=week_id, day=d).first()
            if tipo == "ida":
                if pref.role_ida != "conductor":
                    pref.role_ida = "pasajero"
                pref.assigned_ida_slot = s
            else:
                if pref.role_vuelta != "conductor":
                    pref.role_vuelta = "pasajero"
                pref.assigned_vuelta_slot = s

    db.session.commit()
