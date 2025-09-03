#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import random
from collections import defaultdict

# Orden objetivo de grupos (6 en total)
GROUP_ORDER = [
    "Comida 9",
    "Cena 9",
    "Comida 10",
    "Cena 10",
    "Comida 11",
    "Comida 12",
]

HEADER_RE = re.compile(r"^\s*-\s*(Comida|Cena)\s+(\d+)\s*$", re.IGNORECASE)

# ===================== Entrada =====================

def leer_texto_multilinea() -> str:
    """
    Lee desde stdin hasta detectar:
      - Dos líneas vacías consecutivas (doble Enter), o
      - Una línea que diga exactamente 'FIN'
    """
    print("Pega aquí el mensaje completo.")
    print("Para terminar: pulsa 2 veces Enter (línea en blanco + otra en blanco).")
    print("O escribe 'FIN' en una línea sola y Enter.\n")

    lineas = []
    vacias_consecutivas = 0
    try:
        while True:
            linea = sys.stdin.readline()
            # EOF (por si el entorno no envía nueva línea)
            if not linea:
                break
            # Normalizamos fin anticipado
            if linea.strip() == "FIN":
                break

            # Detección de doble Enter
            if linea.strip() == "":
                vacias_consecutivas += 1
                if vacias_consecutivas >= 2:
                    break
            else:
                vacias_consecutivas = 0

            lineas.append(linea)
    except KeyboardInterrupt:
        # Si cancelan con Ctrl+C, usamos lo que haya.
        pass

    return "".join(lineas).strip()

# ===================== Parsing =====================

def normalize_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def parse_message(msg: str):
    """
    Devuelve:
      - todo_any: lista de nombres bajo 'TODO:' (pueden ir a cualquier grupo)
      - group_lists: dict[group_name] -> lista de nombres listados bajo ese encabezado
    """
    lines = msg.splitlines()
    todo_section = False
    current_group = None
    todo_any = []
    group_lists = defaultdict(list)

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue

        # Inicio de TODO:
        if re.match(r"^\s*TODO\s*:\s*$", line, flags=re.IGNORECASE):
            todo_section = True
            current_group = None
            continue

        # Encabezados tipo "- Comida 9"
        m = HEADER_RE.match(line)
        if m:
            kind, num = m.group(1).capitalize(), m.group(2)
            current_group = f"{kind} {num}"
            todo_section = False
            if current_group not in GROUP_ORDER:
                GROUP_ORDER.append(current_group)  # por si añaden otro día
            continue

        # Línea de nombre
        name = normalize_name(line)
        if name in ("-", "•"):
            continue

        if todo_section:
            todo_any.append(name)
        elif current_group:
            group_lists[current_group].append(name)
        else:
            # líneas sueltas fuera de secciones: ignoradas
            pass

    return todo_any, group_lists

def build_eligibilities(todo_any, group_lists):
    """
    Calcula los grupos permitidos por persona:
      - Los de TODO pueden ir a TODOS los grupos.
      - Los listados bajo encabezados solo a esos encabezados (si aparecen en varios, a cualquiera de esos).
    """
    all_groups = list(GROUP_ORDER)
    person_allowed = defaultdict(set)

    for p in todo_any:
        if p:
            person_allowed[p].update(all_groups)

    for g, names in group_lists.items():
        for p in names:
            if p:
                person_allowed[p].add(g)

    people = sorted(person_allowed.keys(), key=lambda s: s.lower())
    return people, person_allowed, all_groups

# ===================== Lógica de asignación =====================

def target_sizes(n_people, groups):
    """
    Objetivos de tamaño por grupo priorizando que las CENAS queden
    con el tamaño más pequeño cuando no se pueda empatar todo.

    Estrategia:
      - base = n // k para todos
      - reparte los 'rem' incrementos (+1) primero entre COMIDAS
        y solo si sobran, en CENAS.
    """
    k = len(groups)
    base = n_people // k
    rem = n_people % k

    targets = [base] * k
    dinner_idx = [i for i, g in enumerate(groups) if g.lower().startswith("cena")]
    lunch_idx  = [i for i in range(k) if i not in dinner_idx]

    i = 0
    while rem > 0 and i < len(lunch_idx):
        targets[lunch_idx[i]] += 1
        rem -= 1
        i += 1
    i = 0
    while rem > 0 and i < len(dinner_idx):
        targets[dinner_idx[i]] += 1
        rem -= 1
        i += 1

    return targets

