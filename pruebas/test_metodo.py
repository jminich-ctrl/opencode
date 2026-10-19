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
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
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
        # El gate también depende de estos dos: si faltan, da rojo y lo dice.
        shutil.copy(PLANTILLAS / "_suprimidas.py", self.dir / "scripts" / "_suprimidas.py")
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
        # `ignore_errors=True` se tragaba la falla y dejaba el directorio: los objetos de git
        # son de sólo lectura (444) y `rmtree` no los puede borrar sin cambiarles el permiso.
        # La suite dejó 147 directorios temporales en un día de corridas, y el `ignore_errors`
        # hacía que nadie se enterara — un `rm` que falla en silencio es la misma clase de
        # problema que un chequeo que no puede correr y dice que pasó.
        def forzar(func, ruta, _exc):
            try:
                os.chmod(ruta, 0o700)
                func(ruta)
            except OSError:
                pass

        shutil.rmtree(self.repo, onerror=forzar)


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
            # El motivo tiene que estar en una línea MARCADA como falla, no en cualquier
            # parte de la salida. Lo destapó medir mutantes: cambiar `rojo "rompiste tests
            # que andaban"` por `verde "..."` dejaba el mensaje impreso, el gate rojo por
            # otra cosa, y este assert pasaba. Es decir, la exigencia de «rojo por el motivo
            # correcto» se podía satisfacer con el motivo informado en VERDE.
            marcadas = [l for l in r.stdout.splitlines() if l.startswith("  ✗ ")]
            self.assertTrue(any(motivo in l for l in marcadas),
                            f"dio rojo, pero «{motivo}» no aparece en ninguna línea ✗\n"
                            f"líneas ✗: {marcadas}\n{r.stdout[-800:]}")

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

    def test_un_archivo_de_andamiaje_fuera_del_alcance_apunta_al_plan(self):
        """Cuando lo que se fue del alcance huele a andamiaje de test, lo más probable es que
        el criterio de terminado lo esté pidiendo: pasó con T06, cuyo criterio pedía un router
        de prueba que su propio alcance prohibía. El gate no puede decidirlo, pero sí puede
        decir dónde mirar en vez de dejar al agente como único acusado."""
        self.p.implementar()
        (self.p.dir / "src" / "test_sonda.py").write_text("# router de prueba\n")
        r = self.p.gate("T01")
        self.assertRojo(r, "el archivo no está en el alcance", motivo="fuera del alcance")
        self.assertIn("Revisá el criterio de terminado", r.stdout,
                      f"tiene que mandar a mirar el plan, no sólo culpar al agente\n{r.stdout}")

    def test_un_archivo_cualquiera_fuera_del_alcance_no_culpa_al_plan(self):
        """Y la otra mitad: un archivo que no parece andamiaje no insinúa nada del plan.
        Una pista que aparece siempre no es una pista."""
        self.p.implementar()
        (self.p.dir / "src" / "colado.py").write_text("# no va\n")
        r = self.p.gate("T01")
        self.assertRojo(r, "el archivo no está en el alcance", motivo="fuera del alcance")
        self.assertNotIn("Revisá el criterio de terminado", r.stdout,
                         "no hay motivo para sospechar del plan acá")

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

    def test_un_except_vacio_en_varias_lineas_da_rojo(self):
        """La forma más común de apagar una señal en Python ocupa tres líneas y el grep por
        línea no la veía:

            except Exception:
                # un comentario que explica por qué está bien
                pass

        Pasó en serio. El `main.py` de T06 montaba los routers así —citando mi propio texto
        de la tarea para justificarlo— y un módulo de rutas roto quedaba sin montar en
        silencio: el síntoma era un 404 donde el test esperaba un 400, que no se parece en
        nada a su causa. Es la vacuidad otra vez: «no pude» disfrazado de «no hay nada».
        """
        shutil.copy(PLANTILLAS / "_suprimidas.py", self.p.dir / "scripts" / "_suprimidas.py")
        self.p.declarar("src/")
        self.p.implementar("def f():\n"
                           "    try:\n"
                           "        return 42\n"
                           "    except Exception:\n"
                           "        # si falla no importa\n"
                           "        pass\n")
        self.assertRojo(self.p.gate("T01"), "el except se come la falla",
                        motivo="señales suprimidas")

    def test_un_except_que_hace_algo_no_da_rojo(self):
        """La otra mitad: manejar una excepción no es suprimir una señal."""
        shutil.copy(PLANTILLAS / "_suprimidas.py", self.p.dir / "scripts" / "_suprimidas.py")
        self.p.declarar("src/")
        self.p.implementar("def f():\n"
                           "    try:\n"
                           "        return 42\n"
                           "    except ValueError as e:\n"
                           "        raise RuntimeError('no pude') from e\n")
        r = self.p.gate("T01")
        self.assertNotIn("señales suprimidas:", r.stdout,
                         f"relanzar no es suprimir\n{r.stdout}")

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


class TestPortabilidadBash32(unittest.TestCase):
    """macOS trae bash 3.2 y el método escribe sus mensajes en castellano, con «comillas».

    En bash 3.2 una variable pegada a un carácter multibyte se come sus bytes como parte
    del nombre: `"«$x»"` da «unbound variable» y `"«${x}»"` anda. Con `set -u` eso no es un
    mensaje mal impreso: **aborta el script**. Pasó en `escribir-tests.sh` justo después de
    que el agente escribiera bien su test, y la etapa se detuvo por el diagnóstico, no por
    el defecto.

    Es un chequeo estático y no de conducta a propósito: la condición es sintáctica, y
    probarla por conducta pediría una rama de error por cada mensaje.
    """

    PEGADA = re.compile(rb"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7F]")

    def scripts(self):
        for d in ("scripts", "plantillas", "pruebas"):
            yield from sorted((RAIZ / d).glob("*.sh"))
        for d in sorted(RAIZ.glob("ejemplo-*/scripts")):
            yield from sorted(d.glob("*.sh"))

    def test_ninguna_variable_pegada_a_un_caracter_multibyte(self):
        malos = []
        for f in self.scripts():
            datos = f.read_bytes()
            for m in self.PEGADA.finditer(datos):
                linea = datos[:m.start()].count(b"\n") + 1
                malos.append(f"{f.relative_to(RAIZ)}:{linea} — "
                             f"{m.group(0).decode('utf-8', 'replace')}")
        self.assertEqual(malos, [],
                         "en bash 3.2 esto es «unbound variable» y con set -u aborta.\n"
                         "Poné llaves: ${var}.\n  " + "\n  ".join(malos))

    def test_la_reproduccion_minima_sigue_siendo_valida(self):
        """Si una versión futura de bash dejara de hacerlo, el chequeo de arriba sobra y
        conviene saberlo en vez de arrastrarlo."""
        sin_llaves = correr('set -u; x=hola; echo "«$x»"', RAIZ)
        con_llaves = correr('set -u; x=hola; echo "«${x}»"', RAIZ)
        self.assertIn("hola", con_llaves.stdout, "con llaves tiene que andar")
        if sin_llaves.returncode == 0:
            self.skipTest("este bash ya no se come el carácter multibyte: "
                          "revisá si el chequeo estático sigue haciendo falta")


class TestElGateManda(unittest.TestCase):
    """P2 en el mensaje, no sólo en el veredicto.

    T06, T07 y T27 cerraron en verde y se integraron, y la pantalla decía «✗ ERROR del
    agente» por una línea que el agente había impreso al correr npm. El veredicto estaba
    bien; el mensaje decía lo contrario. Un método que predica «el juez es un comando» y
    después informa un error del modelo por encima del comando se contradice donde una
    persona lo lee, y eso erosiona lo único que el método necesita: que el veredicto se crea.
    """

    def log(self, parte_del_agente, rc):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-log-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        p = d / ".tarea.log"
        p.write_text(f"=== T01\n{parte_del_agente}\n=== gate ===\nsalida\n=== rc={rc}\n"
                     f"=== fin T01 · hoy\n")
        return p

    def consultar(self, p, funcion):
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; {funcion} "{p}"', RAIZ).stdout.strip()

    def test_un_error_que_imprimio_un_comando_no_es_falla_de_la_herramienta(self):
        p = self.log("Error: Cannot find native binding. npm has a bug...", rc=0)
        self.assertEqual(self.consultar(p, "error_del_agente"), "",
                         "es la salida de npm, no una falla de la herramienta")
        self.assertEqual(self.consultar(p, "veredicto"), "VERDE")

    def test_una_falla_real_de_la_herramienta_si_se_reconoce(self):
        for linea in ("inference timed out after 600s",
                      "database is locked",
                      "el agente no respondió: inactividad 90s"):
            with self.subTest(linea=linea):
                p = self.log(linea, rc=1)
                self.assertNotEqual(self.consultar(p, "error_del_agente"), "",
                                    f"«{linea}» sí es una falla de la herramienta")

    def test_el_gate_verde_manda_sobre_el_ruido_del_log(self):
        p = self.log("inference timed out after 600s", rc=0)
        self.assertEqual(self.consultar(p, "veredicto"), "VERDE",
                         "si el gate pudo decidir, decide el gate (P2)")


