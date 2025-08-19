from collections import defaultdict
from typing import Dict, List, Tuple
import pulp as pl
from .models import DAYS, IDA_SLOTS, VUELTA_SLOTS

Turno = Tuple[str, str, str]  # (day, slot, tipo)


def build_turnos() -> List[Turno]:
    turnos = []
    for d in DAYS:
        for s in IDA_SLOTS:
            turnos.append((d, s, "ida"))
        for s in VUELTA_SLOTS:
            turnos.append((d, s, "vuelta"))
    return turnos


def modelo_densidad(usuarios: List[dict]):
    """
    Implementación PuLP del Modelo 1 (con bonificación alpha para desempate).
    usuarios: list of {id, demanda_original: {turno: 0/1}, flexibilidad: {turno: 0/1}}
    Return y[u][t] in {0,1}
    """
    turnos = build_turnos()
    prob = pl.LpProblem("Modelo_Densidad", pl.LpMaximize)

    # Variables
    y = {
        (u["id"], t): pl.LpVariable(f"y_{u['id']}_{t[0]}_{t[1]}_{t[2]}", lowBound=0, upBound=1, cat=pl.LpBinary)
        for u in usuarios for t in turnos
    }
    # Pairwise variables to linearize density ~ maximize pairs within same slot
    # p[u,v,t] = 1 if both u and v are assigned to t
    usuarios_ids = [u["id"] for u in usuarios]
    pairs = []
    for i in range(len(usuarios_ids)):
        for j in range(i + 1, len(usuarios_ids)):
            pairs.append((usuarios_ids[i], usuarios_ids[j]))
    pvars = {
        (u, v, t): pl.LpVariable(f"p_{u}_{v}_{t[0]}_{t[1]}_{t[2]}", 0, 1, pl.LpBinary)
        for (u, v) in pairs for t in turnos
    }

    # Link p <= y and p >= y_u + y_v - 1
    for (u, v) in pairs:
        for t in turnos:
            prob += pvars[(u, v, t)] <= y[(u, t)]
            prob += pvars[(u, v, t)] <= y[(v, t)]
            prob += pvars[(u, v, t)] >= y[(u, t)] + y[(v, t)] - 1

    # Objective: maximize sum of pairs + alpha * keep original choices
    alpha = 0.1
    prob += pl.lpSum(pvars.values()) + alpha * pl.lpSum([
        (u["demanda_original"].get(t, 0)) * y[(u["id"], t)]
        for u in usuarios for t in turnos
    ])

    # Restricción 1: Flexibilidad (si f=0 y n=0, no permitir; si n=1 siempre permitir; si f=1 permitir turno adyacente gestionado en preproceso)
    # Para simplificar, permitimos y[u,t] solo si (n[u,t] == 1) OR (flexibilidad[u,t] == 1)
    for u in usuarios:
        for t in turnos:
            if not (u["demanda_original"].get(t, 0) == 1 or u["flexibilidad"].get(t, 0) == 1):
                prob += y[(u["id"], t)] == 0

    # Restricción 3: Asignación única por día (ida y vuelta por separado)
    for u in usuarios:
        for d in DAYS:
            prob += pl.lpSum(y[(u["id"], (d, s, "ida"))] for s in IDA_SLOTS) <= 1
            prob += pl.lpSum(y[(u["id"], (d, s, "vuelta"))] for s in VUELTA_SLOTS) <= 1

    # Restricción 2 (de documento): Demanda total constante
    total_original = sum(sum(u['demanda_original'].values()) for u in usuarios)
    prob += pl.lpSum(y.values()) == total_original

    # Resolver
    status = prob.solve(pl.PULP_CBC_CMD(msg=False))

    # Resultado
    asign = defaultdict(dict)
    if pl.LpStatus[prob.status] == "Optimal":
        for u in usuarios:
            for t in turnos:
                val = pl.value(y[(u["id"], t)])
                if val and val > 0.5:
                    asign[u["id"]][t] = 1
    return asign, pl.LpStatus[prob.status]