def asignar(people, allowed, groups, seed=None, max_intentos=2000):
    """
    Asignación ávida aleatoria balanceada:
      1) Personas con menos opciones primero.
      2) Prefiere grupos por debajo de su objetivo.
      3) En empates, prefiere COMIDAS para mantener CENAS más pequeñas.
    """
    rng = random.Random(seed)
    n = len(people)
    idx = {g: i for i, g in enumerate(groups)}
    objetivos = target_sizes(n, groups)

    mejor = None
    mejor_score = float("inf")

    base_order = sorted(people, key=lambda p: (len(allowed[p]), p.lower()))

    for _ in range(max_intentos):
        # Baraja dentro de cada nivel de flexibilidad
        buckets = defaultdict(list)
        for p in base_order:
            buckets[len(allowed[p])].append(p)

        orden = []
        for k in sorted(buckets.keys()):
            bloque = buckets[k][:]
            rng.shuffle(bloque)
            orden.extend(bloque)

        tam = [0] * len(groups)
        asign = {}
        factible = True

        for p in orden:
            opciones = list(allowed[p])
            if not opciones:
                factible = False
                break

            # Primero grupos por debajo del objetivo
            under = [g for g in opciones if tam[idx[g]] < objetivos[idx[g]]]
            candidatos = under if under else opciones

            # Entre candidatos, los de menor tamaño actual
            min_size = min(tam[idx[g]] for g in candidatos)
            mejores = [g for g in candidatos if tam[idx[g]] == min_size]

            # Preferir COMIDAS si hay empate
            lunch_best = [g for g in mejores if not g.lower().startswith("cena")]
            if lunch_best:
                mejores = lunch_best

            elegido = rng.choice(mejores)
            asign[p] = elegido
            tam[idx[elegido]] += 1

        if factible:
            dev = sum(abs(tam[i] - objetivos[i]) for i in range(len(groups)))
            spread = max(tam) - min(tam)
            score = dev * 10 + spread
            if score < mejor_score:
                mejor_score = score
                mejor = (asign, tam, objetivos)
            if dev == 0 and spread <= 1:
                return asign, tam, objetivos

    if not mejor:
        raise RuntimeError("No se pudo encontrar una asignación factible.")
    return mejor

# ===================== Salida =====================

def imprimir_participantes_unicos(people):
    print("=== Participantes únicos detectados ===")
    print(f"Total: {len(people)}\n")
    for nombre in people:
        print(f" - {nombre}")
    print()

def imprimir_resultado(asignacion, tamanios, objetivos, groups):
    print("=== Resumen de tamaños por grupo ===")
    for g, size, tgt in zip(groups, tamanios, objetivos):
        print(f"{g:>10}: {size} (objetivo {tgt})")
    print()

    por_grupo = defaultdict(list)
    for persona, g in asignacion.items():
        por_grupo[g].append(persona)

    for g in groups:
        print(f"- {g}")
        for nombre in sorted(por_grupo[g], key=lambda s: s.lower()):
            print(f"  • {nombre}")
        print()

# ===================== Main =====================

def main():
    texto = leer_texto_multilinea()
    if not texto:
        print("No recibí texto. Vuelve a ejecutar y pega el mensaje.")
        sys.exit(1)

    todo_any, group_lists = parse_message(texto)
    personas, allowed, _ = build_eligibilities(todo_any, group_lists)

    # Aseguramos exactamente los 6 grupos objetivo en orden
    grupos = [g for g in GROUP_ORDER][:6]

    if not personas:
        print("No se detectaron personas. Revisa el formato.")
        sys.exit(2)

    # Chequeo de imposibles
    imposibles = [p for p in personas if len(allowed[p]) == 0]
    if imposibles:
        print("Hay personas sin opciones de grupo:", imposibles)
        sys.exit(3)

    # Imprimir participantes únicos antes del reparto
    imprimir_participantes_unicos(personas)

    try:
        asignacion, tamanios, objetivos = asignar(personas, allowed, grupos, seed=None)
    except RuntimeError as e:
        print(str(e))
        sys.exit(4)

    imprimir_resultado(asignacion, tamanios, objetivos, grupos)

if __name__ == "__main__":
    main()
