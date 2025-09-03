#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
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

# ===================== Streamlit App =====================

def main():
    st.title("🍽️ Sorteo de Comidas")
    st.markdown("### Organiza automáticamente a las personas en grupos de comidas y cenas")
    
    # Explicación del formato
    with st.expander("📝 Formato del texto de entrada"):
        st.markdown("""
        **Formato esperado:**
        
        ```
        TODO:
        - Persona que puede ir a cualquier grupo
        - Otra persona flexible
        
        - Comida 9
        - Persona específica para comida del día 9
        - Otra persona para comida del día 9
        
        - Cena 9
        - Persona específica para cena del día 9
        
        - Comida 10
        - Persona para comida del día 10
        ...
        ```
        
        **Notas:**
        - Las personas en "TODO:" pueden asignarse a cualquier grupo
        - Las personas bajo encabezados específicos solo van a esos grupos
        - Si una persona aparece en varios grupos, puede ir a cualquiera de esos
        """)
    
    # Área de texto para input
    texto_input = st.text_area(
        "Pega aquí el mensaje con los participantes:",
        height=300,
        placeholder="TODO:\n- Juan Pérez\n- María García\n\n- Comida 9\n- Ana López\n- Carlos Ruiz\n\n- Cena 9\n- Laura Martín\n..."
    )
    
    # Opciones avanzadas
    with st.expander("⚙️ Opciones avanzadas"):
        seed_input = st.text_input(
            "Semilla para el sorteo (opcional):", 
            help="Si introduces la misma semilla, obtendrás siempre el mismo resultado. Déjalo vacío para resultados aleatorios."
        )
        max_intentos = st.slider("Máximo número de intentos:", 500, 5000, 2000)
    
    # Botón para ejecutar sorteo
    if st.button("🎲 Realizar Sorteo", type="primary"):
        if not texto_input.strip():
            st.error("❌ Por favor, introduce el texto con los participantes.")
            return
            
        try:
            # Procesamiento
            todo_any, group_lists = parse_message(texto_input)
            personas, allowed, _ = build_eligibilities(todo_any, group_lists)
            
            # Aseguramos exactamente los 6 grupos objetivo en orden
            grupos = [g for g in GROUP_ORDER][:6]
            
            if not personas:
                st.error("❌ No se detectaron personas. Revisa el formato del texto.")
                return
                
            # Chequeo de personas sin opciones
            imposibles = [p for p in personas if len(allowed[p]) == 0]
            if imposibles:
                st.error(f"❌ Hay personas sin opciones de grupo: {', '.join(imposibles)}")
                return
            
            # Configurar semilla - siempre generar una para transparencia
            if seed_input.strip():
                try:
                    seed = int(seed_input.strip())
                    seed_type = "manual"
                except ValueError:
                    seed = hash(seed_input.strip())
                    seed_type = "manual"
            else:
                # Generar semilla automática basada en timestamp para reproducibilidad
                import time
                seed = int(time.time() * 1000) % 1000000  # Últimos 6 dígitos del timestamp
                seed_type = "automática"
            
            # Realizar asignación
            with st.spinner("🔄 Calculando el mejor reparto..."):
                asignacion, tamanios, objetivos = asignar(personas, allowed, grupos, seed=seed, max_intentos=max_intentos)
            
            # Mostrar resultados
            st.success("✅ ¡Sorteo completado!")
            
            # Mostrar semilla utilizada SIEMPRE
            if seed_type == "manual":
                st.info(f"🌱 **Semilla utilizada:** {seed} (introducida manualmente)")
            else:
                st.info(f"🌱 **Semilla utilizada:** {seed} (generada automáticamente - usa esta semilla para repetir el mismo resultado)")
            
            # Participantes únicos
            st.subheader("👥 Participantes detectados")
            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric("Total personas", len(personas))
            with col2:
                st.write(", ".join(sorted(personas, key=lambda s: s.lower())))
            
            # Resumen de tamaños
            st.subheader("📊 Resumen de grupos")
            cols = st.columns(len(grupos))
            for i, (grupo, size, objetivo) in enumerate(zip(grupos, tamanios, objetivos)):
                with cols[i]:
                    delta = size - objetivo
                    delta_str = f"{delta:+d}" if delta != 0 else "✓"
                    st.metric(
                        label=grupo,
                        value=f"{size} personas",
                        delta=delta_str if delta != 0 else None
                    )
            
            # Asignaciones por grupo
            st.subheader("🍽️ Asignaciones finales")
            
            por_grupo = defaultdict(list)
            for persona, g in asignacion.items():
                por_grupo[g].append(persona)
            
            # Mostrar en columnas
            cols = st.columns(2)
            for i, grupo in enumerate(grupos):
                with cols[i % 2]:
                    st.write(f"**{grupo}**")
                    for nombre in sorted(por_grupo[grupo], key=lambda s: s.lower()):
                        st.write(f"• {nombre}")
                    st.write("")
            
            # Estadísticas adicionales
            with st.expander("📈 Estadísticas del sorteo"):
                desviacion = sum(abs(tamanios[i] - objetivos[i]) for i in range(len(grupos)))
                diferencia_max = max(tamanios) - min(tamanios)
                st.write(f"**Desviación total de objetivos:** {desviacion}")
                st.write(f"**Diferencia entre grupo más grande y más pequeño:** {diferencia_max}")
                st.write(f"**Semilla utilizada:** {seed}")
            
            # Resultados para copiar (siempre visible después del sorteo)
            st.divider()
            st.subheader("📋 Resultados para copiar")
            
            # Generar texto completo de resultados
            resultado_texto = "🍽️ RESULTADOS DEL SORTEO DE COMIDAS\n"
            resultado_texto += "=" * 50 + "\n"
            resultado_texto += f"🌱 Semilla utilizada: {seed}\n"
            resultado_texto += "=" * 50 + "\n\n"
            
            resultado_texto += f"👥 PARTICIPANTES: {len(personas)} personas\n"
            resultado_texto += f"Participantes: {', '.join(sorted(personas, key=lambda s: s.lower()))}\n\n"
            
            resultado_texto += "📊 RESUMEN DE GRUPOS:\n"
            for grupo, size, objetivo in zip(grupos, tamanios, objetivos):
                delta = size - objetivo
                delta_str = f" ({delta:+d})" if delta != 0 else " (✓)"
                resultado_texto += f"• {grupo}: {size} personas{delta_str}\n"
            resultado_texto += "\n"
            
            resultado_texto += "🍽️ ASIGNACIONES FINALES:\n"
            resultado_texto += "-" * 30 + "\n"
            for grupo in grupos:
                resultado_texto += f"\n{grupo.upper()}:\n"
                for nombre in sorted(por_grupo[grupo], key=lambda s: s.lower()):
                    resultado_texto += f"  • {nombre}\n"
            
            resultado_texto += "\n" + "=" * 50 + "\n"
            resultado_texto += f"📈 Estadísticas: Desviación={desviacion}, Diferencia máx={diferencia_max}"
            
            # Mostrar el texto en un área de texto copiable
            st.info("💡 **Instrucciones para móvil:** Mantén presionado sobre el texto de abajo, selecciona todo y copia.")
            st.text_area(
                "Selecciona todo el texto y copia con Ctrl+C (o mantén presionado en móvil):",
                value=resultado_texto,
                height=400,
                help="En móvil: mantén presionado sobre el texto, selecciona todo y copia"
            )
                    
        except Exception as e:
            st.error(f"❌ Error durante el sorteo: {str(e)}")

if __name__ == "__main__":
    main()
