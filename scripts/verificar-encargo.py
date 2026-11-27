#!/usr/bin/env python3
"""¿El ENCARGO funciona? No «¿las tareas cerraron?».

    python3 $AGENTES/scripts/verificar-encargo.py
    python3 $AGENTES/scripts/verificar-encargo.py --exigir    # un ⊘ también es rojo

POR QUÉ EXISTE. El 2026-11-26 levantamos `ejemplo-clasificados` desde cero: 19 de 34 tareas
cerradas, 46 tests de backend y 27 de frontend en verde, `smoke.sh` en 0 — y el sitio
publicaba UNA ruta (`/salud`), el frontend no se podía ni construir («Could not resolve entry
module "index.html"»), y `App.jsx` entero era un `<h1>`. Nada de eso lo vio ninguno de los
1041 tests del método ni ninguno de los 73 del proyecto. Lo vio levantar el sitio y mirarlo.

Y ahí está el hueco, que es de nivel y no de cantidad: **el método verifica TAREAS.** Cada
tarea contra su propio test, cada test contra su propia reversión. Lo que nadie verifica es
el encargo, que es lo único que le importa a quien lo pidió. Agregar un chequeo por cada
defecto encontrado es una rueda de hámster: lo que corta la rueda es subir un nivel.

CÓMO, sin que el método sepa nada del stack. El encargo YA declara sus requisitos con clave
—es lo que `cobertura.py` usa para verificar que cada uno tenga al menos una tarea— y acá se
usa para lo otro: que cada uno tenga algo que lo EJERCITE contra el producto corriendo. El
método trae el corredor; el proyecto trae la prueba, en `pruebas-de-uso/<clave>.sh`. Es el
mismo seam que `scripts/entorno.sh` (los servicios) y `scripts/smoke.sh` (el arranque): el
método no sabe qué base de datos usa nadie, y tampoco sabe qué significa «login» acá.

LOS TRES VEREDICTOS, los de siempre:

    ✓  se ejercitó y pasó
    ✗  se ejercitó y falló
    ⊘  no hay con qué ejercitarlo

**El ⊘ es la mitad del valor.** Hoy «nadie probó `registro` nunca» y «`registro` funciona»
se imprimen igual —los dos como silencio— y es exactamente el defecto que el método persigue
en todas sus otras formas. Por omisión un ⊘ no es rojo, igual que el paso 8 del gate con la
suite reservada; `--exigir` lo vuelve rojo, para antes de desplegar.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _encargo

EXIGIR = "--exigir" in sys.argv
BASE = pathlib.Path(os.environ.get("BASE", ".")).resolve()
ENCARGO = BASE / os.environ.get("ENCARGO", "OBJETIVO.md")
DIR_PRUEBAS = BASE / "pruebas-de-uso"
TOPE_S = int(os.environ.get("TOPE_PRUEBA_S", "120"))

if not ENCARGO.exists():
    print(f"  ✗ no existe {ENCARGO}")
    print("     El encargo lo escribe una persona, en sus palabras (HUMANO.md §1).")
    sys.exit(1)

texto = ENCARGO.read_text()
reqs = _encargo.requisitos(texto)
if not reqs:
    if not _encargo.tiene_seccion(texto):
        print(f"  ⊘ {ENCARGO.name} no declara «## Requisitos» con claves: no hay nada que")
        print("     verificar a nivel encargo. Sin esas claves, que el producto cumpla lo")
        print("     pedido queda entero en manos de quien lo pruebe a mano (G3).")
    else:
        print(f"  ⊘ la sección «## Requisitos» de {ENCARGO.name} no tiene claves entre backticks")
    sys.exit(1 if EXIGIR else 0)


def prueba_de(clave):
    """El archivo que ejercita esta clave, o None. Cualquiera de sus alternativas sirve."""
    if not DIR_PRUEBAS.is_dir():
        return None
    for nombre in _encargo.alternativas(clave):
        for cand in (DIR_PRUEBAS / f"{nombre}.sh", DIR_PRUEBAS / nombre / "prueba.sh"):
            if cand.is_file():
                return cand
    return None


verdes, rojos, vacuos = [], [], []
for clave, _resto in reqs:
    nombre = _encargo.alternativas(clave)[0]
    prueba = prueba_de(clave)
    if prueba is None:
        vacuos.append(clave)
        print(f"  ⊘ {nombre:12} ninguna prueba de uso declarada en pruebas-de-uso/")
        continue
    try:
        r = subprocess.run(["bash", str(prueba)], cwd=str(BASE), timeout=TOPE_S,
                           capture_output=True, text=True)
        salida = (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        rojos.append(clave)
        print(f"  ✗ {nombre:12} la prueba no terminó en {TOPE_S}s: no hay veredicto")
        print(f"       {prueba.relative_to(BASE)} · subí TOPE_PRUEBA_S si de verdad tarda")
        continue
    primera = next((l for l in salida.splitlines() if l.strip()), "")
    if r.returncode == 0:
        verdes.append(clave)
        print(f"  ✓ {nombre:12} {primera[:84]}")
    else:
        rojos.append(clave)
        print(f"  ✗ {nombre:12} {primera[:84]}")
        for l in salida.splitlines()[1:6]:
            print(f"       {l[:96]}")

print()
print(f"  {len(verdes)} de {len(reqs)} requisito(s) del encargo se ejercitaron y pasaron.")
if vacuos:
    # El ⊘ dicho con todas las letras. Un verde que no distingue «pasó» de «nadie lo probó»
    # es el veredicto vacío que este método persigue, y acá sería el más caro de todos:
    # el encargo es lo único que le importa a quien lo pidió.
    print(f"  ⊘ {len(vacuos)} NUNCA se ejercitaron: {', '.join(vacuos)}")
    print("     Este verde NO dice que el encargo esté cumplido: dice que no se preguntó.")
    print("     Cada clave se ejercita con un pruebas-de-uso/<clave>.sh que salga 0 o 1")
    print("     contra el producto corriendo. Lo escribe el proyecto: el método no sabe qué")
    print("     significa esta clave acá.")
if rojos:
    print(f"  ✗ {len(rojos)} falló/fallaron: {', '.join(rojos)}")

sys.exit(1 if rojos or (vacuos and EXIGIR) else 0)
