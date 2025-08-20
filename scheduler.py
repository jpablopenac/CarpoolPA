"""
Programador: tarea semanal para optimizar la semana ACTUAL.

- Se debe programar para ejecutarse los sábados.
- Solo procesa la semana actual (lunes de la fecha de ejecución), no la próxima.
"""

from datetime import date, timedelta

from app import create_app
from app.models import get_or_create_week
from app.services import (
    build_usuarios_from_db,
    build_conductores_from_db,
    persist_assignments,
)
from app.optimizers import modelo_densidad, modelo_conductores, fill_pasajeros


def main():
    # Ejecutar solo los sábados para evitar rehacer cálculos en la semana.
    today = date.today()
    if today.weekday() != 5:  # 5 = sábado
        print(f"Omitido: {today} no es sábado; el scheduler corre solo los sábados.")
        return

    app = create_app()
    with app.app_context():
        monday = today - timedelta(days=today.weekday())  # lunes de la semana actual
        week = get_or_create_week(monday)

        usuarios = build_usuarios_from_db(week.id)
        total_demanda = sum(len(u.get("demanda_original", {})) for u in usuarios)
        if total_demanda == 0:
            print("No hay preferencias para la semana actual:", monday)
            return

        y, s1 = modelo_densidad(usuarios)
        print("Modelo1:", s1)

        conductores = build_conductores_from_db(week.id, usuarios)
        x, N_t, D_t, s2 = modelo_conductores(conductores, y)
        print("Modelo2:", s2)

        if s1 == "Optimal" and s2 == "Optimal":
            pasajeros = fill_pasajeros(y, x)
            persist_assignments(week.id, y, x, pasajeros)
            print("OK: optimización realizada para la semana actual:", monday)
        else:
            print("Optimización no óptima; no se persiste.")


if __name__ == "__main__":
    main()
