#!/usr/bin/env python3
"""El proyecto de un ENSAYO del pipeline: N tareas y la clave de cada una, afuera del proyecto.

Lo usa `scripts/ensayo.sh`. Por qué existe está escrito ahí y en MEDICION.md §9; en una línea:
el pipeline completo —etapas, worktrees, escribir-tests, gate, cierre, merge— no se podía
medir a escala porque medirlo con modelos de verdad cuesta horas y no es repetible.

Cada grupo son tres tareas EN CADENA, una por capa, que es la forma que el chequeo de
arquitectura exige (servicios usa datos, rutas usa servicios):

    T{n}a  src/datos/d{n}.py       —
    T{n}b  src/servicios/s{n}.py   depende de T{n}a
    T{n}c  src/rutas/r{n}.py       depende de T{n}b

Los grupos son independientes entre sí, así que cada etapa queda con una tarea de cada grupo
en paralelo: con 7 grupos son 21 tareas en 3 etapas de 7. Eso es lo que hace falta para medir
el paralelismo —7 worktrees y 7 merges por etapa—, que es donde el método había chocado antes
(dos ramas commiteando su propio `.tests-base`).

  python3 scripts/_ensayo_generar.py <grupos> <destino> <claves>
"""
import pathlib
import subprocess
import sys

AGENTES = pathlib.Path(__file__).resolve().parent.parent
grupos = int(sys.argv[1])
dest = pathlib.Path(sys.argv[2]).resolve()
claves = pathlib.Path(sys.argv[3]).resolve()

CAPAS = [("a", "datos", "d", "leer"), ("b", "servicios", "s", "calcular"),
         ("c", "rutas", "r", "responder")]


def sh(cmd, cwd=dest):
    return subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True)


for d in ("tareas", "scripts", "tests", "src/datos", "src/servicios", "src/rutas"):
    (dest / d).mkdir(parents=True, exist_ok=True)
for p in ("src/__init__.py", "tests/__init__.py", "src/datos/__init__.py",
          "src/servicios/__init__.py", "src/rutas/__init__.py"):
    (dest / p).write_text("")

# El .gitignore EXACTO de la guía: es el mismo que el gate filtra, y un olvido acá produce
# conflictos de merge por etapa (medido con `.tests-base`).
(dest / ".gitignore").write_text(
    "__pycache__/\n*.pyc\nnode_modules/\n.venv\n.entorno\n.mysql/\n.tarea.log\n.plan.log\n"
    ".segundos\n.opencode-data/\n.metricas/\n.artefactos/\n.base-ref\n.tests-base\n"
    "PLAN.md.previo\n")

for f in ("gate.sh", "correr-suite.sh", "_arquitectura.py", "pre-deploy.sh", "smoke.sh"):
    (dest / "scripts" / f).write_text((AGENTES / "plantillas" / f).read_text())
(dest / "AGENTS.md").write_text((AGENTES / "AGENTS.md").read_text())

# Las capas del ensayo son las de la plantilla, así que `_arquitectura.py` queda como viene.

