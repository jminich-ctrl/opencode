#!/usr/bin/env python3
"""¿El `patch` de este test tiene efecto sobre el código que la tarea va a escribir?

Medido el 2026-10-27 con modelos de verdad, 21 tareas, la etapa de los siete `calcularN()`.
Los siete tests que escribió el agente parchearon el mismo lugar —el módulo donde el
nombre se **define**—:

    with patch('src.datos.d1.leer1') as mock_leer1:
        mock_leer1.return_value = 5
        self.assertEqual(calcular1(), 50)

Y el enunciado de la tarea pedía, textualmente, «Usa `from src.datos.d1 import leer1`».
Con ese import el nombre queda ligado en `src.servicios.s1` **antes** de que el patch
corra, así que el patch no toca nada: `calcular1()` devuelve `1*10`, el test espera 50, y
el gate da rojo contra una implementación que es palabra por palabra la del contrato.

Tres de las siete tareas quedaron así, y el método las cerró como «punto muerto: falló dos
veces por lo mismo», que acusa al implementador. Las otras cuatro pasaron **desobedeciendo
el contrato**: una hizo `import src.datos.d2` y usó `d2.leer2()`, dos pusieron el `from`
adentro de la función. O sea que el veredicto quedó correlacionado **al revés** de lo
correcto: obedecer el contrato daba rojo.

La regla es exacta y no hace falta correr nada:

    si el test parchea `X.nombre`, y el módulo bajo prueba trae ese nombre con
    `from X import nombre` A NIVEL DE MÓDULO, el patch no puede tener efecto.

«A nivel de módulo» es la mitad de la regla, y es la que la hace angosta: el mismo `from`
adentro de la función se resuelve en cada llamada, y ahí el patch **sí** pega. Lo mismo
`import X` + `X.nombre`. Un chequeo que marcara esas dos muerde al test honesto.

Qué se mira depende de QUIÉN pregunta, y esa mitad me faltaba. Con `--segun-enunciado`
sólo cuenta el enunciado de la tarea; sin la bandera, la implementación que esté en disco le
gana.

La bandera no es una comodidad: es el arreglo de un falso verde medido el 2026-10-27, dos
horas después de escribir este chequeo. En `escribir-tests.sh` la implementación que hay en
disco es un BORRADOR que el método descarta, y lo escribió **el mismo agente que escribió el
test**, así que es coherente con su test por construcción. El chequeo le preguntaba al
acusado: el agente volvió a escribir `patch('src.datos.d1.leer1')`, su borrador trajo el
nombre de una forma que deja el patch efectivo, el chequeo dio verde, el test se copió al
tronco, y en la etapa siguiente otro agente implementó el contrato al pie de la letra y se
comió el rojo. El mismo defecto que este chequeo vino a cerrar, pasando por el chequeo.

  · `--segun-enunciado` — para la puerta donde el test se escribe: el único compromiso que
    existe sobre la implementación FUTURA es el contrato. Si el enunciado no declara con qué
    import se trae el nombre, sale 2, porque el test está apostando.
  · sin bandera — para después, cuando la implementación en disco es la de verdad: ahí le
    gana al enunciado.

No hay un objetivo de patch que funcione contra las tres formas de import, y por eso esto
no se arregla eligiendo mejor el patch: lo que el contrato fija, el test lo tiene que
respetar. Si el contrato no fija la forma, el defecto está en el contrato.

  python3 scripts/_mocks.py tests/test_s1.py tareas/T01b-cosa.md .

  0  ningún patch inefectivo (o no hay patches con objetivo literal)
  1  hay al menos un patch que no puede tener efecto
  2  hay patches cuyo efecto no se pudo determinar — NO es verde
"""
import ast
import pathlib
import re
import sys


def _modulos_del_repo_que_importa(arbol, raiz):
    """Los módulos de este repo que el test trae: los candidatos a «módulo bajo prueba».

    No alcanza con «su .py existe», y es el caso que importa: los tests se escriben ANTES
    de la implementación, así que el módulo bajo prueba casi nunca existe cuando esto
    corre. Mi primera versión lo pedía, y con eso el chequeo daba 0 justo en el escenario
    que vino a cubrir —fallaba abierto—. Alcanza con que su paquete padre sea un
    directorio de este repo.
    """
    salida = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            if _es_del_repo(nodo.module, raiz):
                salida.append(nodo.module)
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if _es_del_repo(alias.name, raiz):
                    salida.append(alias.name)
    return salida


def _es_del_repo(modulo, raiz):
    """¿`modulo` es de este repo, exista ya su archivo o no?"""
    if _archivo_de(modulo, raiz) is not None:
        return True
    partes = modulo.split(".")
    return len(partes) > 1 and raiz.joinpath(*partes[:-1]).is_dir()


def _archivo_de(modulo, raiz):
    """El .py de un módulo puntuado, si vive en este repo."""
    partes = modulo.split(".")
    for candidato in (raiz.joinpath(*partes).with_suffix(".py"),
                      raiz.joinpath(*partes) / "__init__.py"):
        if candidato.is_file():
            return candidato
    return None


def objetivos_de_patch(arbol):
    """Cada `patch("a.b.nombre")` del test, con la línea donde está.

    Sólo las formas con el objetivo en una cadena literal. `patch.object(mod, "nombre")`
    nombra el objeto que parchea, así que no puede fallar por este defecto.
    """
    salida = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not nodo.args:
            continue
        f = nodo.func
        nombre = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
        if nombre != "patch":
            continue
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "patch":
            continue          # `patch.object`, `patch.dict`: el objetivo no es una ruta
        arg = nodo.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "." in arg.value:
            modulo, _, simbolo = arg.value.rpartition(".")
            salida.append((modulo, simbolo, nodo.lineno))
    return salida