class TestPlataformaCaida(unittest.TestCase):
    """Un 502 de la plataforma no es una falla de la tarea ni del agente.

    Pasó: la API pasó de responder en 3s a devolver 502 en TODO —incluido `/models`— y el
    método lo informaba como «el test no pasa ni con la implementación del propio agente»,
    que es el diagnóstico más lejano posible de la causa. Y peor: reintentaba, gastando el
    presupuesto de cada tarea contra algo que no iba a cambiar por insistir.
    """

    def consultar(self, url):
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; plataforma_responde; echo "rc=$?"',
                      RAIZ, COLABHIVE_BASE_URL=url, COLABHIVE_API_KEY="x")

    def test_una_url_que_no_responde_se_informa(self):
        # Puerto cerrado en loopback: curl falla y el código queda en 000.
        r = self.consultar("http://127.0.0.1:9/v1")
        self.assertIn("rc=1", r.stdout, "tiene que decir que no responde")
        self.assertIn("no responde", r.stderr + r.stdout,
                      "y decir que no es la tarea ni el agente")

    def test_sin_plataforma_configurada_no_opina(self):
        """Si el proyecto no usa esta plataforma, el chequeo no aplica y no puede frenar
        nada: un chequeo que opina sobre algo que no está configurado es un falso rojo."""
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; unset COLABHIVE_BASE_URL; '
                   f'plataforma_responde; echo "rc=$?"', RAIZ)
        self.assertIn("rc=0", r.stdout)

    def test_el_502_se_reconoce_como_falla_de_la_plataforma(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-502-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text("=== T01\nError: Bad Gateway\n=== gate ===\nx\n=== rc=1\n"
                       "=== fin T01 · hoy\n")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; error_del_agente "{log}"', RAIZ)
        self.assertIn("Bad Gateway", r.stdout,
                      "un 502 es una falla de la plataforma, no del test")

    def test_el_stream_cortado_a_la_mitad_se_reconoce(self):
        """El cuelgue del día entero era esto, y tardé el día entero en verlo porque el
        vigilante lo tapaba: la plataforma corta el stream a mitad de la generación y
        devuelve `upstream stream ended without a complete EOS handshake`. Es una falla de
        la plataforma —el agente ya estaba trabajando— y no tiene que gastar intentos."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-eos-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text('=== T06\n> ejecutor\nError: {"message":"upstream stream ended '
                       'without a complete EOS handshake","type":"api_error"}\n'
                       '=== gate ===\nx\n=== rc=1\n=== fin T06 · hoy\n')
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; error_del_agente "{log}"', RAIZ)
        self.assertIn("stream", r.stdout.lower(),
                      "un stream cortado por la plataforma no es culpa del agente")


class TestRetomarPorNumeroNoSaltaTrabajo(unittest.TestCase):
    """Los números de etapa NO son estables entre corridas, y retomar por número saltaba
    trabajo en silencio.

    Las etapas se deducen del grafo de dependencias sobre las tareas **pendientes**. En
    cuanto una etapa cierra, las que siguen se corren un lugar. Pasó: la etapa 1 era
    «T06a T08» y la 2 «T06b T12 T29»; al cerrar la 1, la 2 pasó a ser la 1 y «T06c» a ser
    la 2. Retomé con `correr-todo.sh 2` creyendo que seguía donde había quedado y salté
    T06b, T12 y T29 **sin un solo aviso**.

    El argumento existe para retomar después de arreglar algo, que es legítimo. Lo que no
    puede es saltar tareas pendientes callado: si las etapas que se saltean tienen trabajo
    sin hacer, hay que decirlo y parar.
    """

    def test_correr_todo_avisa_si_saltea_tareas_pendientes(self):
        texto = (SCRIPTS / "correr-todo.sh").read_text()
        # Específico a propósito: la primera versión de este test matcheaba un comentario
        # sobre G3 que ya estaba, así que pasaba sin que hubiera chequeo alguno. Un test
        # que pasa contra el código sin arreglar no prueba nada — es la falla que el propio
        # método persigue en los tests que escriben los agentes.
        self.assertIn(
            "SALTEADAS", texto,
            "correr-todo.sh N no comprueba si las etapas anteriores a N tienen tareas "
            "pendientes: los números se recalculan en cada corrida y saltar trabajo en "
            "silencio es la peor forma de fallar")


class TestLaHuellaLlevaElDatoNoLaCategoria(unittest.TestCase):
    """El motivo que recibe el reintento tiene que decir QUÉ falló, no de qué tipo fue.

    T08 tocó su propio archivo de test, el gate lo frenó —bien— y el reintento recibió
    sólo «✗ tocó archivos intocables (tests o el propio gate):», con los dos puntos y nada
    detrás. El gate imprime cuál archivo en la línea siguiente y la huella la descartaba.
    Le dijimos «tocaste algo intocable» sin decirle qué, y repitió exactamente lo mismo.

    `escribir-tests.sh` ya tenía esta lección escrita en un comentario —«el motivo lleva el
    fallo real, no su categoría… se vio: T02 falló dos veces por lo mismo recibiendo sólo
    *el test está mal*»— y el otro camino no la había aprendido.
    """

    def test_la_huella_incluye_el_detalle_del_gate(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text(
            "=== T08\nalgo\n=== gate ===\n"
            "── 0. Integridad\n"
            "  ✗ tocó archivos intocables (tests o el propio gate):\n"
            "     frontend/tests/test_ads_frontend.test.ts\n"
            "GATE ROJO (2 fallo/s)\n=== rc=1\n=== fin T08 · hoy\n")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_de_falla "{log}"', RAIZ)
        self.assertIn(
            "test_ads_frontend", r.stdout,
            "la huella se queda con la categoría y tira el dato: el reintento no sabe qué "
            f"archivo tocó. Dijo: {r.stdout!r}")

    def test_dos_fallas_distintas_dan_huellas_distintas(self):
        """Y el dato tiene que distinguir: si la próxima vez toca OTRO archivo, es otra
        falla y el reintento vale la pena. Con la categoría sola, todo es la misma."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella2-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        huellas = []
        for archivo in ("frontend/tests/uno.test.ts", "backend/tests/otro.py"):
            log = d / f"{archivo.replace('/', '_')}.log"
            log.write_text(f"=== T08\n=== gate ===\n"
                           f"  ✗ tocó archivos intocables (tests o el propio gate):\n"
                           f"     {archivo}\nGATE ROJO\n=== rc=1\n")
            huellas.append(correr(
                f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_de_falla "{log}"',
                RAIZ).stdout.strip())
        self.assertNotEqual(huellas[0], huellas[1],
                            "tocar dos archivos distintos da la misma huella: el método "
                            "lo va a leer como punto muerto cuando no lo es")


class TestNingunaTareaPendienteTieneSuCodigoHecho(unittest.TestCase):
    """Una tarea pendiente cuyo código ya está commiteado no puede cerrar, y el método no
    lo detectaba: lo descubría el agente, a los veinte minutos, y lo informaba mal.

    Pasó con `backend/app/main.py`: una corrida vieja lo integró con gate verde, después la
    tarea se reabrió y se partió en tres, y el archivo quedó. Las tres partes figuraban
    pendientes con su implementación ya en HEAD.

    Por qué no puede cerrar: el método es tests-first y su validador exige que el test
    **falle** al revertir la implementación del agente. Si la implementación ya está en
    HEAD, el agente no toca nada, no hay nada que revertir, y el paso no se puede evaluar.
    El agente de turno leyó el archivo, vio la tarea hecha, y **declaró haber escrito un
    test que nunca escribió** — la única falta que AGENTS.md dice que invalida todo.

    Es barato de detectar antes de gastar una corrida: es mirar la tabla del plan contra
    `git ls-files`.
    """

    def test_no_acusa_a_una_tarea_que_modifica_lo_que_otra_creo(self):
        """Y el chequeo no puede ser más estricto que la realidad: una tarea que MODIFICA
        un archivo que otra tarea ya terminada creó es el caso normal, no un problema.

        La primera versión de este chequeo acusaba a T11, T12 y T18 por `AdsList.jsx`,
        que existe porque T08 —✅ hecha— lo creó. Eso habría frenado el plan entero por un
        falso rojo, que es exactamente la clase de defecto que este chequeo vino a evitar.

        La distinción: el archivo es un problema sólo si **ninguna tarea terminada lo
        declara**. Si una hecha lo declara, su existencia está explicada.
        """
        texto = (SCRIPTS / "validar-plan.py").read_text()
        self.assertRegex(
            texto, r"hecha|terminada|declarad[oa] por",
            "el chequeo de código-ya-commiteado no exime a los archivos que una tarea ya "
            "terminada declara: va a acusar a toda tarea que modifique trabajo anterior")

    def test_el_validador_del_plan_lo_detecta(self):
        texto = (SCRIPTS / "validar-plan.py").read_text()
        self.assertIn(
            "ya está commiteado", texto,
            "validar-plan.py no cruza las tareas pendientes contra los archivos que ya "
            "están en git: una tarea con su código hecho no puede cerrar tests-first, y "
            "el método lo descubre tarde y lo informa mal")


class TestUnaTareaSePuedePartir(unittest.TestCase):
    """Partir una tarea en T06a / T06b / T06c no estaba soportado: todo el método deduce
    el id con `T\\d+`, sólo dígitos, así que las tres colapsaban en «T06» y el validador
    informaba «T06 tiene más de un archivo» y «T04 depende de una tarea que no está».

    Importa porque **partir una tarea es la respuesta correcta a un defecto real**: la
    nuestra tenía 114 líneas y 7 criterios contra las 44–87 y 2–4 de todas las que cerraron,
    y el agente gastaba el presupuesto entero deliberando sin escribir. Si el método no
    soporta partir, la única salida que deja es renumerar el plan entero o escribir el test
    a mano — las dos peores que la correcta.
    """

    def test_el_sufijo_de_letra_es_parte_del_id(self):
        import re
        malos = []
        for f in sorted(list(SCRIPTS.glob("*.py")) + list(SCRIPTS.glob("*.sh"))):
            texto = f.read_text()
            for n, linea in enumerate(texto.split("\n"), 1):
                if linea.lstrip().startswith("#"):
                    continue
                # Un patrón de id que no acepta sufijo de letra parte las subtareas.
                if re.search(r"T\\d\+(?!\[a-z\])", linea) or re.search(r"T\[0-9\]\+(?!\[a-z\])", linea):
                    malos.append(f"{f.name}:{n}")
        self.assertEqual(
            malos, [],
            f"estos patrones de id no aceptan subtareas (T06a): {malos}. Partir una tarea "
            f"grande es la respuesta correcta a un defecto del plan, y el método tiene que "
            f"poder expresarla")


class TestElGateDicePorQueFallaNoSoloCual(unittest.TestCase):
    """Tercera aparición de la misma lección, en un tercer lugar del método.

    El gate informaba «los tests de T06c siguen fallando: ERROR test_errores.py» — qué
    falla, nunca por qué. El reintento recibía eso y volvía a escribir el mismo código. La
    causa real era de una línea: `from fastapi import RequestValidationError`, cuando vive
    en `fastapi.exceptions`. Dos intentos gastados por un dato que estaba en la salida de
    la suite y el gate no mostraba.

    Ya estaba aprendida en `escribir-tests.sh` («el motivo lleva el fallo real, no su
    categoría») y en `huella_de_falla` (el detalle del gate). Esta es la tercera copia del
    mismo defecto en otro camino.
    """

    def test_el_veredicto_incluye_el_error_real(self):
        for gate in [RAIZ / "plantillas" / "gate.sh"] + sorted(RAIZ.glob("ejemplo-*/scripts/gate.sh")):
            self.assertRegex(
                gate.read_text(), r"PRIMER_ERROR|primer error|por qué falla",
                f"{gate.relative_to(RAIZ)} informa qué tests fallan y no por qué: el "
                f"reintento no tiene nada nuevo con lo que trabajar")

    def test_la_normalizacion_no_mutila_el_id_de_la_tarea(self):
        """«T06c» salía como «TNc» en el mensaje que lee el agente. La normalización de
        números existe para que dos fallas iguales con contadores distintos den la misma
        huella; no para romper los identificadores."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-norm-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text("=== T06c\n=== gate ===\n"
                       "  ✗ los tests de T06c siguen fallando:\n"
                       "     ERROR backend/tests/test_errores.py\n"
                       "GATE ROJO\n=== rc=1\n")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_de_falla "{log}"', RAIZ)
        self.assertIn("T06c", r.stdout,
                      f"la huella mutila el id de la tarea. Dijo: {r.stdout!r}")


class TestNoSeEditanScriptsConUnaCorridaActiva(unittest.TestCase):
    """El método lo tiene escrito en «Tres cosas que muerden»: nunca edites un script de
    bash mientras corre. Bash lee el archivo por posición mientras ejecuta, así que
    insertar líneas en un script en curso le puede hacer ejecutar basura.

    Lo rompí yo, con la regla a la vista, editando `correr-tarea.sh` mientras ese mismo
    script corría una tarea. Una regla que vive sólo en un documento es una regla que se
    incumple: si el método puede detectarlo, tiene que detectarlo.
    """

    def test_hay_un_chequeo_que_lo_impide(self):
        texto = (SCRIPTS / "correr-todo.sh").read_text()
        self.assertIn(
            "corrida activa", texto,
            "nada impide lanzar una corrida nueva ni avisa que hay una en curso: dos "
            "corridas sobre los mismos worktrees se pisan, y editar un script mientras "
            "corre le hace ejecutar basura")


class TestElTranscriptDelFalloSeConserva(unittest.TestCase):
    """El worktree se borra y se recrea en cada reintento, y con él se va el transcript del
    intento que falló — que es el único lugar donde está escrito POR QUÉ falló.

    Hoy lo perdí cuatro veces. Cada vez que quise saber qué había hecho el agente tuve que
    reproducirlo a mano en un worktree aparte, veinte minutos por vez. Y cuando por fin
    conseguí leer uno, la causa estaba ahí en una sola línea: el modelo decía que la tarea
    se contradecía con el pedido.

    Es el mismo defecto que el del vigilante que cortaba antes del error, con otro
    mecanismo: **el método destruye la evidencia de sus propias fallas.** El log del intento
    fallido se guarda antes de recrear el worktree, y el mensaje dice dónde quedó.
    """

    def test_todo_script_que_recrea_un_worktree_guarda_el_log(self):
        """Generalizado: lo arreglé en escribir-tests.sh y no en correr-tarea.sh, y volví a
        perder el transcript de un fallo en el otro camino. Arreglar un lado y no el otro
        es el patrón que este repo repite; el test tiene que cubrir los dos."""
        culpables = []
        for s in sorted(SCRIPTS.glob("*.sh")):
            texto = s.read_text()
            recrea = "worktree add" in texto and ("rm -rf" in texto or "worktree remove" in texto)
            # `conservar_intento` (en _comun.sh) es el que guarda, y guarda el transcript Y el
            # parche. Antes cada script hacía su propio `cp` del log, y esa duplicación es
            # justo lo que hizo perder un transcript: se arregló un lado y no el otro.
            conserva = "fallidos-" in texto or "conservar_intento" in texto
            if recrea and not conserva:
                culpables.append(s.name)
        self.assertEqual(
            culpables, [],
            f"{culpables} recrean el worktree sin conservar el transcript del intento "
            f"anterior: la única constancia de por qué falló se pierde justo cuando hace "
            f"falta")


class TestElArchivoDeTareaNoSeContradiceConLaFase(unittest.TestCase):
    """El MISMO archivo de tarea lo leen dos fases, y decía algo cierto sólo en una.

    Las 29 tareas traían «Los tests de esta tarea **ya están en el repo y fallan**». Es
    cierto cuando le toca al agente que implementa —los tests se escriben antes— y es
    **falso** para el agente que los escribe, que recibe el mismo archivo. El modelo lo
    dijo con todas las letras en su transcript: «the task says the tests already exist and
    are failing, but the user is asking me to write both the implementation and the
    tests». Y entonces no los escribió.

    Horas de T06 fallando por una frase que era verdad en la otra mitad del proceso.

    La regla: **un documento que leen dos fases no puede afirmar el estado de una sola.**
    O se escribe en términos que valgan en las dos, o dice de qué fase habla.
    """

    def test_ninguna_tarea_afirma_que_los_tests_ya_existen(self):
        culpables = []
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            for f in sorted((proyecto / "tareas").glob("*.md")) if (proyecto / "tareas").is_dir() else []:
                texto = f.read_text()
                afirma = ("ya están en el repo y fallan" in texto
                          or "ya escritos, fallando" in texto)
                # La afirmación es válida si viene con su condición: «si te toca
                # implementar, ya están… si te toca escribirlos, todavía no existen».
                # Lo que no puede es afirmarse a secas, porque entonces es falsa para
                # una de las dos fases que leen este mismo archivo.
                aclara = "todavía no existen" in texto
                if afirma and not aclara:
                    culpables.append(str(f.relative_to(RAIZ)))
        self.assertEqual(
            culpables[:5], [],
            f"{len(culpables)} tarea(s) afirman que sus tests ya existen. El agente que "
            f"los ESCRIBE lee el mismo archivo y se frena ante la contradicción. "
            f"Primeras: {culpables[:5]}")

    def test_el_prompt_de_escribir_tests_aclara_la_fase(self):
        """Y aunque el archivo esté bien redactado, el prompt tiene que dejar claro que
        esta corrida es la que los crea: es la única señal que el agente tiene de en qué
        mitad del proceso está."""
        texto = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertRegex(
            texto, r"todavía no existen|no existen todavía|los estás creando|sos vos quien",
            "el prompt no le dice al agente que en esta fase los tests todavía no existen")


class TestLaMemoriaEsParteDelEquipo(unittest.TestCase):
    """Medido sobre nuestras propias fallas, cuatro modelos, diseño A/B/C:

        A sin memoria        6/24  (25%)
        B memoria correcta  18/24  (75%)
        C memoria de otra    6/24  (25%)   ← mismo largo, compra CERO

    C ≡ A dice que lo que sube es el contenido y no el texto. Y el dato que cambia la
    economía del método: **CodeScout-1.7B pasa de 1/6 a 5/6 con memoria correcta, y supera
    al 30B sin memoria (2/6)**. Veníamos eligiendo entre modelos que se mueven de 2 a 3
    sobre 6, cuando la variable que mueve de 1 a 5 era otra.

    La memoria que funciona es la **verificada**: la que lleva el veredicto de un comando
    que puede reprobar. Memoria equivocada no es apenas inútil —en el experimento de
    opt-cf los errores confiados no bajaron con memoria mezclada—. Y eso el método ya lo
    produce en cada corrida y lo tira.

    Dos mitades, y faltan las dos: EMITIR el registro y ENTREGÁRSELO al agente.
    """

    def test_el_metodo_emite_el_registro(self):
        hay = any("memoria" in s.read_text() for s in SCRIPTS.glob("*.sh"))
        self.assertTrue(
            hay, "ningún script escribe el registro de la falla y su arreglo: el veredicto "
                 "se imprime en un log y se tira, que es tirar la única memoria que mide "
                 "bien (B 75% contra A 25%)")

    def test_el_registro_llega_al_agente(self):
        texto = (SCRIPTS / "correr-tarea.sh").read_text()
        self.assertIn(
            "memoria", texto,
            "correr-tarea.sh no le entrega al agente los registros de fallas anteriores "
            "sobre los archivos que va a tocar: una memoria que no llega es como no tenerla")


class TestElMetodoSabeReplanificar(unittest.TestCase):
    """Cuando una tarea falla por cómo está escrita, el método dice «se repiensa la tarea»
    y para esperando a una persona. Esa persona fui yo, y reescribí tres enunciados hasta
    que el agente pudo: así el número de autonomía no mide el método, mide cuánto lo
    empujé.

    El método tiene un agente `arquitecto` justamente para planificar y ningún camino que
    lo use. Esto es ese camino: toma la tarea fallada y su transcript, se lo da al
    arquitecto, y **sólo acepta el resultado si el plan sigue validando** — el juez es un
    comando, igual que en todo lo demás (P2).

    Lo que NO puede hacer es ablandar la tarea para que pase: los criterios de terminado y
    el archivo de test que declara el plan no se tocan.
    """

    def test_existe_el_camino_de_replanificacion(self):
        s = SCRIPTS / "replanificar.sh"
        self.assertTrue(s.exists(),
                        "no hay scripts/replanificar.sh: cuando una tarea falla por su "
                        "enunciado, el método depende de que una persona lo reescriba")

    def test_el_resultado_pasa_por_el_validador(self):
        s = (SCRIPTS / "replanificar.sh").read_text() if (SCRIPTS / "replanificar.sh").exists() else ""
        self.assertIn("validar-plan.py", s,
                      "replanificar.sh acepta lo que escriba el arquitecto sin cruzarlo "
                      "contra el plan: el juez tiene que ser un comando")

    def test_no_informa_exito_si_no_cambio_nada(self):
        """Un verde vacuo en el script escrito para mejorar el método.

        Los tres chequeos que puse —criterios, archivo de test, plan válido— pasan
        TRIVIALMENTE cuando el arquitecto no escribe nada. Y eso fue lo que pasó: leyó,
        razonó bien, nunca llamó a write, y el script informó «✓ T04 replanificada y el
        plan sigue validando» sobre cero líneas de diff.

        Es la falla que el método entero existe para atrapar —un chequeo que no puede
        fallar no es un chequeo— cometida en el chequeo mismo. Tercera vez en el día.
        """
        s = (SCRIPTS / "replanificar.sh").read_text() if (SCRIPTS / "replanificar.sh").exists() else ""
        self.assertRegex(
            s, r"no cambió|sin cambios|diff --quiet|cmp -s",
            "replanificar.sh informa éxito aunque el arquitecto no haya escrito nada: "
            "los tres chequeos pasan trivialmente sobre un archivo intacto")

    def test_el_motivo_sale_de_la_ultima_falla_y_dice_la_fase(self):
        """El arquitecto replanificó dos tareas con un diagnóstico falso porque le pasé
        todos los ✗ de todos los transcripts, incluidos los de hace horas. Se enganchó con
        uno obsoleto. Y le faltaba el dato que lo habría orientado: QUÉ fase falló — si fue
        la que escribe los tests, el archivo de test no existe y el enunciado dice que sí,
        porque está escrito para la fase siguiente."""
        s = (SCRIPTS / "replanificar.sh").read_text() if (SCRIPTS / "replanificar.sh").exists() else ""
        self.assertIn("ls -t", s,
                      "el motivo junta todos los transcripts en vez del último: le da al "
                      "arquitecto señales viejas que ya no aplican")
        self.assertIn("FASE", s,
                      "el motivo no dice en qué fase falló, y el estado del mundo es "
                      "distinto en cada una")

    def test_no_puede_ablandar_los_criterios(self):
        s = (SCRIPTS / "replanificar.sh").read_text() if (SCRIPTS / "replanificar.sh").exists() else ""
        self.assertRegex(
            s, r"criterios|Criterio de terminado",
            "nada impide que el arquitecto achique los criterios de terminado para que la "
            "tarea pase: replanificar no puede ser bajar la vara")


class TestLaSeccionDeTestsNoEsTrabajoDelQueImplementa(unittest.TestCase):
    """Material de una fase en un documento que leen las dos: el mismo defecto que la
    contradicción de «los tests ya existen», con otra forma.

    A T06b y T06c les puse un esqueleto de código de test en la sección «Tests» —helpers de
    recarga, rutas de sonda— para ahorrarle al agente el razonamiento caro. Funcionó para
    quien escribe los tests. Pero el archivo de tarea lo lee también quien IMPLEMENTA, y
    para él un bloque de código bajo «Tests» se lee como trabajo pendiente: lo escribió en
    el archivo de test, que tiene prohibido tocar, y el gate lo reprobó tres veces.

    Agregar la regla a AGENTS.md fue necesario y no suficiente: mientras el documento le
    muestre código que parece faltarle, la instrucción implícita gana.
    """

    def test_la_seccion_tests_avisa_de_qué_fase_es(self):
        faltan = []
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            d = proyecto / "tareas"
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.md")):
                texto = f.read_text()
                if "## Tests" in texto and "no es trabajo tuyo" not in texto:
                    faltan.append(str(f.relative_to(RAIZ)))
        self.assertEqual(
            faltan[:5], [],
            f"{len(faltan)} tarea(s) tienen una sección «Tests» que no aclara de qué fase "
            f"es: quien implementa la lee como trabajo pendiente. Primeras: {faltan[:5]}")


class TestLasReglasDurasLleganAlAgente(unittest.TestCase):
    """Las reglas que el método llama innegociables vivían SÓLO en el AGENTS.md de la raíz,
    y el agente lee el del proyecto.

    Tres violaciones del mismo día, las tres prohibidas en un archivo que el agente no abre:

    - T08 editó su propio archivo de test. Prohibido en «Reglas duras»: *no toques un test
      para que pase*.
    - T06c hizo lo mismo.
    - Y antes, un agente declaró haber escrito un test que nunca escribió. Prohibido en
      «Antes de decir que terminaste»: *nunca digas que corriste algo que no corriste*.

    Las tres son faltas que el método considera graves, y ninguna de las tres le había sido
    comunicada. Culpar al modelo por incumplir una regla que no recibió es el mismo error
    que vengo cometiendo todo el día con otros nombres.
    """

    INNEGOCIABLES = ("## Reglas duras", "## Antes de decir que terminaste")

    def test_cada_proyecto_tiene_las_reglas_duras(self):
        faltan = []
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            if not (proyecto / "tareas").is_dir():
                continue
            texto = (proyecto / "AGENTS.md").read_text() if (proyecto / "AGENTS.md").exists() else ""
            for s in self.INNEGOCIABLES:
                if s not in texto:
                    faltan.append(f"{proyecto.name}: falta «{s}»")
        self.assertEqual(
            faltan, [],
            f"el agente lee el AGENTS.md del PROYECTO, no el de la raíz: {faltan}")

    def test_la_plantilla_tambien(self):
        texto = (RAIZ / "plantillas" / "AGENTS.md").read_text()
        for s in self.INNEGOCIABLES:
            self.assertIn(s, texto,
                          f"un proyecto nuevo nacería sin «{s}»")


class TestLasReglasEstanDondeElAgenteLasBusca(unittest.TestCase):
    """`escribir-tests.sh` le dice al agente «las reglas de cómo escribir tests están en
    AGENTS.md: leelas». El agente corre con el directorio de trabajo en el PROYECTO, así
    que lee `<proyecto>/AGENTS.md` — no el de la raíz del repo.

    Lo rompí yo el mismo día: al recortar el prompt moví esas reglas al AGENTS.md de la
    raíz, que el agente no ve. Desde entonces el prompt lo mandaba a leer una convención
    que no estaba donde buscaba, y los intentos fallaban por no declarar el agrupador con
    el nombre pedido — que era justo una de las reglas que moví.

    Mismo patrón que todo el día: una declaración se mudó y el lector no la siguió.
    """

    def seccion_del_prompt(self):
        texto = (SCRIPTS / "escribir-tests.sh").read_text()
        return "AGENTS.md" in texto

    def test_cada_proyecto_tiene_las_reglas_en_su_propio_agents(self):
        if not self.seccion_del_prompt():
            self.skipTest("⊘ el prompt ya no manda a leer AGENTS.md")
        MARCA = "Si te toca escribir los tests"
        faltan = []
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            if not (proyecto / "tareas").is_dir():
                continue
            agents = proyecto / "AGENTS.md"
            if not agents.exists() or MARCA not in agents.read_text():
                faltan.append(str(agents.relative_to(RAIZ)))
        self.assertEqual(
            faltan, [],
            f"el prompt manda al agente a leer AGENTS.md y estos no tienen la sección: "
            f"{faltan}. El agente lee el del proyecto, no el de la raíz del repo")

    def test_la_plantilla_tambien(self):
        """Un proyecto nuevo arrancado de la plantilla tiene que nacer con la sección, o
        repite este defecto desde el día uno."""
        plantilla = RAIZ / "plantillas" / "AGENTS.md"
        if not plantilla.exists():
            self.skipTest("⊘ no hay plantillas/AGENTS.md")
        self.assertIn("Si te toca escribir los tests", plantilla.read_text(),
                      "la plantilla de AGENTS.md no trae las reglas de escritura de tests")


class TestLaCuraEstaConectadaAlProceso(unittest.TestCase):
    """El método tenía la cura y nadie la aplicaba.

    `sync_limits.py` existe desde hace semanas, sincroniza los `limit.context` con el
    `max_model_len` real de la plataforma, y `INFRAESTRUCTURA.md` hasta lo nombra como la
    respuesta exacta al síntoma: *400 «maximum context length» → sync_limits.py --write*.
    Pero era un paso manual de un runbook, así que no se corrió, y el día que declaré a
    mano `"context": 128000` para un modelo servido con **5312**, la etapa entera murió con
    un 400 que el método informó como «el agente no escribió el test».

    Una cura que depende de que alguien se acuerde no es parte del método: es documentación.
    """

    def test_correr_todo_verifica_los_limites_de_contexto(self):
        texto = (SCRIPTS / "correr-todo.sh").read_text()
        self.assertIn(
            "sync_limits", texto,
            "correr-todo.sh no verifica el drift de limit.context antes de arrancar. "
            "Declarar un contexto mayor que el real hace que CADA tarea muera con un 400 "
            "que no se parece a su causa")

    def test_el_400_de_contexto_se_atribuye_a_la_plataforma(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ctx-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text('=== T06\n> ejecutor\nError: {"message":"vLLM error: {\\"error\\":'
                       '{\\"message\\":\\"This model\'s maximum context length is 5312 '
                       'tokens. However, you requested 0 output tokens and your prompt '
                       'contains 6195 input tokens\\"}}","type":"api_error"}\n'
                       '=== gate ===\nx\n=== rc=1\n=== fin T06 · hoy\n')
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; error_del_agente "{log}"', RAIZ)
        self.assertIn("context", r.stdout.lower(),
                      "un 400 por contexto es de la configuración, no del agente: "
                      "informarlo como «no escribió el test» manda a buscar al lugar "
                      f"equivocado. Dijo: {r.stdout!r}")


class TestElCalentadorSigueALaConfig(unittest.TestCase):
    """`warm.sh` tenía la lista de modelos escrita a mano. En cuanto los agentes cambiaron
    de modelo, siguió calentando los viejos —incluido el que devuelve basura— y dejó frío
    al que la corrida iba a usar.

    Lo que eso produce no se parece a la causa: el modelo nuevo arranca en frío (~253s), la
    sonda de plataforma lo consulta con 45s de tope, se come un timeout, y la corrida se
    niega a empezar diciendo **«la plataforma de modelos no responde»** — con la plataforma
    perfectamente arriba, contestando `/models` en 2,3s y el 27B en 3,4s.

    Es la declaración doble de siempre: qué modelo usa cada agente está en opencode.json, y
    había una segunda copia a mano en otro archivo. La regla del método es cruzarlas; acá
    directamente se borra la copia.
    """

    def modelos_que_usan_los_agentes(self):
        import json
        cfg = json.loads((RAIZ / "colabhive" / "config" / "opencode.json").read_text())
        return {v["model"].split("/")[-1] for v in cfg.get("agent", {}).values()
                if isinstance(v, dict) and v.get("model")}

    def test_ningun_script_clava_un_modelo_que_nadie_usa(self):
        """Generalizado después de encontrar el mismo defecto dos veces en una hora.

        `warm.sh` calentaba el modelo viejo. Y la sonda de plataforma de `_comun.sh` tenía
        `MODELO_SONDA` con el mismo id clavado por omisión: consultaba el modelo roto —que
        además estaba frío y que ya ningún agente usaba—, se comía el timeout, y la corrida
        entera se negaba a empezar diciendo que la plataforma no responde.

        Un id de modelo escrito en un script es una copia de lo que declara opencode.json,
        y una copia que nadie cruza queda vieja el día que cambia el original.
        """
        import re
        usados = self.modelos_que_usan_los_agentes()
        culpables = []
        for s in sorted(list(SCRIPTS.glob("*.sh")) + list((RAIZ / "colabhive" / "scripts").glob("*.sh"))):
            for uuid in set(re.findall(
                    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                    s.read_text())):
                if uuid not in usados:
                    culpables.append(f"{s.name}: {uuid}")
        self.assertEqual(
            culpables, [],
            "estos scripts clavan un id de modelo que ningún agente usa, así que operan "
            "sobre algo que la corrida no va a tocar:\n  " + "\n  ".join(culpables))

    def test_warm_calienta_todos_los_que_los_agentes_usan(self):
        import json, re
        warm = (RAIZ / "colabhive" / "scripts" / "warm.sh").read_text()
        if not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", warm):
            return
        cfg = json.loads((RAIZ / "colabhive" / "config" / "opencode.json").read_text())
        usados = {v["model"].split("/")[-1] for v in cfg.get("agent", {}).values()
                  if isinstance(v, dict) and v.get("model")}
        faltan = sorted(m for m in usados if m not in warm)
        self.assertEqual(
            faltan, [],
            f"hay agentes cuyo modelo warm.sh no calienta: {faltan}. Van a arrancar en "
            f"frío (~253s sin imprimir nada) y el vigilante o la sonda los va a leer mal")


class TestUnTestNoPuedeClavarUnaRutaAbsoluta(unittest.TestCase):
    """Un test con una ruta absoluta no es un test: es una foto del directorio de una
    máquina en un momento.

    Pasó, y tardó dos semanas en verse. El agente de T03 escribió
    `down_file = '/Users/jose/tests-T03/ejemplo-clasificados/backend/migraciones/...'`
    —su PROPIO worktree temporal—, el gate lo aceptó porque ahí adentro pasaba, y se mergeó
    al tronco. Desde entonces ese test falla en todos lados menos en un directorio que ya
    no existe, y la línea base lo venía tapando: quedó registrado como «ya fallaba», así
    que nadie volvió a mirarlo.

    El costo real: la primera comparación válida de tres modelos candidatos salió en rojo
    para los tres por culpa de ese archivo, y durante un rato parecía que los modelos no
    sabían hacer la tarea.

    El método ya tiene la regla del cwd único —la suite corre siempre desde la raíz del
    proyecto—, así que una ruta absoluta nunca hace falta.
    """

    RUTA_ABSOLUTA = re.compile(r'[\'"](/(?:Users|home|private|tmp|var)/[^\'"\n]{4,})[\'"]')

    def test_ningun_test_del_repo_clava_una_ruta_absoluta(self):
        culpables = []
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            for f in list(proyecto.rglob("test_*.py")) + list(proyecto.rglob("*.test.ts")):
                if "node_modules" in f.parts or ".venv" in f.parts:
                    continue
                for m in self.RUTA_ABSOLUTA.finditer(f.read_text(errors="replace")):
                    culpables.append(f"{f.relative_to(RAIZ)}: {m.group(1)[:70]}")
        self.assertEqual(
            culpables, [],
            "estos tests clavan una ruta absoluta, así que sólo pueden pasar en la máquina "
            "y el directorio donde se escribieron:\n  " + "\n  ".join(culpables))

    def test_el_gate_rechaza_un_test_con_ruta_absoluta(self):
        """Y que no vuelva a entrar: el gate tiene que verlo en el diff, no la suite tres
        semanas después en otro worktree."""
        for gate in [RAIZ / "plantillas" / "gate.sh"] + sorted(RAIZ.glob("ejemplo-*/scripts/gate.sh")):
            self.assertIn(
                "ruta absoluta", gate.read_text(),
                f"{gate.relative_to(RAIZ)} no revisa rutas absolutas en los tests que juzga")


class TestLaConfigVersionadaDiceLaVerdad(unittest.TestCase):
    """`OPENCODE.md` llama a `colabhive/config/opencode.json` «el archivo real, versionado
    en este repo». Si la config que de verdad usa opencode no es ésa, el archivo versionado
    describe algo que no corre — y todo el que lo lea para entender qué modelo usa cada
    agente va a leer una mentira.

    Pasó: la copia del repo quedó dos días atrás, sin el `headerTimeout` que bajamos hoy y
    sin los dos modelos candidatos que agregamos para poder medirlos. Es la declaración
    doble de siempre, y el método ya tiene la regla: cruzá toda declaración doble.

    Si no hay config instalada, esto no se puede comprobar: ⊘, se salta diciendo por qué.
    Un chequeo que no pudo correr no es un chequeo que pasó.
    """

    def test_la_config_del_repo_es_la_que_corre(self):
        viva = pathlib.Path.home() / ".config" / "opencode" / "opencode.json"
        if not viva.exists():
            self.skipTest("⊘ no hay opencode instalado acá: nada que cruzar")
        repo = RAIZ / "colabhive" / "config" / "opencode.json"
        import json
        a, b = json.loads(repo.read_text()), json.loads(viva.read_text())
        if a == b:
            return
        difs = sorted(set(json.dumps(a, sort_keys=True).split(",")) ^
                      set(json.dumps(b, sort_keys=True).split(",")))[:6]
        self.fail(f"la config versionada y la instalada no dicen lo mismo. "
                  f"OPENCODE.md llama «el archivo real» a la del repo, así que la "
                  f"diferencia es una mentira documentada. Muestra: {difs}")


class TestTodoWorktreeJuzgadoTieneEntorno(unittest.TestCase):
    """Un worktree recién creado no tiene `.venv` ni `node_modules`, así que la suite no
    puede correr y el gate reprueba por «falta el corredor de tests» — un rojo que no es
    del agente ni del modelo.

    `correr-tarea.sh` ya lo resolvía llamando a `preparar-entorno.sh`, con el comentario
    puesto. `comparar-modelos.sh` no, y por eso su primera comparación válida dio el MISMO
    rojo a los tres modelos por un motivo que no los distinguía: midió el entorno, no los
    modelos. Es el patrón que este repo ya tiene anotado —una mejora en un lado y la
    medición rota en el otro— así que el test es estructural y no sobre un script.
    """

    def test_el_que_crea_worktree_y_juzga_prepara_el_entorno(self):
        culpables = []
        for s in sorted(SCRIPTS.glob("*.sh")):
            texto = s.read_text()
            crea = "worktree add" in texto
            juzga = "cerrar_con_gate" in texto or "gate.sh" in texto
            if crea and juzga and "preparar-entorno.sh" not in texto:
                culpables.append(s.name)
        self.assertEqual(
            culpables, [],
            f"{culpables} crean un worktree y lo juzgan con el gate sin preparar el "
            f"entorno: el gate va a reprobar por falta de corredor, y ese rojo no es del "
            f"agente")


class TestLaSeñalDeVidaNoEsElSilencio(unittest.TestCase):
    """El silencio no distingue a un agente que trabaja de uno colgado, a ningún umbral.

    Historia completa, porque el número se movió tres veces y las tres estuvieron mal:
    45s cortaba antes de que la plataforma informara su error; 90s dejó entrar el error
    pero igual cortó a un modelo que ya había hecho **22 llamadas a herramientas**. Un
    agente callado dos minutos puede estar generando un archivo largo: no hay umbral que
    separe las dos cosas, porque la variable observada no las separa.

    La que sí las separa la encontramos mirando el proceso colgado: tenía **cero
    conexiones TCP** y el hilo principal parado en `kevent64`, mientras uno que trabaja
    mantiene la conexión abierta esperando al modelo. Así que se corta por «callado **Y**
    sin conexión», no por callado.

    Y el chequeo de conexión puede no poder correr (sin `lsof`, sin permisos). Eso es ⊘:
    no se puede leer como «está vivo», porque entonces un cuelgue no se corta nunca.
    """

    def correr_vigilado(self, agente, inactividad=15, total=70, entorno=None):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-vida-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / "vigilado.log"
        log.write_text("x" * 2000)   # pasa el umbral de arranque: ventana larga
        extra = " ".join(f"{k}={v}" for k, v in (entorno or {}).items())
        return correr(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
            f'LOG_VIGILADO="{log}" INACTIVIDAD={inactividad} ARRANQUE={inactividad} '
            f'{extra} con_limite {total} {agente}; echo "rc=$?"', RAIZ)

    # Un agente callado que mantiene una conexión abierta y sigue vivo MUCHO después del
    # momento en que el vigilante decidiría cortar (~30s con INACTIVIDAD=15). Si durara
    # menos, el test pasaría porque el proceso terminó antes, no porque lo respetaran:
    # la primera versión de este test duraba 25s y pasaba con el vigilante viejo.
    # OJO con el fixture: la primera versión lanzaba `srv.accept` en un hilo y soltaba el
    # socket aceptado, así que el server lo cerraba y lsof informaba CLOSE_WAIT, no
    # ESTABLISHED. El test fallaba y la culpa parecía de la implementación. Hay que
    # guardar el socket aceptado para que la conexión siga viva.
    CON_CONEXION = (
        "python3 -c \"import socket,threading,time;"
        "srv=socket.socket();srv.bind(('127.0.0.1',0));srv.listen(1);vivos=[];"
        "threading.Thread(target=lambda: vivos.append(srv.accept()),daemon=True).start();"
        "c=socket.create_connection(srv.getsockname());time.sleep(55)\"")

    def test_un_agente_callado_con_conexion_abierta_no_se_corta(self):
        r = self.correr_vigilado(self.CON_CONEXION)
        self.assertIn("rc=0", r.stdout,
                      "estuvo 55s callado pero con la conexión abierta: estaba esperando "
                      f"al modelo, no colgado. Salida: {r.stdout!r} {r.stderr[-300:]!r}")

    def test_un_agente_callado_sin_conexion_si_se_corta(self):
        r = self.correr_vigilado("sleep 60")
        self.assertIn("rc=142", r.stdout,
                      "callado y sin ninguna conexión abierta: eso es un cuelgue y hay "
                      "que cortarlo")

    def test_si_no_se_puede_mirar_la_conexion_se_corta_igual(self):
        """⊘ aplicado al vigilante: un chequeo que no pudo correr no dice «está vivo».
        Si lo dijera, un cuelgue en una máquina sin `lsof` no se cortaría nunca."""
        r = self.correr_vigilado("sleep 60", entorno={"LSOF": "/no/existe/lsof"})
        self.assertIn("rc=142", r.stdout,
                      "sin poder mirar conexiones hay que volver a la regla del silencio, "
                      "no suponer que está trabajando")


class TestElComparadorNoSeCuelga(unittest.TestCase):
    """`comparar-modelos.sh` existe para elegir modelo midiendo, y lo primero que uno le
    pide a un candidato nuevo es que capaz esté roto. Lanzaba los agentes en paralelo
    SIN límite de tiempo: con un modelo que se cuelga —que es el caso que el comparador
    tiene que detectar— la comparación no termina nunca y no informa nada.

    Un instrumento que no sobrevive al defecto que vino a medir no mide ese defecto.
    """

    def test_el_comparador_limita_el_tiempo_de_cada_agente(self):
        texto = (SCRIPTS / "comparar-modelos.sh").read_text()
        self.assertIn("con_limite", texto,
                      "lanza `opencode run` sin límite: un modelo colgado deja la "
                      "comparación corriendo para siempre")

    def test_el_comparador_informa_por_qué_se_cortó(self):
        """Si corta sin decir si fue silencio o límite total, el resultado «✗ error» no
        distingue un modelo lento de uno roto, que es justo lo que se está midiendo."""
        texto = (SCRIPTS / "comparar-modelos.sh").read_text()
        self.assertIn("motivo_del_corte", texto,
                      "corta pero no informa el motivo del corte")


class TestElVigilanteNoTapaLaEvidencia(unittest.TestCase):
    """La regla que costó un día entero.

    El vigilante de inactividad cortaba a los 45s de silencio. La plataforma tarda **68,4s**
    (medido, tres corridas) en informar que cortó el stream. O sea que durante todo un día
    el vigilante mató el proceso 23 segundos antes de que la herramienta imprimiera el
    diagnóstico, y el error `upstream stream ended without a complete EOS handshake` no
    aparece ni una vez en ningún log del día. Yo no estaba diagnosticando un cuelgue: estaba
    destruyendo la prueba de qué era.

    De ahí la regla general: **un vigilante tiene que perder siempre la carrera contra el
    informe de error de la herramienta que vigila.** Si corta antes, no observa un sistema:
    lo fabrica.
    """

    MARGEN = 20  # sobre los 68,4s medidos

    def test_la_ventana_no_se_redeclara_en_otro_lado(self):
        """Tres copias del mismo número: _comun.sh lo declaraba y escribir-tests.sh y
        correr-tarea.sh lo volvían a declarar con el valor VIEJO (45). Mientras el de
        _comun.sh estuviera seteado no se notaba, que es justamente cómo sobreviven estas
        copias hasta el día que importan."""
        import re
        culpables = []
        for s in sorted(SCRIPTS.glob("*.sh")):
            if s.name == "_comun.sh":
                continue
            for m in re.finditer(r"(INACTIVIDAD|ARRANQUE|UMBRAL_ARRANQUE)\s*=\s*[\"']?\$?\{?\1?:?-?(\d+)",
                                 s.read_text()):
                culpables.append(f"{s.name}: {m.group(1)}={m.group(2)}")
        self.assertEqual(culpables, [],
                         f"la ventana del vigilante se declara en _comun.sh y nada más; "
                         f"estas copias van a quedar viejas: {culpables}")

    def test_la_ventana_de_inactividad_deja_hablar_a_la_herramienta(self):
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; echo "${{INACTIVIDAD:-45}}"', RAIZ)
        ventana = int(r.stdout.strip() or 0)
        self.assertGreaterEqual(
            ventana, 68 + self.MARGEN,
            f"la ventana es {ventana}s y la plataforma tarda 68,4s en informar un stream "
            f"cortado: con esta ventana el error nunca se imprime y el cuelgue queda sin "
            f"causa para siempre")

    def test_un_corte_por_silencio_avisa_que_puede_haber_tapado_un_error(self):
        """Aunque la ventana sea generosa, cortar sigue siendo destruir evidencia. El
        mensaje tiene que decirlo, o el que lo lea va a creer que no había nada que leer."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-tapa-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / "vigilado.log"
        log.write_text("x")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'LOG_VIGILADO="{log}" INACTIVIDAD=15 UMBRAL_ARRANQUE=0 '
                   f'con_limite 120 sleep 90; motivo_del_corte "{log}"', RAIZ)
        self.assertIn("inactividad", r.stdout,
                      "el motivo tiene que decir que cortó el silencio, no el límite total")
        self.assertRegex(
            r.stdout, r"sin ver|pudo haber|no llegó",
            "el corte tiene que avisar que la herramienta puede no haber alcanzado a "
            f"informar su propio error; dijo: {r.stdout!r}")


