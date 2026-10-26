#!/usr/bin/env bash
# Métricas del método, leídas del registro de intentos que escribe el runner.
#
#   bash scripts/metricas.sh
#   PROYECTO=ejemplo-pacman bash scripts/metricas.sh
#
# El registro (.metricas/intentos.csv) tiene una línea por corrida de agente:
# fecha, proyecto, tarea, veredicto, segundos, modelo. Se escribe solo, y es la
# única fuente honesta: deducir los intentos del texto de las tareas da números
# lindos y falsos (lo probamos: decía 80% donde la realidad era 0 de 4).
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
ubicar_proyecto

REG="$RAIZ/.metricas/intentos.csv"
if [ ! -f "$REG" ]; then
  echo "Todavía no hay intentos registrados en $REG."
  echo "Se escribe solo cada vez que corrés scripts/correr-tarea.sh."
  exit 0
fi

PROY="${PROYECTO:-.}" REGISTRO="$REG" RAIZ_REPO="$RAIZ" python3 - <<'PY'
import collections, csv, os, statistics

proyecto = os.environ["PROY"]
_lector = csv.DictReader(open(os.environ["REGISTRO"]))
campos = _lector.fieldnames or []
filas = [f for f in _lector if f["proyecto"] == proyecto]
if not filas:
    raise SystemExit(f"No hay intentos registrados para el proyecto '{proyecto}'.")

por_tarea = collections.OrderedDict()
for f in filas:
    por_tarea.setdefault(f["tarea"], []).append(f)

# Qué fila puede entrar a una TASA. Tres clases de fila no hablan del ejecutor y el
# instrumento las contaba como su rojo o como su verde:
#
#  · INVÁLIDA del método: `correr-suite.sh` declara `exit 3` = «es un defecto del método o
#    del plan, no del código que se juzga». Los primeros intentos de T01, T02 y T03 de
#    clasificados son exactamente eso —faltaba el corredor de tests—, y los tres contaban
#    como ROJO del modelo. Corregidos, la tasa de clasificados pasa de 47% a 60%, o sea de
#    «tareas demasiado grandes o criterios flojos» a «la descomposición funciona»: el
#    diagnóstico sobre la descomposición lo decidían tres filas cuyo propio motivo dice que
#    no hablan del código. MEDICION.md §6.3 ya las nombraba; nadie las leía.
#  · PERDIDA por la plataforma: el propio informe dice «no cuentan contra el modelo» tres
#    bloques más abajo, y acto seguido una fila ERROR hacía de «primer intento» de su tarea y
#    la marcaba ✗. Si no cuenta, no cuenta en ningún lado.
#  · NO ATRIBUIBLE a un modelo: `cerrar-tarea.sh` escribe `modelo=humano` en el MISMO
#    registro, y había filas con la columna vacía. El 61% del pacman se apoyaba en una de
#    ellas: sacando sólo T16 (segundos=0, modelo=humano) da 58%, y sacando las cuatro no
#    atribuibles, 44%. El único proyecto que «funcionaba» cruzaba el umbral por trabajo
#    humano contado como verde del modelo.
#
# La lista de marcas es una ENUMERACIÓN, que es la forma que envejece callando, así que hay
# un test que la cruza contra los mensajes que los gates imprimen de verdad.
MARCAS_INVALIDO = ("corredor", "no corrió ningún test")


def invalido(f):
    m = (f.get("motivo") or "").lower()
    return f["veredicto"] == "ROJO" and any(x in m for x in MARCAS_INVALIDO)


def de_un_modelo(f):
    m = (f.get("modelo") or "").strip()
    return bool(m) and m != "humano"


print(f"{'TAREA':<6} {'INTENTOS':>8}  {'RESULTADO':<12} {'1er INTENTO':<12} {'SEGUNDOS':>9}")
print("─" * 60)
primera_verde = cerradas = 0
delegables = []
n_invalidas = sum(1 for f in filas if invalido(f))
for tarea, intentos in sorted(por_tarea.items()):
    vers = [i["veredicto"] for i in intentos]
    final = vers[-1]
    # El primer intento es el primero que PUDO contar: ni inválido del método ni ajeno a un
    # modelo. Si no hay ninguno, la tarea no entra en la tasa — ni arriba ni abajo.
    cuentan = [i for i in intentos if not invalido(i) and de_un_modelo(i)
               and i["veredicto"] != "ERROR"]
    ok_primero = bool(cuentan) and cuentan[0]["veredicto"] == "VERDE"
    if cuentan:
        delegables.append(tarea)
        if any(i["veredicto"] == "VERDE" for i in cuentan):
            cerradas += 1
        primera_verde += ok_primero
    if not cuentan:
        col = "⊘ no cuenta"
    elif ok_primero:
        col = "✓ verde"
    else:
        col = "✗ " + cuentan[0]["veredicto"]
    segs = [int(i["segundos"]) for i in intentos if i["segundos"].isdigit()]
    print(f"{tarea:<6} {len(intentos):>8}  {final:<12} {col:<12} {sum(segs):>9}")

