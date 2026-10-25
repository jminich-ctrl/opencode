#!/usr/bin/env python3
"""¿El test obliga un contrato que el enunciado no declara?

El chequeo de columnas pregunta si el ENUNCIADO pide algo que el esquema no tiene. Este es
el mismo cruce en la otra dirección: si el TEST obliga claves que el enunciado no nombra, el
contrato lo inventó el test — y como el test se acepta primero y después juzga a toda
implementación, ese invento queda obligado para siempre.

Medido el 2026-10-25 en T20 de clasificados, con su test YA ACEPTADO en el tronco. Su
contrato dice:

    def send_message(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
        \"\"\"Inserta un mensaje y devuelve el registro creado.\"\"\"

`-> dict` y nada más. El test exige DIEZ claves en tres convenciones a la vez —`de_usuario_id`
y `a_usuario_id` como la tabla, `other_user_id` y `last_message` en inglés,
`fecha_ultimo_mensaje` y `ultimo_mensaje` en castellano— y ninguna está en el enunciado. Dos
corridas de la etapa de implementación fallaron adivinando el mapeo: una devolvió
`other_user_id` donde el test pedía `otro_usuario_id`, que es una ONCEAVA variante.

El gate lo aceptó porque sus cinco pasos preguntan si el test DISTINGUE, no si lo que obliga
está declarado. Es el mismo molde del test envenenado de T28, que clavaba `categoria`: un
test aceptado que obliga algo que el plan no dice.

Se cruzan TRES fuentes, y las tres hacen falta. Una clave que el enunciado no nombra puede
ser perfectamente legítima si es una columna —el test lee la fila que la base devuelve— así
que lo que se marca es la clave que NO está en el enunciado Y TAMPOCO es columna de ninguna
tabla: a ésa no la declaró nadie más que el test.

La primera versión de este chequeo exigía que el enunciado declarara CERO claves, por miedo
al ruido, y con eso NO atrapaba el caso que lo motivó: T20 declara 8 de 15. Las 7 que falta
son exactamente las del contrato inventado.

  python3 scripts/_contrato.py <archivo-de-test> <archivo-de-tarea> [proyecto]
"""
import ast
import os
import pathlib
import subprocess
import re
import sys

# Claves de acceso a un dict en el test: `x["clave"]`, y las que se afirman presentes.
def claves_que_obliga(texto):
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return set()
    claves = set()
    for n in ast.walk(arbol):
        # `algo["clave"]`
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str):
            claves.add(n.slice.value)
        # NO se usa `assert "clave" in algo`: ese `algo` puede ser un set, una lista o
        # cualquier colección, y entonces lo de la izquierda no es la clave de un contrato.
        # Medido el 2026-10-25: el test de T06b siembra módulos de prueba y afirma
        # `"prueba_router" in mod.app.state.routers_montados` — nombres de módulo, no claves,
        # y el chequeo los marcaba como contrato inventado. Se pierde algún `in` legítimo
        # sobre un dict, y es el precio de no morder al test honesto.
        # `.get("clave")`
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            claves.add(n.args[0].value)
        # Las claves de un DICCIONARIO LITERAL, que es la forma que de verdad usan estos
        # tests: construyen el dict que esperan —o el que el mock de `fetchall` devuelve— y
        # comparan. Mirando sólo los accesos `x["k"]`, el extractor no veía una sola clave en
        # el test de T20, que tiene diez. Y las del mock son las que CLAVAN los alias que el
        # SQL de la implementación tiene que devolver: el mismo mecanismo por el que el test
        # envenenado de T28 obligaba la columna `categoria`.
        if isinstance(n, ast.Dict):
            for k in n.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    claves.add(k.value)
    # Sólo las que PARECEN claves de un contrato: identificadores, no rutas ni frases.
    return {c for c in claves if re.fullmatch(r"[a-z][a-z0-9_]{2,}", c)}


def columnas_del_esquema(proyecto):
    """Las columnas que crean las migraciones, por la interfaz que `coherencia.py` ya expone.

    `coherencia.py --columnas` existe desde el 2026-10-24 y las imprime por tabla. Mi primera
    versión recortaba su árbol sintáctico para reusar la función sin ejecutar el módulo:
    frágil, y además devolvía un set vacío envuelto en `except Exception` — o sea FALLANDO
    ABIERTO, que es el defecto que este método viene cerrando todo el día. Con cero columnas
    leídas, este chequeo marcaba `anuncio_id`, que SÍ es columna de `mensajes`.

    Devuelve None cuando no pudo leer el esquema, y el llamador no afirma nada: un chequeo
    que cruza tres fuentes y perdió una no puede dar un veredicto.
    """
    aqui = pathlib.Path(__file__).resolve().parent
    r = subprocess.run([sys.executable, str(aqui / "coherencia.py"), "--columnas"],
                       cwd=proyecto, capture_output=True, text=True,
                       env={**os.environ, "PROYECTO": "."})
    if r.returncode != 0:
        return None
    cols = set()
    for linea in r.stdout.split("\n"):
        if ":" not in linea:
            continue
        cols.update(c.strip() for c in linea.split(":", 1)[1].split(",") if c.strip())
    return cols or None


def main(ruta_test, ruta_tarea, proyecto="."):
    test = pathlib.Path(ruta_test)
    tarea = pathlib.Path(ruta_tarea)
    # Un archivo que no está NO es «nada que marcar»: es que no se pudo cruzar, y devolver 0
    # sería decir que el contrato está declarado sin haberlo mirado. Medido: con la ruta de la
    # tarea mal armada —lo más fácil de romper al enganchar esto en otro script— el chequeo
    # devolvía 0 y nadie se enteraba. Es el defecto que este método viene cerrando todo el
    # día, y éste es el último chequeo que escribí hoy.
    faltan = [str(f) for f in (test, tarea) if not f.exists()]
    if faltan:
        print("  ⊘ no pude cruzar el contrato: no encuentro " + ", ".join(faltan))
        print("     Sin el test o sin el enunciado, este chequeo no afirma nada.")
        return 2
    claves = claves_que_obliga(test.read_text())
    if not claves:
        return 0
    enunciado = tarea.read_text()
    # Nombradas en el enunciado, en cualquier parte: entre backticks, en una firma, en prosa.
    # No se exige una forma porque lo que se mide es si la PALABRA está, no cómo se escribió.
    columnas = columnas_del_esquema(proyecto)
    if columnas is None:
        print("  ⊘ no pude leer las columnas del esquema: este chequeo cruza el test, el")
        print("     enunciado y el esquema, y sin una de las tres no afirma nada.")
        return 2
    inventadas = sorted(c for c in claves
                        if not re.search(rf"\b{re.escape(c)}\b", enunciado)
                        and c not in columnas)
    if not inventadas:
        return 0
    print(f"  ✗ el test obliga {len(inventadas)} clave(s) que no declara el enunciado"
          f" ni son columna de ninguna tabla:")
    print("     " + ", ".join(inventadas[:12]))
    print("     El contrato lo está inventando el test, y una vez aceptado lo obliga para")
    print("     siempre: toda implementación tiene que adivinar ese mapeo exacto. Lo declara")
    print(f"     el enunciado ({tarea.name}), no el que escribe el test.")
    return 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]) if len(sys.argv) > 2 else 0)