class TestLimiteDeTiempo(unittest.TestCase):
    """Un agente colgado detiene la corrida para siempre, y eso es peor que un error: un
    error se reintenta, un cuelgue no se nota. Pasó: `opencode run` se quedó 31 minutos con
    el log en 0 bytes mientras la API del modelo respondía en 3 segundos.

    macOS no trae `timeout`, así que el límite lo pone perl con `alarm`. 142 es SIGALRM.
    """

    def correr_con_limite(self, segundos, comando):
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; con_limite {segundos} {comando}',
                      RAIZ)

    def test_un_comando_colgado_se_corta(self):
        r = self.correr_con_limite(1, "sleep 30")
        self.assertEqual(r.returncode, 142,
                         f"tenía que cortar por tiempo y salir 142, salió {r.returncode}")

    def test_el_silencio_se_corta_antes_que_el_limite_total(self):
        """Lo que distingue un cuelgue de un agente lento no es el tiempo total: es el
        silencio. El de opencode termina su propio log en `init` y no escribe más, mientras
        un agente que trabaja escribe todo el tiempo. Con un solo reloj total hay que elegir
        entre cortar rápido y no cortar a quien trabaja; con el de inactividad no."""
        log = pathlib.Path(tempfile.mkdtemp(prefix="prueba-vigilia-")) / "salida.log"
        self.addCleanup(shutil.rmtree, str(log.parent), True)
        log.write_text("")
        t0 = time.time()
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; con_limite 600 sleep 600',
                   RAIZ, LOG_VIGILADO=str(log), INACTIVIDAD=30)
        tardo = time.time() - t0
        self.assertEqual(r.returncode, 142, "el silencio tenía que cortarlo")
        self.assertLess(tardo, 120, f"tardó {tardo:.0f}s: el límite total es 600, así que "
                                    f"cortó por el total y no por el silencio")

    def test_el_motivo_del_corte_dice_cual_reloj_fue(self):
        """Informar «no respondió en 1200s» cuando se lo cortó a los 90 por silencio manda a
        buscar un problema de lentitud que no existe. Pasó, y es el mismo defecto que vengo
        arreglando todo el día: un mensaje con el motivo equivocado."""
        log = pathlib.Path(tempfile.mkdtemp(prefix="prueba-motivo-")) / "salida.log"
        self.addCleanup(shutil.rmtree, str(log.parent), True)
        log.write_text("")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'con_limite 600 sleep 600 >/dev/null 2>&1; motivo_del_corte "{log}"',
                   RAIZ, LOG_VIGILADO=str(log), INACTIVIDAD=30)
        self.assertIn("inactividad", r.stdout,
                      f"cortó por silencio y tiene que decirlo\n{r.stdout}")
        self.assertNotIn("600", r.stdout, "no fue el límite total")

    def test_un_proceso_que_escribe_no_se_corta(self):
        """La otra mitad, que es la que hace útil al reloj: mientras haya salida, no se toca.
        Sin este caso, bajar el umbral de inactividad hasta que 'funcione' mataría a los
        agentes lentos y nadie se enteraría."""
        log = pathlib.Path(tempfile.mkdtemp(prefix="prueba-vigilia2-")) / "salida.log"
        self.addCleanup(shutil.rmtree, str(log.parent), True)
        log.write_text("")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'con_limite 600 bash -c \'for i in 1 2 3 4; do echo x >> {log}; sleep 10; done\'',
                   RAIZ, LOG_VIGILADO=str(log), INACTIVIDAD=25)
        self.assertEqual(r.returncode, 0,
                         "escribía cada 10s con umbral de 25s: no se podía cortar")

    def test_un_comando_que_termina_no_se_toca(self):
        r = self.correr_con_limite(30, "echo listo")
        self.assertEqual(r.returncode, 0)
        self.assertIn("listo", r.stdout)

    def test_el_codigo_de_salida_del_comando_se_respeta(self):
        r = self.correr_con_limite(30, "sh -c 'exit 3'")
        self.assertEqual(r.returncode, 3, "el límite no puede cambiar el veredicto")


