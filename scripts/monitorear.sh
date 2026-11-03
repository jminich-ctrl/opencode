#!/usr/bin/env bash
# El estado de una corrida larga, en un bloque que se lee en diez segundos.
#
# Por qué vive ACÁ y no en el scratchpad: el 2026-10-30 el monitoreo dejó de funcionar porque
# su script había desaparecido de `/private/tmp` —quedó el log y nada más—. La lección estaba
# escrita dos días antes, en la investigación: lo que vive en tmp no es durable. La apliqué al
# dataset y no a mis propias herramientas. Es el mismo movimiento que ya hizo el vigilante.
#
#   bash $AGENTES/scripts/monitorear.sh
#
# Contesta, en este orden y siempre las mismas preguntas:
#   · ¿hay corrida activa? (si la hay, NO se editan scripts ni se commitea)
#   · ¿cómo están las réplicas ANTES de sondear? `warm=0` significa que la plataforma no las
#     repuso, y eso no se puede ver DESPUÉS de la sonda porque la sonda misma las calienta.
#   · ¿la plataforma contesta, y con qué forma de respuesta?
#   · ¿hay deriva entre el contexto DECLARADO en la config y el que la réplica sirve?
#   · estado del tronco, worktrees y disco.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
# El entorno se carga con la función del método, NO con un `source` a mano. Es la regla que
# `_comun.sh` documenta y que la suite de este repo hace cumplir: siete scripts tenían ese
# `source` copiado y pisaba el `COLABHIVE_BASE_URL` que les pasaba quien los llamaba, así que
# ninguno de los siete se podía apuntar a otra plataforma ni medir. Lo volví a escribir acá y
# la suite me lo rechazó en el mismo commit en que el monitoreo entra al repo.
. "$AQUI/_comun.sh" 2>/dev/null || true
cargar_entorno_colabhive 2>/dev/null || true
BUILDER="${COLABHIVE_BUILDER_URL:-${COLABHIVE_BASE_URL%/v1}}"
UMBRAL_DISCO="${UMBRAL_DISCO:-2}"

echo "══ $(date '+%Y-%m-%d %H:%M:%S')"

# ── 1. corrida activa ──────────────────────────────────────────────────────────────────────
VIVOS="$(pgrep -fl "scripts/correr-todo.sh|opencode run|unittest pruebas.test_metodo" 2>/dev/null | grep -v monitorear || true)"
if [ -n "$VIVOS" ]; then
  echo "▶ ACTIVO ($(printf '%s\n' "$VIVOS" | grep -c .) proceso/s) — no editar scripts ni commitear"
  printf '%s\n' "$VIVOS" | head -4 | cut -c1-108 | sed 's/^/    /'
else
  echo "· sin corrida activa"
fi

# ── 2. réplicas ANTES de la sonda ──────────────────────────────────────────────────────────
# El orden importa: sondear calienta, así que preguntar después mostraría todo en verde y
# ocultaría justo lo que se quiere saber.
echo "· réplicas (antes de sondear):"
if [ -z "${COLABHIVE_API_KEY:-}" ] || [ -z "$BUILDER" ]; then
  echo "    ⊘ sin credenciales en el entorno: NO se consultó. No es un pase."
else
  printf 'X-API-Key: %s\n' "$COLABHIVE_API_KEY" \
    | curl -sS -m 45 -H @- "$BUILDER/inference/models?include_readiness=true" 2>/dev/null \
    | python3 "$AQUI/_monitor_replicas.py" "$RAIZ"; RC_REP=$?
  # Sólo el 2 es «no pude leer»: el 1 significa que leyó y hay réplicas frías, y eso ya lo
  # informó con su propio detalle. Confundirlos imprimía «no se pudo leer» sobre una lectura
  # correcta.
  [ "${RC_REP:-0}" = "2" ] && echo "    ⊘ la consulta de réplicas no se pudo verificar"
fi