def modelo_conductores(conductores: List[dict], demanda_opt: Dict[int, Dict[Turno, int]]):
    """
    PuLP implementación del Modelo 2. Devuelve x[u,t]=1 si conductor asignado.
    conductores: list of {id, m: {t:0/1}, v:0/1, p:float}
    demanda_opt: y[u,t] del modelo 1. Para N_t usamos ceil(total_demand/4)
    """
    turnos = build_turnos()

    # Demanda total por turno y N_t calculado con capacidad=4
    demand_t = defaultdict(int)
    for _, tu in demanda_opt.items():
        for t, v in tu.items():
            if v:
                demand_t[t] += 1
    capacidad = 4
    N_t = {t: (demand_t[t] + capacidad - 1) // capacidad for t in turnos}

    prob = pl.LpProblem("Modelo_Conductores", pl.LpMaximize)

    x = {
        (c["id"], t): pl.LpVariable(f"x_{c['id']}_{t[0]}_{t[1]}_{t[2]}", 0, 1, pl.LpBinary)
        for c in conductores for t in turnos
    }

    Base_Reward = 1000.0
    prob += pl.lpSum((Base_Reward + c["p"]) * x[(c["id"], t)] for c in conductores for t in turnos)

    # 1. Disponibilidad para Manejar
    for c in conductores:
        for t in turnos:
            if not c["m"].get(t, 0):
                prob += x[(c["id"], t)] == 0

    # 2. Flujo (igual número ida y vuelta por día)
    for c in conductores:
        for d in DAYS:
            prob += pl.lpSum(x[(c["id"], (d, s, "ida"))] for s in IDA_SLOTS) \
                == pl.lpSum(x[(c["id"], (d, s, "vuelta"))] for s in VUELTA_SLOTS)

    # 3. Manejo obligatorio >=1 día completo (todos deben conducir al menos un día)
    for c in conductores:
        prob += pl.lpSum(x[(c["id"], (d, s, "ida"))] for d in DAYS for s in IDA_SLOTS) >= 1

    # 4. Segundo día voluntario
    for c in conductores:
        prob += pl.lpSum(x[(c["id"], (d, s, "ida"))] for d in DAYS for s in IDA_SLOTS) <= 1 + int(c.get("v", 0))

    # 5. Unicidad de turno por día
    for c in conductores:
        for d in DAYS:
            prob += pl.lpSum(x[(c["id"], (d, s, "ida"))] for s in IDA_SLOTS) <= 1
            prob += pl.lpSum(x[(c["id"], (d, s, "vuelta"))] for s in VUELTA_SLOTS) <= 1

    # Capacidad/limitación opcional: máximo N_t conductores por turno
    for t in turnos:
        prob += pl.lpSum(x[(c["id"], t)] for c in conductores) <= N_t[t]

    status = prob.solve(pl.PULP_CBC_CMD(msg=False))

    asign = defaultdict(dict)
    if pl.LpStatus[prob.status] == "Optimal":
        for c in conductores:
            for t in turnos:
                val = pl.value(x[(c["id"], t)])
                if val and val > 0.5:
                    asign[c["id"]][t] = 1
    return asign, N_t, demand_t, pl.LpStatus[prob.status]


def fill_pasajeros(demanda_opt: Dict[int, Dict[Turno, int]], conductores_asignados: Dict[int, Dict[Turno, int]]):
    """
    Rellena roles de pasajero para todos los y[u,t]==1 no marcados como conductores.
    """
    conductor_turnos = set()
    for uid, tu in conductores_asignados.items():
        for t, v in tu.items():
            if v:
                conductor_turnos.add((uid, t))

    pasajeros = defaultdict(dict)
    for uid, tu in demanda_opt.items():
        for t, v in tu.items():
            if v:
                if (uid, t) not in conductor_turnos:
                    pasajeros[uid][t] = 1
    return pasajeros