class TestImportsDePython(CasoBase):
    """El espejo en Python del chequeo de imports de JS.

    Lo dejé sin hacer un rato porque pensé que pedía mantener a mano la lista de módulos de
    la biblioteca estándar, que es larga y cambia por versión. `sys.stdlib_module_names` la
    trae: el chequeo que parecía caro costaba una línea. Lo habría atrapado al toque —el
    agente de T04 importó `mysql.connector` donde el proyecto declara `pymysql`— y el
    síntoma fue un ModuleNotFoundError que el método informó como «el test está mal».
    """

    def preparar(self, requirements, codigo):
        # `declarar` commitea, así que va ANTES de escribir lo que la tarea tiene que hacer:
        # si no, no queda ningún cambio y el gate da rojo por «la tarea no se hizo».
        # El chequeo es parte del verificador y va commiteado ANTES: si entra después del
        # commit, el gate lo ve como un archivo fuera del alcance de la tarea —y tiene razón—.
        shutil.copy(PLANTILLAS / "_imports.py", self.p.dir / "scripts" / "_imports.py")
        self.p.declarar("src/, requirements.txt")
        (self.p.dir / "requirements.txt").write_text(requirements)
        (self.p.dir / "src" / "cosa.py").write_text(codigo)

    def test_un_import_no_declarado_da_rojo(self):
        self.preparar("pymysql==1.1.0\n", "import mysql.connector\n\n\ndef f():\n    return 42\n")
        self.assertRojo(self.p.gate("T01"), "mysql no está en requirements",
                        motivo="importa paquetes que los requirements no declaran")

    def test_la_biblioteca_estandar_no_se_declara(self):
        self.preparar("pymysql==1.1.0\n",
                      "import os\nimport json\nimport hashlib\n\n\ndef f():\n    return 42\n")
        self.assertVerde(self.p.gate("T01"), "os, json y hashlib son de la stdlib")

    def test_un_modulo_propio_no_es_una_dependencia(self):
        """`src` es del proyecto: importarlo no requiere declararlo en requirements."""
        self.preparar("pymysql==1.1.0\n",
                      "from src.otra import g\n\n\ndef f():\n    return g()\n")
        (self.p.dir / "src" / "otra.py").write_text("def g():\n    return 42\n")
        self.assertVerde(self.p.gate("T01"), "src es del proyecto, no una dependencia")


class TestImportsDeclarados(unittest.TestCase):
    """Importar algo que no se declara: la forma «usar una cosa y declarar otra».

    Pasó dos veces en la corrida de clasificados y las dos el método dio otro diagnóstico:
    T30 importó `@vitejs/plugin-react` en `vite.config.ts` sin ponerlo en `package.json`, y
    T02 llamó `cursor(cursorclass=DictCursor)` en su test y `cursor()` en su código. En
    JS/TS se puede verificar de un lado, así que se verifica.
    """

    GATE = RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh"

    def montar(self, package_json, config):
        repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-imports-"))
        self.addCleanup(shutil.rmtree, str(repo), True)
        d = repo / "proyecto"
        for sub in ("scripts", "tareas", "frontend/src", "frontend/tests", "backend/tests"):
            (d / sub).mkdir(parents=True)
        shutil.copy(self.GATE, d / "scripts" / "gate.sh")
        shutil.copy(self.GATE.parent / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "frontend" / "package.json").write_text(package_json)
        (d / "frontend" / "vite.config.ts").write_text(config)
        correr("git init -q && git add -A && git commit -qm base", repo)
        return correr("bash scripts/gate.sh", d)

    def test_un_import_no_declarado_da_rojo(self):
        r = self.montar('{"devDependencies": {"vite": "^5.0.0"}}\n',
                        "import react from '@vitejs/plugin-react';\n")
        self.assertIn("importa paquetes que el package.json no declara", r.stdout,
                      f"no lo vio\n{r.stdout}")
        self.assertIn("@vitejs/plugin-react", r.stdout, "y tiene que decir cuál")

    def test_un_import_declarado_no_da_rojo(self):
        r = self.montar('{"devDependencies": {"vite": "^5.0.0", "@vitejs/plugin-react": "^4.0.0"}}\n',
                        "import react from '@vitejs/plugin-react';\n")
        self.assertIn("todo lo importado está declarado", r.stdout,
                      f"estaba declarado\n{r.stdout}")

    def test_sin_archivos_js_el_chequeo_es_vacuo_y_no_rojo(self):
        """`grep -r` sin rutas lee la ENTRADA ESTÁNDAR, y en un heredoc eso es el propio
        script: el chequeo «encontraba» los paquetes nombrados en sus comentarios y reprobaba
        a tareas de backend por un import que no habían escrito. Pasó con T02 y T03.

        Un chequeo sin material no es un chequeo que pasa: es ⊘.
        """
        repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sinjs-"))
        self.addCleanup(shutil.rmtree, str(repo), True)
        d = repo / "proyecto"
        for sub in ("scripts", "tareas", "frontend", "backend/tests", "backend/migraciones"):
            (d / sub).mkdir(parents=True)
        shutil.copy(self.GATE, d / "scripts" / "gate.sh")
        shutil.copy(self.GATE.parent / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "frontend" / "package.json").write_text('{"devDependencies": {"vite": "^5.0.0"}}\n')
        (d / "tareas" / "T03-m.md").write_text(
            "# T03\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** backend/migraciones/\n")
        correr("git init -q && git add -A && git commit -qm base", repo)
        # La tarea toca SÓLO un .sql: no hay nada JS/TS que cruzar.
        (d / "backend" / "migraciones" / "001.sql").write_text("CREATE TABLE a (id INT);\n")
        r = correr("bash scripts/gate.sh", d, TAREA="T03")
        self.assertNotIn("importa paquetes que el package.json no declara", r.stdout,
                         f"no tocó ningún JS/TS; no puede acusarla de importar nada\n{r.stdout}")
        self.assertIn("no hay archivos JS/TS que cruzar", r.stdout,
                      f"y tiene que decir que no pudo verificarse\n{r.stdout}")

    def test_un_import_relativo_no_cuenta(self):
        r = self.montar('{"devDependencies": {"vite": "^5.0.0"}}\n',
                        "import algo from './algo';\nimport fs from 'node:fs';\n")
        self.assertIn("todo lo importado está declarado", r.stdout,
                      f"ni lo relativo ni los builtins de node son dependencias\n{r.stdout}")


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

    def test_una_capa_que_todavia_no_existe_es_vacuo_y_no_ausencia(self):
        """El proyecto se construye por etapas y la arquitectura recién está completa al
        final. Exigir el grafo entero en cada merge bloquea todos los merges tempranos:
        integrar T02 —que crea `datos/conexion.py`— daba rojo porque `servicios` y `rutas`
        todavía no tenían un solo módulo. No se calla: se informa ⊘."""
        shutil.copy(PLANTILLAS / "_arquitectura.py", self.p.dir / "scripts" / "_arquitectura.py")
        a = self.p.dir / "scripts" / "_arquitectura.py"
        t = a.read_text().replace('CAPAS = ["datos", "servicios", "rutas"]',
                                  'CAPAS = ["datos", "rutas"]')
        t = t.replace('REQUERIDAS = [\n    ("servicios", "datos"),   # la lógica usa la capa de datos\n'
                      '    ("rutas", "servicios"),   # los endpoints no hablan con datos directamente\n]',
                      'REQUERIDAS = [("rutas", "datos")]')
        a.write_text(t)
        # Sólo existe la capa de abajo: la de arriba no llegó todavía.
        (self.p.dir / "src" / "datos.py").write_text("x = 1\n")
        self.p.implementar()
        self.p.git("add -A"); self.p.git('commit -qm "sólo datos"')
        r = self.p.gate()
        self.assertEqual(r.returncode, 0,
                         f"una capa que no llegó no es una ausencia\n{r.stdout}")
        self.assertIn("todavía no tiene ningún módulo", r.stdout,
                      f"y tiene que decirlo, no callarlo\n{r.stdout}")
        self.assertIn("⊘", r.stdout.split("── 5.")[1], "con la marca de vacuidad")
        self.assertIn("no pudieron correr", r.stdout,
                      "y el veredicto tiene que contarlo entre los vacíos")

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


class TestHuecosQueEncontraronLosMutantes(CasoBase):
    """Cuatro ramas del gate que ninguna caso ejercitaba, encontradas midiendo.

    Tercera medición de la tasa de captura con una semilla nueva: 10 de 20, igual que las
    dos anteriores. Pero de los diez sobrevivientes, cinco son **áridos** —quitar un
    `|| true` en una asignación, un `sort -u` que sólo ordena la lista que se imprime,
    `-ge 0` donde sumaba cero— y no pueden cambiar ningún veredicto. Sobre los quince
    productivos la tasa es 10 de 15.

    Los otros cuatro son huecos reales, y los cuatro son ramas que **yo mismo escribí hoy
    sin un caso que las toque**. Eso es lo que la medición compra: no encuentra los bugs
    que uno imagina, encuentra los que uno acaba de escribir.
    """

    def test_sin_el_ayudante_de_senales_el_gate_da_rojo(self):
        """La guarda la agregué hoy —«un chequeo que no está no es un chequeo que pasó»— y
        no la probé. El mutante que la convertía en verde sobrevivió."""
        (self.p.dir / "scripts" / "_suprimidas.py").unlink()
        self.p.implementar()
        self.assertRojo(self.p.gate("T01"), "sin el ayudante no se puede buscar nada",
                        motivo="falta scripts/_suprimidas.py")

    def test_una_tarea_sin_test_declarado_marca_vacuo_en_el_paso_4(self):
        """El paso 4 compara contra la clase que la tarea declara. Si no declara ninguna,
        sólo puede mirar la suite entera, y eso es ⊘ y no un pase."""
        # La implementación tiene que existir en HEAD para que el paso 4 pueda revertirla;
        # si es nueva, el paso 4 se marca ⊘ por otra razón y no llega a esta rama.
        self.p.implementar("def f():\n    return 0\n")
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "Archivo: `tests/test_cosa.py`, clase `TestCosa`.", "Sin declarar todavía."))
        self.p.git("add -A"); self.p.git('commit -qm "sin test declarado"')
        self.p.implementar()
        r = self.p.gate("T01")
        # El mensaje viejo decía «sólo se pudo verificar la suite entera», y esa afirmación
        # era falsa: con el tronco rojo por diseño (tests-first) la suite entera ya falla
        # antes de revertir, así que no verificaba nada. Ahora dice qué FALTA.
        self.assertIn("no declara", r.stdout,
                      f"tiene que decir que la tarea no declara su archivo y clase\n{r.stdout}")
        self.assertNotIn("sólo se pudo verificar la suite entera", r.stdout,
                         "la suite entera no verifica nada: el tronco está rojo por diseño")
        self.assertIn("⊘", r.stdout.split("── 4.")[1], "y marcarlo como no verificado")

    def test_sin_vacios_el_veredicto_no_habla_de_vacios(self):
        """`[ "$VACIOS" -gt 0 ]` → `-ge 0` hacía que TODO gate verde dijera «con 0
        chequeo/s que no pudieron correr». El invariante de contabilidad no lo veía porque
        0 == 0. Un veredicto que menciona vacíos cuando no hay ninguno es ruido que enseña
        a ignorar la parte que sí importa.

        Para llegar a un gate sin un solo ⊘ hay que armar el caso completo: la
        implementación ya en HEAD pero mal, así que el test de la tarea falla en la línea
        base, y la tarea la arregla. Ahí los seis pasos tienen algo que decir."""
        self.p.implementar("def f():\n    return 0\n")      # mal, y commiteada
        self.p.git("add -A"); self.p.git('commit -qm "implementación equivocada"')
        r0 = correr("bash scripts/correr-suite.sh --fallas", self.p.dir)
        (self.p.dir / ".tests-base").write_text(r0.stdout)
        self.assertIn("test_cosa", r0.stdout, "la línea base tiene que traer la falla")
        self.p.implementar()                                   # la tarea la arregla
        r = self.p.gate("T01")
        self.assertVerde(r, "arregló lo que la línea base tenía roto")
        vacios = [l for l in r.stdout.splitlines() if l.startswith("  ⊘ ")]
        self.assertEqual(vacios, [], f"este caso no debería tener ningún ⊘\n{r.stdout}")
        self.assertNotIn("no pudieron correr", r.stdout,
                         "sin ⊘, el veredicto no puede mencionarlos")

    def test_la_rama_de_linea_base_vacia_es_para_un_caso_degenerado(self):
        """Documenta un hallazgo, no una conducta: con tests-first la línea base de una
        tarea **nunca** está vacía —sus tests están en el tronco y fallan—, así que el
        mensaje «y nada más falla» es para el caso en que alguien corre el gate a mano sobre
        un árbol limpio. Dos mutantes sobrevivieron ahí y no es un hueco de cobertura: es
        una rama casi inalcanzable. Queda anotado para que nadie la persiga."""
        self.p.implementar("def f():\n    return 0\n")
        self.p.git("add -A"); self.p.git('commit -qm base')
        r = correr("bash scripts/correr-suite.sh --fallas", self.p.dir)
        self.assertNotEqual(r.stdout.strip(), "",
                            "con el test en el tronco y la implementación mal, algo falla: "
                            "eso es tests-first, y por eso la línea base nunca está vacía")


