#!/usr/bin/env python3
"""Deduce las etapas de un PLAN.md a partir de la tabla de tareas y sus dependencias.

Imprime una etapa por línea: las tareas que se pueden lanzar juntas, separadas por espacio.

Dos reglas, las mismas que el método pide a mano:
  1. una tarea espera a sus dependencias;
  2. dos tareas que escriben el mismo archivo NO van en la misma etapa, aunque sus
     dependencias lo permitan (es el error más común al paralelizar).
"""
import os
import re
import sys
from collections import OrderedDict

texto = open(os.environ.get("PLAN", "PLAN.md")).read()

tareas = OrderedDict()
# Una fila entera de la tabla, para no perder la columna de estado (donde va el ✅).
for linea in re.findall(r"^\|\s*T\d+\s*\|.*$", texto, re.M):
    celdas = [c.strip() for c in linea.strip("|").split("|")]
    tid = celdas[0]
    # Un plan puede tener más de una tabla indexada por tarea (la de tareas y, por ejemplo,
    # la de tests que hay que escribir). Sin esto la segunda pisaba a la primera y todas
    # las tareas quedaban sin dependencias: ocho tareas en una sola etapa, en paralelo.
    if tid in tareas or len(celdas) < 4:
        continue
    # Por posición, no por texto suelto: | # | Tarea | Depende de | Archivos | Estado |
    deps = set(re.findall(r"T\d+", celdas[2]))
    deps.discard(tid)
    # Con o sin backticks: el plan de Pacman los usaba y el de clasificados no, y por eso
    # los choques de archivo no se detectaban — dos tareas que escriben el mismo archivo
    # quedaban en la misma etapa, que es justo lo que este script existe para evitar.
    archivos = {a.strip(" `") for a in re.split(r"[,\s]+", celdas[3]) if "." in a or "/" in a}
    archivos = {a for a in archivos if a}
    hecha = "✅" in linea
    tareas[tid] = {"deps": deps, "archivos": archivos, "hecha": hecha}

if not tareas:
    # No hay tabla de tareas que leer: es un problema del plan, y quien nos llama tiene
    # que poder distinguirlo de "el plan está terminado".
    sys.exit(2)

# Una tarea sin archivos detectados es invisible para la regla del choque: puede salir
# en paralelo con otra que escribe lo mismo. No es un error del plan necesariamente —una
# tarea puede no declarar archivos— pero es la única forma de enterarse de que la regla
# no se está aplicando. Nos pasó: el plan listaba los archivos sin backticks, este script
# no los veía, y dos tareas sobre el mismo archivo quedaron en la misma etapa.
sin_archivos = [k for k, v in tareas.items() if not v["archivos"]]
if sin_archivos:
    print(f"⚠ sin archivos declarados, no se les puede aplicar la regla del choque: "
          f"{' '.join(sin_archivos)}", file=sys.stderr)

pendientes = OrderedDict((k, v) for k, v in tareas.items() if not v["hecha"])
if not pendientes:
    sys.exit(0)

listas = {k for k, v in tareas.items() if v["hecha"]}
while pendientes:
    etapa, ocupados = [], set()
    for tid, t in list(pendientes.items()):
        if not t["deps"] <= listas:
            continue
        if t["archivos"] & ocupados:       # choque de archivo: va a la etapa siguiente
            continue
        etapa.append(tid)
        ocupados |= t["archivos"]
    if not etapa:                          # dependencia circular o hacia una tarea inexistente
        print(" ".join(pendientes), file=sys.stderr)
        sys.exit("✗ no pude ordenar estas tareas: revisá sus dependencias en el plan")
    print(" ".join(etapa))
    for tid in etapa:
        listas.add(tid)
        pendientes.pop(tid)