def importa_por_nombre_a_nivel_de_modulo(archivo, modulo, simbolo):
    """¿`archivo` hace `from modulo import simbolo` en el cuerpo del módulo?

    Recorre sólo el cuerpo de arriba (y los `if`/`try` de arriba, que también corren al
    importar). Un `from` dentro de una función NO cuenta: se resuelve en cada llamada.
    """
    try:
        arbol = ast.parse(archivo.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    pendientes = list(arbol.body)
    while pendientes:
        nodo = pendientes.pop()
        if isinstance(nodo, ast.ImportFrom) and nodo.module == modulo and nodo.level == 0:
            for alias in nodo.names:
                if alias.name == simbolo and alias.asname is None:
                    return True
        elif isinstance(nodo, (ast.If, ast.Try)):
            for atributo in ("body", "orelse", "finalbody", "handlers"):
                for hijo in getattr(nodo, atributo, []) or []:
                    pendientes.extend(getattr(hijo, "body", [hijo]))
    return False


def el_enunciado_declara_el_from(texto, modulo, simbolo):
    """¿El archivo de tarea le pide al implementador `from modulo import simbolo`?

    Sobre el texto crudo y no sobre un árbol, porque el enunciado es prosa con fragmentos:
    en la tarea medida el import venía en una oración, entre backticks.
    """
    patron = r"from\s+%s\s+import\s+([^\n`]*)" % re.escape(modulo)
    for importados in re.findall(patron, texto):
        partidos = [t.strip() for t in importados.replace("(", "").replace(")", "").split(",")]
        if simbolo in partidos:
            return True
    return False


def main(argv):
    segun_enunciado = "--segun-enunciado" in argv
    argv = [a for a in argv if a != "--segun-enunciado"]
    if not argv:
        print("uso: _mocks.py <archivo_de_test> [<archivo_de_tarea>] [<raiz>]", file=sys.stderr)
        return 2
    test = pathlib.Path(argv[0])
    tarea = pathlib.Path(argv[1]) if len(argv) > 1 and argv[1] else None
    raiz = pathlib.Path(argv[2] if len(argv) > 2 and argv[2] else ".").resolve()
    if not test.is_file():
        print("  no existe %s: no se pudo revisar dónde parchean los tests" % test)
        return 2
    try:
        arbol = ast.parse(test.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as e:
        print("  %s no parsea (%s): no se pudo revisar dónde parchean los tests" % (test, e))
        return 2

    objetivos = objetivos_de_patch(arbol)
    fuente_mirada = ("el enunciado de la tarea" if segun_enunciado
                     else "la implementación en disco, y el enunciado donde no hay")
    if not objetivos:
        print("  inspeccionó: 0 patch(es) con objetivo literal en %s" % test)
        return 0

    bajo_prueba = _modulos_del_repo_que_importa(arbol, raiz)
    texto_tarea = ""
    if tarea is not None and tarea.is_file():
        texto_tarea = tarea.read_text(encoding="utf-8", errors="replace")

    inefectivos, sin_verificar = [], []
    for modulo, simbolo, linea in objetivos:
        for destino in bajo_prueba:
            if destino == modulo:
                continue                      # parchea el módulo que importa: siempre pega
            archivo = None if segun_enunciado else _archivo_de(destino, raiz)
            if archivo is not None:
                visto = importa_por_nombre_a_nivel_de_modulo(archivo, modulo, simbolo)
                if visto is None:
                    sin_verificar.append((modulo, simbolo, linea, destino,
                                          "%s no parsea" % archivo))
                elif visto:
                    inefectivos.append((modulo, simbolo, linea, destino,
                                        "la implementación trae"))
            elif texto_tarea and el_enunciado_declara_el_from(texto_tarea, modulo, simbolo):
                inefectivos.append((modulo, simbolo, linea, destino,
                                    "el enunciado de la tarea manda traer"))
            elif texto_tarea:
                sin_verificar.append((modulo, simbolo, linea, destino,
                                      "todavía no existe, y el enunciado no declara con qué "
                                      "import lo va a traer"))
            else:
                sin_verificar.append((modulo, simbolo, linea, destino,
                                      "todavía no existe y no me pasaron el archivo de tarea"))

    for modulo, simbolo, linea, destino, fuente in inefectivos:
        print("  %s:%d  patch('%s.%s') no va a tener efecto" % (test, linea, modulo, simbolo))
        print("     %s el nombre con `from %s import %s` a nivel de módulo," % (fuente, modulo, simbolo))
        print("     así que %s.%s ya está ligado cuando el patch corre." % (destino, simbolo))
        print("     Parcheá donde se usa:  patch('%s.%s')" % (destino, simbolo))
    for modulo, simbolo, linea, destino, por_que in sin_verificar:
        print("  %s:%d  no pude determinar si patch('%s.%s') tiene efecto sobre %s: %s"
              % (test, linea, modulo, simbolo, destino, por_que))

    print("  inspeccionó: %d patch(es) con objetivo literal contra %s"
          % (len(objetivos), fuente_mirada))
    if inefectivos:
        print("  Un patch que no pega hace fallar al test contra la implementación correcta,")
        print("  y el rojo lo paga el que implementa.")
        return 1
    return 2 if sin_verificar else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
