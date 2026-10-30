#!/usr/bin/env python3
"""Las réplicas de los modelos que ESTE equipo usa, leídas de la API y cruzadas con la config.

Códigos: 0 todas puestas · 1 alguna con warm=0 (informativo, lo dice en su salida) · 2 NO PUDE
LEER. El 1 y el 2 son distintos a propósito: la primera versión devolvía 1 en los dos casos y
el shell imprimía «no se pudo leer el estado» justo cuando SÍ lo había leído y había réplicas
frías. Es el mismo error de leer un código de salida sin distinguir sus significados que este
repo ya cuenta nueve veces.

Separado de `monitorear.sh` porque es un parseo de JSON y en bash eso se escribe mal: la primera
versión de este monitoreo usaba `grep` sobre el JSON y confundía el `readiness` de un modelo con
el del siguiente cuando la API cambiaba el orden de las claves.

`warm=0` es el dato que se busca: la réplica no está puesta y la próxima llamada paga el
arranque en frío. Y se mira ANTES de sondear, porque la sonda calienta.
"""
import ast
import json
import pathlib
import sys


def papeles_por_modelo(raiz):
    """El mapa nombre-de-modelo → papel, LEÍDO de `colabhive/scripts/_status.py`.

    No se copia acá: una regla copiada en dos lados es una regla que va a divergir, y esta ya
    divergió una vez —la config nombra los modelos por uuid y la API por nombre, así que el
    cruce por id no encontraba ninguno y el monitoreo listaba los 31 modelos no fríos del
    catálogo en vez de los tres del equipo—.
    """
    st = raiz / "colabhive" / "scripts" / "_status.py"
    try:
        texto = st.read_text()
    except OSError:
        return {}
    # Se extrae el literal ROLES sin ejecutar el script: `_status.py` lee stdin y sale.
    i = texto.find("ROLES = {")
    if i < 0:
        return {}
    j = texto.find("}", i)
    try:
        return ast.literal_eval(texto[i + len("ROLES = "):j + 1])
    except (ValueError, SyntaxError):
        return {}


def main():
    raiz = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    try:
        datos = json.load(sys.stdin)
    except (ValueError, OSError) as e:
        print(f"    ⊘ la API no devolvió JSON ({e}): NO se verificó. No es un pase.")
        return 2
    ms = datos.get("models") or []
    if not ms:
        print("    ⊘ la API no devolvió ningún modelo: NO se verificó.")
        return 2
    papeles = papeles_por_modelo(raiz)
    por_nombre = {m["model_name"]: m for m in ms}
    frias = 0
    if not papeles:
        print("    ⊘ no pude leer el mapa de papeles de _status.py: muestro sólo los no fríos")
        for nombre, m in sorted((n, m) for n, m in por_nombre.items()
                                if m.get("readiness") != "cold"):
            print(f"    · {m.get('readiness','?'):7} warm={m.get('warm_nodes')} {nombre[:46]}")
        return 0
    for nombre, papel in sorted(papeles.items(), key=lambda x: x[1]):
        m = por_nombre.get(nombre)
        if m is None:
            print(f"    ⊘ {papel:12} {nombre[:40]} no está en el catálogo de la API")
            continue
        warm = m.get("warm_nodes") or 0
        marca = "✓" if warm > 0 else "■"
        if warm == 0:
            frias += 1
        print(f"    {marca} {papel:12} {m.get('readiness','?'):7} warm={warm}  {nombre[:40]}")
    if frias:
        print(f"    ■ {frias} de {len(papeles)} del equipo con warm=0: la plataforma no las")
        print("       repuso, y la próxima llamada paga el arranque en frío")
    print(f"    · {len(ms)} modelos en el catálogo de la API")
    return 1 if frias else 0


if __name__ == "__main__":
    sys.exit(main())
