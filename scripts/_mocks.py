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

## `--corregir`: por qué el método repara esto y nada más

Medido el 2026-10-27 en tres brazos de 21 tareas con modelos de verdad: de los ocho tests
rechazados por este chequeo, **los ocho** eran correctos salvo el objetivo del patch —clase
declarada, aserciones presentes, valores bien— y los tres brazos se detuvieron en la misma
etapa por eso. Y tres canales distintos para decírselo al agente no mueven el sesgo: la regla
en `AGENTS.md` (que OpenCode inyecta: llegó a 7 de 7 y 4 la ignoraron), el reemplazo exacto en
el prompt del reintento (mejora la recuperación, no la primera pasada) y el contrato de la
tarea (ningún efecto: 8 rechazos contra 8).

Lo que se corrige es **una ruta de import, no un test**: no se toca ninguna aserción, ningún
valor esperado ni ningún nombre de caso. El objetivo correcto es una consecuencia mecánica
del import que el contrato ya fija, se calcula por árbol sintáctico y tiene par discriminante
—con el `from` adentro de la función o con `import X` + `X.n` el patch SÍ pega y no se toca
nada—. Los cinco pasos que preguntan si el test distingue siguen juzgando después, sobre el
test corregido.

El riesgo de corregir no es aflojar el gate: es **perder la señal** de que el modelo tiene el
sesgo, que es parte del dataset que este método existe para producir. Por eso corregir deja
constancia en tres lugares y no uno: el log de la corrida, `.metricas/correcciones.csv` y una
copia del test tal como lo escribió el agente. Una corrección en silencio sería un verde
falso del método sobre sí mismo.
"""
import ast
import datetime
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


def corregir_en_archivo(test, inefectivos, tarea, registro):
    """Reescribe el objetivo de cada patch inefectivo, y sólo eso.

    Línea por línea y no sobre el archivo entero: la posición sale del árbol sintáctico, así
    que se toca exactamente la línea del `patch` y nada más. El original queda al lado como
    `<test>.del-agente`, porque el dataset necesita lo que el agente escribió, no lo que el
    método dejó.
    """
    lineas = test.read_text(encoding="utf-8", errors="replace").split("\n")
    hechas = []
    for modulo, simbolo, nro, destino, _fuente in inefectivos:
        i = nro - 1
        if not (0 <= i < len(lineas)):
            continue
        viejo, nuevo = "%s.%s" % (modulo, simbolo), "%s.%s" % (destino, simbolo)
        if viejo not in lineas[i]:
            continue
        lineas[i] = lineas[i].replace(viejo, nuevo)
        hechas.append((nro, viejo, nuevo))
    if not hechas:
        return []
    reg = pathlib.Path(registro)
    original = reg / "del-agente" / test.name
    try:
        original.parent.mkdir(parents=True, exist_ok=True)
        if not original.exists():
            original.write_text(test.read_text(encoding="utf-8", errors="replace"),
                                encoding="utf-8")
    except OSError as e:
        print("  ✗ no pude guardar el test del agente (%s): no corrijo" % e)
        return []
    test.write_text("\n".join(lineas), encoding="utf-8")
    try:
        reg.mkdir(parents=True, exist_ok=True)
        with (reg / "correcciones.csv").open("a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write("fecha,tarea,archivo,linea,de,a\n")
            for nro, viejo, nuevo in hechas:
                f.write("%s,%s,%s,%d,%s,%s\n" % (
                    datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    (tarea.stem if tarea is not None else "?"), test, nro, viejo, nuevo))
    except OSError as e:
        # Que no se pueda registrar NO es un detalle: una corrección sin constancia es el
        # método tapando la señal que vino a medir. Se informa y se devuelve como no hecha.
        print("  ✗ corregí el patch pero NO pude registrarlo (%s): revertí" % e)
        test.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        return []
    return hechas


def anotar_deuda(test, sin_verificar, tarea, registro):
    """Deja constancia del ⊘ para que el rojo que venga después se le cobre a quien lo debe.

    El ⊘ de este chequeo no es neutral: es una DEUDA, y detona en otra tarea. Medida
    completa el 2026-11-01 en la corrida `f1793535892`, con modelos de verdad:

      · T03b escribió `tests/test_s3.py` con `patch('src.datos.d3.leer3')` y el import
        diferido adentro del test. El enunciado no declaraba con qué import `s3` iba a
        traer el nombre, así que este chequeo salió 2: «no pude determinar». El test pasó
        los cinco pasos que preguntan si DISTINGUE —falla sin la implementación, pasa con
        ella, los mutantes mueren, el brazo nulo falla— y se copió al tronco.
      · Pasó porque corrió SOLO: con `sys.modules` vacío, el import diferido se resuelve
        después del patch y el patch pega.
      · Tres tareas después, T03c escribió `src/rutas/r3.py`, cuyo test importa a nivel de
        módulo y por lo tanto precarga `src.servicios.s3` en el momento de la COLECCIÓN.
        Ahí el import diferido de `test_s3.py` encuentra el módulo en caché con el `leer3`
        de verdad ligado, el patch no pega, y `calcular3()` devuelve 30 en vez de 50.
      · El gate reprobó a T03c con «rompiste tests que andaban antes de esta tarea», que es
        verdad y es el sujeto equivocado: T03c no toca ni `s3` ni `d3`. La etapa se detuvo
        pidiendo que decidiera una persona, sobre la tarea inocente.

    Reproducido a mano, sin modelos: `test_s3.py` sola pasa; `test_r3.py test_s3.py`
    juntas dan `AssertionError: 30 != 50`; con el patch en `src.servicios.s3.leer3` pasa de
    las dos formas. De siete servicios, uno traía la bomba: tres parcheaban donde el nombre
    se usa y tres hacían `import src.datos.dN` adentro de la función, que también deja el
    patch efectivo.

    Lo que esto NO hace es decidir la forma del import: eso lo fija el contrato y lo escribe
    el planificador. Acá sólo se anota quién quedó debiendo, para que el gate pueda nombrar
    al deudor en vez de al vecino.
    """
    reg = pathlib.Path(registro)
    filas = []
    for modulo, simbolo, linea, destino, _por_que in sin_verificar:
        filas.append((tarea.stem if tarea is not None else "?", str(test),
                      "%s.%s" % (modulo, simbolo), destino, linea))
    if not filas:
        return False
    try:
        reg.mkdir(parents=True, exist_ok=True)
        with (reg / "deuda-mocks.csv").open("a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write("fecha,tarea,test,objetivo,destino,linea\n")
            for tarea_id, ruta, objetivo, destino, linea in filas:
                f.write("%s,%s,%s,%s,%s,%d\n" % (
                    datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    tarea_id, ruta, objetivo, destino, linea))
    except OSError as e:
        # A diferencia de una corrección sin constancia, esto no bendice nada: el ⊘ se
        # informa igual y sigue sin ser verde. Lo que se pierde es la atribución del rojo
        # futuro, así que se dice en voz alta y no se calla.
        print("  ✗ no pude anotar la deuda del ⊘ (%s): si esto rompe una tarea" % e)
        print("     después, el gate no va a poder nombrar a %s"
              % (tarea.stem if tarea is not None else "quien lo debe"))
        return False
    return True


def main(argv):
    segun_enunciado = "--segun-enunciado" in argv
    corregir = "--corregir" in argv
    # `--registro <dir>`: dónde dejar la constancia. Sin esto caía en `./.metricas`, que
    # durante la fase de tests es el worktree que después se borra.
    registro = None
    if "--registro" in argv:
        i = argv.index("--registro")
        if i + 1 < len(argv):
            registro = argv[i + 1]
            del argv[i:i + 2]
        else:
            print("  --registro necesita un directorio")
            return 2
    argv = [a for a in argv if a not in ("--segun-enunciado", "--corregir")]
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

    # El ⊘ queda anotado, y eso es la mitad del chequeo: sin constancia, el rojo que este
    # ⊘ produce dentro de tres tareas se le cobra al vecino. Ver `anotar_deuda`.
    if sin_verificar:
        if registro is not None:
            anotar_deuda(test, sin_verificar, tarea, registro)
        else:
            print("  ⊘ sin --registro no puedo anotar la deuda de este ⊘: el rojo que")
            print("     produzca después va a quedar a nombre de otra tarea")

    if inefectivos and corregir:
        if registro is None:
            # Corregir sin saber dónde dejar constancia es corregir en silencio, y eso es
            # exactamente lo que no se puede hacer: el sesgo del modelo es parte del dataset.
            print("  ✗ --corregir necesita --registro <dir>: no corrijo en silencio")
            return 1
        hechas = corregir_en_archivo(test, inefectivos, tarea, registro)
        if hechas:
            for nro, viejo, nuevo in hechas:
                print("  ✎ %s:%d  corregí el objetivo del patch: %s → %s"
                      % (test, nro, viejo, nuevo))
            print("     Lo corrigió el MÉTODO, no el agente. Queda en "
                  "%s/correcciones.csv y el original en %s/del-agente/%s"
                  % (registro, registro, test.name))
            print("     Sólo la ruta del patch: ninguna aserción ni valor esperado se tocó.")
            inefectivos = []

    print("  inspeccionó: %d patch(es) con objetivo literal contra %s"
          % (len(objetivos), fuente_mirada))
    if inefectivos:
        print("  Un patch que no pega hace fallar al test contra la implementación correcta,")
        print("  y el rojo lo paga el que implementa.")
        return 1
    return 2 if sin_verificar else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
