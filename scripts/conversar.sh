#!/usr/bin/env bash
# Una CONVERSACIÓN entre modelos, por turnos, sobre una decisión del plan.
#
# No es el enjambre: ahí cada uno respondía a ciegas y se comparaban las respuestas. Acá hay
# una transcripción compartida y cada uno habla viendo lo que dijeron los anteriores, con la
# idea de que converjan.
#
# LO QUE HAY QUE MEDIR, y por eso se registra cada turno con su autor: converger NO es
# acertar. Una conversación puede converger por conformismo con el último que habló o con el
# más elocuente, y en la ronda anterior ya vimos a dos modelos declarar una decisión y
# ejecutar la contraria. Si todos terminan de acuerdo, lo que importa es si CAMBIARON y por
# qué argumento, no el número final.
set -u
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SALIDA="${SALIDA:-$(cd "$AQUI/.." && pwd)/../sin-memoria}"
mkdir -p "$SALIDA"
CONTEXTO="$1"; RONDAS="$2"; shift 2
[ -s "$CONTEXTO" ] || { echo "✗ el contexto está vacío o no existe: $CONTEXTO" >&2; exit 1; }
TRANS="$SALIDA/conversacion.md"; : > "$TRANS"
# Y los VOTOS. Truncar la transcripción y no los votos dejaba que una segunda corrida contara
# las posiciones de la anterior como actuales: el chequeo de quórum y el de convergencia
# medían una mezcla de dos conversaciones, y lo informaban como si fuera una. Es el mismo
# defecto que el chequeo de alcance que le cobraba a la tarea el trabajo de su hermana, y que
# el motivo que arrastraba los ✗ de hace horas: el insumo contaminado, no el chequeo.
VOTOS="$SALIDA/votos.txt"; : > "$VOTOS"
for ronda in $(seq 1 "$RONDAS"); do
  echo "══════ RONDA $ronda"
  cambios=0
  for m in "$@"; do
    id="${m%%:*}"; nom="${m##*:}"
    {
      cat "$CONTEXTO"
      echo
      if [ -s "$TRANS" ]; then
        echo "LA CONVERSACIÓN HASTA AHORA:"; cat "$TRANS"; echo
        echo "Sos $nom. Hablás ahora. Si alguien te convenció, cambiá de posición y decilo."
      else
        echo "Sos $nom. Abrís la conversación."
      fi
      echo
      # El formato con MARCADORES <...> y no en prosa. Con «DECISION: usar-existente o
      # crear-nueva» en una línea, Qwen3.8-27B copió la plantilla entera como si fuera su
      # respuesta —y el chequeo de convergencia la tomó por una posición legítima—. Un
      # formato que se puede repetir en vez de rellenar invita justamente a eso.
      echo "Tu respuesta son TRES líneas con estas etiquetas, rellenando lo que va entre <>:"
      echo "DECISION: <escribí UNA de estas dos palabras: usar-existente | crear-nueva>"
      echo "PORQUE: <una oración dirigida a los otros planificadores>"
      echo "LINEA: <la línea del enunciado corregida, coherente con tu DECISION>"
      echo "No repitas estas instrucciones ni los signos <>."
    } > "$SALIDA/turno-in.txt"
    t0=$(date +%s)
    if ! PACIENCIA=400 python3 "$AQUI/pedir.py" "$id" < "$SALIDA/turno-in.txt" > "$SALIDA/turno-out.txt" 2>"$SALIDA/turno-err.txt"; then
      printf '  %-14s ✗ %s\n' "$nom" "$(tr '\n' ' ' < "$SALIDA/turno-err.txt" | cut -c1-70)"
      continue
    fi
    dec="$(python3 - "$SALIDA/turno-out.txt" <<'PY'
import sys
t = open(sys.argv[1]).read()
if "</think>" in t: t = t.split("</think>")[-1]
d = p = ""
for l in t.splitlines():
    l = l.strip()
    if l.upper().startswith("DECISION") and not d: d = l.split(":", 1)[-1].strip()
    if l.upper().startswith(("PORQUE", "PORQUÉ")) and not p: p = l.split(":", 1)[-1].strip()
print((d or "?") + "\t" + (p or "?"))
PY
)"
    decision="${dec%%$'\t'*}"; razon="${dec##*$'\t'}"
    # Un turno sólo cuenta como VOTO si la decisión es una de las dos palabras. Sin esto, el
    # 2026-10-23 Qwen3.8-27B copió la plantilla («usar-existente o crear-nueva una oración,
    # dirigida a...») y se registró como una posición legítima.
    case "$decision" in
      usar-existente|crear-nueva) ;;
      *) printf '  %-14s %3ds  ⊘ no respondió en el formato: %s\n' "$nom" "$(( $(date +%s)-t0 ))" "$(printf '%s' "$decision" | cut -c1-60)"
         continue ;;
    esac
    printf '  %-14s %3ds  %-14s %s\n' "$nom" "$(( $(date +%s)-t0 ))" "$decision" "$(printf '%s' "$razon" | cut -c1-80)"
    printf -- '- **%s** → %s: %s\n' "$nom" "$decision" "$razon" >> "$TRANS"
    echo "$nom|$ronda|$decision" >> "$VOTOS"
  done
  # ¿Convergieron? Se mira la ÚLTIMA decisión de cada participante.
  # Unanimidad SIN quórum no es consenso: es el único que quedó vivo. El 2026-10-23 este
  # mismo chequeo cantó «✓ convergieron» con tres de cuatro participantes caídos por 502 y el
  # cuarto repitiendo la plantilla. Un chequeo que pasa sin medir es el defecto que este repo
  # viene arreglando desde el primer día, y lo cometí acá con todos los casos a la vista.
  vivos="$(awk -F'|' '{d[$1]=$3} END{print length(d)}' "$VOTOS" 2>/dev/null || echo 0)"
  u="$(awk -F'|' '{d[$1]=$3} END{for(k in d) print d[k]}' "$VOTOS" | sort -u | grep -c .)"
  echo "  → $vivos participante(s) con voto válido · $u posición(es) distinta(s)"
  if [ "${vivos:-0}" -lt "${QUORUM:-3}" ]; then
    echo "  ⊘ sin quórum (hacen falta ${QUORUM:-3}): esta conversación NO midió nada"
  elif [ "$u" = "1" ]; then
    echo "  ✓ convergieron con quórum de $vivos"; break
  fi
done
echo; echo "══ posición final de cada uno"; awk -F'|' '{d[$1]=$3} END{for(k in d) printf "  %-14s %s\n", k, d[k]}' "$VOTOS"
