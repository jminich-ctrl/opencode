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
import re
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
    # errors="replace": npx y algunos corredores escriben bytes que no son UTF-8 válido, y
    # un test que explota al decodificar la salida no mide nada de lo que quería medir.
    return subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True,
                          errors="replace", env=e)


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
        # El gate ya no sabe correr la suite: lo sabe correr-suite.sh, y los dos van juntos.
        shutil.copy(PLANTILLAS / "correr-suite.sh", self.dir / "scripts" / "correr-suite.sh")
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

    def declarar(self, archivos):
        """Cambia el alcance de T01 y lo commitea: el archivo de tarea es de la etapa
        anterior, no del agente. Sin el commit aparecía en su propio diff."""
        self.escribir_tarea("T01", archivos)
        self.git("add -A"); self.git('commit -qm "alcance"')

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

    def test_extension_poco_comun_entra_en_el_alcance(self):
        """La lista de extensiones estaba a mano y `requirements.txt` no estaba: se caía
        fuera del alcance sin decir por qué. Una lista cerrada envejece con el primer stack
        nuevo, así que el patrón tiene que ser genérico."""
        self.p.declarar("src/cosa.py, requirements.txt")
        self.p.implementar()
        (self.p.dir / "requirements.txt").write_text("pytest\n")
        self.assertVerde(self.p.gate("T01"), "requirements.txt estaba declarado")

    def test_declarar_un_directorio_cubre_lo_de_abajo(self):
        """Los planes declaran carpetas (`backend/`), no cada archivo: sin esto, toda tarea
        que crea un archivo nuevo dentro de su propia carpeta da rojo."""
        self.p.declarar("src/")
        self.p.implementar()
        (self.p.dir / "src" / "otra.py").write_text("# hermana, dentro de src/\n")
        self.assertVerde(self.p.gate("T01"), "src/ cubre todo lo que está abajo")

    def test_el_gate_usa_el_python_que_le_pasa_el_runner(self):
        """En un worktree el .venv no viaja: si el gate no honra PY_PROYECTO cae a python3,
        no encuentra la suite y el paso 2 informa una falla que no es del agente."""
        self.p.implementar()
        marca = self.p.dir / ".uso-el-python"
        falso = self.p.dir / "py-falso"
        falso.write_text(f'#!/bin/sh\ntouch "{marca}"\nexec python3 "$@"\n')
        falso.chmod(0o755)
        self.p.gate("T01")  # el veredicto no importa acá, importa a quién llamó
        self.assertFalse(marca.exists(), "sin PY_PROYECTO no debería usarlo")
        correr("bash scripts/gate.sh", self.p.dir, TAREA="T01", PY_PROYECTO=str(falso))
        self.assertTrue(marca.exists(),
                        "el gate ignoró PY_PROYECTO y usó otro intérprete")

    def test_infraestructura_del_runner_no_cuenta_como_fuera_de_alcance(self):
        """`.base-ref` lo escribe el runner y ponía en ROJO toda tarea."""
        self.p.implementar()
        (self.p.dir / ".base-ref").write_text(
            self.p.git("rev-parse HEAD").stdout.strip() + "\n")
        self.assertVerde(self.p.gate("T01"), ".base-ref es del runner, no del agente")

    def test_el_venv_enlazado_no_cuenta_como_trabajo_del_agente(self):
        r"""El runner enlaza el venv del tronco al worktree porque gitignorado no viaja. Un
        enlace simbólico es un ARCHIVO para git, así que el patrón `\.venv/` —con barra— no
        lo matcheaba y el gate se lo contaba al agente. Lo reportó el propio agente de T01:
        «el gate muestra problemas relacionados con archivos del entorno del runner»."""
        self.p.implementar()
        (self.p.dir / ".venv").symlink_to("/usr/bin")
        self.assertVerde(self.p.gate("T01"), "el venv lo enlaza el runner, no el agente")

    def test_node_modules_instalado_no_cuenta_como_archivo_generado(self):
        """Las instala preparar-entorno.sh y AGENTS.md le prohíbe al agente correr npm:
        si aparecieran en el diff, el gate reprobaría por «archivos generados» a la tarea
        que declaró bien su manifiesto."""
        self.p.implementar()
        (self.p.dir / "frontend").mkdir(exist_ok=True)
        (self.p.dir / "frontend" / "node_modules").mkdir()
        (self.p.dir / "frontend" / "node_modules" / "algo.js").write_text("// instalado\n")
        self.assertVerde(self.p.gate("T01"), "node_modules lo instala el método")

    def test_un_directorio_vacio_da_rojo(self):
        """git no versiona directorios, sólo archivos. Un test que verifica que existe una
        carpeta pasa en el worktree del agente —donde la carpeta está— y falla en el tronco
        después del merge, porque el merge no la lleva. Pasó con T01 de clasificados:
        `backend/app/datos` existía, el gate dio VERDE, y el tronco quedó rojo. El gate no
        puede dar por bueno algo que no va a sobrevivir al commit."""
        self.p.implementar()
        (self.p.dir / "src" / "paquete").mkdir()
        self.assertRojo(self.p.gate("T01"), "una carpeta vacía no sobrevive al merge",
                        motivo="directorios vacíos")

    def test_un_directorio_con_un_archivo_no_da_rojo(self):
        self.p.declarar("src/")   # antes de implementar: declarar commitea
        self.p.implementar()
        (self.p.dir / "src" / "paquete").mkdir()
        (self.p.dir / "src" / "paquete" / "__init__.py").touch()
        self.assertVerde(self.p.gate("T01"), "con __init__.py el merge sí la lleva")

    def test_el_lock_que_genera_el_instalador_no_cuenta_como_trabajo_del_agente(self):
        """`npm install` lo corre el método y escribe `package-lock.json`; AGENTS.md le
        prohíbe al agente correr npm. T30 se rechazó por ese archivo, que generamos
        nosotros al preparar su worktree."""
        self.p.implementar()
        (self.p.dir / "frontend").mkdir(exist_ok=True)
        (self.p.dir / "frontend" / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
        self.assertVerde(self.p.gate("T01"), "el lock lo escribe el instalador")

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


class TestLineaBaseDeTests(CasoBase):
    """El método es tests-first: al empezar una etapa el tronco tiene los tests de todas sus
    tareas y la implementación de ninguna. Si el gate de cada tarea exigiera la suite entera
    en verde, **ninguna tarea podría cerrar** —la vería roja por los tests de sus hermanas—.
    Lo que se exige es lo que la tarea sí controla: que sus tests pasen y que no rompa nada
    que andaba. La línea base la escribe el runner antes de que el agente empiece.
    """

    def hermana_fallando(self):
        """Un test de otra tarea de la misma etapa, sin su implementación."""
        (self.p.dir / "tests" / "test_hermana.py").write_text(
            "import unittest\nfrom src.hermana import g\n\n"
            "class TestHermana(unittest.TestCase):\n"
            "    def test_g(self):\n        self.assertEqual(g(), 1)\n")
        self.p.git("add -A"); self.p.git('commit -qm "tests de la etapa"')

    def fijar_base(self):
        r = correr("bash scripts/correr-suite.sh --fallas", self.p.dir)
        (self.p.dir / ".tests-base").write_text(r.stdout)
        return r.stdout

    def test_la_falla_de_una_hermana_no_reprueba_a_esta_tarea(self):
        self.hermana_fallando()
        base = self.fijar_base()
        self.assertIn("test_hermana", base, "la hermana tiene que estar en la línea base")
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertVerde(r, "los tests de T01 pasan; la hermana ya fallaba")
        self.assertIn("línea base", r.stdout, "el veredicto tiene que decir qué dejó pasar")

    def test_el_propio_test_fallando_si_reprueba(self):
        """Lo que la línea base NO puede tapar: los tests de la tarea misma."""
        self.hermana_fallando()
        self.fijar_base()
        # Sin implementar src/cosa.py, el test de T01 sigue rojo.
        (self.p.dir / "src" / "otra.py").write_text("# algo, para que haya cambios\n")
        self.p.declarar("src/")
        self.assertRojo(self.p.gate("T01"), "su propio test sigue rojo",
                        motivo="los tests de T01 siguen fallando")

    def test_romper_un_test_que_andaba_si_reprueba(self):
        """La otra mitad de la regla: la línea base es un conjunto, no un permiso. El test
        de la tarea puede estar en verde y el de al lado roto por lo mismo que ella cambió.
        """
        self.p.declarar("src/")
        self.p.implementar("def f():\n    return 42\n\n\ndef h():\n    return 7\n")
        (self.p.dir / "tests" / "test_vecino.py").write_text(
            "import unittest\nfrom src.cosa import h\n\n"
            "class TestVecino(unittest.TestCase):\n"
            "    def test_h(self):\n        self.assertEqual(h(), 7)\n")
        self.p.git("add -A"); self.p.git('commit -qm "todo verde"')
        self.assertEqual(self.fijar_base().strip(), "", "la línea base arranca vacía")

        # El "agente" deja su propio test en verde y se lleva puesto el del vecino.
        self.p.implementar("def f():\n    return 42\n")
        r = self.p.gate("T01")
        self.assertRojo(r, "f() sigue bien y h() desapareció",
                        motivo="rompiste tests que andaban")
        # El id lo nombra el corredor: con un import roto, unittest informa el módulo.
        self.assertIn("test_vecino", r.stdout, "tiene que decir cuál rompió")


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


class TestContabilidadDelVeredicto(CasoBase):
    """Invariantes sobre la SALIDA del gate, no sobre un chequeo en particular.

    Salieron de medir la tasa de captura con mutantes mecánicos (`pruebas/mutar-gate.py`):
    de 20 mutantes del gate, la suite mataba 9. Tres de los sobrevivientes eran
    `FALLOS=$((FALLOS+0))` y borrados de una línea de chequeo entera, y el remedio no es un
    caso por sobreviviente —eso es sobreajustar de nuevo— sino un invariante que mate la
    familia: **lo que el veredicto cuenta tiene que ser lo que el gate imprimió.**
    """

    def marcas(self, salida):
        rojas = len([l for l in salida.splitlines() if l.startswith("  ✗ ")])
        vacias = len([l for l in salida.splitlines() if l.startswith("  ⊘ ")])
        return rojas, vacias

    def declarado(self, salida):
        """Lo que dice la línea del veredicto: (fallos, vacíos)."""
        fallos = vacios = 0
        for l in salida.splitlines():
            m = re.match(r"GATE ROJO \((\d+) fallo", l)
            if m:
                fallos = int(m.group(1))
            m = re.match(r"GATE VERDE — con (\d+) chequeo", l)
            if m:
                vacios = int(m.group(1))
        return fallos, vacios

    def escenarios(self):
        """Varias configuraciones, para que el invariante se mida en más de una forma."""
        yield "tarea sin implementar", lambda: None, "T01"
        yield "tarea implementada", lambda: self.p.implementar(), "T01"
        yield "modo integración", lambda: self.p.implementar(), None
        def suprimida():
            self.p.implementar("def f():\n    return 42  # noqa\n")
        yield "con señal suprimida", suprimida, "T01"
        def test_tocado():
            self.p.implementar()
            t = self.p.dir / "tests" / "test_cosa.py"
            t.write_text(t.read_text() + "# tocado\n")
        yield "con un test tocado", test_tocado, "T01"

    def test_el_veredicto_cuenta_exactamente_las_marcas_impresas(self):
        for nombre, preparar, tarea in self.escenarios():
            with self.subTest(escenario=nombre):
                self.setUp()
                try:
                    preparar()
                    r = self.p.gate(tarea)
                    rojas, vacias = self.marcas(r.stdout)
                    f_dicho, v_dicho = self.declarado(r.stdout)
                    if rojas:
                        self.assertEqual(f_dicho, rojas,
                                         f"imprimió {rojas} ✗ y el veredicto dice {f_dicho}"
                                         f"\n{r.stdout}")
                        self.assertNotEqual(r.returncode, 0, "con ✗ no puede salir 0")
                    else:
                        self.assertEqual(r.returncode, 0, f"sin ✗ tiene que salir 0\n{r.stdout}")
                        self.assertEqual(v_dicho, vacias,
                                         f"imprimió {vacias} ⊘ y el veredicto dice {v_dicho}"
                                         f"\n{r.stdout}")
                finally:
                    self.tearDown()

    def test_ningun_paso_anunciado_queda_sin_marca(self):
        """Un paso que se anuncia y no imprime nada es un chequeo que se borró sin que el
        veredicto cambie: tres de los mutantes que sobrevivieron eran exactamente eso."""
        for nombre, preparar, tarea in self.escenarios():
            with self.subTest(escenario=nombre):
                self.setUp()
                try:
                    preparar()
                    salida = self.p.gate(tarea).stdout
                    paso, marcas, huerfanos = None, 0, []
                    for l in salida.splitlines():
                        if l.startswith("── "):
                            if paso is not None and marcas == 0:
                                huerfanos.append(paso)
                            paso, marcas = l.strip(), 0
                        elif l.startswith(("  ✓ ", "  ✗ ", "  ⊘ ", "  · ")):
                            marcas += 1
                    if paso is not None and marcas == 0:
                        huerfanos.append(paso)
                    self.assertEqual(huerfanos, [],
                                     f"pasos que no dijeron nada: {huerfanos}\n{salida}")
                finally:
                    self.tearDown()


class TestPaso5PorElGate(CasoBase):
    """El paso 5 —coherencia— sólo estaba probado llamando a `_arquitectura.py` a mano.

    Lo destapó la medición de mutantes: `FALLOS=$((FALLOS+1))` del paso 5 podía pasar a
    `FALLOS+0` y los 74 casos seguían en verde. Es decir, el chequeo de arquitectura podía
    fallar sin poner el gate en rojo y nadie se enteraba. El hueco no era un caso: era un
    paso entero sin cobertura a través del gate.
    """

    def test_sin_arquitectura_el_paso_5_es_vacuo(self):
        self.p.implementar()
        r = self.p.gate()          # modo integración: el paso 5 sólo corre ahí
        self.assertIn("── 5. Coherencia", r.stdout)
        self.assertIn("⊘", r.stdout.split("── 5.")[1].split("── 6.")[0],
                      f"sin _arquitectura.py el paso 5 no pudo verificarse\n{r.stdout}")

    def test_una_divergencia_de_capas_pone_el_gate_en_rojo(self):
        shutil.copy(PLANTILLAS / "_arquitectura.py", self.p.dir / "scripts" / "_arquitectura.py")
        a = self.p.dir / "scripts" / "_arquitectura.py"
        t = a.read_text().replace('CAPAS = ["datos", "servicios", "rutas"]',
                                  'CAPAS = ["datos", "rutas"]')
        t = t.replace('REQUERIDAS = [\n    ("servicios", "datos"),   # la lógica usa la capa de datos\n'
                      '    ("rutas", "servicios"),   # los endpoints no hablan con datos directamente\n]',
                      'REQUERIDAS = []')
        a.write_text(t)
        (self.p.dir / "src" / "datos.py").write_text("from .rutas import x\n")
        (self.p.dir / "src" / "rutas.py").write_text("")
        self.p.implementar()
        self.p.git("add -A"); self.p.git('commit -qm arq')
        r = self.p.gate()
        self.assertNotEqual(r.returncode, 0,
                            f"datos importa rutas: el gate tiene que dar rojo\n{r.stdout}")
        self.assertIn("divergencia", r.stdout, "y tiene que decir por qué")


class TestContratoDeLaSuite(CasoBase):
    """El gate frente a cada código de salida de `correr-suite.sh`.

    Los códigos son contrato (0/1/2/3/127) y cada uno tiene un veredicto distinto; el 3 y el
    127 además tienen que decir que el defecto es del método y no del código juzgado. Se
    prueba con un doble que sale con el código que queremos: así se recorren todas las ramas
    sin necesitar un proyecto roto de cada forma. Mató al mutante que convertía el «falta el
    corredor» en verde — una suite que no se puede correr informada como si hubiera corrido.
    """

    def con_codigo(self, codigo, texto="salida del doble"):
        doble = self.p.dir / "scripts" / "correr-suite.sh"
        doble.write_text(f'#!/usr/bin/env bash\necho "{texto}"\nexit {codigo}\n')
        self.p.implementar()
        return self.p.gate("T01")

    def test_codigo_2_es_rojo_y_dice_que_no_corrio_nada(self):
        self.assertRojo(self.con_codigo(2), "una suite vacía pasa siempre",
                        motivo="no corrió ningún test")

    def test_codigo_3_es_rojo_y_dice_que_es_del_metodo(self):
        r = self.con_codigo(3)
        self.assertRojo(r, "sin corredor no se verifica nada", motivo="falta el corredor")
        self.assertIn("del método", r.stdout,
                      "tiene que decir de quién es el defecto, o se lo cobran al agente")

    def test_codigo_127_es_rojo_y_dice_que_falta_el_archivo(self):
        (self.p.dir / "scripts" / "correr-suite.sh").unlink()
        self.p.implementar()
        self.assertRojo(self.p.gate("T01"), "sin correr-suite.sh no hay un solo comando",
                        motivo="no declara cómo se corre su suite")

    def test_codigo_1_es_rojo(self):
        self.assertRojo(self.con_codigo(1), "la suite falla")

    def test_codigo_0_es_verde_en_el_paso_1(self):
        r = self.con_codigo(0, "3 passed")
        self.assertIn("── 1. Tests", r.stdout)
        self.assertIn("  ✓ ", r.stdout.split("── 2.")[0], f"el paso 1 tenía que estar verde\n{r.stdout}")


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

    def test_estado_distinto_entre_tabla_y_archivo_da_rojo(self):
        """El deductor de etapas lee la columna de la tabla y `estado.sh` lee la línea del
        archivo. T01 de clasificados se integró, quedó verde en el tronco, y la etapa 1 la
        volvía a lanzar: `integrar.sh` marcaba sólo el archivo."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("**Estado:** pendiente", "**Estado:** ✅ hecha"))
        self.assertRojo(self.validar(), "el archivo dice hecha y la tabla pendiente",
                        motivo="la da por hecha y el otro no")

    def test_la_ayuda_de_la_linea_de_estado_no_cuenta_como_hecha(self):
        """La línea trae «← al mergearla: `✅ hecha`» como ayuda, y el ✅ de la ayuda hacía
        que toda tarea pendiente se leyera como hecha. Un chequeo que marca 27 de 28 es un
        chequeo que se ignora."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "**Estado:** pendiente",
            "**Estado:** pendiente   ← al mergearla: `✅ hecha`"))
        self.assertVerde(self.validar(), "el ✅ está en la ayuda, no en el valor")

    def test_alcance_del_archivo_distinto_de_la_tabla_da_rojo(self):
        """Dos declaraciones de lo mismo que leen dos lectores: el deductor de etapas usa
        la tabla para encontrar choques de archivo, y el gate usa el archivo de tarea para
        juzgar el alcance. En clasificados divergían en todo el frontend —la tabla decía
        `Login.jsx` y la tarea `Login.vue`, en un proyecto React—."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("**Archivos que podés tocar:** src/cosa.py",
                                           "**Archivos que podés tocar:** src/cosa.ts"))
        self.assertRojo(self.validar(), "la tabla dice .py y la tarea .ts",
                        motivo="no declaran los mismos archivos")

    def test_nombre_pelado_no_cuenta_como_divergencia(self):
        """La tabla del pacman dice `laberinto.py` donde la tarea dice
        `src/pacman/laberinto.py`: es el mismo archivo y marcarlo sería ruido."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace("**Archivos que podés tocar:** src/cosa.py",
                                           "**Archivos que podés tocar:** cosa.py"))
        self.assertVerde(self.validar(), "es la abreviatura de la misma ruta")

    def test_tarea_que_pide_un_archivo_que_nadie_tiene_asignado_da_rojo(self):
        """T03 declaraba `001_initial.sql` y su contrato le pedía además escribir
        `001_inicial_down.sql`. El agente hizo lo correcto —escribir la reversa que le
        pedían— y el chequeo de alcance lo reprobó por eso."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        c = t.read_text().replace(
            "## Objetivo\n\nQue haya una cosa.",
            "## Objetivo\n\nQue haya una cosa.\n\n## Contrato\n\n"
            "La cosa va en `src/cosa.py` y **tiene que tener su reversa**: un "
            "`src/cosa_reversa.py` que la deshaga.")
        t.write_text(c)
        self.assertRojo(self.validar(), "nadie tiene asignado cosa_reversa.py",
                        motivo="nadie lo va a escribir")

    def test_tarea_que_nombra_el_archivo_de_otra_tarea_no_da_rojo(self):
        """Nombrar el módulo de otra tarea es cómo se describe una interfaz."""
        plan = self.p.dir / "PLAN.md"
        plan.write_text(plan.read_text().replace(
            "| T01 | Una cosa | — | src/cosa.py | pendiente |",
            "| T01 | Una cosa | — | src/cosa.py | pendiente |\n"
            "| T02 | Otra | T01 | src/otra.py | pendiente |"))
        self.p.escribir_tarea("T02", "src/otra.py")
        (self.p.dir / "tareas" / "T02-cosa.md").write_text(
            (self.p.dir / "tareas" / "T02-cosa.md").read_text().replace(
                "**Depende de:** —", "**Depende de:** T01"))
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "## Objetivo\n\nQue haya una cosa.",
            "## Objetivo\n\nQue haya una cosa.\n\n## Contrato\n\n"
            "`src/otra.py` la va a usar; no la toques."))
        self.assertVerde(self.validar(), "src/otra.py es de T02, nombrarla es legítimo")

    def test_tarea_que_declara_un_intocable_da_rojo(self):
        """Una tarea que declara lo que el gate prohíbe es insatisfacible.

        El plan permite lo que el gate prohíbe, así que ningún agente puede cerrarla y la
        tarea quema GPU hasta el punto muerto. Nadie cruzaba esos dos componentes: lo
        encontramos con dos tareas de 28 en el segundo ejemplo, y después con diez de
        diecinueve en el primero —las viejas, de cuando el agente escribía los tests—.
        """
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "**Archivos que podés tocar:** src/cosa.py",
            "**Archivos que podés tocar:** src/cosa.py, tests/test_cosa.py"))
        self.assertRojo(self.validar(), "declara un archivo intocable",
                        motivo="insatisfacible")

    def test_tarea_que_declara_scripts_da_rojo(self):
        """El caso peor: pedirle al agente el verificador que lo juzga.

        El arquitecto, solo, planificó una tarea para que el agente escribiera
        `scripts/_arquitectura.py`. Viola el corolario de P2 —el comando del veredicto tiene
        que ser inmodificable por quien es juzgado— y además era insatisfacible.
        """
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "**Archivos que podés tocar:** src/cosa.py",
            "**Archivos que podés tocar:** scripts/_arquitectura.py"))
        self.assertRojo(self.validar(), "declara scripts/", motivo="insatisfacible")

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


class TestEjemplosNoDerivan(unittest.TestCase):
    """Los ejemplos son copias adaptadas de la plantilla, y la copia se queda vieja: el
    arreglo del extractor de alcance entró en la plantilla y los dos ejemplos siguieron
    con el patrón roto hasta que alguien lo notó a mano.

    No comparamos texto —los ejemplos ADAPTAN líneas a propósito— sino **conducta**: el
    motor de alcance de cada gate tiene que dar el mismo veredicto, por el mismo motivo.
    Si mañana hay un tercer ejemplo, entra solo."""

    GATES = sorted([PLANTILLAS / "gate.sh"] + list(RAIZ.glob("ejemplo-*/scripts/gate.sh")))

    def montar(self, gate, declara, archivos):
        """Repo de juguete con la forma mínima que cualquiera de los gates acepta."""
        repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-drift-"))
        self.addCleanup(shutil.rmtree, str(repo), True)
        d = repo / "proyecto"
        for sub in ("tareas", "scripts", "permitido", "colado"):
            (d / sub).mkdir(parents=True)
        shutil.copy(gate, d / "scripts" / "gate.sh")
        shutil.copy(gate.parent / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "tareas" / "T01-cosa.md").write_text(
            f"# T01 — Una cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            f"**Archivos que podés tocar:** {declara}\n**Prohibido tocar:** tests/\n")
        correr("git init -q && git add -A && git commit -qm base", repo)
        for ruta, cuerpo in archivos.items():
            p = d / ruta
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(cuerpo)
        return correr("bash scripts/gate.sh", d, TAREA="T01")

    def test_todos_detectan_un_archivo_fuera_del_alcance(self):
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                r = self.montar(gate, "permitido/", {"permitido/ok.py": "x = 1\n",
                                                     "colado/mal.py": "x = 2\n"})
                self.assertIn("fuera del alcance", r.stdout,
                              f"no vio el archivo colado\n{r.stdout[-900:]}")
                self.assertIn("colado/mal.py", r.stdout, "no dijo cuál")

    def test_en_todos_el_extractor_de_alcance_lee_la_tarea(self):
        """El patrón mal escapado dejaba PERMITIDOS vacío: el gate acusaba a la tarea de
        no declarar alcance cuando sí lo declaraba. Rojo por el motivo equivocado."""
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                r = self.montar(gate, "permitido/, permitido/requirements.txt",
                                {"permitido/ok.py": "x = 1\n",
                                 "permitido/requirements.txt": "pytest\n"})
                self.assertNotIn("no declara", r.stdout,
                                 f"no pudo leer el alcance declarado\n{r.stdout[-900:]}")
                self.assertIn("dentro del alcance", r.stdout,
                              f"declaró todo y aun así no pasó el paso de alcance\n{r.stdout[-900:]}")

    def test_en_todos_la_suite_corre_desde_la_raiz_del_proyecto(self):
        """El validador de `escribir-tests.sh` corre la suite desde la raíz del proyecto.
        Si un gate la corre desde otro directorio, un test validado en un cwd se juzga en
        otro y hay tests imposibles de pasar: el de scaffolding de clasificados chequeaba
        `backend/app/datos` y en el gate resolvía a `backend/backend/app/datos`.

        Se mide con una canaria que anota su propio `os.getcwd()`: no leemos el texto del
        gate, lo dejamos correr y vemos desde dónde corrió."""
        # TestCase y no una función: `unittest discover` sólo junta clases, y pytest
        # junta las dos. Así la misma canaria sirve para los tres corredores.
        canaria = ("import os\nimport pathlib\nimport unittest\n\n\n"
                   "class TestCanaria(unittest.TestCase):\n"
                   "    def test_anota_el_cwd(self):\n"
                   "        pathlib.Path(os.environ['CANARIA']).write_text(os.getcwd())\n")
        # El corredor tiene que existir o el gate dice —con razón— que falta la herramienta
        # y la canaria no corre. Si no hay ninguno con pytest, lo decimos fuerte.
        venvs = sorted(RAIZ.glob("ejemplo-*/.venv/bin/python"))
        py_con_pytest = next(
            (str(v) for v in venvs
             if subprocess.run([str(v), "-c", "import pytest"], capture_output=True).returncode == 0),
            None)
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-cwd-"))
                self.addCleanup(shutil.rmtree, str(repo), True)
                d = repo / "proyecto"
                marca = repo / "cwd.txt"
                # En los dos layouts a la vez: cada gate va a descubrir el que mira.
                for sub in ("tests", "backend/tests", "tareas", "scripts", "src", "backend/app"):
                    (d / sub).mkdir(parents=True, exist_ok=True)
                for sub in ("tests", "backend/tests"):
                    (d / sub / "__init__.py").touch()
                    (d / sub / "test_canaria.py").write_text(canaria)
                shutil.copy(gate, d / "scripts" / "gate.sh")
                shutil.copy(gate.parent / "correr-suite.sh",
                            d / "scripts" / "correr-suite.sh")
                correr("git init -q && git add -A && git commit -qm base", repo)
                extra = {"PY_PROYECTO": py_con_pytest} if py_con_pytest else {}
                r = correr("bash scripts/gate.sh", d, CANARIA=str(marca), **extra)
                if not marca.exists():
                    if "falta su corredor" in r.stdout and not py_con_pytest:
                        self.fail("no hay ningún python con pytest en los ejemplos, así que "
                                  "este chequeo no puede correr. No es un pase: instalá el "
                                  "corredor (bash scripts/preparar-entorno.sh) y repetilo.")
                    self.fail("la canaria no corrió: el chequeo quedaría vacuo, y un "
                              f"chequeo que no corre no es un chequeo que pasa\n{r.stdout[-900:]}")
                self.assertEqual(marca.read_text(), str(d.resolve()),
                                 "la suite corrió desde otro directorio que la raíz del "
                                 "proyecto: un test validado en un cwd se juzga en otro")

    def test_nadie_mas_que_correr_suite_sabe_correr_la_suite(self):
        """La invocación de la suite vive en UN archivo. Mientras el gate y el validador de
        `escribir-tests.sh` tenían cada uno la suya, diferían en el cwd, el PYTHONPATH, el
        corredor y sus flags, y **cada diferencia producía un test imposible de pasar** que
        el método informaba como «el test está mal».

        Esto es un chequeo de texto y no de conducta a propósito: la conducta ya la mide la
        canaria de cwd, y lo que falta impedir es que alguien vuelva a escribir el comando
        en otro lado. Si aparece, la canaria lo detecta sólo si además cambia el cwd."""
        CORREDORES = re.compile(r"-m\s+(pytest|unittest)|npx[^|\n]*vitest|\bjest\b")
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                suite = gate.parent / "correr-suite.sh"
                self.assertTrue(suite.exists(),
                                f"falta {suite.relative_to(RAIZ)}: el gate devuelve 127 y el "
                                f"proyecto no declara cómo se corre su suite")
                # La suite reservada es la excepción, y es de principio: vive FUERA del
                # repo para que ningún agente la vea, así que no puede correrse por un
                # script del proyecto —que el agente lee y podría cambiar—. El paso 6 la
                # invoca directo a propósito.
                sueltos = [l.strip() for l in gate.read_text().splitlines()
                           if CORREDORES.search(l) and not l.strip().startswith("#")
                           and "RESERVADOS" not in l]
                self.assertEqual(sueltos, [],
                                 "el gate invoca un corredor de tests por su cuenta en vez "
                                 "de pasar por correr-suite.sh:\n  " + "\n  ".join(sueltos))
        validador = (SCRIPTS / "escribir-tests.sh").read_text()
        sueltos = [l.strip() for l in validador.splitlines()
                   if CORREDORES.search(l) and not l.strip().startswith("#")]
        self.assertEqual(sueltos, [],
                         "escribir-tests.sh arma su propio comando de tests:\n  "
                         + "\n  ".join(sueltos))

    def test_el_codigo_de_salida_de_la_suite_esta_en_el_contrato(self):
        """0/1/2/3/127 y nada más. `correr-suite.sh` usa 9 como centinela interno de «esta
        mitad no tiene nada que correr», para combinar backend y frontend cuando se pide la
        suite entera; pedido UN archivo, ese 9 se escapaba. El gate lo caía en «la suite
        está en rojo» y el validador en «el test está mal»: dos diagnósticos falsos para una
        situación que el contrato ya sabe nombrar."""
        CONTRATO = {0, 1, 2, 3, 127}
        SELECTORES = ["", "tests/noexiste.py", "tests/noexiste.py::NoExiste",
                      "frontend/tests/noexiste.test.ts", "backend/tests/noexiste.py",
                      "cosa.rb"]
        for gate in self.GATES:
            suite = gate.parent / "correr-suite.sh"
            if not suite.exists():
                continue
            for sel in SELECTORES:
                with self.subTest(proyecto=str(gate.parent.relative_to(RAIZ)), sel=sel or "(toda)"):
                    r = correr(f'bash {suite} {sel}', gate.parent.parent)
                    self.assertIn(r.returncode, CONTRATO,
                                  f"devolvió {r.returncode}, que no está en el contrato\n"
                                  f"{r.stdout[-400:]}")

    def test_en_todos_un_chequeo_que_no_corre_se_marca_vacuo(self):
        """La regla que no se adapta: ⊘ nunca puede confundirse con ✓."""
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                fuente = gate.read_text()
                self.assertIn("VACIOS=$((VACIOS+1))", fuente, "el ejemplo perdió vacuo()")
                self.assertIn("exit 1", fuente, "el ejemplo perdió la salida en rojo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