class TestElCorredorNoConfundeNoPudeConPaso(unittest.TestCase):
    """El corredor PRODUCE los códigos del contrato; `TestContratoDeLaSuite` prueba cómo
    reacciona el gate a cada uno. Son dos sujetos distintos y faltaba el primero.

    Cuatro defectos, los cuatro encontrados al congelar el banco y los cuatro de la misma
    clase: un ⊘ tapando una falla, o peor, una falla informada como pase. Mientras estuvieron,
    el banco parecía tener 9 ítems viables de 21 y tiene 15 de 17 — la diferencia no era del
    banco, era del instrumento.

    El sujeto es `ejemplo-clasificados`, que es el único con corredor de frontend. Corre sus
    tests de verdad: no escribe en el árbol salvo los dos archivos de prueba, que se borran.
    """

    PROY = RAIZ / "ejemplo-clasificados"

    @classmethod
    def setUpClass(cls):
        if not (cls.PROY / "frontend" / "node_modules" / ".bin" / "vitest").exists():
            raise unittest.SkipTest("falta el entorno del frontend de ejemplo-clasificados")
        # Sonda: ¿puede ARRANCAR el corredor del frontend en este proceso? En esta máquina
        # esbuild está instalado para otra arquitectura que el node que hereda un subproceso
        # (`@esbuild/darwin-arm64` presente, hace falta `darwin-x64`), así que vitest no llega
        # a cargar su config. Eso es del entorno y el corredor ahora lo dice con el código 3.
        # Los casos de frontend se saltean DICIÉNDOLO: un test que no puede correr no pasa.
        r = correr("bash scripts/correr-suite.sh "
                   "frontend/tests/test_scaffolding_frontend.test.ts::TestScaffoldingFrontend",
                   cls.PROY)
        cls.FRONT_VIVO = (r.returncode != 3)
        cls.FRONT_MOTIVO = "" if cls.FRONT_VIVO else (
            "el corredor del frontend no arranca en un subproceso (toolchain de otra "
            "arquitectura); el corredor lo informa con el código 3")

    def correr_sel(self, sel):
        if sel.startswith("frontend/") and not self.FRONT_VIVO:
            self.skipTest(self.FRONT_MOTIVO)
        r = correr(f"bash scripts/correr-suite.sh {shlex.quote(sel)}", self.PROY)
        return r.returncode, r.stdout + r.stderr

    def test_un_toolchain_roto_es_del_entorno_y_no_del_codigo(self):
        """Un corredor que no arranca no es «la suite no corrió nada»: es un defecto del
        entorno, y la diferencia es a quién se le cobra. Salía 2 —culpando al proyecto— y
        tiene que salir 3, que el gate informa como «es del método, no del código juzgado»."""
        if self.FRONT_VIVO:
            self.skipTest("el toolchain del frontend arranca acá: el caso no es alcanzable")
        r = correr("bash scripts/correr-suite.sh "
                   "frontend/tests/test_scaffolding_frontend.test.ts::TestScaffoldingFrontend",
                   self.PROY)
        self.assertEqual(r.returncode, 3,
                         "un corredor que no arranca es del entorno (3), no «cero tests» (2)")
        self.assertIn("del entorno", r.stdout + r.stderr,
                      "y tiene que decir de quién es el defecto")

    # ── Lo que ya andaba, como control positivo ────────────────────────────────────────
    def test_una_clase_que_pasa_da_cero(self):
        for sel in ("backend/tests/test_errores.py::TestErrores",
                    "frontend/tests/test_scaffolding_frontend.test.ts::TestScaffoldingFrontend"):
            with self.subTest(sel=sel):
                rc, _ = self.correr_sel(sel)
                self.assertEqual(rc, 0, "una clase que pasa tiene que dar 0")

    # ── El peor de los cuatro ──────────────────────────────────────────────────────────
    def test_un_filtro_que_no_matchea_nada_no_es_una_suite_verde(self):
        """vitest con `-t <nombre>` que no matchea **saltea todo y sale con 0**, así que el
        corredor devolvía 0 = «los tests pasan». Una clase inexistente se informaba como suite
        verde, y en el paso 4 del gate eso sale como «los tests PASAN con la implementación
        vieja»: culpando al test. La salida lo decía: `Tests  3 skipped (3)`, sin un «passed»."""
        rc, salida = self.correr_sel(
            "frontend/tests/test_scaffolding_frontend.test.ts::ClaseQueNoExiste")
        self.assertEqual(rc, 2,
                         f"saltear todo no es pasar; dio {rc}:\n{salida[-400:]}")

    def test_una_clase_python_que_no_existe_no_corrio_nada(self):
        rc, _ = self.correr_sel("backend/tests/test_errores.py::ClaseQueNoExiste")
        self.assertEqual(rc, 2, "una clase que no existe no corrió ningún test")

    def test_un_archivo_que_no_existe_no_se_pudo_medir(self):
        for sel in ("backend/tests/no_existe.py", "frontend/tests/no_existe.test.ts"):
            with self.subTest(sel=sel):
                rc, _ = self.correr_sel(sel)
                self.assertEqual(rc, 2, "sin archivo no hay nada que correr")

    # ── Un archivo que NO SE PUEDE COLECTAR falló: no es «no pude medir» ──────────────
    def _con_test_roto(self, ruta, cuerpo):
        f = self.PROY / ruta
        self.assertFalse(f.exists(), f"{ruta} ya existe; elegí otro nombre")
        f.write_text(cuerpo)
        self.addCleanup(f.unlink, True)
        return f

    def test_un_test_que_no_puede_importar_su_implementacion_es_una_falla(self):
        """Es la señal más fuerte que hay —la implementación no está— y se informaba como ⊘.

        vitest: imprime `Test Files 1 failed (1)` **y** `Tests no tests` en la misma salida, y
        el corredor buscaba `no tests` antes de mirar si algo falló.
        pytest: sale con **4**, que usa tanto para «el archivo no existe» como para «lo
        encontré y su import falla». Los dos iban a ⊘, y eso descartaba todo ítem cuya
        implementación es un archivo NUEVO: el caso normal en greenfield."""
        casos = (
            ("backend/tests/test_zz_colecta_prueba.py",
             "from app.modulo_que_no_existe import nada\n\n"
             "class TestColectaPrueba:\n    def test_x(self):\n        assert nada\n",
             "backend/tests/test_zz_colecta_prueba.py::TestColectaPrueba"),
            ("frontend/tests/test_zz_colecta_prueba.test.ts",
             "import { describe, it, expect } from 'vitest';\n"
             "import { nada } from '../src/modulo_que_no_existe';\n"
             "describe('TestColectaPrueba', () => {\n"
             "  it('x', () => { expect(nada).toBe(1); });\n});\n",
             "frontend/tests/test_zz_colecta_prueba.test.ts::TestColectaPrueba"),
        )
        for ruta, cuerpo, sel in casos:
            with self.subTest(ruta=ruta):
                self._con_test_roto(ruta, cuerpo)
                rc, salida = self.correr_sel(sel)
                self.assertEqual(rc, 1,
                                 f"un archivo que no se puede colectar FALLÓ, no es ⊘; "
                                 f"dio {rc}:\n{salida[-500:]}")


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


class TestElEstadoNoDaUnVeredictoQueNoPuedeFallar(CasoBase):
    """`estado.sh` decía «tronco: ✗ ROJO» durante toda etapa tests-first, porque los tests
    de la etapa se aceptan y commitean antes de que exista la implementación. Un veredicto
    que no puede dar verde mientras eso dure no mide nada —es la regla de MEDICION.md— y yo
    mismo casi lo leí como una rotura real del repo."""

    def estado(self):
        return correr(f"bash {SCRIPTS}/estado.sh", self.p.dir)

    def test_el_rojo_de_una_etapa_en_vuelo_se_declara_y_se_nombra(self):
        # T01 pendiente y `tests/test_cosa.py` ya en el repo: ése es el rojo del tests-first.
        r = self.estado()
        self.assertIn("POR DISEÑO", r.stdout,
                      f"no distingue el rojo de la etapa del rojo de verdad:\n{r.stdout}")
        self.assertIn("tests/test_cosa.py", r.stdout,
                      "y tiene que nombrar el test en vuelo, no sólo declarar la categoría")

    def test_un_rojo_que_no_es_de_la_etapa_sigue_diciendo_ROJO(self):
        """Brazo nulo del anterior: si dijera «por diseño» siempre, el veredicto volvería a
        no poder fallar —al revés que antes— y el test de arriba pasaría por el motivo
        equivocado."""
        self.p.escribir_tarea("T01", "src/cosa.py", estado="✅ hecha")
        self.p.implementar("def f():\n    return 0\n")   # mergeado y rojo de verdad
        r = self.estado()
        self.assertIn("✗ ROJO", r.stdout, f"un rojo real tiene que decirlo:\n{r.stdout}")
        self.assertNotIn("POR DISEÑO", r.stdout,
                         "no hay ninguna tarea pendiente con test commiteado: este rojo es real")

    def test_el_titulo_de_una_tarea_con_sufijo_no_arrastra_el_numeral(self):
        """`sed 's/^# T[0-9]* — //'` no cubre T04b ni T06a, así que la columna salía como
        «# T04b — …» justo en las tareas partidas, que son las que más se miran."""
        self.p.escribir_tarea("T04b", "src/otra.py")
        r = self.estado()
        fila = [l for l in r.stdout.split("\n") if l.startswith("T04b")]
        self.assertTrue(fila, f"estado.sh no listó T04b:\n{r.stdout}{r.stderr}")
        self.assertNotIn("#", fila[0],
                         f"el título arrastra el H1 del markdown: {fila[0]!r}")


class TestUnContadorQueCuentaDosExperimentos(unittest.TestCase):
    """El presupuesto de cortes y de reintentos se gasta contra UN enunciado. Arreglé el
    contrato de T26 a mitad de la etapa y el contador ya estaba en 2 de 2, gastado contra el
    enunciado roto: lo que iba a frenar la etapa era el contador, no la tarea. Dos
    experimentos conflados en un número."""

    def huella(self, *args):
        return correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_enunciado ' +
            " ".join(shlex.quote(a) for a in args)), RAIZ)

    def cambio(self, nueva, anterior):
        r = correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
            f'el_enunciado_cambio {shlex.quote(nueva)} {shlex.quote(anterior)}'), RAIZ)
        return r.returncode == 0

    def test_la_huella_sale_del_archivo_que_el_agente_va_a_leer(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-enunciado-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        a, b = d / "viejo.md", d / "nuevo.md"
        a.write_text("# T26\n\nhasheá con scrypt\n")
        b.write_text("# T26\n\nhasheá con sha256\n")
        ha, hb = self.huella(str(a)).stdout.strip(), self.huella(str(b)).stdout.strip()
        self.assertTrue(ha and hb, "la huella no puede salir vacía con el archivo presente")
        self.assertNotEqual(ha, hb, "dos enunciados distintos tienen que dar huellas distintas")
        self.assertEqual(ha, self.huella(str(a)).stdout.strip(), "y la misma tiene que repetir")

    def test_sin_archivo_la_huella_es_vacia_y_no_reinicia(self):
        """Si el archivo no está, no se sabe nada: una huella inventada reiniciaría los
        contadores en cada vuelta y el presupuesto no limitaría nada."""
        vacia = self.huella("/no/existe/esto.md").stdout.strip()
        self.assertEqual(vacia, "")
        self.assertFalse(self.cambio("", "abc123"), "sin huella nueva no se reinicia")
        self.assertFalse(self.cambio("abc123", ""), "en el primer intento no hay nada que reiniciar")

    def test_cuando_cambia_el_enunciado_se_reinicia(self):
        self.assertTrue(self.cambio("aaa", "bbb"))
        self.assertFalse(self.cambio("aaa", "aaa"), "el mismo enunciado no reinicia nada")

    def test_el_reinicio_esta_cableado_despues_de_crear_el_worktree(self):
        """Chequeo de forma: la conducta pide una corrida de agente entera. Lo que pina es
        que la huella se lea del worktree —el árbol que el agente ve— y que se reinicien
        TODOS los contadores, incluido el motivo que se le inyecta en el pedido."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        i = s.index('worktree add -q -b "tests/$id"')
        j = s.index("el_enunciado_cambio")
        self.assertLess(i, j, "la huella se lee antes de crear el worktree: leería el anterior")
        self.assertIn('huella_enunciado "$wt/', s[i:j],
                      "la huella tiene que salir del worktree, no del árbol que yo tengo abierto")
        tramo = s[j:j + 700]
        for v in ("intento=1", "cortes=0", "cortes_total=0", 'MOTIVO_TESTS=""',
                  'HUELLA_ANTERIOR=""'):
            self.assertIn(v, tramo, f"el reinicio no toca {v}: queda contando el experimento viejo")
        self.assertIn('ENUNCIADO_ANTERIOR=""', s,
                      "sin inicializarlo por tarea, una tarea hereda la huella de la anterior")


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

    def test_un_archivo_que_ya_existe_no_lo_tiene_que_escribir_nadie(self):
        """El chequeo usa la sección (`## Contrato`, `## Alcance`) como aproximación a «te
        pido que lo escribas», que no distingue «escribí esto» de «leé esto». La existencia
        sí: T26 tiene que nombrar `backend/tests/test_auth_backend.py` para decir cómo se
        mockea, y ese test está en el repo desde T04. El alcance lo sigue cuidando el paso 2
        del gate, que reprueba tocar lo que no es tuyo."""
        ajeno = self.p.dir / "src" / "ya_esta.py"
        ajeno.parent.mkdir(parents=True, exist_ok=True)
        ajeno.write_text("# este archivo ya está en el repo\n")
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text() + "\n## Contrato\n\nSe mockea como en `src/ya_esta.py`.\n")
        self.assertVerde(self.validar(),
                         "nombrar un archivo que ya existe no es pedir que lo escriban")

    def test_un_archivo_que_no_existe_y_nadie_tiene_asignado_sigue_dando_rojo(self):
        """Brazo nulo del anterior: si el chequeo callara para cualquier archivo nombrado, el
        de arriba pasaría por el motivo equivocado. Era el caso de T03."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text() + "\n## Contrato\n\nEscribí `src/nadie_lo_hace.py`.\n")
        self.assertRojo(self.validar(), "nadie lo va a escribir")

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

    def test_nadie_corre_la_suite_desde_un_subdirectorio(self):
        """La canaria de cwd mide los corredores de Python; vitest no la ejecuta, y por ahí
        se colaba el mismo defecto: `cd frontend && vitest` deja el `process.cwd()` de los
        tests en `frontend/`, y un test que abre `frontend/package.json` busca
        `frontend/frontend/package.json`. Pasó, con ese mensaje exacto.

        Chequeo de forma porque la conducta pide vitest instalado, que no está en el
        proyecto de juguete. Lo que pinea es la regla: **nadie hace `cd` a un subdirectorio
        para correr la suite.** Los corredores aceptan el directorio por bandera
        (`--root`, `-s`, `--rootdir`) y así el cwd queda donde tiene que estar."""
        CD_Y_CORREDOR = re.compile(
            r"cd\s+[A-Za-z0-9_./-]+\s*&&\s*[^\n]*(vitest|pytest|unittest|jest)")
        for gate in self.GATES:
            suite = gate.parent / "correr-suite.sh"
            if not suite.exists():
                continue
            with self.subTest(proyecto=str(gate.parent.relative_to(RAIZ))):
                malos = [l.strip() for l in suite.read_text().splitlines()
                         if CD_Y_CORREDOR.search(l) and not l.strip().startswith("#")]
                self.assertEqual(malos, [],
                                 "corre la suite desde un subdirectorio; el cwd de los "
                                 "tests tiene que ser la raíz del proyecto:\n  "
                                 + "\n  ".join(malos))

    def test_en_todos_un_chequeo_que_no_corre_se_marca_vacuo(self):
        """La regla que no se adapta: ⊘ nunca puede confundirse con ✓."""
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                fuente = gate.read_text()
                self.assertIn("VACIOS=$((VACIOS+1))", fuente, "el ejemplo perdió vacuo()")
                self.assertIn("exit 1", fuente, "el ejemplo perdió la salida en rojo")


class TestElInstrumentoNoDaUnNumeroQueNoPuedeMedir(unittest.TestCase):
    """Un instrumento roto no hace ruido: produce resultados limpios.

    `PRUEBAS.md` cubre al verificador que deja de mirar. Esto cubre la clase complementaria,
    la de `MEDICION.md`: el instrumento que corre, mide limpio, informa con tres decimales y
    mide otra cosa. Los tres defectos pineados acá estuvieron commiteados y midiendo.
    """

    COMPARADOR = SCRIPTS / "comparar-modelos.sh"
    BANCO = RAIZ / "pruebas" / "bancos" / "razonamiento.py"

    # ── El tiempo de un brazo paralelo no es el tiempo del modelo ──────────────────────

    def test_el_comparador_corre_un_brazo_a_la_vez_por_omision(self):
        """El mismo MoE A3B mide 16,3 tok/s con un usuario y 122 con ocho. Una columna de
        segundos de brazos simultáneos describe la ocupación de la plataforma en ese minuto,
        no al modelo. El comparador lanzaba todos con `&` + `wait` y después imprimía SEGS."""
        fuente = self.COMPARADOR.read_text()
        self.assertIn(': "${SERIE:=1}"', fuente,
                      "SERIE tiene que estar declarada una sola vez y en 1 por omisión")
        self.assertRegex(fuente, r'\[ "\$SERIE" = 1 \] && wait',
                         "en serie hay que esperar a cada brazo antes de lanzar el siguiente")

    def test_el_comparador_no_imprime_segundos_de_brazos_paralelos(self):
        """Un instrumento que no puede medir el tiempo no muestra un número de tiempo.
        Chequeo de forma: la conducta pide opencode y una plataforma arriba."""
        fuente = self.COMPARADOR.read_text()
        self.assertIn("segs='—'", fuente,
                      "con los brazos en paralelo, SEGS tiene que salir «—», no un número")
        i = fuente.index("segs='—'")
        self.assertIn('"$SERIE"', fuente[max(0, i - 200):i],
                      "el «—» tiene que estar guardado por SERIE, no suelto")

    # ── El campo que se lee ────────────────────────────────────────────────────────────

    def banco(self):
        """El banco pide la plataforma en el import; para mirar el corrector no hace falta."""
        import importlib.util
        os.environ.setdefault("COLABHIVE_BASE_URL", "http://127.0.0.1:9/v1")
        os.environ.setdefault("COLABHIVE_API_KEY", "x")
        spec = importlib.util.spec_from_file_location("banco_razonamiento", self.BANCO)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_el_banco_puntua_la_respuesta_y_no_el_pensamiento(self):
        """El defecto más caro del día: el corrector concatenaba `content` + `reasoning` y
        le pasaba la mezcla al regex. El pensamiento REFORMULA LA PREGUNTA, así que contiene
        las palabras clave que el patrón busca: daba ✓ a razonamientos que terminaban en una
        respuesta equivocada. Invalidó la campaña entera de dos modelos."""
        limpiar = self.banco().limpiar
        self.assertEqual(
            limpiar("<think>quizá sea fastapi.exceptions, o pydantic</think>"
                    "Importalo desde pydantic"),
            "Importalo desde pydantic",
            "el pensamiento entre etiquetas no puede entrar al puntaje")
        self.assertEqual(
            limpiar("</think>\n\nLa ruta es absoluta."), "La ruta es absoluta.",
            "Qwen3.8-27B emite el pensamiento en `content` y cierra con </think>")
        self.assertEqual(
            limpiar("pensando: capaz fastapi.exceptions <think>y además"), "",
            "un bloque que nunca cerró es una respuesta truncada, no una respuesta")
        self.assertEqual(
            limpiar("Importá desde fastapi.exceptions"),
            "Importá desde fastapi.exceptions",
            "una respuesta sin pensamiento tiene que pasar intacta")

    def test_el_banco_lee_content_y_no_el_razonamiento(self):
        fuente = self.BANCO.read_text()
        self.assertNotRegex(
            fuente, r'for k in \("content", *"reasoning"',
            "volvió a concatenar la respuesta con el razonamiento en un solo texto")

    def test_el_banco_decide_por_mayoria(self):
        """La regla de agregación decide el resultado de cada caso, así que es parte del
        corrector. Estaba incrustada en el bucle de la campaña y no se podía ejercitar sin
        gastar una campaña — el mismo defecto que el corrector antes de sacarlo a `limpiar`."""
        resolver = self.banco().resolver
        for reps, espera in (
            (["✓", "✓", "✓"], "✓"),
            (["✓", "✓", "✗"], "✓"),
            (["✓", "✗", "✗"], "✗"),
            (["✗", "✗", "✗"], "✗"),
        ):
            with self.subTest(reps=reps):
                self.assertEqual(resolver(reps)[0], espera)

    def test_el_banco_informa_la_inestabilidad_y_no_la_promedia(self):
        """8 de 12 siempre los mismos es mejor compañero que 8 de 12 distintos cada vez,
        porque el segundo rompe el presupuesto de reintentos de `correr-plan.sh`. Si se
        promedia, los dos dan lo mismo."""
        resolver = self.banco().resolver
        self.assertFalse(resolver(["✓", "✓", "✓"])[1], "tres iguales no son inestables")
        self.assertFalse(resolver(["✗", "✗", "✗"])[1], "tres iguales no son inestables")
        self.assertTrue(resolver(["✓", "✓", "✗"])[1],
                        "dos contra uno es el mismo veredicto Y un caso inestable")
        self.assertTrue(resolver(["✓", "✗", "⊘"])[1],
                        "el ⊘ no se cuenta, pero lo que queda discrepa")

    def test_un_modelo_que_contesta_dos_de_tres_veces_si_se_midio(self):
        """El ⊘ que tapa un resultado real: `MEDICION.md` §4, «el espejo». Marcar ⊘ a un
        sujeto que contestó la mayoría de las veces tira los datos de los peor comportados en
        vez de reprobarlos — y eso ya pasó: GLM-4.7-Flash contestó vacío 6 de 6 y
        **desapareció** de la tabla de razonamiento en vez de sacar 0."""
        resolver = self.banco().resolver
        self.assertEqual(resolver(["✗", "✗", "⊘"])[0], "✗",
                         "contestó 2 de 3 y las dos mal: eso es FALLA, no «no se pudo medir»")
        self.assertEqual(resolver(["✓", "⊘", "⊘"])[0], "⊘",
                         "mayoría sin respuesta: ahí sí no se midió")
        self.assertEqual(resolver(["⊘", "⊘", "⊘"])[0], "⊘")
        self.assertEqual(resolver(["✗", "⊘"])[0], "⊘",
                         "mitad y mitad no es mayoría: no se midió")

    def test_el_banco_no_decide_con_una_sola_corrida(self):
        """La MISMA petición a temperature 0 produjo un tool_call una vez y prosa la
        siguiente: el éxito por corrida es estocástico. Con n=1 el banco no puede ordenar
        dos modelos cercanos, y se usó para decidir."""
        self.assertEqual(self.banco().REPS, 3,
                         "el banco decide por mayoría de 3 corridas, no con una")

    # ── Un defecto nuestro no es un fallo del modelo ───────────────────────────────────

    def declarado(self, cfg, modelo):
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'CONFIG_OC="{cfg}" modelo_declarado "{modelo}"; echo "rc=$?"', RAIZ)
        return r.stdout

    def test_el_comparador_no_arranca_sin_brazo_de_control(self):
        """`MEDICION.md` §7 afirmaba que «el runner se niega a arrancar si el brazo de control
        no está declarado». Era falso: no había un solo brazo de control en ningún script.
        Y el control es lo que evitó publicar un veredicto falso sobre el modelo de un partner:
        cinco fallas limpias y reproducibles, con el control sin moverse."""
        r = correr(f"bash {SCRIPTS}/comparar-modelos.sh T06c modelo-a modelo-b",
                   RAIZ / "ejemplo-clasificados")
        self.assertNotEqual(r.returncode, 0, "sin CONTROL= no puede arrancar")
        self.assertIn("control", (r.stdout + r.stderr).lower(),
                      "y tiene que decir que falta el brazo de control")
        fuente = (SCRIPTS / "comparar-modelos.sh").read_text()
        self.assertIn('set -- "$@" "$CONTROL"', fuente,
                      "el control tiene que correr SIEMPRE, como un brazo más de la tanda")
        self.assertIn("CONTROL=ninguno", fuente,
                      "y tiene que haber una salida explícita que quede escrita en la tabla")

    def test_el_criterio_de_validez_del_control_esta_en_codigo(self):
        """`MEDICION.md` §7 decía que faltaba esto: el comparador corría el control y lo
        informaba, y QUIÉN decide que se movió demasiado seguía siendo una persona.

        Y la banda que el diseño proponía —±2 ítems sobre 12— estaba calculada con p=0,83, que
        es la tasa de **tool-call**, no de verde. La tasa de verde del control, medida en el
        registro, es 0,42 por corrida: con ésa, ±2 descarta el **29%** de los bloques buenos y
        el protocolo se auto-invalida sin parar. Por eso el criterio es continuo y sobre lo que
        tiene varianza baja, no un conteo binomial de doce ítems."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ctrl-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / ".metricas").mkdir()

        def criterio(clave, tools, gate):
            dentro = (f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
                      f'RAIZ="{d}" control_se_movio "{clave}" "{tools}" "{gate}"')
            r = correr("bash -c " + shlex.quote(dentro), RAIZ)
            return r.returncode, r.stdout

        casos = (
            ("primera corrida: queda como línea base", "ctrl|T01", 6, "VERDE", 2),
            ("idéntico a la base: válida", "ctrl|T01", 6, "VERDE", 0),
            ("una variación chica NO descarta", "ctrl|T01", 5, "VERDE", 0),
            ("herramientas a la mitad: se movió el arnés", "ctrl|T01", 2, "VERDE", 1),
            ("otra tarea tiene su propia línea base", "ctrl|T99", 6, "VERDE", 2),
        )
        for nombre, clave, tools, gate, espera in casos:
            with self.subTest(caso=nombre):
                rc, salida = criterio(clave, tools, gate)
                self.assertEqual(rc, espera, f"{nombre}: dio {rc}\n{salida}")

    def test_el_veredicto_del_control_que_cambia_descarta_la_tanda(self):
        """Si el control pasa de verde a rojo, se movió el arnés y la tanda se descarta
        ENTERA, incluidos los brazos que dieron bien: si el instrumento estaba mal, su acierto
        también es sospechoso."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ctrl2-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / ".metricas").mkdir()
        dentro = lambda tools, gate: (
            f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
            f'RAIZ="{d}" control_se_movio "c|T01" "{tools}" "{gate}"')
        correr("bash -c " + shlex.quote(dentro(6, "VERDE")), RAIZ)      # línea base
        r = correr("bash -c " + shlex.quote(dentro(6, "ROJO")), RAIZ)
        self.assertEqual(r.returncode, 1, "un veredicto distinto es el arnés moviéndose")
        self.assertIn("VERDE a ROJO", r.stdout, "y tiene que decir qué se movió")
        # Y el comparador tiene que ABORTAR, no sólo informarlo.
        fuente = (SCRIPTS / "comparar-modelos.sh").read_text()
        self.assertIn("control_se_movio", fuente, "el comparador tiene que aplicar el criterio")
        tramo = fuente.split("control_se_movio")[-1]
        self.assertIn("exit 1", tramo,
                      "con el control movido, la tanda se descarta: informarlo no alcanza")

    def test_el_registro_lleva_concurrencia_y_huella_del_instrumento(self):
        """Dos campos del régimen de `MEDICION.md` §5 que el registro no escribía.
        `concurrencia` es lo que decide si una fila sirve para medir tiempo (el mismo modelo
        pasa de 16,3 a 122 tok/s según la ocupación, y el runner corre con PARALELAS=8).
        `instrumento` es el punto 7 de la regla de parada: dos filas con huellas distintas no
        se comparan, y antes no había cómo saberlo."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-reg9-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "p" / "tareas").mkdir(parents=True)
        correr("git init -q . && git -c user.email=t@t -c user.name=t commit -q "
               "--allow-empty -m x", d)
        dentro = (f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
                  f'RAIZ="{d}" PROYECTO=p anotar_intento T01 ROJO 10 abc')
        correr("bash -c " + shlex.quote(dentro), RAIZ)
        reg = d / ".metricas" / "intentos.csv"
        self.assertTrue(reg.exists(), "no escribió el registro")
        import csv as _csv
        with open(reg) as fh:
            lector = _csv.DictReader(fh)
            campos = lector.fieldnames or []
            filas = list(lector)
        for col in ("concurrencia", "instrumento"):
            self.assertIn(col, campos, f"falta la columna `{col}`")
        self.assertTrue(filas and filas[0]["concurrencia"] != "",
                        "la columna existe pero el runner no la escribe")
        self.assertTrue(all(None not in f for f in filas),
                        "ninguna fila puede tener campos que el encabezado no nombra")

    def test_migrar_el_esquema_rellena_las_filas_viejas(self):
        """Agregar una columna y reescribir SÓLO el encabezado deja las filas viejas con menos
        campos que los nombres — la misma columna ilegible, al revés. Ya pasó una vez con
        `motivo`; agregar dos más era la oportunidad de repetirlo."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-mig-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "p" / "tareas").mkdir(parents=True)
        correr("git init -q . && git -c user.email=t@t -c user.name=t commit -q "
               "--allow-empty -m x", d)
        reg = d / ".metricas" / "intentos.csv"
        reg.parent.mkdir(parents=True)
        reg.write_text("fecha,proyecto,tarea,veredicto,segundos,modelo\n"
                       "2026-01-01T00:00:00Z,p,T01,ROJO,10,abc\n"
                       "2026-01-01T00:01:00Z,p,T02,VERDE,11,abc\n")
        dentro = (f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
                  f'RAIZ="{d}" PROYECTO=p anotar_intento T03 ROJO 12 abc')
        correr("bash -c " + shlex.quote(dentro), RAIZ)
        anchos = {l.count(",") for l in reg.read_text().strip().split("\n") if l}
        self.assertEqual(len(anchos), 1,
                         f"las filas quedaron con anchos distintos: {sorted(anchos)}")

    def test_el_banco_se_niega_a_correr_si_no_puede_reprobar_a_nadie(self):
        """El espejo del control positivo. Un control positivo prueba que el corrector puede
        aprobar; éste prueba que puede REPROBAR, que es la mitad que faltaba y la que hace
        pasar a todos cuando falta. Medido: GLM-4.7 contestó vacío 6 de 6 y **desapareció** de
        la tabla de razonamiento en vez de sacar 0."""
        fuente = self.BANCO.read_text()
        self.assertIn("MALO_CONOCIDO", fuente, "no hay brazo de sujeto-que-se-sabe-malo")
        # Conducta: con la plataforma apagada el sujeto malo da ⊘, y eso tiene que PARAR el
        # banco, no dejarlo correr con un corrector que no puede reprobar.
        r = correr(f"REPS=1 MALO_CONOCIDO=00000000-dead-beef-0000-000000000000 "
                   f"python3 {self.BANCO} 'x=falso'", RAIZ,
                   COLABHIVE_BASE_URL="http://127.0.0.1:9/v1", COLABHIVE_API_KEY="x")
        salida = r.stdout + r.stderr
        self.assertIn("control negativo", salida,
                      f"tenía que parar por el control negativo:\n{salida[:400]}")
        self.assertNotIn("casos:", salida,
                         "no puede correr la campaña si el corrector no puede reprobar")

    def test_un_modelo_sin_declarar_no_es_un_modelo_que_falla(self):
        """Un id que no está en `provider.*.models` muere en ~2 segundos con un error
        genérico que parece de plataforma. Lo tomamos tres veces como «ese modelo no
        sirve»."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-decl-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text('{"provider":{"colabhive":{"models":{"abc-123":{"name":"x"}}}}}')
        self.assertIn("rc=0", self.declarado(cfg, "abc-123"),
                      "un modelo declarado tiene que pasar")
        self.assertIn("rc=1", self.declarado(cfg, "no-existe-0000"),
                      "un modelo sin declarar tiene que dar «no», no «no sé»")

    def test_no_poder_leer_la_config_no_es_un_no(self):
        """⊘ y «no» son distintos, y el ⊘ no frena: no sabemos no es excusa para parar.
        Al revés —un ⊘ tapando un «no»— el chequeo nunca dispara, que es cómo nació roto:
        `python3 ... || return 2` hacía indistinguible el `sys.exit(1)` de un crash."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-decl2-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        roto = d / "roto.json"
        roto.write_text("{ esto no es json")
        self.assertIn("rc=2", self.declarado(roto, "cualquiera"),
                      "una config ilegible es ⊘, no «no está declarado»")
        self.assertIn("rc=2", self.declarado(d / "no-existe.json", "cualquiera"),
                      "sin config no se puede saber: ⊘")


