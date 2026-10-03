#!/usr/bin/env python3
"""Tests del método. Cada caso es un bug que de verdad tuvimos.

  python3 pruebas/test_metodo.py

Por qué existe, y es la pieza que más faltaba: **el método verifica el proyecto y nada
verificaba el método.** En un solo día aparecieron diez fallas de la misma clase —un chequeo
que, ante una situación que no previó, **deja de mirar en vez de fallar**— y cada verificador
nuevo encontró bugs en los anteriores:

- `git diff` devuelve rutas del repo y no del proyecto: el paso 0 daba verde con un test
  modificado.
- `git cat-file` lo mismo: el paso 4 no revertía nada y daba verde.
- `.base-ref`, que escribe el propio runner, contaba como archivo fuera de alcance.
- `Ran 0 tests` contaba como verde.
- `mapfile` no existe en bash 3.2: el runner del plan nunca había corrido.
- `$$` en bash es el PID: un patrón roto dejaba todo "fuera de alcance".
- `--depth 1` contra una ruta local se ignora en silencio.

Ninguna falla a gritos. Todas **dejan de mirar**, y eso se ve igual que "mirá y está bien".
Cada test de acá fija uno de esos casos para que no vuelva.

El patrón de cada caso: se arma un repo de juguete con las plantillas, se lo perturba de una
forma concreta, y se afirma el VEREDICTO esperado. No se afirma el texto exacto de la salida
—eso haría los tests frágiles— sino el código de salida y, cuando importa, que el motivo
aparezca.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
PLANTILLAS = RAIZ / "plantillas"


def correr(cmd, cwd, **env):
    e = dict(os.environ, **{k: str(v) for k, v in env.items()})
    return subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True, env=e)


class Proyecto:
    """Un repo de juguete con la forma que el método espera, para perturbar y tirar."""

    def __init__(self, en_subdirectorio=True):
        # El proyecto va en un SUBDIRECTORIO del repo a propósito: es la configuración donde
        # aparecen los bugs de rutas (`git diff` y `git cat-file` informan desde la raíz del
        # repo, no del proyecto) y es como están los dos ejemplos. Con el proyecto en la
        # raíz, esos bugs no se reproducen y los tests dan verde con el bug puesto — lo
        # comprobamos reintroduciéndolos.
        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-metodo-"))
        self.dir = (self.repo / "proyecto") if en_subdirectorio else self.repo
        self.dir.mkdir(exist_ok=True)
        for d in ("tareas", "scripts", "src", "tests"):
            (self.dir / d).mkdir()
        shutil.copy(PLANTILLAS / "gate.sh", self.dir / "scripts" / "gate.sh")
        (self.dir / "src" / "__init__.py").touch()
        (self.dir / "tests" / "__init__.py").touch()
        (self.repo / ".gitignore").write_text(
            "__pycache__/\n*.pyc\n.tarea.log\n.base-ref\n.metricas/\n.opencode-data/\n")
        self.escribir_tarea("T01", "src/cosa.py")
        (self.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom src.cosa import f\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(), 42)\n")
        (self.dir / "PLAN.md").write_text(
            "# Plan\n\n**Estado del gate G0:** aprobado por nadie el 2026-01-01\n\n"
            "## Requisitos\n\n- `cosa` — que haya una cosa\n\n"
            "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T01 | Una cosa | — | src/cosa.py | pendiente |\n")
        self.git("init -q")
        self.git("add -A"); self.git('commit -qm base')

    def escribir_tarea(self, tid, archivos, estado="pendiente"):
        (self.dir / "tareas" / f"{tid}-cosa.md").write_text(
            f"# {tid} — Una cosa\n\n**Estado:** {estado}\n**Depende de:** —\n"
            f"**Archivos que podés tocar:** {archivos}\n**Prohibido tocar:** tests/\n\n"
            f"## Objetivo\n\nQue haya una cosa.\n\n"
            f"## Tests (ya escritos, fallando)\n\nArchivo: `tests/test_cosa.py`, clase `TestCosa`.\n")

    def git(self, args):
        return correr(f"git {args}", self.repo)

    def implementar(self, cuerpo="def f():\n    return 42\n"):
        (self.dir / "src" / "cosa.py").write_text(cuerpo)

    def gate(self, tarea=None):
        return correr("bash scripts/gate.sh", self.dir, TAREA=(tarea or ""))

    def tirar(self):
        shutil.rmtree(self.repo, ignore_errors=True)


class CasoBase(unittest.TestCase):
    def setUp(self):
        self.p = Proyecto()

    def tearDown(self):
        self.p.tirar()

    def assertRojo(self, r, porque="", motivo=None):
        """Rojo Y por el motivo correcto.

        Sin `motivo` un test pasa cuando el gate da rojo por una causa distinta de la que se
        está probando. Nos pasó: el test de la suite vacía pasaba porque borrar el archivo
        contaba como fuera de alcance, no porque la suite estuviera vacía. Eso es confianza
        falsa, que es peor que no tener el test.
        """
        self.assertNotEqual(r.returncode, 0,
                            f"debía dar ROJO{': ' + porque if porque else ''}\n{r.stdout[-800:]}")
        if motivo:
            self.assertIn(motivo, r.stdout,
                          f"dio rojo, pero no por «{motivo}»\n{r.stdout[-800:]}")

    def assertVerde(self, r, porque=""):
        self.assertEqual(r.returncode, 0,
                         f"debía dar VERDE{': ' + porque if porque else ''}\n{r.stdout[-800:]}")


class TestGate(CasoBase):
    """Los seis pasos, y los falsos verdes que cada uno tapaba."""

    def test_sin_implementacion_da_rojo(self):
        self.assertRojo(self.p.gate("T01"), "los tests fallan")

    def test_con_implementacion_da_verde(self):
        self.p.implementar()
        self.assertVerde(self.p.gate("T01"))

    def test_tocar_un_test_da_rojo(self):
        """El paso 0. Daba VERDE porque git informa rutas del repo y no del proyecto."""
        self.p.implementar()
        with (self.p.dir / "tests" / "test_cosa.py").open("a") as f:
            f.write("# colado\n")
        self.assertRojo(self.p.gate("T01"), "tocó un test", motivo="intocable")

    def test_tocar_el_propio_gate_da_rojo(self):
        self.p.implementar()
        with (self.p.dir / "scripts" / "gate.sh").open("a") as f:
            f.write("# colado\n")
        self.assertRojo(self.p.gate("T01"), "tocó el gate que lo juzga", motivo="intocable")

    def test_suite_vacia_da_rojo(self):
        """`Ran 0 tests` contaba como verde. Una suite vacía pasa siempre."""
        self.p.implementar()
        (self.p.dir / "tests" / "test_cosa.py").unlink()
        self.assertRojo(self.p.gate("T01"), "no corrió ningún test",
                        motivo="no corrió ningún test")

    def test_sin_alcance_declarado_da_rojo(self):
        """Decía 'sin límite de alcance declarado' y seguía en verde."""
        self.p.implementar()
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("**Archivos que podés tocar:** src/cosa.py",
                                           "**Archivos que podés tocar:**"))
        self.assertRojo(self.p.gate("T01"), "la tarea no declara alcance",
                        motivo="no declara")

    def test_alcance_por_ruta_no_por_nombre(self):
        """Permitir `cosa.py` no puede habilitar `tests/cosa.py`."""
        self.p.implementar()
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("src/cosa.py", "cosa.py"))
        (self.p.dir / "tests" / "cosa.py").write_text("# colado donde no va\n")
        self.assertRojo(self.p.gate("T01"), "un archivo en tests/ no entra por nombre",
                        motivo="fuera del alcance")

    def test_infraestructura_del_runner_no_cuenta_como_fuera_de_alcance(self):
        """`.base-ref` lo escribe el runner y ponía en ROJO toda tarea."""
        self.p.implementar()
        (self.p.dir / ".base-ref").write_text(
            self.p.git("rev-parse HEAD").stdout.strip() + "\n")
        self.assertVerde(self.p.gate("T01"), ".base-ref es del runner, no del agente")

    def test_senal_suprimida_da_rojo(self):
        self.p.implementar("def f():\n    return 42  # noqa\n")
        self.assertRojo(self.p.gate("T01"), "apagar una señal no es arreglarla",
                        motivo="señales suprimidas")

    def test_sin_cambios_en_modo_tarea_da_rojo(self):
        """Sin cambios la tarea no se hizo, aunque la suite estuviera verde."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.assertRojo(self.p.gate("T01"), "no hay ningún cambio",
                        motivo="no hay ningún cambio")

    def test_paso4_revierte_de_verdad(self):
        """`git cat-file` usa rutas del repo: el paso 4 daba verde sin revertir nada."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        # Un cambio que ningún test distingue: la suite sigue verde al revertirlo.
        self.p.implementar("def f():\n    return 42\n\n\ndef g():\n    return 1\n")
        self.assertRojo(self.p.gate("T01"), "los tests no distinguen el cambio",
                        motivo="PASAN con la implementación vieja")


class TestValidarPlan(CasoBase):
    def validar(self, extra=""):
        return correr(f"PLAN=PLAN.md python3 {SCRIPTS}/validar-plan.py {extra}", self.p.dir)

    def test_plan_sano_valida(self):
        self.assertVerde(self.validar())

    def test_fila_duplicada_da_rojo(self):
        p = self.p.dir / "PLAN.md"
        fila = "| T01 | Una cosa | — | src/cosa.py | pendiente |\n"
        p.write_text(p.read_text().replace(fila, fila * 2))
        self.assertRojo(self.validar(), "filas repetidas")

    def test_arreglar_quita_la_fila_duplicada(self):
        p = self.p.dir / "PLAN.md"
        fila = "| T01 | Una cosa | — | src/cosa.py | pendiente |\n"
        p.write_text(p.read_text().replace(fila, fila * 2))
        self.validar("--arreglar")
        self.assertVerde(self.validar(), "después de --arreglar tiene que quedar limpio")

    def test_archivo_de_tarea_huerfano_da_rojo(self):
        self.p.escribir_tarea("T99", "src/otra.py")
        self.assertRojo(self.validar(), "T99 no está en la tabla")

    def test_fila_sin_archivo_da_rojo(self):
        (self.p.dir / "tareas" / "T01-cosa.md").unlink()
        self.assertRojo(self.validar(), "T01 está en la tabla y no tiene archivo")

    def test_plantilla_sin_completar_da_rojo(self):
        p = self.p.dir / "PLAN.md"
        p.write_text(p.read_text() + "\nResponsable: <quién>\n")
        self.assertRojo(self.validar(), "quedó un placeholder")

    def test_cabecera_que_no_coincide_con_la_tabla_da_rojo(self):
        """Dos declaraciones de lo mismo que lee gente distinta."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("**Depende de:** —", "**Depende de:** T07"))
        self.assertRojo(self.validar(), "el archivo dice T07 y la tabla dice —",
                        motivo="Depende de")

    def test_generico_de_typescript_no_es_un_placeholder(self):
        p = self.p.dir / "PLAN.md"
        p.write_text(p.read_text() + "\nContrato: `Promise<void>` y `<any>`\n")
        self.assertVerde(self.validar(), "los genéricos no son plantillas sin completar")