print()
total_int = len(filas)
errores = sum(1 for f in filas if f["veredicto"] == "ERROR")
imposibles = sorted({f["tarea"] for f in filas if f["veredicto"] == "IMPOSIBLE"})
segs = [int(f["segundos"]) for f in filas if f["segundos"].isdigit()]
print(f"Intentos: {total_int}   ·   tareas intentadas: {len(por_tarea)}")
if por_tarea:
    # El denominador son TODAS las tareas que tuvieron al menos un intento contable, no solo
    # las que llegaron a verde: contar solo las exitosas es sesgo de supervivencia y da
    # números lindos y falsos. Las imposibles salen del denominador: miden la calidad del
    # plan, no la del ejecutor.
    cuenta_deleg = [t for t in delegables if t not in imposibles]
    n_deleg = len(cuenta_deleg)
    pct = primera_verde * 100 // n_deleg if n_deleg else 0
    print(f"Verde al PRIMER intento: {primera_verde}/{n_deleg} ({pct}%)"
          + (f"  [{len(imposibles)} imposible/s fuera del denominador]" if imposibles else ""))
    fuera = len(por_tarea) - len(delegables)
    if fuera or n_invalidas:
        print(f"  ⊘ fuera de esa tasa: {fuera} tarea(s) sin ningún intento atribuible a un "
              f"modelo, {n_invalidas} intento(s) inválidos del método (exit 3 de la suite)")
    # Numerador y denominador sobre el MISMO conjunto. Antes el numerador descontaba las
    # imposibles y el denominador no, así que la fracción podía mentir en los dos dígitos.
    # Dormido hasta hoy: no hay una sola fila IMPOSIBLE en el registro, o sea que todo este
    # camino nunca se ejecutó con datos.
    nunca_verde = n_deleg - cerradas
    if nunca_verde > 0:
        print(f"Nunca llegaron a verde: {nunca_verde}/{n_deleg} "
              f"— las cerró un humano (regla: lo que falla dos veces no se insiste)")
    # El instrumento: la columna se escribía y NADIE la leía, así que este porcentaje mezclaba
    # todas las corridas históricas del proyecto. MEDICION.md §5 declara que dos filas con
    # huellas distintas no son comparables, y el número que se imprime al final de cada
    # corrida las mezclaba sin decirlo. Hoy el registro tiene seis huellas distintas.
    huellas = {f.get("instrumento") or "" for f in filas} - {""}
    import subprocess as _sp
    # La huella de AHORA se arma igual que la escribe `anotar_intento`, con la marca de árbol
    # sucio incluida. Y se compara por IGUALDAD, no con `startswith`: `X` y `X+sin-commitear`
    # son instrumentos distintos —es justo la distinción que la marca existe para crear— y el
    # prefijo los metía en el mismo balde, deshaciendo dos líneas más abajo lo que el escritor
    # acababa de distinguir.
    # Con `-C <raíz>` las dos preguntas hablan del mismo árbol. `HEAD:scripts` lo resuelve
    # git desde la RAÍZ del repo y el pathspec de `git diff` es relativo al cwd, así que
    # corrido desde `ejemplo-pacman/` uno miraba los scripts del método y el otro los del
    # proyecto. Es el mismo defecto que acabo de arreglar en `_suprimidas.py`, cometido en
    # el arreglo del otro: `git -C` desde el principio o no hay forma de no repetirlo.
    raiz = os.environ.get("RAIZ_REPO") or "."
    actual = _sp.run(["git", "-C", raiz, "rev-parse", "--short", "HEAD:scripts"],
                     capture_output=True, text=True).stdout.strip()
    if actual and _sp.run(["git", "-C", raiz, "diff", "--quiet", "HEAD", "--",
                           "scripts"]).returncode != 0:
        actual += "+sin-commitear"
    if len(huellas) > 1:
        print(f"  ⊘ ese {pct}% mezcla {len(huellas)} instrumentos distintos "
              "(MEDICION.md §5: huellas distintas no se comparan)")
    # Afuera del `len(huellas) > 1`. Con UNA sola huella distinta de la de ahora no se
    # imprimía ni un ⊘: proyecto nuevo, las cinco tareas corridas con el instrumento A,
    # arreglás un script, y el número sigue anunciándose como si describiera el instrumento
    # instalado. Lo que invalida una comparación no es que haya varias huellas: es que la
    # huella de los datos no sea la de ahora.
    if not actual:
        # Si no se puede saber con qué instrumento corre esto, no se puede saber si los datos
        # son comparables — y el bloque entero se salteaba en silencio, que es la misma
        # vacuidad: un chequeo que no puede correr no es un chequeo que pasó.
        print("  ⊘ no se puede leer la huella del instrumento de ahora "
              "(¿scripts/ no está commiteado?): ningún número de acá es comparable")
    elif huellas and huellas != {actual}:
        print(f"  ⊘ el instrumento de ahora ({actual}) no es el de "
              f"{'todos' if actual not in huellas else 'parte de'} los datos: "
              "MEDICION.md §5 dice que eso no se compara")
    mismas = [f for f in filas if (f.get("instrumento") or "") == actual] if actual else []
    if mismas:
        # El primer intento de la TAREA, no la primera fila dentro de esta huella. T04b es
        # VERDE con una huella y VERDE otra vez con la siguiente: contar la segunda como
        # «verde al primer intento» sobre una tarea ya resuelta es sesgo de truncamiento.
        pt = collections.defaultdict(list)
        for f in mismas:
            pt[f["tarea"]].append(f)
        enteras = {t: v for t, v in pt.items() if por_tarea[t][0] in v}
        pv = sum(1 for ts in enteras.values() if ts[0]["veredicto"] == "VERDE")
        if enteras:
            print(f"     con el instrumento de ahora ({actual}): {pv}/{len(enteras)} "
                  f"al primer intento, sobre {len(mismas)} intento(s)")
            if len(enteras) < 2:
                # MEDICION.md §1 pregunta 1: «Un n=1 es una parada». Tres de las seis huellas
                # del registro tienen una sola tarea, y se imprimía «0/1 al primer intento»
                # como si fuera un número.
                print(f"     ⊘ n={len(enteras)}: no es una tasa todavía (MEDICION.md §1)")
        else:
            print(f"     con el instrumento de ahora ({actual}) hay {len(mismas)} intento(s), "
                  "pero ninguno es el PRIMERO de su tarea: no hay tasa que calcular")
    else:
        print(f"     con el instrumento de ahora no hay ningún intento todavía: "
              "el próximo número comparable empieza de cero")
    if pct >= 60:   print("→ ≥60%: la descomposición funciona.")
    elif pct >= 30: print("→ 30-60%: tareas demasiado grandes o criterios flojos.")
    else:           print("→ <30%: el problema está en el plan, no en el modelo.")
