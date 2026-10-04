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

    def __init__(self, donde="proyecto"):
        # El proyecto va en un SUBDIRECTORIO del repo a propósito: es la configuración donde
        # aparecen los bugs de rutas (`git diff` y `git cat-file` informan desde la raíz del
        # repo, no del proyecto) y es como están los dos ejemplos. Con el proyecto en la
        # raíz, esos bugs no se reproducen y los tests dan verde con el bug puesto — lo
        # comprobamos reintroduciéndolos.
        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-metodo-"))
        # `donde` es la ubicación del proyecto DENTRO del repo. Variarla es la relación
        # metamórfica del test de abajo: el veredicto no puede depender de dónde está.
        self.dir = self.repo if donde == "." else (self.repo / donde)
        self.dir.mkdir(parents=True, exist_ok=True)
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


UBICACIONES = [
    ".",                      # el proyecto es la raíz del repo
    "proyecto",               # un nivel, como los dos ejemplos
    "a/b/c/proyecto",         # profundo
    "con espacio",            # un espacio en la ruta
    "ñandú",                  # no-ASCII
]


class TestRelacionMetamorfica(unittest.TestCase):
    """Mover el proyecto no puede cambiar el veredicto.

    Es la relación metamórfica que usa la literatura de testeo de analizadores estáticos, y
    para nosotros es la de mayor rendimiento: **cuatro de nuestros diez bugs eran de rutas**
    —`git diff` y `git cat-file` informan desde la raíz del repo, no del proyecto— y los dos
    defectos de esta misma suite también. El primero fue poner el proyecto en la raíz, donde
    esos bugs no se reproducen: con el bug puesto, los tests daban verde.

    No se afirma un veredicto concreto: se afirma que **todas las ubicaciones coinciden**.
    Eso detecta la clase entera sin tener que anticipar cada caso.
    """

    def _veredicto(self, donde, perturbar):
        p = Proyecto(donde=donde)
        try:
            p.implementar()
            perturbar(p)
            r = p.gate("T01")
            # El motivo, normalizado: nos importa QUÉ marcó, no el texto completo.
            motivos = sorted(l.split("✗")[1].split(":")[0].strip()
                             for l in r.stdout.split("\n") if "✗" in l)
            return (r.returncode == 0, tuple(motivos))
        finally:
            p.tirar()

    def _comparar(self, nombre, perturbar):
        vistos = {d: self._veredicto(d, perturbar) for d in UBICACIONES}
        distintos = set(vistos.values())
        self.assertEqual(len(distintos), 1,
                         f"«{nombre}» da veredictos distintos según dónde esté el proyecto:\n"
                         + "\n".join(f"    {d!r}: {v}" for d, v in vistos.items()))

    def test_proyecto_sano_igual_en_toda_ubicacion(self):
        self._comparar("proyecto sano", lambda p: None)

    def test_test_modificado_igual_en_toda_ubicacion(self):
        """La que atrapa el bug de `--relative`."""
        def perturbar(p):
            with (p.dir / "tests" / "test_cosa.py").open("a") as f:
                f.write("# colado\n")
        self._comparar("test modificado", perturbar)

    def test_gate_modificado_igual_en_toda_ubicacion(self):
        def perturbar(p):
            with (p.dir / "scripts" / "gate.sh").open("a") as f:
                f.write("# colado\n")
        self._comparar("gate modificado", perturbar)

    def test_paso4_igual_en_toda_ubicacion(self):
        """La que atrapa el bug de `git cat-file` sin prefijo."""
        def perturbar(p):
            p.git("add -A"); p.git("commit -qm impl")
            p.implementar("def f():\n    return 42\n\n\ndef g():\n    return 1\n")
        self._comparar("paso 4 sobre un archivo ya versionado", perturbar)

    def test_senal_suprimida_igual_en_toda_ubicacion(self):
        self._comparar("señal suprimida",
                       lambda p: p.implementar("def f():\n    return 42  # noqa\n"))


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