class TestCobertura(CasoBase):
    def cobertura(self):
        return correr(f"ENCARGO=OBJETIVO.md PLAN=PLAN.md python3 {SCRIPTS}/cobertura.py", self.p.dir)

    def encargo(self, requisitos):
        (self.p.dir / "OBJETIVO.md").write_text(
            "# Qué queremos\n\nUna cosa.\n\n## Requisitos\n\n" + requisitos + "\n")

    def test_requisito_cubierto_da_verde(self):
        self.encargo("- `cosa` — que haya una cosa")
        self.assertVerde(self.cobertura())

    def test_requisito_sin_tarea_da_rojo(self):
        self.encargo("- `cosa` — que haya una cosa\n- `otra` — que haya otra")
        self.assertRojo(self.cobertura(), "'otra' no tiene ninguna tarea")

    def test_acentos_y_enie_no_importan(self):
        self.encargo("- `disenio` — con eñe\n- `cosa` — que haya una cosa")
        p = self.p.dir / "PLAN.md"
        p.write_text(p.read_text().replace("| T01 | Una cosa |", "| T01 | Diseñio y cosa |"))
        self.assertVerde(self.cobertura(), "normalizar acentos es parte del contrato")

    def test_alternativas_con_barra(self):
        self.encargo("- `publicar|crud` — crear la cosa")
        p = self.p.dir / "PLAN.md"
        p.write_text(p.read_text().replace("Una cosa", "CRUD de cosas"))
        self.assertVerde(self.cobertura(), "alcanza con que una alternativa aparezca")


