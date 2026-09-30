#!/usr/bin/env python3
"""Verifica que las dependencias entre módulos vayan en una sola dirección.

Por qué existe: los gates del método son POR TAREA, y por lo tanto son estructuralmente
ciegos a la deriva arquitectónica. Cada diff se ve bien en aislamiento y el conjunto se
degrada igual — es la crítica mejor documentada al desarrollo con agentes, y la respuesta
publicada son funciones de aptitud arquitectónica como esta, corriendo sobre el TRONCO.

Es una plantilla: cambiá CAPAS por las de tu proyecto. La regla es una sola, y alcanza
para atrapar el 90% de la deriva: **una capa sólo puede importar capas anteriores.**
"""
import ast
import pathlib
import sys

# ADAPTAR: tus capas, de la más baja a la más alta. Cada una puede importar las anteriores,
# nunca las posteriores. Dos o tres capas ya sirven; no hace falta modelar todo.
CAPAS = ["datos", "servicios", "rutas"]
# ADAPTAR: dónde viven los módulos.
RAIZ = pathlib.Path(__file__).resolve().parent.parent / "src"

nivel = {n: i for i, n in enumerate(CAPAS)}
problemas = []

for archivo in sorted(RAIZ.glob("*.py")):
    modulo = archivo.stem
    if modulo not in nivel:
        continue
    arbol = ast.parse(archivo.read_text())
    for nodo in ast.walk(arbol):
        # Sólo los imports relativos al paquete: `from .otro import X`
        if isinstance(nodo, ast.ImportFrom) and nodo.level and nodo.module in nivel:
            if nivel[nodo.module] >= nivel[modulo]:
                problemas.append(
                    f"{modulo}.py importa {nodo.module} (línea {nodo.lineno}): "
                    f"{modulo} está por debajo de {nodo.module} en las capas"
                )

if problemas:
    for p in problemas:
        print(f"  ✗ {p}")
    sys.exit(1)
print(f"  ✓ dependencias en una sola dirección: {' → '.join(CAPAS)}")
