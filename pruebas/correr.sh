#!/usr/bin/env bash
# La suite del método, corrida de modo que un fallo INTERMITENTE se pueda diagnosticar.
#
# Existe por un fallo que no pude diagnosticar. El 2026-10-26 corrí la suite cinco veces y una
# dio `FAILED (failures=1)`; el comando era de a mano y filtraba las líneas `^FAIL:`, así que
# del único fallo de la noche quedó el NOMBRE del test y nada más: ni el traceback, ni el
# mensaje de la aserción, ni la salida del gate que el test imprime en su mensaje. El test
# pasa 8/8 solo y 12/12 en paralelo, o sea que la evidencia perdida era la única que servía.
#
# Es la misma regla que el método le exige a los proyectos —«un rojo sin evidencia no es un
# veredicto»— aplicada al instrumento, que es donde no la estaba cumpliendo.
#
#   bash pruebas/correr.sh            una corrida
#   VECES=5 bash pruebas/correr.sh    cinco, para cazar lo intermitente; sigue tras un fallo
#
# Sale ≠0 si CUALQUIERA de las corridas falló, y deja cada salida COMPLETA en disco.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
VECES="${VECES:-1}"
# Si lo dan a mano, los registros son del que los pidió y no se tocan.
DONDE_DADO="${DONDE:-}"
DONDE="${DONDE:-$(mktemp -d)}"
# `mktemp -d` crea el directorio; una ruta dada a mano, no. Sin este mkdir el registro no
# se podía escribir y el corredor informaba «SIN VEREDICTO (¿se murió?)»: le echaba la
# culpa a la suite de lo que era suyo. Encontrado al probar el camino del fallo.
mkdir -p "$DONDE" || { echo "no puedo escribir los registros en $DONDE"; exit 1; }
FALLADAS=0

for n in $(seq 1 "$VECES"); do
  registro="$DONDE/corrida-$n.txt"
  inicio=$SECONDS
  python3 -m unittest pruebas.test_metodo -v >"$registro" 2>&1
  codigo=$?
  veredicto="$(grep -E '^(OK|FAILED)' "$registro" | tail -1)"
  echo "── corrida $n/$VECES — $((SECONDS - inicio))s — ${veredicto:-SIN VEREDICTO (¿se murió?)}"
  grep -E '^(Ran [0-9]+ tests)' "$registro" | tail -1 | sed 's/^/   /'

  # Las fugas las avisa `atexit`, no unittest: sin esto un huérfano no se ve.
  grep -n "quedaron SIN TIRAR" "$registro" | sed 's/^/   ⚠ /'

  if [ "$codigo" -ne 0 ] || [ -z "$veredicto" ]; then
    FALLADAS=$((FALLADAS + 1))
    # TODO el bloque de cada fallo: unittest lo separa con una línea de guiones o de iguales,
    # y el mensaje de estos tests trae la salida del gate, que es la evidencia de verdad.
    awk '/^(FAIL|ERROR): /{captura=1} captura' "$registro" | head -120 | sed 's/^/   │ /'
    echo "   registro completo: $registro"
  fi
done

echo
if [ "$FALLADAS" -eq 0 ]; then
  echo "VERDE — $VECES/$VECES"; [ -n "${DONDE_DADO:-}" ] || rm -rf "$DONDE"; exit 0
fi
echo "ROJO — $FALLADAS de $VECES corrida/s falló; los registros quedan en $DONDE"
exit 1
