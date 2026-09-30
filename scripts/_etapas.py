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
    resto = " ".join(celdas[2:])          # dependencias y archivos, sin el título
    deps = set(re.findall(r"T\d+", resto))
    deps.discard(tid)
    archivos = {a for a in re.findall(r"`([^`]+)`", resto) if "." in a or "/" in a}
    hecha = "✅" in linea
    tareas[tid] = {"deps": deps, "archivos": archivos, "hecha": hecha}

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