if errores:
    print(f"Intentos perdidos por errores de plataforma: {errores} "
          f"({errores * 100 // total_int}%) — no cuentan contra el modelo")
# Los motivos repetidos son la señal más útil del registro: si tres tareas fallan por lo
# mismo, el problema es del plan o del gate, no de las tareas.
motivos = collections.Counter(f.get("motivo", "") for f in filas
                              if f["veredicto"] == "ROJO" and f.get("motivo"))
repetidos = [(m, n) for m, n in motivos.most_common(3) if n > 1]
if repetidos:
    print("Motivos de rojo que se repiten:")
    for m, n in repetidos:
        print(f"  {n}×  {m[:70]}")

if imposibles:
    # No son fallas del agente: son tareas mal especificadas que el agente detectó. Contarlas
    # como rojo escondería la señal más útil que da el canal de escalada, y además mezclaría
    # un problema del plan con un problema del modelo.
    print(f"Declaradas IMPOSIBLES por el agente: {len(imposibles)} "
          f"({', '.join(imposibles)}) — son problemas del plan, no del modelo. Leé el motivo.")
# Lo que este lector NECESITA tiene que estar en el encabezado, o `DictReader` devuelve esa
# clave vacía para siempre y el bloque que la usa no imprime nada mientras hay datos de sobra.
# Pasó con `motivo`. Un instrumento que lee por nombre tiene que verificar los nombres.
#
# SUBCONJUNTO y no igualdad: la comparación exacta hacía que agregar una columna al registro
# —`contextos`, que el runner escribe desde hace días— informara ⊘ en CADA corrida, con todo
# funcionando. Un aviso que grita en el caso normal enseña a ignorar los avisos, y éste tapaba
# su propio motivo: lo que importa es que no FALTE ninguna de las que leo, no que no sobre.
NECESARIAS = ["fecha", "proyecto", "tarea", "veredicto", "segundos", "modelo", "motivo",
              "concurrencia", "instrumento"]