filas, filas_tests, requisitos = [], [], []
for g in range(1, grupos + 1):
    for sufijo, capa, pre, verbo in CAPAS:
        tid = f"T{g:02d}{sufijo}"
        mod = f"src/{capa}/{pre}{g}.py"
        ruta_test = f"tests/test_{pre}{g}.py"
        clase = f"Test{pre.upper()}{g}"
        dep = "—" if sufijo == "a" else f"T{g:02d}{'a' if sufijo == 'b' else 'b'}"
        filas.append(f"| {tid} | {verbo} del grupo {g} | {dep} | {mod} | pendiente |")
        filas_tests.append(f"| {tid} | {ruta_test} | {clase} |")

        # La CLAVE: implementación y test, afuera del proyecto. El agente falso copia de acá.
        k = claves / tid
        (k / "src" / capa).mkdir(parents=True, exist_ok=True)
        (k / "tests").mkdir(parents=True, exist_ok=True)
        if sufijo == "a":
            cuerpo = f"def leer{g}():\n    return {g}\n"
            test = (f"import unittest\nfrom src.datos.d{g} import leer{g}\n\n\n"
                    f"class TestD{g}(unittest.TestCase):\n"
                    f"    def test_leer_devuelve_el_numero_del_grupo(self):\n"
                    f"        self.assertEqual(leer{g}(), {g})\n")
        elif sufijo == "b":
            cuerpo = (f"from src.datos.d{g} import leer{g}\n\n\n"
                      f"def calcular{g}():\n    return leer{g}() * 10\n")
            test = (f"import unittest\nfrom src.servicios.s{g} import calcular{g}\n\n\n"
                    f"class TestS{g}(unittest.TestCase):\n"
                    f"    def test_calcular_multiplica_por_diez(self):\n"
                    f"        self.assertEqual(calcular{g}(), {g * 10})\n")
        else:
            cuerpo = (f"from src.servicios.s{g} import calcular{g}\n\n\n"
                      f"def responder{g}():\n    return {{\"valor\": calcular{g}()}}\n")
            test = (f"import unittest\nfrom src.rutas.r{g} import responder{g}\n\n\n"
                    f"class TestR{g}(unittest.TestCase):\n"
                    f"    def test_responder_envuelve_el_valor(self):\n"
                    f"        self.assertEqual(responder{g}(), {{\"valor\": {g * 10}}})\n")
        (k / mod.replace("src/", "src/")).write_text(cuerpo)
        (k / ruta_test).write_text(test)

        # Variantes DEGRADADAS del test, una por cada cosa que `escribir-tests.sh` afirma
        # atrapar antes de aceptar un test. Sin esto el ensayo mide el gate y NO mide el
        # validador de tests, que es la pieza que decide si un test entra al tronco — y de
        # ahí en adelante es el juez de todo lo demás.
        #
        #   vacuo      pasa contra el código actual: no prueba nada           (afirmación 1)
        #   imposible  no pasa ni con la implementación de referencia          (afirmación 2)
        #   flojo      pasa con la referencia y SOBREVIVE a la mutación        (afirmación 3)
        #   otraclase  el archivo y la clase no son los que declara el plan    (afirmación 4)
        importa = {"a": f"from src.datos.d{g} import leer{g}",
                   "b": f"from src.servicios.s{g} import calcular{g}",
                   "c": f"from src.rutas.r{g} import responder{g}"}[sufijo]
        llamada = {"a": f"leer{g}()", "b": f"calcular{g}()",
                   "c": f"responder{g}()"}[sufijo]
        degradados = {
            "vacuo": ("import unittest\n\n\n"
                      f"class {clase}(unittest.TestCase):\n"
                      "    def test_la_cosa_funciona(self):\n"
                      "        self.assertTrue(True)\n"),
            "imposible": (f"import unittest\n{importa}\n\n\n"
                          f"class {clase}(unittest.TestCase):\n"
                          "    def test_la_cosa_funciona(self):\n"
                          f"        self.assertEqual({llamada}, 'nada que ver')\n"),
            "flojo": (f"import unittest\n{importa}\n\n\n"
                      f"class {clase}(unittest.TestCase):\n"
                      "    def test_la_cosa_funciona(self):\n"
                      f"        self.assertIsNotNone({llamada})\n"),
            "otraclase": (f"import unittest\n{importa}\n\n\n"
                          "class TestOtraCosa(unittest.TestCase):\n"
                          "    def test_la_cosa_funciona(self):\n"
                          f"        self.assertIsNotNone({llamada})\n"),
        }
        for nombre, cuerpo_test in degradados.items():
            d = k / "degradados" / nombre / "tests"
            d.mkdir(parents=True, exist_ok=True)
            (d / pathlib.Path(ruta_test).name).write_text(cuerpo_test)

        # El `## Contrato` con la firma Y el import que la tarea usa: sin él, el cruce de
        # imports del validador no tiene nada que leer y avisa —con razón— que no pudo
        # verificar ninguna. Un ensayo que deja chequeos sin material no ensaya el pipeline.
        if sufijo == "a":
            contrato = f"    def leer{g}() -> int:\n        \"\"\"Devuelve {g}.\"\"\"\n"
            usa = ""
        elif sufijo == "b":
            contrato = (f"    def calcular{g}() -> int:\n"
                        f"        \"\"\"Devuelve `leer{g}() * 10`.\"\"\"\n")
            usa = f"\nUsa `from src.datos.d{g} import leer{g}`.\n"
        else:
            contrato = (f"    def responder{g}() -> dict:\n"
                        f"        \"\"\"Devuelve `{{\"valor\": calcular{g}()}}`.\"\"\"\n")
            usa = f"\nUsa `from src.servicios.s{g} import calcular{g}`.\n"

        (dest / "tareas" / f"{tid}-cosa.md").write_text(
            f"# {tid} — {verbo} del grupo {g}\n\n"
            f"**Estado:** pendiente\n**Depende de:** {dep}\n"
            f"**Archivos que podés tocar:** {mod}\n**Prohibido tocar:** tests/, scripts/\n\n"
            f"## Objetivo\n\nQue `{verbo}{g}()` exista en `{mod}` y devuelva lo que su test espera.\n\n"
            f"## Contrato\n\n{contrato}{usa}\n"
            f"## Criterio de aceptación\n\n"
            f"- `{verbo}{g}()` devuelve el valor que verifica `{ruta_test}`\n\n"
            f"## Tests (ya escritos, fallando)\n\nArchivo: `{ruta_test}`, clase `{clase}`.\n")

requisitos.append("- `cosa|grupo` — que cada grupo lea, calcule y responda")
(dest / "OBJETIVO.md").write_text(
    "# Qué queremos\n\nUn ensayo determinista del pipeline.\n\n## Requisitos\n\n"
    + "\n".join(requisitos) + "\n")
(dest / "PLAN.md").write_text(
    "# Plan del ensayo\n\n**Estado del gate G0:** aprobado por nadie el 2026-10-26\n\n"
    "## Requisitos\n\n" + "\n".join(requisitos) + "\n\n"
    "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
    + "\n".join(filas) + "\n\n"
    "## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
    + "\n".join(filas_tests) + "\n")

sh("git init -q .")
sh("git add -A")
sh("git -c user.email=ensayo@metodo -c user.name=ensayo commit -qm 'esqueleto del ensayo'")
print(f"{grupos * 3} tareas en {dest}")
print(f"claves en {claves}")