class TestEtapas(CasoBase):
    def etapas(self):
        return correr(f"PLAN=PLAN.md python3 {SCRIPTS}/_etapas.py", self.p.dir)

    def tabla(self, filas):
        p = self.p.dir / "PLAN.md"
        base = p.read_text().split("| T01 |")[0]
        p.write_text(base + filas)

    def test_dependencias_se_respetan(self):
        self.tabla("| T01 | A | — | src/a.py | pendiente |\n"
                   "| T02 | B | T01 | src/b.py | pendiente |\n")
        r = self.etapas()
        self.assertEqual(r.stdout.split("\n")[0].split(), ["T01"])
        self.assertIn("T02", r.stdout.split("\n")[1])

    def test_choque_de_archivo_separa_tareas(self):
        """La regla que más cuesta aplicar a mano, y la que más se olvida."""
        self.tabla("| T01 | A | — | src/mismo.py | pendiente |\n"
                   "| T02 | B | — | src/mismo.py | pendiente |\n")
        r = self.etapas()
        etapas = [l.split() for l in r.stdout.strip().split("\n") if l.strip()]
        self.assertEqual(len(etapas), 2, f"dos tareas sobre el mismo archivo van en serie: {etapas}")

    def test_archivos_sin_backticks_tambien_cuentan(self):
        """Sólo se leían entre backticks: sin ellos, la regla del choque no se aplicaba."""
        self.tabla("| T01 | A | — | `src/mismo.py` | pendiente |\n"
                   "| T02 | B | — | `src/mismo.py` | pendiente |\n")
        etapas = [l for l in self.etapas().stdout.strip().split("\n") if l.strip()]
        self.assertEqual(len(etapas), 2, "con backticks también")

    def test_segunda_tabla_no_pisa_la_primera(self):
        """La tabla de tests dejó las ocho tareas en una sola etapa, en paralelo."""
        self.tabla("| T01 | A | — | src/a.py | pendiente |\n"
                   "| T02 | B | T01 | src/b.py | pendiente |\n\n"
                   "## Tests\n\n| Tarea | Archivo | Clase |\n|---|---|---|\n"
                   "| T01 | tests/test_a.py | TestA |\n| T02 | tests/test_b.py | TestB |\n")
        etapas = [l for l in self.etapas().stdout.strip().split("\n") if l.strip()]
        self.assertEqual(len(etapas), 2, "la tabla de tests no declara dependencias")

    def test_plan_sin_tabla_sale_con_codigo_2(self):
        (self.p.dir / "PLAN.md").write_text("# Plan\n\nNada.\n")
        self.assertEqual(self.etapas().returncode, 2,
                         "'no hay tabla' tiene que distinguirse de 'está terminado'")


