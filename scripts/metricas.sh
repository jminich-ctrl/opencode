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
filas = [f for f in csv.DictReader(open(os.environ["REGISTRO"]))
         if f["proyecto"] == proyecto]
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
segs = [int(f["segundos"]) for f in filas if f["segundos"].isdigit()]
print(f"Intentos: {total_int}   ·   tareas intentadas: {len(por_tarea)}")
if por_tarea:
    # El denominador son TODAS las tareas intentadas, no solo las que llegaron a verde:
    # contar solo las exitosas es sesgo de supervivencia y da números lindos y falsos.
    pct = primera_verde * 100 // len(por_tarea)
    print(f"Verde al PRIMER intento: {primera_verde}/{len(por_tarea)} ({pct}%)")
    if nunca_verde:
        print(f"Nunca llegaron a verde: {nunca_verde}/{len(por_tarea)} "
              f"— las cerró un humano (regla: lo que falla dos veces no se insiste)")
    if pct >= 60:   print("→ ≥60%: la descomposición funciona.")
    elif pct >= 30: print("→ 30-60%: tareas demasiado grandes o criterios flojos.")
    else:           print("→ <30%: el problema está en el plan, no en el modelo.")
if errores:
    print(f"Intentos perdidos por errores de plataforma: {errores} "
          f"({errores * 100 // total_int}%) — no cuentan contra el modelo")
if segs:
    print(f"Tiempo por intento: mediana {statistics.median(segs):.0f}s, "
          f"máximo {max(segs)}s, total {sum(segs) // 60} min")
modelos = collections.Counter(f["modelo"] for f in filas if f["modelo"])
if modelos:
    print("Modelos usados: " + ", ".join(f"{m} ({n})" for m, n in modelos.items()))
PY