# ── 3. ¿contesta, y con qué forma? ─────────────────────────────────────────────────────────
echo "· plataforma:"
if [ -z "${COLABHIVE_API_KEY:-}" ]; then
  echo "    ⊘ sin clave: no se sondeó"
elif plataforma_responde_la_corrida >/dev/null 2>&1; then
  echo "    ✓ contesta (y la sonda dejó la réplica caliente)"
else
  echo "    ✗ NO contesta como la corrida la necesita — ver colabhive/scripts/warm.sh"
fi

# ── 4. deriva de contextos ─────────────────────────────────────────────────────────────────
echo "· contextos declarado → servido:"
if [ -f "$RAIZ/colabhive/scripts/sync_limits.py" ] && [ -n "${COLABHIVE_API_KEY:-}" ]; then
  python3 "$RAIZ/colabhive/scripts/sync_limits.py" --dry-run 2>/dev/null \
    | grep -E "=|≠|→|⚠" | head -8 | sed 's/^/    /' \
    || echo "    ⊘ sync_limits no pudo leer: NO se verificó"
else
  echo "    ⊘ falta sync_limits.py o la clave: NO se verificó"
fi

# ── 5. tronco, worktrees y disco ───────────────────────────────────────────────────────────
SIN="$(git -C "$RAIZ" status --porcelain 2>/dev/null | grep -c . || true)"
echo "· tronco: ${SIN:-?} archivo/s sin commitear · $(git -C "$RAIZ" log --oneline -1 2>/dev/null | cut -c1-72)"
echo "· worktrees: $(git -C "$RAIZ" worktree list 2>/dev/null | grep -c . || echo '?') · disco libre: $(df -h / | awk 'NR==2{print $4}')"
LIBRE_G="$(df -g / | awk 'NR==2{print $4}')"
case "$LIBRE_G" in ''|*[!0-9]*) : ;; *)
  [ "$LIBRE_G" -lt "$UMBRAL_DISCO" ] && echo "  ■ disco por debajo del acuerdo de ${UMBRAL_DISCO}Gi: parar corridas y avisar" ;;
esac
# ── y DE QUÉ se está llenando, porque «quedan 238 Mi» llega tarde ──
#
# El 2026-11-02 una campaña murió con ENOSPC y el monitoreo anterior había dicho «14Gi
# libres» hacía dos horas. Lo que se lo comió: 1621 dylib anónimos de 4,8 MB en el temporal
# del usuario, 7,28 GB, que deja el toolchain cada vez que corre la suite —ninguno abierto
# por un proceso, todos regenerables—. Al ritmo medido (Oct 27 a Nov 2) son ~1,3 GB por día
# de corridas, o sea que el disco se vuelve a llenar en menos de una semana.
#
# Un umbral solo avisa cuando ya no hay margen para decidir. Esto avisa mientras lo hay, y
# dice qué borrar: es la diferencia entre «parar corridas» y «borrar basura del toolchain».
TMPU="$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null)"
if [ -n "$TMPU" ] && [ -d "$TMPU" ]; then
  FUGA_N="$(find "$TMPU" -maxdepth 1 -type f -name '.*-00000000.dylib' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "${FUGA_N:-0}" -gt 0 ]; then
    FUGA_M="$(find "$TMPU" -maxdepth 1 -type f -name '.*-00000000.dylib' -exec du -ck {} + 2>/dev/null \
              | tail -1 | awk '{printf "%.1f", $1/1024}')"
    echo "· fuga del toolchain: $FUGA_N dylib anónimo/s en el temporal = ${FUGA_M:-?} MB"
    [ "${FUGA_N:-0}" -gt 300 ] && echo "  ■ ya son muchos; se borran sin riesgo (ninguno queda abierto):" \
      && echo "     find \"$TMPU\" -maxdepth 1 -type f -name '.*-00000000.dylib' ! -newermt \"\$(date +%F)\" -delete"
  fi
fi
echo "· NO FRENAR — el monitoreo no reemplaza el trabajo. Si hay algo trabado, se arregla."