class TestVacuidad(CasoBase):
    """Un chequeo que no pudo correr no puede verse como un chequeo que pasó.

    Es la defensa publicada contra nuestra clase de falla. En métodos formales se llama
    vacuidad y tiene teoría desde 1997; en hardware tolerante a fallas es la pérdida de la
    propiedad *self-testing*, definida en 1968. Los cuatro bugs de rutas que tuvimos vivieron
    semanas detrás de un ✓ que no había mirado nada.
    """

    def test_el_paso4_sobre_un_archivo_nuevo_se_marca_vacuo(self):
        """No se puede revertir un archivo que no existía: eso NO es un pase."""
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertIn("⊘", r.stdout, "revertir un archivo nuevo no verifica nada")
        self.assertIn("nada que revertir", r.stdout)

    def test_el_paso4_sobre_un_archivo_versionado_no_es_vacuo(self):
        """Si el archivo existía, el paso 4 sí puede correr y tiene que decir qué hizo."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("def f():\n    return 42\n\n\ndef g():\n    return 1\n")
        r = self.p.gate("T01")
        self.assertNotIn("nada que revertir", r.stdout, "el archivo existía: tenía que revertir")

    def test_el_veredicto_informa_los_vacios(self):
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertIn("no pudieron correr", r.stdout,
                      "el veredicto tiene que dejar constancia de lo que no se verificó")


class TestTestigos(CasoBase):
    """Cada chequeo tiene que informar QUÉ inspeccionó, no sólo su veredicto.

    Esta clase no existe por un bug que tuvimos: existe por una **medición**. Sembramos 12
    fallas realistas en el gate con un agente que no tenía nuestra lista de bugs, y la suite
    atrapó **6 de 12**. Las seis que escaparon eran una sola clase: un chequeo que se vuelve
    no-op e imprime un mensaje plausible.

    El remedio no era agregar un caso por falla escapada —eso es sobreajustar de nuevo— sino
    exigir el testigo. Un chequeo que dice qué miró no puede volverse mudo sin que se note.
    """

    def test_informa_de_donde_sale_la_base_del_diff(self):
        """La falla sembrada 12 la cambiaba por otra y nadie se enteraba."""
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertIn("base del diff", r.stdout)
        self.assertRegex(r.stdout, r"base del diff: \w+ — (fijada por el runner|deducida)")

    def test_el_paso_0_dice_cuantas_rutas_comparo(self):
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertIn("inspeccionó:", r.stdout, "el paso 0 tiene que decir qué miró")
        self.assertRegex(r.stdout, r"inspeccionó: \d+ ruta\(s\) del diff")

    def test_el_paso_4_nombra_la_clase_que_corrio(self):
        """Las fallas 07 y 08 dejaban la clase vacía y el gate caía a la rama genérica."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("def f():\n    return 43\n")   # rompe el test: la clase falla
        r = self.p.gate("T01")
        self.assertIn("TestCosa", r.stdout,
                      "el paso 4 tiene que nombrar la clase que verificó")

    def test_el_paso_5_siempre_dice_algo_en_modo_integracion(self):
        """La falla 09 lo volvía inalcanzable y mudo: ni ✓, ni ✗, ni ⊘."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        r = self.p.gate()
        self.assertIn("5. Coherencia", r.stdout,
                      "el paso 5 no puede desaparecer sin dejar rastro")

    def test_el_paso_6_sin_suite_reservada_es_vacuo_no_informativo(self):
        """La falla 10 hacía que nunca corriera, y siempre decía 'no hay suite reservada'."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        r = self.p.gate()
        self.assertIn("6. Suite reservada", r.stdout)
        self.assertIn("⊘", r.stdout, "sin suite reservada es un vacío, no un dato de color")

    def test_el_paso_6_con_suite_reservada_informa_cuantos_archivos(self):
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        res = self.p.repo.parent / f"reservados-{self.p.dir.name}"
        res.mkdir(exist_ok=True)
        (res / "test_reservado.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertTrue(True)\n")
        try:
            r = correr("bash scripts/gate.sh", self.p.dir, TAREA="", RESERVADOS=str(res))
            self.assertIn("archivo(s) reservado(s)", r.stdout,
                          "tiene que decir cuántos archivos reservados corrió")
        finally:
            shutil.rmtree(res, ignore_errors=True)


class TestAmplitudDePatrones(CasoBase):
    """Los patrones tienen que cubrir las formas que la gente escribe de verdad.

    La falla sembrada 06 angostó el patrón de `TODO` a `TODO:` y escapó. Un testigo no
    atrapa eso: hace falta un caso por cada forma que el patrón debe cubrir.
    """

    def test_todo_en_sus_formas_habituales(self):
        # Sin `# todo pendiente`: en castellano "todo" es una palabra corriente, y poner el
        # grep insensible a mayúsculas generó un falso positivo inmediato —hasta dentro de
        # los .pyc—. El marcador es TODO en mayúsculas. La falla sembrada apuntaba a que el
        # patrón era angosto (`TODO:`), no a la caja.
        for forma in ("# TODO arreglar esto", "# TODO: arreglar", "# TODO(jose) arreglar"):
            with self.subTest(forma=forma):
                self.p.implementar(f"def f():\n    return 42  {forma}\n")
                self.assertRojo(self.p.gate("T01"), f"«{forma}» es un TODO suelto")

    def test_senales_suprimidas_en_sus_formas_habituales(self):
        for forma in ("# noqa", "# type: ignore", "  # NOQA"):
            with self.subTest(forma=forma):
                self.p.implementar(f"def f():\n    return 42  {forma}\n")
                self.assertRojo(self.p.gate("T01"), f"«{forma}» es una señal suprimida",
                                motivo="señales suprimidas")


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
