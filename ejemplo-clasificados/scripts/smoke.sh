#!/usr/bin/env bash
# Smoke de arranque: que la aplicación LEVANTE y conteste. Es el paso 6 de G4.
#
#   bash scripts/smoke.sh
#
# **Los códigos son contrato**, y nada fuera de él sale de acá:
#
#   0  arrancó y contestó
#   1  no arrancó, o arrancó y no contestó lo que tenía que contestar
#   3  este proyecto DECLARA que no tiene nada que levantar (una librería, por ejemplo)
#
# El 3 existe para que «no hay nada que levantar» se pueda DECIR en vez de dejar G4 en rojo
# para siempre o —peor— borrar el paso. Un proyecto sin arranque es legítimo; un G4 que da
# verde salteándose el chequeo que más atrapa, no. Lo medimos el 2026-10-26: una librería JS
# no podía pasar G4 de ninguna forma honesta, y el método no reparte esta plantilla, así que
# el paso exigía un archivo que nadie tenía de dónde copiar.
#
# POR QUÉ ESTE PASO. Es el que más rinde: los tests unitarios no ven el arranque, y el bug
# vive en el cableado y la configuración. El Pacman crasheaba al arrancar con 70 tests verdes.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1

# Este proyecto SÍ tiene algo que levantar: la API. (ADAPTAR 1 del original), poné el motivo acá y listo. Un motivo
# vacío significa que SÍ hay algo que levantar y que lo de abajo está adaptado.
SIN_ARRANQUE=""
if [ -n "$SIN_ARRANQUE" ]; then
  echo "  ⊘ este proyecto no tiene nada que levantar: $SIN_ARRANQUE"
  exit 3
fi

# ADAPTAR 2: cómo se levanta, dónde contesta, y qué tiene que contestar.
ARRANQUE="PYTHONPATH=\"$PWD\" .venv/bin/python -m uvicorn backend.app.main:app --port 8099"
# `/openapi.json` y no `/health`: esta app no tiene un endpoint de salud, y agregárselo sería
# que el método le toque el producto —`backend/app/main.py` es de una tarea cerrada—. Lo que
# importa acá es que la app ARRANQUE y sirva, y eso lo prueba igual: FastAPI publica el
# esquema sólo si la aplicación se construyó, con sus routers montados por importlib.
URL="http://127.0.0.1:8099/openapi.json"
ESPERADO="openapi"
PACIENCIA="${PACIENCIA:-20}"        # segundos para que levante

"$SHELL" -c "$ARRANQUE" >/tmp/smoke.$$.log 2>&1 &
PID=$!
# Matar el árbol, no sólo el proceso: un servidor que forkea deja el puerto tomado y la
# próxima corrida falla por una razón que no es la suya.
limpiar() { kill -TERM -"$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null; wait "$PID" 2>/dev/null; }
trap limpiar EXIT

i=0
while [ "$i" -lt "$PACIENCIA" ]; do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "  ✗ el proceso se murió al arrancar:"
    tail -15 "/tmp/smoke.$$.log" | sed 's/^/     /'
    rm -f "/tmp/smoke.$$.log"; exit 1
  fi
  RESPUESTA="$(curl -fsS -m 2 "$URL" 2>/dev/null)" && break
  i=$((i+1)); sleep 1
done

if [ "$i" -ge "$PACIENCIA" ]; then
  echo "  ✗ levantó el proceso pero no contestó en ${PACIENCIA}s en $URL"
  tail -15 "/tmp/smoke.$$.log" | sed 's/^/     /'
  rm -f "/tmp/smoke.$$.log"; exit 1
fi

rm -f "/tmp/smoke.$$.log"
case "$RESPUESTA" in
  *"$ESPERADO"*) echo "  · arrancó en ${i}s y $URL contestó con «${ESPERADO}»"; exit 0 ;;
  *) echo "  ✗ contestó, pero no lo esperado. Esperaba «${ESPERADO}» y vino:"
     printf '%s\n' "$RESPUESTA" | head -5 | sed 's/^/     /'; exit 1 ;;
esac
