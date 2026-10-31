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
import os
import pathlib
import random
import subprocess
import sys

AGENTES = pathlib.Path(__file__).resolve().parent.parent
grupos = int(sys.argv[1])
dest = pathlib.Path(sys.argv[2]).resolve()
claves = pathlib.Path(sys.argv[3]).resolve()

CAPAS = [("a", "datos", "d", "leer"), ("b", "servicios", "s", "calcular"),
         ("c", "rutas", "r", "responder")]

# ── Variedad, con semilla ────────────────────────────────────────────────────────────────
#
# Por qué: el dataset de veredictos que este ensayo produce vale por su variedad, no por su
# volumen. Está medido afuera —la diversidad de repos paga de forma logarítmica (+4,8 puntos de
# 4 a 100 repos) y las plantillas homogéneas colapsan la diversidad de acciones un 31%— y
# adentro: setenta y cinco corridas del mismo proyecto no son 2.600 ejemplos, son 21 ejemplos
# repetidos setenta y cinco veces.
#
# Y hay una razón del método, no del dataset: el 2026-10-29 medimos que el 33,3% de los tests
# aceptados tenía su paso de mutación en ⊘, porque la capa `c` devolvía un dict literal y
# `mutar.py` no tiene operadores para eso. Variar el cálculo hace que ese paso corra en más
# tareas, que es la única defensa del gate contra una aserción floja.
#
# `SEMILLA` fija la variedad: la misma semilla da el mismo proyecto, y eso es lo que permite
# citar una corrida. Sin semilla, el dataset no es reproducible y los veredictos no se pueden
# auditar.
SEMILLA = os.environ.get("SEMILLA", "")
_rnd = random.Random(SEMILLA) if SEMILLA else None


def elegir(opciones, g):
    """Con semilla, al azar reproducible; sin semilla, la primera — el comportamiento viejo.

    Que sin `SEMILLA` el proyecto sea EXACTAMENTE el de antes no es prolijidad: la suite de
    este repo tiene tests que corren el ensayo y comparan su salida, y el ensayo determinista
    es lo que mide la orquestación. Un generador que cambia sin que nadie lo pida convierte en
    ruido todas las mediciones anteriores.
    """
    return _rnd.choice(opciones) if _rnd else opciones[0]


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

