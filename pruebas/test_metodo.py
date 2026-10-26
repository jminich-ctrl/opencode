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
import json
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


def _test_en_curso():
    """El nombre del test que está corriendo, leído de la pila. `unittest` no lo publica en
    ninguna variable, y la alternativa —pasarlo a mano en cada construcción— se olvida en la
    primera llamada nueva."""
    import traceback
    for cuadro in reversed(traceback.extract_stack()):
        if cuadro.name.startswith("test") or cuadro.name in ("setUp", "setUpClass"):
            return f"{pathlib.Path(cuadro.filename).name}:{cuadro.lineno} {cuadro.name}"
    return "desconocido"


# Lo que resistió el borrado, para que la suite lo diga en vez de dejarlo callado.
NO_BORRADOS = []


def _a_la_fuerza(func, ruta, _exc):
    """Manejador de `rmtree`: los objetos de git son de sólo lectura (444) y no se borran sin
    tocarles el permiso. Si tampoco se puede así, se anota — no se traga.

    Vive a nivel de módulo y no como cierre dentro de `tirar` para que un test pueda
    alcanzarlo: lo que no se puede medir es lo que vuelve a romperse en silencio."""
    try:
        os.chmod(ruta, 0o700)
        func(ruta)
    except OSError as e:
        NO_BORRADOS.append((str(ruta), str(e)))


class Proyecto:
    """Un repo de juguete con la forma que el método espera, para perturbar y tirar."""

    def __init__(self, donde="proyecto"):
        # El proyecto va en un SUBDIRECTORIO del repo a propósito: es la configuración donde
        # aparecen los bugs de rutas (`git diff` y `git cat-file` informan desde la raíz del
        # repo, no del proyecto) y es como están los dos ejemplos. Con el proyecto en la
        # raíz, esos bugs no se reproducen y los tests dan verde con el bug puesto — lo
        # comprobamos reintroduciéndolos.
        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="prueba-metodo-"))
        # Quién lo creó, escrito ADENTRO del directorio. Hoy encontré 56 de estos huérfanos
        # en /var/folders —del 21 al 24 de octubre, un repo de juguete completo cada uno— y
        # no había forma de saber qué test los dejó: todos idénticos, sin logs, sin marca.
        # Un directorio que queda tirado y no dice de quién es obliga a adivinar, que es
        # exactamente lo que este método existe para no hacer. La evidencia viene con su
        # sujeto.
        # Sin `try`: si esto falla justo después de un `mkdtemp` que funcionó, es un
        # problema que hay que ver. Mi primera versión lo envolvió en `except OSError: pass`
        # y la guarda de este mismo archivo —la que vigila que no vuelva ese `pass`— lo
        # atrapó en el acto. Tenía razón: una marca que falla callada deja el directorio
        # huérfano otra vez sin sujeto, que es el defecto que la marca viene a arreglar.
        (self.repo / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        # `donde` es la ubicación del proyecto DENTRO del repo. Variarla es la relación
        # metamórfica del test de abajo: el veredicto no puede depender de dónde está.
        self.dir = self.repo if donde == "." else (self.repo / donde)
        self.dir.mkdir(parents=True, exist_ok=True)
        for d in ("tareas", "scripts", "src", "tests"):
            (self.dir / d).mkdir()
        shutil.copy(PLANTILLAS / "gate.sh", self.dir / "scripts" / "gate.sh")
        # El gate ya no sabe correr la suite: lo sabe correr-suite.sh, y los dos van juntos.
        shutil.copy(PLANTILLAS / "correr-suite.sh", self.dir / "scripts" / "correr-suite.sh")
        # El gate también depende de estos dos: si faltan, da rojo y lo dice. El comentario
        # decía «estos dos» y copiaba UNO: `_imports.py` quedaba sin resolver en todo proyecto
        # de juguete, y eso no se notaba porque su paso fallaba ABIERTO. Al hacerlo fallar
        # cerrado, 22 tests se pusieron rojos de golpe y mostraron que el fixture nunca lo
        # había tenido. La prosa decía una cosa y el código otra, en el fixture esta vez.
        # `mutar.py` entra en la lista: desde el 2026-10-25 el paso 4b del gate pregunta si
        # el test distingue ESTA implementación, y sin el auxiliar el paso da rojo —a propósito,
        # porque lo provee el método—. Un fixture al que le falta un auxiliar mide su ausencia.
        for aux in ("_suprimidas.py", "_imports.py", "mutar.py"):
            shutil.copy(SCRIPTS / aux, self.dir / "scripts" / aux)
        (self.dir / "src" / "__init__.py").touch()
        (self.dir / "tests" / "__init__.py").touch()
        # `.quien-lo-creo` va ignorado: lo escribe el andamio en la raíz del repo ANTES del
        # `git add -A`, y sin esto entraría en los commits del proyecto de juguete y
        # aparecería en cada `git status` que los tests miran. Una marca de diagnóstico que
        # cambia el sujeto medido es peor que no tenerla.
        (self.repo / ".gitignore").write_text(
            "__pycache__/\n*.pyc\n.tarea.log\n.base-ref\n.metricas/\n.opencode-data/\n"
            ".quien-lo-creo\n")
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
        #
        # Ese arreglo movió el silencio un nivel y no lo sacó: el `except OSError: pass` del
        # manejador hacía exactamente lo que el párrafo de arriba denuncia, dos líneas más
        # abajo. Ahora lo que resiste se ANOTA y la suite lo dice. Importa de verdad: hoy
        # llené el disco dos veces, y quedan 8,9 GiB.
        # Llamarlo dos veces no es basura en disco. Los dos tests de contabilidad del
        # veredicto tiran su proyecto en un `finally` y después `unittest` corre su propio
        # `tearDown` sobre el mismo: la segunda pasada daba FileNotFoundError, el manejador
        # la anotaba como «resistió» y el aviso acusaba de dejar basura un directorio
        # correctamente borrado. Un falso positivo en el chequeo que acabo de agregar, y del
        # mismo tipo que todo lo de hoy: el veredicto nombraba al sujeto equivocado.
        if not os.path.exists(self.repo):
            return
        antes = len(NO_BORRADOS)
        shutil.rmtree(self.repo, onerror=_a_la_fuerza)
        nuevos = len(NO_BORRADOS) - antes
        if nuevos or os.path.exists(self.repo):
            print(f"⚠ quedó basura en disco: {self.repo} — {nuevos} ruta(s) resistieron el "
                  f"chmod. Un rm que falla en silencio es un chequeo que no puede correr y "
                  f"dice que pasó.", file=sys.stderr)


class CasoBase(unittest.TestCase):
    def setUp(self):
        self.p = self._proyecto_marcado()

    def tearDown(self):
        self.p.tirar()

    def _proyecto_marcado(self):
        p = Proyecto()
        # El nombre exacto del test, encima del que puso `Proyecto`. `unittest` llama a
        # `setUp` ANTES de entrar al método, así que su cuadro no está en la pila y la marca
        # del andamio sólo puede decir «setUp»: con 300 tests que heredan de esta clase, eso
        # no nombra a nadie. Acá sí se sabe quién es.
        (p.repo / ".quien-lo-creo").write_text(self.id() + "\n")
        return p

    def rehacer_proyecto(self):
        """Un proyecto fresco en MEDIO de un test, sin dejar huérfano el anterior.

        Los dos tests de contabilidad del veredicto llamaban a `self.setUp()` dentro de su
        bucle de escenarios. `setUp` pisa `self.p` con un proyecto nuevo, así que el que
        `unittest` había creado antes de entrar al método quedaba abandonado y nadie lo tiraba
        jamás: un directorio por test, dos tests, dos por corrida. Había 55 acumulados en
        /var/folders del 21 al 24 de octubre —un repo de juguete completo cada uno, todos
        idénticos— y ninguno decía de quién era.

        Quien necesite rearmar el escenario usa esto y no `setUp`: la diferencia es el `tirar`
        del anterior."""
        self.p.tirar()
        self.p = self._proyecto_marcado()

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
        """`Ran 0 tests` contaba como verde. Una suite vacía pasa siempre.

        El archivo queda PRESENTE y sin tests, no borrado: borrarlo lo atrapa antes el
        chequeo de «declara un test que no está en el árbol», que es un rojo distinto y más
        preciso (ver TestUnTestDeclaradoYAusenteNoEsUnTestQuePasa). Con el archivo presente,
        el escenario ejercita lo que este test dice que ejercita."""
        self.p.implementar()
        (self.p.dir / "tests" / "test_cosa.py").write_text("# el archivo está, tests no hay\n")
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
        shutil.copy(SCRIPTS / "_suprimidas.py", self.p.dir / "scripts" / "_suprimidas.py")
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
        shutil.copy(SCRIPTS / "_suprimidas.py", self.p.dir / "scripts" / "_suprimidas.py")
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

    def test_una_falla_de_infraestructura_no_se_le_cobra_a_la_tarea(self):
        """La diferencia entre dos muestras de la suite NO es causal. Todos los worktrees
        comparten un MySQL, así que la base que la etapa de tests vio poblada la etapa de
        tareas la puede ver sin tablas, y la tarea cargaba con esa diferencia.

        Cadáver del 2026-10-21: T05a tocó UN archivo nuevo —`backend/app/datos/ads.py`,
        datos de avisos— y el gate la acusó de romper
        `test_register_backend.py::test_crear_usuario_hash_correcto`. Sacando ese archivo del
        worktree fallaban los mismos dos tests, y la causa era
        `(1146, "Table 'clasificados.users' doesn't exist")`. Dos intentos, punto muerto y el
        plan detenido por una falla que la tarea no podía causar: no toca registro ni hasheo.

        Es el mismo principio que el gate ya aplica a `FALTA_CORREDOR` —«es del método y no
        del código»— y no ablanda nada: detiene igual. Lo único que cambia es a quién se le
        cobra."""
        base = self.fijar_base()
        self.assertNotIn("test_infra", base, "al fijar la base esto todavía no existe")
        # El entorno se mueve DESPUÉS de la línea base: la tabla desaparece.
        (self.p.dir / "tests" / "test_infra.py").write_text(
            "import unittest\n\n"
            "class TestInfra(unittest.TestCase):\n"
            "    def test_lee_la_tabla(self):\n"
            "        raise Exception(\"(1146, \\\"Table 'clasificados.users' doesn't "
            "exist\\\")\")\n")
        self.p.implementar()
        r = self.p.gate("T01")
        salida = r.stdout + r.stderr
        self.assertIn("el entorno se movió", salida,
                      f"la tarea no puede cargar con una falla de infraestructura:\n{salida}")
        self.assertIn("ENTORNO_MOVIDO", salida,
                      f"y el runner necesita el marcador para no reintentar:\n{salida}")
        self.assertNotIn("rompiste tests", salida,
                         f"eso es acusar a la tarea de algo que no hizo:\n{salida}")
        # Y NO es verde: detener sigue siendo lo correcto.
        self.assertNotEqual(0, r.returncode,
                            f"no se ablanda el veredicto, se corrige el sujeto:\n{salida}")

    def test_una_rotura_de_verdad_sigue_siendo_de_la_tarea(self):
        """El guardia del arreglo de arriba. Si una falla nueva no trae firma de
        infraestructura, es del cambio y se dice así: lo contrario volvería «entorno» a
        cualquier rotura y apagaría el chequeo que de verdad protege al tronco."""
        # La base se fija CON T01 ya implementada: así la única falla nueva es la rotura que
        # este test introduce, y no el propio test de T01 que el fixture deja fallando.
        self.p.implementar()
        base = self.fijar_base()
        self.assertEqual("", base.strip(), f"la base tiene que quedar limpia: {base!r}")
        # Una rotura común: la tarea rompe un test de otra parte del proyecto.
        (self.p.dir / "tests" / "test_vecino.py").write_text(
            "import unittest\n\n"
            "class TestVecino(unittest.TestCase):\n"
            "    def test_suma(self):\n        self.assertEqual(2 + 2, 5)\n")
        r = self.p.gate("T01")
        salida = r.stdout + r.stderr
        self.assertIn("rompiste tests", salida,
                      f"una rotura sin firma de infraestructura es de la tarea:\n{salida}")
        self.assertNotIn("el entorno se movió", salida,
                         f"si todo fuera «entorno», el chequeo no protegería nada:\n{salida}")

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
        """Sólo las líneas que bash EJECUTA. Mirando el archivo entero, el chequeo reprueba la
        prosa: un comentario que escriba «los tests de $TAREA» queda marcado, y bash nunca
        evalúa un comentario. Pasó el 2026-10-19 con un comentario que explicaba un arreglo.
        Es la misma forma que el repo viene arreglando todo el día —un chequeo tan ancho que
        marca a todos— y acá la víctima era la documentación.

        Se saltan las líneas de comentario PURO, no los comentarios al final de una línea de
        código: ahí todavía puede haber un `$var` pegado que sí importa."""
        malos = []
        for f in self.scripts():
            datos = f.read_bytes()
            for m in self.PEGADA.finditer(datos):
                linea = datos[:m.start()].count(b"\n") + 1
                texto = datos.split(b"\n")[linea - 1]
                if texto.lstrip().startswith(b"#"):
                    continue
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
        # Se busca la LLAMADA a la guardia, no la variable interna `SALTEADAS`: la guardia
        # se mudó a `_comun.sh` porque `correr-plan.sh` tomaba el mismo índice SIN ella —el
        # arreglo había quedado en un solo hermano, que es el defecto que la guardia venía a
        # cerrar—. Un test clavado a la variable convierte ese arreglo en un rojo falso.
        self.assertIn(
            'rechazar_salteo "$DESDE"', texto,
            "correr-todo.sh N no comprueba si las etapas anteriores a N tienen tareas "
            "pendientes: los números se recalculan en cada corrida y saltar trabajo en "
            "silencio es la peor forma de fallar")
        self.assertIn(
            'rechazar_salteo "$DESDE"', (SCRIPTS / "correr-plan.sh").read_text(),
            "y correr-plan.sh toma el mismo índice: la guardia tiene que estar en los dos")


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
    _PY_CONEXION = ("import socket,threading,time;"
                    "srv=socket.socket();srv.bind(('127.0.0.1',0));srv.listen(1);vivos=[];"
                    "threading.Thread(target=lambda: vivos.append(srv.accept()),"
                    "daemon=True).start();"
                    "c=socket.create_connection(srv.getsockname());time.sleep(55)")
    CON_CONEXION = 'python3 -c ' + shlex.quote(_PY_CONEXION)
    # El mismo, pero el que tiene la conexión SE CAMBIA DE GRUPO con `setsid`.
    #
    # Es lo que hace el arnés real: medido el 2026-10-24, con el agente dentro de un `bash -c`
    # la conexión al modelo no aparece en el grupo y el vigilante corta a los 15s. Mi primera
    # versión de este caso usaba `bash -c` a secas y NO medía nada: un nieto hereda el pgid del
    # padre, así que `lsof -g` lo veía igual y la mutación a «sólo el grupo» quedaba verde.
    # Lo que saca al proceso del grupo es el `setsid`, no el envoltorio.
    _PY_FUERA_DEL_GRUPO = "import os;os.setsid();" + _PY_CONEXION
    FUERA_DEL_GRUPO = ("bash -c " + shlex.quote("python3 -c "
                       + shlex.quote(_PY_FUERA_DEL_GRUPO) + "; true"))

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

    def test_la_conexion_se_ve_aunque_el_agente_este_detras_de_un_envoltorio(self):
        """`lsof -g` mira el GRUPO de procesos, y el grupo no es el árbol: basta un envoltorio
        entre `con_limite` y el agente para que la conexión al modelo quede afuera del grupo
        que se consulta, y entonces el vigilante mata por «sin ninguna conexión abierta» a un
        agente que está esperando al modelo.

        Medido el 2026-10-24 con el arnés real y el modelo que razona:

            agente como hijo DIRECTO de con_limite  →  150s callado, NO se cortó por silencio
            el mismo agente dentro de `bash -c`     →  cortado a los 15s, «sin conexión»

        Hoy ningún call site envuelve al agente, así que no era un defecto activo: era una
        trampa para el próximo que agregue uno, y el síntoma habría sido «el agente se colgó»
        —el sujeto equivocado, otra vez—. El `; true` del envoltorio está para que bash NO
        haga exec del comando: sin eso no hay nieto y el test no mide nada."""
        r = self.correr_vigilado(self.FUERA_DEL_GRUPO)
        self.assertIn("rc=0", r.stdout,
                      "la conexión la tiene un NIETO del proceso vigilado; mirar sólo el "
                      f"grupo la pierde. Salida: {r.stdout!r} {r.stderr[-300:]!r}")

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
        shutil.copy(SCRIPTS / "_imports.py", self.p.dir / "scripts" / "_imports.py")
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
                self.rehacer_proyecto()
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
                self.rehacer_proyecto()
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
        base, y la tarea la arregla. Ahí los seis pasos tienen algo que decir.

        Y la implementación tiene que tener ALGO QUE MUTAR: desde que el gate pregunta si el
        test distingue ESTA implementación (paso 4b), un `return 42` pelado deja un ⊘ honesto
        —«no hubo nada que mutar con provecho»— y este caso dejaba de ser el escenario sin
        vacíos que necesita. El test seguía midiendo lo suyo; lo que había que actualizar era
        su escenario, porque el gate tiene un paso más que antes."""
        # El TEST primero —exige las dos ramas, así que hay un mutante que puede matar— y
        # después la implementación MALA, commiteada. El test queda rojo en la línea base y
        # la tarea lo arregla. Mi primera versión commiteaba la implementación buena junto
        # con el test, y entonces no quedaba cambio para la tarea: «no hay ningún cambio».
        (self.p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom src.cosa import f\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(), 42)\n"
            "    def test_tope(self):\n        self.assertEqual(f(200), 1)\n")
        self.p.implementar("def f(x=0):\n    return 0\n")   # mal, y commiteada
        self.p.git("add -A"); self.p.git('commit -qm "implementación equivocada"')
        r0 = correr("bash scripts/correr-suite.sh --fallas", self.p.dir)
        (self.p.dir / ".tests-base").write_text(r0.stdout)
        self.assertIn("test_cosa", r0.stdout, "la línea base tiene que traer la falla")
        # La tarea la arregla, CON la condición, para que haya algo que mutar.
        self.p.implementar("def f(x=0):\n"
                           "    if x > 100:\n        return 1\n"
                           "    return 42\n")
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


class TestUnaLlamadaEmitidaComoTextoNoEsUnaFallaDeLaTarea(unittest.TestCase):
    """El ejecutor escribió `<tool_call>` en el CONTENIDO en vez de pedir la herramienta por
    su canal: nadie la ejecuta, el modelo no recibe resultado y la corrida muere sin tocar un
    archivo. El gate dice «no hay ningún cambio: la tarea no se hizo» —cierto, y no se parece
    a su causa—. Es un fallo de protocolo entre modelo y harness, y contarlo como falla de la
    tarea corrompe la comparación entre modelos: un inválido anotado como reprobado.

    Cadáver real: `fallidos-T26/intento-…Z.log`, T26 del 2026-10-19 con el ejecutor
    `f5d76140`, después de que el mismo modelo escribiera bien el test de esa misma tarea."""

    def error(self, cuerpo):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-proto-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        log = d / "intento.log"
        log.write_text(cuerpo + "=== gate ===\nGATE ROJO (2 fallo/s)\n")
        return correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; error_del_agente {shlex.quote(str(log))}'),
            RAIZ).stdout.strip()

    def test_una_llamada_cruda_se_declara_fallo_de_protocolo(self):
        e = self.error("Voy a revisar el archivo de rutas:\n\n"
                       "<tool_call>\n<function/read>\n"
                       "<parameter=filePath>\nbackend/app/rutas/auth.py\n</parameter>\n"
                       "</function>\n</tool_call>\n")
        self.assertIn("protocolo", e, "una llamada emitida como texto tiene que declararse")
        self.assertIn("no de la tarea", e, "y tiene que decir de quién NO es la falla")

    def test_mencionarla_en_prosa_no_cuenta(self):
        """Brazo nulo: si matcheara en cualquier lugar del texto, un agente que NOMBRE
        `<tool_call>` quedaría marcado como error. Un detector que marca a todos no distingue
        a ninguno — es el mismo defecto que el ⊘ que tapa un resultado real, al revés."""
        e = self.error("El modelo a veces emite <tool_call> en el texto; lo evito.\n")
        self.assertEqual(e, "", f"falso positivo: marcó un error donde sólo se lo menciona: {e!r}")

    def test_un_error_nuevo_de_la_plataforma_se_reconoce_por_el_SOBRE(self):
        """La función enumeraba MENSAJES: reconocía «Failed to start inference server» y
        «upstream stream ended» porque estaban en la lista, y dejaba pasar
        `memory_delivery_unavailable`, que el 2026-10-19 mató T11 y T20 en la misma etapa.
        Los dos quedaron anotados como «la tarea no se hizo», o sea contra el modelo. Una
        lista de mensajes envejece con cada error nuevo, y lo que envejece calla."""
        e = self.error('Error: {"message":"memory_delivery_unavailable","type":"api_error"}\n')
        self.assertIn("memory_delivery_unavailable", e,
                      "un error de plataforma que no está en la lista tiene que salir igual")

    def test_el_sobre_se_reconoce_aunque_venga_con_colores(self):
        """El log guarda la salida de opencode con escapes ANSI: la línea real es
        `\\e[91m\\e[1mError: \\e[0m{...}`, así que `^Error:` no ancla nunca. Lo descubrí
        verificando contra una copia del log que yo mismo había limpiado para leerla."""
        e = self.error('\033[91m\033[1mError: \033[0m'
                       '{"message":"memory_delivery_unavailable","type":"api_error"}\n')
        self.assertIn("memory_delivery_unavailable", e,
                      "con los colores puestos no lo reconoce, y así viene el log de verdad")

    def test_un_json_de_api_error_citado_en_prosa_no_cuenta(self):
        """Brazo nulo: anclado a `^Error: {`. Si matcheara en cualquier parte, un agente que
        escriba un test CON ese JSON adentro quedaría marcado como error de plataforma —y hay
        tests del método que lo contienen—. Un detector que marca a todos no distingue a
        ninguno."""
        e = self.error('escribí un caso con {"message":"x","type":"api_error"} adentro\n')
        self.assertEqual(e, "", f"falso positivo sobre una cita: {e!r}")

    def test_un_error_de_infraestructura_sigue_saliendo(self):
        """Y el chequeo nuevo no puede tapar los que ya salían: va antes en la función."""
        e = self.error("Error: inference timed out after 60s\n")
        self.assertIn("inference timed out", e)

    def test_el_transcript_preservado_se_nombra_en_UTC(self):
        """El log se encabeza en UTC y el archivo se nombraba en hora local: leí «16:38 UTC»
        adentro de `intento-133855` y concluí que el transcript se había perdido. Comparé dos
        relojes y por un rato creí que el método destruía su propia evidencia."""
        for s in ((SCRIPTS / "_comun.sh").read_text(), (SCRIPTS / "escribir-tests.sh").read_text()):
            for linea in [l for l in s.split("\n")
                          if ("intento-$(date" in l or "parche-$(date" in l)]:
                self.assertIn("date -u", linea,
                              f"nombre en hora local contra un log en UTC: {linea.strip()!r}")


class TestLaMemoriaQueElRunnerEscribeNoFrenaLaIntegracion(CasoBase):
    """`recordar_falla` escribía `memoria/TNN.md` en el tronco y lo dejaba SIN TRACKEAR, así
    que `integrar.sh` —que se niega a mergear con el tronco sucio, y tiene razón— frenó la
    etapa 1 de clasificados con T04b y T26 las dos en verde. El método bloqueándose con su
    propia salida, y con un mensaje («el tronco tiene cambios sin commitear») que hace pensar
    en un descuido del humano."""

    def recordar(self):
        return correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto >/dev/null 2>&1; '
            'recordar_falla T01 "falló así: un import" "src/cosa.py"'), self.p.dir)

    def test_despues_de_registrar_memoria_el_tronco_queda_limpio(self):
        self.recordar()
        self.assertTrue((self.p.dir / "memoria" / "T01.md").is_file(),
                        "la memoria tiene que quedar escrita")
        sucio = correr("git status --porcelain", self.p.repo).stdout.strip()
        self.assertEqual(sucio, "",
                         "el runner dejó el tronco sucio con su propia salida, y la etapa "
                         f"siguiente no va a poder integrar:\n{sucio}")

    def test_la_memoria_viaja_en_su_propio_commit(self):
        self.recordar()
        r = correr("git log -1 --format=%s", self.p.repo).stdout.strip()
        self.assertEqual(r, "T01: memoria verificada",
                         "el commit tiene que nombrarse como los otros del runner")
        archivos = correr("git show --name-only --format= HEAD", self.p.repo).stdout.split()
        self.assertEqual([a for a in archivos if a], ["proyecto/memoria/T01.md"],
                         "commitea ESE archivo y no barre lo que haya sucio al lado")

    def test_no_barre_otros_cambios_sin_commitear(self):
        """Brazo nulo del anterior: si commiteara todo, el runner se llevaría puesto el
        trabajo del humano y el tronco quedaría «limpio» por el motivo equivocado."""
        ajeno = self.p.dir / "src" / "mio.py"
        ajeno.write_text("# lo estaba editando yo\n")
        self.recordar()
        sucio = correr("git status --porcelain", self.p.repo).stdout
        self.assertIn("src/mio.py", sucio,
                      "se llevó puesto un cambio que no era suyo")

    def test_sin_motivo_no_escribe_nada(self):
        """Sin motivo no hay par (qué falló, qué lo arregló): no hay memoria que registrar, y
        escribir un archivo vacío volvería a ensuciar el tronco por nada."""
        correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto >/dev/null 2>&1; '
            'recordar_falla T01 "" "src/cosa.py"'), self.p.dir)
        self.assertFalse((self.p.dir / "memoria").exists(),
                         "sin motivo no se escribe ni el directorio")


class TestElInstrumentoNoMandaAlHumanoAHacerLoQueNoVa(unittest.TestCase):
    """Dos mensajes del método que decían algo que no era, los dos cobrados el 2026-10-19
    mientras diagnosticaba por qué la etapa 1 no integraba. Chequeos de forma: el primero
    sólo se alcanza con una corrida de agente entera (el script exige al menos una tarea) y
    el segundo necesita una integración que falle."""

    def test_el_aviso_de_commitear_los_tests_no_sugiere_add_de_todo(self):
        """Sugería `git add -A`, que barre el trabajo a medio hacer del humano a un commit
        llamado «tests de …».

        Mirando sólo las líneas que se IMPRIMEN: adentro del worktree desechable el script
        hace `git add -A` y ahí está bien, porque ese árbol se tira. La primera versión de
        este test miraba el archivo entero y reprobaba esa línea legítima — un detector que
        marca a todos no distingue a ninguno, que es la lección del día."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        impresas = [l for l in s.split("\n")
                    if l.strip().startswith(("echo ", 'echo"', "printf ")) and "add -A" in l]
        self.assertEqual(impresas, [],
                         "un mensaje al humano sugiere `git add -A` sobre el tronco, y eso "
                         "se lleva lo que no es suyo:\n  " + "\n  ".join(impresas))

    def test_el_aviso_de_commitear_los_tests_sale_solo_si_hay_algo(self):
        """Se imprimía SIEMPRE, incluso cuando las dos tareas se saltearon por «ya declara la
        clase — no se toca». Lo leí con el tronco limpio y dudé del estado del repo."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        i = s.index("Los tests aceptados están en el tronco sin commitear")
        antes = s[max(0, i - 700):i]
        self.assertIn("status --porcelain", antes,
                      "el aviso no está guardado por el estado real del tronco")
        self.assertIn('if [ -n "$SUCIO" ]', antes, "falta el `if` que lo condiciona")

    def test_cuando_falla_la_integracion_el_hint_no_es_recorrer_la_etapa(self):
        """`correr-todo.sh N` re-corre la etapa ENTERA. Con la integración como único paso
        fallado, eso borra los worktrees que ya están en VERDE: seguí el mensaje al pie de la
        letra y tiré las implementaciones verdes de T04b y T26."""
        s = (SCRIPTS / "correr-todo.sh").read_text()
        i = s.index('integrar.sh" "${tareas[@]}"')
        tramo = s[i:i + 400]
        self.assertIn("parar", tramo, "la integración tiene que parar el plan")
        self.assertIn("integrar.sh ${tareas[*]}", tramo,
                      "al fallar la integración, el comando para retomar es la integración, "
                      "no la etapa entera")
        d = s[s.index("parar() {"):]
        d = d[:d.index("\n}")]
        self.assertIn('${3:-}', d, "parar() no acepta un comando preciso")
        self.assertIn("NO uses", d, "y tiene que avisar de lo que NO hay que correr")


class TestElIndiceDeEtapaNoPuedeSignificarDosCosas(CasoBase):
    """`correr-todo.sh` le pasaba su `$n` a `correr-plan.sh`, que **re-deduce** las etapas por
    su cuenta. El 2026-10-19 la fase de tests corrió «ETAPA 2/8: T05» y la de tareas,
    re-deduciendo con T04b y T26 ya hechas, tomó su etapa 2 —T14 T20 T11 T28— y SALTEÓ T05,
    que quedó con su test rojo en el tronco y sin implementación. Nadie se enteró hasta que
    alguien leyó dos líneas del log que decían 8 etapas y 7.

    `correr-plan.sh` ya documentaba que los números no son estables entre corridas, y
    `correr-todo.sh` tenía un guardia para el `--desde` del humano: el arreglo estaba de un
    lado y no del otro."""

    def dos_etapas(self):
        """T01 y después T02, que depende de ella: la etapa 1 es T01 y la 2 es T02."""
        self.p.escribir_tarea("T02", "src/otra.py")
        plan = self.p.dir / "PLAN.md"
        plan.write_text(plan.read_text().rstrip("\n") +
                        "\n| T02 | Otra cosa | T01 | src/otra.py | pendiente |\n")

    def etapas(self, *args):
        return correr("bash " + str(SCRIPTS / "correr-plan.sh") + " " + " ".join(args),
                      self.p.dir, SOLO_ETAPAS="1")

    def test_nombrar_la_tarea_corre_ESA_y_no_la_que_caiga_en_ese_indice(self):
        self.dos_etapas()
        r = self.etapas("T02")
        self.assertIn("ETAPA 1: T02", r.stdout,
                      f"nombré T02 y no es lo que va a correr:\n{r.stdout}{r.stderr}")
        self.assertNotIn("T01", r.stdout.split("Plan con")[-1],
                         "nombrar una tarea no puede arrastrar las otras etapas")
        self.assertIn("1 etapa", r.stdout, "lo nombrado es UNA etapa, no un punto de partida")

    def test_por_indice_sigue_deduciendo(self):
        """Brazo nulo: el uso humano `correr-plan.sh 2` no puede volverse una lista de tareas,
        o el guardia de `--desde` de correr-todo.sh se queda sin nada que guardar."""
        self.dos_etapas()
        r = self.etapas("1")
        self.assertIn("ETAPA 1: T01", r.stdout, f"dejó de deducir:\n{r.stdout}{r.stderr}")
        self.assertIn("ETAPA 2: T02", r.stdout, "con un índice se listan TODAS las etapas")

    def test_mezclar_indice_y_tareas_se_rechaza(self):
        """Si aceptara la mezcla habría que adivinar qué quiso decir, y adivinar es lo que
        produjo el salteo."""
        r = self.etapas("2", "T01")
        self.assertNotEqual(r.returncode, 0, "la mezcla tiene que fallar, no elegir una")
        self.assertIn("no las dos cosas", r.stdout + r.stderr)

    def test_correr_todo_le_pasa_los_nombres(self):
        """Chequeo de forma del cableado: la conducta pide una corrida de agente entera."""
        s = (SCRIPTS / "correr-todo.sh").read_text()
        # La que EJECUTA, no la que lista: correr-todo.sh también llama a correr-plan.sh con
        # SOLO_ETAPAS para enterarse de las etapas, y ahí no va ninguna tarea. La primera
        # versión de este test miraba la primera aparición y reprobaba esa línea legítima.
        ejecuta = [l for l in s.split("\n") if "correr-plan.sh" in l and "SOLO_UNA" in l]
        self.assertEqual(len(ejecuta), 1, f"esperaba una sola llamada que ejecute: {ejecuta}")
        self.assertIn('"${tareas[@]}"', ejecuta[0],
                      f"sigue pasando un índice a correr-plan.sh: {ejecuta[0].strip()!r}")
        self.assertNotIn('correr-plan.sh" "$n"', s,
                         "quedó una llamada por índice: el número significa otra cosa allá")


class TestUnTestDeclaradoYAusenteNoEsUnTestQuePasa(CasoBase):
    """El veredicto del paso 1 se mide contra las fallas que MENCIONAN el test declarado por
    la tarea: si el archivo no existe, no hay fallas que lo mencionen, así que no hay rojo —y
    el testigo llegaba a afirmar «y <ruta> en verde», nombrando algo que no está en el árbol—.
    Con la suite entera en verde pasaba por el caso 0, sin mirar nada.

    Cadáver: el 2026-10-19 un salteo de etapa hizo que T14, T20 y T28 de clasificados se
    implementaran sin que nadie escribiera sus tests. Las tres cerraron en VERDE y se
    integraron. La de T14 ni se podía importar (`from .conexion import get_db_connection`,
    que no existe) y nadie se enteró hasta que la tarea siguiente se rompió contra ella."""

    def test_sin_el_archivo_de_test_el_gate_es_rojo(self):
        self.p.implementar()          # la implementación está bien
        (self.p.dir / "tests" / "test_cosa.py").unlink()   # lo que falta es el test
        self.assertRojo(self.p.gate("T01"),
                        "un test declarado y ausente no puede dar verde",
                        motivo="no está en el árbol")

    def test_con_el_test_presente_sigue_dando_verde(self):
        """Brazo nulo: si el chequeo disparara siempre, ninguna tarea podría cerrar y el
        rojo dejaría de significar algo."""
        self.p.implementar()
        r = self.p.gate("T01")
        self.assertNotIn("no está en el árbol", r.stdout,
                         f"falso positivo con el test presente:\n{r.stdout}")
        self.assertVerde(r, "con test e implementación el gate tiene que cerrar")

    def test_integrar_tampoco_mergea_una_tarea_sin_su_test(self):
        """El mismo agujero un nivel más arriba: el veredicto de `integrar.sh` es «no agregó
        fallas nuevas sobre la línea base», y una tarea sin tests no agrega ninguna. El
        2026-10-19 integré T14, T20 y T28 así, invocando el script A MANO después del salteo
        de etapa, y hubo que revertir las tres.

        Chequeo de forma: el arnés de conducta pediría un worktree hermano del repo
        (`$RAIZ/../trabajo-TNN`), que en el proyecto de juguete cae en el temp compartido y
        colisionaría entre tests. Lo que pina es la posición: después de leer el veredicto
        —porque un veredicto que no es VERDE ya corta— y antes del merge."""
        s = (SCRIPTS / "integrar.sh").read_text()
        self.assertIn("no está en el árbol", s, "le falta el chequeo del test declarado")
        i = s.index("no está en el árbol")
        self.assertLess(s.index('v" != "VERDE"'), i, "va después de leer el veredicto")
        self.assertLess(i, s.index('merge --no-edit'), "y antes de mergear")
        tramo = s[s.index("t_decl=", 0) if "t_decl=" in s else 0:i]
        self.assertIn("clase `[A-Za-z0-9_]*`", tramo,
                      "tiene que leer la declaración canónica del archivo de tarea, la misma "
                      "que lee el gate: dos lectores de una declaración se desincronizan")

    def test_el_chequeo_esta_en_las_tres_copias_del_gate(self):
        """El gate vive copiado en tres lugares y este repo ya se comió el arreglo puesto en
        uno solo: el paso 4 existía en clasificados y no en pacman."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=str(g.relative_to(RAIZ))):
                s = g.read_text()
                self.assertIn("no está en el árbol", s, "le falta el chequeo")
                i, j = s.index("RUTA_DECLARADA="), s.index('case "$RC" in')
                self.assertLess(i, j, "el chequeo va ANTES del case: con la suite en verde, "
                                      "el caso 0 pasaba sin mirar el test declarado")


class TestEditarUnScriptEnCursoNoPuedeQuedarCallado(unittest.TestCase):
    """bash lee el script por POSICIÓN mientras ejecuta: si el archivo cambia a mitad de
    corrida, los offsets se corren y el intérprete ejecuta pedazos de otro programa. La regla
    está en METODO.md «Tres cosas que muerden» y la incumplieron las dos personas que la
    conocían: quien la escribió y yo, el 2026-10-19, mergeando tres veces con el plan en
    vuelo.

    El síntoma quedó en el log dos veces: la corrida salió del bucle de etapas después de la
    PRIMERA, cayó en el `echo` final e informó «Todas las etapas en verde» con siete etapas
    sin tocar. Y encima yo había afirmado que era seguro porque git reemplaza con rename —no
    lo hace para el árbol de trabajo: abre con O_TRUNC y reescribe el mismo inodo—.

    Una regla que vive sólo en un documento es una regla que se incumple."""

    def huella(self, dir_scripts):
        return correr("bash -c " + shlex.quote(
            f'AQUI={shlex.quote(str(dir_scripts))}; '
            'cat "$AQUI"/*.sh 2>/dev/null | git hash-object --stdin'), RAIZ).stdout.strip()

    def test_la_huella_cambia_si_cambia_un_script(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella-s-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "a.sh").write_text("echo a\n")
        (d / "b.sh").write_text("echo b\n")
        antes = self.huella(d)
        self.assertTrue(antes, "la huella no puede salir vacía")
        (d / "b.sh").write_text("echo b\necho c\n")
        self.assertNotEqual(antes, self.huella(d),
                            "si no distingue un script editado, el guardia no guarda nada")

    def test_la_huella_no_cambia_sola(self):
        """Brazo nulo: una huella que cambia por su cuenta pararía toda corrida y el guardia
        se volvería un ruido que se aprende a ignorar."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella-n-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "a.sh").write_text("echo a\n")
        self.assertEqual(self.huella(d), self.huella(d))

    def test_el_guardia_corre_en_cada_etapa_y_para_el_plan(self):
        s = (SCRIPTS / "correr-todo.sh").read_text()
        # La huella vive en el MÉTODO (una copia) y el runner la usa: antes este assert la
        # exigía dentro de `correr-todo.sh`, o sea pinaba su ubicación y no su existencia.
        self.assertIn("huella_scripts()", (SCRIPTS / "_comun.sh").read_text(),
                      "no existe la huella")
        self.assertIn("instrumento_se_movio", s, "el runner no la usa")
        captura = s.index("instrumento_se_movio")
        bucle = s.index('for etapa in "${ETAPAS[@]}"')
        self.assertLess(captura, bucle, "la huella se fija ANTES del bucle de etapas")
        cuerpo = s[bucle:]
        i = cuerpo.index("instrumento_se_movio")
        self.assertIn("parar", cuerpo[i:i + 400],
                      "detectarlo no alcanza: una corrida cuyo instrumento cambió no es "
                      "una corrida, es un inválido")
        # Y el borde de etapa ya no es el ÚNICO lugar donde se mira: eso es lo que me dejó
        # editar un script con un intento en curso sin que nada avisara.
        for otro in ("escribir-tests.sh", "correr-tarea.sh"):
            self.assertIn("instrumento_se_movio", (SCRIPTS / otro).read_text(),
                          f"{otro} gasta intentos y tiene que mirar antes de cada uno")


class TestImportarDeUnModuloPropioAlgoQueNoDefine(unittest.TestCase):
    """`_imports.py` cruzaba los imports contra los requirements y SALTEABA los módulos
    locales, así que el agujero quedaba justo en el medio del chequeo de imports.

    Cadáver: T14 se integró con `from .conexion import get_db_connection` y conexion.py sólo
    exporta `configuracion()` y `conexion()`. El módulo no se podía importar, el gate la cerró
    en VERDE —no tenía test declarado— y nadie se enteró hasta que la tarea siguiente se
    estrelló contra ella. Y el nombre inventado aparece en intentos de TRES tareas distintas
    (T04, T15, T26): tres fallas con la misma huella son una del enunciado, y por eso además
    está nombrado en el AGENTS.md del proyecto."""

    def proyecto(self, modulos):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-imp-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "requirements.txt").write_text("pymysql\n")
        shutil.copy(SCRIPTS / "_imports.py", d / "_imports.py")
        for ruta, cuerpo in modulos.items():
            f = d / ruta
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(cuerpo)
        return d

    def correr_imports(self, d, *archivos):
        return correr("python3 _imports.py " + " ".join(archivos), d)

    def test_un_nombre_que_el_modulo_no_define_es_rojo(self):
        d = self.proyecto({
            "app/__init__.py": "",
            "app/conexion.py": "from contextlib import contextmanager\n\n"
                               "@contextmanager\ndef conexion():\n    yield None\n",
            "app/datos.py": "from .conexion import get_db_connection\n",
        })
        r = self.correr_imports(d, "app/datos.py")
        self.assertEqual(r.returncode, 1, f"tenía que reprobar:\n{r.stdout}{r.stderr}")
        self.assertIn("get_db_connection", r.stdout)
        self.assertIn("no está en", r.stdout, "y tiene que decir dónde lo buscó")

    def test_importar_un_submodulo_de_un_paquete_no_cuenta(self):
        """Brazo nulo: `from paquete import submodulo` lo resuelve Python importando el
        submódulo, y el `__init__.py` no tiene por qué nombrarlo. Es además la forma que el
        método EXIGE para que el `@patch` del test aplique. Sin esto el chequeo reprobaba el
        código que anda — lo encontró el control negativo contra el tronco, con dos falsos
        positivos, antes de que esto viera la luz."""
        d = self.proyecto({
            "app/__init__.py": "",
            "app/datos/__init__.py": "",
            "app/datos/users.py": "def leer(email):\n    return None\n",
            "app/servicios.py": "from app.datos import users\n\n"
                                "def f(e):\n    return users.leer(e)\n",
        })
        r = self.correr_imports(d, "app/servicios.py")
        self.assertEqual(r.returncode, 0,
                         f"falso positivo sobre un submódulo:\n{r.stdout}{r.stderr}")

    def test_con_import_estrella_no_afirma_nada(self):
        """Los nombres se crean en tiempo de ejecución: decir «no está» sería un falso rojo.
        Un chequeo que marca a todos no distingue a ninguno."""
        d = self.proyecto({
            "app/__init__.py": "",
            "app/base.py": "from os.path import *\n",
            "app/usa.py": "from .base import join\n",
        })
        r = self.correr_imports(d, "app/usa.py")
        self.assertEqual(r.returncode, 0, f"no puede afirmar nada acá:\n{r.stdout}")

    def test_las_tres_copias_del_chequeo_son_la_misma(self):
        """El repo ya se comió el arreglo puesto de un solo lado más de una vez."""
        # La invariante cambió: antes era «las tres copias son idénticas» y ahora es «hay UNA
        # copia». Es más fuerte, porque dos copias idénticas hoy divergen mañana — pasó dos
        # veces. El chequeo de que no reaparezcan está en
        # TestLosChequeosDelMetodoVivenEnUnSoloLugar.
        unica = SCRIPTS / "_imports.py"
        self.assertIn("internos_rotos", unica.read_text(),
                      "le falta el chequeo de imports internos")
        self.assertEqual([p.relative_to(RAIZ).as_posix()
                          for p in RAIZ.rglob("_imports.py") if ".git" not in p.parts],
                         ["scripts/_imports.py"], "reapareció una copia")


class TestUnPuntoMuertoDiceQueSignifica(unittest.TestCase):
    """`correr-plan.sh` decía «punto muerto — falló dos veces por lo mismo» y nada más.
    Dos cortes por LÍMITE TOTAL no son «el agente falla igual»: son «trabajó todo el
    presupuesto y no terminó», dos veces, y eso habla de la TAREA. `escribir-tests.sh` ya lo
    explicaba en su propio camino y éste no — el arreglo de un lado y no del hermano.

    Cadáver: T05 el 2026-10-19, dos cortes de 1200s, con el transcript mostrando al agente
    escribiendo los tres archivos que la tarea pide y quedándose sin tiempo iterando. Ni el
    enunciado (ya arreglado) ni el modelo: el presupuesto."""

    def explicar(self, huella, tarea="T05"):
        return correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
            f'explicar_punto_muerto {shlex.quote(huella)} {tarea}'), RAIZ).stdout

    def test_dos_cortes_por_limite_total_se_explican(self):
        s = self.explicar("agente: el agente no respondió: límite total 1200s")
        self.assertIn("trabajó TODO el presupuesto", s, "tiene que decir qué pasó")
        self.assertIn("la TAREA", s, "y de qué habla eso")
        self.assertIn("LIMITE_AGENTE", s, "y cómo relanzarla con más presupuesto")
        self.assertIn("T05", s, "nombrando la tarea, no un TNN de ejemplo")

    def test_otra_huella_no_recibe_explicacion_inventada(self):
        """Brazo nulo: si explicara cualquier punto muerto como presupuesto, mandaría a subir
        el límite de una tarea que falla por otra cosa — y el consejo equivocado es peor que
        ningún consejo."""
        s = self.explicar("✗ tocó archivos intocables (tests o el propio gate): tests/x.py")
        self.assertEqual(s.strip(), "", f"explicó algo que no sabe: {s!r}")

    def test_no_lleva_numeros_escritos_a_mano(self):
        """Un número en un mensaje envejece y después miente. Lo que lleva es el comando que
        lo calcula: `metricas.sh`. (El 2400 del ejemplo de relanzamiento es un valor que se
        pasa, no una medición.)"""
        s = self.explicar("agente: el agente no respondió: límite total 1200s")
        self.assertIn("metricas.sh", s, "tiene que apuntar al comando que mide el margen")
        for n in ("970", "180", "1200s de presupuesto"):
            self.assertNotIn(n, s, f"«{n}» es una medición escrita a mano: va a envejecer")

    def test_correr_plan_lo_llama(self):
        s = (SCRIPTS / "correr-plan.sh").read_text()
        i = s.index("punto muerto — falló dos veces")
        self.assertIn("explicar_punto_muerto", s[i:i + 400],
                      "el diagnóstico no se usa donde se detecta el punto muerto")


class TestLoQueLaAuditoriaEncontro(unittest.TestCase):
    """Cinco auditorías en paralelo, una por FORMA de defecto, el 2026-10-19. Todo lo de acá
    salió de ahí y está verificado contra el código o contra logs reales. El resultado grande:
    el gate estaba parcialmente decorativo. Ver AUDITORIA-20261019.md."""

    # ── 1. Las fallas de vitest eran invisibles al paso 1, por DOS causas independientes
    def test_el_extractor_ve_las_fallas_de_vitest_y_con_la_ruta_del_plan(self):
        """Causa A: vitest padea la etiqueta a dos espacios y el patrón pedía uno, con `>`
        obligatorio. Causa B: corre con `--root frontend`, así que imprime `tests/x.test.ts`
        mientras la tarea declara `frontend/tests/x.test.ts` — el `grep -F` del gate no podía
        matchear ni con el patrón arreglado. 15 tareas, 8 ya marcadas hechas."""
        s = (RAIZ / "ejemplo-clasificados" / "scripts" / "correr-suite.sh").read_text()
        i = s.index("fallas() {"); cuerpo = s[i:s.index("\n}", i)]
        self.assertIn("frontend/", cuerpo, "falta el prefijo que empareja con lo que declara el plan")
        self.assertIn("sed -E", cuerpo, "el `\\|` de BRE no existe en el sed de BSD")
        # Y la conducta, con las dos formas reales sacadas de logs de este repo:
        guion = ("printf '%s\\n' ' FAIL  tests/a.test.ts [ tests/a.test.ts ]' "
                 "' FAIL  tests/b.test.ts > TestB > caso' ' ✓ tests/ok.test.ts (3 tests)' "
                 "| grep -oE '^ *(FAIL|×)[[:space:]]+[^ ]+' "
                 "| sed -E 's/^ *//; s/^(FAIL|×)[[:space:]]*//; s/ *$//' | grep . "
                 "| sed 's#^#frontend/#'")
        r = correr("bash -c " + shlex.quote(guion), RAIZ)
        self.assertEqual(sorted(r.stdout.split()),
                         ["frontend/tests/a.test.ts", "frontend/tests/b.test.ts"])

    def test_un_extractor_vacio_contra_una_suite_roja_es_rojo(self):
        """Lo que vuelve durable el arreglo: toda lista de formatos envejece, pero juzgar con
        una lista vacía es juzgar nada. Evidencia de un log real: en T11 el agente murió sin
        tocar un archivo y el paso 1 escribió «✓ los tests de T11 pasan … y <su test> en
        verde»."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.name + ":" + g.parent.name):
                s = g.read_text()
                self.assertIn("el extractor de fallas no entendió su salida", s)

    # ── 2. Con el corredor ausente, el paso 1 decía que los tests de la tarea pasaban
    def test_falta_el_corredor_de_su_mitad_no_es_un_verde(self):
        """La línea base de `FALTA_CORREDOR` no nombra ninguna ruta de test, así que `mios`
        quedaba vacío por construcción y el veredicto era verde con CERO tests corridos. Y no
        alcanza con dar rojo siempre: si falta el corredor del frontend, los tests de una
        tarea de backend sí corrieron — ése era el cadáver original (T30 contra T02 y T03)."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.name + ":" + g.parent.name):
                s = g.read_text()
                self.assertIn('FALTA_CORREDOR${mitad', s, "no mira la mitad que le toca")
                i = s.index('FALTA_CORREDOR${mitad')
                self.assertIn("rojo ", s[i:i + 300], "detectarlo sin reprobar no sirve")
                self.assertLess(i, s.index('if [ -n "$mios" ]'),
                                "va antes del verde, o el verde gana")

    # ── 3. integrar.sh comparaba una línea constante
    def test_integrar_compara_fallas_de_a_una(self):
        """En modo integración el paso 1 del gate colapsa la suite en UNA línea constante
        —«✗ la suite está en rojo»—, así que el `comm` entre antes y después comparaba dos
        listas idénticas de un elemento y siempre salía vacío. Un merge que rompiera veinte
        tests pasaba y se marcaba ✅ hecha. Así entraron T14, T20 y T28."""
        s = (SCRIPTS / "integrar.sh").read_text()
        self.assertIn("fallas_del_tronco", s)
        self.assertIn("correr-suite.sh --fallas", s, "la granularidad sale del mismo comando "
                                                     "que usa el runner para la línea base")
        i = s.index("fallas_del_tronco() {")
        self.assertIn("la suite está en rojo", s[i:i + 900],
                      "hay que sacar la línea resumen para no mezclar granularidades")
        self.assertEqual(s.count("""| grep '✗' | sort -u || true)"""), 0,
                         "quedó una captura con la comparación vieja")

    # ── 4 y 5. Los dos ⊘ que mutar.py vendía como pase
    def test_nada_que_mutar_es_un_circulo_y_no_un_pase(self):
        """`CODIGO` valía `src` por defecto y nadie lo seteaba: en un proyecto cuyo código vive
        en `backend/app` y `frontend/src`, mutar.py no encontraba un solo archivo, devolvía 0,
        y escribir-tests.sh imprimía «✓ los mutantes mueren» con la salida silenciada. Era TODO
        clasificados: 2 de los 4 tests aceptados ese día lo recibieron."""
        s = (SCRIPTS / "mutar.py").read_text()
        self.assertIn("return 2", s, "«nada que mutar» tiene que ser un ⊘, no un 0")
        # Los DOS caminos por su MENSAJE, no contando ocurrencias de `return 2` en el archivo.
        # El conteo exigía exactamente dos y se rompió al agregar un tercer camino legítimo
        # —el del tope de tiempo inválido, que también es un ⊘—. Lo que este test vigila es
        # que estos dos caminos no devuelvan 0; cuántos otros ⊘ existan no es asunto suyo.
        for mensaje in ("no hay código Python cambiado que mutar bajo",
                        "el diff no tiene nada que mutar con provecho"):
            i = s.index(mensaje)
            # Desde el mensaje hasta el próximo `return`: tiene que ser el 2.
            tramo = s[i:]
            j = tramo.index("return ")
            self.assertTrue(tramo[j:].startswith("return 2"),
                            f"el camino de «{mensaje[:40]}» no devuelve 2:\n"
                            f"{tramo[j:j + 40]!r}")
        self.assertIn('split(",")', s, "CODIGO es una lista de prefijos, como dice el contrato")
        e = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertIn('RC_MUT" = "2"', e, "escribir-tests.sh tiene que distinguir el ⊘")
        i = e.index('RC_MUT" = "2"')
        self.assertIn("No es un pase", e[i:i + 400])
        self.assertIn("CODIGO_TAREA", e, "el CODIGO sale de lo que la tarea declara")

    def test_mutar_devuelve_2_cuando_no_hay_nada_bajo_CODIGO(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-mutar-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "backend").mkdir()
        (d / "backend" / "x.py").write_text("def f():\n    return 1\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        (d / "backend" / "x.py").write_text("def f():\n    return 2\n")
        r = correr(f"BASE=HEAD CODIGO=src SUITE=true python3 {SCRIPTS}/mutar.py", d)
        self.assertEqual(r.returncode, 2,
                         f"con CODIGO que no matchea tiene que ser ⊘:\n{r.stdout}{r.stderr}")
        self.assertIn("No es un pase", r.stdout)

    # ── 6. El material del intento se destruía antes de conservarlo
    def test_se_conserva_antes_de_destruir_el_worktree(self):
        """`conservar_intento` arranca con `[ -d "$wt" ] || return 0` y estaba DESPUÉS del
        `rm -rf`: código muerto. Evidencia al descubrirlo: `fallidos-T26` tenía 9 transcripts
        y 0 parches, mientras `fallidos-T05` —que pasa por el hermano que lo hace bien— tenía
        3. La fábrica de dataset no recogía nada del camino donde el agente falla más."""
        for s_ in (SCRIPTS / "escribir-tests.sh", SCRIPTS / "correr-tarea.sh",
                   SCRIPTS / "comparar-modelos.sh"):
            with self.subTest(script=s_.name):
                s = s_.read_text()
                if "conservar_intento" not in s or 'rm -rf "$wt"' not in s:
                    self.skipTest(f"{s_.name} no recrea worktrees así")
                self.assertLess(s.index("conservar_intento"), s.index('rm -rf "$wt"'),
                                "destruye el worktree antes de conservarlo: código muerto")

    # ── 7. El guardia del árbol commiteado, en un solo lugar y con dos lectores
    def test_el_guardia_del_arbol_commiteado_lo_leen_los_dos_runners(self):
        """Estaba sólo en correr-tarea.sh. En escribir-tests.sh la consecuencia es peor: allá
        se pierde una corrida, acá se ACEPTA y se copia al tronco el test del enunciado viejo,
        porque la validación compara el test del agente contra la referencia del propio
        agente, las dos escritas contra el enunciado que vio."""
        self.assertIn("tarea_sin_commitear()", (SCRIPTS / "_comun.sh").read_text(),
                      "una regla copiada en dos lados es una regla que va a divergir")
        for s_ in (SCRIPTS / "correr-tarea.sh", SCRIPTS / "escribir-tests.sh"):
            with self.subTest(script=s_.name):
                s = s_.read_text()
                self.assertIn('tarea_sin_commitear "$id"', s)
                self.assertLess(s.index('tarea_sin_commitear "$id"'),
                                s.index("worktree add"), "el guardia va antes del worktree")

    def test_el_guardia_detecta_la_tarea_sucia_y_no_molesta_si_esta_limpia(self):
        p = Proyecto()
        self.addCleanup(shutil.rmtree, p.repo, ignore_errors=True)
        dentro = (f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; ubicar_proyecto >/dev/null 2>&1; '
                  'tarea_sin_commitear T01')
        limpio = correr("bash -c " + shlex.quote(dentro), p.dir)
        self.assertEqual(limpio.returncode, 0, f"falso positivo con el árbol limpio:\n{limpio.stdout}")
        (p.dir / "tareas" / "T01-cosa.md").write_text(
            (p.dir / "tareas" / "T01-cosa.md").read_text() + "\ncambio sin commitear\n")
        sucio = correr("bash -c " + shlex.quote(dentro), p.dir)
        self.assertEqual(sucio.returncode, 1, "no vio la tarea sucia")
        self.assertIn("SIN COMMITEAR", sucio.stdout)

    # ── 8. El paso 4 enumeraba extensiones
    def test_el_paso_4_lee_el_alcance_declarado_y_no_una_lista_de_extensiones(self):
        """La lista era `(backend/app|frontend/src)/.*\\.(py|ts|tsx|jsx)$` y dejaba afuera
        `.scss` (T13, T19), `.sql` (T03) y los manifiestos (T30): con IMPL vacío el paso
        imprimía ⊘ y el gate cerraba verde con el único chequeo de que los tests distinguen
        sin correr. T19 era el caso extremo: test `.test.ts` invisible para el extractor de
        fallas e implementación `.scss` invisible acá — ningún paso la verificaba."""
        s = (RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh").read_text()
        # Sólo las líneas que se EJECUTAN: el comentario del arreglo cita el patrón viejo, y
        # en este repo cada arreglo documenta su cadáver. La primera versión de este test
        # miraba el archivo entero y reprobaba su propia explicación — la trampa del día,
        # cobrada sobre mí.
        activas = [l for l in s.split("\n") if l.strip() and not l.strip().startswith("#")]
        self.assertFalse([l for l in activas if ".(py|ts|tsx|jsx)$" in l],
                         "sigue enumerando extensiones en código vivo")
        self.assertIn("declarado_por_la_tarea", s)
        self.assertIn("archivos_de_la_tarea()", s, "UN solo lector para UNA declaración")

    def test_el_paso_4_ve_una_implementacion_scss(self):
        proy = RAIZ / "ejemplo-clasificados"
        guion = ('. /dev/stdin <<"SRC"\n'
                 + "\n".join(l for l in (proy / "scripts" / "gate.sh").read_text().split("\n")
                              if True)[:0]  # el heredoc se arma abajo
                 + "SRC\n")
        # Más simple y menos frágil: se extraen las dos funciones y se las ejercita.
        fuente = (proy / "scripts" / "gate.sh").read_text()
        def extraer(nombre):
            i = fuente.index(f"{nombre}() {{")
            return fuente[i:fuente.index("\n}", i) + 2]
        script = (extraer("archivos_de_la_tarea") + "\n" + extraer("declarado_por_la_tarea")
                  + '\ndeclarado_por_la_tarea "frontend/src/design/_favorites.scss"\n')
        r = correr("bash -c " + shlex.quote(script), proy, TAREA="T19")
        self.assertEqual(r.returncode, 0,
                         f"el paso 4 no vería el .scss de T19:\n{r.stdout}{r.stderr}")


class TestLosChequeosQueReprobabanCodigoLegitimo(unittest.TestCase):
    """La familia espejo de la auditoría del 2026-10-19: en vez de dejar pasar lo malo,
    reprueban lo bueno. El resultado es que el chequeo se esquiva —escribiendo peor código— o
    se aprende a ignorar. Ver AUDITORIA-20261019.md, hallazgos 9, 10 y 14."""

    def test_el_patron_de_secretos_pide_un_literal(self):
        """`[^a-z]{0,3}[:=]` aceptaba cero caracteres antes del `:`, así que `password: str`
        matcheaba. Medido sobre el código del ejemplo: **17 de 88 líneas** candidatas daban
        rojo, todas anotaciones de tipo, campos de Pydantic, un `useState` y hasta
        `'password': os.environ.get('MYSQL_PASSWORD', '')`, que es lo contrario de un secreto
        commiteado. El commit que integra el auth ponía G4 en rojo y el deploy no arrancaba."""
        import re as _re
        s = (PLANTILLAS / "pre-deploy.sh").read_text()
        self.assertIn("DEL_ENTORNO", s, "las lecturas del entorno son la forma correcta")
        self.assertIn("TRIVIAL", s, "falta la exención del literal que lleva el nombre adentro")
        self.assertIn("PATRON_FLOJO", s,
                      "el patrón flojo no puede desaparecer: tiene que quedar como aviso")
        # Y la conducta de los patrones, con las líneas reales de los dos controles.
        NOMBRE = r"(api[_-]?key|secret|password|passwd|token)"
        PATRON = _re.compile(NOMBRE + r"""[^a-z]{0,3}[:=] *['"][^'"]{6,}['"]|BEGIN [A-Z ]*PRIVATE KEY""", _re.I)
        ENT = _re.compile(r"environ|getenv|process\.env|import\.meta\.env", _re.I)
        TRIV = _re.compile(NOMBRE + r"""[^a-z]{0,3}[:=] *['"][^'"]*""" + NOMBRE, _re.I)
        def rojo(l):
            return bool((not ENT.search(l)) and PATRON.search(l) and not TRIV.search(l))
        legitimas = [
            "def login(email: str, password: str) -> dict | None:",
            "    password: str",
            "const [password, setPassword] = useState('');",
            "    'password': os.environ.get('MYSQL_PASSWORD', ''),",
            "def usuario_desde_token(token: str) -> int | None:",
            "json={'email': 'test@example.com', 'password': 'password'})",
            'return {"token": "mocked-token-for-user-" + str(user.get("id"))}',
        ]
        for l in legitimas:
            with self.subTest(linea=l[:50]):
                self.assertFalse(rojo(l), "reprueba código legítimo")
        secretos = ['api_key = "sk-live-abc123def456"',
                    '    token: "eyJhbGciOiJIUzI1NiJ9"',
                    "-----BEGIN RSA PRIVATE KEY-----",
                    'password="hunter2000"']
        for l in secretos:
            with self.subTest(secreto=l[:40]):
                self.assertTrue(rojo(l), "deja pasar un secreto de verdad")

    def test_el_diff_de_pre_deploy_lleva_pathspec(self):
        """Sin pathspec el diff barre el repo ENTERO: corriendo G4 del pacman entraban los
        archivos del método, y sus fixtures de test están llenos de la palabra «password» a
        propósito. El chequeo de dependencias ya lo filtraba; estos dos no."""
        s = (PLANTILLAS / "pre-deploy.sh").read_text()
        for linea in [l for l in s.split("\n") if 'git diff "$BASE"...HEAD -U0' in l]:
            with self.subTest(linea=linea.strip()[:60]):
                self.assertIn("PREFIJO", linea, "este diff barre el repo entero")

    def test_las_senales_suprimidas_se_acotan_al_diff_y_tienen_forma_legitima(self):
        """El gate pasa los archivos CAMBIADOS y `revisar()` leía cada archivo ENTERO: tres
        `except Exception: pass` del idiom de curses, que viven en el pacman desde siempre,
        reprobaban a cualquier tarea nueva sobre esos archivos —y son el alcance declarado de
        T07, T08, T11 y T12—. No podía sacarlas sin romper el idiom ni tocarlas sin que el
        paso 2 la reprobara: el único camino era escribir peor código."""
        for s_ in (SCRIPTS / "_suprimidas.py",):   # una sola copia, en el método
            with self.subTest(copia=s_.parent.name):
                s = s_.read_text()
                self.assertIn("lineas_cambiadas", s, "no acota al diff")
                self.assertIn("best-effort", s, "no deja ninguna forma legítima de escribirlo")
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.name):
                # Lo que pina es que le PASE la base, no la ruta del chequeo: la ruta
                # cambió cuando los chequeos pasaron a vivir en un solo lugar, y un test
                # clavado a la forma convierte un refactor legítimo en un rojo.
                #
                # Y se busca la línea que lo INVOCA, no la primera aparición del nombre: el
                # comentario del resolver también lo menciona, y una ventana alrededor de la
                # primera aparición cae sobre la prosa. Undécima vez que un chequeo mío
                # confunde la mención con la cosa, y la segunda en este mismo test.
                s = g.read_text()
                invoca = [l for l in s.split("\n")
                          if "_suprimidas.py" in l and "aux_del_metodo" in l
                          and ("python3" in l or "PY_PROYECTO" in l)]
                self.assertEqual(len(invoca), 1,
                                 f"esperaba una invocación del chequeo: {invoca}")
                # `BASE_SUP` y no `BASE_REF`: este assert PINABA EL DEFECTO. Exigía que la
                # base viajara en los dos modos, y en modo integración eso filtra todos los
                # hallazgos —`BASE_REF` es el merge-base con main, el árbol está limpio, el
                # diff sale vacío—, así que el chequeo quedaba decorativo justo en el modo
                # que revisa el tronco entero. Un test escrito desde el comentario de al
                # lado («en modo tarea, sólo lo que ESTA tarea tocó») pina la intención, no
                # la conducta.
                self.assertIn('BASE="$BASE_SUP"', invoca[0],
                              "el gate no le pasa la base, así que no puede acotar al diff")
                self.assertRegex(s, r'BASE_SUP=""',
                                 "y en modo integración la base tiene que ser vacía, o el "
                                 "acote filtra TODO en vez de nada")

    def test_una_senal_suprimida_nueva_sigue_cayendo(self):
        """Brazo nulo del acote: si el filtro tapara todo, el chequeo dejaría de existir."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sup-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        shutil.copy(SCRIPTS / "_suprimidas.py", d / "_suprimidas.py")
        f = d / "x.py"
        f.write_text("def vieja():\n    try:\n        pass\n    except Exception:\n        pass\n")
        for cmd in (["init","-q","-b","main"],["add","-A"],
                    ["-c","user.email=t@t","-c","user.name=t","commit","-qm","base"]):
            subprocess.run(["git",*cmd], cwd=d, check=True, capture_output=True)
        vieja = correr("BASE=HEAD python3 _suprimidas.py x.py", d)
        self.assertEqual(vieja.returncode, 0,
                         f"le cobra a la tarea una señal que ya estaba:\n{vieja.stdout}")
        f.write_text(f.read_text() + "\ndef nueva():\n    try:\n        pass\n"
                     "    except Exception:\n        pass\n")
        nueva = correr("BASE=HEAD python3 _suprimidas.py x.py", d)
        self.assertEqual(nueva.returncode, 1, f"una señal NUEVA tiene que caer:\n{nueva.stdout}")
        f.write_text(f.read_text().replace("    except Exception:\n        pass\n",
                                           "    except Exception:  # best-effort: da igual\n        pass\n"))
        exenta = correr("BASE=HEAD python3 _suprimidas.py x.py", d)
        self.assertEqual(exenta.returncode, 0,
                         f"la forma legítima tiene que pasar:\n{exenta.stdout}")

    def test_el_TODO_se_acota_a_lo_que_la_tarea_cambio(self):
        """Barría el árbol entero, sin guarda de TAREA ni filtro por lo cambiado, a diferencia
        de sus tres vecinos inmediatos, que fueron acotados a propósito y con comentario. Un
        `# TODO: paginar` que dejó otra tarea reprobaba a la de al lado, que no puede sacarlo
        sin salirse de su alcance."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.name):
                s = g.read_text()
                self.assertIn("ARG_TODO", s, "el TODO no está acotado")
                i = s.index("ARG_TODO")
                self.assertIn('${TAREA:-}', s[max(0, i - 400):i + 200],
                              "falta la guarda de modo tarea")
                # Y que el GREP la use. La primera versión de este test verificaba que la
                # variable existiera, y el grep seguía usando los directorios fijos: el
                # arreglo que el comentario del gate describe NO EXISTÍA y el test daba
                # verde. Nombrar la cosa no alcanza — acá aplicado al test mismo.
                grepea = [l for l in s.split("\n")
                          if 'grep -rnE "\\bTODO' in l and not l.strip().startswith("#")]
                self.assertEqual(len(grepea), 1, f"esperaba un grep de TODO: {grepea}")
                self.assertIn("${ARG_TODO}", grepea[0],
                              "el grep del TODO no usa el acote que se calculó arriba")

    def test_un_TODO_en_un_archivo_ajeno_no_reprueba_a_la_tarea(self):
        """La conducta, no la forma: un `# TODO` que dejó otra tarea en un archivo que ESTA
        no tocó no puede reprobarla, porque no puede sacarlo sin salirse de su alcance —y
        tocarlo la reprueba el paso 2—. El único camino era escribir peor código."""
        p = Proyecto()
        self.addCleanup(shutil.rmtree, p.repo, ignore_errors=True)
        ajeno = p.dir / "src" / "ajeno.py"
        ajeno.write_text("def g():\n    return 1  # TODO: paginar\n")
        p.git("add -A"); p.git('commit -qm "lo dejó otra tarea"')
        p.implementar()                      # T01 toca sólo src/cosa.py
        r = p.gate("T01")
        self.assertNotIn("quedaron TODO", r.stdout,
                         f"le cobra a T01 un TODO que no escribió:\n{r.stdout}")

    def test_un_TODO_propio_sigue_reprobando(self):
        """Brazo nulo: si el acote tapara todo, el chequeo dejaría de existir."""
        p = Proyecto()
        self.addCleanup(shutil.rmtree, p.repo, ignore_errors=True)
        p.implementar("def f():\n    return 42  # TODO: arreglar esto\n")
        r = p.gate("T01")
        self.assertIn("quedaron TODO", r.stdout,
                      f"dejó pasar un TODO que la tarea SÍ escribió:\n{r.stdout}")

    def test_el_detector_de_tailwind_no_mira_las_dependencias(self):
        """Sin `--exclude-dir`, alcanzaba con que la cadena existiera en cualquier .json/.js/.ts
        bajo frontend/, incluido `node_modules/`, que instala `preparar-entorno.sh` y no el
        agente. Es la clase de rojo que el filtro INFRA del paso 2 existe para evitar."""
        s = (RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh").read_text()
        linea = next((l for l in s.split("\n") if "tailwind" in l and "grep -rq" in l), "")
        self.assertTrue(linea, "no encontré el detector de Tailwind")
        self.assertIn("--exclude-dir=node_modules", linea)


class TestLosCuatroHallazgosQueFaltaban(unittest.TestCase):
    """Los que quedaban de AUDITORIA-20261019.md: 11, 12, 13 y 15. Ninguno lo encontró una
    corrida — los cuatro salieron de leer el código con una forma en la cabeza."""

    def control(self, *args, raiz=None):
        d = raiz or pathlib.Path(tempfile.mkdtemp(prefix="prueba-ctrl-")).resolve()
        if raiz is None:
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ={shlex.quote(str(d))}; '
            'control_se_movio ' + " ".join(shlex.quote(a) for a in args)), RAIZ), d

    def test_un_control_degenerado_no_se_puede_usar_de_linea_base(self):
        """La línea base se escribía sin validar NADA, así que un control que ya estaba roto se
        auto-validaba para siempre: con `tools=0` la primera mitad del criterio queda apagada
        —pide `t_prev > 0`— y con un veredicto estable la segunda nunca dispara. Es justo el
        modo de falla para el que la función existe («el modelo de un partner daba 0 de 6
        llamadas por un defecto del arnés»). Los cinco casos pineados usaban 6, 5 y 2
        llamadas y veredicto VERDE: ninguno probaba el caso degenerado."""
        r, _ = self.control("m|T05", "0", "ROJO")
        self.assertEqual(r.returncode, 1, f"aceptó un control que no actuó:\n{r.stdout}")
        self.assertIn("no sirve como línea base", r.stdout)

    def test_un_control_sano_sigue_sirviendo_de_linea_base(self):
        """Brazo nulo: si rechazara cualquier primera corrida, no habría línea base nunca y el
        comparador no podría arrancar."""
        r, d = self.control("m|T05", "6", "VERDE")
        self.assertEqual(r.returncode, 2, f"rechazó un control sano:\n{r.stdout}")
        r2, _ = self.control("m|T05", "6", "VERDE", raiz=d)
        self.assertEqual(r2.returncode, 0, "la segunda corrida igual tiene que ser válida")
        r3, _ = self.control("m|T05", "0", "VERDE", raiz=d)
        self.assertEqual(r3.returncode, 1, "un derrumbe de herramientas tiene que detectarse")

    def test_la_huella_del_instrumento_dice_si_habia_cambios_sin_commitear(self):
        """Salía de `HEAD:scripts`, el árbol COMMITEADO, así que dos corridas con scripts
        distintos sin commitear comparten huella — el estado contra el que avisa el guardia de
        `correr-todo.sh`. `congelar-banco.sh` ya lo marcaba y esto no."""
        # Por CONDUCTA y no por una ventana de caracteres: la versión anterior miraba 600
        # caracteres después del `rev-parse` y el comentario que explica el arreglo del
        # stage la desbordó, así que reprobaba al código arreglado. Es la misma forma que
        # mordió a tres tests este día.
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella3-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "scripts").mkdir()
        (d / "scripts" / "x.sh").write_text("echo 1\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'anotar_intento T01 VERDE 10 abc', RAIZ)
        limpio = (d / ".metricas" / "intentos.csv").read_text().strip().split("\n")[-1]
        self.assertNotIn("sin-commitear", limpio,
                         f"con el árbol limpio no hay nada que marcar:\n{limpio}")
        (d / "scripts" / "x.sh").write_text("echo 2\n")
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'anotar_intento T02 VERDE 10 abc', RAIZ)
        sucio = (d / ".metricas" / "intentos.csv").read_text().strip().split("\n")[-1]
        self.assertIn("sin-commitear", sucio,
                      f"la huella del commit miente cuando el árbol cambió:\n{sucio}")

    def test_las_metricas_declaran_que_mezclan_instrumentos(self):
        """La columna se escribía y NADIE la leía: el porcentaje que se imprime al final de
        cada corrida mezclaba todas las corridas históricas, y MEDICION.md §5 declara que dos
        filas con huellas distintas no son comparables. Hoy el registro tiene 6 huellas."""
        s = (SCRIPTS / "metricas.sh").read_text()
        self.assertIn("instrumento", s)
        self.assertIn("mezcla", s, "no declara la mezcla")
        # La regla citada en el MENSAJE que se imprime, no dentro de una ventana de 500
        # caracteres del código: el comentario que explica el arreglo de la igualdad la
        # desbordó y el test reprobaba al código arreglado.
        self.assertRegex(s, r'MEDICION\.md §5[^"\n]*"',
                         "el aviso tiene que citar la regla, o no se entiende")

    def test_el_guardia_de_corrida_activa_no_confunde_una_mencion_con_una_corrida(self):
        """Usaba `pgrep -f "correr-todo\\.sh"`, que matchea cualquier proceso cuya línea de
        comando MENCIONE la cadena. El 2026-10-20 mató un relanzamiento del plan porque mi
        propia suite de tests tenía `"scripts/correr-todo.sh"` en su línea de comando, dentro
        de una lista de archivos: el mensaje decía «ya hay una corrida activa (pid 45489)» y
        45489 era un `python3 -m unittest`.

        Es la decimosexta vez que aparece la misma forma —un chequeo que lee texto confunde la
        mención con la cosa—, y la primera en la que la víctima es el plan y no un veredicto.

        El lockfile no se confunde: lo escribe sólo quien corre. Y verifica que el pid esté
        vivo, así que una corrida muerta a lo bruto no deja el plan trabado para siempre."""
        s = (SCRIPTS / "correr-todo.sh").read_text()
        activas = [l for l in s.split("\n")
                   if l.strip() and not l.strip().startswith("#") and "pgrep -f" in l]
        self.assertEqual(activas, [],
                         "el guardia sigue usando pgrep -f: una mención lo activa:\n  "
                         + "\n  ".join(activas))
        self.assertIn("corrida-activa", s, "falta el lockfile")
        self.assertIn('kill -0 "$PID_LOCK"', s,
                      "sin verificar que el pid viva, una corrida muerta traba el plan para siempre")
        self.assertIn("trap 'rm -f \"$LOCK\"' EXIT", s, "el lock tiene que soltarse al salir")
        i = s.index("LOCK=\"$RAIZ/.metricas/")
        self.assertIn(".metricas", s[i:i + 120],
                      "va en .metricas/, que está en el .gitignore: un lock commiteado es peor")

    def test_los_avisos_del_corte_de_etapas_no_van_a_dev_null(self):
        """Ahí viajan los dos avisos de que el corte puede estar mal. Callados, dos tareas que
        escriben el mismo archivo pueden salir en la misma etapa, en paralelo — la falla que
        `_etapas.py` existe para evitar y que ya pasó una vez (BITACORA §13). El síntoma
        aparece tres pasos después, como un conflicto de merge que acusa a la segunda."""
        s = (SCRIPTS / "correr-todo.sh").read_text()
        linea = next(l for l in s.split("\n") if "SOLO_ETAPAS=1" in l and "ETAPAS_TXT" in l)
        self.assertNotIn("2>/dev/null", linea, "sigue tirando los avisos")
        self.assertIn("AVISOS_ETAPAS", linea)
        i = s.index("AVISOS_ETAPAS")
        self.assertIn("echo", s[i:i + 900], "capturarlos sin imprimirlos es lo mismo que tirarlos")

    def test_los_intocables_de_la_plantilla_cubren_los_layouts_de_dos_mitades(self):
        """`^(tests/|scripts/)` no cubre `backend/tests/test_x.py` ni
        `frontend/tests/x.test.ts`. Un proyecto nuevo copiado de la plantilla obtenía «✓ tests
        y scripts intactos» mientras el agente editaba su propio test."""
        s = (PLANTILLAS / "gate.sh").read_text()
        patron = next(l for l in s.split("\n") if l.startswith("INTOCABLES=")).split("=", 1)[1]
        patron = patron.strip().strip("'").strip('"')
        import re as _re
        rx = _re.compile(patron)
        for intocable in ("backend/tests/test_conexion.py", "frontend/tests/x.test.ts",
                          "src/cosa_test.py", "scripts/gate.sh", "tests/test_a.py"):
            with self.subTest(intocable=intocable):
                self.assertTrue(rx.search(intocable), "el agente podría editar su propio test")
        for libre in ("backend/app/datos/ads.py", "frontend/src/pages/Login.jsx",
                      "src/pacman/render.py", "PLAN.md"):
            with self.subTest(libre=libre):
                self.assertFalse(rx.search(libre), "reprueba código legítimo")

    def test_la_reversa_de_una_migracion_puede_ser_un_archivo_hermano(self):
        """La convención del método es el par `001_initial.sql` + `001_initial_down.sql`, que
        `validar-plan.py` discute. Pidiendo la palabra sólo DENTRO del archivo, el chequeo
        marcaba al correcto y además marcaba a la reversa misma."""
        s = (PLANTILLAS / "pre-deploy.sh").read_text()
        self.assertIn("_down.sql", s, "no contempla el archivo hermano")
        i = s.index("REVERSA=")
        self.assertIn('[ -f "$REVERSA" ]', s[i:i + 400])


class TestElMotivoLlevaSuDato(unittest.TestCase):
    """«El motivo lleva el fallo real, no su categoría» ya estaba escrito en
    `escribir-tests.sh` para el caso de la suite. El paso de los mutantes lo incumplía por un
    arreglo mío a medias."""

    def test_el_motivo_de_los_mutantes_lleva_su_dato(self):
        """`mutar.py` se corría DOS veces —una muda para el veredicto y otra para capturar el
        detalle— y cuando arreglé el `CODIGO` de la primera dejé la segunda con el viejo. El
        detalle salía vacío, el reintento recibía «sobreviven mutantes» sin un solo dato, y
        T05a llegó a punto muerto por eso: dos intentos sin información nueva.

        Dos invocaciones del mismo comando son dos cosas que pueden divergir, y divergieron en
        el mismo bloque y en el mismo arreglo. Ahora corre una vez y el detalle sale de esa
        corrida, así que no puede desaparecer ni contradecirla."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        invocaciones = [l for l in s.split("\n")
                        if 'mutar.py' in l and 'python3' in l and not l.strip().startswith("#")]
        self.assertEqual(len(invocaciones), 1,
                         "más de una invocación de mutar.py: pueden divergir\n  "
                         + "\n  ".join(i.strip() for i in invocaciones))
        self.assertIn("SALIDA_MUT", s, "la salida tiene que capturarse una vez y reusarse")
        i = s.index("SOBREVIVEN=")
        self.assertIn('printf \'%s\\n\' "$SALIDA_MUT"', s[i:i + 200],
                      "el detalle tiene que salir de la MISMA corrida que el veredicto")
        self.assertIn("no listó sobrevivientes", s,
                      "si el detalle sale vacío igual, hay que decirlo: mandar a adivinar es "
                      "lo que produjo el punto muerto")


class TestLosChequeosDelMetodoVivenEnUnSoloLugar(unittest.TestCase):
    """Etapa 1 hacia un método genérico. `_imports.py` y `_suprimidas.py` estaban copiados en
    la plantilla y en los dos ejemplos —**idénticos byte a byte**, mismo md5—, así que cada
    arreglo había que escribirlo tres veces, y la auditoría del 2026-10-19 encontró dos casos
    donde una copia quedó atrás.

    Lo que varía de verdad por proyecto es `correr-suite.sh` (cómo se corre SU suite) y la
    config de `_arquitectura.py` (sus capas). El juicio no varía, y por eso no se copia."""

    def test_hay_una_sola_copia_de_cada_chequeo_compartido(self):
        for n in ("_imports.py", "_suprimidas.py"):
            with self.subTest(chequeo=n):
                copias = [p for p in RAIZ.rglob(n) if ".git" not in p.parts]
                self.assertEqual([p.relative_to(RAIZ).as_posix() for p in copias],
                                 [f"scripts/{n}"],
                                 "un chequeo copiado es un chequeo que va a divergir")

    def test_AGENTES_existe_como_variable_y_no_solo_en_la_prosa(self):
        """`$AGENTES` aparecía 31 veces en los mensajes del método y no existía como variable
        en ninguna parte: una ruta que el método le pedía al humano tener en la cabeza. Es la
        misma forma que este repo viene encontrando —una regla que vive sólo en un documento—
        aplicada a su propia ubicación."""
        r = correr("bash -c " + shlex.quote(
            f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; echo "$AGENTES"'), RAIZ)
        self.assertEqual(r.stdout.strip(), str(RAIZ),
                         f"AGENTES no apunta a la raíz del método: {r.stdout!r}")
        self.assertIn("export AGENTES", (SCRIPTS / "_comun.sh").read_text(),
                      "sin export, el gate del proyecto no la recibe")

    def test_los_tres_gates_buscan_el_chequeo_en_el_metodo(self):
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.name):
                s = g.read_text()
                self.assertIn("aux_del_metodo", s, "sigue buscando una copia local")
                # Sólo las líneas que lo INVOCAN, no las que lo nombran: el mensaje
                # `rojo "falta scripts/_suprimidas.py: …"` menciona la ruta y es correcto.
                # Décima vez que un chequeo mío confunde la mención con la cosa; acá la
                # víctima era un mensaje de error.
                activas = [l for l in s.split("\n")
                           if l.strip() and not l.strip().startswith("#")
                           and ("scripts/_imports.py" in l or "scripts/_suprimidas.py" in l)
                           and "aux_del_metodo" not in l
                           and ("python3" in l or "PY_PROYECTO" in l or "[ -f " in l)]
                self.assertEqual(activas, [],
                                 "quedó una referencia a la copia del proyecto:\n  "
                                 + "\n  ".join(a.strip() for a in activas))

    def test_el_resolver_encuentra_el_chequeo_y_falla_a_la_vista(self):
        """La cadena: `$AGENTES`, después la raíz del repo, después el proyecto. Y si no está
        en ninguna, devuelve vacío para que el paso que lo necesita dé ROJO: un chequeo que no
        se encuentra no es un chequeo que pasa."""
        fuente = (PLANTILLAS / "gate.sh").read_text()
        i = fuente.index("aux_del_metodo() {")
        cuerpo = fuente[i:fuente.index("\n}", i) + 2]   # + 2: el `\n}` de cierre va incluido
        guion = cuerpo + '\naux_del_metodo "$1" || echo VACIO\n'
        con = correr("bash -c " + shlex.quote(guion) + " x _imports.py",
                     RAIZ, AGENTES=str(RAIZ))
        self.assertIn("_imports.py", con.stdout, f"no lo encontró con AGENTES:\n{con.stdout}")
        sin = correr("bash -c " + shlex.quote(guion) + " x no_existe_nunca.py",
                     RAIZ, AGENTES=str(RAIZ))
        self.assertIn("VACIO", sin.stdout,
                      "tiene que devolver vacío cuando no está, no una ruta inventada")


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


    def test_un_enunciado_que_declara_un_HUECO_da_rojo(self):
        """El defecto que costó un día entero. El 2026-10-24, T05c de clasificados tenía en su
        línea 55 «- **HUECO**: No existe función para listar todos los anuncios en la capa de
        servicios ni datos», escrita por la replanificación de `51f5c3f`.

        El arquitecto obedeció la instrucción (3) del prompt —«si el problema es que la tarea
        necesita algo que ninguna tarea del plan entrega, decilo con la palabra HUECO»— y la
        escribió donde se le pidió escribir: en el cuerpo de la tarea. El relevo busca HUECO en
        el TRANSCRIPT, y nadie miraba el enunciado que SALE. Los cuatro jueces lo aprobaron, se
        commiteó, y el ejecutor chocó con el hueco: entregó un `GET /ads` que devuelve `501 No
        implementado` y escribió en dos archivos que no eran suyos buscando la función que no
        existe.

        Después de eso yo diagnostiqué tres veces mal —el enunciado, el alcance, el modelo—
        mientras la respuesta estaba escrita en el archivo. Un enunciado que declara un hueco
        no es un enunciado: es una decisión de producto pendiente."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text() + "\n- **HUECO**: no existe función para listar las cosas\n")
        r = self.validar()
        self.assertRojo(r, "HUECO")
        self.assertIn("listar las cosas", r.stdout + r.stderr,
                      f"el rojo tiene que decir QUÉ falta, no que falta algo — es la misma "
                      f"lección que el motivo que era una categoría:\n{r.stdout}{r.stderr}")

    def test_la_palabra_hueco_en_una_frase_no_es_una_declaracion(self):
        """El marcador es una línea, no una palabra suelta: `HUECO` en mayúsculas al principio
        del renglón. Si cualquier mención lo disparara, el chequeo volvería rojo cualquier
        enunciado que hable de huecos —una grilla con huecos, un hueco en la pared— y un
        chequeo que se dispara con la prosa es un chequeo que se apaga."""
        t = self.p.dir / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text() + "\nEl laberinto tiene un hueco en la pared de arriba.\n")
        self.assertVerde(self.validar())

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
        # 2, no 0: «no hubo nada que mutar con provecho» es un ⊘ y no un pase. Lo que este
        # test pina sigue siendo que los nodos áridos NO se mutan —el mensaje lo dice—, pero
        # el veredicto no puede ser verde: si no se probó un solo mutante, nadie verificó que
        # el test distinga. El ⊘ no bloquea la aceptación, igual que el de TypeScript; lo que
        # cambia es que ya no miente.
        self.assertEqual(r.returncode, 2,
                         f"nada que mutar es un ⊘, no un verde:\n{r.stdout}{r.stderr}")
        self.assertIn("No es un pase", r.stdout)
        self.assertIn("árido", r.stdout, "y tiene que decir que lo agregado era árido")
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


    # ── Lo de abajo mide la forma que tienen los proyectos de verdad.
    #
    # Los tres tests de arriba declaran `src/datos.py` y `src/rutas.py`: archivos PLANOS
    # cuyo nombre coincide con el de la capa. En esa forma —la del Pacman— el chequeo
    # andaba. En la otra, la de clasificados y la que describe la propia plantilla
    # (`app/datos → app/servicios → app/rutas`), una capa es un DIRECTORIO y sus módulos se
    # llaman como su asunto: `datos/ads.py`. Ahí el chequeo no mapeaba un solo módulo y
    # daba ✓ igual. El fixture plano fue la razón de que sobreviviera un mes.

    def preparar_en_directorios(self, capas, requeridas, archivos):
        """Igual que `preparar`, pero las capas son directorios y los módulos van adentro."""
        self.preparar(capas, requeridas, {})
        for ruta, cuerpo in archivos.items():
            archivo = self.p.dir / "src" / ruta
            archivo.parent.mkdir(parents=True, exist_ok=True)
            (archivo.parent / "__init__.py").write_text("")
            archivo.write_text(cuerpo)

    def test_divergencia_da_rojo_con_las_capas_en_directorios(self):
        """El mismo caso que `test_divergencia_da_rojo`, en la forma de un proyecto real."""
        self.preparar_en_directorios(["datos", "rutas"], [],
                                     {"datos/ads.py": "from ..rutas.api import x\n",
                                      "rutas/api.py": ""})
        self.assertRojo(self.arq(), "datos/ads importa rutas/api", motivo="divergencia")

    def test_dos_modulos_homonimos_en_capas_distintas_no_son_el_mismo(self):
        """`datos/ads.py` y `servicios/ads.py` existen los dos en clasificados. Con los
        módulos identificados por su nombre a secas, son UN nodo: la arista entre ellos es
        un lazo sobre sí mismo, se descarta, y una violación de capa entre los dos es
        invisible por construcción."""
        self.preparar_en_directorios(["datos", "servicios"], [("servicios", "datos")],
                                     {"datos/ads.py": "",
                                      "servicios/ads.py": "from ..datos.ads import x\n"})
        r = self.arq()
        self.assertVerde(r, "servicios/ads usa datos/ads: es la dependencia requerida")
        self.assertIn("están las", r.stdout,
                      f"la dependencia requerida se puede verificar y no se verificó:\n{r.stdout}")

    def test_una_capa_con_modulos_adentro_no_se_informa_vacia(self):
        """El ⊘ decía «servicios todavía no tiene ningún módulo» en un proyecto con
        `servicios/ads.py` y `servicios/favorites.py`. Un ⊘ es honesto cuando la causa que
        declara es la verdadera; éste nombraba una causa falsa, y por eso tapó el defecto
        durante un mes en vez de delatarlo."""
        self.preparar_en_directorios(["datos", "servicios"], [("servicios", "datos")],
                                     {"datos/ads.py": "",
                                      "servicios/ads.py": "from ..datos.ads import x\n"})
        self.assertNotIn("no tiene ningún módulo", self.arq().stdout)

    def test_importar_de_la_propia_capa_no_es_divergencia(self):
        """`datos/ads.py` importa `datos/conexion.py`: normal, y en clasificados pasa. Con
        las capas en directorios aparecen aristas DENTRO de una capa, que antes no podían
        existir (un archivo plano por capa nunca se importa a sí mismo). Prohibirlas sería
        un rojo falso en el primer proyecto real que se mire."""
        self.preparar_en_directorios(["datos", "servicios"], [],
                                     {"datos/conexion.py": "",
                                      "datos/ads.py": "from .conexion import x\n",
                                      "servicios/ads.py": "from ..datos.ads import x\n"})
        r = self.arq()
        self.assertVerde(r, "importar de la propia capa es legal")
        self.assertNotIn("cobertura del mapeo", r.stdout,
                         f"los tres módulos están en capas declaradas:\n{r.stdout}")

    def test_sin_un_solo_modulo_mapeado_no_hay_visto_bueno(self):
        """Lo que hacía en clasificados y en cualquier proyecto nuevo: cobertura 0% —ni un
        módulo en ninguna capa— y aun así `✓ dependencias en una sola dirección`. El ✓ era
        cierto y vacío: con cero módulos mapeados, el bucle de divergencias no tiene una
        sola iteración. Un chequeo que no puede fallar no es un chequeo."""
        self.preparar_en_directorios(["datos", "servicios"], [],
                                     {"cosas/saldo.py": "", "cosas/descuento.py": ""})
        r = self.arq()
        self.assertNotIn("✓", r.stdout, f"no verificó nada y puso un ✓:\n{r.stdout}")
        # Rojo y no ⊘, a propósito: un ⊘ dice «no pude medir», y acá SÍ se midió. Están los
        # módulos, están las capas, y está medido que no se parecen. Un ⊘ no bloquea nada y
        # así es como esto duró un mes.
        self.assertRojo(self.arq(), "cobertura 0%", motivo="ninguno de los 2 módulos")

    def test_una_RAIZ_que_no_existe_da_rojo_y_no_un_encogimiento_de_hombros(self):
        """Era `· no encuentro .../src: nada que verificar` con código 0, o sea «GATE VERDE»
        limpio. Quien adapta CAPAS y se olvida de RAIZ —o mueve el código— se queda sin el
        único chequeo que mira a través de las tareas, y el gate no se lo dice."""
        self.preparar(["datos"], [], {})
        a = self.p.dir / "scripts" / "_arquitectura.py"
        a.write_text(a.read_text().replace('/ "src"', '/ "donde-no-hay-nada"'))
        self.assertRojo(self.arq(), "RAIZ no existe", motivo="no existe")

    def test_un_proyecto_sin_modulos_todavia_es_un_vacio_declarado(self):
        """El otro lado: `src/` existe y todavía no hay un módulo. Eso sí es un ⊘ —el
        proyecto recién arranca— y tiene que contarse como vacío, no imprimir un ✓."""
        self.preparar(["datos"], [("datos", "datos")], {})
        r = self.arq()
        self.assertVerde(r, "un proyecto que arranca no está roto")
        self.assertIn("⊘", r.stdout, f"el vacío se declara:\n{r.stdout}")
        self.assertNotIn("✓", r.stdout, f"no verificó nada:\n{r.stdout}")


class TestElChequeoDeArquitecturaEstaVivoEnLosProyectosReales(unittest.TestCase):
    """El único chequeo del método que mira A TRAVÉS de las tareas estuvo muerto en
    clasificados —18 tareas cerradas— sin que nadie lo notara, porque informaba ✓.

    Este test no mide la plantilla sobre un proyecto de juguete: corre la copia de cada
    ejemplo sobre su propio código. Es la clase de test que faltaba, y la única que podía
    encontrar esto: todos los demás usaban un fixture con la forma en que el chequeo sí
    andaba."""

    def test_cada_ejemplo_mapea_sus_modulos_y_verifica_al_menos_una_dependencia(self):
        for proyecto in sorted(RAIZ.glob("ejemplo-*")):
            chequeo = proyecto / "scripts" / "_arquitectura.py"
            if not chequeo.exists():
                continue
            with self.subTest(proyecto=proyecto.name):
                r = correr("python3 scripts/_arquitectura.py", proyecto)
                self.assertNotIn("cobertura del mapeo: 0%", r.stdout,
                                 f"ni un módulo del proyecto cae en una capa declarada: el "
                                 f"chequeo no puede ver nada\n{r.stdout}")
                self.assertIn("están las", r.stdout,
                              f"ninguna dependencia requerida se pudo verificar en un "
                              f"proyecto con código escrito\n{r.stdout}")


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
                    # La cobertura se declara en las 6 líneas de CÓDIGO de arriba: o llama
                    # al helper, o dice «conservar_intento: no-aplica» con el motivo.
                    #
                    # De código y no de texto, y es el arreglo: la ventana contaba líneas
                    # crudas, así que un comentario largo empujaba al helper afuera y el
                    # sitio aparecía huérfano sin haber cambiado. Pasó el 2026-10-25 al
                    # documentar por qué la base se tira antes del `rm -rf`: once líneas de
                    # explicación y el sitio quedó «descubierto». En un repo con esta densidad
                    # de comentarios, medir distancia en texto es medir prosa — y el comentario
                    # de este mismo test ya decía que detectar por distancia era frágil.
                    # Se retrocede hasta acumular 6 líneas de CÓDIGO: la distancia no la
                    # puede fijar la prosa, porque en este repo un comentario de once líneas
                    # —como el que explica por qué la base se tira antes del `rm -rf`— empuja
                    # al helper fuera de una ventana contada en texto y el sitio aparece
                    # huérfano sin haber cambiado.
                    j, codigo_visto = i, 0
                    while j > 0 and codigo_visto < 6:
                        j -= 1
                        x = lineas[j].strip()
                        if x and not x.startswith("#"):
                            codigo_visto += 1
                    tramo = lineas[j:i]
                    # DOS búsquedas sobre dos conjuntos, que es lo que el comentario de este
                    # test pedía desde el principio: «o llama al helper, o dice
                    # conservar_intento: no-aplica con el motivo».
                    #
                    # La LLAMADA sólo cuenta en código. Buscar el nombre en el tramo completo
                    # lo encuentra en el comentario que explica la llamada, así que sacándola
                    # el test seguía verde — es el defecto que este mismo test dice haber
                    # arreglado, y lo reintroduje al incluir los comentarios en la ventana
                    # para no perder el marcador. Las dos cosas se pueden tener, separadas.
                    llama = any("conservar_intento" in x and not x.strip().startswith("#")
                                for x in tramo)
                    # El MARCADOR sólo cuenta en comentarios, y es una frase explícita: una
                    # mención suelta del nombre no declara nada.
                    declara = any("conservar_intento: no-aplica" in x
                                  for x in tramo if x.strip().startswith("#"))
                    sitios.append((f"{f.name}:{i + 1}", llama or declara))
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

    def test_un_submodulo_que_otra_tarea_crea_no_es_un_import_huerfano(self):
        """`provee` juntaba sólo los `def f(...)` de los contratos, así que una tarea que
        declara el ARCHIVO `backend/app/datos/ads.py` no «proveía» el módulo `ads`, y
        `from backend.app.datos import ads` salía como import huérfano. Falso rojo justo sobre
        la forma que el método EXIGE para que el `@patch` del test aplique.

        Tercera vez que el mismo caso muerde un chequeo distinto de este repo: ya había pasado
        con `_imports.py` —donde lo atrapó el control negativo contra los dos proyectos— y con
        el paso 4 del gate. Un submódulo declarado como archivo es una declaración; que no
        tenga `def` no la vuelve inexistente."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-coh-sub-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-datos.md").write_text(
            "# T01 — datos\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/ads.py\n**Prohibido tocar:** \n\n"
            "## Contrato\n\n```python\ndef insert_ad(x: int) -> int: ...\n```\n")
        (d / "tareas" / "T02-servicio.md").write_text(
            "# T02 — servicio\n\n**Estado:** pendiente\n**Depende de:** T01\n"
            "**Archivos que podés tocar:** app/servicios/ads.py\n**Prohibido tocar:** \n\n"
            "## Contrato\n\n```python\nfrom app.datos import ads\n"
            "def crear(x: int) -> int: ...\n```\n")
        r = correr(f"python3 {SCRIPTS}/coherencia.py", d)
        self.assertEqual(r.returncode, 0,
                         f"falso rojo sobre un submódulo que otra tarea crea:\n{r.stdout}")

    def test_un_import_que_nadie_provee_sigue_siendo_rojo(self):
        """Brazo nulo del anterior: si cualquier nombre contara como provisto, el chequeo
        dejaría de existir. Éste es el cadáver original (T05 inventando
        `obtener_usuario_id_desde_token` y grepeando siete coincidencias, todas suyas)."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-coh-huer-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-servicio.md").write_text(
            "# T01 — servicio\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/servicios/x.py\n**Prohibido tocar:** \n\n"
            "## Contrato\n\n```python\n"
            "from app.servicios.auth import obtener_usuario_id_desde_token\n"
            "def f() -> int: ...\n```\n")
        r = correr(f"python3 {SCRIPTS}/coherencia.py", d)
        self.assertEqual(r.returncode, 1, f"dejó pasar un import que nadie provee:\n{r.stdout}")
        self.assertIn("obtener_usuario_id_desde_token", r.stdout)

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
        # La aserción va contra EL AVISO QUE ESTE TEST MIDE, no contra cualquier `⚠`. La
        # primera versión decía `assertNotIn("⚠", ...)` y se puso roja cuando el cruce empezó
        # a informar su cobertura —«1 de 1 tarea no declara imports»—, que es un aviso correcto
        # y de otro asunto. Una aserción más amplia que su sujeto convierte cualquier mejora
        # del chequeo en un rojo que no habla de lo que el test vino a fijar.
        self.assertNotIn("nombra `", r.stdout,
                         f"la cita del defecto viejo no es una declaración:\n{r.stdout}")
        self.assertNotIn("hashlib", r.stdout, f"\n{r.stdout}")


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
        self.assertIn("VACÍOS", f, "y reprobar el test que lo satisface")
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
            # `0` y no `1`: la columna la mide quien LANZA, antes de lanzar, así que la
            # corrida no se cuenta a sí misma y 0 es «ninguna otra viva». Con `<= 1` el
            # filtro admitía una fila con un competidor vivo, que es justo lo que la columna
            # existe para excluir — y antes de arreglarlo la columna se medía al CERRAR, con
            # lo que sus valores decrecían con el orden de finalización.
            ("serializadas", enc9, filas(0), "mediana"),
            ("un competidor vivo", enc9, filas(1), "—"),
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


class TestLaTerceraAuditoria(unittest.TestCase):
    """Los defectos que encontró la auditoría del 2026-10-20, sobre dos superficies: los ~60
    commits del día anterior y el aparato de medición.

    El resultado que ordena a todos los demás: **cuatro de los chequeos que esos commits
    introdujeron o acotaron no podían fallar**, y dos están en el mismo archivo y el mismo
    commit — el que el informe anterior anota como «acoté un chequeo demasiado ancho y lo
    volví demasiado angosto». La estrechez quedó, por los dos lados que no se probaron.

    Y una lección de forma: el defecto más caro de la lista —`git cat-file -e "$base:$ruta"`
    resuelto desde la raíz del repo y no desde el cwd— tenía su test, y el test armaba el
    repo con el proyecto EN LA RAÍZ, donde el prefijo es vacío. La clase `Proyecto` de este
    mismo archivo existe para eso y lleva el comentario que lo explica desde hace semanas.
    No alcanza con tener el caso: hay que usarlo.
    """

    # ── El acote al diff: el prefijo y el tramo ────────────────────────────────────────

    def repo_sub(self, contenido):
        """Un repo con el proyecto en un SUBDIRECTORIO, que es donde vive todo proyecto real
        y donde el prefijo de git no es vacío."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-aud3-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "proyecto" / "app").mkdir(parents=True)
        (d / "proyecto" / "app" / "m.py").write_text(contenido)
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        return d / "proyecto", d / "proyecto" / "app" / "m.py"

    def sup(self, cwd, arg="app/m.py", base="HEAD"):
        return correr(f'BASE={base} python3 "{SCRIPTS}/_suprimidas.py" {arg}', cwd)

    def test_el_acote_al_diff_funciona_con_el_proyecto_en_un_subdirectorio(self):
        """`git cat-file -e <rev>:<ruta>` resuelve la ruta desde la RAÍZ DEL REPO, no desde el
        cwd, así que sin el prefijo salía 128 («path does not exist») para todo proyecto que
        viva en un subdirectorio —los dos ejemplos y cualquier monorepo—. `lineas_cambiadas`
        devolvía None siempre, el acote no existía, y las tres `except Exception: pass` del
        idiom de curses seguían reprobando a T07, T08, T11 y T12 de pacman: exactamente el
        defecto que el acote venía a cerrar. Medido con el árbol limpio: rc 1 sobre un archivo
        IDÉNTICO a HEAD. El gate hacía esto bien dos pasos más abajo, con el comentario que
        explica el mecanismo; el arreglo del hermano no se copió."""
        p, _ = self.repo_sub("def f():\n    try:\n        pass\n    except Exception:\n        pass\n")
        r = self.sup(p)
        self.assertEqual(r.returncode, 0,
                         f"le cobra una señal que ya estaba y que no tocó:\n{r.stdout}")

    def test_una_senal_nueva_en_un_subdirectorio_sigue_cayendo(self):
        """Brazo nulo del test de arriba: si el prefijo arreglado apagara el chequeo, daría
        verde acá también."""
        p, f = self.repo_sub("def f():\n    return 1\n")
        f.write_text(f.read_text() + "\ndef g():\n    try:\n        pass\n"
                     "    except Exception:\n        pass\n")
        r = self.sup(p)
        self.assertEqual(r.returncode, 1, f"una señal NUEVA tiene que caer:\n{r.stdout}")

    def test_apagar_un_handler_que_ya_existia_no_pasa_el_acote(self):
        """El hallazgo se registraba en la línea del `except` y el acote compara contra las
        líneas que el cambio TOCÓ. Quien reemplaza el cuerpo de un handler existente por
        `pass` cambia la línea del CUERPO, no la del `except`: el filtro lo dejaba pasar sin
        imprimir nada. Es la forma más común de apagar una señal en código que ya existe, y
        es la mitad que el arreglo del archivo nuevo no cubrió."""
        p, f = self.repo_sub("import logging\n\n\ndef f():\n    try:\n        pass\n"
                            "    except Exception as e:\n        logging.error(e)\n")
        f.write_text(f.read_text().replace("        logging.error(e)", "        pass"))
        r = self.sup(p)
        self.assertEqual(r.returncode, 1,
                         f"apagar un handler que ya estaba tiene que caer:\n{r.stdout}")

    def test_saltear_un_test_que_ya_existia_no_pasa_el_acote(self):
        """La otra forma de la misma cosa: el `@skip` agregado arriba de un test que ya
        estaba. Se informaba en la línea del `def`, que no cambió."""
        p, f = self.repo_sub("import unittest\n\n\nclass T(unittest.TestCase):\n"
                            "    def test_a(self):\n        self.assertTrue(True)\n")
        f.write_text(f.read_text().replace("    def test_a",
                                           "    @unittest.skip('luego')\n    def test_a"))
        r = self.sup(p)
        self.assertEqual(r.returncode, 1, f"saltear un test que ya estaba cae:\n{r.stdout}")

    def test_en_modo_integracion_el_chequeo_no_se_acota_a_nada(self):
        """Los tres gates pasaban `BASE="${BASE_REF:-}"` en LOS DOS modos, aunque el
        comentario de arriba decía «en modo tarea, sólo lo que ESTA tarea tocó». En el tronco
        `BASE_REF` es el merge-base con main —o sea HEAD— y el árbol está limpio, así que el
        diff no tiene un solo hunk: `tocadas` quedaba en el conjunto VACÍO, que no es None, y
        se filtraban TODOS los hallazgos. El chequeo quedaba decorativo justo en el modo que
        revisa el tronco entero. Al arreglarlo, el tronco del pacman salió rojo en el acto
        con las tres de curses, que se marcaron `# best-effort`: el chequeo encontró lo que
        existe para encontrar en la primera corrida en que pudo fallar."""
        p, _ = self.repo_sub("def f():\n    try:\n        pass\n    except Exception:\n        pass\n")
        r = self.sup(p, base="")       # modo integración: sin base
        self.assertEqual(r.returncode, 1,
                         f"sin base no se filtra NADA; esto tiene que ser rojo:\n{r.stdout}")
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.parent.name):
                s = g.read_text()
                invoca = [l for l in s.split("\n")
                          if "_suprimidas.py" in l and "aux_del_metodo" in l
                          and ("python3" in l or "PY_PROYECTO" in l)]
                self.assertEqual(len(invoca), 1, f"una sola invocación: {invoca}")
                self.assertIn('BASE="$BASE_SUP"', invoca[0],
                              "la base tiene que venir de una variable que distinga el modo")
                self.assertRegex(s, r'BASE_SUP=""',
                                 "y en modo integración tiene que ser vacía")

    # ── `expone`: un falso ROJO sobre código que anda ──────────────────────────────────

    def imports(self, cwd, arg):
        return correr(f'python3 "{SCRIPTS}/_imports.py" {arg}', cwd)

    def proyecto_dos_modulos(self, conf, usa):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-exp-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "app").mkdir()
        (d / "app" / "__init__.py").touch()
        (d / "app" / "conf.py").write_text(conf)
        (d / "app" / "usa.py").write_text(usa)
        return d

    def test_expone_ve_todas_las_formas_de_ligar_un_nombre(self):
        """`expone()` enumeraba CUATRO formas de definir un nombre (`Assign` con target
        `Name`, `AnnAssign`, los dos `import`) y todo lo demás le era invisible, así que daba
        ROJO sobre código que Python corre sin chistar. Y el mensaje manda a buscar el nombre
        donde sí está —«fijate cómo se llama»—, o sea que la tarea quema sus reintentos contra
        un rojo que sólo se apaga reescribiendo una asignación correcta. Un chequeo que
        enumera formas envejece callando: cada forma del lenguaje que no esté en la lista es
        un falso rojo esperando. Las que ligan nombres son las de contexto Store, y eso el
        árbol sintáctico ya lo dice."""
        casos = {
            "tupla": "DATO, OTRO = 1, 2\n",
            "with": "import os\nwith open(os.devnull) as _f:\n    DATO = _f.name\nOTRO = 1\n",
            "for": "for _n in (1,):\n    DATO = _n\nOTRO = 1\n",
            "match": "match 1:\n    case 1:\n        DATO = True\nOTRO = 1\n",
            "walrus": "if (DATO := 1):\n    pass\nOTRO = 1\n",
            "aumentada": "DATO = 0\nDATO += 1\nOTRO = 1\n",
        }
        for nombre, conf in casos.items():
            with self.subTest(forma=nombre):
                d = self.proyecto_dos_modulos(conf, "from .conf import DATO\nprint(DATO)\n")
                # Control positivo: si Python no lo corre, el caso está mal escrito y el
                # chequeo tendría razón. Se verifica antes de exigirle verde al chequeo.
                real = correr("python3 -c 'import app.usa'", d)
                self.assertEqual(real.returncode, 0,
                                 f"el caso tiene que correr de verdad:\n{real.stderr}")
                r = self.imports(d, "app/usa.py")
                self.assertEqual(r.returncode, 0,
                                 f"falso rojo sobre código que anda ({nombre}):\n{r.stdout}")

    def test_un_nombre_que_de_verdad_no_esta_sigue_cayendo(self):
        """Brazo nulo: el arreglo de arriba no puede ser «aceptá todo». Éste es el cadáver
        original, `get_db_connection`, que es por lo que el chequeo existe."""
        d = self.proyecto_dos_modulos("DATO = 1\n", "from .conf import NO_EXISTE\n")
        r = self.imports(d, "app/usa.py")
        self.assertEqual(r.returncode, 1, f"un nombre inventado tiene que caer:\n{r.stdout}")
        self.assertIn("NO_EXISTE", r.stdout, "y el informe tiene que decir cuál")

    # ── El único eslabón que fallaba abierto ───────────────────────────────────────────

    def test_si_falta_el_chequeo_de_imports_el_gate_da_rojo_y_dice_de_quien_es(self):
        """`if [ -n "$(aux_del_metodo _imports.py)" ]; then … fi`, sin `else`: si el resolver
        devolvía vacío, el paso no imprimía nada, no sumaba a FALLOS ni a VACIOS, y el
        veredicto salía «GATE VERDE» limpio —ni siquiera «con N chequeos que no pudieron
        correr»—. Era el único eslabón de la cadena nueva que fallaba ABIERTO; su hermano
        `_suprimidas.py` tenía su `rojo` desde el principio, y el mensaje del commit que movió
        los chequeos al método afirmaba que los dos lo tenían. Cualquier gate corrido sin
        $AGENTES exportada (CI, cron, una shell nueva) perdía el chequeo en silencio, y el
        commit que los movió borró la copia local de la plantilla."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.parent.name):
                s = g.read_text()
                # Por ESTRUCTURA y no por distancia: la primera versión de este test miraba
                # una ventana de 400 caracteres y el comentario que explica el arreglo la
                # desbordó, así que reprobaba al código arreglado. Duodécima vez que un
                # chequeo mío confunde «cerca» con «en el mismo bloque».
                i = s.index('if [ -z "$(aux_del_metodo _imports.py)" ]; then')
                # La rama negativa, y que sea `rojo`: un `echo` acá es la misma vacuidad.
                j = s.index('rojo "falta scripts/_imports.py', i)
                self.assertLess(i, j, "el rojo va dentro de la rama que detecta la falta")
                self.assertLess(j, s.index("\nelse\n", i),
                                "y antes del `else`, o sea en la rama negativa")

    def test_el_gate_que_no_encuentra_un_chequeo_no_dice_verde(self):
        """Conducta, no forma: un proyecto sin el chequeo y sin $AGENTES no puede cerrar
        verde. Vale para los dos chequeos de la cadena."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        p.implementar()
        (p.dir / "scripts" / "_suprimidas.py").unlink()
        r = correr("bash scripts/gate.sh", p.dir, TAREA="", AGENTES="/no/existe")
        self.assertNotEqual(r.returncode, 0,
                            f"sin los chequeos del método el gate no puede dar verde:\n{r.stdout}")
        self.assertRegex(r.stdout, r"falta scripts/_(imports|suprimidas)\.py",
                         f"y tiene que decir qué falta y de quién es:\n{r.stdout}")

    # ── La huella del instrumento ──────────────────────────────────────────────────────

    def huella(self, d):
        """La función real del método, apuntada al directorio `d`.

        Antes se extraía con awk de `correr-todo.sh` y se evaluaba con `AQUI` apuntando a
        `d`. Al mudarla a `_comun.sh` el test se rompió —no por conducta: por ubicación y por
        nombre de variable—, y además la función había quedado clavada a `$AGENTES/scripts`,
        o sea inverificable. Ahora toma el directorio como argumento y el test la llama."""
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; huella_scripts "{d}"',
                      RAIZ).stdout.strip()

    def test_la_huella_del_instrumento_cubre_los_py_y_no_solo_los_sh(self):
        """`cat "$AQUI"/*.sh` dejaba afuera los diez `.py` que viven en `scripts/` y que SON
        el instrumento: `_imports.py` y `_suprimidas.py` son lo que el gate ejecuta,
        `mutar.py` y `vaciar.py` deciden si un test se acepta, `coherencia.py` y `_etapas.py`
        deciden si el plan arranca y cómo se cortan las etapas. Editar uno con el plan en
        vuelo —que es literalmente lo que pasó cuatro veces el 2026-10-20— pasaba el guardia
        de borde de etapa en silencio: la etapa 1 se juzgaba con un chequeo y la etapa 5 con
        otro, y el guardia decía que era la misma corrida."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-huella2-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "a.sh").write_text("echo a\n")
        (d / "b.py").write_text("print('b')\n")
        antes = self.huella(d)
        self.assertRegex(antes, r"^[0-9a-f]{7,}$", f"la huella tiene que ser un hash: {antes}")
        (d / "b.py").write_text("print('b2')\n")
        self.assertNotEqual(antes, self.huella(d),
                            "cambiar un .py de scripts/ CAMBIA el instrumento")
        # Y no depende de un `.DS_Store` que aparezca en el medio: eso no es el método.
        (d / ".DS_Store").write_text("basura\n")
        self.assertEqual(self.huella(d), self.huella(d),
                         "la huella tiene que ser estable")
        sin_punto = self.huella(d)
        (d / ".DS_Store").write_text("otra basura\n")
        self.assertEqual(sin_punto, self.huella(d),
                         "un archivo que empieza con punto no es el instrumento")

    def test_la_marca_de_sin_commitear_ve_los_cambios_en_el_stage(self):
        """`git diff --quiet -- scripts` compara árbol↔ÍNDICE, así que un `git add scripts/`
        —el reflejo de cualquiera que quiera mirar su propio diff antes de lanzar— apagaba la
        marca: la fila quedaba con la huella del commit viejo y sin aviso, que es justo el
        estado que la marca existe para delatar. El modelo que se citó al escribirla
        (`congelar-banco.sh`) tenía el mismo defecto, así que el arreglo copió el agujero."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-stage-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "scripts").mkdir()
        (d / "scripts" / "x.sh").write_text("echo 1\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        (d / "scripts" / "x.sh").write_text("echo 2\n")
        subprocess.run(["git", "add", "scripts"], cwd=d, check=True, capture_output=True)
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'anotar_intento T01 ROJO 10 abc', RAIZ)
        fila = (d / ".metricas" / "intentos.csv").read_text().strip().split("\n")[-1]
        self.assertIn("+sin-commitear", fila,
                      f"un cambio en el stage es un instrumento sin commitear:\n{fila}")

    # ── El veredicto que se escribe ────────────────────────────────────────────────────

    def test_el_registro_escribe_el_veredicto_del_gate_no_el_ruido_de_la_herramienta(self):
        """El arreglo «el gate primero, siempre» entró en el mensaje de CONSOLA y no en el
        valor que se escribe, así que el registro siguió contradiciendo al gate. Medido: T07,
        T27 y T06 del 2026-10-04 tienen su commit `TNN: gate verde` al segundo exacto de una
        fila ERROR —y `cerrar_con_gate` commitea sólo con rc 0, así que el commit prueba el
        verde—, y `metricas.sh` las informaba como «nunca llegaron a verde» y además las
        descontaba como pérdida de plataforma: un ⊘ tapando un sí, contra el modelo y contra
        la tarea a la vez. Es P2: el juez es un comando."""
        def v(rc, error, log="/dev/null"):
            return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                          f'veredicto_registrado {rc} "{error}" "{log}"', RAIZ).stdout.strip()
        self.assertEqual(v(0, "api_error: 500"), "VERDE",
                         "si el gate dio 0, el ruido del log no lo desmiente")
        self.assertEqual(v(1, "api_error: 500"), "ERROR",
                         "con el gate en rojo, el error de la herramienta sí manda")
        self.assertEqual(v(1, ""), "ROJO",
                         "y nunca se escribe una columna vacía: nadie la puede clasificar")
        # Y el llamador tiene que usar la función, no decidir inline otra vez.
        s = (SCRIPTS / "correr-tarea.sh").read_text()
        linea = [l for l in s.split("\n") if "anotar_intento" in l and "$id" in l]
        self.assertEqual(len(linea), 1, f"una sola llamada: {linea}")
        self.assertIn("veredicto_registrado", linea[0],
                      "la decisión vive en la función, que es lo que se puede verificar")

    def test_la_concurrencia_se_mide_al_arrancar_y_no_al_cerrar(self):
        """`anotar_intento` la contaba sola, y corre DESPUÉS del agente y del gate: lo que
        anotaba era «cuántas quedaban vivas cuando yo ya terminé». Medido en la tanda del
        2026-10-19: cuatro tareas arrancadas en 12 segundos, solapadas por completo, con
        valores 1, 2, 2 y 0 que decrecen con el orden de finalización — y la que compitió con
        tres durante sus 970 s enteros quedó anotada como 0, o sea como la única serializada.
        La columna que existe para que el tiempo no mida la ocupación de la plataforma estaba
        midiendo la ocupación de la plataforma."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-conc-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; RAIZ="{d}" PROYECTO=p '
               f'CONCURRENCIA_AL_ARRANCAR=3 anotar_intento T01 VERDE 10 abc', RAIZ)
        fila = (d / ".metricas" / "intentos.csv").read_text().strip().split("\n")[-1]
        self.assertEqual(fila.split(",")[7], "3",
                         f"la concurrencia que se anota es la que midió quien lanzó:\n{fila}")
        # Y quien lanza la tiene que medir ANTES de lanzar al agente.
        s = (SCRIPTS / "correr-tarea.sh").read_text()
        i_mide = s.index("CONCURRENCIA_AL_ARRANCAR=")
        i_lanza = s.index("opencode run --agent")
        self.assertLess(i_mide, i_lanza,
                        "medirla después de lanzar al agente es medir otra cosa")

    # ── El lector: qué fila puede entrar a una tasa ────────────────────────────────────

    def repo_con_registro(self, filas):
        """Un repo de juguete con un proyecto y un registro, para correr `metricas.sh`."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-met3-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "p" / "tareas").mkdir(parents=True)
        (d / ".metricas").mkdir()
        # Con `scripts/` commiteado: sin él no hay huella de instrumento que leer, y el
        # bloque de comparabilidad no tiene contra qué comparar.
        (d / "scripts").mkdir()
        (d / "scripts" / "x.sh").write_text("echo 1\n")
        enc = ("fecha,proyecto,tarea,veredicto,segundos,modelo,motivo,"
               "concurrencia,instrumento")
        (d / ".metricas" / "intentos.csv").write_text("\n".join([enc, *filas]) + "\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        return d

    def metricas(self, d):
        return correr(f'bash "{SCRIPTS}/metricas.sh"', d, PROYECTO="p").stdout

    def test_el_lector_no_cuenta_contra_el_modelo_lo_que_no_es_del_modelo(self):
        """Tres clases de fila no hablan del ejecutor y el instrumento las contaba como su
        rojo o como su verde:

        · INVÁLIDA del método: `correr-suite.sh` declara `exit 3` = «defecto del método o
          del plan, no del código que se juzga». Los primeros intentos de T01, T02 y T03 de
          clasificados son eso —faltaba el corredor—, y contaban como ROJO del modelo.
        · PERDIDA por la plataforma: el propio informe dice «no cuentan contra el modelo»
          tres bloques más abajo, y acto seguido una fila ERROR hacía de primer intento.
        · NO ATRIBUIBLE: `cerrar-tarea.sh` escribe `modelo=humano` en el MISMO registro. El
          61% del pacman se apoyaba en una fila con `segundos=0` y `modelo=humano`; sacando
          las cuatro filas no atribuibles da 44%, o sea el otro lado del umbral. El único
          proyecto del repo que «funcionaba» lo hacía por trabajo humano contado como verde
          del modelo.
        """
        filas = [
            # T01: el método falló primero, el modelo acertó en cuanto pudo correr.
            "2026-01-01T00:00:00Z,p,T01,ROJO,10,m1,✗ falta el corredor de tests,0,aa",
            "2026-01-01T00:10:00Z,p,T01,VERDE,20,m1,,0,aa",
            # T02: la plataforma se comió el primero.
            "2026-01-01T00:20:00Z,p,T02,ERROR,10,m1,agente: api_error,0,aa",
            "2026-01-01T00:30:00Z,p,T02,VERDE,20,m1,,0,aa",
            # T03: la cerró un humano. No es evidencia sobre ningún modelo.
            "2026-01-01T00:40:00Z,p,T03,VERDE,0,humano,,0,aa",
            # T04: el modelo falló de verdad. Ésta sí cuenta, y en contra.
            "2026-01-01T00:50:00Z,p,T04,ROJO,30,m1,✗ los tests siguen fallando,0,aa",
        ]
        s = self.metricas(self.repo_con_registro(filas))
        self.assertIn("Verde al PRIMER intento: 2/3", s,
                      f"T01 y T02 cuentan como verde al primer intento CONTABLE, "
                      f"T03 no cuenta, T04 cuenta en contra:\n{s}")
        self.assertIn("⊘ fuera de esa tasa: 1 tarea(s)", s,
                      f"y la tarea que no cuenta se informa, no se esconde:\n{s}")
        self.assertIn("1 intento(s) inválidos del método", s,
                      f"y el inválido del método también:\n{s}")

    def test_la_lista_de_motivos_invalidos_cubre_los_mensajes_que_el_gate_imprime(self):
        """La detección del inválido es una ENUMERACIÓN de marcas en el texto del motivo, que
        es la forma que envejece callando. Esto la cruza contra los mensajes que los gates
        imprimen DE VERDAD: si alguien reescribe el mensaje del corredor faltante, el lector
        vuelve a contar un defecto del método como rojo del modelo, y acá se entera."""
        m_ = re.search(r'MARCAS_INVALIDO = \((.*?)\)',
                       (SCRIPTS / "metricas.sh").read_text(), re.S)
        self.assertIsNotNone(m_, "el lector no declara qué motivos son inválidos del método: "
                                 "sin eso vuelve a contarlos como rojo del modelo")
        marcas = [x.strip().strip('"') for x in m_.group(1).split(",") if x.strip()]
        mensajes = []
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            mensajes += re.findall(r'rojo "([^"]*corredor[^"]*)"', g.read_text())
            mensajes += re.findall(r'rojo "([^"]*ningún test[^"]*)"', g.read_text())
        self.assertTrue(mensajes, "si el gate ya no dice nada de esto, revisá este test")
        for m in mensajes:
            with self.subTest(mensaje=m[:50]):
                self.assertTrue(any(x in m.lower() for x in marcas),
                                f"el lector no reconoce como inválido un mensaje que el gate "
                                f"imprime: «{m}» contra {marcas}")

    def test_el_instrumento_de_ahora_se_compara_por_igualdad_y_avisa_con_una_sola_huella(self):
        """Dos defectos del mismo bloque:

        · `startswith(actual)` metía `X` y `X+sin-commitear` en el mismo balde, deshaciendo
          dos líneas más abajo la distinción que el escritor acababa de crear — y que existe
          justamente para separar la corrida commiteada de la que no lo está.
        · Todo el bloque vivía dentro de `if len(huellas) > 1`. Proyecto nuevo, las cinco
          tareas corridas con el instrumento A, arreglás un script: UNA sola huella, ni un ⊘,
          y el número se seguía anunciando como si describiera el instrumento instalado.
          Lo que invalida la comparación no es que haya varias huellas: es que la de los
          datos no sea la de ahora.
        """
        d = self.repo_con_registro([
            "2026-01-01T00:00:00Z,p,T01,VERDE,10,m1,,0,viejo",
            "2026-01-01T00:10:00Z,p,T02,VERDE,10,m1,,0,viejo",
        ])
        s = self.metricas(d)
        self.assertIn("⊘ el instrumento de ahora", s,
                      f"con UNA huella que no es la de ahora, también hay que avisar:\n{s}")
        self.assertNotIn("con el instrumento de ahora (", s.split("⊘ el instrumento")[-1]
                         .split("\n")[0], "no puede informar una tasa de datos ajenos")

    def test_el_lector_informa_lo_mismo_desde_la_raiz_y_desde_el_proyecto(self):
        """Relación metamórfica: el informe no puede depender de dónde estás parado.
        `HEAD:scripts` lo resuelve git desde la RAÍZ del repo y el pathspec de `git diff` es
        relativo al cwd, así que corrido desde el subdirectorio del proyecto una pregunta
        miraba los scripts del método y la otra los del proyecto. Lo cometí en el arreglo
        de la huella mientras arreglaba el mismo defecto en `_suprimidas.py`."""
        d = self.repo_con_registro([
            "2026-01-01T00:00:00Z,p,T01,VERDE,10,m1,,0,aa",
        ])
        (d / "p" / "scripts").mkdir()
        (d / "p" / "scripts" / "otro.sh").write_text("echo distinto\n")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "scripts del proyecto"], cwd=d, check=True,
                       capture_output=True)
        # El `scripts/` DEL PROYECTO sucio y el del método limpio: es la asimetría que hace
        # visible la diferencia. Con los dos limpios las dos rutas coinciden por casualidad,
        # y la primera versión de este test daba verde con el defecto puesto.
        (d / "p" / "scripts" / "otro.sh").write_text("echo cambiado\n")
        desde_raiz = correr(f'bash "{SCRIPTS}/metricas.sh"', d, PROYECTO="p").stdout
        desde_proy = correr(f'bash "{SCRIPTS}/metricas.sh"', d / "p", PROYECTO="p").stdout
        self.assertEqual(desde_raiz, desde_proy,
                         "el informe cambia según el directorio desde el que se lo corre:\n"
                         f"--- raíz:\n{desde_raiz}\n--- proyecto:\n{desde_proy}")

    def test_la_mediana_de_tiempo_no_lleva_el_techo_del_propio_vigilante(self):
        """6 de las 16 filas que entraban a la mediana eran ERROR, y 4 de ellas con «límite
        total 1200s» en el motivo: el techo del vigilante metido adentro del número.
        `MEDICION.md` §4 manda INVÁLIDO para un timeout. El «máximo 1855s» que se imprimía
        era un ROJO, y el éxito más lento medía 970 s — y es ese número, no el máximo, el que
        `_comun.sh` manda mirar para dimensionar el presupuesto del agente. Calibrar un
        presupuesto con el techo de la propia regla es medirse con la regla."""
        d = self.repo_con_registro([
            "2026-01-01T00:00:00Z,p,T01,VERDE,100,m1,,0,aa",
            "2026-01-01T00:10:00Z,p,T02,ERROR,1200,m1,el agente no respondió: límite total 1200s,0,aa",
        ])
        s = self.metricas(d)
        self.assertIn("éxito más lento: 100s", s,
                      f"el número para calibrar es el éxito más lento:\n{s}")
        self.assertNotIn("1200", s.split("Tiempo por intento")[-1],
                         f"el techo del vigilante no entra a la estadística de tiempo:\n{s}")

    # ── «Por diseño» es una afirmación que hay que verificar ───────────────────────────

    def test_el_estado_imprime_las_fallas_y_no_declara_por_diseno_sin_comprobarlo(self):
        """`en_vuelo` se llenaba si CUALQUIER tarea no-✅ tenía su archivo de test presente, y
        el `grep '✗'` vivía sólo en el `else`: con una etapa en vuelo, un tronco realmente
        roto no mostraba una sola falla. Es el estado exacto de clasificados el 2026-10-19
        —etapa en vuelo Y T14 integrada con un `from .conexion import get_db_connection` que
        abortaba la colección entera—: el informe decía «por diseño» y el ImportError quedaba
        invisible. Cambiar un rojo que no medía por un rojo que se explica sin comprobar la
        explicación es la misma vacuidad con otra cara."""
        s = (SCRIPTS / "estado.sh").read_text()
        self.assertIn('echo "tronco: ✗ rojo —', s,
                      "el informe tiene que imprimir las fallas del tronco en TODOS los "
                      "casos, no sólo cuando no hay una etapa en vuelo")
        self.assertLess(s.index('echo "tronco: ✗ rojo —'),
                        s.index('if [ -n "$en_vuelo" ]; then',
                                s.index('echo "tronco: ✗ rojo —')),
                        "las fallas se imprimen ANTES de decidir si el rojo es por diseño")
        self.assertIn("NO las explica ningún test en vuelo", s,
                      "«por diseño» se verifica falla por falla, no se afirma")
        # Y el aviso tiene que poder dispararse: una falla que ningún test en vuelo nombra.
        self.assertRegex(s, r'ajenas="\$ajenas',
                         "tiene que juntar las fallas que el «por diseño» no cubre")

    # ── La guardia que quedó en un solo hermano ────────────────────────────────────────

    def test_los_dos_runners_rechazan_saltear_una_etapa_pendiente(self):
        """La guardia nació del salteo de T05 —los números de etapa se recalculan en cada
        corrida, así que `correr-todo.sh 2` salteó tres tareas sin un solo aviso— y se escribió
        **sólo en `correr-todo.sh`**. `correr-plan.sh` siguió tomando el índice sin guardia: el
        arreglo dejó abierto el script hermano del defecto que venía a cerrar, reproducido por
        un auditor sobre el plan real (`DESDE=2` saltea T05a). Es la cuarta vez en un día que
        un arreglo se aplica a una copia y no a su hermana, así que ahora hay UNA copia."""
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'rechazar_salteo 2 "relanzá así" "T01 T02" "T03"', RAIZ)
        self.assertEqual(r.returncode, 1, f"saltear una etapa pendiente se rechaza:\n{r.stdout}")
        self.assertIn("T01 T02", r.stderr, "y tiene que decir QUÉ se saltea")
        self.assertIn("relanzá así", r.stderr, "y cómo relanzar bien")
        ok = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                    f'rechazar_salteo 1 "x" "T01" "T02"; echo PASO', RAIZ)
        self.assertIn("PASO", ok.stdout, "sin salteo no molesta")
        for runner in ("correr-todo.sh", "correr-plan.sh"):
            with self.subTest(runner=runner):
                s = (SCRIPTS / runner).read_text()
                self.assertIn('rechazar_salteo "$DESDE"', s,
                              f"{runner} toma un índice de etapa y tiene que llamar la guardia")
                self.assertLess(s.index('rechazar_salteo "$DESDE"'),
                                s.index('[ "$n" -ge "$DESDE" ] || continue'),
                                "la guardia va ANTES del bucle que saltea")

    # ── El paso 4, en los tres gates ───────────────────────────────────────────────────

    def test_los_tres_gates_deducen_el_paso_4_del_alcance_declarado(self):
        """`IMPL` se deducía con un patrón de rutas (`^$CODIGO/`, `^src/.*\\.py$`), así que
        quedaba VACÍO para toda tarea cuya implementación no cayera en él —un `.scss`, un
        `.sql`, un manifiesto, un archivo fuera del directorio de código—: el paso imprimía
        «⊘ no hay implementación que revertir» y el gate cerraba, con el ÚNICO chequeo de que
        los tests distinguen sin correr. El arreglo existía en UN ejemplo de tres, y faltaba
        justamente en la plantilla, que es la que copia todo proyecto nuevo."""
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.parent.name):
                s = g.read_text()
                self.assertIn("declarado_por_la_tarea", s,
                              "el alcance del paso 4 sale de lo que la tarea DECLARA")
                i = s.index("── 4. ¿Los tests distinguen?")
                bloque = s[i:i + 1200]
                self.assertIn("declarado_por_la_tarea", bloque,
                              "y el paso 4 lo tiene que usar, no sólo definirlo")
                self.assertNotRegex(bloque, r'IMPL="\$\(echo "\$CAMBIADOS" \| grep -E',
                                    "nada de patrones de ruta: envejecen con cada extensión")

    def test_el_paso_4_revierte_una_implementacion_que_no_es_py(self):
        """Conducta: una tarea cuyo alcance es un archivo que ningún patrón de los viejos
        matcheaba. El paso 4 tiene que revertirlo y exigir rojo, no saltearse."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        # FUERA de `$CODIGO` a propósito: un `.scss` dentro de `src/` lo matcheaba el patrón
        # viejo por casualidad, y la primera versión de este test daba verde con el defecto
        # puesto. Lo que el patrón no podía ver es lo que vive en otro directorio.
        (p.dir / "assets").mkdir()
        p.declarar("assets/estilos.scss")
        (p.dir / "assets" / "estilos.scss").write_text(".a { color: red; }\n")
        (p.dir / "tests" / "test_cosa.py").write_text(
            "import pathlib, unittest\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_hay_estilo(self):\n"
            "        self.assertIn('color', "
            "pathlib.Path('assets/estilos.scss').read_text())\n")
        r = p.gate("T01")
        self.assertNotIn("no hay implementación que revertir", r.stdout,
                         f"un .scss declarado fuera de $CODIGO ES implementación:\n{r.stdout}")
        self.assertIn("assets/estilos.scss", r.stdout,
                      f"y el paso 4 tiene que nombrar lo que revirtió:\n{r.stdout}")

    # ── El informe de estado nombra al sujeto correcto ─────────────────────────────────

    def test_un_worktree_sin_entorno_no_se_informa_como_tronco_roto(self):
        """`estado.sh` imprimía ocho fallas de colección por `ModuleNotFoundError: pymysql`
        —un worktree de desarrollo sin `.venv` ni `node_modules`— y las atribuía a «lo
        mergeado sin pasar su propio gate». Es la distinción que `correr-suite.sh` codifica en
        su código 3 y que este informe perdía: no es que la suite corrió y dio mal, es que no
        corrió. Acusar al merge por un worktree sin entorno es nombrar mal al sujeto."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        (p.dir / "requirements.txt").write_text("pymysql\n")
        (p.dir / "tareas" / "T01-cosa.md").write_text(
            (p.dir / "tareas" / "T01-cosa.md").read_text().replace(
                "## Tests (ya escritos, fallando)\n\nArchivo: `tests/test_cosa.py`, clase `TestCosa`.\n",
                "## Tests\n\nNinguno todavía.\n"))
        p.git("add -A"); p.git("commit -qm reqs")
        r = correr(f'bash "{SCRIPTS}/estado.sh"', p.dir, PROYECTO="proyecto")
        self.assertIn("no tiene entorno", r.stdout,
                      f"el informe tiene que nombrar el entorno como causa:\n{r.stdout}")
        self.assertIn(".venv", r.stdout, f"y decir qué falta:\n{r.stdout}")
        self.assertNotIn("sin pasar su propio gate", r.stdout,
                         f"y NO acusar a lo mergeado:\n{r.stdout}")

    def test_el_test_en_vuelo_explica_su_falla_en_las_dos_notaciones(self):
        """Los corredores nombran la falla como MÓDULO (`tests.test_cosa`) y la tarea declara
        su test como RUTA (`tests/test_cosa.py`). Comparar la ruta cruda marcaba como «no
        explicada» justo al test en vuelo que la explica, o sea un aviso que grita en cada
        etapa tests-first: exactamente cuando hay que poder creerle."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        r = correr(f'bash "{SCRIPTS}/estado.sh"', p.dir, PROYECTO="proyecto")
        self.assertIn("tests/test_cosa.py ← T01, pendiente", r.stdout,
                      f"el test en vuelo se tiene que listar:\n{r.stdout}")
        self.assertIn("el rojo es POR DISEÑO", r.stdout,
                      f"y su propia falla la tiene que explicar él:\n{r.stdout}")
        self.assertNotIn("NO las explica ningún test en vuelo", r.stdout,
                         f"no puede gritar contra el test que sí la explica:\n{r.stdout}")

    def test_un_plan_con_todo_hecho_cierra_limpio_y_no_aborta(self):
        """En bash 3.2 —el que trae macOS— expandir un array VACÍO con `set -u` no imprime
        mal: **aborta el script** (`a[@]: unbound variable`). La guardia de salteo recibe las
        etapas como argumentos, así que un plan sin etapas pendientes pasa por esa expansión.
        Hoy no se dispara porque un `exit 0` anterior lo intercepta, pero la garantía es
        incidental: alcanza con mover una línea. Esto prueba la propiedad, no la sintaxis."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        p.escribir_tarea("T01", "src/cosa.py", estado="✅ hecha")
        pl = p.dir / "PLAN.md"
        pl.write_text(pl.read_text().replace("| pendiente |", "| ✅ hecha |"))
        p.git("add -A"); p.git("commit -qm hecha")
        r = correr(f'bash "{SCRIPTS}/correr-plan.sh"', p.dir, PROYECTO="proyecto")
        self.assertEqual(r.returncode, 0, f"tiene que cerrar limpio:\n{r.stdout}\n{r.stderr}")
        self.assertIn("no hay nada que lanzar", r.stdout,
                      f"y decirlo, no morir con «unbound variable»:\n{r.stdout}\n{r.stderr}")
        self.assertNotIn("unbound variable", r.stderr, r.stderr)

    # ── El gate corrido como el método le pide al agente ───────────────────────────────

    def test_el_gate_corrido_a_mano_no_muere_con_unbound_variable(self):
        """**El defecto más caro que encontramos, y vivía a la vista.** `AGENTS.md` le dice al
        agente «al terminar corré `bash scripts/gate.sh`», o sea SIN `TAREA` en el entorno. Con
        `set -u`, `"tareas/${TAREA}"-*.md` en `test_de_la_tarea` aborta el script:
        `gate.sh: line 131: TAREA: unbound variable`. El agente ve «✗ la suite está en rojo»
        sin ninguna causa —porque el gate murió antes de poder decir cuál— e itera contra eso
        hasta agotar el presupuesto.

        Medido en vivo el 2026-10-20, en T05a: el agente escribió su test (172 líneas) y su
        implementación (78), corrió la suite —7 passed—, corrió el gate, se topó con esto, y
        quemó los 1200 s enteros dos veces. El método lo anotó como «el agente no respondió:
        límite total», que su propia documentación interpreta como «habla de la TAREA, no del
        modelo». **No hablaba de la tarea: hablaba de un gate que no arranca.**

        Y no se veía desde acá porque todo el resto del método invoca el gate con
        `TAREA=` —definida y vacía, que `set -u` acepta—: `estado.sh`, `integrar.sh`, el
        runner y esta suite. La única invocación sin definirla es la que hace el agente, que
        es la única que nadie probaba. Es la decimoséptima vez que aparece la misma forma: el
        camino que no se ejercita es el que falla.
        """
        p = Proyecto()
        self.addCleanup(p.tirar)
        p.implementar()
        for env, nombre in ((None, "sin TAREA en el entorno"), ("", "con TAREA vacía"),
                            ("T01", "en modo tarea")):
            with self.subTest(caso=nombre):
                if env is None:
                    r = correr("env -u TAREA bash scripts/gate.sh", p.dir)
                else:
                    r = correr("bash scripts/gate.sh", p.dir, TAREA=env)
                self.assertNotIn("unbound variable", r.stdout + r.stderr,
                                 f"el gate se muere antes de poder juzgar ({nombre}):\n"
                                 f"{r.stdout[-800:]}\n{r.stderr[-400:]}")
                # Y tiene que llegar a dar un veredicto, no morir en el camino.
                self.assertRegex(r.stdout, r"GATE (VERDE|ROJO)",
                                 f"no llegó a un veredicto ({nombre}):\n{r.stdout[-800:]}")

    # ── El detalle de los mutantes, que se destruía ────────────────────────────────────

    def test_el_sobreviviente_sale_con_el_marcador_que_el_consumidor_busca(self):
        """`escribir-tests.sh` extrae los sobrevivientes con `grep '→'` para ponerlos en el
        mensaje que el agente lee en su reintento, y `mutar.py` los imprimía SIN flecha. La
        extracción salía vacía en todas las corridas de la historia, y el reintento iba a
        ciegas: es por eso que T05a llegó a punto muerto el 2026-10-20 —«sobreviven mutantes»
        dos veces, sin un solo dato— después de que el arreglo anterior (una sola invocación
        de `mutar.py`) ya hubiera descartado la otra causa.

        Cuarta vez que el extractor busca una forma que el productor no emite: el ✗ del gate,
        las fallas de vitest, el TODO, y esto. Los dos lados viven en archivos distintos y
        nadie los lee juntos, así que el test tiene que leerlos por los dos."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-mut3-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "scripts").mkdir()
        shutil.copy(PLANTILLAS / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "app").mkdir()
        (d / "app" / "__init__.py").touch()
        # Una función con comparación y asignación: `mutar.py` marca como «árido» —y con
        # razón— todo cuerpo cuyas hojas son sólo `return`, así que un `return a + b` no
        # produce mutantes y el caso no mediría nada. Lo descubrí escribiendo este test.
        (d / "app" / "m.py").write_text(
            "def clasificar(n):\n    return 'bajo'\n")
        (d / "tests").mkdir()
        (d / "tests" / "__init__.py").touch()
        # Un test que CUBRE la línea y no verifica el comportamiento: el caso exacto.
        (d / "tests" / "test_m.py").write_text(
            "import unittest\nfrom app.m import clasificar\n\n"
            "class TestM(unittest.TestCase):\n"
            "    def test_devuelve_un_texto(self):\n"
            "        self.assertIsInstance(clasificar(5), str)\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        (d / "app" / "m.py").write_text(
            "def clasificar(n):\n"
            "    etiqueta = 'bajo'\n"
            "    if n > 10:\n"
            "        etiqueta = 'alto'\n"
            "    return etiqueta\n")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "impl"], cwd=d, check=True, capture_output=True)
        r = correr(f'BASE=HEAD~1 CODIGO=app '
                   f'SUITE=\'python3 -m unittest tests.test_m -q\' '
                   f'python3 "{SCRIPTS}/mutar.py"', d)
        # 1 o 3, y lo que este test mide es el MARCADOR, no cuál de los dos. Fijaba el 1 y
        # se puso rojo al partirse el veredicto en sus dos lecturas: su caso sintético tiene
        # el `etiqueta = 'alto'` dentro de un `if n > 10:` que este test nunca alcanza, así
        # que el 3 —«la línea NO se ejecuta»— es el diagnóstico correcto. La aserción era más
        # angosta que su sujeto: clavaba un código cuando lo que vigila es que el detalle
        # llegue al reintento.
        self.assertIn(r.returncode, (1, 3),
                      f"un test que no verifica comportamiento deja mutantes vivos:\n{r.stdout}")
        self.assertIn("→", r.stdout,
                      f"sin el marcador, `escribir-tests.sh` extrae un detalle VACÍO y el "
                      f"reintento va a ciegas:\n{r.stdout}")
        # Y el marcador tiene que llevar el DATO, no sólo estar.
        flechas = [l for l in r.stdout.split("\n") if "→" in l]
        self.assertRegex(flechas[0], r"app/m\.py:\d+",
                         f"el sobreviviente se nombra con archivo y línea: {flechas}")
        # Y el consumidor tiene que seguir buscando lo que el productor emite.
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertIn("""grep '→'""", s,
                      "si cambia el extractor, este test tiene que enterarse")

    def test_el_paso_de_mutantes_no_descarta_su_propia_evidencia(self):
        """En la rama de falla, `SALIDA_MUT` no se imprimía —sólo el extracto—, así que cuando
        la extracción fallaba la evidencia no quedaba en ninguna parte: ni el agente ni la
        persona podían saber qué sobrevivió, y el aviso mandaba a mirar un log donde no
        estaba. La rama del ⊘, doce líneas más arriba, sí la imprimía. Un chequeo que descarta
        su propia evidencia no se puede auditar."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        i = s.index('malo "sobreviven mutantes')
        fin = s.index("# 4. El BRAZO NULO", i)
        self.assertIn('printf \'%s\\n\' "$SALIDA_MUT"', s[i:fin],
                      "la rama de falla tiene que dejar la salida completa en el log")

    # ── La etapa de tests corría sin línea base ────────────────────────────────────────

    def test_la_etapa_de_tests_fija_la_base_igual_que_la_de_implementacion(self):
        """**La explicación completa del punto muerto de T05a, y es del método.**

        `correr-tarea.sh` escribe `.base-ref` y `.tests-base` antes de lanzar al agente, y su
        propio comentario dice por qué: «el método es tests-first, al empezar la etapa el
        tronco tiene los tests de todas sus tareas y la implementación de ninguna, así que la
        suite no puede estar verde; **sin esta lista el gate de cada tarea la vería roja por
        los tests de sus hermanas y ninguna podría cerrar**».

        `escribir-tests.sh` no escribía ninguna de las dos. Medido el 2026-10-20: `AGENTS.md`
        manda correr el gate, el gate del worktree de tests no tenía línea base, las 3 fallas
        preexistentes del tronco —de T26 y T04b, ya mergeadas, por `CR_CONN_HOST_ERROR`— se
        le cobraban a la tarea, y el veredicto quedaba INSATISFACIBLE. El agente escribía su
        test y su implementación, el gate le decía «la suite está en rojo», e iteraba hasta
        agotar los 1200 s. Tres corridas, seis intentos, tres puntos muertos, todos
        informados como «el agente trabajó y no terminó: habla de la TAREA».

        Quinta vez en el día que el arreglo vive en un hermano y no en el otro."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        i = s.index('worktree add')
        j = s.index("opencode run", i)
        bloque = s[i:j]
        self.assertIn(".base-ref", bloque,
                      "la base del diff se fija ANTES de que el agente toque nada")
        self.assertIn(".tests-base", bloque,
                      "y la línea base de tests también, o el gate le cobra a la tarea los "
                      "tests rojos de sus hermanas")
        self.assertIn("correr-suite.sh --fallas", bloque,
                      "la línea base sale del MISMO comando que usa el resto del método")
        # Y lo mismo que hace su hermano, con el mismo comando: una sola forma.
        otro = (SCRIPTS / "correr-tarea.sh").read_text()
        for pieza in ("rev-parse HEAD", "correr-suite.sh --fallas"):
            self.assertIn(pieza, otro, f"cambió el hermano: revisá que sigan iguales ({pieza})")

    def test_la_suite_roja_muestra_las_fallas_y_no_las_ultimas_lineas(self):
        """`echo "$SALIDA" | tail -15` supone que las fallas están al FINAL. Con una suite de
        dos mitades la que falla puede ser la primera: medido el 2026-10-20, el backend falló
        3 tests y el frontend pasó 27, el tail cayó entero dentro del frontend, y el agente
        leyó «✗ la suite está en rojo» seguido de «Tests 27 passed (27)» **sin una sola falla
        a la vista**. Un informe que nombra una falla y muestra sólo aprobados es peor que no
        mostrar nada: el agente itera contra un veredicto que su propia evidencia contradice.
        """
        for g in (PLANTILLAS / "gate.sh",
                  RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                  RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            with self.subTest(gate=g.parent.parent.name):
                s = g.read_text()
                i = s.index('rojo "la suite está en rojo"')
                fin = s.index("esac", i)
                bloque = s[i:fin]
                self.assertIn("correr-suite.sh --fallas", bloque,
                              "las fallas se piden al corredor, no se adivinan de la cola")
                self.assertIn("⊘", bloque,
                              "y si el corredor no lista ninguna, eso se declara: es un "
                              "desacuerdo entre el corredor y el gate, no un pase")

    # ── La sonda de plataforma vs. el arranque en frío ─────────────────────────────────

    def servidor_lento(self, demora):
        """Un endpoint que tarda `demora` segundos en contestar 200, como un modelo que
        arranca en frío."""
        import http.server, threading
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                time.sleep(demora)
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                except (BrokenPipeError, ConnectionResetError):
                    # best-effort: el caso impaciente CORTA la conexión a propósito, así que
                    # esta escritura falla por diseño. Sin atraparla, `http.server` imprime
                    # un traceback en medio de la suite, y un traceback de ruido tapa las
                    # fallas de verdad — que es lo que la suite existe para mostrar.
                    pass
            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        # Los dos, y en este orden: `shutdown` para el bucle, `server_close` para el socket.
        # Sin el segundo la suite deja un ResourceWarning por cada corrida del test.
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def test_la_sonda_le_da_al_modelo_el_tiempo_que_tarda_en_arrancar(self):
        """Con `curl -m 45` la sonda no sobrevivía al arranque de un modelo DESALOJADO
        —medido con `oc --warm`: 91, 97 y 106 s— así que devolvía «HTTP 000» y el runner
        abortaba el plan entero con «la plataforma de modelos no responde». Era falso: la
        plataforma contestaba 200 a otros modelos en 13 s, y el propio ejecutor contestó 200
        en 41,5 s en cuanto unos pedidos lo arrancaron. Nos bloqueó tres lanzamientos el
        2026-10-20, y me llevó a culpar primero al `nohup` y después a la ejecución en
        segundo plano: las dos veces mal, porque el mensaje nombraba al sujeto equivocado.

        Es la misma regla que el vigilante de inactividad ya tenía escrita: **un vigilante
        tiene que perder la carrera contra el error que la herramienta vigilada sabe
        informar.** Si corta antes, no observa el sistema: lo fabrica."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sonda-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text('{"provider":{"colabhive":{"models":{"m-sonda":{}}}}}')
        base = self.servidor_lento(2)
        def sonda(paciencia):
            return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                          f'ARRANQUE_FRIO={paciencia} COLABHIVE_BASE_URL="{base}" '
                          f'COLABHIVE_API_KEY=x MODELO_SONDA=m-sonda CONFIG_OC="{cfg}" '
                          f'plataforma_responde', RAIZ)
        impaciente = sonda(1)
        self.assertNotEqual(impaciente.returncode, 0,
                            "con menos paciencia que el arranque, la sonda tiene que fallar "
                            "(si no, este test no prueba que la use)")
        self.assertIn("000", impaciente.stderr,
                      f"y el 000 es «ni contestó», no «contestó mal»:\n{impaciente.stderr}")
        self.assertIn("reintentá una vez", impaciente.stderr,
                      "y el mensaje tiene que decir que el pedido pudo haber arrancado el "
                      "modelo, en vez de declarar la plataforma caída")
        paciente = sonda(20)
        self.assertEqual(paciente.returncode, 0,
                         f"con la paciencia suficiente tiene que pasar:\n{paciente.stderr}")

    def test_el_arranque_en_frio_se_declara_en_un_solo_lugar(self):
        """El presupuesto del calentador y la paciencia de la sonda son el MISMO número —
        cuánto tarda un modelo desalojado en levantarse— y estaban escritos dos veces: 240 en
        `con_limite 240 oc --warm` y 45 en el `curl -m 45`. Dos copias del mismo número es
        tenerlo mal una vez."""
        c = (SCRIPTS / "_comun.sh").read_text()
        self.assertIn(': "${ARRANQUE_FRIO:=', c, "el número se declara una vez, con su medición")
        self.assertIn('curl -s -m "$ARRANQUE_FRIO"', c, "la sonda lo usa")
        t = (SCRIPTS / "correr-todo.sh").read_text()
        self.assertIn('con_limite "$ARRANQUE_FRIO" oc --warm', t, "y el calentador también")
        self.assertNotRegex(c, r"curl -s -m 45", "no puede quedar el número viejo")

    def test_una_anotacion_de_tipo_no_es_un_mutante_que_un_test_pueda_matar(self):
        """`dict | None` es un `BinOp(BitOr)` en el árbol, así que entraba como «cambiar el
        operador aritmético» y producía un mutante **inmatable**: ningún test observa el tipo
        declarado, así que el mutante sobrevive por construcción.

        El efecto: toda tarea cuya implementación sea un archivo NUEVO —donde el diff cubre
        también la línea de la firma— con un tipo unión moderno falla el chequeo de mutación
        para siempre. Es lo que dejó a T05a en punto muerto cuatro corridas seguidas, con un
        veredicto correcto en su forma («el test cubre las líneas y no verifica su
        comportamiento») y falso en su contenido. Sólo se pudo ver después de arreglar el
        marcador `→`, porque hasta entonces el mensaje no decía QUÉ había sobrevivido.

        El brazo nulo de este arreglo es el test de arriba: un test que de verdad no verifica
        comportamiento tiene que seguir dejando mutantes vivos."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-anot-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        for sub in ("app", "tests"):
            (d / sub).mkdir()
            (d / sub / "__init__.py").touch()
        (d / "app" / "otro.py").write_text("x = 1\n")
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", *cmd], cwd=d, check=True, capture_output=True)
        # Archivo NUEVO: el diff cubre la firma, igual que en una tarea real.
        (d / "app" / "m.py").write_text(
            "def buscar(id: int) -> dict | None:\n"
            "    tabla = {1: 'uno'}\n"
            "    if id in tabla:\n"
            "        return {'id': id, 'v': tabla[id]}\n"
            "    return None\n")
        # Un test que SÍ verifica comportamiento, en los dos caminos y con valores reales.
        (d / "tests" / "test_m.py").write_text(
            "import unittest\nfrom app.m import buscar\n\n"
            "class TestM(unittest.TestCase):\n"
            "    def test_encuentra(self):\n"
            "        self.assertEqual(buscar(1)['v'], 'uno')\n"
            "    def test_no_encuentra(self):\n"
            "        self.assertIsNone(buscar(99))\n")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "nuevo"], cwd=d, check=True, capture_output=True)
        r = correr(f'BASE=HEAD~1 CODIGO=app '
                   f'SUITE=\'python3 -m unittest tests.test_m -q\' '
                   f'python3 "{SCRIPTS}/mutar.py"', d)
        self.assertEqual(r.returncode, 0,
                         f"un test que verifica comportamiento no puede fallar por una "
                         f"anotación de tipo:\n{r.stdout}")
        self.assertNotIn("-> dict | None", r.stdout,
                         f"la firma no es un candidato a mutar:\n{r.stdout}")
        # Y el chequeo tiene que seguir mutando lo que sí es código.
        self.assertRegex(r.stdout, r"[1-9][0-9]* mutante\(s\) probados",
                         f"si no mutó nada, la exclusión se comió el chequeo:\n{r.stdout}")

    def servidor_que_falla_las_primeras(self, fallas, codigo=502):
        """Un endpoint que contesta `codigo` las primeras `fallas` veces y 200 después:
        una plataforma intermitente, que es la que tenemos."""
        import http.server, threading
        estado = {"n": 0}
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                estado["n"] += 1
                try:
                    if estado["n"] <= fallas:
                        self.send_response(codigo)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                    else:
                        self.send_response(200)
                        self.send_header("Content-Length", "2")
                        self.end_headers()
                        self.wfile.write(b"{}")
                except (BrokenPipeError, ConnectionResetError):
                    pass   # best-effort: el cliente puede haber cortado
            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1", estado

    def test_un_502_transitorio_no_declara_la_plataforma_caida(self):
        """Una muestra puntual de un servicio intermitente no alcanza para declararlo caído.
        El 2026-10-21 un 502 abortó un plan de 7 etapas y dos minutos después el mismo pedido
        —con y sin herramientas— contestaba 200. El costo de reintentar son segundos; el de
        un aborto falso es un lanzamiento entero y un diagnóstico que apunta a la plataforma.

        Y no puede tapar una caída real: si todas las muestras fallan, el veredicto es el
        mismo, y la SECUENCIA de códigos se informa siempre — «502 200» y «502 502 502» dicen
        cosas distintas y quien decide necesita esa diferencia."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-502-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text('{"provider":{"colabhive":{"models":{"m-sonda":{}}}}}')

        def sonda(base):
            return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                          f'COLABHIVE_BASE_URL="{base}" COLABHIVE_API_KEY=x '
                          f'MODELO_SONDA=m-sonda CONFIG_OC="{cfg}" plataforma_responde', RAIZ)

        base, estado = self.servidor_que_falla_las_primeras(1)
        r = sonda(base)
        self.assertEqual(r.returncode, 0,
                         f"un 502 y después 200 es una plataforma intermitente, no caída:"
                         f"\n{r.stderr}")
        self.assertEqual(estado["n"], 2, "tiene que haber reintentado, no adivinado")
        self.assertIn("intermitente", r.stderr,
                      f"y hay que decir que lo está, porque los tiempos no son comparables:"
                      f"\n{r.stderr}")

        # Caída de verdad: el veredicto no se ablanda.
        base2, estado2 = self.servidor_que_falla_las_primeras(99)
        r2 = sonda(base2)
        self.assertNotEqual(r2.returncode, 0, "tres fallas son una caída, y se declara")
        self.assertEqual(estado2["n"], 3, "no más de tres muestras: no se insiste gratis")
        self.assertIn("502 502 502", r2.stderr,
                      f"la secuencia completa, no sólo la última:\n{r2.stderr}")

    # ── Un error de plataforma no es una falla de la tarea ─────────────────────────────

    def test_la_etapa_de_tests_reconoce_un_error_de_plataforma(self):
        """`error_del_agente` aparecía 2 veces en `correr-tarea.sh` y **0** en
        `escribir-tests.sh`, así que un `{"message":"memory_session_expired",
        "type":"api_error"}` se informaba como «✗ no escribió backend/tests/X.py declarando
        TestX»: cierto en la letra y falso en el sujeto. La tarea gastaba un reintento por una
        falla que no era suya y el registro anotaba un rojo del modelo.

        Medido el 2026-10-21 en T05a: el agente venía leyendo archivos con normalidad y la API
        le cortó la sesión. Misma familia que mató T11 y T20 el 2026-10-19 con
        `memory_delivery_unavailable` —el detector ya reconoce el SOBRE `api_error` entero, no
        una lista de mensajes, justo por eso—. Séptima vez en el día que el arreglo vive en un
        hermano y no en el otro, así que el test mira a los dos."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertIn("error_del_agente", s,
                      "la etapa de tests tiene que clasificar los errores de plataforma")
        # Y con el presupuesto generoso, no con el de «límite total», que es el único que
        # habla de la tarea.
        i = s.index('PLATAFORMA_CORTO:-0')
        bloque = s[i:i + 900]
        self.assertIn("no cuenta contra la tarea", bloque,
                      "un corte de plataforma no puede gastar el presupuesto de la tarea")
        self.assertIn('MOTIVO_TESTS=""', bloque,
                      "y el reintento no puede recibir «un intento anterior falló así» con "
                      "un motivo que el enunciado no puede arreglar")
        # El detector, por conducta: reconoce el sobre, no el mensaje.
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-plat-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        for msg in ("memory_session_expired", "memory_delivery_unavailable",
                    "un_mensaje_que_nadie_enumero_todavia"):
            with self.subTest(mensaje=msg):
                log = d / "t.log"
                log.write_text('=== T05a\n> ejecutor\n→ Read tareas\n'
                               'Error: {"message":"%s","type":"api_error"}\n'
                               '=== rc=1\n=== fin T05a · hoy\n' % msg)
                r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                           f'error_del_agente "{log}"', RAIZ)
                self.assertIn(msg, r.stdout,
                              f"el sobre api_error es lo que identifica a la plataforma, no "
                              f"una lista de mensajes conocidos:\n{r.stdout}")

    # ── El guardia del instrumento miraba cuando ya era tarde ──────────────────────────

    def test_el_instrumento_se_verifica_antes_de_cada_intento(self):
        """El guardia comparaba la huella de `scripts/` **en el borde de etapa**, que es el
        único momento en que ya es tarde: entre dos bordes pueden pasar cuarenta minutos y
        seis intentos, y cualquier edición en esa ventana queda fuera de su alcance.

        Lo demostré rompiéndolo. El 2026-10-21 edité `escribir-tests.sh` dos veces con un
        intento en curso —con la regla a la vista, y después de haberla citado cuatro veces
        en la misma sesión— y el guardia no se enteró. Es el mismo problema que
        `huella_enunciado` ya resuelve bien y en el mismo archivo: se compara la huella del
        sujeto antes de CADA intento, no una vez por tanda."""
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                   f'instrumento_se_movio; echo "primera=$?"; '
                   f'instrumento_se_movio; echo "igual=$?"; '
                   f'HUELLA_INSTRUMENTO=distinta instrumento_se_movio 2>/dev/null; '
                   f'echo "cambiada=$?"', RAIZ)
        self.assertIn("primera=1", r.stdout,
                      f"la primera llamada FIJA la huella y no acusa a nadie:\n{r.stdout}")
        self.assertIn("igual=1", r.stdout,
                      f"sin cambios no se movió:\n{r.stdout}")
        self.assertIn("cambiada=0", r.stdout,
                      f"con el instrumento cambiado tiene que avisar:\n{r.stdout}")
        # Y los dos que iteran por intento lo tienen que llamar ANTES de lanzar al agente.
        for ruta, lanza in (("escribir-tests.sh", "opencode run"),
                            ("correr-tarea.sh", "opencode run")):
            with self.subTest(script=ruta):
                s = (SCRIPTS / ruta).read_text()
                self.assertIn("instrumento_se_movio", s,
                              f"{ruta} gasta intentos: tiene que verificar el instrumento")
                self.assertLess(s.index("instrumento_se_movio"), s.index(lanza),
                                "y antes de lanzar al agente, no después")
        # Una sola copia de la huella, en el método.
        self.assertIn("huella_scripts()", (SCRIPTS / "_comun.sh").read_text(),
                      "la huella vive en el método")
        self.assertNotIn("huella_scripts() {", (SCRIPTS / "correr-todo.sh").read_text(),
                         "y no duplicada en el runner")

    def test_el_corte_por_instrumento_no_sigue_con_la_tarea_siguiente(self):
        """Con un `break` simple, el bucle pasaba a la tarea siguiente: lo contrario de lo que
        dice el mensaje («relanzá la corrida desde cero») y, peor, lo que viniera después se
        juzgaría con el instrumento nuevo — que es justo el defecto que esto ataja."""
        s = (SCRIPTS / "escribir-tests.sh").read_text()
        self.assertIn("instrumento_se_movio", s,
                      "sin el guardia no hay nada que cortar: ver el test de arriba")
        i = s.index("instrumento_se_movio")
        self.assertIn("break 2", s[i:i + 400],
                      "tiene que salir del bucle de intentos Y del de tareas")
        t = (SCRIPTS / "correr-tarea.sh").read_text()
        j = t.index("instrumento_se_movio")
        self.assertIn("exit 1", t[j:j + 400],
                      "y en correr-tarea.sh, que corre en una subshell `( ) &`, un `break` "
                      "no rompe nada y sigue como si el chequeo hubiera pasado")

    # ── El contexto declarado es instrumento y no estaba en ninguna huella ─────────────

    def cfg_con(self, d, contextos, extra=None):
        """Una config de opencode con los contextos dados: {id: context}."""
        cfg = d / "opencode.json"
        modelos = {mid: {"name": mid, "limit": {"context": ctx}}
                   for mid, ctx in contextos.items()}
        doc = {"provider": {"colabhive": {"models": modelos}}}
        if extra:
            doc.update(extra)
        cfg.write_text(json.dumps(doc))
        return cfg

    def huella_ctx(self, cfg):
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; '
                      f'CONFIG_OC="{cfg}" huella_contextos', RAIZ).stdout.strip()

    def test_la_huella_de_contextos_se_mueve_con_el_contexto_y_no_con_el_tema(self):
        """`huella_scripts` cubre `scripts/`, pero el `limit.context` de cada modelo vive en
        la config de opencode, AFUERA del repo: cambiarlo no movía ninguna huella y las filas
        de antes y después quedaban comparables sin serlo.

        Medido el 2026-10-21: el ejecutor venía declarado con 32000 cuando la plataforma le
        sirve 241000 —ocho veces menos— y al corregirlo nada dijo que las filas anteriores
        dejaban de ser comparables. Un cambio de contexto cambia lo que el sujeto PUEDE
        hacer: es la misma clase de cosa que cambiar un script.

        Y la otra mitad del requisito, que es la que vuelve usable a una huella: no se mueve
        por cosas que no afectan al sujeto. Se hashea sólo `{id: limit.context}`, no el
        archivo, porque la config lleva tema, atajos y claves."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ctx-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)

        base = self.huella_ctx(self.cfg_con(d, {"ejecutor": 32000, "orq": 69000}))
        self.assertRegex(base, r"^[0-9a-f]{7}$", f"tiene que ser un hash: {base}")

        # El caso real: 32000 -> 241000.
        movido = self.huella_ctx(self.cfg_con(d, {"ejecutor": 241000, "orq": 69000}))
        self.assertNotEqual(base, movido,
                            "cambiar el contexto declarado TIENE que mover la huella")

        # Lo mismo escrito distinto no es un cambio del sujeto.
        igual = self.huella_ctx(self.cfg_con(d, {"orq": 69000, "ejecutor": 32000}))
        self.assertEqual(base, igual, "el orden de las claves no es un cambio de contexto")

        # Y un cambio que no toca al sujeto no puede invalidar mediciones.
        con_tema = self.huella_ctx(self.cfg_con(
            d, {"ejecutor": 32000, "orq": 69000},
            extra={"theme": "dracula", "keybinds": {"leader": "ctrl+x"}}))
        self.assertEqual(base, con_tema,
                         "una huella que se mueve con el tema es una huella que nadie usa")

    def test_el_registro_anota_los_contextos_de_cada_fila(self):
        """Las filas viejas quedan con el campo VACÍO, que es lo honesto: no dice «el mismo
        contexto», dice «no se registró». No hay forma de recuperar hacia atrás con qué
        contexto corrió una fila que no lo anotó."""
        s = (SCRIPTS / "_comun.sh").read_text()
        i = s.index('local ENCABEZADO="fecha,proyecto')
        encabezado = s[i:s.index("\n", i)]
        self.assertIn("contextos", encabezado,
                      f"el registro tiene que anotar los contextos:\n{encabezado}")
        # Y la fila escrita tiene que llevar el campo, no sólo el nombre: una columna que
        # nadie escribe es exactamente la columna `motivo` que no se leyó nunca.
        fila = [l for l in s.split("\n") if l.strip().startswith('echo "$(date -u +%FT%TZ)')]
        self.assertTrue(fila, "no encontré la línea que escribe la fila")
        self.assertIn("$contextos", fila[0],
                      f"la columna se nombra pero no se escribe:\n{fila[0]}")
        self.assertEqual(encabezado.count(","), fila[0].count(","),
                         f"el encabezado y la fila tienen que tener el mismo ancho:\n"
                         f"{encabezado}\n{fila[0]}")

    # ── La ruta del enunciado que se le entrega al agente ──────────────────────────────

    def test_el_enunciado_va_con_ruta_absoluta_dentro_del_worktree(self):
        """De las tres formas de nombrarle el enunciado al agente, dos fallan:

          · absoluta del repo ORIGINAL -> OpenCode la ve como `external_directory` y la
            rechaza por permisos. Está escrito en `correr-tarea.sh` desde hace tiempo y hoy
            se vio en el log: «permission requested: external_directory (/Users/jose/*);
            auto-rejecting».
          · relativa (`tareas/X.md`)   -> OpenCode la resuelve contra la RAÍZ DEL WORKTREE y
            no contra el `cd` del bloque que lanza al agente, y ahí no hay `tareas/`: el
            proyecto vive en `$wt/$PROYECTO`.
          · absoluta del WORKTREE      -> se lee.

        Cadáver del 2026-10-21: «Read /Users/jose/tests-T05a/tareas/T05a-avisos-datos.md
        failed: File not found» con el archivo presente en
        `/Users/jose/tests-T05a/ejemplo-clasificados/tareas/`. Que la absoluta del worktree
        sí se puede leer lo prueba ese mismo log: falló con «File not found» y NO con un
        rechazo de permisos.

        Y lo que más dice del repo: `escribir-tests.sh` ya calculaba la ruta correcta tres
        líneas antes —para `huella_enunciado`— y al agente le entregaba la otra."""
        for nombre in ("escribir-tests.sh", "correr-tarea.sh"):
            with self.subTest(script=nombre):
                s = (SCRIPTS / nombre).read_text()
                # La forma correcta tiene que estar en el script: en el prompt mismo
                # (escribir-tests.sh) o en la variable que el prompt usa (correr-tarea.sh,
                # que la arma en `archivo=`). Las dos cuentan: lo que importa es qué ruta
                # termina viendo el agente.
                self.assertIn("$wt/$PROYECTO/tareas/", s,
                              f"{nombre}: el enunciado tiene que ir absoluto y dentro del "
                              f"worktree")
                # Y la forma vieja no puede estar: `tareas/X.md` suelta se resuelve contra la
                # raíz del worktree, donde no hay `tareas/`.
                self.assertNotIn('archivo="tareas/$(basename', s,
                                 f"{nombre}: ésa es la ruta relativa que mató a T05a")
                self.assertNotRegex(
                    s, r"Leé tareas/\$\(basename",
                    f"{nombre}: ésa es la ruta relativa que mató a T05a")

    def test_una_ruta_absoluta_del_worktree_resuelve_desde_las_dos_raices(self):
        """La propiedad por la que se eligió esa forma: no depende de cuál de las dos raíces
        use OpenCode para resolver. El 2026-10-21 el mismo prompt con ruta relativa anduvo en
        un intento y falló en el siguiente, así que esa resolución no es estable y no se
        puede construir nada encima."""
        wt = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ruta-")).resolve()
        self.addCleanup(shutil.rmtree, str(wt), True)
        proyecto = "ejemplo-clasificados"
        (wt / proyecto / "tareas").mkdir(parents=True)
        tarea = wt / proyecto / "tareas" / "T05a-avisos-datos.md"
        tarea.write_text("# T05a\n")

        absoluta = f"{wt}/{proyecto}/tareas/T05a-avisos-datos.md"
        relativa = "tareas/T05a-avisos-datos.md"
        for raiz, etiqueta in ((wt, "raíz del worktree"),
                               (wt / proyecto, "directorio del proyecto")):
            with self.subTest(resuelve_desde=etiqueta):
                r = correr(f'[ -f "{absoluta}" ] && echo si || echo no', raiz)
                self.assertEqual("si", r.stdout.strip(),
                                 f"la absoluta tiene que resolver desde {etiqueta}")
        # Y la relativa, que es la que estaba, falla desde la raíz del worktree: es el
        # cadáver exacto.
        r = correr(f'[ -f "{relativa}" ] && echo si || echo no', wt)
        self.assertEqual("no", r.stdout.strip(),
                         "si esto diera «si», el defecto no sería lo que digo que es")


class TestUnErrorDeColeccionNoPuedeEsconderLaSuite(unittest.TestCase):
    """pytest, ante UN error de colección, no corre NINGÚN test: informa el error y nada más.

    En un método tests-first eso no es un caso raro, es el caso NORMAL: al empezar una etapa
    el tronco tiene los tests de todas las tareas y la implementación de ninguna, así que al
    menos un archivo no se puede importar. Resultado: la LÍNEA BASE venía truncada en todas
    las etapas, siempre.

    Cadáver del 2026-10-21, y es caro. La línea base de T05a decía, completa:

        ERROR backend/tests/test_ads_datos.py

    Cuando el agente implementó `ads.py` la colección pasó a funcionar y las 3 fallas
    preexistentes aparecieron por PRIMERA vez, así que el gate las leyó como nuevas y acusó a
    la tarea de «rompiste tests que andaban antes» — tests de registro de usuarios, que T05a
    no toca. Dos intentos, punto muerto y el plan detenido.

    Y por qué no se vio nunca: `unittest` NO trunca —informa el módulo roto y además los
    demás— y el otro proyecto de ejemplo usa unittest. El método se calibró contra él."""

    def proyecto_pytest(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-colec-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tests").mkdir()
        # Un test que falla de verdad, y otro que no se puede ni importar.
        (d / "tests" / "test_falla.py").write_text(
            "def test_suma():\n    assert 2 + 2 == 5\n")
        (d / "tests" / "test_sin_implementacion.py").write_text(
            "from app.todavia_no import nada\n\ndef test_algo():\n    assert nada\n")
        return d

    def py_con_pytest(self):
        for v in (RAIZ / "ejemplo-clasificados" / ".venv" / "bin" / "python",
                  pathlib.Path(sys.executable)):
            if v.exists() and subprocess.run(
                    [str(v), "-c", "import pytest"], capture_output=True).returncode == 0:
                return str(v)
        return None

    def test_pytest_sin_la_bandera_esconde_las_fallas_reales(self):
        py = self.py_con_pytest()
        if not py:
            self.skipTest("no hay un python con pytest disponible")
        d = self.proyecto_pytest()
        sin = subprocess.run([py, "-m", "pytest", "-q", "tests"],
                             cwd=str(d), capture_output=True, text=True)
        con = subprocess.run([py, "-m", "pytest", "-q",
                              "--continue-on-collection-errors", "tests"],
                             cwd=str(d), capture_output=True, text=True)
        # La falla real existe en los dos casos; sólo uno la informa.
        self.assertNotIn("test_suma", sin.stdout,
                         f"si pytest ya la informara, el defecto no sería lo que digo:\n"
                         f"{sin.stdout[-600:]}")
        self.assertIn("test_suma", con.stdout,
                      f"con la bandera, la falla real tiene que aparecer:\n"
                      f"{con.stdout[-600:]}")

    def test_el_corredor_del_proyecto_lleva_la_bandera(self):
        """El arreglo donde importa: el corredor que produce la línea base. Si alguna vez se
        saca, la línea base vuelve a mentir y el gate vuelve a acusar a la tarea."""
        encontrados = 0
        for ruta in sorted(RAIZ.glob("ejemplo-*/scripts/correr-suite.sh")):
            s = ruta.read_text()
            if "-m pytest" not in s:
                continue          # unittest no trunca: no necesita la bandera
            encontrados += 1
            with self.subTest(corredor=str(ruta.relative_to(RAIZ))):
                for linea in s.split("\n"):
                    if "-m pytest" in linea and not linea.strip().startswith("#"):
                        self.assertIn("--continue-on-collection-errors", linea,
                                      f"sin esto la línea base viene truncada:\n{linea}")
        self.assertGreater(encontrados, 0,
                           "ningún ejemplo usa pytest: este test no estaría midiendo nada")


class TestUnaTablaQueNadieCrea(unittest.TestCase):
    """`coherencia.py` cruzaba imports entre tareas y no mirabla el ESQUEMA. Cadáver del
    2026-10-21: `backend/app/datos/users_register.py` hace `INSERT INTO users` y la migración
    `001_initial.sql` crea `usuarios`. Esa tabla nunca existió, así que los tests de registro
    no podían pasar — y durante trece corridas el método culpó por eso a tareas que no tocan
    registro, hasta dejar el plan detenido.

    Es el mismo chequeo que el de imports en otra superficie: lo que el código consume contra
    lo que alguien provee. Y la decisión no es del método: o la migración crea la tabla, o el
    código usa la que existe, y eso lo resuelve quien planifica."""

    def proyecto(self, migracion=None, codigo=None):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-tabla-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-x.md").write_text(
            "# T01 — Una cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/x.py\n\n## Objetivo\n\nUna cosa.\n")
        (d / "app").mkdir()
        if migracion is not None:
            (d / "migraciones").mkdir()
            (d / "migraciones" / "001_initial.sql").write_text(migracion)
        if codigo is not None:
            (d / "app" / "datos.py").write_text(codigo)
        return d

    def correr(self, d):
        return correr(f'PROYECTO="{d}" python3 "{SCRIPTS}/coherencia.py"', RAIZ)

    def test_una_tabla_sin_migracion_es_rojo_con_el_candidato_parecido(self):
        d = self.proyecto(
            migracion="CREATE TABLE usuarios (id INT PRIMARY KEY, email VARCHAR(255));\n",
            codigo='def insertar(c, email):\n'
                   '    c.execute("INSERT INTO users (email) VALUES (%s)", (email,))\n')
        r = self.correr(d)
        self.assertEqual(1, r.returncode, f"tiene que ser rojo:\n{r.stdout}{r.stderr}")
        self.assertIn("`users`", r.stdout, f"tiene que nombrar la tabla:\n{r.stdout}")
        self.assertIn("usuarios", r.stdout,
                      f"y el candidato parecido, que es lo que quien planifica necesita:"
                      f"\n{r.stdout}")

    def test_una_clausula_de_columna_no_es_una_tabla(self):
        """El falso positivo que encontró el control contra los ejemplos:
        `actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` lleva
        la palabra UPDATE y no es una consulta. Un rojo apoyado en una palabra suelta no es
        mecánico: es un augurio, y éste decide si el plan arranca."""
        d = self.proyecto(
            migracion="CREATE TABLE usuarios (id INT PRIMARY KEY);\n",
            codigo="COLUMNAS = [\n"
                   "    'creado_en DATETIME DEFAULT CURRENT_TIMESTAMP',\n"
                   "    'actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP "
                   "ON UPDATE CURRENT_TIMESTAMP',\n"
                   "]\n")
        r = self.correr(d)
        self.assertNotIn("current_timestamp", r.stdout.lower(),
                         f"eso es una columna, no una tabla:\n{r.stdout}")
        self.assertEqual(0, r.returncode, f"y no puede reprobar el plan:\n{r.stdout}")

    def test_un_import_de_python_no_es_un_from_de_sql(self):
        """Por esto se leen sólo literales de cadena, con `ast`: un
        `from backend.app.datos import users` tiene la palabra `from` seguida de un nombre, y
        un regex plano sobre el archivo lo leería como SQL."""
        d = self.proyecto(
            migracion="CREATE TABLE usuarios (id INT PRIMARY KEY);\n",
            codigo="from app import otra_cosa\nfrom app.datos import tablas_raras\n\n"
                   "def f():\n    return otra_cosa, tablas_raras\n")
        r = self.correr(d)
        self.assertNotIn("otra_cosa", r.stdout, f"ése es un import:\n{r.stdout}")
        self.assertNotIn("tablas_raras", r.stdout, f"ése es un import:\n{r.stdout}")
        self.assertEqual(0, r.returncode, f"no hay nada que reprobar:\n{r.stdout}")

    def test_sin_migraciones_el_chequeo_no_opina(self):
        """Sin migraciones no hay con qué comparar. Un chequeo que no puede medir no opina:
        la misma regla que el método aplica a los corredores de tests que faltan."""
        d = self.proyecto(
            codigo='def leer(c):\n    c.execute("SELECT * FROM cualquier_cosa")\n')
        r = self.correr(d)
        self.assertNotIn("cualquier_cosa", r.stdout,
                         f"sin migraciones no se puede afirmar que falte:\n{r.stdout}")
        self.assertEqual(0, r.returncode, f"y no reprueba:\n{r.stdout}")

    def test_el_control_contra_los_dos_proyectos_de_ejemplo(self):
        """La práctica que este repo ya tiene escrita: todo chequeo nuevo se corre contra los
        dos ejemplos. El de pacman no tiene SQL, así que no puede encontrar nada — y si
        encuentra algo, el extractor está inventando."""
        pac = RAIZ / "ejemplo-pacman"
        if not (pac / "tareas").is_dir():
            self.skipTest("no está ejemplo-pacman")
        r = correr(f'PROYECTO=ejemplo-pacman python3 "{SCRIPTS}/coherencia.py"', RAIZ)
        self.assertNotIn("ninguna migración la crea", r.stdout,
                         f"un proyecto sin SQL no puede tener tablas faltantes:\n{r.stdout}")


class TestUnEnunciadoQueDaPorHechaUnaTabla(unittest.TestCase):
    """El cruce de esquema contra el CÓDIGO llega tarde por construcción: para poder hablar
    necesita que un agente haya escrito el código, y para entonces ya se gastó.

    Cadáver del 2026-10-19, medido el 21: el enunciado de T26 dice «almacene los datos en la
    tabla `users`» y la migración de otra tarea del mismo plan crea `usuarios`. El agente
    escribió `INSERT INTO users` porque se lo pidieron, el gate le dio VERDE —commit
    `d8eb1e3 "T26: gate verde"`— y dejó dos tests en rojo permanente con
    `Table 'clasificados.users' doesn't exist`. Esos dos tests después se leyeron como «la
    tarea rompió tests que andaban» y como línea base truncada: dos defectos más, buscando en
    el lugar equivocado una causa que estaba en una palabra del plan.

    El enunciado y las migraciones existen el día que se planifica. Contradecirse entre ellos
    es detectable ahí, con cero agentes gastados, y eso es lo que mide esta clase."""

    MIGRACION = "CREATE TABLE usuarios (id INT PRIMARY KEY, email VARCHAR(255));\n"

    def proyecto(self, enunciado, migracion=MIGRACION):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-enunciado-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T26-registro.md").write_text(
            "# T26 — Registro\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/x.py\n\n## Objetivo\n\n" + enunciado + "\n")
        (d / "app").mkdir()
        if migracion is not None:
            (d / "migraciones").mkdir()
            (d / "migraciones" / "001_initial.sql").write_text(migracion)
        return d

    def correr(self, d):
        return correr(f'PROYECTO="{d}" python3 "{SCRIPTS}/coherencia.py"', RAIZ)

    def test_el_enunciado_que_nombra_una_tabla_que_nadie_crea_es_rojo_sin_codigo(self):
        """Sin una línea de código en el proyecto: el rojo sale del plan contra la migración."""
        d = self.proyecto("Almacenar los datos en la tabla `users`.")
        r = self.correr(d)
        self.assertEqual(1, r.returncode, f"tiene que ser rojo:\n{r.stdout}{r.stderr}")
        self.assertIn("T26", r.stdout, f"y nombrar la TAREA, que es lo que se corrige:\n{r.stdout}")
        self.assertIn("usuarios", r.stdout, f"con el candidato parecido:\n{r.stdout}")

    def test_nombra_el_enunciado_y_no_al_agente(self):
        """El defecto más caro de estos días es cobrarle al sujeto equivocado. Acá el sujeto
        es el enunciado: el agente que escriba esa consulta va a estar obedeciendo."""
        d = self.proyecto("Almacenar los datos en la tabla `users`.")
        r = self.correr(d)
        self.assertIn("ENUNCIADO", r.stdout, f"tiene que decir dónde está el defecto:\n{r.stdout}")
        self.assertNotIn("el agente se equivocó", r.stdout)

    def test_un_from_de_python_en_el_enunciado_no_es_una_tabla(self):
        """El falso positivo que cometí escribiendo esto: `from fastapi import FastAPI` citado
        en un enunciado daba la tabla `fastapi`. Seis de siete hallazgos contra clasificados
        eran de esta forma, y es el MISMO falso positivo que coherencia.py ya documentaba del
        lado del código. Un rojo que decide si el plan arranca no puede apoyarse en una
        palabra suelta."""
        d = self.proyecto("Montar la app con `from fastapi import FastAPI` y "
                          "`from contextlib import asynccontextmanager`.")
        r = self.correr(d)
        self.assertEqual(0, r.returncode, f"no hay ninguna tabla acá:\n{r.stdout}{r.stderr}")
        for falsa in ("`fastapi`", "`contextlib`"):
            self.assertNotIn(falsa, r.stdout, f"{falsa} no es una tabla:\n{r.stdout}")

    def test_una_tabla_que_el_enunciado_promete_crear_no_es_un_hueco(self):
        """Guardia contra sobre-detección: si una tarea promete crear la tabla, el plan es
        coherente y el chequeo tiene que callarse. Sin esto, todo plan que cree su esquema por
        migración sería rojo el día uno."""
        d = self.proyecto("Crear la tabla `pagos` en una migración y guardar ahí los cobros.")
        r = self.correr(d)
        self.assertEqual(0, r.returncode,
                         f"la misma tarea promete crearla:\n{r.stdout}{r.stderr}")

    def test_sin_migraciones_no_opina(self):
        """La misma regla que el resto del método: un chequeo que no puede medir no opina. Un
        proyecto sin SQL no tiene con qué comparar, y un ⊘ no es un pase pero tampoco un rojo."""
        d = self.proyecto("Almacenar los datos en la tabla `users`.", migracion=None)
        r = self.correr(d)
        self.assertEqual(0, r.returncode, f"sin migraciones no hay con qué comparar:\n{r.stdout}")

    def test_el_control_contra_los_dos_proyectos_de_ejemplo(self):
        """El control mide que el chequeo NO INVENTE, no que encuentre cadáveres concretos.

        La primera versión exigía hallar `users` en T26 y `ads` en T28, que eran los dos casos
        reales del 2026-10-23. Cuando el método los arregló —los corrigieron dos modelos
        locales en dos segundos— este test se puso ROJO: ataba la suite a un estado
        transitorio del ejemplo, así que **castigaba el progreso**. Es el defecto que este
        repo ya tiene anotado —tests que miden la ubicación en vez de la propiedad— cometido
        en el test de control.

        La propiedad la miden los cinco tests de arriba, con proyectos temporales que
        contienen la contradicción a propósito. Acá sólo se verifica lo que no depende de
        cuándo se corra: que un proyecto sin SQL no produzca hallazgos de tabla, y que contra
        un proyecto real el chequeo termine sin reventar."""
        pac = RAIZ / "ejemplo-pacman"
        if (pac / "tareas").is_dir():
            r = correr(f'PROYECTO=ejemplo-pacman python3 "{SCRIPTS}/coherencia.py"', RAIZ)
            self.assertNotIn("da por hecha la tabla", r.stdout,
                             f"un proyecto sin SQL no puede tener tablas faltantes:\n{r.stdout}")
        cla = RAIZ / "ejemplo-clasificados"
        if (cla / "tareas").is_dir():
            r = correr(f'PROYECTO=ejemplo-clasificados python3 "{SCRIPTS}/coherencia.py"', RAIZ)
            self.assertIn(r.returncode, (0, 1),
                          f"contra un proyecto real tiene que dar veredicto, no reventar:"
                          f"\n{r.stdout}{r.stderr}")
            self.assertNotIn("Traceback", r.stdout + r.stderr,
                             f"y sin excepciones:\n{r.stdout}{r.stderr}")


class TestElPreflightTieneCaminoAlArquitecto(unittest.TestCase):
    """`coherencia.py` terminaba sus rojos con «Lo decide quien planifica» y `correr-todo.sh`
    hacía `exit 1`: un veredicto correcto que **paraba a esperar a una persona**. Es palabra
    por palabra el defecto que `replanificar.sh` corrigió del lado de las tareas, reaparecido
    en el chequeo más nuevo — y acá la persona que iba a inferir era quien escribe el método,
    que es exactamente lo que no tiene que pasar.

    Estos tests no miran el texto del script: le ponen un arquitecto falso en el PATH y miden
    qué hace con lo que escribe. El juez que importa es que el MISMO chequeo que encontró el
    problema sea el que acepta el arreglo."""

    def proyecto(self, enunciado):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-replan-coh-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T26-registro.md").write_text(
            "# T26 — Registro\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/x.py\n\n## Objetivo\n\n" + enunciado + "\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE usuarios (id INT PRIMARY KEY);\n")
        # El formato que `validar-plan.py` exige de verdad. La primera versión de este
        # andamio puso una tabla inventada de dos columnas, y el test «se acepta» falló con
        # «el plan dejó de validar»: estaba midiendo mi PLAN.md de juguete y no el script.
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T26 | Registro | — | `app/x.py` | pendiente |\n")
        return d

    def arquitecto_falso(self, d, guion):
        """Un `opencode` en el PATH que hace lo que diga `guion` sobre tareas/T26."""
        bin_ = d / ".bin"; bin_.mkdir()
        (bin_ / "opencode").write_text("#!/usr/bin/env bash\n" + guion + "\n")
        (bin_ / "opencode").chmod(0o755)
        return f'PATH="{bin_}:$PATH"'

    def correr_replan(self, d, guion):
        env = self.arquitecto_falso(d, guion)
        return correr(f'{env} PROYECTO=. LIMITE_AGENTE=60 '
                      f'bash "{SCRIPTS}/replanificar-coherencia.sh"', d)

    def test_si_el_arquitecto_no_resuelve_el_rojo_se_descarta_y_las_tareas_vuelven(self):
        """El juez es el preflight, no la buena voluntad del arquitecto. Y descartar tiene que
        DEJAR EL PLAN COMO ESTABA: un arreglo a medias en tareas/ es peor que ninguno, porque
        la corrida siguiente arranca sobre algo que nadie revisó."""
        d = self.proyecto("Guardar los datos en la tabla `users`.")
        antes = (d / "tareas" / "T26-registro.md").read_text()
        r = self.correr_replan(d, 'echo "ya lo pensé" >> tareas/T26-registro.md')
        self.assertNotEqual(0, r.returncode, f"no resolvió nada:\n{r.stdout}{r.stderr}")
        self.assertIn("preflight sigue en rojo", r.stdout + r.stderr,
                      f"y tiene que decir POR QUÉ se descarta:\n{r.stdout}{r.stderr}")
        self.assertEqual(antes, (d / "tareas" / "T26-registro.md").read_text(),
                         "la tarea tiene que quedar exactamente como estaba")

    def test_si_el_arquitecto_usa_la_tabla_que_existe_se_acepta(self):
        """La salida (a) del enunciado: que use el nombre que la migración ya crea."""
        d = self.proyecto("Guardar los datos en la tabla `users`.")
        r = self.correr_replan(
            d, "sed -i '' 's/tabla `users`/tabla `usuarios`/' tareas/T26-registro.md")
        self.assertEqual(0, r.returncode, f"el rojo desapareció:\n{r.stdout}{r.stderr}")
        self.assertIn("ya no se contradice", r.stdout, f"\n{r.stdout}")
        self.assertIn("usuarios", (d / "tareas" / "T26-registro.md").read_text())

    def test_un_arquitecto_que_no_escribe_nada_no_es_una_replanificacion(self):
        """El chequeo que a `replanificar.sh` le faltaba y costó dos verdes con cero líneas de
        diff: los jueces pasan trivialmente sobre un archivo intacto."""
        d = self.proyecto("Guardar los datos en la tabla `users`.")
        r = self.correr_replan(d, "echo 'leí todo y no escribí nada'")
        self.assertNotEqual(0, r.returncode, f"no ocurrió nada:\n{r.stdout}{r.stderr}")
        self.assertIn("no cambió nada", r.stdout + r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_no_puede_achicar_los_criterios_de_terminado(self):
        """Replanificar no es bajar la vara. El arquitecto podría hacer desaparecer el rojo
        borrando la tarea entera, y eso no es un arreglo."""
        d = self.proyecto("Guardar los datos en la tabla `users`.")
        r = self.correr_replan(
            d, "printf '# T26 — Registro\\n\\n**Estado:** pendiente\\n\\n## Objetivo\\n\\nNada.\\n'"
               " > tareas/T26-registro.md")
        self.assertNotEqual(0, r.returncode, f"borró el criterio:\n{r.stdout}{r.stderr}")
        self.assertIn("criterios de terminado", r.stdout + r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_sin_rojos_no_llama_al_arquitecto(self):
        """Un script que gasta un agente para no hacer nada enseña a no correrlo."""
        d = self.proyecto("Guardar los datos en la tabla `usuarios`.")
        r = self.correr_replan(d, "echo NO_DEBERIA_CORRER; exit 1")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("NO_DEBERIA_CORRER", r.stdout)
        self.assertIn("no hay nada que replanificar", r.stdout)


class TestElVeredictoNoDependeDeComoLoInvocas(unittest.TestCase):
    """El filtro de dependencias de `coherencia.py` buscaba la subcadena `/.venv`, y con
    `PROYECTO=.` las rutas salen relativas —`.venv/lib/python3.12/...`, sin barra delante— así
    que no matcheaba nada y el chequeo se comía las dependencias enteras.

    Medido el 2026-10-21 contra ejemplo-clasificados: **2 rojos** con `PROYECTO=<carpeta>` o
    con ruta absoluta, **37** con `PROYECTO=.`, 35 de ellos tablas de `pip/_vendor/distlib`.
    Y `PROYECTO="."` es exactamente lo que `ubicar_proyecto` deja cuando el método se corre
    desde la raíz del proyecto, así que el preflight habría detenido el plan por tablas de
    pip con el sujeto más equivocado posible.

    Un chequeo cuyo resultado depende de cómo lo invocás no mide el sujeto: mide la
    invocación. Lo que este test fija es la INVARIANCIA, no el número."""

    def proyecto(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-invar-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-x.md").write_text(
            "# T01 — Una cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/x.py\n\n## Objetivo\n\nUsar la tabla `usuarios`.\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE usuarios (id INT PRIMARY KEY);\n")
        # Una dependencia con SQL adentro, como pip/_vendor/distlib, que NO es del proyecto.
        dep = d / ".venv" / "lib" / "python3.12" / "site-packages" / "libreria"
        dep.mkdir(parents=True)
        (dep / "cache.py").write_text(
            'def leer(c):\n    c.execute("SELECT * FROM tabla_de_la_libreria")\n')
        (d / "app").mkdir()
        (d / "app" / "x.py").write_text(
            'def leer(c):\n    c.execute("SELECT * FROM usuarios")\n')
        return d

    def test_las_tres_formas_de_nombrar_el_proyecto_dan_el_mismo_veredicto(self):
        d = self.proyecto()
        desde_afuera = correr(f'PROYECTO="{d.name}" python3 "{SCRIPTS}/coherencia.py"', d.parent)
        absoluta = correr(f'PROYECTO="{d}" python3 "{SCRIPTS}/coherencia.py"', RAIZ)
        desde_adentro = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        codigos = {"relativa": desde_afuera.returncode, "absoluta": absoluta.returncode,
                   "punto": desde_adentro.returncode}
        self.assertEqual({0}, set(codigos.values()),
                         f"el mismo proyecto da veredictos distintos según cómo se nombre: "
                         f"{codigos}\n--- punto:\n{desde_adentro.stdout}")

    def test_una_tabla_que_vive_en_una_dependencia_no_es_del_proyecto(self):
        """Y el caso concreto: la tabla de la librería no se le cobra al plan."""
        d = self.proyecto()
        r = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        self.assertNotIn("tabla_de_la_libreria", r.stdout,
                         f"el plan no es responsable del SQL de sus dependencias:\n{r.stdout}")


class TestUnaCorridaPorRojo(unittest.TestCase):
    """El techo de la sesión de memoria de ColabHive, medido el 2026-10-21 con el mismo agente
    y el mismo prompt, variando sólo cuánto se le permitía durar:

      240s directo · 300s directo · 240s con con_limite  → cortadas por alarma, TRABAJANDO
      1800s por el script, cuatro veces                  → memory_* a los 8-13 min
      900s directo, sin script                           → memory_session_expired a los 7:03
      420s directo, UN rojo, prompt de 541 caracteres    → ✓ hecho en 4:09

    Ninguna murió antes de los 5 minutos y ninguna sobrevivió más de 13, así que el pedido que
    no entra en ese techo no falla por su contenido sino por su tamaño. Le cobré el corte a la
    plataforma tres veces antes de medirlo.

    Lo que este test fija es que el script PARTE el trabajo: una corrida por contradicción. No
    fija el techo en segundos —es de la plataforma y se mueve— ni baja `LIMITE_AGENTE`, porque
    el vigilante tiene que seguir perdiendo la carrera contra el error que la plataforma sabe
    informar."""

    def proyecto(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-por-rojo-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        # El archivo que cada tarea declara tiene que ser EL MISMO que el PLAN.md le asigna:
        # `validar-plan.py` cruza las dos cosas, y mi primer andamio puso `app/x.py` en las dos
        # tareas con el plan diciendo `app/y.py` para T28. El test falló con «el plan dejó de
        # validar» y el defecto era del andamio, no del script. Segunda vez en esta clase de
        # tests: medir el andamio en vez del sujeto.
        for tid, tabla, arch in (("T26", "users", "app/x.py"), ("T28", "ads", "app/y.py")):
            (d / "tareas" / f"{tid}-x.md").write_text(
                f"# {tid} — Algo\n\n**Estado:** pendiente\n**Depende de:** —\n"
                f"**Archivos que podés tocar:** {arch}\n\n## Objetivo\n\n"
                f"Guardar en la tabla `{tabla}`.\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE usuarios (id INT PRIMARY KEY);\nCREATE TABLE anuncios (id INT);\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n"
            "|---|---|---|---|---|\n| T26 | Algo | — | `app/x.py` | pendiente |\n"
            "| T28 | Otro | — | `app/y.py` | pendiente |\n")
        return d

    def test_dos_contradicciones_son_dos_corridas_y_cada_prompt_nombra_un_archivo(self):
        d = self.proyecto()
        bin_ = d / ".bin"; bin_.mkdir()
        # El arquitecto falso anota su invocación y qué archivo le pidieron.
        (bin_ / "opencode").write_text(
            '#!/usr/bin/env bash\n'
            'echo "$*" >> "$INVOCACIONES"\n'
            # Corrige la tabla del archivo que el prompt nombre, y nada más.
            'arch="$(printf "%s" "$*" | grep -oE "tareas/T[0-9]+[a-z]?-[a-z]+\\.md" | head -1)"\n'
            '[ -n "$arch" ] && { sed -i "" "s/tabla \\`users\\`/tabla \\`usuarios\\`/; '
            's/tabla \\`ads\\`/tabla \\`anuncios\\`/" "$arch"; }\n')
        (bin_ / "opencode").chmod(0o755)
        inv = d / "invocaciones.txt"
        r = correr(f'PATH="{bin_}:$PATH" INVOCACIONES="{inv}" PROYECTO=. LIMITE_AGENTE=60 '
                   f'bash "{SCRIPTS}/replanificar-coherencia.sh"', d)
        lineas = inv.read_text().splitlines() if inv.exists() else []
        self.assertEqual(2, len(lineas),
                         f"dos contradicciones tienen que ser dos corridas, no una con las "
                         f"dos adentro:\n{chr(10).join(lineas)}\n--- salida:\n{r.stdout}{r.stderr}")
        for linea in lineas:
            nombrados = re.findall(r"tareas/T\d+[a-z]?-\w+\.md", linea)
            self.assertEqual(1, len(set(nombrados)),
                             f"cada corrida tiene que pedir UN archivo: {nombrados}")
        self.assertEqual(0, r.returncode, f"y el preflight queda limpio:\n{r.stdout}{r.stderr}")


class TestElReplanificadorNoDejaEscribirEnElTronco(unittest.TestCase):
    """Los dos replanificadores corren `cd "$BASE"` sobre el proyecto REAL, no sobre un
    worktree: sus agentes pueden escribir en el tronco. El prompt se lo prohíbe —«NO escribas
    ningún archivo: tu respuesta ES el entregable»— y nadie lo verificaba. Un prompt no es un
    permiso.

    Medido el 2026-10-24: el relevo de T05c corrió de 10:16:44 a 10:27:07 y el modelo que
    tenía que reescribir el enunciado IMPLEMENTÓ la tarea. Dejó `backend/app/rutas/ads.py`
    —89 líneas, sin seguimiento— en el tronco a las 10:26:51, y la corrida terminó con
    `exit=0` diciendo sólo «✗ no escribió el cuerpo nuevo».

    Lo que estaba en juego era la corrida SIGUIENTE: ese código quedaba ahí para que el
    próximo intento de tests-first de T05c lo encontrara ya hecho —lo que `validar-plan.py`
    prohíbe— y para que el paso 0 del gate viera «implementó la feature, el test pasa» y
    concluyera «el test no prueba nada». Dos corridas unidas por un archivo que nadie puso en
    ninguna foto: la de `escribir-tests.sh` mide el worktree del ejecutor, y esto pasa fuera
    de todo worktree.

    Estos tests no miran el texto del script: le ponen un `opencode` falso en el PATH que
    escribe de más y miden qué queda en el tronco."""

    def proyecto(self):
        # El repo va en un SUBDIRECTORIO del temporal porque la cuarentena se escribe en
        # `$RAIZ/..`, igual que `fallidos-<id>`: así todo lo que la corrida crea cae adentro
        # del árbol que este test borra al terminar.
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-tronco-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T40-avisos.md").write_text(
            "# T40 — Avisos rutas\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/rutas/ads.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nImplementar los endpoints.\n\n"
            "## Tests\n\nArchivo: `tests/test_ads.py`, clase `TestAds`\n\n"
            "## Terminado cuando\n\n- [ ] andan los endpoints\n")
        (d / "app" / "rutas").mkdir(parents=True)
        (d / "app" / "rutas" / "ads.py").write_text("# vacío todavía\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T40 | Avisos rutas | — | `app/rutas/ads.py` | pendiente |\n")
        correr("git add -A && git commit -qm base", d)
        # El transcript del fallo, que el relevo exige antes de gastar un agente: sin esto
        # frena en «no hay transcripts de fallo» y estos tests no llegan al paso que miden.
        #
        # Lo encontró la suite COMPLETA, no la clase corrida sola: en aislamiento los cuatro
        # tests seguían verdes porque la guarda que los frena se agregó después, y el cuarto
        # —el que mide que no haya falso reproche— pasaba trivialmente por no llegar nunca al
        # agente. Un verde que depende de que el script se detenga antes no mide nada.
        # Con las dos formas que tiene un transcript real: la línea del gate y el error
        # concreto. La primera versión puso sólo el `E  AssertionError` y el relevo siguió
        # frenando, porque su extractor buscaba únicamente `✗|por qué falla`.
        fallidos = d.parent / "fallidos-T40"; fallidos.mkdir()
        (fallidos / "intento-1.log").write_text(
            "  ✗ el test no pasa ni con la implementación del propio agente.\n"
            "E  AssertionError: Expected 'execute' to be called once. Called 0 times.\n")
        return d

    def opencode_falso(self, d, diagnostica, escribe):
        """Un `opencode` que hace una cosa en el paso 1 y otra en el paso 2. Los distingue por
        `.diagnostico-T40.md`, que el arnés escribe DESPUÉS del primer agente."""
        bin_ = d / ".bin"; bin_.mkdir()
        (bin_ / "opencode").write_text(
            "#!/usr/bin/env bash\n"
            "if [ -f .diagnostico-T40.md ]; then\n" + escribe + "\nelse\n" + diagnostica + "\nfi\n")
        (bin_ / "opencode").chmod(0o755)
        return f'PATH="{bin_}:$PATH"'

    def correr_relevo(self, d, diagnostica, escribe):
        env = self.opencode_falso(d, diagnostica, escribe)
        return correr(f'{env} PROYECTO=. LIMITE_AGENTE=60 DIAGNOSTICA=m1 ESCRIBE=m2 '
                      f'bash "{SCRIPTS}/replanificar-relevo.sh" T40', d)

    # El caso real, con el nombre que tenía: el que debía escribir el enunciado implementó la
    # tarea. El `echo` del cuerpo está para que el único reproche posible sea el archivo de
    # más —si no escribiera el cuerpo, el script cortaría con «no escribió el cuerpo nuevo» y
    # el test podría pasar por el motivo equivocado.
    ESCRIBIO_CODIGO = ('echo "implementé la tarea, mi implementación está correcta"\n'
                       'printf "@router.get(\\"/ads\\")\\ndef list_ads(): pass\\n" '
                       '> app/rutas/ads.py\n'
                       'printf "## Objetivo\\n\\nCuerpo nuevo con el diagnóstico aplicado.\\n" '
                       '> .replan-T40-cuerpo.md\n')
    DIAGNOSTICO_OK = 'echo "al enunciado le falta decir donde vive cada cosa que nombra"\n'

    def test_el_que_reescribe_el_enunciado_no_puede_implementar_la_tarea(self):
        d = self.proyecto()
        antes = (d / "app" / "rutas" / "ads.py").read_text()
        r = self.correr_relevo(d, self.DIAGNOSTICO_OK, self.ESCRIBIO_CODIGO)
        salida = r.stdout + r.stderr
        self.assertIn("PROHIBIDO escribir", salida,
                      f"escribió código en el tronco y la corrida no lo dijo:\n{salida}")
        self.assertIn("app/rutas/ads.py", salida, f"y tiene que NOMBRAR el archivo:\n{salida}")
        self.assertEqual(antes, (d / "app" / "rutas" / "ads.py").read_text(),
                         f"el tronco tiene que quedar como estaba:\n{salida}")

    def test_lo_que_escribio_de_mas_se_guarda_y_no_se_borra(self):
        """La evidencia es lo único que este método produce. El archivo de más del 2026-10-24
        tenía un `GET /ads` con `501 No implementado` y el comentario «esta funcionalidad no
        está implementada en el servicio de ads según el alcance de la tarea T05c»: era la
        prueba, escrita por el propio modelo, del HUECO que el 27B diagnosticó aparte."""
        d = self.proyecto()
        r = self.correr_relevo(d, self.DIAGNOSTICO_OK, self.ESCRIBIO_CODIGO)
        guardados = sorted(p for p in (d.parent).rglob("relevo-escribio-T40/**/ads.py"))
        self.assertTrue(guardados,
                        f"sacarlo del tronco no es tirarlo:\n{r.stdout}{r.stderr}\n"
                        f"hay en {d.parent}: {[p.name for p in d.parent.iterdir()]}")
        self.assertIn("list_ads", guardados[0].read_text(),
                      "y lo guardado tiene que ser lo que el agente escribió")

    def test_el_que_diagnostica_tampoco_puede_escribir(self):
        """El paso 1 tiene la prohibición más explícita de todo el método —«NO escribas ningún
        archivo»— y era el menos vigilado: su chequeo posterior sólo mira si el transcript
        quedó vacío."""
        d = self.proyecto()
        antes = (d / "app" / "rutas" / "ads.py").read_text()
        r = self.correr_relevo(d, 'echo "diagnostico"; echo "# mio" > app/rutas/ads.py',
                               self.ESCRIBIO_CODIGO)
        salida = r.stdout + r.stderr
        self.assertIn("PROHIBIDO escribir", salida, f"\n{salida}")
        self.assertIn("m1", salida.split("PROHIBIDO")[0].split("\n")[-1],
                      f"el veredicto tiene que nombrar al agente del paso 1, no al del 2:\n{salida}")
        self.assertEqual(antes, (d / "app" / "rutas" / "ads.py").read_text(), f"\n{salida}")

    def test_el_relevo_le_pasa_el_error_concreto_y_no_la_categoria(self):
        """El arreglo de `1b44184` vivía sólo en `replanificar.sh`. Acá el extractor era
        `✗|por qué falla` y nada más —la categoría que ese commit sacó del otro lado—, así que
        el 2026-10-23 el agente recibió «✗ la suite está en rojo» con el
        `ModuleNotFoundError` dos líneas más abajo en el mismo archivo: 16 minutos para no
        cambiar nada.

        Octava vez que el arreglo vive en un hermano y no en el otro, y la segunda en este
        mismo par de scripts en el mismo día."""
        d = self.proyecto()
        # El transcript real: la línea del gate es genérica, el dato está debajo.
        (d.parent / "fallidos-T40" / "intento-1.log").write_text(
            "  ✗ la suite está en rojo\n"
            "E  ModuleNotFoundError: No module named 'app.servicios.listar'\n")
        prompts = d.parent / "prompts.txt"
        env = f'PATH="{d}/.bin:$PATH"'
        bin_ = d / ".bin"; bin_.mkdir()
        (bin_ / "opencode").write_text(
            '#!/usr/bin/env bash\necho "$*" >> "$PROMPTS"\necho ok\n')
        (bin_ / "opencode").chmod(0o755)
        correr(f'{env} PROMPTS="{prompts}" PROYECTO=. LIMITE_AGENTE=60 '
               f'DIAGNOSTICA=m1 ESCRIBE=m2 bash "{SCRIPTS}/replanificar-relevo.sh" T40', d)
        texto = prompts.read_text() if prompts.exists() else ""
        self.assertIn("ModuleNotFoundError", texto,
                      f"le pasó la categoría y se guardó el dato:\n{texto[:600]}")

    def test_un_relevo_que_hace_lo_suyo_no_recibe_ningun_reproche(self):
        """El otro lado del chequeo: el andamio que el arnés mismo escribe en el proyecto —el
        log, `.opencode-data/`, el cuerpo que el paso 2 TIENE que escribir— no es una escritura
        de más. Un guardia que le cobra al agente el andamio del método es el mismo defecto
        que este test persigue, con el sujeto invertido."""
        d = self.proyecto()
        r = self.correr_relevo(
            d, self.DIAGNOSTICO_OK,
            'printf "## Objetivo\\n\\nCuerpo nuevo con el diagnóstico aplicado.\\n" '
            '> .replan-T40-cuerpo.md\n')
        salida = r.stdout + r.stderr
        self.assertNotIn("PROHIBIDO escribir", salida,
                         f"no escribió nada de más y se lo reprochó:\n{salida}")


class TestElMarcadorDeHuecoSobreviveAlMarkdown(unittest.TestCase):
    """El extractor de HUECO de los dos replanificadores pedía las marcas de markdown UNA vez
    y antes de los espacios: `^[ \\t]*[*#>-]*[ \\t]*HUECO\\b`. El 2026-10-24 el 27B escribió

        - **HUECO**: No existe función para listar todos los anuncios en la capa de servicios

    —guión, espacio, asteriscos: marcas INTERCALADAS— y no matcheó. El hueco se perdió, el
    relevo siguió al paso 2 y gastó otro agente de 16 minutos en una tarea que requería una
    decisión de producto.

    Es la tercera vez que un extractor frágil decide un veredicto: el `grep '→'` de mutar.py y
    el motivo que era una categoría son el mismo defecto. Por eso el test mide la LÍNEA REAL,
    no una inventada: lo que rompió el patrón fue la forma en que los modelos escriben."""

    # La línea tal cual salió del diagnóstico del 27B, y las formas vecinas que cualquier
    # modelo produce para lo mismo.
    FORMAS = ["- **HUECO**: No existe función para listar todos los anuncios",
              "**HUECO**: falta la función",
              "HUECO: falta la función",
              "  - HUECO — falta la función",
              "### HUECO",
              "> **HUECO:** falta la función",
              "3. **HUECO**: falta la función"]
    NO_SON = ["El laberinto tiene un hueco en la pared.",
              "escribí la palabra HUECO y qué falta",
              "- Whether there's a HUECO (a gap that no task delivers)"]

    def patrones(self):
        """Los patrones tal como están escritos en los scripts, uno por aparición. Se leen del
        archivo a propósito: un test que copia el patrón mide la copia."""
        hallados = []
        for n in ("replanificar.sh", "replanificar-relevo.sh"):
            texto = (SCRIPTS / n).read_text()
            for m in re.finditer(r"grep -q?[A-Za-z]* +-?[A-Za-z]* *'(\^[^']*HUECO[^']*)'", texto):
                hallados.append((n, m.group(1)))
            for m in re.finditer(r"grep -A[0-9]+ -E +'(\^[^']*HUECO[^']*)'", texto):
                hallados.append((n, m.group(1)))
        return hallados

    def test_los_dos_scripts_tienen_el_patron(self):
        nombres = {n for n, _ in self.patrones()}
        self.assertEqual({"replanificar.sh", "replanificar-relevo.sh"}, nombres,
                         f"falta el extractor en alguno: {self.patrones()}")

    def test_cada_patron_ve_la_linea_que_el_27B_escribio(self):
        """Y TODAS las apariciones, no la primera: en `replanificar.sh` el `grep -q` que
        DETECTA se arregló y el `grep -A3` que IMPRIME quedó con el patrón viejo, así que el
        aviso se disparaba y no mostraba el hueco. Un arreglo a medias en el mismo `if`."""
        for nombre, patron in self.patrones():
            for linea in self.FORMAS:
                r = subprocess.run(
                    ["grep", "-qE", patron], input=linea + "\n", text=True, capture_output=True)
                self.assertEqual(0, r.returncode,
                                 f"{nombre}: el patrón {patron!r} no ve «{linea}»")

    def test_y_no_confunde_la_prosa_ni_el_prompt_devuelto(self):
        """El transcript trae el prompt adentro —«escribí la palabra HUECO y qué falta»— así
        que un patrón sin ancla declararía un hueco en cada corrida."""
        for nombre, patron in self.patrones():
            for linea in self.NO_SON:
                r = subprocess.run(["grep", "-qE", patron], input=linea + "\n",
                                   text=True, capture_output=True)
                self.assertEqual(1, r.returncode,
                                 f"{nombre}: el patrón {patron!r} se dispara con «{linea}»")


class TestReplanificarSinMotivoNoReplanifica(unittest.TestCase):
    """Los dos replanificadores arman el motivo así:

        MOTIVO="$FASE  Lo que falló: $(...extracción del transcript...)"

    y `replanificar.sh` lo protegía con `if [ -z "$MOTIVO" ]`, que NUNCA puede ser cierto:
    `$FASE` siempre tiene texto. La guarda no podía dispararse jamás, así que el script
    replanificaba con «Lo que falló:» y nada detrás —adivinando, que es exactamente lo que su
    propio mensaje dice que no hay que hacer—. En el relevo la guarda no existía siquiera.

    Y un arquitecto que recibe un motivo vacío no se queda quieto: inventa una causa. Es cómo
    T05c acumuló tres replanificaciones sin que el hueco real apareciera.

    Cuarta guarda que encuentro incapaz de dispararse, y la cuarta vez con el mismo defecto:
    el chequeo mira una variable derivada en vez del dato. El test mide que el agente NO se
    llame, porque gastarlo es el costo que la guarda evita."""

    def proyecto(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sinmotivo-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T41-cosa.md").write_text(
            "# T41 — Una cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/cosa.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nQue haya una cosa.\n\n"
            "## Tests\n\nArchivo: `tests/test_cosa.py`, clase `TestCosa`\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T41 | Una cosa | — | `app/cosa.py` | pendiente |\n")
        correr("git add -A && git commit -qm base", d)
        bin_ = d / ".bin"; bin_.mkdir()
        # Un agente que deja rastro de haber sido llamado. Si la guarda anda, no existe.
        #
        # La marca va AFUERA del proyecto: la primera versión la dejaba adentro y el guardia
        # de escrituras de más —el de `relevo-escribio-<id>`— se la llevó a la cuarentena,
        # así que el test falló midiendo mi andamio en vez del script. El guardia tenía razón.
        (bin_ / "opencode").write_text(
            '#!/usr/bin/env bash\ntouch "$(dirname "$0")/../../LO-LLAMARON"\n'
            'echo "replanifiqué a ciegas"\n')
        (bin_ / "opencode").chmod(0o755)
        return d

    def test_replanificar_no_gasta_un_agente_sin_transcript(self):
        d = self.proyecto()
        r = correr(f'PATH="{d}/.bin:$PATH" PROYECTO=. LIMITE_AGENTE=60 MODELO=m1 '
                   f'bash "{SCRIPTS}/replanificar.sh" T41', d)
        salida = r.stdout + r.stderr
        self.assertFalse((d.parent / "LO-LLAMARON").exists(),
                         f"llamó al arquitecto sin tener qué contarle:\n{salida}")
        self.assertIn("no hay transcripts de fallo", salida, f"\n{salida}")

    def test_el_relevo_tampoco(self):
        """La misma regla con dos lectores. Acá no había ninguna guarda: el relevo gastaba DOS
        agentes —el que diagnostica y el que escribe— sobre un motivo vacío."""
        d = self.proyecto()
        r = correr(f'PATH="{d}/.bin:$PATH" PROYECTO=. LIMITE_AGENTE=60 '
                   f'DIAGNOSTICA=m1 ESCRIBE=m2 bash "{SCRIPTS}/replanificar-relevo.sh" T41', d)
        salida = r.stdout + r.stderr
        self.assertFalse((d.parent / "LO-LLAMARON").exists(),
                         f"gastó agentes sin tener qué contarles:\n{salida}")
        self.assertIn("no hay transcripts de fallo", salida, f"\n{salida}")

    def test_con_transcript_si_replanifica(self):
        """El otro lado: una guarda que frena siempre es peor que ninguna."""
        d = self.proyecto()
        fallidos = d.parent / "fallidos-T41"; fallidos.mkdir()
        (fallidos / "intento-1.log").write_text(
            "E  AssertionError: Expected 'execute' to be called once. Called 0 times.\n")
        r = correr(f'PATH="{d}/.bin:$PATH" PROYECTO=. LIMITE_AGENTE=60 MODELO=m1 '
                   f'bash "{SCRIPTS}/replanificar.sh" T41', d)
        salida = r.stdout + r.stderr
        self.assertTrue((d.parent / "LO-LLAMARON").exists(),
                        f"con el motivo en la mano tiene que llamarlo:\n{salida}")
        self.assertIn("AssertionError", salida,
                      f"y pasarle el error CONCRETO, no la categoría:\n{salida}")


class TestLaSondaMideLosModelosQueLaCorridaVaAUsar(unittest.TestCase):
    """`plataforma_responde` mide UN modelo —`modelo_del_agente ejecutor`— y autoriza una
    corrida que usa varios. En la config de hoy son 13 papeles declarados sobre 3 modelos
    distintos, y las réplicas se caen de a una: el 2026-10-24 el monitoreo midió réplicas
    ancladas con `min=1` que quedaron en `actuales=0`, y el 27B estuvo TRES HORAS caído
    mientras el ejecutor contestaba 200.

    Con esa sonda el preflight daba verde y la corrida moría en la primera replanificación,
    informando que falló la tarea. Un chequeo que mide un sujeto y autoriza a otro es el
    defecto central de este método, y acá estaba en la puerta: es lo único que separa «no
    arrancar» de nueve etapas de agentes.

    El servidor falso contesta 200 o 503 según el modelo que venga en el cuerpo del pedido,
    así que estos tests miden el camino real —`/chat/completions` con herramientas— y no una
    función imitada."""

    PAPELES = {"arquitecto": "m-razona", "plan": "m-razona", "reviewer": "m-razona",
               "ejecutor": "m-escribe", "build": "m-escribe",
               "title": "m-chico", "summary": "m-chico"}

    def entorno(self, caidos=()):
        # Local, como en los otros dos andamios de servidor de este archivo.
        import http.server, threading
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sonda-corrida-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text(json.dumps({
            "provider": {"colabhive": {"models": {m: {} for m in set(self.PAPELES.values())}}},
            "agent": {p: {"model": f"colabhive/{m}"} for p, m in self.PAPELES.items()}}))

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                cuerpo = self.rfile.read(n).decode("utf-8", "replace")
                roto = any(f'"{m}"' in cuerpo for m in caidos)
                self.send_response(503 if roto else 200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return cfg, f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def sondear(self, cfg, base, funcion):
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; {funcion}; echo "rc=$?"',
                      RAIZ, COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x",
                      CONFIG_OC=str(cfg), ARRANQUE_FRIO=5)

    def test_con_todos_arriba_da_verde_y_nombra_los_papeles(self):
        cfg, base = self.entorno()
        r = self.sondear(cfg, base, "plataforma_responde_la_corrida")
        self.assertIn("rc=0", r.stdout, f"\n{r.stdout}{r.stderr}")
        for papel in ("arquitecto", "ejecutor", "title"):
            self.assertIn(papel, r.stdout + r.stderr,
                          f"tiene que decir qué papeles probó:\n{r.stdout}{r.stderr}")

    def test_el_modelo_del_arquitecto_caido_frena_la_corrida(self):
        """El caso medido: el del ejecutor contesta y el del arquitecto no."""
        cfg, base = self.entorno(caidos=("m-razona",))
        r = self.sondear(cfg, base, "plataforma_responde_la_corrida")
        self.assertNotIn("rc=0", r.stdout, f"dio verde con un modelo caído:\n{r.stdout}{r.stderr}")
        salida = r.stdout + r.stderr
        self.assertIn("arquitecto", salida,
                      f"y tiene que nombrar el PAPEL, no sólo el id del modelo:\n{salida}")

    def test_la_sonda_vieja_daba_verde_en_ese_mismo_escenario(self):
        """El test que mide el defecto de frente, no el arreglo: con el modelo del arquitecto
        caído y el del ejecutor sano, `plataforma_responde` autoriza la corrida. Si algún día
        este test se pone rojo, es que la sonda vieja cambió y hay que mirar las dos."""
        cfg, base = self.entorno(caidos=("m-razona",))
        r = self.sondear(cfg, base, "plataforma_responde")
        self.assertIn("rc=0", r.stdout,
                      f"la sonda vieja mide el ejecutor y nada más; si esto cambió, revisar "
                      f"`plataforma_responde_la_corrida`:\n{r.stdout}{r.stderr}")

    def test_el_ejecutor_caido_tambien_frena(self):
        """El otro lado, para que el verde no venga de probar siempre lo mismo."""
        cfg, base = self.entorno(caidos=("m-escribe",))
        r = self.sondear(cfg, base, "plataforma_responde_la_corrida")
        self.assertNotIn("rc=0", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("ejecutor", r.stdout + r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_sin_agentes_declarados_cae_a_la_sonda_vieja_y_lo_dice(self):
        """Un chequeo que no puede leer su insumo no dice «verde»: dice que no pudo, y hace lo
        que puede. Callado sería un falso verde, que es el defecto 19 de esta investigación."""
        cfg, base = self.entorno()
        cfg.write_text(json.dumps({"provider": {"colabhive": {"models": {"m-escribe": {}}}}}))
        r = self.sondear(cfg, base, "plataforma_responde_la_corrida")
        self.assertIn("⊘", r.stdout + r.stderr,
                      f"tiene que avisar que no pudo leer los papeles:\n{r.stdout}{r.stderr}")

    def test_los_modelos_de_la_corrida_salen_sin_repetir_y_con_sus_papeles(self):
        cfg, _ = self.entorno()
        r = correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; modelos_de_la_corrida',
                   RAIZ, CONFIG_OC=str(cfg))
        lineas = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertEqual(3, len(lineas), f"tres modelos, siete papeles:\n{r.stdout}")
        self.assertEqual({"m-razona", "m-escribe", "m-chico"},
                         {l.split()[0] for l in lineas}, f"\n{r.stdout}")
        razona = [l for l in lineas if l.startswith("m-razona")][0]
        self.assertEqual("arquitecto,plan,reviewer", razona.split()[1], f"\n{r.stdout}")


class TestLaSuiteNoDejaBasuraEnSilencio(unittest.TestCase):
    """`Proyecto.tirar` arrancó con `ignore_errors=True`, que dejó 147 directorios temporales
    en un día de corridas sin que nadie se enterara. El arreglo puso un manejador que hace
    `chmod` y reintenta —los objetos de git son 444 y `rmtree` no los toca— pero terminaba en
    `except OSError: pass`: el silencio se movió un nivel y no se fue. El comentario denunciaba
    «un rm que falla en silencio» dos líneas arriba del `pass`.

    No es higiene de andamio: hoy llené el disco dos veces y quedan 8,9 GiB. Una suite que
    pierde un directorio por corrida y no lo dice es una suite que un día no corre.

    El manejador se midió inyectándole la falla, porque la otra forma —fabricar un archivo
    que de verdad resista el `chmod`— no es portable: un usuario normal siempre puede
    cambiarle el permiso a sus propios archivos."""

    def test_tirar_borra_un_repo_de_git_con_objetos_de_solo_lectura(self):
        """El defecto original: `rmtree` a secas falla con los 444 de .git/objects."""
        p = Proyecto()
        repo = p.repo
        self.assertTrue((repo / ".git").is_dir(), "el andamio tiene que haber creado el repo")
        p.tirar()
        self.assertFalse(os.path.exists(repo), "tirar() tiene que dejar el disco limpio")

    def test_si_el_chmod_falla_se_anota_en_vez_de_tragarse(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-basura-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        victima = d / "resiste.txt"
        victima.write_text("x")
        antes = len(NO_BORRADOS)
        chmod_real = os.chmod
        os.chmod = lambda *a, **k: (_ for _ in ()).throw(OSError("chmod falla a propósito"))
        try:
            _a_la_fuerza(os.unlink, victima, None)
        finally:
            os.chmod = chmod_real
        self.assertEqual(antes + 1, len(NO_BORRADOS),
                         "el manejador se tragó la falla: nadie se va a enterar")
        self.assertIn("resiste.txt", NO_BORRADOS[-1][0],
                      f"y tiene que anotar QUÉ ruta quedó: {NO_BORRADOS[-1]}")
        NO_BORRADOS.pop()

    def test_tirar_dos_veces_no_es_basura_en_disco(self):
        """El falso positivo que el aviso nuevo produjo en su primera corrida. Los dos tests
        de contabilidad del veredicto tiran su proyecto en un `finally` y después `unittest`
        corre su propio `tearDown` sobre el mismo: la segunda pasada daba FileNotFoundError,
        el manejador la anotaba como «resistió» y el aviso acusaba de dejar basura un
        directorio correctamente borrado. Dos avisos falsos por corrida, del mismo tipo que
        todo lo de hoy: el veredicto nombraba al sujeto equivocado."""
        p = Proyecto()
        p.tirar()
        antes = len(NO_BORRADOS)
        p.tirar()
        self.assertEqual(antes, len(NO_BORRADOS),
                         "tirar lo ya tirado no es una ruta que resistió")

    def test_rehacer_proyecto_no_deja_huerfano_el_anterior(self):
        """El defecto real detrás de los 55 directorios de /var/folders: un test que llama a
        `self.setUp()` para rearmar el escenario pisa `self.p` y abandona el proyecto que
        `unittest` ya había creado. `rehacer_proyecto` tira el anterior primero."""
        caso = TestValidarPlan("test_plan_sano_valida")
        caso.setUp()
        try:
            primero = caso.p.repo
            caso.rehacer_proyecto()
            segundo = caso.p.repo
            self.assertNotEqual(primero, segundo, "tiene que ser un proyecto NUEVO")
            self.assertFalse(os.path.exists(primero),
                             f"dejó huérfano el anterior: {primero}")
            self.assertTrue(os.path.exists(segundo))
        finally:
            caso.tearDown()

    def test_ningun_test_llama_a_setUp_a_mano(self):
        """El pie de banco que causó todo esto. `setUp` crea un proyecto y pisa `self.p`:
        llamarlo desde el cuerpo de un test abandona el anterior en silencio. Quien necesite
        rearmar el escenario tiene `rehacer_proyecto`, que tira el anterior primero."""
        fuente = (RAIZ / "pruebas" / "test_metodo.py").read_text()
        # La llamada PELADA y nada más. La primera versión buscaba la subcadena y se
        # matcheaba a sí misma, a su propia prosa y a los dos docstrings que explican el
        # defecto: tres falsos positivos de tres. Mismo defecto de extractor que el `HUECO`
        # de esta mañana, por tercera vez hoy y otra vez en el test que vigila.
        culpables = [f"línea {n}" for n, l in enumerate(fuente.splitlines(), 1)
                     if l.strip() == "self.setUp()"]
        self.assertEqual([], culpables,
                         "un test llama a setUp() a mano y deja un proyecto huérfano por "
                         f"corrida: {culpables}. Usá rehacer_proyecto().")

    def test_un_huerfano_dice_de_quien_es(self):
        """Había 55 en /var/folders, del 21 al 24 de octubre, todos idénticos y sin una marca
        que los distinguiera: no se podía nombrar al sujeto sin adivinar."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        marca = (p.repo / ".quien-lo-creo").read_text()
        self.assertIn("test_un_huerfano_dice_de_quien_es", marca,
                      f"la marca tiene que nombrar al test que lo creó: {marca!r}")

    def test_la_marca_no_ensucia_el_worktree_del_juguete(self):
        """La marca cae en la raíz del repo de juguete ANTES del `git add -A`. Sin ignorarla,
        entraría en los commits y aparecería en cada `git status` que los tests miran: una
        marca de diagnóstico que cambia el sujeto medido es peor que no tenerla."""
        p = Proyecto()
        self.addCleanup(p.tirar)
        r = correr("git status --short", p.repo)
        self.assertEqual("", r.stdout.strip(),
                         f"el juguete tiene que arrancar limpio:\n{r.stdout}")

    def test_el_manejador_es_alcanzable_desde_un_test(self):
        """Era un cierre dentro de `tirar`: ningún test podía llamarlo, y lo que no se puede
        medir es lo que vuelve a romperse. El test fija que siga siendo alcanzable."""
        self.assertTrue(callable(_a_la_fuerza))
        # Sin la sangría adentro del patrón. La primera versión de este test buscaba la
        # cadena literal con los 16 espacios del cierre viejo, así que una mutación con otra
        # sangría le pasaba por al lado: de tres tests mutados, dos quedaron verdes. Es el
        # mismo defecto de extractor frágil que el `HUECO` de hoy y el `grep '→'` de
        # mutar.py, cometido en el test que lo vigila.
        fuente = (RAIZ / "pruebas" / "test_metodo.py").read_text()
        self.assertIsNone(re.search(r"except OSError[^\n]*:\s*\n\s*pass\b", fuente),
                          "volvió el `pass` que se tragaba la falla del borrado")


class TestElCanalSinMemoria(unittest.TestCase):
    """El canal sin memoria —`pedir.py`, `limpiar.py`, `enjambre.sh`, `conversar.sh`— vivía en
    el scratchpad de una sesión, sin un solo test en esta suite. Es lo que resolvió una
    contradicción del plan en 2 segundos con dos modelos locales, mientras siete corridas del
    arnés con memoria morían con `memory_session_expired` a los 7-13 minutos para corregir UNA
    palabra de un archivo.

    O sea: el camino que FUNCIONA era el único sin red. Un método cuya parte más barata y más
    efectiva no está en el repo ni se mide es un método que la va a perder.

    El servidor falso contesta como `/chat/completions`, así que estos tests miden el camino
    real y no una función imitada."""

    def servidor(self, respuestas, codigo=200, demora=0):
        """`respuestas` es {modelo: texto}. Lo que no esté ahí da 503."""
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                pedido = json.loads(self.rfile.read(n).decode("utf-8", "replace"))
                if demora:
                    time.sleep(demora)
                texto = respuestas.get(pedido.get("model"))
                if texto is None or codigo != 200:
                    self.send_response(503)
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                    return
                cuerpo = json.dumps(
                    {"choices": [{"message": {"content": texto}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def salida(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-sinmem-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        return d

    # ── pedir.py: el POST pelado, sin sesión ni herramientas

    def test_pedir_devuelve_el_contenido_del_modelo(self):
        base = self.servidor({"m1": "la respuesta"})
        d = self.salida()
        (d / "p.txt").write_text("¿cuál?\n")
        r = correr(f'python3 "{SCRIPTS}/pedir.py" m1 < "{d}/p.txt"', RAIZ,
                   COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertEqual("la respuesta", r.stdout.strip())

    def test_pedir_falla_con_codigo_distinto_de_cero_y_lo_dice_por_stderr(self):
        """Un canal que falla en silencio es peor que no tenerlo: el que lee la tabla del
        enjambre tiene que poder distinguir «dijo esto» de «no contestó»."""
        base = self.servidor({})
        d = self.salida()
        (d / "p.txt").write_text("¿cuál?\n")
        r = correr(f'python3 "{SCRIPTS}/pedir.py" m1 < "{d}/p.txt"', RAIZ,
                   COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x")
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("ERROR", r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_pedir_respeta_PACIENCIA(self):
        """El método tiene medido que un modelo desalojado tarda 253s en levantarse y que el
        POST es lo que lo arranca. Con una paciencia corta el pedido muere justo antes de que
        termine de cargar, y el que lee la tabla concluye «este modelo no responde» cuando lo
        que pasó es que no lo esperamos: el mismo error que la sonda de 45s contra un arranque
        de 91-106s, que ya costó tres lanzamientos."""
        base = self.servidor({"m1": "tarde pero seguro"}, demora=2)
        d = self.salida()
        (d / "p.txt").write_text("¿cuál?\n")
        corto = correr(f'python3 "{SCRIPTS}/pedir.py" m1 < "{d}/p.txt"', RAIZ,
                       COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", PACIENCIA=1)
        self.assertNotEqual(0, corto.returncode,
                            "con menos paciencia que la demora tiene que fallar (si no, este "
                            f"test no prueba que la use):\n{corto.stdout}{corto.stderr}")
        largo = correr(f'python3 "{SCRIPTS}/pedir.py" m1 < "{d}/p.txt"', RAIZ,
                       COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", PACIENCIA=30)
        self.assertEqual(0, largo.returncode, f"\n{largo.stdout}{largo.stderr}")
        self.assertIn("tarde pero seguro", largo.stdout)

    # ── limpiar.py: la regla de «dónde termina el razonamiento»

    def limpiar(self, texto, *extra):
        d = self.salida()
        (d / "r.txt").write_text(texto)
        r = correr(f'python3 "{SCRIPTS}/limpiar.py" {" ".join(extra)} "{d}/r.txt"', RAIZ)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        return r.stdout.strip()

    def test_limpiar_saca_el_razonamiento_y_las_cercas(self):
        """El caso del 2026-10-23: el ejecutor devolvió un test correcto envuelto en ```python
        a pesar de que el prompt lo prohibía, y el chequeo lo informó como «✗ sintaxis:
        invalid syntax (line 1)». El contenido estaba bien; el extractor no."""
        self.assertEqual(
            "def f():\n    return 1",
            self.limpiar("pienso<think>dudo</think>\n```python\ndef f():\n    return 1\n```\n"))

    def test_limpiar_no_rompe_un_texto_sin_cercas_ni_razonamiento(self):
        self.assertEqual("usar-existente", self.limpiar("usar-existente\n"))

    def test_la_ultima_linea_sale_del_texto_YA_normalizado(self):
        """La copia incrustada en `enjambre.sh` tomaba la última línea del texto CRUDO, así que
        para una respuesta en cercas devolvía «```» —la cerca de cierre— y la tabla del
        enjambre mostraba eso como la respuesta del modelo. Tercera vez que un extractor no
        acuerda con el formato de su fuente."""
        salida = self.limpiar("pienso<think>dudo</think>\n```\nprimera\nla buena\n```\n",
                              "--ultima-linea")
        self.assertEqual("la buena", salida)
        self.assertNotIn("`", salida)

    def test_la_regla_del_razonamiento_vive_en_un_solo_lado(self):
        """`</think>` partido a mano aparecía en `enjambre.sh` y en `conversar.sh` además de
        en `limpiar.py`. Una regla copiada en tres lados es una regla que va a divergir, y hoy
        esa forma ya costó dos defectos."""
        self.assertNotIn("</think>", (SCRIPTS / "enjambre.sh").read_text(),
                         "enjambre.sh volvió a traerse la regla: usá limpiar.py")

    # ── enjambre.sh: varios modelos, y la evidencia cruda guardada

    def test_el_enjambre_guarda_la_salida_cruda_de_cada_modelo(self):
        """La extracción se hace sobre el ARCHIVO y no en la tubería: la primera versión
        extraía con `sed/tail` al vuelo, se trajo el razonamiento en vez de la respuesta y
        encima descartaba la evidencia que permitiría notarlo."""
        base = self.servidor({"id-a": "pienso<think>…</think>\nrespuesta de A",
                              "id-b": "respuesta de B"})
        d = self.salida()
        (d / "p.txt").write_text("¿cuál?\n")
        r = correr(f'bash "{SCRIPTS}/enjambre.sh" "{d}/p.txt" id-a:alfa id-b:beta', RAIZ,
                   COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", SALIDA=str(d))
        self.assertIn("respuesta de A", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("respuesta de B", r.stdout, f"\n{r.stdout}{r.stderr}")
        crudo = (d / "enj-alfa.out").read_text()
        self.assertIn("<think>", crudo,
                      "la salida cruda tiene que conservar el razonamiento: es la evidencia")

    def test_un_modelo_caido_no_se_lleva_el_enjambre_y_queda_marcado(self):
        """Medido: de 18 pedidos, 17 dieron 502. Si el primer 502 cortara la corrida, no
        habría enjambre nunca."""
        base = self.servidor({"id-b": "respuesta de B"})
        d = self.salida()
        (d / "p.txt").write_text("¿cuál?\n")
        r = correr(f'bash "{SCRIPTS}/enjambre.sh" "{d}/p.txt" id-a:alfa id-b:beta', RAIZ,
                   COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", SALIDA=str(d))
        self.assertIn("✗", r.stdout, f"el caído tiene que quedar marcado:\n{r.stdout}")
        self.assertIn("respuesta de B", r.stdout,
                      f"y el que contesta tiene que aparecer igual:\n{r.stdout}")

    def test_el_enjambre_no_llama_a_nadie_con_el_prompt_vacio(self):
        """Gastar modelos sobre un prompt vacío produce una tabla de respuestas a la nada, que
        es peor que un error: parece un dato."""
        base = self.servidor({"id-a": "no deberia"})
        d = self.salida()
        (d / "p.txt").write_text("")
        r = correr(f'bash "{SCRIPTS}/enjambre.sh" "{d}/p.txt" id-a:alfa', RAIZ,
                   COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", SALIDA=str(d))
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("no deberia", r.stdout)

    # ── conversar.sh: el quórum, y el insumo que no se arrastra

    def conversar(self, respuestas, d, rondas=1, **env):
        base = self.servidor(respuestas)
        (d / "ctx.txt").write_text("Hay que decidir algo.\n")
        return correr(f'bash "{SCRIPTS}/conversar.sh" "{d}/ctx.txt" {rondas} '
                      f'id-a:alfa id-b:beta id-c:gama', RAIZ,
                      COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", SALIDA=str(d), **env)

    VOTO = ("DECISION: usar-existente\nPORQUE: ya existe\n"
            "LINEA: usar la que está\n")

    def test_una_segunda_conversacion_no_hereda_los_votos_de_la_primera(self):
        """El defecto que encontré al traerlo al repo: `conversacion.md` se truncaba y
        `votos.txt` no, así que la segunda corrida contaba las posiciones de la primera como
        actuales. El chequeo de quórum y el de convergencia medían una mezcla de dos
        conversaciones y lo informaban como si fuera una — el mismo insumo contaminado que el
        chequeo de alcance que le cobraba a la tarea el trabajo de su hermana."""
        d = self.salida()
        primera = self.conversar({"id-a": self.VOTO, "id-b": self.VOTO, "id-c": self.VOTO}, d)
        self.assertIn("convergieron", primera.stdout, f"\n{primera.stdout}{primera.stderr}")
        # Ahora NADIE contesta: sin herencia, no puede haber quórum.
        segunda = self.conversar({}, d)
        self.assertIn("sin quórum", segunda.stdout,
                      f"heredó los votos de la conversación anterior:\n{segunda.stdout}")
        self.assertNotIn("convergieron", segunda.stdout, f"\n{segunda.stdout}")

    def test_unanimidad_sin_quorum_no_es_consenso(self):
        """El 2026-10-23 este chequeo cantó «✓ convergieron» con tres de cuatro participantes
        caídos por 502 y el cuarto repitiendo la plantilla del prompt."""
        d = self.salida()
        r = self.conversar({"id-a": self.VOTO}, d)
        self.assertIn("sin quórum", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("✓ convergieron", r.stdout, f"\n{r.stdout}")

    def test_un_modelo_que_copia_la_plantilla_no_cuenta_como_voto(self):
        """Lo que pasó de verdad: Qwen3.8-27B devolvió «usar-existente | crear-nueva» —la
        plantilla— y se registró como una posición legítima. Un formato que se puede repetir
        en vez de rellenar invita a eso."""
        d = self.salida()
        plantilla = ("DECISION: <escribí UNA de estas dos palabras: usar-existente | "
                     "crear-nueva>\nPORQUE: <una oración>\nLINEA: <la línea>\n")
        r = self.conversar({"id-a": self.VOTO, "id-b": self.VOTO, "id-c": plantilla}, d)
        self.assertIn("no respondió en el formato", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("sin quórum", r.stdout,
                      f"dos votos válidos de tres no alcanzan el quórum de 3:\n{r.stdout}")


class TestReplanificarSinCanalDeMemoria(unittest.TestCase):
    """`replan-sin-memoria.sh` arregla las contradicciones del preflight con un POST plano por
    cada rojo: 7 corridas con sesión de memoria, 1 completó, cortes entre los 7 y los 13
    minutos; por POST plano, 11 a 14 segundos. Lo que NO cambia son los jueces: el chequeo que
    encontró el problema sigue siendo el que acepta el arreglo.

    Tenía la ruta de una máquina y el proyecto de ejemplo escritos adentro, el modelo clavado
    por UUID y el respaldo del plan dentro del proyecto. Y no tenía tests: el camino más
    efectivo del método era el único sin medir."""

    def proyecto(self, linea="Guardar los datos en la tabla `users`."):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-replansm-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T26-registro.md").write_text(
            "# T26 — Registro\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/x.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\n" + linea + "\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE usuarios (id INT PRIMARY KEY);\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T26 | Registro | — | `app/x.py` | pendiente |\n")
        correr("git add -A && git commit -qm base", d)
        return d

    def servidor(self, respuesta):
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(n)
                if respuesta is None:
                    self.send_response(503); self.send_header("Content-Length", "2")
                    self.end_headers(); self.wfile.write(b"{}")
                    return
                cuerpo = json.dumps(
                    {"choices": [{"message": {"content": respuesta}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers(); self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def replanificar(self, d, respuesta):
        base = self.servidor(respuesta)
        salida = d.parent / "sin-memoria"
        return correr(f'PROYECTO=. MODELO=m1 bash "{SCRIPTS}/replan-sin-memoria.sh"', d,
                      COLABHIVE_BASE_URL=base, COLABHIVE_API_KEY="x", SALIDA=str(salida))

    def tarea(self, d):
        return (d / "tareas" / "T26-registro.md").read_text()

    def test_corrige_la_contradiccion_y_el_preflight_la_acepta(self):
        d = self.proyecto()
        r = self.replanificar(d, "Guardar los datos en la tabla `usuarios`.")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("ya no se contradice", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("usuarios", self.tarea(d))

    def test_el_prefijo_de_la_linea_lo_decide_el_ARCHIVO_y_no_el_modelo(self):
        """Tres intentos fallaron antes de la versión que quedó, los tres distinto: el modelo
        COMIÓ el «- » de un item y lo sacó de la lista; pidiéndoselo en el prompt lo AGREGÓ a
        un párrafo; y el `sed` de normalización usaba `\\|`, que anda en GNU sed y no en el BSD
        de macOS, así que no hacía nada. El modelo aporta el contenido, nunca la forma."""
        d = self.proyecto(linea="- Guardar los datos en la tabla `users`.")
        # El modelo devuelve la línea SIN el guión: el script tiene que reponerlo.
        r = self.replanificar(d, "Guardar los datos en la tabla `usuarios`.")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("- Guardar los datos en la tabla `usuarios`.", self.tarea(d),
                      f"perdió el prefijo del item:\n{self.tarea(d)}")

    def test_y_tampoco_le_agrega_un_prefijo_a_un_parrafo(self):
        """La sobre-corrección del segundo intento: el modelo devuelve un «- » que la línea no
        tenía y el párrafo se convierte en item."""
        d = self.proyecto()
        r = self.replanificar(d, "- Guardar los datos en la tabla `usuarios`.")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("\nGuardar los datos en la tabla `usuarios`.", self.tarea(d),
                      f"le agregó un prefijo que no tenía:\n{self.tarea(d)}")

    def test_una_respuesta_inutilizable_deja_el_plan_como_estaba(self):
        """Un arreglo a medias en tareas/ es peor que ninguno: la corrida siguiente arranca
        sobre algo que nadie revisó."""
        d = self.proyecto()
        antes = self.tarea(d)
        r = self.replanificar(d, "DECISION: no sé qué hacer")
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertEqual(antes, self.tarea(d), "la tarea tiene que quedar intacta")

    def test_si_la_plataforma_no_contesta_no_se_toca_el_plan(self):
        d = self.proyecto()
        antes = self.tarea(d)
        r = self.replanificar(d, None)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertEqual(antes, self.tarea(d))

    def test_no_deja_el_respaldo_del_plan_dentro_del_proyecto(self):
        """Estaba en `.tareas-previo` adentro de `$BASE`: si el script muere a mitad de camino,
        eso queda sin seguimiento en el tronco. Hoy un replanificador ya dejó 89 líneas de
        implementación ahí sin que nadie lo midiera."""
        # Se mide en el camino de FALLO: en el de éxito el script borra el respaldo igual,
        # así que un test sobre el éxito no distingue dónde estaba. La primera versión de este
        # test pasaba con el respaldo clavado adentro del proyecto.
        d = self.proyecto()
        r = self.replanificar(d, "DECISION: no sé qué hacer")
        self.assertNotEqual(0, r.returncode, "este test mide el camino de fallo")
        g = correr("git status --short", d)
        self.assertNotIn("tareas-previo", g.stdout,
                         f"dejó el respaldo sin seguimiento en el tronco:\n{g.stdout}")
        self.assertFalse((d / ".tareas-previo").exists())

    def test_el_juez_no_le_exige_arreglar_lo_que_el_actor_no_puede_tocar(self):
        """La primera versión del juez exigía CERO rojos y descartó un arreglo correcto: las
        líneas del enunciado quedaron bien en 3 segundos y el veredicto fue «se descarta»
        porque seguía apareciendo el rojo de un archivo ya commiteado, que replanificar no
        puede tocar. Un juez que pide lo imposible reprueba al que hizo bien su parte.

        El fixture tiene las dos clases de rojo a la vez: una contradicción de ENUNCIADO, que
        el actor sí arregla, y una de CÓDIGO —una tarea marcada hecha cuyo código consulta una
        tabla que nadie crea— que sólo se arregla reabriendo esa tarea."""
        d = self.proyecto()
        (d / "app").mkdir()
        (d / "app" / "registro.py").write_text(
            "def leer():\n    return db.execute('SELECT * FROM sesiones')\n")
        (d / "tareas" / "T27-sesion.md").write_text(
            "# T27 — Sesión\n\n**Estado:** ✅ hecha\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/registro.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer la sesión.\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "PLAN.md").write_text((d / "PLAN.md").read_text()
                                   + "| T27 | Sesión | — | `app/registro.py` | ✅ hecha |\n")
        correr("git add -A && git commit -qm t27", d)
        previo = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        self.assertIn("da por hecha la tabla", previo.stdout,
                      f"el fixture tiene que traer el rojo de ENUNCIADO:\n{previo.stdout}")
        self.assertIn("figura HECHA", previo.stdout,
                      f"y el de CÓDIGO que el actor no puede tocar:\n{previo.stdout}")
        r = self.replanificar(d, "Guardar los datos en la tabla `usuarios`.")
        self.assertEqual(0, r.returncode,
                         f"arregló lo suyo y el juez lo reprobó por lo ajeno:\n{r.stdout}{r.stderr}")
        self.assertIn("usuarios", self.tarea(d))

    def test_tambien_trata_los_rojos_de_COLUMNA(self):
        """Este script nació para los rojos de tabla, y desde el 2026-10-24 el preflight
        también da rojos de columna: sin esto decía «no pude ubicar archivo o tabla» y el rojo
        se quedaba sin nadie que lo trate.

        Y el canal plano es el vehículo correcto para los dos. El router con arnés le pide
        escribir al modelo del agente `arquitecto`, que está MEDIDO como el que no escribe
        —«Qwen3.8-27B razonamiento 6/6 · replanificando NO llamó a write»—. Ante este mismo
        rojo se pasó el turno citando el prompt y razonándolo frase por frase, llegó a la
        conclusión correcta y se le acabó antes de actuar."""
        d = self.proyecto(linea="Filtro por columna `categoria`.")
        m = d / "migraciones" / "001_initial.sql"
        m.write_text("CREATE TABLE usuarios (id INT PRIMARY KEY);\n"
                     "CREATE TABLE anuncios (\n    id INT, categoria_id INT\n);\n")
        previo = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        self.assertIn("nombra la columna", previo.stdout,
                      f"el fixture tiene que traer el rojo de columna:\n{previo.stdout}")
        r = self.replanificar(d, "Filtro por columna `categoria_id`.")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("categoria_id", self.tarea(d), f"\n{self.tarea(d)}")

    def test_al_modelo_le_pasa_el_esquema_de_COLUMNAS_y_no_el_de_tablas(self):
        """El menú tiene que ser del problema: un arquitecto al que se le pide arreglar una
        columna con la lista de tablas adivina."""
        d = self.proyecto(linea="Filtro por columna `categoria`.")
        m = d / "migraciones" / "001_initial.sql"
        m.write_text("CREATE TABLE usuarios (id INT PRIMARY KEY);\n"
                     "CREATE TABLE anuncios (\n    id INT, categoria_id INT\n);\n")
        self.replanificar(d, "Filtro por columna `categoria_id`.")
        enviado = (d.parent / "sin-memoria" / "in.txt").read_text()
        self.assertIn("Columnas que las migraciones YA crean", enviado, f"\n{enviado[:300]}")
        self.assertIn("categoria_id", enviado, f"\n{enviado[:300]}")
        self.assertIn("agregar la que nombra", enviado,
                      f"la salida (b) de un rojo de columna:\n{enviado[:400]}")

    def test_el_juez_final_tambien_mira_los_rojos_de_columna(self):
        """Miraba sólo «da por hecha la tabla», así que un rojo de columna sin corregir pasaba
        por el juez sin que nadie lo notara: el chequeo que acepta el arreglo tiene que cubrir
        lo mismo que el que lo pidió."""
        d = self.proyecto(linea="Filtro por columna `categoria`.")
        m = d / "migraciones" / "001_initial.sql"
        m.write_text("CREATE TABLE usuarios (id INT PRIMARY KEY);\n"
                     "CREATE TABLE anuncios (\n    id INT, categoria_id INT\n);\n")
        antes = self.tarea(d)
        # El modelo "corrige" a otra columna que TAMPOCO existe: el juez tiene que descartar.
        r = self.replanificar(d, "Filtro por columna `inventada`.")
        self.assertNotEqual(0, r.returncode,
                            f"aceptó un arreglo que deja el rojo vivo:\n{r.stdout}{r.stderr}")
        self.assertEqual(antes, self.tarea(d), "y tiene que restaurar el enunciado")

    def test_sin_rojos_no_gasta_un_modelo(self):
        d = self.proyecto(linea="Guardar los datos en la tabla `usuarios`.")
        r = self.replanificar(d, "NO DEBERIA LLAMARSE")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("nada que replanificar", r.stdout, f"\n{r.stdout}")
        self.assertNotIn("NO DEBERIA", self.tarea(d))

    def test_ni_la_ruta_ni_el_proyecto_ni_el_modelo_estan_clavados(self):
        """El script decía «replanifica el preflight» y replanificaba UN proyecto, en UNA casa,
        contra UN uuid. Estos tests corren sobre un proyecto de juguete: si la ruta volviera a
        estar clavada, ninguno de los de arriba pasaría. Esto fija las tres fuentes."""
        fuente = (SCRIPTS / "replan-sin-memoria.sh").read_text()
        codigo = [l for l in fuente.splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        self.assertEqual([], [l for l in codigo if "/Users/" in l],
                         "volvió una ruta absoluta de una máquina")
        self.assertIn("ubicar_proyecto", fuente)
        self.assertIn("modelo_del_agente ejecutor", fuente)


class TestElEntornoDeLaPlataformaNoPisaAQuienLlama(unittest.TestCase):
    """Siete scripts tenían `[ -f ~/.config/colabhive/env ] && . ~/.config/colabhive/env`
    copiado, y corría DESPUÉS de recibir el entorno: pisaba el `COLABHIVE_BASE_URL` que le
    pasó quien los llama.

    La consecuencia no es un detalle de estilo: ninguno de los siete se podía apuntar a otra
    plataforma, así que ninguno se podía medir. El canal sin memoria —lo que arregla una
    contradicción del plan en 11-14 segundos, contra los 7-13 minutos del arnés con memoria—
    estuvo sin un solo test por esto, y su primer test le pegó a la plataforma REAL con un id
    de juguete y recibió un 404. Lo intestable es lo que se rompe sin que nadie se entere."""

    def casa(self, url="http://del-archivo", clave="clave-del-archivo"):
        """Un HOME de juguete con el archivo de entorno que los scripts leen."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-entorno-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / ".config" / "colabhive").mkdir(parents=True)
        (d / ".config" / "colabhive" / "env").write_text(
            f'export COLABHIVE_BASE_URL="{url}"\nexport COLABHIVE_API_KEY="{clave}"\n')
        return d

    def cargar(self, casa, **env):
        """Arranca de un entorno LIMPIO salvo lo que el test ponga a propósito.

        La primera versión heredaba las variables de quien corre la suite, así que «lo que ya
        viene seteado gana» tomaba la plataforma de producción y el test medía la máquina en
        vez del cargador. Es, literalmente, el defecto que esta clase persigue, cometido en su
        propio andamio: el entorno de afuera decidiendo el resultado.

        Y la CLAVE no se imprime: se compara adentro del shell y sale «si» o «no». La primera
        versión la echaba, y el mensaje de una falla la dejó escrita en la salida de la
        suite. Un andamio no tiene por qué manipular el secreto para medir que llegó."""
        env.setdefault("COLABHIVE_BASE_URL", "")
        env.setdefault("COLABHIVE_API_KEY", "")
        return correr(f'. {SCRIPTS}/_comun.sh >/dev/null 2>&1; cargar_entorno_colabhive; '
                      f'echo "rc=$?"; echo "URL=${{COLABHIVE_BASE_URL:-}}"; '
                      f'echo "CLAVE_DEL_ARCHIVO=$([ "${{COLABHIVE_API_KEY:-}}" = '
                      f'"clave-del-archivo" ] && echo si || echo no)"',
                      RAIZ, HOME=str(casa), **env)

    def test_lo_que_ya_viene_seteado_gana(self):
        r = self.cargar(self.casa(), COLABHIVE_BASE_URL="http://del-invocante")
        self.assertIn("URL=http://del-invocante", r.stdout,
                      f"el archivo pisó a quien llama:\n{r.stdout}{r.stderr}")

    def test_lo_que_falta_lo_rellena_el_archivo(self):
        """El otro lado: si el cargador no rellenara nada, los scripts no andarían a mano."""
        r = self.cargar(self.casa())
        self.assertIn("URL=http://del-archivo", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("CLAVE_DEL_ARCHIVO=si", r.stdout, f"\n{r.stdout}{r.stderr}")

    def test_mezcla_las_dos_fuentes_sin_perder_ninguna(self):
        """El caso de una medición real: la URL apunta al servidor de prueba y la clave sale
        de la config, porque el servidor de prueba no valida nada pero el script la exige."""
        r = self.cargar(self.casa(), COLABHIVE_BASE_URL="http://del-invocante")
        self.assertIn("URL=http://del-invocante", r.stdout, f"\n{r.stdout}")
        self.assertIn("CLAVE_DEL_ARCHIVO=si", r.stdout, f"\n{r.stdout}")

    def test_devuelve_cero_aunque_haya_rellenado(self):
        """El invariante: un cargador de entorno nunca informa falla por haber hecho su
        trabajo. Nueve scripts lo llaman y varios lo encadenan.

        Lo que este test NO prueba es que el `return 0` del final sea necesario: lo medí
        quitándolo y queda verde, porque el `export` de la línea anterior ya devuelve 0. Mi
        comentario en `_comun.sh` afirmaba lo contrario y lo corregí. Vale decirlo acá: un
        test cuya prosa promete más de lo que mide es confianza falsa."""
        self.assertIn("rc=0", self.cargar(self.casa()).stdout)
        self.assertIn("rc=0", self.cargar(self.casa(),
                                          COLABHIVE_BASE_URL="http://x").stdout)

    def test_sin_archivo_no_falla_ni_inventa(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-entorno-vacia-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        r = self.cargar(d, COLABHIVE_BASE_URL="http://del-invocante")
        self.assertIn("rc=0", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertIn("URL=http://del-invocante", r.stdout, f"\n{r.stdout}")

    def test_ningun_script_sourcea_el_entorno_a_mano(self):
        """Una regla con nueve lectores no se copia nueve veces: así es como una queda vieja y
        nadie se entera. Es la forma que este repo repite y que hoy ya costó tres defectos."""
        culpables = []
        for s in sorted(SCRIPTS.glob("*.sh")):
            if s.name == "_comun.sh":
                continue
            for linea in s.read_text().splitlines():
                if "config/colabhive/env" in linea and not linea.strip().startswith("#"):
                    culpables.append(f"{s.name}: {linea.strip()[:60]}")
        self.assertEqual([], culpables,
                         "volvió la copia del cargador de entorno; usá "
                         f"cargar_entorno_colabhive: {culpables}")


class TestLaFotoDelAlcanceNoRevientaConElWorktreeLimpio(unittest.TestCase):
    """`grep -c .` imprime `0` Y SALE CON 1 cuando no hay líneas, así que el `|| echo 0` que
    tenía al lado disparaba TAMBIÉN y la variable quedaba con «0\\n0». El `[ -gt ]` reventaba
    con «[: 0 0: integer expression expected».

    Y pasaba en el caso MÁS COMÚN —el worktree limpio—, así que el aviso «el worktree ya traía
    N archivos cambiados» no podía imprimirse nunca y en su lugar salía un error de bash en el
    log de la corrida. Una medición que no mide y encima ensucia la evidencia que uno lee
    después para diagnosticar.

    Lo destapó la corrida REAL de T05c, no esta suite: ningún test miraba esa línea. Por eso
    este test extrae las dos líneas DEL SCRIPT y las corre: un test que copia el código mide
    la copia."""

    def bloque(self):
        """Las líneas del script que calculan e informan `heredados`, tal como están."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        lineas = [l for l in fuente.splitlines()
                  if l.strip().startswith("heredados=") or '"$heredados" -gt 0' in l]
        self.assertEqual(2, len(lineas), f"no encontré las dos líneas: {lineas}")
        return "wt=\"$1\"\n" + "\n".join(l.strip() for l in lineas) + '\necho FIN\n'

    def correr_con(self, contenido):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-foto-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / ".sucio-antes").write_text(contenido)
        guion = d / "g.sh"
        guion.write_text(self.bloque())
        return correr(f'bash "{guion}" "{d}"', RAIZ)

    def test_con_el_worktree_limpio_no_dice_nada_y_no_revienta(self):
        r = self.correr_con("")
        self.assertIn("FIN", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("integer expression", r.stderr,
                         f"revienta con el caso más común:\n{r.stderr}")
        self.assertNotIn("el worktree ya traía", r.stdout,
                         "no había nada heredado: no hay nada que avisar")

    def test_con_archivos_heredados_los_cuenta_y_lo_dice(self):
        """El otro lado: el aviso existe porque el chequeo de alcance RESTA esos archivos, y
        quien lee el log tiene que saber que se restaron."""
        r = self.correr_con("app/a.py\napp/b.py\n")
        self.assertIn("2 archivo(s)", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("integer expression", r.stderr, f"\n{r.stderr}")


class TestLasColumnasTambienSeCruzanContraLaMigracion(unittest.TestCase):
    """El chequeo de tablas mira un nivel y faltaba el de abajo. Medido el 2026-10-24 contra
    ejemplo-clasificados, SEIS columnas inventadas en tres archivos, los tres de tareas con
    gate VERDE:

        anuncios.categoria        la tabla tiene `categoria_id`     (T28, hecha)
        usuarios.password_hash    la tabla tiene `clave_hash`       (T26, hecha)
        mensajes.remitente_id     la tabla tiene `de_usuario_id`    (T20, cerrada HOY)
        mensajes.destinatario_id  la tabla tiene `a_usuario_id`
        mensajes.contenido        la tabla tiene `cuerpo`
        mensajes.fecha_envio      la tabla tiene `creado_en`

    Ninguno de esos códigos puede correr, y los tres pasaron su gate porque sus tests simulan
    la base: nadie comparaba la consulta contra el esquema. Lo encontró el ejecutor de OTRA
    tarea, al que el guardia de alcance frenó por tocar un archivo ajeno —estaba corrigiendo
    `categoria` por `categoria_id`—: el método tenía el dato adentro de un rechazo y lo tiraba.

    La mitad de estos tests son de FALSOS ROJOS a propósito. Un rojo de este chequeo detiene
    el plan, así que lo que hay que medir no es sólo que vea el defecto: es que se calle
    cuando no puede afirmar nada."""

    def proyecto(self, consulta, estado="pendiente", esquema="id INT, nombre VARCHAR(50)"):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-cols-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-cosas.md").write_text(
            f"# T01 — Cosas\n\n**Estado:** {estado}\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer cosas.\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            f"CREATE TABLE cosas (\n    {esquema}\n);\n")
        (d / "app" / "datos").mkdir(parents=True)
        (d / "app" / "datos" / "cosas.py").write_text(
            f'def leer():\n    return db.execute({consulta!r})\n')
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            f"| T01 | Cosas | — | `app/datos/cosas.py` | {estado} |\n")
        return d

    def coherencia(self, d):
        return correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)

    # ── lo que TIENE que ver

    def test_una_columna_que_la_migracion_no_crea_con_la_tarea_cerrada_es_rojo(self):
        d = self.proyecto("SELECT id, titulo FROM cosas", estado="✅ hecha")
        r = self.coherencia(d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("cosas.titulo", r.stdout, f"\n{r.stdout}")
        self.assertIn("REABRIR T01", r.stdout,
                      f"una tarea cerrada con código que no puede correr se REABRE, no se "
                      f"parchea desde otra:\n{r.stdout}")

    def test_el_veredicto_dice_qué_columnas_tiene_la_tabla(self):
        """Y no una adivinanza por parecido. Medido: para `destinatario_id` el `difflib`
        sugería `de_usuario_id` y para `remitente_id` sugería `a_usuario_id` —las dos
        INVERTIDAS—. Una pista equivocada adentro de un veredicto es peor que ninguna."""
        d = self.proyecto("SELECT id, titulo FROM cosas", estado="✅ hecha")
        r = self.coherencia(d)
        self.assertIn("La tabla tiene:", r.stdout, f"\n{r.stdout}")
        self.assertIn("`nombre`", r.stdout, f"\n{r.stdout}")

    def test_las_columnas_de_un_INSERT_tambien_se_cruzan(self):
        """La otra superficie explícita, y la del cadáver de `users_register.py`:
        `INSERT INTO usuarios (email, password_hash)` contra una tabla con `clave_hash`."""
        d = self.proyecto("INSERT INTO cosas (id, inventada) VALUES (%s, %s)",
                          estado="✅ hecha")
        r = self.coherencia(d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("cosas.inventada", r.stdout, f"\n{r.stdout}")

    def test_con_la_tarea_pendiente_avisa_pero_no_detiene_el_plan(self):
        """La tarea que declara el archivo va a correr y su gate la va a juzgar: detener el
        plan acá sería impedir su propio arreglo. Misma regla que el chequeo de tablas."""
        d = self.proyecto("SELECT id, titulo FROM cosas", estado="pendiente")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode,
                         f"con dueño pendiente el plan puede arrancar:\n{r.stdout}{r.stderr}")
        self.assertIn("cosas.titulo", r.stdout, f"pero tiene que decirlo:\n{r.stdout}")

    # ── lo que tiene que CALLAR, que es la mitad del valor

    def test_un_asterisco_no_afirma_ninguna_columna(self):
        d = self.proyecto("SELECT * FROM cosas", estado="✅ hecha")
        self.assertEqual(0, self.coherencia(d).returncode)

    def test_un_JOIN_no_permite_saber_de_qué_tabla_viene_la_columna(self):
        d = self.proyecto("SELECT id, otra FROM cosas JOIN otras ON cosas.id = otras.id",
                          estado="✅ hecha")
        # La tabla del JOIN también tiene que existir, o salta el chequeo de TABLAS y este
        # test mediría esa otra dimensión. Mi primera versión no la creaba y el rojo que
        # obtuve era correcto, pero de otro chequeo.
        m = d / "migraciones" / "001_initial.sql"
        m.write_text(m.read_text() + "CREATE TABLE otras (\n    id INT, otra INT\n);\n")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")

    def test_una_funcion_o_un_alias_en_la_lista_hacen_callar_al_chequeo(self):
        for consulta in ("SELECT COUNT(id) FROM cosas",
                         "SELECT id AS clave FROM cosas",
                         "SELECT cosas.id FROM cosas"):
            with self.subTest(consulta=consulta):
                d = self.proyecto(consulta, estado="✅ hecha")
                r = self.coherencia(d)
                self.assertEqual(0, r.returncode, f"{consulta}:\n{r.stdout}{r.stderr}")

    def test_una_columna_agregada_por_ALTER_TABLE_existe(self):
        """Sin esto, una migración posterior que agrega un campo deja al chequeo acusando al
        código que lo usa: el defecto tendría el sujeto exactamente invertido."""
        d = self.proyecto("SELECT id, extra FROM cosas", estado="✅ hecha")
        (d / "migraciones" / "002_extra.sql").write_text(
            "ALTER TABLE cosas ADD COLUMN extra INT NOT NULL;\n")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")

    def test_los_parentesis_anidados_del_esquema_no_se_comen_columnas(self):
        """`VARCHAR(255)` y `FOREIGN KEY (x) REFERENCES y(id)` anidan paréntesis. Un regex
        perezoso corta el cuerpo del CREATE TABLE en el primer `)` y pierde la mitad de las
        columnas — y un chequeo de columnas que no ve todas las columnas no informa de menos:
        INVENTA rojos. Por eso el delimitador es un contador de paréntesis."""
        d = self.proyecto("SELECT id, nombre, precio FROM cosas", estado="✅ hecha",
                          esquema=("id INT AUTO_INCREMENT PRIMARY KEY,\n"
                                   "    nombre VARCHAR(255) NOT NULL,\n"
                                   "    precio DECIMAL(10,2) NOT NULL,\n"
                                   "    FOREIGN KEY (id) REFERENCES otras(id)"))
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode,
                         f"se comió columnas del esquema y acusó al código:\n{r.stdout}")

    def test_sin_migraciones_el_chequeo_no_opina(self):
        """Un chequeo que no puede medir no opina: la misma regla que el método aplica a los
        corredores de tests. Sin esquema no hay con qué comparar."""
        d = self.proyecto("SELECT id, titulo FROM cosas", estado="✅ hecha")
        shutil.rmtree(d / "migraciones")
        self.assertEqual(0, self.coherencia(d).returncode)


class TestReabrirUnaTareaConVeredictoFalso(unittest.TestCase):
    """`coherencia.py` termina sus rojos más graves con «Su gate dio un veredicto falso: ese
    código no puede funcionar. Hay que REABRIR TNN, no parchear a mano» — y el método no tenía
    con qué. Ordenaba una operación y dejaba su ejecución a mano, que es de donde este repo
    dice, en varios comentarios, que vienen sus defectos.

    Reabrir son cuatro cosas, y hacer tres está peor que no hacer ninguna: el estado en el
    archivo, el estado en la tabla del plan, sacar el código que la tarea produjo, y dejar
    escrito por qué. Estos tests miden las cuatro por separado, porque la que se olvide va a
    ser la que deje la tarea en un estado que ningún lector entiende igual."""

    def proyecto(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-reabrir-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T07-cosas.md").write_text(
            "# T07 — Cosas\n\n**Estado:** ✅ hecha\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer cosas.\n\n"
            "## Tests\n\nArchivo: `tests/test_cosas.py`, clase `TestCosas`\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE cosas (\n    id INT, nombre VARCHAR(50)\n);\n")
        (d / "app" / "datos").mkdir(parents=True)
        (d / "app" / "datos" / "cosas.py").write_text(
            "def leer():\n    return db.execute('SELECT id, titulo FROM cosas')\n")
        (d / "tests").mkdir()
        (d / "tests" / "test_cosas.py").write_text(
            "class TestCosas:\n    def test_algo(self):\n        assert True\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T07 | Cosas | — | `app/datos/cosas.py` | ✅ hecha |\n")
        correr("git add -A && git commit -qm base", d)
        return d

    def reabrir(self, d, motivo="su código consulta una columna que la migración no crea"):
        return correr(f'PROYECTO=. bash "{SCRIPTS}/reabrir.sh" T07 {shlex.quote(motivo)}', d)

    def test_el_estado_queda_pendiente_en_el_archivo_Y_en_la_tabla(self):
        """Marcar uno solo deja la tarea invisible para el otro lector: `validar-plan.py`
        cruza las dos declaraciones y el deductor de etapas lee la tabla. Ya pasó al revés
        —T01 se integró, quedó verde en el tronco, y la etapa 1 la volvía a lanzar—."""
        d = self.proyecto()
        r = self.reabrir(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        tarea = (d / "tareas" / "T07-cosas.md").read_text()
        self.assertIn("**Estado:** pendiente", tarea, f"\n{tarea[:200]}")
        self.assertNotIn("✅", tarea.split("## Objetivo")[0],
                         "el encabezado no puede seguir diciendo hecha")
        plan = (d / "PLAN.md").read_text()
        self.assertNotIn("✅ hecha", plan, f"la tabla del plan quedó en hecha:\n{plan}")
        self.assertIn("pendiente", plan, f"\n{plan}")

    def test_saca_del_tronco_el_codigo_que_la_tarea_declara(self):
        """La fase que escribe los tests valida que el test FALLE antes de que exista la
        implementación. Con el código viejo en su lugar el test pasa de entrada y el gate
        concluye «el test no prueba nada»: el diagnóstico equivocado."""
        d = self.proyecto()
        r = self.reabrir(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertFalse((d / "app" / "datos" / "cosas.py").exists(),
                         "el código declarado tiene que salir del tronco")
        self.assertFalse((d / "tests" / "test_cosas.py").exists(),
                         "y su test también: si codifica el error, obliga a reproducirlo")

    def test_el_codigo_sacado_no_se_pierde(self):
        """Sacar no es tirar: es la evidencia de qué dio verde siendo falso."""
        d = self.proyecto()
        self.reabrir(d)
        guardado = d.parent / "reabrir-T07-previo" / "codigo" / "app" / "datos" / "cosas.py"
        self.assertTrue(guardado.exists(), f"no quedó copia; hay en {d.parent}: "
                                           f"{[p.name for p in d.parent.iterdir()]}")
        self.assertIn("SELECT id, titulo", guardado.read_text())

    def test_deja_escrito_por_que_se_reabrio(self):
        d = self.proyecto()
        self.reabrir(d, motivo="la columna titulo no existe en la tabla")
        tarea = (d / "tareas" / "T07-cosas.md").read_text()
        self.assertIn("## Reabierta", tarea, f"\n{tarea[-400:]}")
        self.assertIn("la columna titulo no existe", tarea, f"\n{tarea[-400:]}")

    def test_la_nota_no_mete_identificadores_entre_backticks(self):
        """Los chequeos leen los identificadores entre backticks de un enunciado como un
        COMPROMISO de usarlos: una nota de reapertura que nombraba así la tabla equivocada
        hizo que el chequeo de coherencia la tomara por una promesa del enunciado y el rojo se
        duplicara. La nota informa a una persona, no declara un contrato."""
        d = self.proyecto()
        self.reabrir(d, motivo="la tabla `users` no existe: es `usuarios`")
        # Hasta la SIGUIENTE sección, no hasta el final del archivo. La extracción asumía
        # que la nota era lo último, que es donde la escribía `>>`; desde que va arriba, un
        # slice al final del archivo se lleva el resto del enunciado con sus backticks y el
        # test medía otra cosa. Un extractor que depende de la posición de su sujeto se rompe
        # cuando el sujeto se mueve, y acá se movió a propósito.
        resto = (d / "tareas" / "T07-cosas.md").read_text().split("## Reabierta")[1]
        nota = resto.split("\n## ")[0]
        self.assertNotIn("`", nota, f"la nota metió backticks:\n{nota}")
        self.assertIn("users", nota, "pero el dato tiene que seguir estando")
        # El `split` de arriba consume UN `\n`, así que la nota termina con `\n` sólo si
        # había una línea en blanco antes del `## `. Buscar `\n\n## ` en todo el resto no
        # medía esto: lo encontraba en cualquier otra sección del archivo y pasaba con la
        # línea en blanco sacada.
        self.assertTrue(nota.endswith("\n"),
                        f"la nota tiene que quedar separada de la sección siguiente por una"
                        f" línea en blanco, o el enunciado se lee mal:\n{nota[-200:]!r}")

    def test_mide_los_rojos_antes_y_despues_y_los_informa(self):
        """La reapertura tiene un juez: si AGREGA contradicciones, se revierte entera. Lo que
        este test mide es que la comparación OCURRA y se informe, no la rama de reversión.

        Y lo digo porque no encontré estímulo realista para esa rama, después de dos intentos,
        y las dos veces porque el método ya estaba bien:

          · un motivo que prometía una tabla inexistente no agrega nada, porque el script le
            saca los backticks a la nota y los chequeos exigen el identificador entre
            backticks para leerlo como promesa del enunciado;
          · sacar del tronco un módulo del que otra tarea PENDIENTE importa tampoco, porque al
            reabrirla la tarea vuelve a ser su dueña declarada y el cruce de imports la cuenta
            como proveedora.

        Así que la reversión queda como red defensiva, sin cobertura, y queda dicho. Un test
        que fabrica un estímulo artificial para tocar una rama mide el estímulo, no la rama."""
        d = self.proyecto()
        # Un SEGUNDO rojo que la reapertura de T07 no toca: así el «después» no puede ser
        # cero, y el número informado se puede comparar con el real. Sin esto, con el contador
        # clavado en 0 el renglón salía igual y mi test no medía nada: lo mostró mutar.
        (d / "app" / "datos" / "otras.py").write_text(
            "def leer():\n    return db.execute('SELECT id, inventada FROM cosas')\n")
        (d / "tareas" / "T09-otras.md").write_text(
            "# T09 — Otras\n\n**Estado:** ✅ hecha\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/otras.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer otras.\n\n## Terminado cuando\n\n- [ ] anda\n")
        plan = d / "PLAN.md"
        plan.write_text(plan.read_text()
                        + "| T09 | Otras | — | `app/datos/otras.py` | ✅ hecha |\n")
        correr("git add -A && git commit -qm t09", d)
        r = self.reabrir(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        real = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        quedan = len([l for l in real.stdout.splitlines() if "✗" in l])
        self.assertRegex(r.stdout, rf"rojos del preflight: \d+ → {quedan}\b",
                         f"el número que informa tiene que ser el que mide de verdad "
                         f"(quedan {quedan}):\n{r.stdout}")
        self.assertGreater(quedan, 0,
                           "si no quedara ninguno, este test no distinguiría un contador "
                           "clavado en cero")

    def test_sin_la_tarea_no_hace_nada_y_lo_dice(self):
        d = self.proyecto()
        r = correr(f'PROYECTO=. bash "{SCRIPTS}/reabrir.sh" T99 x', d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("no existe", r.stdout + r.stderr)


class TestElQueProveeUnImportCorreAntesDelQueLoConsume(unittest.TestCase):
    """El cruce de imports pregunta si ALGUIEN provee el símbolo. Esto pregunta si lo provee
    EN SU MOMENTO, que no es lo mismo y es lo que decide si la corrida sirve.

    Cadáver del 2026-10-24, y es mío: decidí que `GET /ads` de T05c liste con
    `buscar_anuncios`, que es de T28, y no declaré esa dependencia. El cruce daba VERDE —T28
    lo provee— y el deductor de etapas puso las dos en la MISMA etapa, en paralelo, contra un
    módulo que no estaba en el tronco. El agente de T05c habría chocado con un ImportError y
    el veredicto habría nombrado a T05c.

    Es la familia que `_etapas.py` ya atiende para choques de archivo —«paralelizaba tareas que
    sí chocan»— sin el equivalente para imports. El deductor ordena por `Depende de`: si la
    dependencia no está declarada, no hay nada que ordenar."""

    def proyecto(self, deps_consumidor="—", estado_proveedor="pendiente", en_tronco=False):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-orden-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        # El proveedor declara la función en su contrato.
        (d / "tareas" / "T30-provee.md").write_text(
            f"# T30 — Provee\n\n**Estado:** {estado_proveedor}\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/servicios/busca.py\n"
            "**Prohibido tocar:** Ninguno\n\n## Objetivo\n\nBuscar.\n\n"
            "## Contrato\n\n```python\ndef buscar(texto):\n    ...\n```\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        # El consumidor lo nombra EN PROSA, que es la forma que el método pide.
        (d / "tareas" / "T31-consume.md").write_text(
            f"# T31 — Consume\n\n**Estado:** pendiente\n**Depende de:** {deps_consumidor}\n"
            "**Archivos que podés tocar:** app/rutas/busca.py\n"
            "**Prohibido tocar:** Ninguno\n\n## Objetivo\n\nExponer la búsqueda.\n\n"
            "- Llama a `buscar(None)` del módulo `app/servicios/busca.py`\n"
            "  (import exacto: `from app.servicios.busca import buscar`).\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        if en_tronco:
            (d / "app" / "servicios").mkdir(parents=True)
            (d / "app" / "servicios" / "busca.py").write_text("def buscar(texto):\n    return []\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            f"| T30 | Provee | — | `app/servicios/busca.py` | {estado_proveedor} |\n"
            f"| T31 | Consume | {deps_consumidor} | `app/rutas/busca.py` | pendiente |\n")
        return d

    def coherencia(self, d):
        return correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)

    def test_sin_la_dependencia_declarada_es_rojo_y_nombra_a_las_dos(self):
        d = self.proyecto(deps_consumidor="—")
        r = self.coherencia(d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("T31 importa `buscar`", r.stdout, f"\n{r.stdout}")
        self.assertIn("T30", r.stdout, f"tiene que nombrar al proveedor:\n{r.stdout}")
        self.assertIn("ImportError", r.stdout,
                      f"y decir a quién se le va a cobrar el error:\n{r.stdout}")

    def test_con_la_dependencia_declarada_no_dice_nada(self):
        d = self.proyecto(deps_consumidor="T30")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("orden:", r.stdout, f"\n{r.stdout}")

    def test_la_dependencia_TRANSITIVA_alcanza(self):
        """Si T31 depende de T32 y T32 de T30, el deductor ya pone T30 antes: exigir la arista
        directa sería un falso rojo, y un falso rojo en el preflight cuesta una corrida."""
        d = self.proyecto(deps_consumidor="T32")
        (d / "tareas" / "T32-medio.md").write_text(
            "# T32 — Medio\n\n**Estado:** pendiente\n**Depende de:** T30\n"
            "**Archivos que podés tocar:** app/servicios/medio.py\n"
            "**Prohibido tocar:** Ninguno\n\n## Objetivo\n\nAlgo.\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        plan = d / "PLAN.md"
        plan.write_text(plan.read_text()
                        + "| T32 | Medio | T30 | `app/servicios/medio.py` | pendiente |\n")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode, f"la transitiva tiene que alcanzar:\n{r.stdout}")

    def test_si_el_modulo_ya_esta_en_el_tronco_no_hay_orden_que_exigir(self):
        """El consumidor puede correr: el módulo está. Que el proveedor lo reescriba después es
        otra cosa, y la juzga su propio gate."""
        d = self.proyecto(deps_consumidor="—", en_tronco=True)
        self.assertEqual(0, self.coherencia(d).returncode)

    def test_si_el_proveedor_ya_esta_hecho_tampoco(self):
        d = self.proyecto(deps_consumidor="—", estado_proveedor="✅ hecha", en_tronco=True)
        self.assertEqual(0, self.coherencia(d).returncode)

    def test_el_cruce_lee_los_imports_escritos_en_prosa(self):
        """No es una forma suelta: es la que el método PIDE. El prompt del replanificador dice
        «decí DÓNDE vive cada cosa: archivo exacto, import exacto», el arquitecto obedece y lo
        escribe entre backticks en el cuerpo — y el cruce leía sólo lo que estaba adentro de
        `## Contrato`. El método pedía una forma y después no la leía."""
        d = self.proyecto(deps_consumidor="—")
        r = self.coherencia(d)
        self.assertIn("buscar", r.stdout,
                      f"el import de la prosa tiene que entrar al cruce:\n{r.stdout}")

    def test_dice_cuántas_tareas_no_pudo_cruzar(self):
        """Medido el 2026-10-24: en pacman 19 de 19 tareas no declaran ningún import, y el
        veredicto decía «✓ 19 tareas cruzadas: ningún import huérfano». El ✓ hablaba de un
        trabajo que no hizo. Un chequeo que no puede medir no dice verde: dice cuánto midió."""
        d = self.proyecto(deps_consumidor="T30")
        r = self.coherencia(d)
        self.assertIn("cobertura:", r.stdout,
                      f"T30 no declara imports: eso tiene que figurar:\n{r.stdout}")
        self.assertIn("1 de 2", r.stdout, f"\n{r.stdout}")

    def test_un_modulo_escrito_con_la_raiz_del_corredor_no_es_un_huerfano(self):
        """`from app.main import app` para `backend/app/main.py`: los enunciados escriben el
        import como lo ve el corredor de tests, cuyo rootdir es `backend/`. Resolver sólo
        contra la raíz del proyecto daba dos rojos FALSOS en cuanto el cruce empezó a leer la
        prosa — y el chequeo viejo tenía la misma debilidad, latente."""
        d = self.proyecto(deps_consumidor="T30")
        (d / "backend" / "app").mkdir(parents=True)
        (d / "backend" / "app" / "main.py").write_text("app = object()\n")
        t = d / "tareas" / "T31-consume.md"
        t.write_text(t.read_text() + "\nEl test hace `from app.main import app`.\n")
        r = self.coherencia(d)
        self.assertEqual(0, r.returncode,
                         f"el archivo existe en backend/app/main.py:\n{r.stdout}{r.stderr}")


class TestLaTemperaturaNoLaElijeElServidor(unittest.TestCase):
    """Medido el 2026-10-24 contra el ejecutor real: sin mandar `temperature`, cinco llamadas
    al MISMO prompt dieron dos respuestas distintas —`cantidad_de_avisos` tres veces y
    `cantidad_avisos` dos—. Con `temperature: 0`, las cinco idénticas. La plataforma no usa
    greedy por omisión y veníamos corriendo con un valor que nadie eligió.

    Lo que eso rompe no es sólo el acierto —Udgam Labs midió que pasar de greedy a 0,7 le bajó
    el acierto de llamadas a herramientas de 60% a 46%— sino EL BRAZO DE CONTROL, que es el
    instrumento con el que este método decide si un resultado se le puede atribuir a un
    modelo: `comparar-modelos.sh` razona sobre «salidas idénticas carácter por carácter en dos
    tandas separadas por horas». Con temperatura no nula, eso era suerte.

    Y queda como perilla porque hay un caso donde la diversidad es el punto: el best-of-N con
    verificador. 48 intentos a temperatura 0 son el mismo intento 48 veces."""

    def servidor(self):
        """Un `/chat/completions` que DEVUELVE la temperatura que recibió."""
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                pedido = json.loads(self.rfile.read(n).decode("utf-8", "replace"))
                visto = repr(pedido.get("temperature", "AUSENTE"))
                cuerpo = json.dumps(
                    {"choices": [{"message": {"content": f"temperatura={visto}"}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def pedir(self, **env):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-temp-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "p.txt").write_text("¿cuál?\n")
        return correr(f'python3 "{SCRIPTS}/pedir.py" m1 < "{d}/p.txt"', RAIZ,
                      COLABHIVE_BASE_URL=self.servidor(), COLABHIVE_API_KEY="x", **env)

    def test_por_omision_manda_cero_y_no_la_deja_al_servidor(self):
        r = self.pedir()
        self.assertIn("temperatura=0.0", r.stdout,
                      f"si no la manda, la elige el servidor:\n{r.stdout}{r.stderr}")

    def test_se_puede_subir_por_env_para_el_best_of_N(self):
        """Determinismo para medir, diversidad para buscar. Clavarla en 0 haría imposible el
        best-of-N con verificador, que es lo único que un modelo de 95M necesitó para pasar de
        54,7% a 72,3%."""
        r = self.pedir(TEMPERATURA="0.7")
        self.assertIn("temperatura=0.7", r.stdout, f"\n{r.stdout}{r.stderr}")

    def test_el_canal_entero_la_manda_no_solo_pedir(self):
        """`enjambre.sh` y `conversar.sh` llaman a `pedir.py`, así que heredan la decisión. El
        test lo fija: si alguno armara su propio POST, este chequeo lo dice."""
        # Sobre las líneas de CÓDIGO, no sobre el archivo entero. La primera versión miró el
        # texto completo y se tropezó con un COMENTARIO —«un POST plano a /chat/completions
        # por cada rojo»— que describe el diseño en vez de implementarlo. Quinta vez hoy que
        # una guarda mía matchea prosa: el patrón es mío, no del repo.
        for n in ("enjambre.sh", "conversar.sh", "replan-sin-memoria.sh"):
            fuente = (SCRIPTS / n).read_text()
            codigo = [l for l in fuente.splitlines()
                      if l.strip() and not l.strip().startswith("#")]
            propios = [l.strip()[:70] for l in codigo if "chat/completions" in l]
            self.assertEqual([], propios,
                             f"{n} arma su propio POST y se saltea la decisión de "
                             f"temperatura: {propios}")
            self.assertIn("pedir.py", fuente, f"{n} tiene que pasar por pedir.py")


class TestLoProhibidoNoSeExplicaEnProsa(unittest.TestCase):
    """Cadáver del 2026-10-24, y es mío. El enunciado de T05c decía, en el cuerpo:

        «si alguna vez hacen falta esos campos, se amplía la consulta de
         backend/app/datos/search_ads.py, que es de T28 y está cerrada — o sea que no es
         trabajo de esta tarea»

    El ejecutor fue y editó ese archivo. La prohibición estaba escrita, en castellano, dos
    líneas DESPUÉS de la receta: le di el cómo y después le dije que no. El guardia de alcance
    lo rechazó —correctamente— y de paso destapó que ese archivo tenía una columna inexistente.

    Udgam Labs midió la misma cosa por otro lado: a su modelo de 95M, un número IRRELEVANTE
    insertado en el problema le baja el acierto de 54,7% a 20,7%. Un dato que no hace falta no
    es neutro: compite por la atención.

    NO hay chequeo automático para esto, y lo probé: la regla «no nombres archivos ajenos» es
    inchequeable porque el método PIDE nombrarlos —«decí dónde vive cada cosa: archivo exacto,
    import exacto» es lo más útil que un enunciado hace—, y la variante mecánica que busqué
    —«nombra un archivo que no existe»— da 13 positivos en clasificados y todos son el propio
    archivo de test de cada tarea, que por tests-first todavía no existe. Sin cadáver no hay
    chequeo: la regla va donde tiene efecto, que es el prompt y la plantilla."""

    def test_la_plantilla_de_tarea_lo_dice_donde_se_declara_el_campo(self):
        # Sin fijar la caja: un test que exige «no en prosa» en minúscula se puso rojo porque
        # la plantilla lo escribe en mayúscula para que se vea. Fijar la ortografía de una
        # frase en prosa es sobre-especificar: lo que importa es que la regla esté ahí.
        t = (PLANTILLAS / "TAREA.md").read_text().lower()
        encabezado = t[:t.index("**prohibido tocar:**")]
        self.assertIn("no en prosa", encabezado,
                      "la regla tiene que estar JUNTO al campo que se llena, no al final del "
                      "archivo: quien completa la plantilla lee lo que tiene al lado")
        self.assertIn("cómo", encabezado, "y decir que no se explica el cómo")

    def test_los_dos_prompts_que_escriben_enunciados_la_llevan(self):
        """Los dos, no uno: la forma que este repo repite es el arreglo que vive en un hermano
        y no en el otro, y hoy ya costó cuatro defectos."""
        for n in ("replanificar.sh", "replanificar-relevo.sh"):
            fuente = (SCRIPTS / n).read_text()
            self.assertIn("Prohibido tocar», no en prosa", fuente,
                          f"{n} no le pide al arquitecto que la prohibición vaya al campo")
            self.assertIn("NO expliques cómo hacer lo que prohibís", fuente,
                          f"{n} no le pide que no dé la receta de lo prohibido")

    def test_y_sigue_pidiendo_el_import_exacto(self):
        """El otro lado: la regla NO puede terminar desalentando que el enunciado diga dónde
        vive cada cosa. Eso es lo que resolvió T05c, y es la recomendación con la que el 27B
        cerró su diagnóstico. Una regla que se come a la buena se aplicó demasiado."""
        for n in ("replanificar.sh", "replanificar-relevo.sh"):
            fuente = (SCRIPTS / n).read_text()
            self.assertIn("DÓNDE vive cada cosa", fuente, f"{n}")
            self.assertIn("import exacto", fuente, f"{n}")


class TestLaVentanaDeclaradaNoEsLaUsable(unittest.TestCase):
    """El monitoreo cruza el contexto DECLARADO contra el SERVIDO, y las dos cifras pueden
    coincidir mientras el modelo no recupere nada del medio del prompt. Udgam Labs lo midió en
    su propio modelo: la recuperación a 3.500 tokens pasó del 1% al 83% después de preentrenar
    en ventana larga, con el mismo tamaño declarado antes y después.

    Para este método importa más que para un chat: lo que mandamos es el enunciado más
    AGENTS.md más los archivos que la tarea nombra. Si el modelo no recupera del medio, lo que
    se degrada en silencio es el ENUNCIADO — y el veredicto que salga va a nombrar a la tarea.

    Medido el 2026-10-24 contra los tres modelos de la corrida, al 10%, 50% y 90% de ~21.600
    tokens: los tres recuperaron la aguja. El 27B tardó 34s contra 7-10s de los otros dos, y
    contestó con su razonamiento adelante en vez de sólo el código."""

    def servidor(self, responde):
        """Un `/chat/completions` que contesta lo que diga `responde(prompt)`."""
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                pedido = json.loads(self.rfile.read(n).decode("utf-8", "replace"))
                texto = responde(pedido["messages"][0]["content"])
                cuerpo = json.dumps(
                    {"choices": [{"message": {"content": texto}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1"

    def medir(self, responde, **env):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ventana-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text(json.dumps({"provider": {"c": {"models": {
            "m1": {"limit": {"context": 8000}}}}}}))
        base = dict(TECHO_TOKENS="600", PROFUNDIDADES="0.5", CONFIG_OC=str(cfg))
        base.update(env)
        return correr(f'python3 "{SCRIPTS}/medir-ventana.py" m1', RAIZ,
                      COLABHIVE_BASE_URL=self.servidor(responde),
                      COLABHIVE_API_KEY="x", **base)

    def test_un_modelo_que_recupera_la_aguja_da_verde(self):
        r = self.medir(lambda p: "7314-QX")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("✓", r.stdout, f"\n{r.stdout}")

    def test_un_modelo_que_NO_la_recupera_da_rojo_y_dice_dónde(self):
        r = self.medir(lambda p: "no encontré ningún código")
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("NO recuperan", r.stdout, f"\n{r.stdout}")
        self.assertIn("50%", r.stdout, f"tiene que decir a qué profundidad:\n{r.stdout}")

    def test_la_aguja_va_a_la_profundidad_pedida_y_no_al_final(self):
        """Si la aguja quedara siempre al final, el test mediría el final del prompt —lo más
        fácil de recuperar— y daría verde con cualquier modelo."""
        visto = {}

        def responde(prompt):
            i = prompt.find("7314-QX")
            visto["frac"] = i / max(len(prompt), 1)
            return "7314-QX"

        self.medir(responde, PROFUNDIDADES="0.25")
        self.assertLess(visto["frac"], 0.45,
                        f"al 25% la aguja tiene que estar en el primer tramo: "
                        f"quedó en {visto['frac']:.2f}")

    def test_la_evidencia_impresa_sostiene_el_veredicto(self):
        """La primera versión mostraba los primeros 48 caracteres crudos, y para el 27B eso
        era «We need answer user's request...» —su razonamiento— al lado de un ✓: el valor
        estaba más adelante. Un ✓ junto a una evidencia que no lo muestra es ilegible en el
        mejor caso y una mentira en el peor."""
        r = self.medir(lambda p: "Pensemos. El usuario pide algo en castellano. " * 3
                                 + "\n7314-QX")
        self.assertEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        linea = [l for l in r.stdout.splitlines() if "✓" in l and "%" in l][0]
        self.assertIn("7314-QX", linea,
                      f"el renglón del ✓ tiene que mostrar la aguja:\n{linea}")

    def test_un_corte_de_plataforma_no_es_un_modelo_que_falla(self):
        """La lección del defecto 19: un chequeo que no pudo correr no dice «rojo» sobre el
        sujeto que vino a medir. Acá un 503 no es un modelo que no recupera."""
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(503); self.send_header("Content-Length", "2")
                self.end_headers(); self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-ventana-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        cfg = d / "opencode.json"
        cfg.write_text(json.dumps({"provider": {"c": {"models": {"m1": {}}}}}))
        r = correr(f'python3 "{SCRIPTS}/medir-ventana.py" m1', RAIZ,
                   COLABHIVE_BASE_URL=f"http://127.0.0.1:{srv.server_address[1]}/v1",
                   COLABHIVE_API_KEY="x", TECHO_TOKENS="600", PROFUNDIDADES="0.5",
                   CONFIG_OC=str(cfg), PACIENCIA="5")
        self.assertIn("⊘", r.stdout, f"\n{r.stdout}{r.stderr}")
        self.assertNotIn("NO recuperan", r.stdout,
                         f"no se le puede cobrar al modelo un corte de plataforma:\n{r.stdout}")

    def test_sin_plataforma_configurada_no_opina(self):
        r = correr(f'python3 "{SCRIPTS}/medir-ventana.py" m1', RAIZ,
                   COLABHIVE_BASE_URL="")
        self.assertEqual(2, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("⊘", r.stderr, f"\n{r.stderr}")


class TestElEnunciadoTampocoPuedePedirUnaColumnaQueNoExiste(unittest.TestCase):
    """El chequeo de tablas tiene DOS lados: lo que dicen los enunciados y lo que hace el
    código. El de columnas tenía sólo el del código, y la asimetría se cobró el 2026-10-24.

    Secuencia completa, porque es la más instructiva del día. El chequeo de columnas encontró
    que `datos/search_ads.py` consultaba `anuncios.categoria`, que no existe. Reabrí T28, lo
    que SACÓ ese código del tronco — y con el código fuera el chequeo se quedó sin nada que
    leer: preflight en verde. Lancé la corrida, el ejecutor reescribió el test siguiendo el
    enunciado, que dice «filtro por columna `categoria`», y MySQL lo rechazó:

        pymysql.err.OperationalError: (1054, "Unknown column 'categoria' in 'field list'")

    El defecto sobrevivió a su propio arreglo porque vivía en el TEXTO, y el único que lo
    detectó fue la base de datos, después de dos intentos de agente."""

    def proyecto(self, cuerpo, esquema="id INT, nombre VARCHAR(50)"):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-colenun-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T40-cosas.md").write_text(
            "# T40 — Cosas\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer cosas.\n\n" + cuerpo + "\n\n"
            "## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            f"CREATE TABLE cosas (\n    {esquema}\n);\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T40 | Cosas | — | `app/datos/cosas.py` | pendiente |\n")
        return d

    def coherencia(self, d):
        return correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)

    def test_columna_inexistente_en_el_enunciado_es_rojo(self):
        d = self.proyecto("Filtro por columna `titulo`.")
        r = self.coherencia(d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("`titulo`", r.stdout, f"\n{r.stdout}")
        self.assertIn("Unknown column", r.stdout,
                      f"tiene que decir cómo va a fallar, no sólo que está mal:\n{r.stdout}")

    def test_una_columna_que_existe_no_molesta(self):
        d = self.proyecto("Filtro por columna `nombre`.")
        self.assertEqual(0, self.coherencia(d).returncode)

    def test_varias_columnas_en_una_frase(self):
        d = self.proyecto("Devuelve las columnas `id`, `nombre` y `precio`.")
        r = self.coherencia(d)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("`precio`", r.stdout, f"\n{r.stdout}")
        self.assertNotIn("`nombre`", r.stdout, f"no puede marcar las que existen:\n{r.stdout}")

    def test_un_identificador_suelto_entre_backticks_no_se_marca(self):
        """El chequeo es estrecho A PROPÓSITO. Un `identificador` entre backticks puede ser
        una variable, un campo de un JSON o una columna de una tabla de la interfaz. «columna
        `x`» es una afirmación sobre el esquema; `x` solo, no.

        El caso real: T26 nombra `password_hash` —que tampoco existe en el esquema— pero lo
        nombra como lo que `login` compara, no como columna. Marcarlo sería adivinar."""
        d = self.proyecto("El login compara contra `password_hash` y hay que guardar igual.")
        self.assertEqual(0, self.coherencia(d).returncode)

    def test_sin_migraciones_no_opina(self):
        d = self.proyecto("Filtro por columna `titulo`.")
        shutil.rmtree(d / "migraciones")
        self.assertEqual(0, self.coherencia(d).returncode)


class TestElRouterLePasaElMenuDelProblemaQueRecibe(unittest.TestCase):
    """`replanificar-coherencia.sh` toma cualquier `✗` del preflight y se lo da al arquitecto.
    Su prompt era SIEMPRE de tablas: «las tablas que las migraciones ya crean son...» y «usá
    una tabla de la lista o prometé crear la tabla que nombra».

    Desde el 2026-10-24 hay rojos de COLUMNA, y a ésos ese menú no les sirve: le pide arreglar
    un nombre de columna ofreciéndole opciones sobre tablas, y acompañado de la lista
    equivocada. Un arquitecto al que se le pide arreglar X con las opciones de Y adivina — y
    adivinar es lo único que este método no le pide a nadie.

    El cadáver es del mismo día: el enunciado de T28 decía «filtro por columna `categoria`»,
    la tabla `anuncios` tiene `categoria_id`, y lo único que lo detectó fue MySQL con «Unknown
    column», después de dos intentos de agente."""

    def proyecto(self, cuerpo):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-router-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T40-cosas.md").write_text(
            "# T40 — Cosas\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\n" + cuerpo + "\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE cosas (\n    id INT, nombre VARCHAR(50)\n);\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T40 | Cosas | — | `app/datos/cosas.py` | pendiente |\n")
        bin_ = d / ".bin"; bin_.mkdir()
        (bin_ / "opencode").write_text(
            '#!/usr/bin/env bash\necho "$*" >> "$PROMPTS"\necho "no toqué nada"\n')
        (bin_ / "opencode").chmod(0o755)
        return d

    def correr_router(self, d):
        prompts = d.parent / "prompts.txt"
        r = correr(f'PATH="{d}/.bin:$PATH" PROMPTS="{prompts}" PROYECTO=. LIMITE_AGENTE=60 '
                   f'MODELO=m1 bash "{SCRIPTS}/replanificar-coherencia.sh"', d)
        return r, (prompts.read_text() if prompts.exists() else "")

    def test_un_rojo_de_columna_recibe_las_columnas_y_el_menu_de_columnas(self):
        d = self.proyecto("Filtro por columna `titulo`.")
        r, prompt = self.correr_router(d)
        self.assertIn("columnas que las migraciones YA crean", prompt,
                      f"le pasó la lista equivocada:\n{prompt[:400]}")
        self.assertIn("cosas: id, nombre", prompt,
                      f"y tiene que traer el esquema real:\n{prompt[:400]}")
        self.assertIn("agregar la columna", prompt,
                      f"la salida (b) de un rojo de columna es agregarla, no crear una tabla:"
                      f"\n{prompt[:400]}")
        self.assertNotIn("CREAR la tabla", prompt,
                         f"ése es el menú del otro problema:\n{prompt[:400]}")

    def test_un_rojo_de_tabla_sigue_recibiendo_el_menu_de_tablas(self):
        """El otro lado: arreglar el caso nuevo no puede romper el que ya andaba. Ese prompt
        de tablas es el que logró la única corrida que replanificó en 4:09."""
        d = self.proyecto("Guardar los datos en la tabla `inventada`.")
        r, prompt = self.correr_router(d)
        self.assertIn("tablas que las migraciones YA crean", prompt, f"\n{prompt[:400]}")
        self.assertIn("CREAR la tabla", prompt, f"\n{prompt[:400]}")
        self.assertNotIn("agregar la columna", prompt, f"\n{prompt[:400]}")

    def test_el_patron_de_HUECO_es_el_mismo_que_en_los_hermanos(self):
        """Arreglé el patrón en `replanificar.sh` y `replanificar-relevo.sh` por la mañana y
        me salté ÉSTE, que es el que enruta. Tercera vez en el día con la misma forma: el
        arreglo que vive en un hermano y no en el otro."""
        patrones = set()
        for n in ("replanificar.sh", "replanificar-relevo.sh", "replanificar-coherencia.sh"):
            fuente = (SCRIPTS / n).read_text()
            patrones |= set(re.findall(r"'(\^[^']*HUECO[^']*)'", fuente))
        self.assertEqual(1, len(patrones),
                         f"los tres scripts tienen que buscar HUECO igual: {patrones}")


class TestElEstadoQueQuedoNoSeLeCobraAlTest(unittest.TestCase):
    """El validador de tests-first corre el MISMO test DOS VECES: una sin la implementación,
    para comprobar que falla, y otra con ella. Contra una base con estado, la segunda pasada
    encuentra lo que insertó la primera.

    Medido el 2026-10-24 en T26: la primera pasada insertó `test@example.com`, la segunda
    chocó con el UNIQUE de `usuarios.email`, y el veredicto fue «el test no pasa ni con la
    implementación del propio agente». Le cobró al test lo que dejó su propia primera pasada,
    y el ejecutor gastó dos intentos en eso.

    El gate ya tenía el concepto escrito para su lado —ENTORNO_MOVIDO: «todos los worktrees
    comparten el MySQL de 127.0.0.1:33306, lo que una etapa deja la siguiente lo encuentra; es
    del entorno y no del código, así que no se le cobra a la tarea»— pero su lista de firmas
    reconocía «Table doesn't exist», «Access denied» y «Can't connect», no un choque de
    UNIQUE. En el validador de tests faltaba entero.

    No ablanda nada: el test no se acepta igual. Lo único que cambia es A QUIÉN se le cobra."""

    FIRMAS = ["pymysql.err.IntegrityError: (1062, \"Duplicate entry 'x' for key 'u.email'\")",
              "sqlite3.IntegrityError: UNIQUE constraint failed: usuarios.email",
              "E   Duplicate entry 'test@example.com' for key 'usuarios.email'"]
    NO_SON = ["AssertionError: assert 401 == 201",
              "ModuleNotFoundError: No module named 'backend'",
              "E   TypeError: insert_user() missing 1 required positional argument"]

    def patron_del_validador(self):
        """El patrón TAL COMO ESTÁ en el script: un test que lo copia mide la copia."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        m = re.search(r'grep -qiE "([^"]*IntegrityError[^"]*)"', fuente)
        self.assertIsNotNone(m, "el validador no reconoce la firma del estado que quedó")
        return m.group(1)

    def patron_del_gate(self):
        fuente = (PLANTILLAS / "gate.sh").read_text()
        m = re.search(r'grep -qiE "([^"]*Duplicate entry[^"]*)"', fuente)
        self.assertIsNotNone(m, "el gate no reconoce la firma del estado que quedó")
        return m.group(1)

    def test_el_validador_reconoce_el_choque_de_unique(self):
        patron = self.patron_del_validador()
        for firma in self.FIRMAS:
            r = subprocess.run(["grep", "-qiE", patron], input=firma + "\n",
                               text=True, capture_output=True)
            self.assertEqual(0, r.returncode, f"no ve «{firma[:50]}»")

    def test_y_no_confunde_un_test_realmente_malo(self):
        """Si esta firma se disparara con cualquier fallo, el validador dejaría de rechazar
        tests malos — y ése es su trabajo. El riesgo de ablandar es real y va medido."""
        patron = self.patron_del_validador()
        for firma in self.NO_SON:
            r = subprocess.run(["grep", "-qiE", patron], input=firma + "\n",
                               text=True, capture_output=True)
            self.assertEqual(1, r.returncode, f"se dispara con «{firma[:50]}»")

    def test_el_gate_tambien_la_reconoce(self):
        """Los dos lados, no uno: el validador la ve al escribir el test y el gate al juzgar la
        implementación. Es la forma que este repo repite, y hoy ya costó cuatro defectos."""
        patron = self.patron_del_gate()
        for firma in self.FIRMAS:
            r = subprocess.run(["grep", "-qiE", patron], input=firma + "\n",
                               text=True, capture_output=True)
            self.assertEqual(0, r.returncode, f"el gate no ve «{firma[:50]}»")

    def test_el_mensaje_nombra_al_metodo_y_no_al_test(self):
        """Un veredicto que no dice de quién es el problema deja que el próximo lo diagnostique
        de cero. El de hoy decía «el test no pasa ni con la implementación del propio agente»,
        que es exactamente el sujeto equivocado."""
        # Las DOS ramas nombran un sujeto, cada una el suyo. Este test fijaba la frase «Lo
        # causa el MÉTODO», que era el único caso que había; desde que a quién se le cobra se
        # MIDE —si la limpieza de esa pasada funcionó, la base arrancó vacía y el choque es
        # del test— hay dos sujetos y el veredicto nombra el que corresponde. Es más de lo
        # que este test pedía, no menos, así que lo que cambia es cómo se lo mide: la
        # conducta de nombrar, no una redacción.
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        i = fuente.index("IntegrityError")
        bloque = fuente[i:i + 4200]
        # Por el MARCADOR y no por el primer `else`: las tres ramas de la familia
        # IntegrityError viven dentro de la primera, así que el `else` más cercano es interno.
        corte = bloque.index("⊘ $id: el test choca con datos que YA estaban")
        rama_test, rama_metodo = bloque[:corte], bloque[corte:]
        self.assertIn("insertó ÉL MISMO", rama_test,
                      f"con la base vacía el sujeto es el test:\n{rama_test[-500:]}")
        self.assertIn("lo arregla el test", rama_test,
                      "y tiene que decir quién lo arregla, no sólo quién lo causó")
        self.assertIn("no se le cobra a la tarea", rama_metodo,
                      f"sin poder limpiar, el sujeto no es la tarea:\n{rama_metodo[:600]}")
        # «reintenta» y no la frase entera: mi primera versión buscaba «no se reintenta» y el
        # mensaje dice «ni se reintenta contra ella». Fijar la redacción exacta de una frase en
        # prosa es sobre-especificar, y hoy ya me pasó con la plantilla.
        self.assertIn("reintenta", rama_metodo,
                      "la segunda pasada va a encontrar la misma fila: reintentar es gastar")


class TestUnTestMockeadoNoPuedeClavarUnaConsultaImposible(unittest.TestCase):
    """El falso verde más fuerte del 2026-10-24, y el gate lo ACEPTÓ.

    El test que el validador aprobó para T28 fijaba:

        mock_cursor.execute.assert_called_once_with(
          "SELECT id, usuario_id, titulo, categoria, precio FROM anuncios WHERE 1=1 ...")

    Ni `categoria` ni `precio` existen: son `categoria_id` y `precio_centavos`. Pasó los
    cuatro chequeos porque está completamente mockeado —la base nunca se toca, el mock acepta
    cualquier cadena— y los mutantes MUEREN, porque `assert_called_once_with` fija la cadena
    exacta. O sea que el chequeo de mutación lo satisface un test que clava una consulta
    equivocada.

    Eso no es un test que deja pasar el bug: es un test que lo OBLIGA. La implementación que
    lo haga pasar va a escribir esa consulta y MySQL la va a rechazar, con el veredicto
    apuntando a la tarea que la escribió.

    Y el chequeo existía: `coherencia.py` lo marcó… en el preflight de la corrida SIGUIENTE,
    con el test ya en el tronco. La información estaba en el momento equivocado."""

    def test_el_validador_pregunta_por_el_esquema_antes_de_aceptar(self):
        """El orden importa y es lo único que cambió: el mismo juez, antes del `cp` al tronco.
        Sin esto el chequeo corre cuando el daño ya está hecho."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        i = fuente.index("coherencia.py")
        j = fuente.index('cp "$ruta" "$BASE/$ruta"')
        self.assertLess(i, j,
                        "el chequeo de esquema tiene que correr ANTES de copiar el test al "
                        "tronco: después es el preflight de la corrida siguiente")

    def test_filtra_por_el_archivo_que_esta_entrando(self):
        """Si no filtrara, cualquier rojo preexistente del proyecto rechazaría un test
        correcto: el veredicto nombraría a esta tarea por un problema ajeno, que es el defecto
        que este repo persigue."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        # Hasta el `malo` que cierra el bloque, no una ventana de N caracteres: mi primera
        # versión cortó a los 1400 y el comentario del bloque es más largo, así que el test
        # miraba de menos y daba rojo por su propia ventana.
        desde = fuente.index("5. El test contra el ESQUEMA")
        bloque = fuente[desde:fuente.index("el test clava una consulta", desde)]
        self.assertIn('grep -F "$ruta"', bloque,
                      f"tiene que mirar sólo los rojos que nombran el test que entra:"
                      f"\n{bloque[-400:]}")

    def test_el_chequeo_de_columnas_ve_los_archivos_de_test(self):
        """Lo que lo hace posible: `coherencia.py` no excluye `tests/`. Si los excluyera —y es
        una exclusión que varios chequeos de este archivo SÍ hacen— un test mockeado podría
        clavar cualquier consulta sin que nadie la cruzara nunca."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-testmock-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T40-cosas.md").write_text(
            "# T40 — Cosas\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer cosas.\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE cosas (\n    id INT, nombre VARCHAR(50)\n);\n")
        (d / "tests").mkdir()
        (d / "tests" / "test_cosas.py").write_text(
            "def test_consulta():\n"
            "    esperado = 'SELECT id, inventada FROM cosas'\n"
            "    assert esperado\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T40 | Cosas | — | `app/datos/cosas.py` | pendiente |\n")
        r = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        self.assertIn("cosas.inventada", r.stdout,
                      f"una consulta clavada en un TEST tiene que cruzarse igual:\n{r.stdout}")


class TestLaCapaDeDatosNoSePruebaConMocks(unittest.TestCase):
    """Las dos cosas que tenía anotadas como problemas separados son el mismo problema.

    La regla del proyecto dice «mockeá la función de la CAPA DE DATOS por su ruta», y sirve
    para probar SERVICIOS. Pero cuando la tarea ES la capa de datos, abajo no hay nada que
    mockear salvo `conexion()` — y eso deja exactamente dos salidas, las dos medidas el
    2026-10-24 en dos tareas distintas:

      · clavar la cadena SQL → los mutantes mueren, el test se acepta, y una consulta
        imposible queda OBLIGADA (T28: `categoria` y `precio`, que no existen);
      · no afirmar nada sobre la consulta → sobreviven los mutantes y se rechaza (T26).

    O sea que un test de capa de datos mockeado no puede salir bien. La salida es la base
    real, donde el esquema rechaza la columna inexistente — y eso depende del aislamiento de
    la base, que no existe. Las dos cosas son una."""

    def test_la_plantilla_dice_que_la_capa_de_datos_va_contra_la_base_real(self):
        t = (PLANTILLAS / "AGENTS.md").read_text()
        self.assertIn("CAPA DE DATOS", t, "la plantilla no distingue ese caso")
        i = t.index("CAPA DE DATOS")
        bloque = t[i:i + 2200]
        self.assertIn("base REAL", bloque, f"\n{bloque[:300]}")
        self.assertIn("OBLIGA", bloque,
                      "tiene que decir que el mock apretado no deja pasar el bug: lo obliga")

    def test_y_dice_que_todavia_no_es_seguro_y_por_que(self):
        """Una regla cuya precondición no se cumple es una trampa. La base compartida no se
        limpia entre corridas, así que mandar «usá la base real» sin decirlo haría que el
        próximo choque con el `Duplicate entry` y no entienda por qué."""
        t = (PLANTILLAS / "AGENTS.md").read_text()
        i = t.index("CAPA DE DATOS")
        bloque = t[i:i + 2200]
        self.assertIn("Duplicate entry", bloque, f"\n{bloque[-600:]}")
        self.assertIn("hueco del método", bloque,
                      "y que lo diga en vez de inventar un test que pase")


class TestUnaBasePorWorktree(unittest.TestCase):
    """Hasta el 2026-10-25 todos los worktrees escribían en la MISMA base y nadie la limpiaba.
    Consecuencia medida: el validador de tests corre el mismo test DOS VECES —una sin la
    implementación y otra con ella— así que la segunda chocaba con la fila que insertó la
    primera:

        pymysql.err.IntegrityError: (1062, "Duplicate entry 'test@example.com'
                                            for key 'usuarios.email'")

    y el veredicto decía «el test no pasa ni con la implementación del propio agente»: le
    cobraba al test lo que dejó su propia primera pasada. Dos intentos del ejecutor gastados.

    La causa concreta: `.entorno` —que lleva el NOMBRE de la base— se enlazaba al del tronco,
    así que compartir ese archivo era compartir la base. Lo verifiqué en el worktree de T26:
    era un enlace a `metodo-agentes/ejemplo-clasificados/.entorno`.

    El servidor sigue siendo UNO —levantar un mysqld por worktree sería absurdo, y el worktree
    no tiene ni `.mysql/` ni cliente— y lo que se aísla es la base."""

    def test_el_entorno_del_worktree_no_se_enlaza_si_el_proyecto_lo_regenera(self):
        fuente = (SCRIPTS / "preparar-entorno.sh").read_text()
        i = fuente.index("      .entorno)")
        bloque = fuente[i:i + 1600]
        self.assertIn('[ -x "$BASE/scripts/entorno.sh" ]', bloque,
                      f"tiene que condicionarlo a que el proyecto sepa regenerarlo:\n{bloque[:300]}")

    def test_un_enlace_previo_se_deshace_antes_de_escribir(self):
        """Imprescindible, no cosmético: `entorno.sh` escribe con `cat >`, y escribir a través
        de un enlace escribe en su DESTINO. Sin deshacerlo, generar el `.entorno` del worktree
        PISA el del tronco con el nombre de la base de una tarea, y el tronco entero pasa a
        apuntar ahí."""
        fuente = (SCRIPTS / "preparar-entorno.sh").read_text()
        i = fuente.index("      .entorno)")
        bloque = fuente[i:i + 1600]
        self.assertIn('if [ -L "$destino" ]', bloque, f"\n{bloque[:600]}")
        self.assertIn("rm -f", bloque, f"\n{bloque[:600]}")

    def test_el_nombre_de_la_base_sale_del_tronco_y_del_worktree(self):
        """El prefijo del `.entorno` del tronco porque el método no sabe cómo se llama la base
        de un proyecto —lo decide su `entorno.sh`— y el sufijo del worktree, que es la unidad
        de aislamiento que el método ya tiene."""
        # Un worktree de GIT de verdad, no dos directorios pelados. La función pregunta a
        # git si el destino es un worktree —`--git-dir` contra `--git-common-dir`— porque
        # decidirlo comparando `$DESTINO` con `$BASE` la hacía depender del directorio actual,
        # y con el cwd adentro del worktree devolvía vacío: `entorno.sh` recibía `MYSQL_DB`
        # vacío, usaba su valor por omisión, y el worktree quedaba apuntando a la BASE REAL
        # del proyecto. Con directorios pelados este test medía una derivación que ya no
        # existe, y era él el que había que actualizar.
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-basewt-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        tronco = d / "tronco"
        tronco.mkdir()
        (tronco / ".entorno").write_text("export MYSQL_DB=miproyecto\n")
        (tronco / "algo.txt").write_text("para tener un commit\n")
        correr("git init -q .", tronco)
        correr("git -c user.email=t@t -c user.name=t add algo.txt", tronco)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', tronco)
        wt = d / "tests-T42"
        correr(f"git worktree add -q --detach {wt} HEAD", tronco)
        self.addCleanup(lambda: correr(f"git worktree remove --force {wt}", tronco))
        guion = (f'BASE="{tronco}"; DESTINO="{wt}"; PROYECTO=.\n'
                 + self._funcion_nombre() + '\nbase_de_datos_del_arbol\n')
        g = d / "g.sh"; g.write_text(guion)
        r = correr(f'bash "{g}"', RAIZ)
        self.assertEqual("miproyecto_tests_T42", r.stdout.strip(),
                         f"\n{r.stdout}{r.stderr}")

    def test_sobre_el_tronco_no_cambia_la_base(self):
        """Una corrida sobre el tronco tiene que seguir usando la base del proyecto: es la que
        una persona mira entre corridas."""
        # Repo git de verdad, igual que el de arriba y por el mismo motivo: con directorios
        # pelados este test daba verde por la razón EQUIVOCADA —esperaba vacío y lo obtenía
        # porque el destino no era un repo, no porque fuera el tronco— y habría seguido verde
        # con el arreglo puesto al revés.
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-basewt-")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        tronco = d / "tronco"
        tronco.mkdir()
        (tronco / ".entorno").write_text("export MYSQL_DB=miproyecto\n")
        (tronco / "algo.txt").write_text("para tener un commit\n")
        correr("git init -q .", tronco)
        correr("git -c user.email=t@t -c user.name=t add algo.txt", tronco)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', tronco)
        guion = (f'BASE="{tronco}"; DESTINO="{tronco}"; PROYECTO=.\n'
                 + self._funcion_nombre() + '\nbase_de_datos_del_arbol; echo "fin"\n')
        g = d / "g.sh"; g.write_text(guion)
        r = correr(f'bash "{g}"', RAIZ)
        self.assertEqual("fin", r.stdout.strip(),
                         f"sobre el tronco no tiene que devolver nombre:\n{r.stdout}")

    def _funcion_nombre(self):
        """La función TAL COMO ESTÁ en el script: un test que la copia mide la copia."""
        fuente = (SCRIPTS / "preparar-entorno.sh").read_text()
        i = fuente.index("base_de_datos_del_arbol() {")
        j = fuente.index("\n}", i) + 2
        return fuente[i:j]

    def test_el_drop_es_del_proyecto_y_no_del_metodo(self):
        """Misma división que el encabezado de `entorno.sh` declara: «el método no sabe qué
        base de datos usa nadie». El método llama, el proyecto tira."""
        comun = (SCRIPTS / "_comun.sh").read_text()
        i = comun.index("tirar_base_del_worktree() {")
        bloque = comun[i:comun.index("\n}", i)]
        self.assertIn("entorno.sh --tirar", bloque,
                      "el método no puede armar el DROP por su cuenta")
        self.assertIn('[ ! -L "$ent" ]', bloque,
                      "un .entorno que es ENLACE es el del tronco: esa base no se toca")

    def test_el_proyecto_se_niega_a_tirar_la_base_del_tronco(self):
        """La guarda que importa: un `--tirar` mal invocado no puede llevarse la base del
        proyecto, que es la que una persona mira."""
        ent = RAIZ / "ejemplo-clasificados" / "scripts" / "entorno.sh"
        if not ent.exists():
            self.skipTest("este repo ya no tiene ejemplo-clasificados")
        r = correr(f'MYSQL_DB=clasificados bash "{ent}" --tirar', ent.parent.parent)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("base del tronco", r.stdout + r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_todo_remove_de_worktree_tira_su_base_antes(self):
        """La forma que este repo repite es el arreglo que vive en un hermano y no en el otro.
        Si alguien agrega un `worktree remove` sin el drop, el servidor se llena de bases
        muertas y nadie se entera: cambiaríamos una fuga por otra."""
        for n in ("escribir-tests.sh", "correr-tarea.sh"):
            lineas = (SCRIPTS / n).read_text().splitlines()
            for i, l in enumerate(lineas):
                if "worktree remove --force" in l and '"$wt"' in l:
                    previas = "\n".join(lineas[max(0, i - 3):i])
                    self.assertIn("tirar_base_del_worktree", previas,
                                  f"{n}:{i + 1} borra el worktree sin tirar su base:\n{l}")


class TestLaBaseSeVaciaAntesDeCadaPasada(unittest.TestCase):
    """Aislar la base por worktree era NECESARIO y NO SUFICIENTE, y lo mostró la corrida.

    Con la base propia ya creada y anunciada —«· base de datos de este worktree:
    clasificados_tests_T26»— T26 SEGUÍA dando:

        Duplicate entry 'test@example.com' for key 'usuarios.email'

    Porque el choque no venía de una corrida anterior: viene de las DOS PASADAS del propio
    validador —una sin la implementación y otra con ella— sobre la misma base. El test inserta
    sus datos en la preparación, haya implementación o no, así que la segunda encuentra la fila
    de la primera por nueva que sea la base.

    Lo que el aislamiento habilitó es el arreglo: vaciar la base no le rompe nada a ninguna
    tarea hermana, porque ahora es de un solo árbol. Era la única objeción que esta salida
    tenía cuando se la planteé."""

    def test_cada_pasada_de_la_suite_se_precede_de_la_limpieza(self):
        lineas = (SCRIPTS / "escribir-tests.sh").read_text().splitlines()
        # TODAS las pasadas que deciden, sin fijar el número: mi primera versión exigió DOS y
        # el validador tiene TRES —me había olvidado del brazo nulo, que también corre la
        # suite—. El test lo encontró, que es para lo que está; fijar el número habría
        # convertido un hallazgo en un rojo sobre mi propia cuenta.
        pasadas = [i for i, l in enumerate(lineas) if 'eval "$prueba" >/dev/null 2>&1; then' in l]
        self.assertGreaterEqual(len(pasadas), 2,
                                f"esperaba al menos dos pasadas; encontré {len(pasadas)}")
        # Busca LA LLAMADA, no el nombre: mi primera versión miraba si el nombre aparecía en
        # las líneas previas, y lo encontraba en el COMENTARIO que explica la llamada. Quitando
        # la llamada, el test seguía verde. Sexta vez en dos días que una guarda mía matchea
        # prosa; el patrón es mío.
        for i in pasadas:
            previas = [l.strip() for l in lineas[max(0, i - 6):i]]
            # `in` sobre la lista exigía la línea EXACTA, y ahora la llamada lleva pegada la
            # medición de si la limpieza funcionó —`&& BASE_VACIA_AL_EMPEZAR=1 || ...=0`—. Lo
            # que este test vigila es que la pasada esté precedida de la limpieza, no cómo se
            # escribe. La aserción va DENTRO del `for`: al reescribirla quedó un nivel afuera
            # y el test pasó a mirar sólo la última pasada — un bucle sin aserción adentro no
            # recorre nada, y el rojo de una pasada intermedia se perdía.
            self.assertTrue(any('limpiar_base_del_arbol "$wt"' in l for l in previas),
                            f"la pasada de la línea {i + 1} arranca con lo que dejó la "
                            f"anterior:\n" + "\n".join(previas))

    def test_no_vacia_la_base_del_tronco(self):
        """Dos guardas, porque vaciar la base del proyecto sería borrarle los datos a una
        persona: el método no la toca si el `.entorno` es un ENLACE —ése es el del tronco— y el
        proyecto se niega si el nombre es el de por omisión."""
        comun = (SCRIPTS / "_comun.sh").read_text()
        i = comun.index("limpiar_base_del_arbol() {")
        bloque = comun[i:comun.index("\n}", i)]
        self.assertIn('[ ! -L "$ent" ]', bloque, f"\n{bloque}")
        ent = RAIZ / "ejemplo-clasificados" / "scripts" / "entorno.sh"
        if not ent.exists():
            self.skipTest("este repo ya no tiene ejemplo-clasificados")
        r = correr(f'MYSQL_DB=clasificados bash "{ent}" --limpiar', ent.parent.parent)
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}{r.stderr}")
        self.assertIn("base del tronco", r.stdout + r.stderr, f"\n{r.stdout}{r.stderr}")

    def test_conserva_la_contabilidad_del_esquema(self):
        """`_migraciones` no se vacía: es la contabilidad del esquema, no datos de prueba.
        Vaciarla haría que la pasada siguiente reaplicara todo."""
        ent = RAIZ / "ejemplo-clasificados" / "scripts" / "entorno.sh"
        if not ent.exists():
            self.skipTest("este repo ya no tiene ejemplo-clasificados")
        fuente = ent.read_text()
        i = fuente.index("--limpiar")
        bloque = fuente[i:i + 1800]
        self.assertIn("_migraciones", bloque, f"\n{bloque[:400]}")
        self.assertIn("FOREIGN_KEY_CHECKS", bloque,
                      "sin apagar las claves foráneas, truncar en el orden equivocado falla")


class TestElRojoDeColumnaNoSeDegradaPorCompania(unittest.TestCase):
    """El chequeo de columnas agrupaba por (tabla, columna) y atribuía al PRIMER archivo de la
    lista, con los demás comprimidos en «y N más». Eso esconde al sujeto, y el 2026-10-25
    escondió uno que importaba.

    La implementación de T28 y su TEST nombraban la misma columna inexistente. `app/...`
    ordena antes que `tests/...`, el dueño del primero estaba PENDIENTE, y todo el rojo se
    degradó a «⚠ el plan puede arrancar». El test quedó dentro de «y 1 más» — y el chequeo
    que lo habría rechazado antes de copiarlo al tronco busca `✗`. Así que el test entró, y
    yo había dicho el día anterior que eso no podía volver a pasar.

    Medido en un proyecto de juguete:

        con implementación + test → ⚠ (app/datos/cosas.py:2 y 1 más), T40 pendiente
        sólo el test             → ✗ tests/test_cosas.py:2, nadie lo declara

    O sea que el MISMO defecto cambiaba de gravedad según qué más lo acompañara."""

    def proyecto(self, con_implementacion):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="prueba-degrada-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / "repo"; d.mkdir()
        correr("git init -q . && git config user.email a@b && git config user.name a", d)
        (d / "tareas").mkdir()
        (d / "tareas" / "T40-cosas.md").write_text(
            "# T40 — Cosas\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** app/datos/cosas.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nLeer cosas.\n\n## Terminado cuando\n\n- [ ] anda\n")
        (d / "migraciones").mkdir()
        (d / "migraciones" / "001_initial.sql").write_text(
            "CREATE TABLE cosas (\n    id INT, nombre VARCHAR(50)\n);\n")
        (d / "tests").mkdir()
        (d / "tests" / "test_cosas.py").write_text(
            "def test_x():\n    esperado = 'SELECT id, titulo FROM cosas'\n    assert esperado\n")
        if con_implementacion:
            (d / "app" / "datos").mkdir(parents=True)
            (d / "app" / "datos" / "cosas.py").write_text(
                "def leer():\n    return db.execute('SELECT id, titulo FROM cosas')\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n## Tareas\n\n"
            "| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T40 | Cosas | — | `app/datos/cosas.py` | pendiente |\n")
        return d

    def test_el_test_da_rojo_aunque_la_implementacion_lo_acompañe(self):
        """El caso exacto que se escapó."""
        d = self.proyecto(con_implementacion=True)
        r = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        rojos = [l for l in r.stdout.splitlines() if "✗" in l and "tests/test_cosas.py" in l]
        self.assertTrue(rojos,
                        f"el test tiene que traer su propio ✗, no quedar en «y N más»:"
                        f"\n{r.stdout}")
        self.assertNotEqual(0, r.returncode, f"\n{r.stdout}")

    def test_y_la_implementacion_sigue_siendo_aviso_porque_su_tarea_corre(self):
        """El otro lado: por archivo no significa todo en rojo. La implementación la declara
        una tarea PENDIENTE que va a correr y cuyo gate la va a juzgar, así que el plan puede
        arrancar — y eso tiene que seguir siendo un aviso."""
        d = self.proyecto(con_implementacion=True)
        r = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        avisos = [l for l in r.stdout.splitlines()
                  if "⚠" in l and "app/datos/cosas.py" in l and "PENDIENTE" in l]
        self.assertTrue(avisos, f"\n{r.stdout}")

    def test_cada_archivo_trae_su_propio_lugar(self):
        """Sin «y N más» mezclando archivos distintos: cada renglón nombra el archivo del que
        habla, que es lo único que permite actuar."""
        d = self.proyecto(con_implementacion=True)
        r = correr(f'PROYECTO=. python3 "{SCRIPTS}/coherencia.py"', d)
        for linea in r.stdout.splitlines():
            if "cosas.titulo" not in linea:
                continue
            nombrados = {a for a in ("tests/test_cosas.py", "app/datos/cosas.py")
                         if a in linea}
            self.assertEqual(1, len(nombrados),
                             f"un renglón que habla de dos archivos no nombra a ninguno:"
                             f"\n{linea}")

    def test_el_chequeo_previo_a_aceptar_no_depende_del_simbolo(self):
        """Buscaba sólo `✗`, así que un rojo degradado a `⚠` por la compañía lo dejaba pasar.
        Un test que clava una consulta imposible no se acepta ni si alguien «se hace cargo» del
        archivo: el test OBLIGA la consulta, y la obliga para siempre."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        i = fuente.index("5. El test contra el ESQUEMA")
        bloque = fuente[i:fuente.index("el test clava una consulta", i)]
        self.assertIn("⚠ esquema", bloque,
                      f"tiene que mirar los avisos también:\n{bloque[-400:]}")


class TestUnMutanteQueSobreviveAdmiteDosLecturasOpuestas(CasoBase):
    """«Sobreviven mutantes» no es un diagnóstico, son dos, y el método afirmaba siempre uno.

    El mensaje que el agente leía era «el test cubre las líneas y no verifica su
    comportamiento», que manda a mejorar las aserciones. Pero un mutante también sobrevive
    cuando el test **no ejecuta** esa línea, y ahí las aserciones no tienen nada que ver: lo
    que sobra es el mock que la reemplaza. Son consejos opuestos y el método daba el primero
    en los dos casos, sin haberlo medido.

    Medido el 2026-10-25 en T26 de clasificados: el test mockeaba
    `backend.app.datos.users_register.insert_user`, que ES la función que la tarea pide
    escribir, así que los tres mutantes de ese archivo sobrevivían por no correr nunca. El
    agente recibió «cubre las líneas» dos corridas seguidas y la tarea quedó trabada. El
    veredicto era correcto en su forma y falso en su contenido — la misma clase de error que
    el de T05a con las anotaciones de tipo.

    La pregunta se contesta con un centinela: se reemplaza la sentencia por una excepción que
    nadie atrapa. Si la suite PASA con eso puesto, la línea no se ejecutó. No hace falta
    medir cobertura ni agregar un corredor que pueda diverger del que juzga.
    """

    def preparar(self, cuerpo, test, mas=None):
        """Deja el proyecto con `src/cosa.py` nuevo y un solo test, y devuelve el rc de mutar."""
        self.p.implementar("def otra():\n    return 0\n")
        self.p.git("add -A"); self.p.git("commit -qm previo")
        self.p.implementar(cuerpo)
        if mas:
            for nombre, texto in mas.items():
                (self.p.dir / nombre).write_text(texto)
        # El test del andamio se va: el que juzga es el que este caso escribe.
        (self.p.dir / "tests" / "test_cosa.py").write_text(test)
        self.p.git("add -A"); self.p.git("commit -qm nuevo")
        return correr(
            f"BASE=HEAD~1 CODIGO=src SUITE='python3 -m unittest discover -s tests -t . -q' "
            f"python3 {SCRIPTS}/mutar.py", self.p.dir)

    CUERPO = ("from src.pozo import pozo\n\n\n"
              "def guardar(x):\n"
              "    with pozo() as p:\n"
              "        p.append(x)\n"
              "        return len(p)\n")
    POZO = ("import contextlib\n\nHONDO = []\n\n\n"
            "@contextlib.contextmanager\ndef pozo():\n    yield HONDO\n")

    def test_la_linea_que_el_test_no_ejecuta_se_informa_como_tal(self):
        """El caso de T26: el test mockea la función de la propia tarea."""
        r = self.preparar(self.CUERPO,
                          "import unittest\nfrom unittest.mock import patch\n"
                          "import src.cosa\n\n"
                          "class TestCosa(unittest.TestCase):\n"
                          "    @patch('src.cosa.guardar')\n"
                          "    def test_con_mock(self, m):\n"
                          "        m.return_value = 1\n"
                          "        self.assertEqual(src.cosa.guardar('a'), 1)\n",
                          mas={"src/pozo.py": self.POZO})
        self.assertEqual(r.returncode, 3,
                         "un mutante que sobrevive sobre una línea que NO se ejecuta tiene "
                         f"que distinguirse del que sobrevive por aserciones flojas:\n"
                         f"{r.stdout}{r.stderr}")
        self.assertIn("NO se ejecuta", r.stdout, f"\n{r.stdout}")
        self.assertNotIn("cubre las líneas", r.stdout,
                         "no puede afirmar que cubre una línea que midió que no corre")

    def test_la_linea_que_si_se_ejecuta_sigue_siendo_aserciones_flojas(self):
        """El control, y es el que importa: el diagnóstico viejo tiene que sobrevivir donde
        era correcto. Un chequeo nuevo que se come el caso del anterior no arregla nada."""
        r = self.preparar(self.CUERPO,
                          "import unittest\nimport src.cosa\n\n"
                          "class TestCosa(unittest.TestCase):\n"
                          "    def test_no_explota(self):\n"
                          "        src.cosa.guardar('a')\n",
                          mas={"src/pozo.py": self.POZO})
        self.assertEqual(r.returncode, 1,
                         f"el test ejecuta la línea: el veredicto es el de siempre\n"
                         f"{r.stdout}{r.stderr}")
        self.assertNotIn("NO se ejecuta", r.stdout,
                         f"midió que la línea corre y dijo lo contrario:\n{r.stdout}")

    def test_un_test_que_verifica_de_verdad_sigue_en_verde(self):
        """El otro control: el centinela no puede ensuciar el caso bueno. Y si el mutador no
        escribiera el archivo, este test y el de arriba darían lo mismo — es la medición que
        me faltó las dos veces que un script de mutación no mutó y el verde pareció confirmar."""
        r = self.preparar(self.CUERPO,
                          "import unittest\nimport src.cosa\nimport src.pozo\n\n"
                          "class TestCosa(unittest.TestCase):\n"
                          "    def test_guarda_y_cuenta(self):\n"
                          "        src.pozo.HONDO.clear()\n"
                          "        self.assertEqual(src.cosa.guardar('a'), 1)\n"
                          "        self.assertEqual(src.pozo.HONDO, ['a'])\n",
                          mas={"src/pozo.py": self.POZO})
        self.assertEqual(r.returncode, 0, f"{r.stdout}{r.stderr}")

    def test_el_centinela_restaura_el_archivo(self):
        """Muta y restaura: si dejara el `raise` puesto, la tarea siguiente heredaría un
        archivo roto y el método le cobraría la falla a otro."""
        self.test_la_linea_que_el_test_no_ejecuta_se_informa_como_tal()
        self.assertNotIn("centinela", (self.p.dir / "src" / "cosa.py").read_text())
        self.assertNotIn("centinela", (self.p.dir / "src" / "pozo.py").read_text())
        self.assertEqual(self.p.git("status --porcelain").stdout.strip(), "",
                         "el centinela dejó el árbol sucio")

    def test_el_shell_elige_el_mensaje_segun_el_codigo(self):
        """El veredicto lo imprime `escribir-tests.sh`, no `mutar.py`: si el shell no mira el
        código 3, la distinción se mide y se tira. Se lee del CÓDIGO, no de los comentarios:
        los de este arreglo nombran las dos frases y un grep ingenuo matchearía la prosa."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        self.assertIn('"$RC_MUT" = "3"', codigo,
                      "el shell no distingue el código 3: el diagnóstico no llega al agente")
        i = codigo.index('"$RC_MUT" = "3"')
        bloque = codigo[i:i + 700]
        self.assertIn("NO EJECUTA", bloque, f"\n{bloque[:400]}")
        self.assertNotIn("cubre las líneas", bloque[:bloque.index("else")],
                         "en la rama del 3 no puede afirmar que cubre las líneas")


class TestUnaAsercionQueNoPuedeFallarConNingunaImplementacion(unittest.TestCase):
    """Los cinco pasos del validador comparan el test contra VERSIONES DEL PRODUCTO, y por
    eso ninguno ve el test que no mira el producto en absoluto.

    Medido el 2026-10-25: T26 de clasificados tenía ACEPTADO este test, uno de los tres de
    la tarea.

        password = "mi_password_segura"
        expected_hash = hashlib.sha256(password.encode()).hexdigest()
        assert expected_hash == hashlib.sha256(password.encode()).hexdigest()

    Los dos lados son la misma expresión: no hay implementación —ninguna, nunca— con la que
    eso falle. Pasó «falla sin la implementación» porque sus compañeros de archivo importan
    el módulo y el import es lo que revienta; pasó el brazo nulo por lo mismo; y los
    mutantes no lo tocan porque muta el producto, que este test no llama. Se llamaba
    `test_insert_user_hashea_con_sha256`, afirmando lo contrario de lo que la implementación
    documenta —que el hasheo es del servicio, no de la capa de datos—, así que leerlo por
    encima tranquilizaba.

    El chequeo es estático y exacto, y va antes de gastar tres pasadas de suite."""

    def correr(self, texto, nombre="test_x.py", extra=None):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-aserciones-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / ".git").mkdir()                     # raíz del repo: define qué es «del producto»
        (d / "src").mkdir()
        (d / "src" / "__init__.py").touch()
        (d / "src" / "cosa.py").write_text("def f(x):\n    return x * 2\n")
        for n, t in (extra or {}).items():
            (d / n).write_text(t)
        (d / nombre).write_text(texto)
        return correr(f"python3 {SCRIPTS}/_aserciones.py {nombre}", d)

    def test_los_dos_lados_iguales_por_una_variable_se_atrapan(self):
        """El caso literal de T26."""
        r = self.correr("import hashlib\n\n\n"
                        "def test_hashea(self):\n"
                        "    clave = 'x'\n"
                        "    esperado = hashlib.sha256(clave.encode()).hexdigest()\n"
                        "    assert esperado == hashlib.sha256(clave.encode()).hexdigest()\n")
        self.assertEqual(r.returncode, 1, f"{r.stdout}{r.stderr}")
        self.assertIn("no pueden fallar", r.stdout)
        self.assertIn("test_hashea", r.stdout, "el hallazgo tiene que venir con su sujeto")

    def test_tambien_en_la_forma_de_unittest(self):
        r = self.correr("import hashlib\nimport unittest\n\n\n"
                        "class TestX(unittest.TestCase):\n"
                        "    def test_hashea(self):\n"
                        "        esperado = hashlib.sha256(b'x').hexdigest()\n"
                        "        self.assertEqual(esperado, hashlib.sha256(b'x').hexdigest())\n")
        self.assertEqual(r.returncode, 1, f"{r.stdout}{r.stderr}")

    # ── Los controles. Son la mitad del chequeo: uno que muerde al test honesto se apaga.
    def test_el_test_de_idempotencia_sobre_el_producto_no_se_marca(self):
        """`assert f(x) == f(x)` sobre una función DEL PRODUCTO es una afirmación de verdad
        sobre el producto —que es determinista— y tiene que pasar."""
        r = self.correr("from src.cosa import f\n\n\n"
                        "def test_determinista():\n"
                        "    assert f(3) == f(3)\n")
        self.assertEqual(r.returncode, 0, f"muerde al test honesto:\n{r.stdout}{r.stderr}")

    def test_el_test_de_idempotencia_sobre_un_ayudante_propio_tampoco(self):
        """Lo midieron dos tests de esta misma suite: `assertEqual(self.huella(d),
        self.huella(d))`, que dice «la huella tiene que ser estable». Es la afirmación, no
        una tautología, y el chequeo la marcaba."""
        r = self.correr("import unittest\n\n\n"
                        "class TestX(unittest.TestCase):\n"
                        "    def huella(self):\n        return 1\n"
                        "    def test_estable(self):\n"
                        "        self.assertEqual(self.huella(), self.huella())\n")
        self.assertEqual(r.returncode, 0, f"muerde al test honesto:\n{r.stdout}{r.stderr}")

    def test_que_algo_no_cambio_despues_de_una_llamada_tampoco(self):
        """`antes = f.read_text()` … `correr(...)` … `assertEqual(antes, f.read_text())` es
        un test legítimo de que algo NO cambió, y los dos lados son el mismo árbol. Lo que
        lo distingue es que en el medio pasó algo.

        Eran 4 de los 6 falsos positivos de la primera versión, y por un bug mío: el orden
        era `if Assign … elif hay_Call`, así que una asignación que CONTIENE una llamada
        —`salida = correr(...)`, la forma más común que hay— entraba por la primera rama y
        no invalidaba nada."""
        r = self.correr("import pathlib\nimport unittest\n\n\n"
                        "class TestX(unittest.TestCase):\n"
                        "    def test_no_cambio(self):\n"
                        "        p = pathlib.Path('src/cosa.py')\n"
                        "        antes = p.read_text()\n"
                        "        salida = p.stat()\n"
                        "        self.assertEqual(antes, p.read_text())\n")
        self.assertEqual(r.returncode, 0, f"muerde al test honesto:\n{r.stdout}{r.stderr}")

    def test_los_tests_que_ya_existen_pasan_todos(self):
        """El control de verdad, y el que decide si esto se puede encender: los 31 archivos
        de test del repo —los dos proyectos ejemplo, las plantillas y esta suite, que sola
        tiene miles de aserciones— no pueden dar un solo falso positivo. La primera versión
        daba 6 y los 6 eran legítimos."""
        tests = sorted(str(p) for d in ("ejemplo-clasificados", "ejemplo-pacman",
                                        "pruebas", "plantillas")
                       for p in (RAIZ / d).rglob("test_*.py"))
        self.assertGreater(len(tests), 20, "el control no sirve si no encontró los tests")
        r = correr(f"python3 {SCRIPTS}/_aserciones.py " + " ".join(tests), RAIZ)
        self.assertEqual(r.returncode, 0,
                         f"falso positivo sobre tests que ya existen:\n{r.stdout}")

    def test_el_validador_lo_corre_y_falla_cerrado(self):
        """Se lee del CÓDIGO y no de los comentarios: los de este arreglo nombran el chequeo
        varias veces y un grep ingenuo matchearía la prosa.

        Falla cerrado por la lección que el fixture de esta suite aprendió a los golpes: una
        guarda `[ -f auxiliar ]` que saltea el paso cuando el auxiliar no está hace que el
        paso no corra nunca y nadie se entere."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        # La INVOCACIÓN, no la mención. La primera versión de este test buscaba
        # «_aserciones.py» en el código y daba verde con la invocación apuntada a
        # /dev/null, porque la guarda `[ ! -f ... ]` seguía nombrando el archivo. Un test
        # que afirma menos que su sujeto: el bug reintroducido pasó entero.
        invoca = [l for l in codigo.split("\n")
                  if "_aserciones.py" in l and "python3" in l]
        self.assertTrue(invoca, f"el validador no INVOCA el chequeo:\n{codigo[:0]}")
        self.assertIn("_aserciones.py", invoca[0].split("python3", 1)[1],
                      f"corre otra cosa, no el chequeo:\n{invoca[0]}")
        i = codigo.index("_aserciones.py")
        bloque = codigo[i - 200:i + 900]
        self.assertIn("malo ", bloque, f"lo corre y no hace nada con el resultado:\n{bloque}")
        self.assertIn('[ ! -f "$AQUI/_aserciones.py" ]', bloque,
                      "si el auxiliar falta tiene que ser rojo, no un salteo silencioso")
        self.assertIn('"$RC_A" != "0"', bloque,
                      "un rc inesperado también es rojo: el chequeo no se puede saltear")


class TestElBrazoNuloConVariosArchivosSeSatisfaceConUno(unittest.TestCase):
    """El brazo nulo vaciaba los archivos de la tarea TODOS JUNTOS y una sola pasada
    decidía, así que bastaba que UNO fuera necesario para dar verde: los demás no se
    preguntaban nunca.

    Medido el 2026-10-25 en T04 de clasificados, cerrada como ✅ hecha. Declara tres
    archivos —`rutas/auth.py`, `servicios/auth.py`, `datos/users.py`—, sus tres tests
    mockean `read_user_by_email`, y ese archivo es un stub que lo dice en su propio
    comentario: «Por ahora retornamos None como placeholder». Vaciar los tres rompía el test
    por los otros dos; vaciar sólo `users.py` no cambia nada. Con ese stub el login de
    clasificados no funciona para ningún usuario, y la tarea está cerrada.

    Las tres tareas de clasificados con más de un archivo .py son T04, T26 y T28, y son las
    tres que fallaron. Es el molde ruta+servicio+datos, donde el test mockea la capa de datos
    y el brazo nulo conjunto no lo nota.

    Y el dato estaba: `vaciar.py` SIEMPRE supo reconocer el stub —su comentario decía «ya era
    un stub: no cuenta»— y de ese reconocimiento sacaba la conclusión opuesta a la correcta.
    Es el mismo patrón que el ejecutor de las 9 AM: el método tenía el dato adentro de un
    descarte y lo tiraba."""

    VACIAR = SCRIPTS / "vaciar.py"

    def molde_de_T04(self):
        """Ruta + servicio + datos, con el test mockeando la capa de datos. Es la forma de
        T04, T26 y T28, y la que el brazo nulo conjunto no puede juzgar."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-brazo-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "app").mkdir()
        (d / "app" / "__init__.py").touch()
        # La capa de datos: un STUB, como el users.py de T04.
        (d / "app" / "datos.py").write_text(
            "def leer_usuario(email):\n"
            "    \"\"\"El usuario como dict, o None.\"\"\"\n"
            "    # Por ahora devolvemos None como placeholder\n"
            "    return None\n")
        # El servicio, que sí tiene lógica.
        # `from app import datos` y no `from app.datos import leer_usuario`: así es T04
        # —`from backend.app.datos import users`, `users.read_user_by_email(email)`— y es lo
        # que hace que parchear la ruta del módulo tenga efecto. Con el `from … import
        # nombre` el nombre queda ligado al importar y el parche no llega: mi primera versión
        # del molde era infiel por eso y sus dos mediciones no medían nada.
        (d / "app" / "servicio.py").write_text(
            "from app import datos\n\n\n"
            "def entrar(email, clave):\n"
            "    u = datos.leer_usuario(email)\n"
            "    if u is None or u['clave'] != clave:\n"
            "        return None\n"
            "    return u['id']\n")
        # El test: mockea la capa de datos, que es un archivo DE LA TAREA.
        (d / "test_login.py").write_text(
            "from unittest.mock import patch\n"
            "from app.servicio import entrar\n\n\n"
            "@patch('app.datos.leer_usuario')\n"
            "def test_entra(m):\n"
            "    m.return_value = {'id': 7, 'clave': 'x'}\n"
            "    assert entrar('a@b', 'x') == 7\n\n\n"
            "@patch('app.datos.leer_usuario')\n"
            "def test_clave_mala(m):\n"
            "    m.return_value = {'id': 7, 'clave': 'x'}\n"
            "    assert entrar('a@b', 'z') is None\n")
        return d, "python3 -m pytest -q test_login.py"

    def test_el_brazo_nulo_conjunto_da_verde_sobre_el_molde_de_T04(self):
        """La medición del defecto: vaciar los dos archivos juntos ROMPE el test, así que el
        brazo nulo conjunto acepta — y `app/datos.py` nunca se preguntó."""
        d, suite = self.molde_de_T04()
        self.assertEqual(correr(suite, d).returncode, 0, "el test pasa con la implementación")
        correr(f"python3 {self.VACIAR} app/datos.py app/servicio.py", d)
        self.assertNotEqual(correr(suite, d).returncode, 0,
                            "vaciar los dos juntos rompe el test: por eso el brazo nulo "
                            "conjunto daba verde y el stub pasaba")
        correr(f"python3 {self.VACIAR} --restaurar", d)

    def test_pero_vaciar_solo_la_capa_de_datos_no_cambia_nada(self):
        """El otro lado de la misma medición, y es el veredicto que faltaba: el test no nota
        que `app/datos.py` se quedó sin cuerpo, porque lo mockea."""
        d, suite = self.molde_de_T04()
        correr(f"python3 {self.VACIAR} app/datos.py", d)
        self.assertEqual(correr(suite, d).returncode, 0,
                         "el test no prueba app/datos.py: preguntándole de a uno se ve")
        correr(f"python3 {self.VACIAR} --restaurar", d)

    def test_vaciar_informa_el_stub_en_vez_de_descartarlo(self):
        """`vaciar.py` reconocía el stub y lo descartaba del conteo. Ahora es el hallazgo."""
        d, _ = self.molde_de_T04()
        r = correr(f"python3 {self.VACIAR} app/datos.py", d)
        self.assertEqual(r.returncode, 3,
                         f"un stub entre los archivos de la tarea es un veredicto, no un ⊘:"
                         f"\n{r.stdout}{r.stderr}")
        self.assertIn("NO implementa nada", r.stdout, f"\n{r.stdout}")
        self.assertIn("leer_usuario", r.stdout, "el hallazgo viene con su sujeto")
        correr(f"python3 {self.VACIAR} --restaurar", d)

    def test_un_archivo_con_logica_de_verdad_no_se_marca_como_stub(self):
        """El control: `vaciar.py` no puede llamar stub a lo que tiene cuerpo."""
        d, _ = self.molde_de_T04()
        r = correr(f"python3 {self.VACIAR} app/servicio.py", d)
        self.assertEqual(r.returncode, 0, f"{r.stdout}{r.stderr}")
        self.assertNotIn("stub", r.stdout, f"\n{r.stdout}")
        correr(f"python3 {self.VACIAR} --restaurar", d)

    def test_una_funcion_vacia_entre_varias_con_cuerpo_es_aviso_y_no_rojo(self):
        """El control que decide si esto se puede encender. Vaciando también el `.venv` de
        clasificados aparecen 16 archivos con funciones que devuelven None y las 16 son
        legítimas —clases base que la subclase sobreescribe, shims de compatibilidad— y las
        16 viven rodeadas de decenas de funciones con cuerpo. Sin la distinción, el chequeo
        marcaría la primera clase base que una tarea escriba.

        No es degradar un rojo por su compañía, que es un defecto que este método ya cerró:
        «este archivo no implementa nada» y «esta función de diez está vacía» son dos
        afirmaciones distintas, y la segunda la contesta el brazo nulo de ese archivo."""
        d, _ = self.molde_de_T04()
        (d / "app" / "base.py").write_text(
            "class Fuente:\n"
            "    def extra(self):\n"
            "        \"\"\"Lo que la subclase quiera agregar.\"\"\"\n"
            "        return None\n\n"
            "    def leer(self, k):\n"
            "        return {'k': k}\n\n"
            "    def escribir(self, k, v):\n"
            "        return (k, v)\n")
        r = correr(f"python3 {self.VACIAR} app/base.py", d)
        self.assertEqual(r.returncode, 0,
                         f"una clase base con un método vacío no es «no implementa nada»:"
                         f"\n{r.stdout}{r.stderr}")
        self.assertIn("⚠", r.stdout, f"pero tiene que decirlo:\n{r.stdout}")
        self.assertNotIn("NO implementa nada", r.stdout, f"\n{r.stdout}")
        correr(f"python3 {self.VACIAR} --restaurar", d)

    def test_el_validador_pregunta_archivo_por_archivo(self):
        """Se lee del CÓDIGO: los comentarios de este arreglo nombran el defecto varias
        veces y un grep ingenuo matchearía la prosa."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        i = codigo.index("4. El BRAZO NULO") if "4. El BRAZO NULO" in codigo else 0
        bloque = codigo[codigo.index("PREGUNTADOS=0"):]
        bloque = bloque[:bloque.index("else")]
        self.assertIn("for f in $impl", bloque,
                      f"el brazo nulo tiene que preguntar por cada archivo:\n{bloque}")
        self.assertIn('vaciar.py" "$f"', bloque,
                      "y vaciar UNO a la vez, no todos juntos")
        self.assertIn('"$RC_V" = "3"', bloque,
                      "y tratar el stub como rojo, que es el código que vaciar.py devuelve")
        # La limpieza de la base, que tiene que seguir antes de CADA pasada.
        self.assertIn("limpiar_base_del_arbol", bloque,
                      "cada pasada arranca con la base vacía, igual que las tres de arriba")


class TestReabrirNoPuedeQuedarBloqueadoPorElDisco(unittest.TestCase):
    """El método ordenaba una operación que él mismo rechazaba.

    `coherencia.py` termina sus rojos más graves con «hay que REABRIR TNN», y
    `reabrir.sh` existe para eso. Pero reabrir SACA del tronco el código que la tarea
    produjo —si no, el test pasa de entrada y el gate concluye «el test no prueba nada»— y
    `validar-plan.py` usaba la EXISTENCIA del archivo como respaldo para no marcar una
    referencia de lectura:

        T26 nombra `backend/tests/test_auth_backend.py` para decir cómo se hace el patch, y
        ese test está en el repo desde T04.

    Sacado el código de T04, esa referencia se convertía en «nadie lo va a escribir», el
    juez de `reabrir.sh` revertía, y T04 no se podía reabrir. Medido el 2026-10-25 al
    intentar reabrirla: el veredicto dependía del orden de las operaciones y no del plan.

    La autoridad correcta estaba a mano y no mira el disco: la TABLA DE TESTS del plan ya
    dice qué test escribe cada tarea."""

    def proyecto(self, contrato_de_T02, con_tabla_de_tests=True):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-reabrir-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        tabla_tests = ("\n## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
                       "| T01 | tests/test_uno.py | TestUno |\n"
                       "| T02 | tests/test_dos.py | TestDos |\n"
                       if con_tabla_de_tests else "")
        (d / "PLAN.md").write_text(
            "# Plan\n\n**Estado del gate G0:** aprobado por nadie el 2026-01-01\n\n"
            "## Requisitos\n\n- `uno` — que haya uno\n\n"
            "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T01 | Uno | — | src/uno.py | pendiente |\n"
            "| T02 | Dos | T01 | src/dos.py | pendiente |\n" + tabla_tests)
        # Las dependencias y el test de cada tarea tienen que coincidir con el plan: el
        # validador cruza las dos cosas, y mi primera versión del fixture las contradecía.
        # Un fixture incoherente no mide el chequeo que uno quiere medir, mide el otro.
        for tid, arch, dep, test, clase, contrato in (
                ("T01", "src/uno.py", "—", "tests/test_uno.py", "TestUno",
                 "- Escribí `src/uno.py`.\n"),
                ("T02", "src/dos.py", "T01", "tests/test_dos.py", "TestDos",
                 contrato_de_T02)):
            (d / "tareas" / f"{tid}-cosa.md").write_text(
                f"# {tid} — Cosa\n\n**Estado:** pendiente\n**Depende de:** {dep}\n"
                f"**Archivos que podés tocar:** {arch}\n**Prohibido tocar:** Ninguno\n\n"
                f"## Objetivo\n\nQue haya una cosa.\n\n"
                f"## Contrato\n\n{contrato}\n"
                f"## Tests (ya escritos, fallando)\n\n"
                f"Archivo: `{test}`, clase `{clase}`.\n")
        return d

    def validar(self, d):
        return correr(f"PLAN=PLAN.md python3 {SCRIPTS}/validar-plan.py", d)

    def test_nombrar_el_test_de_otra_tarea_vale_aunque_el_archivo_no_exista(self):
        """El caso de T26 → T04: una referencia de lectura al test de otra tarea. En el
        disco no está nada —es un proyecto nuevo— y la tabla de tests dice quién lo escribe."""
        d = self.proyecto("- Seguí el patrón de `tests/test_uno.py`, que mockea la capa.\n")
        r = self.validar(d)
        self.assertEqual(r.returncode, 0,
                         f"el test de otra tarea está repartido en la tabla de tests: "
                         f"nombrarlo no es pedir que alguien lo escriba\n{r.stdout}{r.stderr}")

    def test_sin_la_tabla_de_tests_el_mismo_plan_queda_en_rojo(self):
        """El control de que lo que lo salva es la TABLA y no una laxitud nueva: el mismo
        plan, sin la tabla que reparte los tests, sigue siendo un archivo que nadie escribe."""
        d = self.proyecto("- Seguí el patrón de `tests/test_uno.py`, que mockea la capa.\n",
                          con_tabla_de_tests=False)
        r = self.validar(d)
        self.assertNotEqual(r.returncode, 0,
                            f"sin la tabla nadie escribe ese test:\n{r.stdout}")
        self.assertIn("nadie lo va a escribir", r.stdout)

    def test_el_archivo_que_ninguna_tarea_tiene_sigue_en_rojo(self):
        """El otro control, y es el que importa: el chequeo existe para atrapar esto —fue el
        caso real de T03— y no puede haberse apagado."""
        d = self.proyecto("- Escribí `src/inexistente_xyz.py` con la lógica.\n")
        r = self.validar(d)
        self.assertNotEqual(r.returncode, 0, f"se apagó el chequeo:\n{r.stdout}")
        self.assertIn("inexistente_xyz.py", r.stdout)
        self.assertIn("nadie lo va a escribir", r.stdout)

    def test_el_validador_no_decide_esto_mirando_el_disco(self):
        """Se lee del CÓDIGO: los comentarios de este arreglo nombran el disco y la tabla
        varias veces."""
        fuente = (SCRIPTS / "validar-plan.py").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        i = codigo.index("nadie lo va a escribir")
        bloque = codigo[max(0, i - 900):i]
        self.assertIn("tests_plan.values()", bloque,
                      f"la tabla de tests tiene que entrar en los asignados:\n{bloque[-400:]}")


class TestReabrirNoPuedeRomperUnaTareaQueSigueHecha(unittest.TestCase):
    """Reabrir rompe el test de la tarea que reabre: eso es tests-first y es el punto. Lo que
    no puede es romper el de OTRA tarea que sigue marcada como hecha — ésa queda con su verde
    cobrado y su código afuera, y el rojo se lo va a cobrar la próxima tarea que corra.

    Medido el 2026-10-25 reabriendo T04 de clasificados: dejó 4 tests en error, uno de ellos
    `test_sesion.py`, que es de T04b — una tarea ✅ hecha que declara el mismo
    `backend/app/servicios/auth.py`. Los dos jueces que había miraban el plan y las
    contradicciones de coherencia, y ninguno miraba el árbol.

    El aviso viene con nombre propio porque las dos autoridades están a mano: la tabla de
    tests del plan dice de quién es cada archivo de test, y el archivo de cada tarea dice su
    estado. Quien decida la cascada no tiene que adivinar cuál."""

    def proyecto(self, estado_de_T02="✅ hecha"):
        """T01 y T02 comparten `src/compartido.py`, y T02 está cerrada. Es la forma de
        T04/T04b: la segunda extiende lo que escribió la primera."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-tercerjuez-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        for sub in ("tareas", "scripts", "src", "tests"):
            (d / sub).mkdir()
        shutil.copy(PLANTILLAS / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "src" / "__init__.py").touch()
        (d / "tests" / "__init__.py").touch()
        (d / "src" / "compartido.py").write_text(
            "def uno():\n    return 1\n\n\ndef dos():\n    return 2\n")
        # `unittest.TestCase` y no una clase pelada: la plantilla `correr-suite.sh` del
        # proyecto de juguete corre unittest, que no descubre las clases estilo pytest. Mi
        # primera versión del fixture no corría un solo test —«Ran 0 tests»— así que el juez
        # no tenía nada que medir y el caso daba verde con el defecto puesto.
        (d / "tests" / "test_uno.py").write_text(
            "import unittest\nfrom src.compartido import uno\n\n\n"
            "class TestUno(unittest.TestCase):\n"
            "    def test_uno(self):\n        self.assertEqual(uno(), 1)\n")
        (d / "tests" / "test_dos.py").write_text(
            "import unittest\nfrom src.compartido import dos\n\n\n"
            "class TestDos(unittest.TestCase):\n"
            "    def test_dos(self):\n        self.assertEqual(dos(), 2)\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n**Estado del gate G0:** aprobado por nadie el 2026-01-01\n\n"
            "## Requisitos\n\n- `uno` — que haya uno\n\n"
            "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T01 | Uno | — | src/compartido.py | ✅ hecha |\n"
            f"| T02 | Dos | T01 | src/compartido.py | {estado_de_T02} |\n"
            "\n## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
            "| T01 | tests/test_uno.py | TestUno |\n"
            "| T02 | tests/test_dos.py | TestDos |\n")
        for tid, dep, test, clase, estado in (
                ("T01", "—", "tests/test_uno.py", "TestUno", "✅ hecha"),
                ("T02", "T01", "tests/test_dos.py", "TestDos", estado_de_T02)):
            (d / "tareas" / f"{tid}-cosa.md").write_text(
                f"# {tid} — Cosa\n\n**Estado:** {estado}\n**Depende de:** {dep}\n"
                f"**Archivos que podés tocar:** src/compartido.py\n"
                f"**Prohibido tocar:** Ninguno\n\n"
                f"## Objetivo\n\nQue haya una cosa.\n\n"
                f"## Contrato\n\n- Escribí `src/compartido.py`.\n\n"
                f"## Tests (ya escritos, fallando)\n\n"
                f"Archivo: `{test}`, clase `{clase}`.\n")
        correr("git init -q .", d)
        correr("git -c user.email=t@t -c user.name=t add -A", d)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', d)
        return d

    def test_reabrir_T01_se_revierte_porque_T02_sigue_hecha(self):
        d = self.proyecto(estado_de_T02="✅ hecha")
        antes = (d / "src" / "compartido.py").read_text()
        r = correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01 motivo", d)
        self.assertNotEqual(r.returncode, 0, f"tenía que revertir:\n{r.stdout}{r.stderr}")
        self.assertIn("marcadas como hechas", r.stdout, f"\n{r.stdout}")
        self.assertIn("T02", r.stdout, "el aviso tiene que nombrar la tarea afectada")
        self.assertEqual((d / "src" / "compartido.py").read_text(), antes,
                         "revirtió el veredicto pero dejó el código afuera")
        self.assertIn("**Estado:** ✅ hecha", (d / "tareas" / "T01-cosa.md").read_text(),
                      "y el estado de la tarea tiene que volver")

    def test_si_T02_ya_estaba_pendiente_la_reapertura_procede(self):
        """El control, y es el que decide si el juez sirve: no puede bloquear toda
        reapertura. Con T02 pendiente su test ya no es un verde cobrado, así que romperlo no
        le quita nada a nadie."""
        d = self.proyecto(estado_de_T02="pendiente")
        r = correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01 motivo", d)
        self.assertEqual(r.returncode, 0,
                         f"el juez no puede bloquear una reapertura legítima:"
                         f"\n{r.stdout}{r.stderr}")
        self.assertFalse((d / "src" / "compartido.py").exists(),
                         "si procede, el código tiene que salir del tronco")

    def test_la_cascada_reabre_las_dos_y_procede(self):
        """Dos tareas cerradas que comparten un archivo no se pueden reabrir de a una: el
        tercer juez frena la primera, con razón. La cascada no es una comodidad, es la única
        forma de reabrir en ese caso — y el juez ya dice con nombre propio cuál es la otra.

        Es el caso de T04 y T04b, que comparten `backend/app/servicios/auth.py` porque la
        segunda extiende lo que escribió la primera."""
        d = self.proyecto(estado_de_T02="✅ hecha")
        r = correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01,T02 motivo", d)
        self.assertEqual(r.returncode, 0,
                         f"la cascada tiene que proceder:\n{r.stdout}{r.stderr}")
        self.assertIn("cascada", r.stdout, "y decir que lo es")
        self.assertFalse((d / "src" / "compartido.py").exists(),
                         "el código compartido sale del tronco")
        for tid in ("T01", "T02"):
            self.assertIn("**Estado:** pendiente",
                          (d / "tareas" / f"{tid}-cosa.md").read_text(),
                          f"{tid} tiene que quedar pendiente")
            self.assertRegex((d / "PLAN.md").read_text(),
                             rf"\| *{tid} *\|[^|\n]*\|[^|\n]*\|[^|\n]*\| *pendiente *\|",
                             f"y también en la TABLA: el deductor de etapas lee la tabla")
        self.assertFalse((d / "tests" / "test_uno.py").exists(), "y sus tests también salen")
        self.assertFalse((d / "tests" / "test_dos.py").exists())

    def test_la_cascada_tambien_se_revierte_entera(self):
        """Si el juez frena, las DOS vuelven. Restaurar una sola deja el plan mintiendo en
        la mitad, que es peor que no haber tocado nada: `reabrir.sh` ya dice en su cabecera
        que reabrir son cuatro cosas y hacer tres está peor que hacer ninguna."""
        d = self.proyecto(estado_de_T02="✅ hecha")
        # T03 cerrada y compartiendo el archivo: nadie la incluye en la cascada, así que el
        # juez tiene que frenar las dos.
        (d / "tareas" / "T03-cosa.md").write_text(
            "# T03 — Cosa\n\n**Estado:** ✅ hecha\n**Depende de:** T01\n"
            "**Archivos que podés tocar:** src/compartido.py\n**Prohibido tocar:** Ninguno\n\n"
            "## Objetivo\n\nOtra cosa.\n\n## Contrato\n\n- Escribí `src/compartido.py`.\n\n"
            "## Tests (ya escritos, fallando)\n\nArchivo: `tests/test_tres.py`, clase `TestTres`.\n")
        (d / "tests" / "test_tres.py").write_text(
            "import unittest\nfrom src.compartido import uno\n\n\n"
            "class TestTres(unittest.TestCase):\n"
            "    def test_tres(self):\n        self.assertEqual(uno(), 1)\n")
        plan = (d / "PLAN.md").read_text().replace(
            "| T02 | Dos | T01 | src/compartido.py | ✅ hecha |\n",
            "| T02 | Dos | T01 | src/compartido.py | ✅ hecha |\n"
            "| T03 | Tres | T01 | src/compartido.py | ✅ hecha |\n").replace(
            "| T02 | tests/test_dos.py | TestDos |\n",
            "| T02 | tests/test_dos.py | TestDos |\n| T03 | tests/test_tres.py | TestTres |\n")
        (d / "PLAN.md").write_text(plan)
        antes = (d / "src" / "compartido.py").read_text()
        r = correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01,T02 motivo", d)
        self.assertNotEqual(r.returncode, 0, f"T03 sigue hecha:\n{r.stdout}{r.stderr}")
        self.assertIn("T03", r.stdout, "y el aviso tiene que nombrarla")
        self.assertEqual((d / "src" / "compartido.py").read_text(), antes,
                         "el código tiene que volver")
        for tid in ("T01", "T02"):
            self.assertIn("**Estado:** ✅ hecha",
                          (d / "tareas" / f"{tid}-cosa.md").read_text(),
                          f"{tid} no volvió a su estado: la reversión dejó el plan mintiendo")

    def test_la_nota_de_reapertura_va_arriba_no_al_final(self):
        """La nota lleva el dato que corrige a la tarea, y al final llegaba después de todo
        lo que corrige.

        Medido el 2026-10-25 en T26: su nota decía «su codigo inserta la columna
        password_hash y la tabla usuarios tiene clave_hash», y estaba en la línea 104 de 110
        — después de cien líneas donde el enunciado nombra `password_hash` cuatro veces,
        incluida la firma `def insert_user(email, password_hash)` que le pide escribir. El
        agente escribió `password_hash` y MySQL lo rechazó con «Unknown column».

        Un enunciado se lee de arriba hacia abajo: la corrección tiene que llegar antes que
        lo corregido."""
        d = self.proyecto(estado_de_T02="pendiente")
        correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01 el-motivo-medido", d)
        texto = (d / "tareas" / "T01-cosa.md").read_text()
        lineas = texto.split("\n")
        i_nota = next(i for i, l in enumerate(lineas) if l.startswith("## Reabierta"))
        i_primera = next(i for i, l in enumerate(lineas) if l.startswith("## "))
        self.assertEqual(i_nota, i_primera,
                         f"la nota tiene que ser la PRIMERA sección:\n{texto}")
        # Y el encabezado que los scripts leen por posición queda intacto y antes.
        for campo in ("**Estado:**", "**Depende de:**", "**Archivos que podés tocar:**"):
            i_campo = next(i for i, l in enumerate(lineas) if l.startswith(campo))
            self.assertLess(i_campo, i_nota, f"{campo} tiene que quedar antes de la nota")
        self.assertIn("el-motivo-medido", texto)

    def test_dos_reaperturas_no_dejan_dos_notas(self):
        """Dos bloques «## Reabierta» y el lector no sabe cuál rige. Se saca DONDE ESTÉ y no
        sólo si cae en el corte: una nota escrita por la versión anterior de este script está
        al final, y mirando sólo la primera sección sobrevivía. Lo midió T26, que quedó con
        dos —la de abajo diciendo password_hash y la de arriba diciendo clave_hash—, que es
        peor que no haber movido nada."""
        d = self.proyecto(estado_de_T02="pendiente")
        t = d / "tareas" / "T01-cosa.md"
        # Una nota vieja, al final, como la dejaba la versión anterior.
        t.write_text(t.read_text() + "\n## Reabierta\n\nla nota vieja de abajo\n")
        correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01 la-nota-nueva", d)
        texto = t.read_text()
        self.assertEqual(texto.count("## Reabierta"), 1,
                         f"quedaron dos notas:\n{texto}")
        self.assertIn("la-nota-nueva", texto)
        self.assertNotIn("la nota vieja de abajo", texto,
                         "la nota vieja tiene que irse, esté donde esté")

    def test_el_juez_no_rasca_la_salida_de_la_suite(self):
        """La primera versión buscaba `FAILED ruta::test` y `ERROR ruta`, que es el formato de
        pytest. La plantilla `correr-suite.sh` de un proyecto con unittest imprime `FAILED
        (errors=2)`, así que el grep matcheaba eso como si fuera un nombre de test y el juez
        quedaba comparando basura — fallando ABIERTO en todo proyecto unittest, que es la
        mitad de los ejemplos. Quinta vez que el que raspa busca una forma que el productor no
        emite. Lo único que se usa es el código de salida, que es el contrato que el gate ya
        usa para juzgar."""
        fuente = (SCRIPTS / "reabrir.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        i = codigo.index("marcadas como hechas")
        bloque = codigo[max(0, i - 2000):i]
        self.assertNotIn("FAILED", bloque,
                         f"el juez no puede depender del formato de un corredor:\n{bloque}")
        self.assertIn("correr-suite.sh", bloque, "mide corriendo el test de la otra tarea")

    def test_el_test_de_la_otra_tarea_sale_de_la_tabla_de_tests(self):
        """Las dos tablas del plan tienen tres columnas y la de tareas viene primero —`| T04b
        | Verificar sesión | T04 |`—, así que un grep por la fila de la tarea devuelve el
        título y la dependencia. Tercera vez hoy que un extractor de este método lee la tabla
        de al lado, y la suite ya tiene un test que dice «la segunda tabla no pisa la
        primera»."""
        d = self.proyecto(estado_de_T02="✅ hecha")
        r = correr(f"PROYECTO=. bash {SCRIPTS}/reabrir.sh T01 motivo", d)
        self.assertIn("su test tests/test_dos.py", r.stdout,
                      f"el juez tiene que nombrar el test que midió, no decir que no pudo:"
                      f"\n{r.stdout}")


class TestLoViejoNoVuelveAPasarPorElInstrumentoNuevo(unittest.TestCase):
    """El método mejora sus instrumentos y los instrumentos nuevos encuentran cosas en lo ya
    cerrado — pero nada vuelve a pasar el material viejo por el instrumento nuevo. El gate
    corre cuando la tarea se cierra, y después nadie vuelve, así que cada chequeo que se
    agrega sólo protege lo que viene.

    Medido el 2026-10-25. Ese día se agregaron cuatro chequeos y, pasando a mano los nueve
    pares test↔implementación que el plan de clasificados permite preguntar, aparecieron DOS
    verdes falsos entre 19 tareas cerradas: T04 —un archivo que no implementa nada y lo dice
    en su propio comentario— y T04b, cuyo test fue reemplazado al arreglar el brazo nulo y
    quedó ROJO en el tronco desde entonces sin que nadie se lo atribuyera.

    `auditar-cerradas.sh` no inventa instrumentos: corre los que el validador ya usa, sobre
    el material viejo. Y no toca nada —ni estados, ni código, ni plan—: informa, y reabrir es
    otra decisión, otro comando y otros jueces."""

    def proyecto(self, cuerpo_de_la_impl, estado="✅ hecha", con_tabla=True):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-auditar-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        for sub in ("tareas", "scripts", "src", "tests"):
            (d / sub).mkdir()
        shutil.copy(PLANTILLAS / "correr-suite.sh", d / "scripts" / "correr-suite.sh")
        (d / "src" / "__init__.py").touch()
        (d / "tests" / "__init__.py").touch()
        (d / "src" / "cosa.py").write_text(cuerpo_de_la_impl)
        (d / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom unittest.mock import patch\nimport src.cosa\n\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    @patch('src.cosa.f')\n"
            "    def test_f(self, m):\n"
            "        m.return_value = 42\n"
            "        self.assertEqual(src.cosa.f(), 42)\n")
        tabla = ("\n## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
                 "| T01 | tests/test_cosa.py | TestCosa |\n" if con_tabla else "")
        (d / "PLAN.md").write_text(
            "# Plan\n\n**Estado del gate G0:** aprobado por nadie el 2026-01-01\n\n"
            "## Requisitos\n\n- `cosa` — que haya una cosa\n\n"
            "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            f"| T01 | Una cosa | — | src/cosa.py | {estado} |\n" + tabla)
        (d / "tareas" / "T01-cosa.md").write_text(
            f"# T01 — Una cosa\n\n**Estado:** {estado}\n**Depende de:** —\n"
            f"**Archivos que podés tocar:** src/cosa.py\n**Prohibido tocar:** Ninguno\n\n"
            f"## Objetivo\n\nQue haya una cosa.\n\n## Contrato\n\n- Escribí `src/cosa.py`.\n\n"
            f"## Tests (ya escritos, fallando)\n\nArchivo: `tests/test_cosa.py`, clase `TestCosa`.\n")
        # `_comun.sh` exige estar dentro de un repo git: sin esto el auditor salía con
        # «Corré esto desde adentro del repo git de tu proyecto» por stderr y stdout vacío,
        # así que los tests fallaban sin decir por qué. Un fixture al que le falta el
        # andamio mide el andamio.
        correr("git init -q .", d)
        correr("git -c user.email=t@t -c user.name=t add -A", d)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', d)
        return d

    def auditar(self, d):
        return correr(f"PROYECTO=. bash {SCRIPTS}/auditar-cerradas.sh", d)

    STUB = 'def f():\n    """Lo que sea."""\n    # Por ahora devolvemos None como placeholder\n    return None\n'
    BUENA = "def f():\n    return 42\n"

    def test_encuentra_la_tarea_cerrada_cuyo_archivo_no_implementa_nada(self):
        """El caso de T04, reproducido: cerrada, con un stub, y el test lo mockea."""
        r = self.auditar(self.proyecto(self.STUB))
        self.assertEqual(r.returncode, 1, f"{r.stdout}{r.stderr}")
        self.assertIn("no pasaría el gate de hoy", r.stdout)
        self.assertIn("NO implementa nada", r.stdout, f"\n{r.stdout}")
        self.assertIn("T01", r.stdout, "el hallazgo viene con su sujeto")

    def test_una_tarea_cerrada_sana_no_se_marca(self):
        """El control: el auditor no puede morder lo que está bien. Misma tarea, misma forma
        de test —con mock incluido—, pero la implementación implementa."""
        d = self.proyecto(self.BUENA)
        # El test mockea, así que el brazo nulo lo va a rechazar. Lo que este control mide es
        # que NO se marque como «no implementa nada», que es otro hallazgo.
        r = self.auditar(d)
        self.assertNotIn("NO implementa nada", r.stdout, f"\n{r.stdout}")

    def test_no_toca_nada_del_proyecto(self):
        """Auditar informa; cambiar es otra decisión y otro comando. Si el auditor dejara el
        estado o el código cambiados, el método estaría tomando por su cuenta la decisión que
        `reabrir.sh` somete a tres jueces."""
        # Con la implementación BUENA, no con el stub: sobre un archivo que sólo tiene stubs
        # `vaciar.py` no escribe nada —no hay cuerpos que vaciar— así que no hay nada que
        # restaurar y el test daba verde con el `--restaurar` sacado. Otra aserción más
        # angosta que su sujeto. Acá el archivo tiene cuerpo, se vacía de verdad, y si no se
        # restaura el proyecto queda roto.
        d = self.proyecto(self.BUENA)
        antes_impl = (d / "src" / "cosa.py").read_text()
        antes_tarea = (d / "tareas" / "T01-cosa.md").read_text()
        antes_plan = (d / "PLAN.md").read_text()
        self.auditar(d)
        self.assertEqual((d / "src" / "cosa.py").read_text(), antes_impl,
                         "dejó la implementación vaciada: el brazo nulo no restauró")
        self.assertEqual((d / "tareas" / "T01-cosa.md").read_text(), antes_tarea)
        self.assertEqual((d / "PLAN.md").read_text(), antes_plan)
        self.assertEqual(list((d / "src").glob("*.vaciar-original")), [],
                         "quedaron respaldos de vaciar.py tirados")

    def test_cero_auditadas_no_es_un_pase(self):
        """Mi primera versión informaba «✓ ninguna tarea cerrada falla los chequeos de hoy»
        después de preguntar por NINGUNA. Es el defecto que esta herramienta vino a encontrar,
        cometido en la herramienta, y lo encontró su primera corrida sobre `ejemplo-pacman`,
        donde no pudo leer un solo test."""
        d = self.proyecto(self.STUB, estado="pendiente")
        r = self.auditar(d)
        self.assertEqual(r.returncode, 2,
                         f"cero auditadas es un ⊘, no un verde:\n{r.stdout}{r.stderr}")
        self.assertIn("no es un pase", r.stdout, f"\n{r.stdout}")

    def test_el_test_sale_del_plan_o_del_archivo_de_la_tarea(self):
        """`ejemplo-pacman` no tiene tabla de tests: declara el test en cada tarea. Mirando
        sólo el plan, el auditor no servía en la mitad de los ejemplos."""
        r = self.auditar(self.proyecto(self.STUB, con_tabla=False))
        self.assertEqual(r.returncode, 1,
                         f"sin tabla de tests tiene que leerlo de la tarea:\n{r.stdout}")
        self.assertIn("NO implementa nada", r.stdout)

    def test_no_adivina_el_test_por_el_nombre_del_archivo(self):
        """En pacman `tareas/T01-laberinto.md` y `tests/test_laberinto.py` se corresponden, y
        deducirlo sería inferir lo que el plan no dice. Se informa el hueco con su sujeto."""
        d = self.proyecto(self.STUB, con_tabla=False)
        t = d / "tareas" / "T01-cosa.md"
        t.write_text(t.read_text().replace(
            "Archivo: `tests/test_cosa.py`, clase `TestCosa`.", "Los tests ya están escritos."))
        r = self.auditar(d)
        self.assertEqual(r.returncode, 2, f"sin test declarado no hay nada que auditar:\n{r.stdout}")
        self.assertIn("ni el plan ni su archivo declaran su test", r.stdout, f"\n{r.stdout}")


class TestElNombreDeLaBaseQueSeInformaEsElQueQuedaEscrito(unittest.TestCase):
    """El `.entorno` es la ÚNICA fuente de la base para todo lo que viene después: el test la
    lee de ahí y `limpiar_base_del_arbol` también. Si el nombre que el método deriva y el que
    queda escrito no son el mismo, se informa una base, se limpia otra y el test usa una
    tercera — y el choque reaparece como `Duplicate entry` con el veredicto cobrado al test,
    que es el defecto que se cerró el 2026-10-25 y volvió a aparecer ese mismo día.

    Medido en la corrida de T26 de ese día: el método informó `clasificados_tests_T26`, el
    `.entorno` quedó diciendo `clasificados_tests_T26_tests_T26` —el sufijo dos veces— y las
    DOS bases existían en el servidor con una fila cada una. `limpiar_base_del_arbol` vació la
    del `.entorno` y dejó la otra intacta.

    NO es el arreglo de la causa, y eso está dicho también en el script: tres pasadas seguidas
    de `preparar-entorno.sh` dan el mismo nombre, y el `entorno.sh` del proyecto no deriva
    nada —escribe el `MYSQL_DB` que recibe—. Es el chequeo que va a atrapar la causa con los
    dos nombres a la vista la próxima vez que pase. Un desacuerdo acá es barato de ver y caro
    de diagnosticar después."""

    def proyecto(self, lo_que_escribe_entorno):
        """Un proyecto con un `entorno.sh` de juguete: escribe el `.entorno` que le pidan, sin
        MySQL ni migraciones. La condición que se mide es el desacuerdo de nombres, y para eso
        no hace falta una base de verdad."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-nombrebase-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        proy = d / "proy"
        (proy / "scripts").mkdir(parents=True)
        # `ubicar_proyecto` exige `tareas/`: sin eso el script sale por stderr antes de
        # llegar al chequeo, y los tres tests fallaban sin decir por qué.
        (proy / "tareas").mkdir()
        (proy / "tareas" / "T01-cosa.md").write_text(
            "# T01 — Cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** src/cosa.py\n**Prohibido tocar:** Ninguno\n")
        (proy / ".gitignore").write_text(".entorno\n")
        (proy / ".entorno").write_text("export MYSQL_DB=basedeljuguete\n")
        ent = proy / "scripts" / "entorno.sh"
        ent.write_text(
            "#!/usr/bin/env bash\n"
            'DESTINO="${ENTORNO_DESTINO:-.}"\n'
            'mkdir -p "$DESTINO"\n'
            f'printf "export MYSQL_DB=%s\\n" "{lo_que_escribe_entorno}" > "$DESTINO/.entorno"\n')
        ent.chmod(0o755)
        (proy / "PLAN.md").write_text("# Plan\n")
        correr("git init -q .", d)
        correr("git -c user.email=t@t -c user.name=t add -A", d)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', d)
        return d

    def preparar(self, d, nombre_wt="tests-TNN"):
        wt = d.parent / nombre_wt
        self.addCleanup(shutil.rmtree, str(wt), True)
        correr(f"git worktree add -q --detach {wt} HEAD", d)
        self.addCleanup(lambda: correr(f"git worktree remove --force {wt}", d))
        return correr(f"PROYECTO=proy bash {SCRIPTS}/preparar-entorno.sh {wt}/proy", d)

    def test_la_base_del_worktree_no_depende_del_directorio_actual(self):
        """La relación metamórfica: el nombre de la base de un worktree es el mismo se
        invoque desde donde se invoque. Si depende del cwd, el `.entorno` cambia de valor
        entre dos invocaciones y todo lo que lo lee queda desincronizado.

        Era así. `base_de_datos_del_arbol` decidía «es un worktree» con `[ "$DESTINO" !=
        "$BASE" ]`, y `$BASE` lo resuelve `ubicar_proyecto` desde el DIRECTORIO ACTUAL:
        corriendo el script con el cwd dentro del worktree, los dos eran el mismo y la
        función devolvía vacío.

        Medido el 2026-10-25 en la segunda corrida de T26: `escribir-tests.sh` invoca
        `preparar-entorno.sh` DOS veces y la segunda corre después de que el agente trabajó
        en el worktree. El `.entorno` cambiaba entre las pasadas del validador, la limpieza
        vaciaba una base y el test usaba otra, y el `Duplicate entry` volvía con el veredicto
        cobrado al test. Ahora se le pregunta a GIT."""
        d = self.proyecto("")   # lo que escriba entorno.sh no importa: se mide el derivado
        wt = d.parent / "tests-TNN"
        self.addCleanup(shutil.rmtree, str(wt), True)
        correr(f"git worktree add -q --detach {wt} HEAD", d)
        self.addCleanup(lambda: correr(f"git worktree remove --force {wt}", d))

        def derivado(cwd):
            r = correr(f"PROYECTO=proy bash {SCRIPTS}/preparar-entorno.sh {wt}/proy", cwd)
            for l in r.stdout.split("\n"):
                if "base de datos de este worktree:" in l:
                    return l.split(":", 1)[1].strip()
            return ""

        desde_el_tronco = derivado(d)
        desde_el_worktree = derivado(wt)
        self.assertTrue(desde_el_tronco, "no derivó ninguna base desde el tronco")
        self.assertEqual(desde_el_tronco, desde_el_worktree,
                         "el nombre de la base cambia según desde dónde se corra el script")
        # Y el sufijo no se aplica dos veces: de ahí salía `..._tests_T26_tests_T26`.
        self.assertEqual(desde_el_tronco.count("tests_TNN"), 1,
                         f"el sufijo quedó más de una vez: {desde_el_tronco}")

    def test_un_worktree_sin_base_propia_no_sigue(self):
        """El agujero por el que esto pasó: con la derivación vacía, `entorno.sh` recibía
        `MYSQL_DB` vacío, usaba su valor por omisión, y el `.entorno` del worktree quedaba
        apuntando a LA BASE REAL del proyecto. Los tests del worktree habrían escrito ahí; la
        de clasificados quedó con 0 filas de pura suerte.

        El chequeo de consistencia no lo veía porque exigía un derivado no vacío: comparar el
        derivado con el escrito verifica consistencia, no corrección."""
        fuente = (SCRIPTS / "preparar-entorno.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        self.assertIn('[ -z "$DB_ARBOL" ]', codigo,
                      "un worktree sin base derivada tiene que parar, no seguir en silencio")
        i = codigo.index('[ -z "$DB_ARBOL" ]')
        bloque = codigo[i:i + 700]
        self.assertIn("exit 1", bloque, f"y parar de verdad:\n{bloque}")
        self.assertIn("git-common-dir", bloque,
                      "y saber si es un worktree por git, no por el cwd")

    def test_si_el_nombre_escrito_no_es_el_derivado_para(self):
        """El caso de T26: el `.entorno` termina con otro nombre y nadie se entera."""
        d = self.proyecto("basedeljuguete_tests_TNN_tests_TNN")
        r = self.preparar(d)
        self.assertNotEqual(r.returncode, 0,
                            f"dos nombres para una base no se puede dejar pasar:\n{r.stdout}")
        self.assertIn("no coincide", r.stdout, f"\n{r.stdout}")
        # Los DOS nombres a la vista: sin eso, diagnosticarlo cuesta lo que costó hoy.
        self.assertIn("basedeljuguete_tests_TNN", r.stdout, "falta el nombre derivado")
        self.assertIn("basedeljuguete_tests_TNN_tests_TNN", r.stdout, "falta el escrito")

    def test_si_coinciden_no_molesta(self):
        """El control: el chequeo no puede frenar el caso bueno, que es todas las corridas."""
        d = self.proyecto("basedeljuguete_tests_TNN")
        r = self.preparar(d)
        self.assertEqual(r.returncode, 0, f"frenó el caso bueno:\n{r.stdout}{r.stderr}")

    def test_un_entorno_vacio_tambien_para(self):
        """Un `.entorno` sin `MYSQL_DB` deja al test y a la limpieza sin fuente: el valor por
        omisión del proyecto no es la base del worktree, así que es el mismo choque."""
        d = self.proyecto("")
        r = self.preparar(d)
        self.assertNotEqual(r.returncode, 0, f"\n{r.stdout}")
        self.assertIn("(vacío)", r.stdout, f"y tiene que decir que quedó vacío:\n{r.stdout}")


class TestLaBaseDelWorktreeSeTiraAntesDeBorrarlo(unittest.TestCase):
    """`tirar_base_del_worktree` necesita leer el `.entorno` del worktree para saber CÓMO SE
    LLAMA la base. `escribir-tests.sh` la llamaba antes de `git worktree remove` —que es lo
    que pide el encabezado de la función— y DESPUÉS de un `rm -rf "$wt"`, que se lleva el
    `.entorno`. La función salía por su guarda sin tirar nada. La llamada cumplía la letra y
    violaba el motivo.

    Medido el 2026-10-25 en los tres intentos de T26: la base de un worktree NUNCA se tiraba
    entre intentos. El intento siguiente la encontraba con lo que dejó el anterior —el log lo
    delata, porque no vuelve a decir «aplicando migración»— y el validador chocaba con
    `Duplicate entry 'test@example.com'` en su segunda pasada.

    Y eso se informaba como un ⊘ cuya explicación decía «hay que limpiar la base entre
    pasadas o aislarla por corrida»: las dos cosas ya estaban hechas y medidas ese mismo día,
    y lo que faltaba era esto. Tres corridas de agente perseguí un defecto cuyo mensaje me
    mandaba a lo ya arreglado."""

    def test_la_llamada_va_antes_del_rm_en_TODOS_los_scripts(self):
        """Se lee del CÓDIGO y por POSICIÓN, que es lo que estaba mal: los comentarios de este
        arreglo nombran las dos cosas en el orden correcto y un grep los encontraría igual.

        Y en TODOS los scripts, no en el que tenía el bug. La primera versión miraba sólo
        `escribir-tests.sh`, y `correr-tarea.sh` tenía exactamente el mismo orden invertido —
        tres líneas debajo de un comentario que dice «arreglar un lado y no el otro es el
        patrón que este repo repite». Lo arreglé de un lado y no del otro, y lo cantó el aviso
        nuevo de la función en su primera corrida real, la de T15. Un test que mira un archivo
        no protege a sus hermanos."""
        malos = []
        for f in sorted(SCRIPTS.glob("*.sh")):
            lineas = f.read_text().splitlines()
            for i, l in enumerate(lineas):
                if "tirar_base_del_worktree" not in l or l.strip().startswith("#"):
                    continue
                if l.strip().startswith("tirar_base_del_worktree()"):
                    continue            # la definición, no una llamada
                # Las 12 líneas de código de arriba: si entre ellas está el `rm -rf` del
                # worktree, el `.entorno` ya no existe cuando se la llama.
                previas = [x for x in lineas[max(0, i - 12):i]
                           if x.strip() and not x.strip().startswith("#")]
                if any('rm -rf "$wt"' in x for x in previas):
                    malos.append(f"{f.name}:{i + 1}")
        self.assertEqual(malos, [],
                         "el `rm -rf` se lleva el .entorno, que es donde vive el nombre de la "
                         "base: tirarla después es no tirarla. Sitios: " + ", ".join(malos))

    def test_todo_sitio_que_destruye_un_worktree_tira_su_base(self):
        """Nueve sitios destruyen worktrees en este método y UNO no tiraba su base: el camino
        del VERDE, en `marcar_hecha_y_limpiar`. Una tarea que cierra bien y se integra dejaba
        su base viva en el servidor. Medido el 2026-10-25 después de integrar T15: su worktree
        ya no estaba y `clasificados_trabajo_T15` seguía ahí.

        El test de los cinco sitios declara ese sitio «no-aplica» para `conservar_intento`, y
        es correcto —no hay intento que conservar cuando el código de la tarea vive en un
        commit—. Pero la base no es el intento: la excepción de un chequeo se leyó como
        excepción del otro, y ésa es la forma en que este repo pierde cobertura.

        Los otros cuatro que faltaban eran `comparar-modelos.sh` y `congelar-banco.sh`, que
        también preparan entorno y por lo tanto también derivan base propia."""
        malos = []
        for f in sorted(SCRIPTS.glob("*.sh")):
            lineas = f.read_text().splitlines()
            for i, l in enumerate(lineas):
                if "worktree remove --force" not in l or l.strip().startswith("#"):
                    continue
                # Las 6 líneas de CÓDIGO de arriba, por el mismo motivo que el test de
                # `conservar_intento`: contar texto deja que un comentario largo empuje la
                # llamada afuera. Y la llamada sólo cuenta en código, no en la prosa que la
                # explica.
                j, visto = i, 0
                while j > 0 and visto < 6:
                    j -= 1
                    x = lineas[j].strip()
                    if x and not x.startswith("#"):
                        visto += 1
                tramo = lineas[j:i]
                if any("tirar_base_del_worktree" in x and not x.strip().startswith("#")
                       for x in tramo):
                    continue
                if any("tirar_base_del_worktree: no-aplica" in x
                       for x in tramo if x.strip().startswith("#")):
                    continue
                malos.append(f"{f.name}:{i + 1}")
        self.assertEqual(malos, [],
                         "estos destruyen un worktree y dejan su base viva en el servidor: "
                         + ", ".join(malos))

    def test_la_limpieza_preventiva_no_avisa_porque_no_hay_nada_que_avisar(self):
        """Este test y el siguiente reemplazan a `test_un_worktree_que_ya_no_esta_avisa_en_
        vez_de_callar`, que medía la conducta anterior —avisar SIEMPRE que el directorio
        faltara— con una ruta que git no conoce. Esa conducta cambió a propósito, y su
        intención —que el silencio se vuelva dato— queda cubierta por el par: uno mide que no
        hay ruido en el caso normal y el otro que el caso real sigue hablando. Dejar el viejo
        habría sido medir una conducta que ya no se quiere.

        El aviso distingue «nunca existió» de «lo borraron antes de tiempo», y lo dice GIT:
        si conoce el worktree, el directorio estuvo y su base quedó viva; si no lo conoce, es
        la limpieza preventiva de la primera corrida.

        Sin la distinción el aviso salía en TODA corrida de tarea —lo midieron T15 y T20— y
        eso es la forma más rápida de que alguien aprenda a ignorarlo. Un aviso que grita en
        el caso normal se apaga en una semana; es la misma lección que dio el chequeo de
        tautologías, que no se podía encender hasta que dejó de morder al test honesto."""
        d = self.proyecto_con_git()
        r = correr(f'PROYECTO=. bash -c \'. "{SCRIPTS}/_comun.sh"; ubicar_proyecto; '
                   f'tirar_base_del_worktree {d}/nunca-existio\'', d)
        self.assertNotIn("ya no está", r.stdout + r.stderr,
                         f"avisó por un worktree que nunca existió:\n{r.stdout}{r.stderr}")

    def test_pero_un_worktree_que_git_conoce_y_falta_sigue_avisando(self):
        """El control: el silencio no puede tragarse el caso real. Si git lo tiene registrado
        y el directorio no está, su base quedó viva y hay que decirlo."""
        d = self.proyecto_con_git()
        wt = d.parent / "huerfano"
        correr(f"git worktree add -q --detach {wt} HEAD", d)
        self.addCleanup(lambda: correr(f"git worktree prune", d))
        shutil.rmtree(wt, ignore_errors=True)        # alguien lo borró a mano
        r = correr(f'PROYECTO=. bash -c \'. "{SCRIPTS}/_comun.sh"; ubicar_proyecto; '
                   f'tirar_base_del_worktree {wt}\'', d)
        self.assertIn("ya no está", r.stdout + r.stderr,
                      f"se calló con la base viva:\n{r.stdout}{r.stderr}")

    def proyecto_con_git(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-avisobase-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        (d / "tareas" / "T01-cosa.md").write_text(
            "# T01 — Cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** src/cosa.py\n**Prohibido tocar:** Ninguno\n")
        (d / "scripts").mkdir()
        (d / "scripts" / "entorno.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (d / "scripts" / "entorno.sh").chmod(0o755)
        correr("git init -q .", d)
        correr("git -c user.email=t@t -c user.name=t add -A", d)
        correr('git -c user.email=t@t -c user.name=t commit -qm base', d)
        return d

    def test_el_encabezado_de_la_funcion_ya_declaraba_el_requisito(self):
        """La función documentaba exactamente este requisito y la llamada lo violaba. El test
        existe para que la prosa y el código no vuelvan a decir cosas distintas: si alguien
        saca la advertencia del encabezado, es que decidió otra cosa y hay que verlo."""
        comun = (SCRIPTS / "_comun.sh").read_text()
        # La DEFINICIÓN, no la primera mención: la primera está dentro del propio encabezado
        # —la línea de uso— así que el slice hacia atrás tomaba el comentario de otra función.
        i = comun.index("tirar_base_del_worktree() {")
        encabezado = comun[max(0, i - 1400):i]
        self.assertIn("ANTES", encabezado,
                      f"el encabezado tiene que seguir declarando el orden:\n{encabezado[-400:]}")
        self.assertIn(".entorno", encabezado, "y por qué: el nombre de la base vive ahí")


class TestAQuienSeLeCobraUnChoqueDeUniqueSeMide(unittest.TestCase):
    """El ⊘ del `Duplicate entry` afirmaba «Lo causa el MÉTODO» SIEMPRE, sin medirlo, y
    recomendaba «limpiar la base entre pasadas o aislarla por corrida».

    El 2026-10-25 las dos cosas ya estaban hechas y medidas ese mismo día, y la afirmación
    fue falsa tres corridas seguidas de T26: me mandó a revisar lo ya arreglado mientras el
    defecto real era otro —la base de un worktree no se tiraba al rehacerlo, porque la
    llamada que la tira estaba después de un `rm -rf` que se lleva el `.entorno` donde vive
    su nombre—. Un veredicto que nombra la causa equivocada cuesta más que uno que dice «no
    sé»: perseguí el camino que me señalaba.

    El dato que faltaba lo tenía el método: si su propia limpieza funcionó antes de esa
    pasada, la base arrancó VACÍA, y entonces las filas que chocan las insertó el test en esa
    misma corrida. Es del test. Si no pudo limpiar, el estado puede venir de cualquier parte
    y no se le cobra a la tarea."""

    def test_la_limpieza_informa_si_pudo_o_no(self):
        """Terminaba en `|| true` y devolvía 0 siempre, así que quien la llamaba no podía
        distinguir «la base quedó vacía» de «no pude»."""
        comun = (SCRIPTS / "_comun.sh").read_text()
        i = comun.index("limpiar_base_del_arbol() {")
        cuerpo = comun[i:comun.index("\n}", i)]
        # Sin los comentarios: el del arreglo CITA el `|| true` que saca, así que buscarlo en
        # el texto crudo lo encuentra en la prosa. Séptima vez hoy que un test mío matchea un
        # comentario, y esta vez en el test del arreglo que viene a medir en vez de afirmar.
        codigo = "\n".join(l for l in cuerpo.split("\n") if not l.strip().startswith("#"))
        self.assertNotIn("|| true", codigo,
                         f"con `|| true` el resultado no se puede medir:\n{codigo}")

    def test_el_validador_usa_ese_dato_para_decidir_a_quien_cobrarle(self):
        """Se lee del CÓDIGO: los comentarios de este arreglo citan el mensaje viejo entero."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        self.assertIn("BASE_VACIA_AL_EMPEZAR", codigo,
                      "el validador no recuerda si pudo limpiar: no puede medir la culpa")
        # Y el valor sale del RESULTADO de la limpieza, no de una suposición. Pedir que
        # estén en la misma línea no medía esto: `limpiar_base_del_arbol "$wt";
        # BASE_VACIA_AL_EMPEZAR=1` pasa, y es exactamente la suposición que el arreglo saca.
        # Lo que hace falta es que la asignación sea CONDICIONAL al resultado.
        linea = next(l for l in codigo.split("\n")
                     if "BASE_VACIA_AL_EMPEZAR=1" in l)
        self.assertRegex(linea, r"limpiar_base_del_arbol[^;]*&&\s*BASE_VACIA_AL_EMPEZAR=1",
                         f"el valor tiene que depender de que la limpieza funcione:\n{linea}")
        self.assertIn("|| BASE_VACIA_AL_EMPEZAR=0", linea,
                      f"y el caso de que no funcione tiene que quedar en 0:\n{linea}")

    def test_con_la_base_vacia_el_choque_es_del_test_y_se_le_cobra(self):
        """La diferencia que importa: con la base vacía esto es un rojo del test —`malo`— y
        no un ⊘ que lo absuelve. El ⊘ no reintenta ni acepta; el rojo sí le habla al agente."""
        # Se corta por el MARCADOR de la otra rama, no por el primer `else`. Desde que
        # `IntegrityError` se partió en tres —duplicado, clave foránea, NOT NULL— el primer
        # `else` es de las ramas internas y la extracción cortaba en el lugar equivocado. Una
        # extracción posicional se rompe cuando alguien anida algo adentro, y hoy lo anidé yo.
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        i = fuente.index('BASE_VACIA_AL_EMPEZAR:-0}" = "1"')
        bloque = fuente[i:i + 3600]
        rama_si = bloque[:bloque.index("⊘ $id: el test choca con datos que YA estaban")]
        self.assertIn("malo ", rama_si,
                      f"con la base vacía el choque es del test:\n{rama_si}")
        self.assertIn("insertó ÉL MISMO", rama_si, f"\n{rama_si}")
        self.assertNotIn("Lo causa el MÉTODO", rama_si,
                         "no puede seguir afirmando una causa que midió que es falsa")

    def test_sin_haber_podido_limpiar_no_se_le_cobra_a_la_tarea(self):
        """El otro lado, y es el que el ⊘ existe para proteger: si el método no pudo dejar la
        base vacía, el estado puede venir de cualquier corrida y cobrárselo al test sería el
        mismo error en la dirección contraria."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        i = fuente.index('BASE_VACIA_AL_EMPEZAR:-0}" = "1"')
        bloque = fuente[i:i + 3600]
        # Desde el marcador de esta rama, por el mismo motivo que arriba.
        rama_no = bloque[bloque.index("⊘ $id: el test choca con datos que YA estaban"):]
        self.assertIn("⊘", rama_no, f"\n{rama_no[:400]}")
        self.assertIn("no se le cobra a la tarea", rama_no)
        # Y el consejo que da ahora es el del defecto real, no el de lo ya arreglado.
        self.assertIn("tirarla ANTES de borrar", rama_no,
                      "el consejo tiene que apuntar a la causa medida")


class TestElGateNoPreguntabaSiElTestDistingueESTAImplementacion(CasoBase):
    """El paso 4 del gate revierte la implementación ENTERA y exige que la suite falle. Eso
    distingue «con código» de «sin código», que no es lo mismo que «este código» de «este
    código con un bug» — y el paso se llama «¿los tests distinguen?», así que prometía más de
    lo que medía.

    `escribir-tests.sh` SÍ muta, pero contra la implementación de REFERENCIA que escribió el
    agente de tests. La implementación final la escribe otro agente, en otra etapa. Un
    mutante que muere contra la referencia puede sobrevivir contra la final, y entre las dos
    no había nadie.

    Medido el 2026-10-25 en T20 de clasificados, con gate VERDE al primer intento: dos
    mutantes sobreviven y uno es un bug latente. La línea

        row["de_usuario_id"] if row["de_usuario_id"] != user_id else row["a_usuario_id"]

    es «el otro usuario de la conversación»; invirtiendo el `!=` devuelve el PROPIO usuario y
    el test no lo nota. Ese verde no se ganó, y sin este paso se integraba al tronco.

    El paso vive en el gate del PROYECTO, que tiene tres copias divergentes —plantilla y los
    dos ejemplos—. El código del paso usa `aux_del_metodo mutar.py`, que es el mecanismo que
    el repo ya usa para los auxiliares que provee el método, así que lo que se duplica es la
    invocación y no la lógica."""

    def preparar(self, impl, test):
        """El test COMMITEADO y la implementación SIN commitear, que es el estado real en que
        el gate juzga una tarea: el test lo escribió la etapa anterior y vive en HEAD, y la
        tarea sólo toca su implementación.

        Mi primera versión escribía las dos cosas juntas, y el gate reprobaba —con razón— por
        «tocó archivos intocables» y «fuera del alcance». Un fixture que no reproduce el
        estado real mide el chequeo de al lado."""
        (self.p.dir / "tests" / "test_cosa.py").write_text(test)
        self.p.git("add -A"); self.p.git('commit -qm "tests de la etapa anterior"')
        self.p.implementar(impl)
        return self.p.gate("T01")

    IMPL_CON_TOPE = ("def f():\n    return 42\n\n\n"
                     "def tope(x):\n"
                     "    if x >= 999:\n        return 999\n"
                     "    return x\n")

    def test_un_mutante_que_sobrevive_pone_el_gate_en_rojo(self):
        """El caso de T20: el test cubre la línea y no verifica su comportamiento."""
        r = self.preparar(
            self.IMPL_CON_TOPE,
            "import unittest\nfrom src.cosa import f, tope\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(), 42)\n"
            "    def test_tope(self):\n        tope(5)\n")
        self.assertIn("4b.", r.stdout, f"el paso no corrió:\n{r.stdout}")
        self.assertIn("sobreviven mutantes", r.stdout, f"\n{r.stdout}")
        self.assertIn("→", r.stdout, "y tiene que decir QUÉ mutante sobrevivió")
        self.assertNotEqual(r.returncode, 0, "un mutante vivo es un verde que no se ganó")

    def test_un_test_que_verifica_de_verdad_lo_deja_en_verde(self):
        """El control, y decide si el paso se puede encender: no puede reprobar al test que
        sí distingue, porque entonces ninguna tarea cerraría."""
        r = self.preparar(
            self.IMPL_CON_TOPE,
            "import unittest\nfrom src.cosa import f, tope\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(), 42)\n"
            "    def test_tope_corta(self):\n        self.assertEqual(tope(1000), 999)\n"
            "    def test_tope_pasa(self):\n        self.assertEqual(tope(5), 5)\n")
        self.assertIn("4b.", r.stdout, f"el paso no corrió:\n{r.stdout}")
        self.assertIn("los mutantes de esta implementación mueren", r.stdout, f"\n{r.stdout}")

    def test_una_linea_que_el_test_no_ejecuta_se_informa_como_tal(self):
        """El otro veredicto, el que se separó esta mañana: si la línea NO se ejecuta, el
        problema no son las aserciones. El mensaje tiene que mandar al lado correcto."""
        r = self.preparar(
            self.IMPL_CON_TOPE,
            "import unittest\nfrom unittest.mock import patch\nimport src.cosa\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    @patch('src.cosa.tope')\n"
            "    def test_tope(self, m):\n"
            "        m.return_value = 7\n"
            "        self.assertEqual(src.cosa.tope(5), 7)\n"
            "    def test_f(self):\n        self.assertEqual(src.cosa.f(), 42)\n")
        self.assertIn("4b.", r.stdout, f"el paso no corrió:\n{r.stdout}")
        self.assertIn("NO EJECUTA", r.stdout, f"\n{r.stdout}")
        self.assertNotEqual(r.returncode, 0)

    def test_las_tres_copias_del_gate_tienen_el_paso(self):
        """El gate del proyecto tiene tres copias divergentes, y el comentario del paso 4 ya
        denuncia lo que pasa: «el arreglo existía en un ejemplo de tres; la plantilla, que es
        la que copia todo proyecto nuevo, seguía con el patrón». Un paso que falta en la
        plantilla no existe para ningún proyecto futuro."""
        faltan = []
        for ruta in (PLANTILLAS / "gate.sh",
                     RAIZ / "ejemplo-clasificados" / "scripts" / "gate.sh",
                     RAIZ / "ejemplo-pacman" / "scripts" / "gate.sh"):
            if not ruta.exists():
                continue
            texto = ruta.read_text()
            if "4b." not in texto or "aux_del_metodo mutar.py" not in texto:
                faltan.append(str(ruta.relative_to(RAIZ)))
        self.assertEqual(faltan, [],
                         "estas copias del gate no preguntan si el test distingue ESTA "
                         "implementación: " + ", ".join(faltan))


class TestElPorQueFallaNoPuedeCitarAUnVecino(CasoBase):
    """El gate dice QUÉ tests de la tarea fallan y POR QUÉ. El «por qué» salía de grepear la
    salida COMPLETA de la suite y tomar el primer match — y el tronco está rojo por diseño
    mientras una etapa está en vuelo, así que arriba siempre hay errores ajenos.

    Medido el 2026-10-25 en T20 de clasificados: su test fallaba por `KeyError:
    'otro_usuario_id'` y el gate informó «ModuleNotFoundError: No module named
    'backend.app.servicios.messages'», que es de T21, otra tarea pendiente. El reintento
    habría ido a buscar un módulo que no le toca escribir.

    Es el defecto del día entero —el veredicto nombra al sujeto equivocado— y acá lo hace
    citando a un vecino. El motivo sale ahora de una corrida que SÓLO incluye los tests de la
    tarea, que es la única forma de que el error sea suyo."""

    def test_el_motivo_es_del_test_de_la_tarea_y_no_del_vecino(self):
        # Un test AJENO que revienta al importar. Se llama `test_ajeno` y no `test_vecino`
        # a propósito: unittest lista los errores en orden alfabético de módulo, así que con
        # «vecino» salía DESPUÉS de `test_cosa` y el defecto no se manifestaba — el test daba
        # verde con el bug puesto. En pytest el orden lo daba la colección, que informa sus
        # errores antes de cualquier aserción. El fixture tiene que poner al ajeno PRIMERO,
        # que es la condición que hace al defecto visible.
        (self.p.dir / "tests" / "test_ajeno.py").write_text(
            "import unittest\nfrom src.modulo_de_otra_tarea import algo\n\n"
            "class TestAjeno(unittest.TestCase):\n"
            "    def test_algo(self):\n        self.assertTrue(algo())\n")
        # Y el test de LA TAREA, que falla por su propia causa, bien distinta.
        (self.p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom src.cosa import f\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n"
            "        self.assertEqual(f()['clave_que_falta'], 1)\n")
        self.p.implementar("def f():\n    return {'otra_clave': 1}\n")
        self.p.git("add -A"); self.p.git('commit -qm "tests y una implementación que falla"')
        # La línea base, con la falla del VECINO ya dentro: así el gate la descuenta y la
        # falla de la tarea queda como «mía», que es la rama donde se informa el motivo. Sin
        # esto el gate dice «la suite está en rojo» y nunca llega a dar un por qué.
        r0 = correr("bash scripts/correr-suite.sh --fallas", self.p.dir)
        (self.p.dir / ".tests-base").write_text(
            "\n".join(l for l in r0.stdout.splitlines() if "ajeno" in l) + "\n")
        self.p.implementar("def f():\n    return {'otra_clave': 2}\n")
        r = self.p.gate("T01")
        self.assertIn("por qué falla", r.stdout, f"no dio motivo:\n{r.stdout}")
        motivo = next(l for l in r.stdout.splitlines() if "por qué falla" in l)
        self.assertIn("clave_que_falta", motivo,
                      f"el motivo tiene que ser el del test de la tarea:\n{motivo}")
        self.assertNotIn("modulo_de_otra_tarea", motivo,
                         f"citó el error de un vecino, que es el defecto:\n{motivo}")

    def test_el_motivo_sale_de_una_corrida_acotada_a_la_tarea(self):
        """Se lee del CÓDIGO: los comentarios de este arreglo citan el error ajeno entero."""
        fuente = (PLANTILLAS / "gate.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        i = codigo.index("PRIMER_ERROR=")
        bloque = codigo[max(0, i - 700):i]
        self.assertIn("SALIDA_MIA", bloque,
                      f"el motivo sigue saliendo de la salida completa:\n{bloque[-400:]}")
        self.assertIn("correr-suite.sh \"$RUTA_PE::$CLASE_PE\"", bloque,
                      "y la corrida tiene que estar acotada al test de la tarea")


class TestIntegrityErrorEsUnaFamiliaYNoUnError(unittest.TestCase):
    """Con la base vacía, un duplicado y una clave foránea fallida piden arreglos casi
    OPUESTOS, y el mensaje afirmaba «inserta la misma fila dos veces» para los dos.

      · 1062 «Duplicate entry» → el test inserta la misma fila dos veces, o no limpia entre
        sus propios casos. El arreglo está en el test;
      · 1452 «foreign key constraint fails» → el test referencia filas que NO EXISTEN. La
        base arranca vacía cada pasada, así que los datos semilla que da por sentados no
        están. El arreglo es que los cree él, en su setUp;
      · 1048 «cannot be null» → una columna NOT NULL sin valor. Puede ser del test o del
        enunciado, que pide una fila que el esquema no acepta.

    Medido el 2026-10-25 en T16, la primera tarea limpia que pasó por el validador con los
    chequeos de ese día: su test inserta favoritos para un usuario inexistente y recibió
    «inserta la misma fila dos veces», que no describe nada de lo que pasó. Un veredicto que
    nombra la causa equivocada cuesta más que uno que dice «no sé», y es la tercera vez en el
    día — las otras dos fueron el ⊘ que culpaba al método y el «por qué falla» que citaba a un
    vecino.

    El patrón que dispara la rama es `IntegrityError` genérico, y eso está bien: la familia
    entera merece un veredicto medido. Lo que no puede es tener UN mensaje."""

    def ramas(self):
        """Sin comentarios. Los de este arreglo CITAN la frase vieja —«inserta la misma fila
        dos veces»— para explicar que ya no se usa para la FK, así que buscarla en el texto
        crudo la encuentra en la prosa. Octava vez en el día que un test mío matchea un
        comentario; el patrón es mío y el filtro va en el helper, no en cada aserción."""
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        i = codigo.index('BASE_VACIA_AL_EMPEZAR:-0}" = "1"')
        return codigo[i:i + 2200]

    def test_la_clave_foranea_tiene_su_propio_veredicto(self):
        bloque = self.ramas()
        self.assertIn("1452", bloque, f"no distingue la FK:\n{bloque[:400]}")
        i = bloque.index("1452")
        rama = bloque[i:bloque.index("elif", i)]
        self.assertIn("no existen", rama, f"\n{rama}")
        self.assertIn("setUp", rama,
                      "y tiene que decir qué hacer: crear lo que referencia")
        self.assertNotIn("la misma fila dos veces", rama,
                         "una FK fallida no es un duplicado")

    def test_el_not_null_tambien(self):
        bloque = self.ramas()
        self.assertIn("1048", bloque, f"no distingue el NOT NULL:\n{bloque[:400]}")
        i = bloque.index("1048")
        rama = bloque[i:bloque.index("else", i)]
        self.assertIn("NOT NULL", rama, f"\n{rama}")
        # Y no se lo cobra sólo al test: puede ser el enunciado pidiendo una fila imposible.
        self.assertIn("enunciado", rama,
                      "puede ser del enunciado, y el veredicto no puede cerrarlo de antemano")

    def test_el_duplicado_conserva_el_suyo(self):
        """El control: el veredicto que ya estaba medido no se pierde al agregar los otros."""
        bloque = self.ramas()
        i = bloque.rindex("la misma fila dos veces")
        rama = bloque[max(0, i - 600):i + 200]
        self.assertIn("insertó ÉL MISMO", rama, f"\n{rama}")
        self.assertIn("no hay estado de otra corrida", rama)

    def test_las_tres_ramas_le_cobran_al_test_y_no_al_metodo(self):
        """Las tres son `malo`, no ⊘: con la base vacía el método hizo su parte, y el ⊘
        existe para cuando NO pudo. Si una rama fuera ⊘, el agente no recibiría el rojo."""
        bloque = self.ramas()
        hasta_else = bloque[:bloque.rindex("else")]
        self.assertEqual(hasta_else.count("malo "), 3,
                         f"las tres ramas tienen que cobrarle al test:\n{hasta_else}")
        self.assertNotIn("⊘", hasta_else,
                         "con la base vacía no corresponde un ⊘: el método hizo su parte")


class TestUnTestNoPuedeObligarUnContratoQueElEnunciadoNoDeclara(unittest.TestCase):
    """El chequeo de columnas pregunta si el ENUNCIADO pide algo que el esquema no tiene. Éste
    es el mismo cruce en la otra dirección, y hace falta porque el test se acepta PRIMERO y
    después juzga a toda implementación: lo que invente queda obligado para siempre.

    Medido el 2026-10-25 sobre los tests YA ACEPTADOS de clasificados. Dos lo hacen:

      · T20 obliga seis claves que su enunciado no nombra y que no son columna de ninguna
        tabla —`other_user_id`, `ultimo_mensaje`, `last_message`, `last_message_date`,
        `fecha_ultimo_mensaje`, `created_at`— con un contrato que dice sólo `-> dict` y
        «devuelve el registro creado». Dos corridas de implementación fallaron adivinando el
        mapeo: una devolvió `other_user_id` donde el test pedía `otro_usuario_id`;
      · T21 obliga `message_id` con un contrato igual de mudo.

    Es el mismo molde del test envenenado de T28 que saqué esa mañana, que clavaba la columna
    `categoria`: un test aceptado que obliga algo que el plan no dice. El gate no lo veía
    porque sus cinco pasos preguntan si el test DISTINGUE, no si lo que obliga está
    declarado."""

    SCRIPT = SCRIPTS / "_contrato.py"

    def proyecto(self, contrato, test, migracion="id INT, email VARCHAR(80)"):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-contrato-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        for sub in ("tareas", "migraciones", "tests"):
            (d / sub).mkdir()
        (d / "migraciones" / "001.sql").write_text(
            f"CREATE TABLE usuarios (\n    {migracion}\n);\n")
        (d / "tareas" / "T01-cosa.md").write_text(
            "# T01 — Cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
            "**Archivos que podés tocar:** src/cosa.py\n**Prohibido tocar:** Ninguno\n\n"
            f"## Contrato\n\n```python\n{contrato}\n```\n")
        (d / "tests" / "test_cosa.py").write_text(test)
        return d

    def correr_chequeo(self, d):
        return correr(f"python3 {self.SCRIPT} tests/test_cosa.py tareas/T01-cosa.md .", d)

    def test_una_clave_inventada_se_marca(self):
        """El caso de T21: el contrato dice `-> dict` y el test exige una clave."""
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve el registro.\"\"\"",
                          "def test_f():\n    assert f() == {'message_id': 1}\n")
        r = self.correr_chequeo(d)
        self.assertEqual(r.returncode, 1, f"{r.stdout}{r.stderr}")
        self.assertIn("message_id", r.stdout, f"\n{r.stdout}")
        self.assertIn("no declara el enunciado", r.stdout)

    def test_una_clave_que_el_enunciado_declara_no_se_marca(self):
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve {'message_id': int}.\"\"\"",
                          "def test_f():\n    assert f() == {'message_id': 1}\n")
        self.assertEqual(self.correr_chequeo(d).returncode, 0,
                         "si el enunciado la declara, el contrato existe")

    def test_una_columna_del_esquema_no_se_marca(self):
        """La tercera fuente, y es la que evita el ruido: una clave que el enunciado no nombra
        puede ser perfectamente legítima si es una COLUMNA —el test lee la fila que la base
        devuelve—. Sin esto el chequeo marcaba `anuncio_id` en T20, que sí es columna."""
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve la fila.\"\"\"",
                          "def test_f():\n    assert f() == {'email': 'a@b'}\n")
        self.assertEqual(self.correr_chequeo(d).returncode, 0,
                         "una columna del esquema no la inventó el test")

    def test_un_proyecto_SIN_base_de_datos_igual_se_audita(self):
        """CERO columnas no es «no pude leer»: es un proyecto sin base, y ahí ninguna clave
        puede ser columna, así que todas las no declaradas las inventó el test.

        `cols or None` confundía los dos casos y con eso el chequeo quedaba INÚTIL en
        cualquier proyecto sin SQL —que son la mayoría—. Medido el 2026-10-25 corriéndolo en
        un proyecto nuevo sin migraciones: decía «no pude leer las columnas» y no afirmaba
        nada sobre un test con tres defectos. El rc de `coherencia.py --columnas` ya
        distinguía los dos casos: devuelve 0 con salida vacía cuando no hay migraciones."""
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve algo.\"\"\"",
                          "def test_f():\n    assert f() == {'inventada': 1}\n")
        shutil.rmtree(d / "migraciones")      # un proyecto que no usa base de datos
        r = self.correr_chequeo(d)
        self.assertEqual(r.returncode, 1,
                         f"sin base de datos el chequeo igual tiene que poder juzgar:"
                         f"\n{r.stdout}{r.stderr}")
        self.assertIn("inventada", r.stdout, f"\n{r.stdout}")

    def test_sin_poder_leer_el_esquema_no_afirma_nada(self):
        """Un chequeo que cruza tres fuentes y perdió una no puede dar un veredicto. Mi
        primera versión devolvía un set vacío envuelto en `except Exception` —fallando
        ABIERTO— y con cero columnas leídas marcaba las que sí lo eran.

        «No poder leer» es que el LECTOR falle, no que el proyecto no tenga base: eso último
        es cero columnas y se audita igual (ver el test de arriba). Y no se provoca con un
        esquema inválido —`coherencia.py --columnas` es tolerante: devuelve cero columnas sin
        reventar, lo medí— sino con una INSTALACIÓN INCOMPLETA, que es el caso real: el
        auxiliar corre sin su lector al lado."""
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve la fila.\"\"\"",
                          "def test_f():\n    assert f() == {'email': 'a@b'}\n")
        # El auxiliar, solo, sin `coherencia.py` al lado: una instalación a medias.
        suelto = d / "solo"
        suelto.mkdir()
        shutil.copy(self.SCRIPT, suelto / "_contrato.py")
        r = correr(f"python3 {suelto / '_contrato.py'} tests/test_cosa.py tareas/T01-cosa.md .",
                   d)
        self.assertEqual(r.returncode, 2,
                         f"sin esquema tiene que ser ⊘, no un veredicto:\n{r.stdout}")
        self.assertIn("no afirma nada", r.stdout, f"\n{r.stdout}")

    def test_un_in_sobre_una_coleccion_no_es_un_contrato(self):
        """`assert "x" in algo` no dice que `algo` sea un dict: puede ser un set o una lista,
        y entonces lo de la izquierda no es una clave. Lo midió T06b, cuyo test siembra
        módulos de prueba y afirma `"prueba_router" in ...routers_montados`. Marcarlo era
        morder al test honesto."""
        d = self.proyecto("def f() -> set:\n    \"\"\"Devuelve los montados.\"\"\"",
                          "def test_f():\n    assert 'prueba_router' in f()\n")
        self.assertEqual(self.correr_chequeo(d).returncode, 0,
                         "un `in` sobre una colección no declara un contrato")

    def test_el_validador_lo_corre_y_falla_cerrado(self):
        fuente = (SCRIPTS / "escribir-tests.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        invoca = [l for l in codigo.split("\n") if "_contrato.py" in l and "python3" in l]
        self.assertTrue(invoca, "el validador no invoca el chequeo")
        self.assertIn('"$archivo"', invoca[0],
                      f"tiene que pasarle el archivo de tarea que el script ya resolvió, no "
                      f"una variable inventada:\n{invoca[0]}")
        self.assertIn('[ ! -f "$AQUI/_contrato.py" ]', codigo,
                      "si falta el auxiliar es rojo, no un salteo silencioso")

    def test_los_tests_ya_aceptados_del_repo_dan_dos_hallazgos_y_cero_ruido(self):
        """El control que decide si esto se puede encender: sobre los tests aceptados de los
        dos proyectos, dos hallazgos —T20 y T21, los dos verificados a mano— y ningún falso
        positivo. Pacman, con otro corredor y 19 tareas, no marca nada."""
        marcados = []
        for proyecto in ("ejemplo-clasificados", "ejemplo-pacman"):
            base = RAIZ / proyecto
            for tf in sorted((base / "tareas").glob("T*.md")):
                tid = re.match(r"(T\d+[a-z]?)-", tf.name).group(1)
                del_plan = re.search(
                    rf"^\|\s*{tid}\s*\|\s*`?([^|`]*?\.py)`?\s*\|", (base / "PLAN.md").read_text(),
                    re.M) if (base / "PLAN.md").exists() else None
                ruta = del_plan.group(1).strip() if del_plan else None
                if not ruta:
                    m = re.search(r"Archivo: `([^`]*\.py)`", tf.read_text())
                    ruta = m.group(1) if m else None
                if not ruta or not (base / ruta).exists():
                    continue
                r = correr(f"python3 {self.SCRIPT} {ruta} tareas/{tf.name} .", base)
                if r.returncode == 1:
                    marcados.append(f"{proyecto}:{tid}")
        self.assertEqual(sorted(marcados),
                         ["ejemplo-clasificados:T20", "ejemplo-clasificados:T21"],
                         f"los marcados cambiaron: {marcados}")

    def test_un_archivo_que_falta_no_es_un_pase(self):
        """Con la ruta de la tarea mal armada —lo más fácil de romper al enganchar esto en
        otro script— el chequeo devolvía 0, o sea: «el contrato está declarado» sin haberlo
        mirado. Es el defecto que este método viene cerrando todo el día, y éste fue el
        último chequeo que escribí."""
        d = self.proyecto("def f() -> dict:\n    \"\"\"Devuelve algo.\"\"\"",
                          "def test_f():\n    assert f() == {'inventada': 1}\n")
        r = correr(f"python3 {self.SCRIPT} tests/test_cosa.py tareas/NO-EXISTE.md .", d)
        self.assertEqual(r.returncode, 2,
                         f"un archivo que falta es ⊘, no un pase:\n{r.stdout}{r.stderr}")
        self.assertIn("no afirma nada", r.stdout, f"\n{r.stdout}")

    def test_el_auditor_de_cerradas_tambien_lo_corre(self):
        """El chequeo es nuevo y encontró dos tests YA ACEPTADOS, así que es exactamente el
        material que `auditar-cerradas.sh` existe para revisar. Hoy no dispara ahí porque T20
        y T21 están pendientes —y eso es buena noticia: las cerradas están limpias— pero el
        enganche tiene que estar para cuando una se cierre."""
        fuente = (SCRIPTS / "auditar-cerradas.sh").read_text()
        codigo = "\n".join(l for l in fuente.split("\n") if not l.strip().startswith("#"))
        self.assertIn("_contrato.py", codigo, "el auditor no cruza el contrato")
        i = codigo.index("_contrato.py")
        bloque = codigo[i:i + 300]
        self.assertIn("rojo_de_esta", bloque,
                      f"lo corre y no hace nada con el resultado:\n{bloque}")



class TestUnaVariableQueNadieLeeDaUnMutanteInmatable(CasoBase):
    """Borrar una asignación a un nombre que NADIE LEE no cambia el comportamiento por
    definición: el mutante es inmatable y ningún test puede matarlo. El método lo informaba
    como «la suite no nota estos cambios», que culpa al test de algo imposible.

    Es la misma clase que las anotaciones de tipo, que ya estaban excluidas por producir
    «un mutante INMATABLE: ningún test observa el tipo declarado».

    Medido el 2026-10-25 en T20 de clasificados: de sus dos mutantes sobrevivientes uno era
    `result = []` —una lista que el código reemplaza por `conversations` y nunca lee— y el
    otro un bug latente de verdad, la condición que elige «el otro usuario de la
    conversación». Mezclar los dos en la misma lista hace que el real pese la mitad, y el
    real era el que no había que dejar pasar."""

    def mutar(self, base="HEAD~1"):
        return correr(f"BASE={base} CODIGO=src "
                      f"SUITE='python3 -m unittest discover -s tests -t . -q' "
                      f"python3 {SCRIPTS}/mutar.py", self.p.dir)

    def test_la_variable_muerta_no_se_muta(self):
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("def f():\n    sobrante = []\n    return 42\n")
        self.p.git("add -A"); self.p.git("commit -qm muerta")
        r = self.mutar()
        self.assertNotIn("sobrante", r.stdout,
                         f"es inmatable: ningún test puede notar que se fue\n{r.stdout}")
        # Y como no quedó nada que mutar, es un ⊘ honesto y no un verde.
        self.assertEqual(r.returncode, 2, f"{r.stdout}")

    def test_la_variable_que_si_se_lee_sigue_mutandose(self):
        """El control: excluir de más apaga el chequeo donde sirve."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        # El valor por omisión tiene que ser 42, que es lo que el test del fixture espera:
        # con `x=0` la suite arranca en rojo y `mutar.py` se niega a mutar —con razón— así
        # que el caso no medía la exclusión sino esa negativa.
        self.p.implementar("def f(x=42):\n    tope = 100\n"
                           "    if x > tope:\n        return tope\n    return x\n")
        self.p.git("add -A"); self.p.git("commit -qm viva")
        r = self.mutar()
        self.assertIn("mutante(s) probados", r.stdout, f"\n{r.stdout}")
        self.assertNotEqual(r.returncode, 2,
                            f"una variable que se lee tiene algo que mutar:\n{r.stdout}")

    def test_la_leida_desde_una_closure_tampoco_se_declara_muerta(self):
        """Se mira si el nombre se lee en TODO el archivo, no en la función: una closure o
        una global lo leen desde otro ámbito, y declararla muerta sería apagar el chequeo
        sobre una variable viva."""
        self.p.implementar(); self.p.git("add -A"); self.p.git("commit -qm impl")
        self.p.implementar("def f(x=42):\n    guardado = x\n"
                           "    def interna():\n        return guardado\n"
                           "    return interna()\n")
        (self.p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom src.cosa import f\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(), 42)\n")
        self.p.git("add -A"); self.p.git("commit -qm closure")
        r = self.mutar()
        self.assertIn("1 mutante(s) probados", r.stdout,
                      f"la variable de la closure se lee: hay que mutarla\n{r.stdout}")
        self.assertEqual(r.returncode, 0, f"y el test la mata:\n{r.stdout}")


class TestUnMutanteQueCuelgaElProgramaColgabaElGate(CasoBase):
    """`mutar.py` corría la suite SIN tope de tiempo, así que un mutante que deja el programa
    girando cuelga el gate entero y la corrida no termina nunca.

    Medido el 2026-10-25 auditando `ejemplo-pacman`: un mutante en `__main__.py` —que es el
    game loop— dejó la suite corriendo 45 MINUTOS contra una suite que tarda 0,24 s, con un
    archivo mutado en el árbol todo ese tiempo. En cualquier proyecto con un loop, un servidor
    o un `input()`, eso está garantizado.

    El timeout cuenta como MUERTE del mutante, no como supervivencia: el mutante cambió el
    comportamiento de una forma perfectamente observable —el programa dejó de terminar— y
    contarlo como «sobrevivió» le cobraría al test una diferencia que sí distingue. Es lo
    mismo que hace el gate de TestForge/Meta ACH, que trata fail, error y timeout como muerte.

    Se mata el ÁRBOL y no el proceso: `SUITE` es un shell que lanza python, así que matar al
    shell deja al nieto girando. Es el defecto que este repo ya cerró en su vigilante —«miraba
    el grupo de procesos, no el árbol»— y que acá volvía por otra puerta."""

    def con_loop(self):
        """Un proyecto donde un mutante puede colgar la suite: el incremento de un `while`."""
        self.p.implementar("def f(x):\n    return x\n")
        self.p.git("add -A"); self.p.git("commit -qm base")
        self.p.implementar("def f(x):\n    return x\n\n\n"
                           "def loop(n):\n    i = 0\n    while i < n:\n"
                           "        i += 1\n    return i\n")
        (self.p.dir / "tests" / "test_cosa.py").write_text(
            "import unittest\nfrom src.cosa import f, loop\n\n"
            "class TestCosa(unittest.TestCase):\n"
            "    def test_f(self):\n        self.assertEqual(f(42), 42)\n"
            "    def test_loop(self):\n        self.assertEqual(loop(3), 3)\n")
        self.p.git("add -A"); self.p.git("commit -qm loop")

    def setUp(self):
        super().setUp()
        # Lo que este caso deja girando se limpia solo. El control de reintroducción del bug
        # —matar el proceso en vez del árbol— deja nietos vivos POR DEFINICIÓN: el bug ES
        # dejarlos. El test lo detecta y falla, que es lo correcto, pero la basura quedaba:
        # el 2026-10-25 tres suites colgadas consumieron CPU veinte minutos y el monitoreo las
        # informó como «medición activa», que me hizo dudar dos bloques seguidos de si había
        # algo trabado. Un test que ensucia el entorno le cobra su defecto al siguiente.
        # Se matan sólo los HUÉRFANOS —los que quedaron con padre 1— que es exactamente lo
        # que el bug deja: un `pkill` por nombre se llevaría también la suite de un test en
        # curso. Y el cwd es RAIZ y no el proyecto: los cleanup son LIFO, así que éste corre
        # ÚLTIMO, cuando el directorio de juguete ya se borró, y pasarle ese cwd hacía
        # explotar los cinco tests en el propio cleanup.
        self.addCleanup(lambda: correr(
            "for p in $(pgrep -f 'correr-suite.sh' 2>/dev/null); do "
            "  [ \"$(ps -o ppid= -p $p 2>/dev/null | tr -d ' ')\" = 1 ] && kill -9 $p; "
            "done; true", RAIZ))

    def mutar(self, tope=None):
        # `correr-suite.sh` y NO el comando pelado, porque es la diferencia que hace al
        # defecto visible: con un comando simple bash hace `exec` y SE CONVIERTE en python,
        # así que no hay nieto y matar el proceso alcanza. Con un script —que es lo que usa
        # cualquier proyecto real— bash no puede exec-ear y queda el nieto girando. Medido:
        # con el script, matar el proceso deja 1 vivo y matar el grupo deja 0; con el comando
        # pelado, los dos dejan 0, y el test daba verde con el bug puesto.
        env = f"TOPE_MUTANTE={tope} " if tope else ""
        return correr(f"{env}BASE=HEAD~1 CODIGO=src "
                      f"SUITE='bash scripts/correr-suite.sh' "
                      f"python3 {SCRIPTS}/mutar.py", self.p.dir)

    def test_el_mutante_que_cuelga_muere_por_tope_y_no_cuelga_la_corrida(self):
        """La medición es que la corrida VUELVE. Sin tope no vuelve nunca, así que si este
        test termina, el tope cortó: no hace falta cronometrarlo.

        Mi primera versión agregaba `assertLess(tardo, 60)`, y eso lo volvió INTERMITENTE:
        falló cuando compartió máquina con la suite completa de 558 tests y pasó cuando corrió
        sola. Un umbral de tiempo absoluto mide la carga de la máquina, no el arreglo — y un
        verde intermitente es peor que un rojo, porque no se sabe qué guardia tenés."""
        self.con_loop()
        r = self.mutar(tope=5)
        self.assertEqual(r.returncode, 0,
                         f"el mutante que cuelga tiene que MORIR:\n{r.stdout}{r.stderr}")
        self.assertIn("murieron", r.stdout, f"\n{r.stdout}")
        # Y que el tope se haya aplicado de verdad, que es lo que hizo que vuelva.
        self.assertIn("tope por mutante: 5s", r.stdout,
                      f"no usó el tope que le pedí:\n{r.stdout}")

    def test_no_deja_procesos_colgados(self):
        """Matar el shell y no el árbol deja al nieto girando, y el que lo paga es la próxima
        corrida: el repo ya perdió 45 minutos así."""
        self.con_loop()
        self.mutar(tope=5)
        vivos = correr("pgrep -f 'correr-suite' | wc -l", self.p.dir)
        self.assertEqual(vivos.stdout.strip(), "0",
                         f"quedaron procesos de la suite girando: {vivos.stdout}")

    def test_un_tope_menor_que_la_suite_no_es_un_pase(self):
        """El agujero que abre el arreglo, y había que cerrarlo antes de confiar: con un tope
        por debajo de lo que tarda la suite SIN mutar, todos los mutantes dan timeout, el
        timeout cuenta como muerte, y el veredicto sale «todos murieron: la suite distingue».
        Un falso verde producido por el reloj. Medido con TOPE_MUTANTE=0.01 sobre una suite de
        0,14 s: tres mutantes, tres muertes, verde."""
        self.con_loop()
        r = self.mutar(tope="0.01")
        self.assertEqual(r.returncode, 2,
                         f"un tope inválido es ⊘, no un pase:\n{r.stdout}{r.stderr}")
        self.assertIn("el verde lo produciría el reloj", r.stdout, f"\n{r.stdout}")
        self.assertNotIn("murieron", r.stdout, "no puede cantar muertes que midió el reloj")

    def test_el_tope_invalido_no_se_informa_como_suite_en_rojo(self):
        """Los dos motivos mandan a lugares distintos: «la suite está en rojo» es del proyecto
        y «el tope es inválido» es de la configuración. Devolver un solo False hacía que un
        tope mal puesto se informara como suite roja —falso— y encima con código 0."""
        self.con_loop()
        r = self.mutar(tope="0.01")
        self.assertNotIn("la suite ya está en rojo", r.stdout,
                         f"la suite está VERDE; el problema es el tope:\n{r.stdout}")

    def test_sin_tope_forzado_se_calibra_con_la_suite(self):
        """Una suite de 0,2 s y una de 15 minutos no pueden compartir número."""
        self.con_loop()
        r = self.mutar()
        self.assertIn("tope por mutante", r.stdout, f"\n{r.stdout}")
        self.assertRegex(r.stdout, r"la suite sin mutar tarda \d+\.\d+s",
                         "tiene que decir con qué calibró")


class TestElMetodoEsReplicableSiguiendoSuPropiaGuia(unittest.TestCase):
    """¿Un proyecto NUEVO puede aplicar el método siguiendo `EMPEZAR.md`? Hasta el
    2026-10-25 la respuesta era no, y el documento afirmaba lo contrario.

    Seguido al pie de la letra, el procedimiento producía un proyecto donde el gate daba
    ROJO por tres motivos distintos:

      · no copiaba `scripts/correr-suite.sh`, que el gate exige —«el proyecto no declara
        cómo se corre su suite»— y que vive en `plantillas/`;
      · su sección 3 decía «tiene que dar verde sobre el repo limpio», que es IMPOSIBLE en
        ese paso: el gate exige que la suite ejecute algo y todavía no hay tests. El verde
        llega recién con la primera tarea hecha a mano;
      · y nombraba `ejemplo-pacman/scripts/gate.sh` en vez del gate del proyecto nuevo,
        residuo de copiar el comando de otro lado.

    Este test EJECUTA los comandos del propio documento en vez de repetirlos acá. Si alguien
    cambia el procedimiento, lo que se mide cambia con él; copiarlos sería medir mi copia, y
    el repo ya tiene demasiadas prosas que dicen una cosa y código que hace otra."""

    def bloques_de_bash(self):
        """Los bloques ```bash del documento, en orden."""
        texto = (RAIZ / "EMPEZAR.md").read_text()
        return re.findall(r"```bash\n(.*?)```", texto, re.S)

    def test_el_procedimiento_copia_lo_que_el_gate_exige(self):
        """Los tres archivos que el gate reclama por su cuenta tienen que salir del
        procedimiento o de `$AGENTES`: `correr-suite.sh` del proyecto, y los dos auxiliares
        que provee el método."""
        comandos = "\n".join(self.bloques_de_bash())
        self.assertIn("plantillas/correr-suite.sh", comandos,
                      "sin copiarlo, el gate da «el proyecto no declara cómo se corre su "
                      "suite» y el documento promete verde")
        self.assertIn("plantillas/gate.sh", comandos, "el juez tiene que copiarse")
        # Los auxiliares del método NO se copian: se resuelven con $AGENTES, y el documento
        # tiene que decir que esa variable se exporta.
        self.assertIn("export AGENTES", comandos,
                      "sin $AGENTES el gate no encuentra _imports.py ni _suprimidas.py")

    def test_el_proyecto_armado_asi_da_el_rojo_ESPERADO_y_no_otro(self):
        """La prueba de replicabilidad: se arma el proyecto con los comandos del documento y
        se corre su gate. El rojo correcto es «la suite no corrió ningún test» —no hay tests
        todavía—; cualquier otro rojo es una pieza que el procedimiento no deja en su lugar."""
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-replicable-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        proy = d / "mi-proyecto"
        # El bloque del paso 1, tal como está en el documento, con `~/mi-proyecto` apuntado
        # al temporal y sin el `git clone` del paso 0.
        paso1 = next(b for b in self.bloques_de_bash() if "mkdir -p tareas scripts src tests" in b)
        guion = (f"set -e\nexport AGENTES={RAIZ}\n"
                 + paso1.replace("~/mi-proyecto", str(proy))
                        .replace("git commit -m", "git -c user.email=t@t -c user.name=t commit -m"))
        r = correr(f"bash -c {shlex.quote(guion)}", d)
        self.assertTrue(proy.is_dir(), f"el procedimiento no armó el proyecto:\n{r.stderr}")
        g = correr(f"AGENTES={RAIZ} bash scripts/gate.sh", proy)
        rojos = [l.strip() for l in g.stdout.splitlines() if l.strip().startswith("✗")]
        self.assertEqual(len(rojos), 1,
                         "el gate de un proyecto recién armado tiene UN rojo —el de la suite "
                         f"vacía— y no {len(rojos)}:\n" + "\n".join(rojos))
        self.assertIn("no corrió ningún test", rojos[0],
                      f"el rojo tiene que ser el de la suite vacía, no una pieza faltante:\n"
                      f"{rojos[0]}")

    def test_la_guia_no_manda_a_probar_el_gate_de_un_ejemplo(self):
        """Decía `ejemplo-pacman/scripts/gate.sh` donde va el del proyecto nuevo. Quien sigue
        la guía termina probando el gate de otro proyecto y creyendo que probó el suyo."""
        texto = (RAIZ / "EMPEZAR.md").read_text()
        i = texto.index("## 3. Ajustá el gate")
        seccion = texto[i:texto.index("## 4.", i)]
        self.assertNotIn("ejemplo-pacman/scripts/gate.sh", seccion,
                         f"manda a probar el gate de un ejemplo:\n{seccion[:300]}")

    def test_la_guia_avisa_que_ese_paso_da_rojo(self):
        """Prometer verde donde el rojo es obligado enseña a ignorar el rojo, que es lo último
        que este método puede permitirse.

        La aserción es POSITIVA —que avise del rojo— y no negativa sobre la frase vieja. Mi
        primera versión buscaba que «tiene que dar verde sobre el repo limpio» no apareciera, y
        la encontró en la prosa que EXPLICA que esa frase era falsa. Una aserción negativa
        sobre texto es frágil por naturaleza: la explicación de un arreglo cita lo que
        arregló. Novena vez en el día que un test mío matchea prosa."""
        texto = (RAIZ / "EMPEZAR.md").read_text()
        i = texto.index("## 3. Ajustá el gate")
        seccion = texto[i:texto.index("## 4.", i)]
        self.assertIn("ROJO", seccion,
                      f"tiene que avisar que ese paso da rojo:\n{seccion[:300]}")
        self.assertIn("sin tests no hay gate", seccion,
                      "y decir POR QUÉ, que es lo que evita que alguien lo tome por una falla")


class TestLoQueSeReplicaTieneQueEstarVivoYExplicado(unittest.TestCase):
    """Dos guardianes sobre la pieza que cada proyecto nuevo copia.

    Medido el 2026-10-25, en el ciclo de replicabilidad:

      · `plantillas/gate.sh` tenía `herramienta_falta()` definida y JAMÁS llamada —residuo de
        cuando la detección del corredor ausente se movió a `correr-suite.sh`, que emite
        FALTA_CORREDOR—. Era la única función muerta de todo el método y estaba justo en la
        plantilla. Los dos ejemplos ya la habían eliminado: la plantilla estaba ATRASADA
        respecto de ellos, al revés de lo que supuse al empezar a medir;
      · `EMPEZAR.md` no mencionaba la SUITE RESERVADA ni una vez, y el gate la exige. Está en
        METODO.md y PRUEBAS.md, pero no en el documento que alguien sigue para replicar: un
        proyecto nuevo la ve como ⊘ para siempre sin saber qué le piden, y es lo que el propio
        gate llama «el único que mide lo que el agente no pudo optimizar»."""

    def scripts_del_metodo(self):
        return (sorted(SCRIPTS.glob("*.sh")) + sorted(PLANTILLAS.glob("*.sh"))
                + sorted(RAIZ.glob("ejemplo-*/scripts/*.sh")))

    def test_ninguna_funcion_de_shell_esta_definida_y_sin_llamar(self):
        """Los usos se buscan en TODO el método, no en el archivo que define: `_comun.sh` es
        una biblioteca y sus funciones se llaman desde otros scripts. Mi primer barrido las
        contó dentro del propio archivo y dio 24 muertas, de las cuales 23 eran falsas."""
        archivos = self.scripts_del_metodo()
        sin_comentarios = lambda t: "\n".join(
            l for l in t.split("\n") if not l.strip().startswith("#"))
        todo = "\n".join(sin_comentarios(f.read_text()) for f in archivos)
        muertas = []
        for f in archivos:
            codigo = sin_comentarios(f.read_text())
            for m in re.finditer(r"^([a-z_][a-z0-9_]*)\(\)\s*\{", codigo, re.M):
                n = m.group(1)
                defs = len(re.findall(rf"^{re.escape(n)}\(\)", todo, re.M))
                if len(re.findall(rf"\b{re.escape(n)}\b", todo)) - defs == 0:
                    muertas.append(f"{f.relative_to(RAIZ)}: {n}()")
        self.assertEqual(sorted(set(muertas)), [],
                         "funciones definidas que nadie llama. En la plantilla es peor: todo "
                         "proyecto nuevo la copia.\n  " + "\n  ".join(sorted(set(muertas))))

    def test_la_guia_de_arranque_explica_la_suite_reservada(self):
        """El gate la exige y la guía no la nombraba. Una pieza que existe pero no se replica
        es, para un proyecto nuevo, una pieza que no existe."""
        guia = (RAIZ / "EMPEZAR.md").read_text()
        self.assertRegex(guia, r"reservad",
                         "la guía no menciona la suite reservada, que el gate exige")
        # Y con lo que hace falta para armarla: dónde va y por qué va AFUERA.
        self.assertIn("reservados-", guia,
                      "tiene que decir dónde la busca el gate: ../reservados-<proyecto>")
        i = guia.lower().index("reservad")
        bloque = guia[max(0, i - 400):i + 1200]
        self.assertIn("fuera", bloque.lower(),
                      "y por qué van afuera del repo, que es la parte que un proyecto nuevo "
                      "se saltea si no se lo explican")

    def test_el_gate_que_se_copia_pide_lo_que_la_guia_arma(self):
        """El cruce que importa: cada ruta que el gate exige por su cuenta tiene que salir del
        procedimiento de la guía o de `$AGENTES`. Es la forma general del defecto que dejaba un
        proyecto nuevo con el gate en rojo por falta de `correr-suite.sh`."""
        gate = (PLANTILLAS / "gate.sh").read_text()
        guia = (RAIZ / "EMPEZAR.md").read_text()
        exigidas = set(re.findall(r'no existe (scripts/[a-z_.-]+)', gate))
        exigidas |= set(re.findall(r'falta (scripts/[a-z_.-]+)', gate))
        self.assertTrue(exigidas, "el gate dejó de exigir rutas: revisá este test")
        # Los AUXILIARES que el método provee se resuelven con `$AGENTES` y no se copian; el
        # resto tiene que estar nombrado en el procedimiento.
        #
        # Mi primera versión ponía `and "export AGENTES" not in guia` en la condición, y como
        # la guía SÍ lo tiene, la lista salía SIEMPRE vacía: un test que no podía fallar.
        # Escribí una tautología el mismo día que agregué el chequeo que las detecta, y la
        # encontró el control de reintroducción —sacar `correr-suite.sh` de la guía lo dejaba
        # en verde— y no la lectura.
        # Los auxiliares se reconocen por cómo el gate los RESUELVE —`aux_del_metodo X`— y no
        # por una convención de nombres. Mi primera versión usaba el prefijo `_`, y este test
        # marcó `mutar.py`: entró al gate hoy en el paso 4b, se resuelve con `aux_del_metodo`
        # y no empieza con guión bajo. El test tenía razón y la clasificación era mía.
        del_metodo = set(re.findall(r"aux_del_metodo ([a-z_][a-z0-9_.]*)", gate))
        # En los COMANDOS, no en la prosa: lo que tiene que pasar es que el procedimiento
        # ponga el archivo en su lugar, no que el documento lo nombre. Mi versión anterior
        # buscaba en todo el texto y `correr-suite.sh` aparece en la explicación de la sección
        # 3, así que quitar el `cp` dejaba el test en verde. Décima vez en el día que una
        # aserción mía mide prosa en vez de conducta.
        comandos = "\n".join(re.findall(r"```bash\n(.*?)```", guia, re.S))
        faltan = [r for r in sorted(exigidas)
                  if r.split("/")[-1] not in del_metodo
                  and r.split("/")[-1] not in comandos]
        self.assertEqual(faltan, [],
                         "el gate exige estas rutas y la guía no dice de dónde salen: "
                         + ", ".join(faltan))


class TestElValidadorPremiabaElIncumplimientoTotal(unittest.TestCase):
    """`validar-plan.py` condicionaba TODO el chequeo de la tabla de tests a que hubiera al
    menos una fila: `if tests_plan:`. Declarar una tarea obligaba a declararlas todas;
    declarar NINGUNA no obligaba nada.

    Medido el 2026-10-25: `ejemplo-pacman` tiene 19 tareas cerradas, ninguna declara su test,
    17 de 19 están fuera del alcance de todos los chequeos que cruzan test contra
    implementación, y su plan validaba limpio. Estaba «bien» ante el validador precisamente
    por no haber declarado ni una.

    Es la tercera vez en el día con la misma forma —una condición que protege al caso completo
    y deja libre al vacío—: el brazo nulo conjunto absolvía a dos archivos si uno era
    necesario, y la excepción de `conservar_intento` se leyó como excepción de la base.

    Y la plantilla de PLAN.md no traía la tabla, así que el camino por DEFECTO producía
    proyectos opacos."""

    def plan_con(self, tests=""):
        d = pathlib.Path(tempfile.mkdtemp(prefix="prueba-tablatests-")).resolve()
        (d / ".quien-lo-creo").write_text(_test_en_curso() + "\n")
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "tareas").mkdir()
        for tid in ("T01", "T02"):
            (d / "tareas" / f"{tid}-cosa.md").write_text(
                f"# {tid} — Cosa\n\n**Estado:** pendiente\n**Depende de:** —\n"
                f"**Archivos que podés tocar:** src/{tid.lower()}.py\n"
                f"**Prohibido tocar:** Ninguno\n\n## Objetivo\n\nAlgo.\n\n"
                f"## Tests (ya escritos, fallando)\n\n"
                f"Archivo: `tests/test_{tid.lower()}.py`, clase `Test{tid}`.\n")
        (d / "PLAN.md").write_text(
            "# Plan\n\n**Estado del gate G0:** aprobado por nadie el 2026-01-01\n\n"
            "## Requisitos\n\n- `algo` — que haya algo\n\n"
            "## Tareas\n\n| # | Tarea | Depende de | Archivos | Estado |\n|---|---|---|---|---|\n"
            "| T01 | Una | — | src/t01.py | pendiente |\n"
            "| T02 | Otra | T01 | src/t02.py | pendiente |\n" + tests)
        return d

    TABLA = ("\n## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
             "| T01 | tests/test_t01.py | TestT01 |\n"
             "| T02 | tests/test_t02.py | TestT02 |\n")

    def validar(self, d):
        return correr(f"PLAN=PLAN.md python3 {SCRIPTS}/validar-plan.py", d)

    def test_un_plan_sin_ninguna_fila_avisa_con_el_conteo(self):
        r = self.validar(self.plan_con(""))
        self.assertIn("ninguna de las 2 tarea(s)", r.stdout,
                      f"no declarar NADA salía gratis:\n{r.stdout}")
        # Y con la consecuencia, que es lo que distingue un aviso de un ruido.
        self.assertIn("no pueden auditar NINGUNA", r.stdout, f"\n{r.stdout}")

    def test_un_plan_con_la_tabla_completa_no_avisa(self):
        r = self.validar(self.plan_con(self.TABLA))
        self.assertNotIn("ninguna de las", r.stdout,
                         f"declarando todo no corresponde el aviso:\n{r.stdout}")

    def test_declarar_a_medias_sigue_siendo_error(self):
        """El chequeo que ya existía no se tocó: una fila de dos es un error de forma, porque
        `escribir-tests.sh` saltea la que falta."""
        media = ("\n## Tests\n\n| Tarea | Archivo de test | Clase |\n|---|---|---|\n"
                 "| T01 | tests/test_t01.py | TestT01 |\n")
        r = self.validar(self.plan_con(media))
        self.assertIn("sin test declarado", r.stdout, f"\n{r.stdout}")
        self.assertNotEqual(r.returncode, 0, "declarar a medias es error, no aviso")

    def test_la_plantilla_trae_la_tabla_y_el_validador_la_LEE(self):
        """La plantilla es el camino por defecto: si no la trae, todo proyecto nuevo nace
        opaco. Y tiene que ser LEGIBLE: mi primera versión usaba placeholders `Test<LoQueSea>`
        y el validador exige que la clase sea un identificador, así que la tabla no se leía y
        la plantilla avisaba CONTRA SÍ MISMA."""
        plan = (PLANTILLAS / "PLAN.md").read_text()
        self.assertRegex(plan, r"##+ *Tests", "la plantilla no trae la tabla de tests")
        filas = re.findall(
            r"^\|\s*(T\d+[a-z]?)\s*\|\s*`?([^|`]+?)`?\s*\|\s*`?([A-Za-z_][\w]*)`?\s*\|\s*$",
            plan, re.M)
        self.assertGreaterEqual(len(filas), 2,
                                f"el validador no puede LEER la tabla de la plantilla: sus "
                                f"filas tienen que cumplir el formato, sin `<>`. Leí: {filas}")