class TestNoSeTiraElMaterialDeUnIntento(CasoBase):
    """`recordar_falla` sólo escribe un registro cuando el veredicto es VERDE, así que de un
    intento que el gate reprobó el método no guardaba nada ejecutable: el código se iba con el
    worktree en `worktree remove --force`. Los 16 intentos rechazados que tenemos hoy son un
    rescate accidental de worktrees de experimento que estaban por borrarse.
    """

    def conservar(self, wt, id="PRUEBA"):
        # RAIZ es el repo, y el helper escribe en `$RAIZ/../fallidos-<id>`, igual que el
        # runner, que crea los worktrees como hermanos del repo.
        dentro = (f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
                  f'RAIZ="{wt}" conservar_intento "{wt}" "{id}"')
        return correr("bash -c " + shlex.quote(dentro), RAIZ)

    def test_el_parche_del_intento_se_guarda_y_APLICA(self):
        """Un parche que no aplica no es material: es un archivo. Lo que lo vuelve útil para
        reconstruir un intento rechazado es que `git apply` lo acepte."""
        p = self.p
        (p.dir / "src" / "cosa.py").write_text("def f():\n    return 1\n")
        p.git("add -A"); p.git('commit -qm base2')
        p.implementar("def f():\n    return 42\n")              # modificado
        (p.dir / "src" / "nuevo.py").write_text("X = 1\n")        # nuevo
        r = self.conservar(p.repo)
        dest = p.repo.parent / "fallidos-PRUEBA"
        self.addCleanup(shutil.rmtree, str(dest), True)
        parches = sorted(dest.glob("parche-*.diff"))
        self.assertTrue(parches, f"no guardó ningún parche:\n{r.stdout}\n{r.stderr}")
        cuerpo = parches[0].read_text()
        self.assertIn("cosa.py", cuerpo, "falta el archivo modificado")
        self.assertIn("nuevo.py", cuerpo,
                      "falta el archivo NUEVO: `git diff HEAD` solo no los incluye")
        # Y la prueba que importa: aplica sobre el estado base.
        p.git("checkout -- ."); (p.dir / "src" / "nuevo.py").unlink()
        ap = correr(f"git apply --check {shlex.quote(str(parches[0]))}", p.repo)
        self.assertEqual(ap.returncode, 0,
                         f"el parche guardado no aplica:\n{ap.stderr}")

    def test_no_guarda_la_infraestructura_del_metodo_como_trabajo_del_agente(self):
        """El worktree tiene `.tarea.log`, `.base-ref`, venv y node_modules que los prepara el
        método. Si entran al parche, el material queda inservible y enorme."""
        p = self.p
        p.implementar()
        (p.repo / ".tarea.log").write_text("ruido\n")
        (p.repo / ".base-ref").write_text("deadbeef\n")
        (p.dir / "node_modules").mkdir(exist_ok=True)
        (p.dir / "node_modules" / "paquete.js").write_text("// dependencia\n")
        self.conservar(p.repo)
        dest = p.repo.parent / "fallidos-PRUEBA"
        self.addCleanup(shutil.rmtree, str(dest), True)
        parches = sorted(dest.glob("parche-*.diff"))
        self.assertTrue(parches, "no guardó parche")
        cuerpo = parches[0].read_text()
        for ruido in (".tarea.log", ".base-ref", "node_modules"):
            self.assertNotIn(ruido, cuerpo, f"{ruido} no es trabajo del agente")

    def test_los_cinco_sitios_que_destruyen_un_worktree_pasan_por_el_mismo_helper(self):
        """Cuatro de cinco: el quinto (`marcar_hecha_y_limpiar`) corre cuando la tarea ya
        cerró verde y está integrada, así que su código vive en un commit. «Arreglar un lado y
        no el otro» es el patrón que este repo repite, y acá se perdió un log por eso."""
        sitios = []
        for f in sorted(SCRIPTS.glob("*.sh")):
            lineas = f.read_text().splitlines()
            for i, l in enumerate(lineas):
                if "worktree remove --force" in l and not l.strip().startswith("#"):
                    # La cobertura se declara en las 6 líneas de arriba: o llama al helper, o
                    # dice «conservar_intento: no-aplica» con el motivo. Detectarlo por
                    # distancia a una función era frágil; un marcador explícito se ve.
                    ventana = "\n".join(lineas[max(0, i - 6):i])
                    sitios.append((f"{f.name}:{i + 1}",
                                   "conservar_intento" in ventana))
        self.assertGreaterEqual(len(sitios), 4, f"esperaba al menos 4 sitios, vi {sitios}")
        huerfanos = [n for n, cubierto in sitios if not cubierto]
        self.assertEqual(huerfanos, [],
                         "estos destruyen un worktree sin conservar el intento: "
                         + ", ".join(huerfanos))