faltan_cols = [c for c in NECESARIAS if c not in campos]
if faltan_cols:
    print(f"⊘ al registro le faltan columnas que este reporte lee: {faltan_cols}")
    print(f"  encabezado encontrado: {campos} — una columna ausente se lee vacía, no ausente")

if segs:
    # Una mediana de tiempos de corridas simultáneas describe la ocupación de la plataforma,
    # no la tarea: con PARALELAS=8 el mismo modelo pasa de 16,3 a 122 tok/s. Si las corridas
    # comparten ventana, el número no se muestra. Es la misma regla que SERIE=1 en
    # comparar-modelos.sh, que estaba arreglada de un lado y no del otro.
    # La columna `concurrencia` la escribe el runner al arrancar cada corrida. Antes esto
    # infería el solapamiento comparando timestamps a 60 s, que era un paliativo: dos corridas
    # pueden arrancar en el mismo segundo sin competir, y dos separadas por minutos pueden
    # solaparse si la primera duró mucho. El dato lo tiene quien corrió, no quien analiza.
    # `concurrencia == 0`, no `<= 1`: el 1 admitía una fila con un competidor vivo, que es
    # justo lo que la columna existe para excluir.
    #
    # Y sin las filas ERROR: 6 de las 16 que entraban a la mediana eran errores, 4 de ellas
    # con «límite total 1200s» en el motivo, o sea el TECHO DEL PROPIO VIGILANTE metido
    # adentro del número. MEDICION.md §4 manda INVÁLIDO para un timeout. El «máximo 1855s»
    # que se imprimía era un ROJO; el éxito más lento medía 970 s. Importa porque `_comun.sh`
    # manda al humano a dimensionar el presupuesto del agente con ese máximo.
    serie = [f for f in filas if (f.get("concurrencia") or "").isdigit()
             and int(f["concurrencia"]) == 0 and (f.get("segundos") or "").isdigit()
             and f["veredicto"] not in ("ERROR",) and not invalido(f)]
    sin_dato = [f for f in filas if not (f.get("concurrencia") or "").isdigit()]
    segs_serie = [int(f["segundos"]) for f in serie if int(f["segundos"]) > 0]
    if segs_serie:
        print(f"Tiempo por intento (serializadas, sin inválidas): "
              f"mediana {statistics.median(segs_serie):.0f}s, "
              f"máximo {max(segs_serie)}s, sobre {len(segs_serie)} de {len(filas)} corridas")
        ok = [int(f["segundos"]) for f in serie if f["veredicto"] == "VERDE"
              and int(f["segundos"]) > 0]
        # El dato que se usa para calibrar LIMITE_AGENTE es el éxito más lento, y es el único
        # que no puede estar contaminado por el límite que se quiere calibrar.
        print(f"  éxito más lento: {max(ok)}s (sobre {len(ok)} verde/s)" if ok else
              "  ⊘ ninguna corrida verde y serializada: no hay con qué calibrar el presupuesto")
    else:
        print(f"Tiempo por intento: — (0 de {len(filas)} corridas son serializadas y válidas; "
              "con tareas en paralelo el tiempo mide la plataforma, no la tarea)")
    if sin_dato:
        print(f"  ⊘ {len(sin_dato)} corrida(s) sin columna `concurrencia`: anteriores al "
              "arreglo, su tiempo no se puede atribuir y no entra en la mediana")
modelos = collections.Counter(f.get("modelo") or "(sin registrar)" for f in filas)
print("Modelos usados: " + ", ".join(f"{m} ({n})" for m, n in modelos.items()))
if modelos.get("(sin registrar)"):
    # Una columna vacía no puede desaparecer del reporte: así vivió un bug del extractor
    # durante tres corridas sin que nadie lo viera.
    print(f"  ⊘ {modelos['(sin registrar)']} intento(s) sin modelo registrado — el extractor falló")
PY
