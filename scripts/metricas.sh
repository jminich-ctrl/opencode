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

PROY="${PROYECTO:-.}" REGISTRO="$REG" python3 - <<'PY'
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

print(f"{'TAREA':<6} {'INTENTOS':>8}  {'RESULTADO':<12} {'1er INTENTO':<12} {'SEGUNDOS':>9}")
print("─" * 60)
primera_verde = cerradas = 0
for tarea, intentos in sorted(por_tarea.items()):
    vers = [i["veredicto"] for i in intentos]
    final = vers[-1]
    ok_primero = vers[0] == "VERDE"
    if "VERDE" in vers:
        cerradas += 1
        primera_verde += ok_primero
    segs = [int(i["segundos"]) for i in intentos if i["segundos"].isdigit()]
    print(f"{tarea:<6} {len(intentos):>8}  {final:<12} "
          f"{'✓ verde' if ok_primero else '✗ ' + vers[0]:<12} {sum(segs):>9}")

print()
total_int = len(filas)
nunca_verde = len(por_tarea) - cerradas
errores = sum(1 for f in filas if f["veredicto"] == "ERROR")
imposibles = sorted({f["tarea"] for f in filas if f["veredicto"] == "IMPOSIBLE"})
segs = [int(f["segundos"]) for f in filas if f["segundos"].isdigit()]
print(f"Intentos: {total_int}   ·   tareas intentadas: {len(por_tarea)}")
if por_tarea:
    # El denominador son TODAS las tareas intentadas, no solo las que llegaron a verde:
    # contar solo las exitosas es sesgo de supervivencia y da números lindos y falsos.
    # Las imposibles salen del denominador: miden la calidad del plan, no la del ejecutor.
    delegables = len(por_tarea) - len(imposibles)
    pct = primera_verde * 100 // delegables if delegables else 0
    print(f"Verde al PRIMER intento: {primera_verde}/{delegables} ({pct}%)"
          + (f"  [{len(imposibles)} imposible/s fuera del denominador]" if imposibles else ""))
    nunca_verde -= len(imposibles)
    if nunca_verde > 0:
        print(f"Nunca llegaron a verde: {nunca_verde}/{len(por_tarea)} "
              f"— las cerró un humano (regla: lo que falla dos veces no se insiste)")
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
# El encabezado tiene que nombrar TODAS las columnas que escribe el runner, o DictReader
# manda las de más a la clave None y las leemos vacías para siempre. Pasó con `motivo`: el
# bloque de abajo nunca imprimió nada mientras había datos de sobra. Un instrumento que lee
# por nombre tiene que verificar los nombres.
ESPERADO = ["fecha", "proyecto", "tarea", "veredicto", "segundos", "modelo", "motivo",
            "concurrencia", "instrumento"]
if campos != ESPERADO:
    print(f"⊘ el encabezado del registro no es el que escribe el runner: {campos}")
    print(f"  esperado: {ESPERADO} — las columnas que faltan se leen vacías, no ausentes")

if segs:
    # Una mediana de tiempos de corridas simultáneas describe la ocupación de la plataforma,
    # no la tarea: con PARALELAS=8 el mismo modelo pasa de 16,3 a 122 tok/s. Si las corridas
    # comparten ventana, el número no se muestra. Es la misma regla que SERIE=1 en
    # comparar-modelos.sh, que estaba arreglada de un lado y no del otro.
    # La columna `concurrencia` la escribe el runner al arrancar cada corrida. Antes esto
    # infería el solapamiento comparando timestamps a 60 s, que era un paliativo: dos corridas
    # pueden arrancar en el mismo segundo sin competir, y dos separadas por minutos pueden
    # solaparse si la primera duró mucho. El dato lo tiene quien corrió, no quien analiza.
    serie = [f for f in filas if (f.get("concurrencia") or "").isdigit()
             and int(f["concurrencia"]) <= 1 and (f.get("segundos") or "").isdigit()]
    sin_dato = [f for f in filas if not (f.get("concurrencia") or "").isdigit()]
    segs_serie = [int(f["segundos"]) for f in serie if int(f["segundos"]) > 0]
    if segs_serie:
        print(f"Tiempo por intento (sólo serializadas): mediana {statistics.median(segs_serie):.0f}s, "
              f"máximo {max(segs_serie)}s, sobre {len(segs_serie)} de {len(filas)} corridas")
    else:
        print(f"Tiempo por intento: — (0 de {len(filas)} corridas tienen concurrencia 1; "
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
