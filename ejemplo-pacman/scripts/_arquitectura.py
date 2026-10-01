#!/usr/bin/env python3
"""Verifica la forma del sistema: dirección de dependencias, dependencias que faltan, y deriva.

Por qué existe: los gates del método son POR TAREA, y por lo tanto son estructuralmente
ciegos a la deriva arquitectónica. Cada diff se ve bien en aislamiento y el conjunto se
degrada igual. La respuesta publicada son funciones de aptitud arquitectónica como esta,
corriendo sobre el TRONCO.

Tres cosas, y la segunda es la que casi nadie hace:

1. **Divergencias** — una capa importa una capa posterior. Prohibido.
2. **Ausencias** — una dependencia que la arquitectura REQUIERE y el código no tiene. Un
   chequeo de dirección de imports es un modelo de reflexión de una sola relación: ve lo que
   no debería estar, **nunca lo que falta**. Si `servicios` existe y nadie lo llama, o si
   `rutas` habla con la base salteándose `datos`, la dirección sigue siendo correcta y la
   arquitectura ya no es la que dijimos.
3. **Costo de propagación** — qué fracción del sistema alcanza a cada módulo por el cierre
   transitivo de sus dependencias. **No es un gate y el valor absoluto no se compara con
   nada**: la métrica crece cuando hay pocos módulos, y las referencias publicadas (Linux
   5%, Mozilla 17%, Mozilla 3% después de rediseñarse) son sobre miles de archivos. Lo que
   se lee es la **serie**: si sube mientras el proyecto crece, hay deriva.

Las listas de abajo son las del Pacman; la plantilla genérica está en plantillas/.
"""
import ast
import csv
import datetime
import pathlib
import sys

# Las capas del Pacman, de la más baja a la más alta. Cada una puede importar las anteriores,
# nunca las posteriores. Dos o tres ya sirven.
CAPAS = ["laberinto", "entidades", "juego", "render", "__main__"]

# Las dependencias que la arquitectura REQUIERE. Cada par es "este módulo tiene que
# usar aquel". Declarar esto es una afirmación más fuerte que prohibir, así que poné sólo las
# que, si desaparecen, significan que alguien se salteó una capa.
REQUERIDAS = [
    ("juego", "laberinto"),    # el estado de la partida consulta el mapa, no lo reimplementa
    ("render", "laberinto"),   # dibujar usa los caracteres del mapa, no constantes propias
    ("__main__", "juego"),     # el bucle usa el estado del juego
    ("__main__", "render"),    # y dibuja con el renderer
]

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "src" / "pacman"

REGISTRO = pathlib.Path(__file__).resolve().parent.parent / ".metricas" / "arquitectura.csv"


def grafo_de_imports(raiz):
    """Dependencias entre módulos del proyecto, por nombre de módulo.

    Lee imports relativos (`from .otro import X`) y absolutos que apunten a un módulo
    propio. No ve acoplamiento dinámico: en Python, `importlib` y los imports dentro de una
    función no aparecen acá, y eso subestima el acoplamiento real.
    """
    modulos = {p.stem for p in raiz.rglob("*.py") if p.stem != "__init__"}
    grafo = {m: set() for m in modulos}
    for archivo in sorted(raiz.rglob("*.py")):
        if archivo.stem == "__init__":
            continue
        try:
            arbol = ast.parse(archivo.read_text())
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                destino = nodo.module.split(".")[-1]
                if destino in modulos and destino != archivo.stem:
                    grafo[archivo.stem].add(destino)
            elif isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    destino = alias.name.split(".")[-1]
                    if destino in modulos and destino != archivo.stem:
                        grafo[archivo.stem].add(destino)
    return grafo


def alcanzables(grafo, origen):
    """Cierre transitivo desde un módulo, incluyéndolo (es visible para sí mismo)."""
    vistos, pila = {origen}, [origen]
    while pila:
        actual = pila.pop()
        for siguiente in grafo.get(actual, ()):
            if siguiente not in vistos:
                vistos.add(siguiente)
                pila.append(siguiente)
    return vistos


def main():
    if not RAIZ.is_dir():
        print(f"  · no encuentro {RAIZ}: nada que verificar")
        return 0

    grafo = grafo_de_imports(RAIZ)
    if not grafo:
        print(f"  · no hay módulos en {RAIZ}")
        return 0

    nivel = {n: i for i, n in enumerate(CAPAS)}
    problemas = []

    # 1. Divergencias
    for modulo, destinos in grafo.items():
        if modulo not in nivel:
            continue
        for destino in sorted(destinos):
            if destino in nivel and nivel[destino] >= nivel[modulo]:
                problemas.append(f"{modulo} importa {destino}: {modulo} está por debajo "
                                 f"de {destino} en las capas (divergencia)")

    # 2. Ausencias. Se mira el cierre transitivo, no el import directo: pasar por una capa
    #    intermedia declarada cuenta como usarla.
    for origen, destino in REQUERIDAS:
        if origen not in grafo:
            problemas.append(f"la arquitectura requiere que {origen} use {destino}, "
                             f"y {origen} no existe (ausencia)")
        elif destino not in alcanzables(grafo, origen) - {origen}:
            problemas.append(f"{origen} NO usa {destino}, y la arquitectura lo requiere "
                             f"(ausencia): o alguien se salteó una capa, o la capa sobra")

    # 3. Costo de propagación: fracción de la matriz de visibilidad que está en 1.
    #    Informativo, no gate: no hay umbral universal y crece con la centralización.
    n = len(grafo)
    visibles = sum(len(alcanzables(grafo, m)) for m in grafo)
    costo = 100.0 * visibles / (n * n) if n else 0.0

    for p in problemas:
        print(f"  ✗ {p}")
    if not problemas:
        print(f"  ✓ dependencias en una sola dirección: {' → '.join(CAPAS)}")
        if REQUERIDAS:
            print(f"  ✓ están las {len(REQUERIDAS)} dependencias que la arquitectura requiere")
    # El valor absoluto no se compara con nada: la métrica crece cuando hay pocos módulos
    # (un único punto de entrada que ve todo ya aporta n/n²) y las referencias publicadas
    # —Linux 5%, Mozilla 17%, Mozilla 3% después de su rediseño— son sobre miles de
    # archivos. Lo que se lee es la SERIE: si sube mientras el proyecto crece, hay deriva.
    print(f"  · costo de propagación: {costo:.1f}% sobre {n} módulos"
          + (" — con tan pocos módulos el número no se compara con nada;"
             " sirve la serie en .metricas/arquitectura.csv" if n < 20 else ""))

    # El número solo no dice nada; la serie sí. Por eso se registra.
    try:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not REGISTRO.exists()
        with REGISTRO.open("a", newline="") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(["fecha", "modulos", "costo_propagacion", "divergencias_y_ausencias"])
            w.writerow([datetime.datetime.now(datetime.timezone.utc).strftime("%FT%TZ"),
                        n, f"{costo:.1f}", len(problemas)])
    except OSError:
        pass

    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