class TestMutar(CasoBase):
    def mutar(self, base="HEAD~1"):
        return correr(f"BASE={base} CODIGO=src SUITE='python3 -m unittest discover -s tests -t . -q' "
                      f"python3 {SCRIPTS}/mutar.py", self.p.dir)

    def test_mutante_que_sobrevive_se_informa(self):
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("def f():\n    return 42\n\n\ndef tope(x):\n"
                           "    if x >= 999:\n        return 999\n    return x\n")
        self.p.git("add -A"); self.p.git("commit -qm tope")
        self.assertRojo(self.mutar(), "nada testea el tope", motivo="sobrevivieron")

    def test_nodos_aridos_no_se_mutan(self):
        """Logging, `raise` de contrato y comparaciones contra None son improductivos."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("import logging\n\n\ndef f():\n"
                           "    logging.info('hola')\n"
                           "    if f is None:\n        raise ValueError('imposible')\n"
                           "    return 42\n")
        self.p.git("add -A"); self.p.git("commit -qm aridos")
        r = self.mutar()
        self.assertVerde(r, "todo lo agregado es árido")
        self.assertIn("árido", r.stdout)


class TestArquitectura(CasoBase):
    def preparar(self, capas, requeridas, modulos):
        shutil.copy(PLANTILLAS / "_arquitectura.py", self.p.dir / "scripts" / "_arquitectura.py")
        a = self.p.dir / "scripts" / "_arquitectura.py"
        s = a.read_text()
        s = s.replace('CAPAS = ["datos", "servicios", "rutas"]', f"CAPAS = {capas!r}")
        s = s.replace('REQUERIDAS = [\n    ("servicios", "datos"),   # la lógica usa la capa de datos\n'
                      '    ("rutas", "servicios"),   # los endpoints no hablan con datos directamente\n]',
                      f"REQUERIDAS = {requeridas!r}")
        a.write_text(s)
        for nombre, contenido in modulos.items():
            (self.p.dir / "src" / f"{nombre}.py").write_text(contenido)

    def arq(self):
        return correr(f"python3 scripts/_arquitectura.py", self.p.dir)

    def test_divergencia_da_rojo(self):
        self.preparar(["datos", "rutas"], [],
                      {"datos": "from .rutas import x\n", "rutas": ""})
        self.assertRojo(self.arq(), "datos importa rutas", motivo="divergencia")

    def test_ausencia_da_rojo(self):
        """Lo que un chequeo de dirección NO ve: la dependencia que debería estar."""
        self.preparar(["datos", "rutas"], [("rutas", "datos")],
                      {"datos": "", "rutas": "# no usa datos\n"})
        self.assertRojo(self.arq(), "rutas no usa datos y la arquitectura lo requiere",
                        motivo="ausencia")

    def test_arquitectura_sana_da_verde(self):
        self.preparar(["datos", "rutas"], [("rutas", "datos")],
                      {"datos": "", "rutas": "from .datos import x\n"})
        self.assertVerde(self.arq())


if __name__ == "__main__":
    unittest.main(verbosity=2)
