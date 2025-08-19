# PythonAnywhere: configure a daily task calling this script to optimize next week
from datetime import date, timedelta
from app import create_app
from app.models import get_or_create_week
from app.services import build_usuarios_from_db, build_conductores_from_db, persist_assignments
from app.optimizers import modelo_densidad, modelo_conductores, fill_pasajeros

app = create_app()

with app.app_context():
    today = date.today()
    mon = today - timedelta(days=today.weekday())  # semana actual
    week = get_or_create_week(mon)

    usuarios = build_usuarios_from_db(week.id)
    if usuarios:
        y, s1 = modelo_densidad(usuarios)
        print("Modelo1:", s1)
        conductores = build_conductores_from_db(week.id, usuarios)
        x, N_t, D_t, s2 = modelo_conductores(conductores, y)
        print("Modelo2:", s2)
        if s1 == "Optimal" and s2 == "Optimal":
            pasajeros = fill_pasajeros(y, x)
            persist_assignments(week.id, y, x, pasajeros)
            print("OK: optimization done for current week", mon)
        else:
            print("Optimization not optimal, skipping persist")
    else:
        print("No users/preferences for current week", mon)