class TestNadieCruzabaLasTareasEntreSi(unittest.TestCase):
    """El gate mira UNA tarea; el paso 5 mira la arquitectura. Nadie miraba si dos tareas se
    contradicen — y los dos defectos más caros del 2026-10-19 fueron exactamente eso: tareas
    que pasaban sus propios tests y juntas rompían el sistema.

    **T05** decía «respetando la autorización del usuario», no declaraba con qué, y no podía
    tocar `servicios/auth.py`. El agente inventó `obtener_usuario_id_desde_token`, cableó tres
    archivos a ella y se quedó una hora contra su propio `ImportError`.

    **T26** pedía `hashlib.scrypt` mientras `servicios/auth.py` compara `hashlib.sha256`.
    Registro habría guardado un hash que login no puede verificar, y ninguna prueba cruza
    registro con login.
    """

    CHEQUEO = SCRIPTS / "coherencia.py"

    def proyecto_de_juguete(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-coh-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        (d / "app").mkdir()
        (d / "app" / "auth.py").write_text(
            "import hashlib\n\n"
            "def login(email, password):\n"
            "    return hashlib.sha256(password.encode()).hexdigest()\n")
        return d

    def tarea(self, d, tid, contrato="", alcance=""):
        (d / "tareas" / f"{tid}-x.md").write_text(
            f"# {tid} — una cosa\n\n**Estado:** pendiente\n\n"
            f"## Alcance\n\nEntra:\n{alcance}\n\n## Contrato\n\n```python\n{contrato}\n```\n")

    def correr(self, d):
        return correr(f"python3 {self.CHEQUEO}", d)

    def test_un_import_que_nadie_provee_da_rojo(self):
        """Cadáver 1. El contrato importa un símbolo que no está en el tronco y que ninguna
        otra tarea declara: la tarea es inejecutable y el agente va a inventarlo."""
        d = self.proyecto_de_juguete()
        self.tarea(d, "T05", contrato="from app.auth import usuario_desde_token")
        r = self.correr(d)
        self.assertEqual(r.returncode, 1, f"tenía que dar rojo:\n{r.stdout}{r.stderr}")
        self.assertIn("usuario_desde_token", r.stdout)
        self.assertIn("ninguna tarea", r.stdout, "y decir que nadie lo provee")

    def test_un_import_que_otra_tarea_declara_no_da_rojo(self):
        """El control del otro lado: si alguna tarea lo promete en su contrato, está provisto."""
        d = self.proyecto_de_juguete()
        self.tarea(d, "T04b", contrato="def usuario_desde_token(token: str) -> int | None:\n    ...")
        self.tarea(d, "T05", contrato="from app.auth import usuario_desde_token")
        r = self.correr(d)
        self.assertEqual(r.returncode, 0, f"T04b lo declara:\n{r.stdout}{r.stderr}")

    def test_un_import_que_ya_esta_en_el_tronco_no_da_rojo(self):
        d = self.proyecto_de_juguete()
        self.tarea(d, "T05", contrato="from app.auth import login")
        self.assertEqual(self.correr(d).returncode, 0, "`login` existe en el tronco")

    def test_la_biblioteca_estandar_no_la_provee_ninguna_tarea(self):
        """La lista blanca a mano tenía tres nombres y `contextlib` salía como huérfano."""
        d = self.proyecto_de_juguete()
        self.tarea(d, "T02", contrato="from contextlib import contextmanager\nimport hashlib")
        self.assertEqual(self.correr(d).returncode, 0, "contextlib es de la estándar")

    def test_un_algoritmo_que_contradice_al_codigo_avisa(self):
        """Cadáver 2. El par importa: el enunciado contra el CÓDIGO, no contra otro enunciado
        — `sha256` vivía en `auth.py` y no en el texto de T04."""
        d = self.proyecto_de_juguete()
        self.tarea(d, "T26", alcance="- Hash de la contraseña con `hashlib.scrypt`.")
        r = self.correr(d)
        self.assertIn("hashlib.scrypt", r.stdout, f"no avisó:\n{r.stdout}")
        self.assertIn("hashlib.sha256", r.stdout, "y tiene que decir qué usa el código")
        self.assertIn("auth.py", r.stdout, "nombrando el archivo")
        self.assertEqual(r.returncode, 0, "es aviso, no rojo: puede ser legítimo")

    def test_el_plan_no_arranca_si_las_tareas_se_contradicen(self):
        """No alcanza con informarlo: tiene que frenar antes de gastar una llamada al modelo.

        Chequeo de forma porque la conducta pide una corrida entera, y además `ubicar_proyecto`
        saca `RAIZ` del PRIMER worktree que lista git —el principal— así que un
        `correr-todo.sh` lanzado desde un worktree de desarrollo lee el proyecto del tronco y
        no el de al lado. Lo aprendí midiendo el árbol equivocado."""
        fuente = (SCRIPTS / "correr-todo.sh").read_text()
        self.assertIn("coherencia.py", fuente, "el arranque tiene que cruzar las tareas")
        # Y afuera del bloque de error de validar-plan: adentro, sólo corre cuando ESA falla.
        i = fuente.index("coherencia.py")
        antes = fuente[:i]
        self.assertNotIn("Arreglalo antes de lanzar", antes.split("validar-plan.py")[-1],
                         "quedó dentro del `|| {` de validar-plan: sólo corre si ésa falla")
        tramo = fuente[i:i + 900]
        self.assertIn("exit 1", tramo, "informarlo no alcanza: tiene que frenar")

    def test_lo_que_la_tarea_dice_que_NO_hace_no_cuenta(self):
        """En este repo cada arreglo documenta su cadáver, así que una tarea corregida CITA el
        defecto viejo. Un chequeo que lee prosa vería la cita como la declaración, y le pasaría
        con TODA tarea arreglada."""
        d = self.proyecto_de_juguete()
        (d / "tareas" / "T26-x.md").write_text(
            "# T26 — registro\n\n## Alcance\n\nEntra:\n"
            "- Hash con el mismo esquema que usa `app/auth.py`.\n\n"
            "No entra:\n"
            "- Cambiar el esquema. Acá decía «hash con `hashlib.scrypt`» y era un defecto.\n\n"
            "## Contrato\n\n```python\ndef crear(email, password) -> int:\n    ...\n```\n")
        r = self.correr(d)
        self.assertNotIn("⚠", r.stdout,
                         f"la cita del defecto viejo no es una declaración:\n{r.stdout}")


class TestElBrazoNuloDelValidadorDeTests(unittest.TestCase):
    """Los tres pasos del validador preguntan «¿este test distingue ESTE cambio?». Faltaba el
    anterior: **¿distingue algo de nada?**

    El test aceptado de T04b tenía cinco pruebas y las cinco negativas —token inválido, vacío,
    nulo, mal formado, id inexistente— y ninguna verificaba que un token válido devolviera el
    id, que era el criterio de la tarea. Pasó los tres pasos: falla sin la implementación (por
    `ImportError`), pasa con la del agente, y los mutantes mueren sobre la lógica de ésa. Pero
    `def usuario_desde_token(token): return None` pasaba los cinco.

    `experimentos/README.md` ya exige un brazo nulo para los experimentos por este mismo
    motivo: «el sujeto reemplazado por un no-op, rojo obligatorio en todos».
    """

    VACIAR = SCRIPTS / "vaciar.py"

    def vaciar(self, d, *archivos):
        return correr(f"python3 {self.VACIAR} " + " ".join(archivos), d)

    def test_vacia_el_cuerpo_y_deja_todo_lo_que_el_import_necesita(self):
        """Si lo que rompe es el import, el rojo no distingue nada: es el mismo rojo del paso
        1. Así que firma, imports, clases y constantes de módulo se conservan."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-vaciar-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "m.py").write_text(
            "import hashlib\n\n"
            "CONSTANTE = 42\n\n"
            "def f(x: int) -> int | None:\n"
            '    """Lo que hace."""\n'
            "    return x * 2\n\n"
            "class C:\n"
            "    def g(self):\n"
            "        return 'algo'\n")
        r = self.vaciar(d, "m.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        salida = (d / "m.py").read_text()
        for conservado in ("import hashlib", "CONSTANTE = 42", "def f(x: int)", "class C",
                           "Lo que hace"):
            self.assertIn(conservado, salida, f"se perdió «{conservado}»")
        self.assertNotIn("x * 2", salida, "no vació el cuerpo de f")
        self.assertNotIn("'algo'", salida, "no vació el método g")
        # Y el original se guarda, para poder volver.
        self.assertTrue((d / "m.py.vaciar-original").exists(), "no guardó el original")
        r = correr(f"python3 {self.VACIAR} --restaurar", d)
        self.assertIn("x * 2", (d / "m.py").read_text(), "no restauró")

    def test_un_test_de_puros_casos_negativos_pasa_con_los_cuerpos_vacios(self):
        """El caso real que lo motivó, reproducido: el test de T04b tal como fue aceptado."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-vacuo-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "impl.py").write_text(
            "PREFIJO = 'tok-'\n\n"
            "def usuario_desde_token(token):\n"
            "    if not token or not isinstance(token, str):\n"
            "        return None\n"
            "    if not token.startswith(PREFIJO):\n"
            "        return None\n"
            "    return int(token[len(PREFIJO):])\n")
        # Cinco casos y los cinco negativos: es el test que fue aceptado.
        (d / "test_impl.py").write_text(
            "from impl import usuario_desde_token\n\n"
            "def test_invalido(): assert usuario_desde_token('nada') is None\n"
            "def test_vacio(): assert usuario_desde_token('') is None\n"
            "def test_nulo(): assert usuario_desde_token(None) is None\n")
        suite = f"python3 -m pytest -q test_impl.py"
        self.assertEqual(correr(suite, d).returncode, 0,
                         "el test tiene que pasar con la implementación de verdad")
        self.vaciar(d, "impl.py")
        r = correr(suite, d)
        self.assertEqual(r.returncode, 0,
                         "este test es vacuo a propósito: TIENE que pasar con los cuerpos "
                         "vacíos, y por eso el brazo nulo lo reprueba")

    def test_un_test_con_el_caso_positivo_falla_con_los_cuerpos_vacios(self):
        """El control del otro lado: el brazo nulo no puede reprobar un test bueno."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-bueno-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "impl.py").write_text(
            "PREFIJO = 'tok-'\n\n"
            "def usuario_desde_token(token):\n"
            "    if not token or not isinstance(token, str):\n"
            "        return None\n"
            "    if not token.startswith(PREFIJO):\n"
            "        return None\n"
            "    return int(token[len(PREFIJO):])\n")
        # El mismo test, MÁS el caso positivo: el que faltaba.
        (d / "test_impl.py").write_text(
            "from impl import usuario_desde_token\n\n"
            "def test_valido(): assert usuario_desde_token('tok-7') == 7\n"
            "def test_invalido(): assert usuario_desde_token('nada') is None\n"
            "def test_vacio(): assert usuario_desde_token('') is None\n")
        suite = f"python3 -m pytest -q test_impl.py"
        self.assertEqual(correr(suite, d).returncode, 0, "tiene que pasar con la implementación")
        self.vaciar(d, "impl.py")
        self.assertNotEqual(correr(suite, d).returncode, 0,
                            "con el caso positivo, los cuerpos vacíos TIENEN que fallar")

    def test_el_validador_corre_el_brazo_nulo(self):
        f = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertIn("vaciar.py", f, "el validador tiene que armar el brazo nulo")
        self.assertIn("cuerpos VACÍOS", f, "y reprobar el test que lo satisface")
        self.assertIn("--restaurar", f, "y devolver la implementación después")


class TestUnCorteQueTrabajoNoEsUnCorteQueColgo(unittest.TestCase):
    """Dos fallas distintas que compartían un contador, y por eso ninguna decía nada.

    El presupuesto de 12 cortes está justificado con esta cuenta, textual del código: «con el
    cuelgue de arranque cortado a los 20s, doce cortes son cuatro minutos de sobrecarga en el
    peor caso». Eso vale para el corte por INACTIVIDAD, que es el cuelgue transitorio de la
    herramienta —opencode inicializa y nunca le pide nada al modelo— donde insistir es la
    respuesta correcta.

    Un corte por LÍMITE TOTAL es otra cosa: el agente trabajó los 1200 s y no terminó. Doce de
    esos son cuatro horas, y no hablan de la herramienta: hablan de la TAREA. Medido en T05:
    tres cortes seguidos por límite total, cero por inactividad, y el agente iterando contra un
    `ImportError` de una función que él mismo inventó porque la tarea le exigía autorización
    sin decirle con qué.
    """

    FUENTE = SCRIPTS / "escribir-tests.sh"

    def test_los_dos_cortes_tienen_presupuestos_distintos(self):
        f = self.FUENTE.read_text()
        self.assertIn("CORTES_TOTAL_MAX", f,
                      "el corte por límite total necesita su propio presupuesto")
        self.assertRegex(f, r'CORTES_TOTAL_MAX="\$\{CORTES_TOTAL_MAX:-[1-3]\}"',
                         "el presupuesto de límite total tiene que ser chico: 12 son 4 horas")
        self.assertRegex(f, r'CORTES_MAX="\$\{CORTES_MAX:-\d+\}"',
                         "el de inactividad se queda generoso: es transitorio")

    def test_el_corte_por_limite_total_se_decide_por_el_motivo(self):
        """`motivo_del_corte` ya distinguía los dos casos; lo que faltaba era usar la
        distinción para presupuestar."""
        f = self.FUENTE.read_text()
        tramo = f.split('RC_AGENTE:-0}" = "142"')[-1]
        self.assertIn("límite total", tramo,
                      "la rama de corte tiene que ramificar por el motivo, no contar todo igual")
        self.assertIn("cortes_total", tramo, "y llevar la cuenta aparte")

    def test_el_mensaje_dice_cual_de_los_dos_fue(self):
        """«corte 3 de 12» no distingue «la herramienta no arrancó» de «la tarea no entra», y
        son decisiones opuestas: una se reintenta, la otra se replanifica."""
        f = self.FUENTE.read_text()
        self.assertIn("corte por límite total", f)
        self.assertIn("corte por inactividad", f)
        self.assertIn("es la TAREA", f,
                      "al agotarse, tiene que decir de quién es el defecto")


class TestLaDeclaracionDelProyectoLlegaALosHijos(unittest.TestCase):
    """`ubicar_proyecto` fijaba PROYECTO como variable de shell y no la exportaba, así que
    cada script hijo tenía que re-detectarla del cwd. Sale bien mientras el cwd esté adentro
    del proyecto; cuando no —justo después de borrar un worktree— la detección busca un
    `tareas/` hacia abajo, encuentra los DOS ejemplos de este repo, y muere con «Hay varios
    proyectos». Pasó en la etapa 1 de clasificados: un error impreso que no correspondía a
    ninguna decisión y que podía tapar uno real."""

    def test_un_hijo_hereda_el_proyecto_aunque_el_cwd_no_lo_diga(self):
        proy = RAIZ / "ejemplo-clasificados"
        dentro = (f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto; cd "$RAIZ"; '
                  f'bash -c ". {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto && '
                  f'echo HIJO=$PROYECTO"')
        r = correr("bash -c " + shlex.quote(dentro), proy)
        self.assertIn("HIJO=ejemplo-clasificados", r.stdout,
                      f"el hijo no heredó el proyecto:\n{r.stdout}\n{r.stderr}")
        self.assertNotIn("Hay varios proyectos", r.stdout + r.stderr,
                         "re-detectó en vez de heredar")

    def test_sin_el_export_el_hijo_no_puede_adivinar(self):
        """El control del otro lado: desde la raíz del repo, sin PROYECTO en el entorno, la
        detección automática NO puede elegir — y eso es correcto, no un bug. Lo que estaba mal
        era que el padre lo supiera y no se lo pasara."""
        dentro = (f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto 2>&1 | head -2')
        r = correr("env -u PROYECTO bash -c " + shlex.quote(dentro), RAIZ)
        salida = r.stdout + r.stderr
        if "Hay varios proyectos" not in salida:
            self.skipTest("este repo ya no tiene dos proyectos de ejemplo: el caso no aplica")
        self.assertIn("ejemplo-", salida, "y tiene que listar los candidatos")


class TestElPaso4DistingueDeVerdad(CasoBase):
    """El paso 4 es el UNICO chequeo de que los tests distinguen, y era el mas roto del gate.

    Tres defectos a la vez, los tres medidos: el gate de pacman **no lo tenia**; el de
    clasificados exigia solo que fallara la suite ENTERA —que esta roja por diseno mientras
    una etapa esta en vuelo (tests-first), asi que imprimia el visto siempre—; y el patron que
    acota por clase de test anclaba en `tests/`, con lo que en clasificados acotaba en 0 de 31
    porque sus rutas son `backend/tests/` y `frontend/tests/`.
    """

    GATES = sorted([PLANTILLAS / "gate.sh"] + list(RAIZ.glob("ejemplo-*/scripts/gate.sh")))

    def test_los_tres_gates_tienen_paso_4(self):
        """pacman cerro 19 tareas sin este paso. No es un chequeo mas: es el que sostiene P2."""
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                fuente = gate.read_text()
                self.assertIn("4. \u00bfLos tests distinguen?", fuente,
                              "a este gate le falta el paso 4")
                self.assertIn("test_de_la_tarea", fuente,
                              "el paso 4 tiene que acotar por la clase que declara la tarea")

    def test_el_extractor_acepta_las_dos_formas_de_la_declaracion(self):
        """La misma declaracion aparece en dos formas en el repo. Anclar en «Archivo:» perdia
        T16 de pacman; anclar en `tests/` perdia las 31 de clasificados. Lo que la identifica
        es la ruta y la clase juntas."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-decl-t4-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        casos = {
            "T01": ("Archivo: `backend/tests/test_errores.py`, clase `TestErrores`.",
                    "backend/tests/test_errores.py TestErrores"),
            "T02": ("> **Los tests ya estan escritos y fallan** (`tests/test_juego.py`, clase `TestFruta`).",
                    "tests/test_juego.py TestFruta"),
            "T03": ("**Prohibido tocar:** `tests/` (los tests ya estan), `otro.py`, `mas.py`", ""),
        }
        for tid, (linea, espera) in casos.items():
            (d / "tareas" / f"{tid}-x.md").write_text(linea + "\n")
        for tid, (_, espera) in casos.items():
            with self.subTest(tarea=tid):
                r = correr("bash -c " + shlex.quote(
                    "sed -n 's/.*`\\([^`]*\\)`, *clase `\\([A-Za-z0-9_]*\\)`.*/\\1 \\2/p' "
                    f"tareas/{tid}-x.md | head -1"), d)
                self.assertEqual(r.stdout.strip(), espera,
                                 f"la declaracion de {tid} se leyo mal")

    def test_el_acotamiento_alcanza_a_las_tareas_reales_de_los_dos_ejemplos(self):
        """Datos reales, no de juguete. El patron viejo anclaba en `tests/` y las rutas de
        clasificados son `backend/tests/` y `frontend/tests/`: acotaba en **0 de 31**, asi que
        el paso 4 se conformaba con «la suite entera falla» en todas las tareas del proyecto
        que mas corrimos. Un patron que no alcanza a los datos del propio repo no es un
        patron: es una declaracion que el lector no recibe."""
        # El patron sale DEL GATE, no de una copia en el test: si el del gate se desvia, este
        # test se entera. Un test con su propia copia de la regla mide los datos, no la regla.
        import re as _re
        fuente = (PLANTILLAS / "gate.sh").read_text()
        m = _re.search(r"sed -n 's/\.\*(.+?)\.\*/", fuente)
        self.assertIsNotNone(m, "no encontre el patron de test_de_la_tarea en la plantilla")
        PATRON = _re.compile(
            m.group(1).replace("\\(", "(").replace("\\)", ")").replace("\\|", "|"))
        totales = {}
        for proy in sorted(RAIZ.glob("ejemplo-*/tareas")):
            tareas = sorted(proy.glob("*.md"))
            acotables = [f for f in tareas if PATRON.search(f.read_text())]
            totales[proy.parent.name] = (len(acotables), len(tareas))
        self.assertIn("ejemplo-clasificados", totales, "no encontre las tareas de clasificados")
        acot, tot = totales["ejemplo-clasificados"]
        self.assertEqual(acot, tot,
                         f"clasificados: {acot} de {tot} tareas acotables; el paso 4 no puede "
                         "verificar las demas")
        acot_p, tot_p = totales.get("ejemplo-pacman", (0, 0))
        self.assertGreaterEqual(acot_p, 3,
                                f"pacman: solo {acot_p} de {tot_p} acotables, menos que antes")

    def test_la_suite_roja_por_otra_causa_no_es_prueba_de_que_estos_tests_distingan(self):
        """**El caso que producia el falso verde**, y es el normal en este metodo: el tronco
        esta rojo por diseno mientras una etapa esta en vuelo (tests-first). El gate de
        clasificados exigia solo «la suite entera falla», que ya se cumplia ANTES de revertir,
        asi que imprimia el visto siempre. Aca la suite esta roja por un test ajeno y la clase
        de la tarea pasa con el codigo viejo: tiene que dar rojo, y nombrar la clase."""
        p = self.p
        p.declarar("src/cosa.py")
        # El test de la tarea pasa con cualquier implementacion: no distingue.
        (p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nimport src.cosa\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_existe(self):\n        self.assertTrue(hasattr(src.cosa, '__file__'))\n")
        # Y un test de OTRA etapa, ya escrito y fallando: el tronco rojo por diseno.
        (p.dir / "tests" / "test_otra_etapa.py").write_text(
            "import unittest\n\nclass TestOtraEtapa(unittest.TestCase):\n"
            "    def test_pendiente(self):\n        from src.todavia_no import g  # noqa: F401\n")
        (p.dir / "src" / "cosa.py").write_text("def f():\n    return 1\n")
        p.git("add -A"); p.git('commit -qm "tronco rojo por diseno + test que no distingue"')
        p.implementar("def f():\n    return 42\n")
        r = p.gate("T01")
        paso4 = r.stdout.split("4. \u00bfLos tests distinguen?")[-1]
        self.assertIn("NO por los tests de esta tarea", paso4,
                      "con la suite roja por otra causa, el paso 4 no puede dar el visto:\n"
                      + paso4)
        self.assertIn("TestCosa", paso4, "y tiene que nombrar la clase que corrio")
        self.assertNotEqual(r.returncode, 0, "y el gate entero tiene que salir en rojo")

    @staticmethod
    def _seccion_paso4(salida):
        """Las lineas DEL PASO 4, no todo lo que viene despues.

        La primera version de estos tests buscaba el simbolo de vacuidad en
        `salida.split("4. ...")[-1]`, que incluye la linea de veredicto final — y esa linea
        dice «GATE VERDE — con N chequeo/s que no pudieron correr». O sea que el assert
        matcheaba el vacuo del veredicto, no el del paso 4, y pasaba con el gate roto. Es la
        misma falla que estos tests existen para atrapar, en el test."""
        cuerpo = salida.split("4. \u00bfLos tests distinguen?")[-1]
        lineas = []
        for l in cuerpo.splitlines():
            if l.startswith("\u2500\u2500 ") or l.startswith("GATE "):
                break
            lineas.append(l)
        return "\n".join(lineas)

    def test_el_paso_4_respeta_el_contrato_de_codigos_del_corredor(self):
        """`correr-suite.sh` tiene un contrato: 0 pasa, 1 falla, 2 no corrio ningun test,
        3 es del metodo, 127 falta el corredor. El paso 4 leia TODO lo distinto de cero como
        «los tests fallan», asi que una suite vacia o un corredor ausente se informaban como
        el visto en el unico chequeo de que los tests distinguen. El paso 1 ya respetaba el
        contrato con un `case`; el paso 4 no.

        Chequeo de forma: los codigos 2, 3 y 127 no son alcanzables desde el proyecto de
        juguete sin romper el corredor, y romperlo medir\u00eda el corredor y no el gate."""
        for gate in self.GATES:
            with self.subTest(gate=str(gate.relative_to(RAIZ))):
                fuente = gate.read_text()
                tramo = fuente.split("4. \u00bfLos tests distinguen?")[-1].split("\n# \u2500\u2500 5.")[0]
                self.assertIn("RC_T4", tramo,
                              "el paso 4 tiene que capturar el codigo del corredor, no leer "
                              "«distinto de cero» como una falla de los tests")
                for codigo in ("0)", "1)", "2)", "3)"):
                    self.assertIn(codigo, tramo,
                                  f"el paso 4 no distingue el codigo {codigo} del contrato")

    def test_una_clase_que_no_distingue_no_se_informa_como_que_distingue(self):
        """Control negativo por conducta: si la clase declarada pasa con el codigo viejo, el
        paso 4 no puede imprimir el visto nombrandola."""
        p = self.p
        p.declarar("src/cosa.py")
        (p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nimport src.cosa\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_existe(self):\n        self.assertTrue(hasattr(src.cosa, '__file__'))\n")
        (p.dir / "src" / "cosa.py").write_text("def f():\n    return 1\n")
        p.git("add -A"); p.git('commit -qm "test que no distingue"')
        p.implementar("def f():\n    return 42\n")
        paso4 = self._seccion_paso4(p.gate("T01").stdout)
        self.assertNotIn("fallan los tests de la tarea", paso4,
                         f"afirmo que distinguen tests que pasan con el codigo viejo:\n{paso4}")


class TestElRegistroDiceLaVerdadSobreSiMismo(unittest.TestCase):
    """El registro de intentos es la única fuente honesta del método (deducir los intentos
    del texto de las tareas daba 80% donde la realidad era 0 de 4). Estos cuatro defectos
    estuvieron todos vivos a la vez, y los cuatro son la misma forma: **el instrumento
    informaba un número que no podía medir, o no informaba el que sí tenía.**
    """

    def test_la_huella_de_falla_es_una_linea(self):
        """El pipe final —`tr '\n' ' '` y `cut -c1-220`— había quedado DENTRO de un
        comentario que empezaba al final de la línea del `sed` y seguía dos líneas más. La
        huella devolvía hasta 4 líneas, cada salto partía la fila del CSV en dos, y el
        registro quedó con filas huérfanas de un campo. Un comentario que se come el código
        no se ve leyendo: se ve corriendo la función y contando las líneas."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        log = d / ".tarea.log"
        log.write_text("=== T08\n> ejecutor\nx\n=== gate ===\n"
                       "  ✓ tests y scripts intactos\n"
                       "  ✗ tocó archivos intocables (tests o el propio gate):\n"
                       "      tests/test_api.py\n      tests/test_db.py\n"
                       "=== rc=1\n=== fin T08 · hoy\n")
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_de_falla "{log}"', RAIZ)
        self.assertEqual(r.stdout.count("\n"), 0,
                         f"la huella tiene que ser UNA línea; salió:\n{r.stdout}")
        self.assertIn("intocables", r.stdout, "y tiene que decir la categoría")
        self.assertIn("test_api.py", r.stdout,
                      "y llevar el dato: sin él, dos archivos distintos dan la misma huella")

    def registro(self, d, encabezado, filas=()):
        reg = d / ".metricas" / "intentos.csv"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text("\n".join([encabezado, *filas]) + "\n")
        return reg

    def test_el_encabezado_nombra_todas_las_columnas_que_el_runner_escribe(self):
        """El encabezado se escribía SÓLO si el archivo no existía, así que agregar la
        columna `motivo` dejó un registro con 6 nombres y filas de 7 campos. `DictReader`
        manda el séptimo a la clave None: `metricas.sh` leía `motivo` vacío SIEMPRE y el
        bloque «motivos de rojo que se repiten» nunca imprimió nada, con datos de sobra.
        Una columna que nadie puede leer no existe."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-enc-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        reg = self.registro(d, "fecha,proyecto,tarea,veredicto,segundos,modelo",
                            ["2026-01-01T00:00:00Z,p,T01,ROJO,10,abc"])
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'anotar_intento T02 ROJO 11 abc', RAIZ)
        import csv as _csv
        with open(reg) as fh:
            lector = _csv.DictReader(fh)
            campos = lector.fieldnames or []
            filas = list(lector)
        self.assertIn("motivo", campos,
                      "el runner escribe `motivo`; si el encabezado no lo nombra, se lee vacío")
        self.assertTrue(all(None not in f for f in filas),
                        "ninguna fila puede tener campos que el encabezado no nombra")

    def test_un_motivo_de_varias_lineas_no_parte_la_fila(self):
        """Sanear acá además de arreglar la huella es a propósito: el registro no puede
        depender de que quien lo alimenta se porte bien."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-multi-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        reg = self.registro(d, "fecha,proyecto,tarea,veredicto,segundos,modelo,motivo")
        log = d / ".tarea.log"
        log.write_text("=== T01\n> ejecutor\nx\n=== gate ===\n"
                       "  ✗ tocó archivos intocables:\n      tests/a.py\n      tests/b.py\n"
                       "=== rc=1\n=== fin T01 · hoy\n")
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'anotar_intento T01 ROJO 12 abc "{log}"', RAIZ)
        lineas = reg.read_text().strip().split("\n")
        cuerpo = [l for l in lineas[1:] if l]
        self.assertEqual(len(cuerpo), 1, f"una corrida es UNA fila; salieron:\n{cuerpo}")
        # Tantos campos como nombres tenga el encabezado, no un número clavado: el esquema
        # creció de 7 a 9 columnas y un número en el test lo habría convertido en una falla
        # falsa en vez de verificar la invariante, que es «la fila no se parte».
        self.assertEqual(cuerpo[0].count(","), lineas[0].count(","),
                         f"la fila no tiene el ancho del encabezado:\n{lineas[0]}\n{cuerpo[0]}")

    def test_no_se_informa_una_mediana_de_corridas_simultaneas(self):
        """`correr-tarea.sh` corre con PARALELAS=8 por omisión, y el mismo modelo pasa de
        16,3 a 122 tok/s según la ocupación: el tiempo de corridas simultáneas describe la
        plataforma, no la tarea.

        El dato lo tiene quien corrió, no quien analiza: el runner escribe la columna
        `concurrencia`. Antes esto se inferÍa comparando timestamps a 60 s, que era un
        paliativo —dos corridas pueden arrancar en el mismo segundo sin competir, y dos
        separadas por minutos pueden solaparse si la primera duró mucho—."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-med-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "p" / "tareas").mkdir(parents=True)
        (d / "p" / "tareas" / "T01-x.md").write_text("# T01\n")
        correr("git init -q . && git add -A && "
               "git -c user.email=t@t -c user.name=t commit -qm x", d)
        enc9 = ("fecha,proyecto,tarea,veredicto,segundos,modelo,motivo,"
                "concurrencia,instrumento")

        def filas(conc):
            return [f"2026-01-0{i}T00:00:00Z,p,T0{i},VERDE,{100 + i * 10},abc,,{conc},aaaaaaa"
                    for i in range(1, 7)]

        casos = (
            ("serializadas", enc9, filas(1), "mediana"),
            ("simultaneas", enc9, filas(8), "—"),
            # El esquema viejo: la columna no existe, así que el dato no está. Eso NO es
            # «concurrencia 1»: es que no se sabe, y un tiempo que no se puede atribuir no
            # entra en la mediana. Suponerlo serializado sería inventar el dato.
            ("sin la columna",
             "fecha,proyecto,tarea,veredicto,segundos,modelo,motivo",
             [f"2026-01-0{i}T00:00:00Z,p,T0{i},VERDE,{100 + i * 10},abc," for i in range(1, 7)],
             "⊘"),
        )
        for caso, enc, cuerpo, espera in casos:
            with self.subTest(caso=caso):
                reg = d / ".metricas" / "intentos.csv"
                reg.parent.mkdir(parents=True, exist_ok=True)
                reg.write_text("\n".join([enc, *cuerpo]) + "\n")
                r = correr(f"bash {SCRIPTS}/metricas.sh", d / "p", PROYECTO="p")
                tiempo = [l for l in r.stdout.split("\n")
                          if "Tiempo por intento" in l or "sin columna" in l]
                self.assertTrue(tiempo, f"no imprimió nada de tiempo:\n{r.stdout}\n{r.stderr}")
                self.assertIn(espera, "\n".join(tiempo),
                              f"caso «{caso}»: esperaba «{espera}» y dijo:\n"
                              + "\n".join(tiempo))

    def test_el_veredicto_del_gate_se_captura_pegado_a_su_llamada(self):
        """`local rc=$?` leía el estado del bloque de memoria que se insertó en el medio, y
        un `if` con condición falsa vale 0: el runner imprimía «✓ gate VERDE» SIEMPRE. El
        método existe porque un agente dijo «GATE VERDE» con el gate rojo; esto era el arnés
        haciendo lo mismo, y 162 tests pasaban sin verlo.

        Chequeo de forma porque la conducta pide una corrida de agente entera. Lo que pina
        es la regla: entre `cerrar_con_gate` y la captura de `$?` no puede haber nada que se
        ejecute."""
        fuente = (SCRIPTS / "correr-tarea.sh").read_text().split("\n")
        llamada = [i for i, l in enumerate(fuente) if "cerrar_con_gate" in l and not l.strip().startswith("#")]
        self.assertTrue(llamada, "correr-tarea.sh dejó de llamar al gate")
        i = llamada[0]
        resto = fuente[i + 1:]
        captura = next((j for j, l in enumerate(resto) if "rc=$?" in l), None)
        self.assertIsNotNone(captura, "nadie captura el código de salida del gate")
        medio = [l for l in resto[:captura] if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(medio, [],
                         "entre el gate y la captura de $? hay código que se ejecuta, así "
                         "que $? es el estado de ESO y no del gate:\n  " + "\n  ".join(medio))

    def test_una_memoria_que_no_llega_lo_dice(self):
        """T06 se partió en T06a/T06b/T06c y su archivo de tarea se borró. Un `memoria/T06.md`
        queda inalcanzable para siempre, y antes se descartaba callado: la memoria existía y
        no llegaba, sin que nadie se enterara. Los registros globales (prefijo `_`, los lee
        el replanificador) sí se saltan callados, porque no son de ninguna tarea."""
        proy = RAIZ / "ejemplo-clasificados"
        perdida = proy / "memoria" / "T06.md"
        self.assertFalse(perdida.exists(), "el repo ya tiene un memoria/T06.md; ajustá el test")
        perdida.write_text("## x\n**Falló así:** algo\n"
                           "**Quedó en verde al:** backend/app/main.py\n")
        self.addCleanup(perdida.unlink, True)
        # `bash -c` explícito: `correr` usa /bin/sh, que rechaza el `<(...)` de `memoria_para`
        # y aborta el sourcing ahí. Ver test_comun_se_sourcea_completo.
        dentro = (f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; "
                  "ubicar_proyecto >/dev/null 2>&1; memoria_para T06c")
        r = correr("bash -c " + shlex.quote(dentro), proy)
        self.assertIn("T06.md", r.stderr,
                      "un registro cuya tarea ya no existe tiene que avisar, no desaparecer")
        self.assertNotIn("_planificacion", r.stderr,
                         "el registro global del planificador no es una memoria perdida")

    def test_comun_se_sourcea_completo(self):
        """`correr()` lanza con `shell=True`, o sea **/bin/sh**, que rechaza el `<(...)` de
        `memoria_para`: el sourcing abortaba AHI y las funciones definidas despues no
        existian. Los tests que usan funciones anteriores a esa linea pasaban igual, asi que
        el arnes sourceaba el archivo a medias sin que nada lo dijera.

        Es el instrumento, no el sujeto: un test que se cae por el interprete y no por el
        codigo mide el interprete."""
        fuente = (SCRIPTS / "_comun.sh").read_text()
        declaradas = sorted(set(re.findall(r"^([a-z_][a-z0-9_]*)\(\) *\{", fuente, re.M)))
        self.assertGreater(len(declaradas), 10, "no encontre las funciones de _comun.sh")
        dentro = f". {SCRIPTS}/_comun.sh >/dev/null 2>&1; declare -F"
        r = correr("bash -c " + shlex.quote(dentro), RAIZ)
        faltan = [f for f in declaradas if f" {f}" not in r.stdout]
        self.assertEqual(faltan, [],
                         "bajo bash tienen que definirse TODAS; faltaron: " + ", ".join(faltan))

    def test_un_if_con_condicion_falsa_vale_cero(self):
        """El hecho de bash que hizo posible el defecto de arriba, pineado aparte para que
        el test anterior no haya que creerlo: no es que el gate devolviera 0, es que `$?`
        había dejado de ser el del gate."""
        r = correr('f(){ return 7; }; f; if false; then :; fi; echo "rc=$?"', RAIZ)
        self.assertIn("rc=0", r.stdout,
                      "si esto cambia, el test de forma de arriba puede relajarse")


class TestLosScriptsOperanSobreElArbolDelQueSalieron(unittest.TestCase):
    """`RAIZ` salía de `git worktree list | head -1`, que es el worktree PRINCIPAL. Corriendo
    el plan desde un worktree de desarrollo, los scripts de ese worktree operaban sobre el
    proyecto del tronco. Hoy me hizo afirmar «el import huérfano no se detecta» cuando sí se
    detectaba: medí el árbol equivocado y le creí al número. Y hacía fallar a
    `test_una_memoria_que_no_llega_lo_dice`, que escribe en el `RAIZ` de Python y lee con el
    de shell: la suite estaba verde sólo porque siempre la corría desde el árbol principal.

    El arreglo es `--show-toplevel`, NO `dirname $BASH_SOURCE`: RAIZ es el repo del proyecto,
    que puede no ser el repo donde viven los scripts."""

    def _repo_con_dos_worktrees(self):
        # .resolve() porque en esta Mac mkdtemp devuelve /var/... y `pwd -P` /private/var/...:
        # sin esto el test compara dos nombres del mismo directorio y falla por el symlink.
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-raiz-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        principal, otro = d / "principal", d / "otro"
        (principal / "scripts").mkdir(parents=True)
        (principal / "proy" / "tareas").mkdir(parents=True)
        (principal / "scripts" / "_comun.sh").write_text((SCRIPTS / "_comun.sh").read_text())
        # Un archivo adentro de tareas/: git no versiona directorios vacíos, así que sin
        # esto el worktree nuevo no tiene proy/tareas y el fixture miente (lo vi probándolo:
        # el brazo arreglado «fallaba» por el fixture, no por el arreglo). Es la trampa de T01.
        (principal / "proy" / "tareas" / "T01-algo.md").write_text("# T01\n")
        (principal / "quien-soy").write_text("principal\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
                    ["worktree", "add", "-q", str(otro)]):
            subprocess.run(["git", *cmd], cwd=principal, check=True,
                           capture_output=True)
        (otro / "quien-soy").write_text("otro\n")
        return principal, otro

    def test_raiz_es_el_worktree_del_script_y_no_el_principal(self):
        principal, otro = self._repo_con_dos_worktrees()
        # Se corre el `_comun.sh` DEL worktree «otro», con el cwd adentro de «otro».
        r = subprocess.run(
            ["bash", "-c", '. ./scripts/_comun.sh; ubicar_proyecto; echo "RAIZ=$RAIZ"'],
            cwd=otro, capture_output=True, text=True)
        self.assertIn(f"RAIZ={otro}", r.stdout,
                      "los scripts de un worktree operan sobre el árbol de OTRO:\n"
                      f"  esperaba {otro}\n  salida: {r.stdout}{r.stderr}")

    def test_sin_el_arreglo_el_test_falla(self):
        """Brazo nulo del chequeo anterior: con la deducción vieja tiene que dar el principal.
        Si no, el test de arriba pasa por cualquier motivo menos el que dice."""
        principal, otro = self._repo_con_dos_worktrees()
        comun = otro / "scripts" / "_comun.sh"
        texto = comun.read_text()
        nueva = [l for l in texto.split("\n") if l.strip() == 'RAIZ="$(git rev-parse --show-toplevel)"']
        self.assertEqual(len(nueva), 1, "cambió la línea de RAIZ; actualizá este brazo nulo")
        comun.write_text(texto.replace(
            nueva[0],
            '  RAIZ="$(git worktree list --porcelain | sed -n \'1s/^worktree //p\')"', 1))
        r = subprocess.run(
            ["bash", "-c", '. ./scripts/_comun.sh; ubicar_proyecto; echo "RAIZ=$RAIZ"'],
            cwd=otro, capture_output=True, text=True)
        self.assertIn(f"RAIZ={principal}", r.stdout,
                      "la deducción vieja ya no devuelve el principal, así que el test de "
                      f"arriba no distingue nada:\n  salida: {r.stdout}{r.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
