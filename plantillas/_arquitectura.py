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

ADAPTAR: las tres listas de abajo y RAIZ.
"""
import ast
import csv
import datetime
import pathlib
import sys

# ADAPTAR: tus capas, de la más baja a la más alta. Cada una puede importar las anteriores,
# nunca las posteriores. Dos o tres ya sirven.
CAPAS = ["datos", "servicios", "rutas"]

# ADAPTAR: las dependencias que la arquitectura REQUIERE. Cada par es "este módulo tiene que
# usar aquel". Declarar esto es una afirmación más fuerte que prohibir, así que poné sólo las
# que, si desaparecen, significan que alguien se salteó una capa.
REQUERIDAS = [
    ("servicios", "datos"),   # la lógica usa la capa de datos
    ("rutas", "servicios"),   # los endpoints no hablan con datos directamente
]

# ADAPTAR: dónde viven los módulos.
RAIZ = pathlib.Path(__file__).resolve().parent.parent / "src"

REGISTRO = pathlib.Path(__file__).resolve().parent.parent / ".metricas" / "arquitectura.csv"


def modulos_del_proyecto(raiz):
    """Un nodo por archivo, identificado por su RUTA relativa sin `.py` (`datos/ads`).

    Antes el nodo era el nombre del archivo a secas, y eso tenía dos consecuencias, las dos
    medidas en clasificados el 2026-10-25:

      · `datos/ads.py` y `servicios/ads.py` eran el MISMO nodo. La arista entre ellos es un
        lazo sobre sí mismo, se descarta, y una violación de capa entre los dos no se podía
        ver por construcción.
      · ningún nombre de archivo coincidía con una capa (`ads`, `conexion`, `favorites`),
        así que la cobertura del mapeo era 0%: el chequeo no miraba un solo módulo y
        imprimía ✓ igual.
    """
    nodos = {}
    for archivo in sorted(raiz.rglob("*.py")):
        if archivo.stem == "__init__":
            continue
        nodos["/".join(archivo.relative_to(raiz).with_suffix("").parts)] = archivo
    return nodos


def indice_por_sufijo(nodos):
    """De cada sufijo punteado de una ruta al nodo que nombra: `datos.ads` → `datos/ads`."""
    indice = {}
    for nid in nodos:
        partes = nid.split("/")
        for i in range(len(partes)):
            indice.setdefault(".".join(partes[i:]), set()).add(nid)
    return indice


def destino_de(punteado, indice):
    """El nodo que nombra un import, por el sufijo más largo que casa SIN ambigüedad.

    `from backend.app.datos.favorites import toggle_favorite` entra acá como
    `backend.app.datos.favorites` y sale como `datos/favorites`. Un sufijo que casa con dos
    nodos no decide nada y se descarta: preferimos no ver una arista antes que inventarla.
    """
    partes = punteado.split(".")
    for i in range(len(partes)):
        candidatos = indice.get(".".join(partes[i:]))
        if candidatos and len(candidatos) == 1:
            return next(iter(candidatos))
    return None


def grafo_de_imports(raiz):
    """Dependencias entre módulos del proyecto, por ruta relativa.

    Lee imports relativos (`from .otro import X`, `from ..capa.otro import X`) y absolutos
    que apunten a un módulo propio, en las dos formas: `from capa.modulo import simbolo` y
    `from capa import modulo`. No ve acoplamiento dinámico: en Python, `importlib` y los
    imports dentro de una función no aparecen acá, y eso subestima el acoplamiento real
    (clasificados usa `importlib` en `main.py`).
    """
    nodos = modulos_del_proyecto(raiz)
    indice = indice_por_sufijo(nodos)
    grafo = {nid: set() for nid in nodos}
    for nid, archivo in nodos.items():
        try:
            arbol = ast.parse(archivo.read_text())
        except SyntaxError:
            continue
        paquete = nid.split("/")[:-1]
        for nodo in ast.walk(arbol):
            punteados = []
            if isinstance(nodo, ast.ImportFrom):
                if nodo.level:
                    # `level` 1 es el paquete del propio archivo, 2 el de arriba, etc.
                    corte = len(paquete) - (nodo.level - 1)
                    if corte < 0:
                        continue
                    base = paquete[:corte]
                else:
                    base = []
                camino = base + (nodo.module.split(".") if nodo.module else [])
                if not camino:
                    continue
                # Las dos formas: `from capa.modulo import simbolo` nombra al módulo en
                # `module`, y `from capa import modulo` lo nombra en el alias.
                punteados.append(".".join(camino))
                punteados += [".".join(camino + [a.name]) for a in nodo.names]
            elif isinstance(nodo, ast.Import):
                punteados += [a.name for a in nodo.names]
            for punteado in punteados:
                destino = destino_de(punteado, indice)
                if destino and destino != nid:
                    grafo[nid].add(destino)
    return grafo


def capa_de(nid, nivel):
    """La capa de un módulo: la primera parte de su ruta que esté declarada en CAPAS.

    Incluye el nombre del archivo, así que un proyecto con un archivo plano por capa
    —`src/pacman/laberinto.py`, que es la forma del ejemplo del Pacman— mapea igual que
    con un directorio por capa.
    """
    for parte in nid.split("/"):
        if parte in nivel:
            return parte
    return None


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
        # No es un ⊘: una ruta declarada que no existe es un error de configuración MEDIDO,
        # y mientras esté así el chequeo no va a verificar nada nunca. Antes imprimía
        # «nada que verificar» con un · y devolvía 0: el gate salía «GATE VERDE» limpio.
        print(f"  ✗ RAIZ apunta a {RAIZ} y ese directorio no existe: ADAPTALA, o el "
              f"chequeo de arquitectura no mira nada")
        return 1

    grafo = grafo_de_imports(RAIZ)
    if not grafo:
        print(f"  ⊘ no hay ningún módulo en {RAIZ} todavía — no pudo verificarse")
        return 0

    nivel = {n: i for i, n in enumerate(CAPAS)}
    capa = {nid: capa_de(nid, nivel) for nid in grafo}
    problemas = []

    # Cobertura del mapeo. Una ausencia es ambigua por construcción: puede ser que falte la
    # dependencia, o que falte declarar el módulo. En los dos únicos estudios longitudinales
    # publicados, el 100% de las ausencias resultaron artefactos del mapeo. Por eso nunca se
    # reporta una ausencia sin esto en la misma salida.
    sin_mapear = sorted(nid for nid in grafo if capa[nid] is None)
    cobertura = 100.0 * (len(grafo) - len(sin_mapear)) / len(grafo)

    # Cero módulos mapeados es el caso que tapó el defecto: con el bucle de divergencias sin
    # una sola iteración, NO FALLAR no significa nada. Rojo, y no ⊘, por lo mismo que arriba:
    # está medido que las capas declaradas no son las de este proyecto.
    if sin_mapear and len(sin_mapear) == len(grafo):
        print(f"  ✗ ninguno de los {len(grafo)} módulos de {RAIZ.name} cae en una capa "
              f"declarada ({' → '.join(CAPAS)}): con cobertura 0% este chequeo no puede "
              f"fallar, y entonces su verde no dice nada")
        print(f"     · módulos: {' '.join(sin_mapear[:12])}"
              + (" …" if len(sin_mapear) > 12 else ""))
        print( "     Declará en CAPAS los nombres que existen —el directorio de cada capa, o "
               "el archivo si tenés uno por capa—, o sacá scripts/_arquitectura.py: un "
               "chequeo que no puede fallar es peor que ninguno.")
        return 1

    # Una capa declarada en REQUERIDAS y ausente de CAPAS es un par muerto: no se puede
    # verificar ni hoy ni nunca, y el ⊘ lo contaría como «la capa todavía está vacía».
    for origen, destino in REQUERIDAS:
        for nombre in (origen, destino):
            if nombre not in nivel:
                problemas.append(f"REQUERIDAS nombra la capa «{nombre}», que no está en "
                                 f"CAPAS: ese par no se puede verificar nunca")

    # 1. Divergencias. Una capa puede importar las ANTERIORES y a sus propios compañeros de
    #    capa; lo prohibido es importar una posterior. El `>=` de la primera versión no
    #    distinguía «la misma capa» de «una capa posterior», y con los módulos por nombre de
    #    archivo eso no se notaba: dos módulos de la misma capa eran el mismo nodo. Con las
    #    rutas, `datos/ads → datos/conexion` es una arista real y perfectamente legal.
    aristas_entre_capas = 0
    for modulo, destinos in grafo.items():
        if capa[modulo] is None:
            continue
        for destino in sorted(destinos):
            if capa[destino] is None or capa[destino] == capa[modulo]:
                continue
            aristas_entre_capas += 1
            if nivel[capa[destino]] > nivel[capa[modulo]]:
                problemas.append(f"{modulo} importa {destino}: {capa[modulo]} está por "
                                 f"debajo de {capa[destino]} en las capas (divergencia)")

    # 2. Ausencias. Se mira el cierre transitivo, no el import directo: pasar por una capa
    #    intermedia declarada cuenta como usarla.
    miembros = {c: sorted(nid for nid in grafo if capa[nid] == c) for c in CAPAS}
    vacuos = []
    for origen, destino in REQUERIDAS:
        if origen not in nivel or destino not in nivel:
            continue
        # Una capa que todavía no tiene un módulo no es una ausencia: es una capa que no
        # llegó. El proyecto se construye por etapas y la arquitectura recién está completa
        # al final, así que exigir el grafo entero en cada merge bloquea todos los merges
        # tempranos. Pasó: integrar T02 —que crea `datos/conexion.py`— daba rojo porque
        # `servicios` y `rutas` todavía no tenían un solo módulo.
        #
        # No se calla: se informa como ⊘, que es lo que es —no pudo verificarse—, y el gate
        # lo cuenta como vacío. Un chequeo que no pudo correr no es un chequeo que pasó.
        if not miembros[origen] or not miembros[destino]:
            falta = origen if not miembros[origen] else destino
            vacuos.append(f"la arquitectura requiere que {origen} use {destino}, y {falta} "
                          f"todavía no tiene ningún módulo")
            continue
        alcanzado = set()
        for m in miembros[origen]:
            alcanzado |= alcanzables(grafo, m)
        if not alcanzado & set(miembros[destino]):
            problemas.append(f"{origen} NO usa {destino}, y la arquitectura lo requiere "
                             f"(ausencia): o alguien se salteó una capa, o la capa sobra")

    # 3. Costo de propagación: fracción de la matriz de visibilidad que está en 1.
    #    Informativo, no gate: no hay umbral universal y crece con la centralización.
    n = len(grafo)
    visibilidad = {m: alcanzables(grafo, m) for m in grafo}
    visibles = sum(len(v) for v in visibilidad.values())
    costo = 100.0 * visibles / (n * n) if n else 0.0

    # El componente fuertemente conexo más grande: módulos que se alcanzan mutuamente, o sea
    # un ciclo. Es la cantidad estable e interpretable, y la que explica el costo: medido,
    # agregar UNA arista de vuelta movió el costo de 53% a 90% y el SCC de 36 a 180 módulos.
    # El costo de propagación es casi un detector de ciclos disfrazado de gradiente.
    mayor_ciclo = max((len({o for o in grafo if m in visibilidad[o]} & visibilidad[m])
                       for m in grafo), default=0)

    if sin_mapear:
        print(f"  · cobertura del mapeo: {cobertura:.0f}% — sin declarar en CAPAS: "
              f"{' '.join(sin_mapear)}")
        if any("ausencia" in p for p in problemas):
            print("    Con cobertura incompleta, una ausencia puede ser del mapeo y no del código.")
    for p in problemas:
        print(f"  ✗ {p}")
    for v in vacuos:
        print(f"  ⊘ {v} — no pudo verificarse")
    if not problemas:
        # El ✓ dice CUÁNTAS aristas entre capas se miraron. Sin ese número, «no encontré una
        # divergencia» y «no miré una sola arista» se imprimen igual, que es exactamente cómo
        # este chequeo estuvo muerto un mes.
        if aristas_entre_capas:
            print(f"  ✓ dependencias en una sola dirección: {' → '.join(CAPAS)}"
                  f" ({aristas_entre_capas} arista/s entre capas)")
        else:
            print(f"  · todavía no hay una sola arista entre capas distintas: la dirección "
                  f"no se puede contradecir, así que tampoco se verificó")
        verificadas = len([1 for o, d in REQUERIDAS if o in nivel and d in nivel]) - len(vacuos)
        if verificadas > 0:
            print(f"  ✓ están las {verificadas} dependencias requeridas que ya se pueden "
                  f"verificar")
        elif REQUERIDAS:
            print(f"  · ninguna de las {len(REQUERIDAS)} dependencias requeridas se puede "
                  f"verificar todavía: las capas están vacías")
    # El valor absoluto no se compara con nada: la métrica crece cuando hay pocos módulos
    # (un único punto de entrada que ve todo ya aporta n/n²) y las referencias publicadas
    # —Linux 5%, Mozilla 17%, Mozilla 3% después de su rediseño— son sobre miles de
    # archivos. Lo que se lee es la SERIE: si sube mientras el proyecto crece, hay deriva.
    print(f"  · costo de propagación: {costo:.1f}% sobre {n} módulos"
          + (" — con tan pocos módulos no se compara con nada; sirve la serie"
             if n < 20 else ""))
    if mayor_ciclo > 1:
        print(f"  · ciclo más grande: {mayor_ciclo} módulos que se alcanzan mutuamente"
              f" — es lo que explica el costo, y lo que conviene mirar")
    else:
        print("  · sin ciclos entre módulos")

    # El número solo no dice nada; la serie sí. Por eso se registra.
    try:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not REGISTRO.exists()
        with REGISTRO.open("a", newline="") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(["fecha", "modulos", "costo_propagacion", "mayor_ciclo",
                            "cobertura_mapeo", "divergencias_y_ausencias"])
            w.writerow([datetime.datetime.now(datetime.timezone.utc).strftime("%FT%TZ"),
                        n, f"{costo:.1f}", mayor_ciclo, f"{cobertura:.0f}", len(problemas)])
    except OSError:
        pass

    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