# La forma elegida por grupo, para que las tres capas del grupo se cuenten la misma historia:
# el contrato de `b` tiene que declarar el import que su implementación usa, y el ejemplo del
# patch tiene que apuntar al objetivo que ESA forma hace efectivo. Cuando varié sólo la capa
# `c` y dejé el contrato viejo, el validador rechazó el test de referencia —con razón— y la
# FNR del brazo bueno subió a 33%.
forma_a_de, objetivo_de, importa_de = {}, {}, {}
esperado_a_de, expr_de = {}, {}
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
            # La FORMA DEL RETORNO se elige. Medido el 2026-10-31 sobre 998 veredictos: sólo
            # el 40% de los tests eran distintos, porque las capas `a` y `b` tenían la misma
            # forma en todas las corridas y el agente escribía el mismo test veinte veces. Un
            # dataset que crece en filas y no en información es el mismo problema que un
            # chequeo que no puede fallar.
            forma_a = elegir(["numero", "lista", "mapa"], g)
            if forma_a == "numero":
                valor, esperado_a = f"{g}", f"{g}"
            elif forma_a == "lista":
                valor, esperado_a = f"[{g}, {g * 2}]", f"[{g}, {g * 2}]"
            else:
                valor, esperado_a = f'{{"n": {g}}}', f'{{"n": {g}}}'
            forma_a_de[g] = forma_a
            esperado_a_de[g] = esperado_a
            cuerpo = f"def leer{g}():\n    return {valor}\n"
            test = (f"import unittest\nfrom src.datos.d{g} import leer{g}\n\n\n"
                    f"class TestD{g}(unittest.TestCase):\n"
                    f"    def test_leer_devuelve_lo_del_grupo(self):\n"
                    f"        self.assertEqual(leer{g}(), {esperado_a})\n")
        elif sufijo == "b":
            # Y acá la FORMA DEL IMPORT, que es la que más información agrega de todas: es la
            # que decide CUÁL es el objetivo correcto del `patch()`.
            #
            #   desde  → `from src.datos.dN import leerN`: el nombre queda ligado en el módulo
            #            que lo usa, así que hay que parchear `src.servicios.sN.leerN`.
            #   modulo → `import src.datos.dN`: la búsqueda es en tiempo de llamada, así que
            #            parchear `src.datos.dN.leerN` SÍ tiene efecto.
            #
            # Con una sola forma, la respuesta correcta era siempre la misma y un juez
            # entrenado con este dataset aprendería una regla fija en vez del razonamiento. De
            # hecho 248 de los ~400 rechazos del dataset son esa única clase.
            forma_i = elegir(["desde", "modulo"], g)
            if forma_i == "desde":
                importa_b = f"from src.datos.d{g} import leer{g}"
                llama_b = f"leer{g}()"
                objetivo = f"src.servicios.s{g}.leer{g}"
            else:
                importa_b = f"import src.datos.d{g}"
                llama_b = f"src.datos.d{g}.leer{g}()"
                objetivo = f"src.datos.d{g}.leer{g}"
            # El dato que `leerN` devuelve depende de la forma de la capa `a` de ESTE grupo:
            # con lista o mapa hay que sacar el número antes de multiplicar, y el test tiene
            # que esperar lo mismo que la implementación calcula.
            fa = forma_a_de.get(g, "numero")
            if fa == "numero":
                expr = f"{llama_b} * 10"
            elif fa == "lista":
                expr = f"{llama_b}[0] * 10"
            else:
                expr = f'{llama_b}["n"] * 10'
            cuerpo = (f"{importa_b}\n\n\n"
                      f"def calcular{g}():\n    return {expr}\n")
            test = (f"import unittest\nfrom src.servicios.s{g} import calcular{g}\n\n\n"
                    f"class TestS{g}(unittest.TestCase):\n"
                    f"    def test_calcular_multiplica_por_diez(self):\n"
                    f"        self.assertEqual(calcular{g}(), {g * 10})\n")
            objetivo_de[g] = objetivo
            importa_de[g] = importa_b
            expr_de[g] = expr
        else:
            # La forma del cálculo se elige: con `return {"valor": calcular()}` —lo único que
            # este generador producía— `mutar.py` no tiene NADA que mutar, y medimos el
            # 2026-10-29 que eso deja al 33,3% de los tests aceptados sin el único paso que
            # juzga la fuerza de la aserción. Las otras dos formas traen un operador, así que
            # el paso corre. Cada una con su expectativa, calculada acá: un test que no
            # coincide con su implementación mide el andamio.
            forma = elegir(["envuelve", "suma", "compara"], g)
            base = g * 10
            if forma == "envuelve":
                calculo = f'{{"valor": calcular{g}()}}'
                esperado = f'{{"valor": {base}}}'
                frase = "envuelve el valor"
            elif forma == "suma":
                calculo = f'{{"valor": calcular{g}() + {g}}}'
                esperado = f'{{"valor": {base + g}}}'
                frase = "suma el grupo al valor"
            else:
                calculo = f'{{"valor": calcular{g}(), "alto": calcular{g}() > {base - 1}}}'
                esperado = f'{{"valor": {base}, "alto": True}}'
                frase = "marca si el valor es alto"
            cuerpo = (f"from src.servicios.s{g} import calcular{g}\n\n\n"
                      f"def responder{g}():\n    return {calculo}\n")
            test = (f"import unittest\nfrom src.rutas.r{g} import responder{g}\n\n\n"
                    f"class TestR{g}(unittest.TestCase):\n"
                    f"    def test_responder_{forma}(self):\n"
                    f"        self.assertEqual(responder{g}(), {esperado})\n")
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
            tipo_a = {"numero": "int", "lista": "list", "mapa": "dict"}[forma_a_de.get(g, "numero")]
            contrato = (f"    def leer{g}() -> {tipo_a}:\n"
                        f"        \"\"\"Devuelve `{esperado_a_de[g]}`.\"\"\"\n")
            usa = ""
        elif sufijo == "b":
            contrato = (f"    def calcular{g}() -> int:\n"
                        f"        \"\"\"Devuelve `{expr_de[g]}`.\"\"\"\n")
            # El contrato declara la CONSECUENCIA del import que él mismo manda, y es lo
            # único con señal replicada de la sesión: 21 de 21 tareas cerradas con modelos
            # chicos, dos veces de dos, contra 7 sin esta línea (MEDICION.md §13). Cambia
            # el sujeto de las mediciones anteriores —§5: instrumento distinto, no se
            # comparan— y se cambia a propósito: el ensayo tiene que generar planes como
            # los que el método recomienda escribir, no como los que ya sabemos que fallan.
            # El objetivo correcto DEPENDE de la forma del import, y el enunciado tiene que
            # decir cuál es: con `from X import n` el nombre queda ligado en el módulo que lo
            # usa; con `import X` la búsqueda es en tiempo de llamada y parchear `X.n` sí
            # tiene efecto. Antes había una sola forma y el enunciado podía decir una regla
            # fija; con las dos, decirla fija sería mentir en la mitad de las tareas.
            if importa_de[g].startswith("from"):
                porque = (f"`src.servicios.s{g}.leer{g}` —el módulo donde se USA—, no\n"
                          f"`src.datos.d{g}.leer{g}`: con ese import el nombre ya quedó ligado\n"
                          f"cuando el patch corre, y parchear donde se define no tiene efecto.\n")
            else:
                porque = (f"`src.datos.d{g}.leer{g}` —donde se DEFINE—: con este import la\n"
                          f"búsqueda del nombre pasa en el momento de la llamada, así que\n"
                          f"parchear el módulo de origen sí tiene efecto.\n")
            usa = (f"\nUsa `{importa_de[g]}`.\n"
                   f"\nSi el test necesita controlar lo que devuelve `leer{g}()`, parcheá\n"
                   + porque)
        else:
            # El contrato tiene que declarar la MISMA forma que la implementación de
            # referencia, o el validador rechaza el test de referencia —y con razón— con «el
            # test obliga un contrato que el enunciado no declara». Lo descubrí midiendo: al
            # parametrizar el cálculo y dejar el contrato viejo, la FNR del brazo bueno subió
            # a 33%. El gate funcionaba; el enunciado era mío y estaba mal.
            contrato = (f"    def responder{g}() -> dict:\n"
                        f"        \"\"\"Devuelve `{calculo}`.\"\"\"\n")
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
    + "\n".join(filas_tests) + "\n\n"
    # El gate humano, que el validador exige: sin él `correr-todo.sh` frena el ensayo, y con
    # razón. Un proyecto de ensayo que no es un proyecto bien formado no ensaya nada.
    "### G3 — prueba de uso (responsable: nadie, 1 minuto)\n\n"
    "- [ ] ¿Devuelve cada grupo lo que su contrato dice?\n"
    "- [ ] ¿Se entiende qué hace cada capa sin leer los tests?\n")

sh("git init -q .")
sh("git add -A")
sh("git -c user.email=ensayo@metodo -c user.name=ensayo commit -qm 'esqueleto del ensayo'")
print(f"{grupos * 3} tareas en {dest}")
print(f"claves en {claves}")
