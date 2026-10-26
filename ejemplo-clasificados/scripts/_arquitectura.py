#!/usr/bin/env python3
"""Las capas de clasificados: app/datos → app/servicios → app/rutas.

El juicio lo hace `scripts/_arquitectura_motor.py`, del método.

Este archivo es config: tres declaraciones y nada más. Está separado del juicio porque el
juicio copiado derivó — el 2026-10-25 el mismo arreglo hubo que escribirlo en tres copias
idénticas, y antes de eso el chequeo estuvo un mes mapeando cero módulos e imprimiendo ✓.
El por qué de cada cosa que verifica está en el motor.

"""
import os
import pathlib
import subprocess
import sys

# Las capas, tal como se cerraron en el encargo, de la más baja a la más alta. Cada una puede importar las anteriores y
# a sus compañeras de capa, nunca las posteriores. Dos o tres ya sirven. Se reconocen por la
# RUTA de cada módulo, así que sirven las dos formas: un directorio por capa
# (`src/datos/ads.py`) o un archivo por capa (`src/datos.py`).
CAPAS = ["datos", "servicios", "rutas"]

# Las dependencias que la arquitectura REQUIERE. Cada par es "este módulo tiene que
# usar aquel". Declarar esto es una afirmación más fuerte que prohibir, así que poné sólo las
# que, si desaparecen, significan que alguien se salteó una capa.
REQUERIDAS = [
    ("servicios", "datos"),   # la lógica usa la capa de datos
    ("rutas", "servicios"),   # los endpoints no hablan con datos directamente
]

# Dónde viven los módulos.
RAIZ = pathlib.Path(__file__).resolve().parent.parent / "backend" / "app"

REGISTRO = pathlib.Path(__file__).resolve().parent.parent / ".metricas" / "arquitectura.csv"


def motor_del_metodo():
    """El motor, en el mismo orden en que el gate busca los chequeos compartidos: `$AGENTES`
    primero, después la raíz del repo, y por último `scripts/` de este proyecto.

    Si no está, esto da ROJO y lo dice. El antecedente es de este repo: el único eslabón de
    la cadena de chequeos compartidos que fallaba ABIERTO no imprimía nada, no sumaba a
    fallos ni a vacíos, y el veredicto salía «GATE VERDE» limpio.
    """
    candidatos = []
    if os.environ.get("AGENTES"):
        candidatos.append(pathlib.Path(os.environ["AGENTES"]) / "scripts")
    try:
        tope = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        tope = ""
    if tope:
        candidatos.append(pathlib.Path(tope) / "scripts")
    candidatos.append(pathlib.Path(__file__).resolve().parent)
    for c in candidatos:
        if (c / "_arquitectura_motor.py").is_file():
            sys.path.insert(0, str(c))
            import _arquitectura_motor
            return _arquitectura_motor
    print("  ✗ falta scripts/_arquitectura_motor.py: el chequeo de arquitectura no puede "
          "correr, así que nadie verificó la forma del sistema")
    print("     Lo provee el método; exportá $AGENTES. Esto es del método, no del código "
          "juzgado. Buscado en: " + " · ".join(str(c) for c in candidatos))
    return None


if __name__ == "__main__":
    motor = motor_del_metodo()
    sys.exit(1 if motor is None else motor.verificar(CAPAS, REQUERIDAS, RAIZ, REGISTRO))
