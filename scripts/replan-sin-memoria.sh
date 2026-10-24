#!/usr/bin/env bash
# Replanifica las contradicciones del preflight SIN el canal de memoria: un POST plano a
# /chat/completions por cada rojo, el script aplica la línea, y los jueces del método deciden.
#
# El canal de memoria queda afuera por decisión del dueño de la plataforma. Y los números lo
# acompañan: 7 corridas con sesión de memoria, 1 completó, cortes entre los 7 y los 13
# minutos; por POST plano, 11 a 14 segundos.
#
# Lo que NO cambia son los jueces: el chequeo que encontró el problema sigue siendo el que
# acepta el arreglo. Eso es lo que la literatura respalda —autocorrección contra un
# verificador externo, no consenso entre modelos— y es lo que el método ya tenía.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$AQUI/_comun.sh"
# El proyecto se UBICA, no se clava. La primera versión tenía el proyecto de ejemplo y la
# ruta de mi máquina escritos en dos variables: un script que dice «replanifica el preflight»
# y en realidad replanifica UN proyecto, en UNA casa. El resto del método usa
# `ubicar_proyecto` desde el primer día.
ubicar_proyecto
# La config del entorno NO pisa lo que ya venga seteado. Estaba al revés, y un script que
# sobrescribe la variable que le pasó quien lo llama no se puede apuntar a otra plataforma
# —ni medir: el primer test de este canal le pegó a la plataforma REAL con un id de juguete y
# recibió un 404—. Es parte de por qué este camino no tenía tests: era intestable por
# construcción, y lo intestable es lo que se rompe sin que nadie se entere.
cargar_entorno_colabhive
# Y el modelo sale de la CONFIG, no de un UUID escrito acá. Clavado, este script le pide a un
# id que puede no existir más —hoy mismo `GLM-4.7-Flash` está declarado y no desplegado— y el
# error que sale no habla del plan.
MODELO="${MODELO:-$(modelo_del_agente ejecutor)}"
[ -n "$MODELO" ] || { echo "✗ no pude saber qué modelo usa el ejecutor: pasá MODELO=<id>" >&2; exit 1; }
SALIDA="${SALIDA:-$RAIZ/../sin-memoria}"
mkdir -p "$SALIDA"

cd "$BASE"
ROJOS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1 | grep '✗' || true)"
[ -n "$ROJOS" ] || { echo "✓ el preflight no tiene rojos: nada que replanificar"; exit 0; }
TABLAS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" --tablas 2>/dev/null | tr '\n' ';')"
COLUMNAS="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" --columnas 2>/dev/null | tr '\n' ';')"
echo "▶ replanificando sin canal de memoria. Lo que el preflight encontró:"
printf '%s\n' "$ROJOS" | sed 's/^/     /'

CRIT_ANTES="$(cat tareas/*.md | grep -c '^- \[ \]' || true)"
TESTS_ANTES="$(grep -ohE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`[^|]*clase `[A-Za-z0-9_]+`' tareas/*.md | sort || true)"
# El respaldo va AFUERA del proyecto. Estaba adentro de `$BASE`, y si el script muere a
# mitad de camino eso queda como un directorio sin seguimiento en el tronco —lo mismo que hoy
# dejó 89 líneas de implementación ahí sin que nadie lo midiera—.
RESPALDO="$SALIDA/tareas-previo"
rm -rf "$RESPALDO"; cp -R tareas "$RESPALDO"
restaurar() { rm -rf tareas; cp -R "$RESPALDO" tareas; }

fallo=""
while IFS= read -r rojo; do
  [ -n "$rojo" ] || continue
  tid="$(printf '%s\n' "$rojo" | grep -oE '\bT[0-9]+[a-z]?\b' | head -1)"
  # DOS CLASES DE ROJO, no una. Este script nació para las tablas y desde el 2026-10-24 el
  # preflight también da rojos de COLUMNA. Sin esto decía «no pude ubicar archivo o tabla» y
  # el rojo se quedaba sin nadie que lo trate.
  #
  # Y el canal plano es el vehículo correcto para los dos: el router con arnés le pide
  # escribir al modelo del agente `arquitecto`, que está MEDIDO como el que no escribe
  # —«Qwen3.8-27B razonamiento 6/6 · replanificando NO llamó a write», en el encabezado del
  # relevo—. Hoy se vio otra vez: ante este mismo rojo se pasó el turno citando el prompt y
  # razonándolo frase por frase, llegó a la conclusión correcta («anuncios has categoria_id»)
  # y se le acabó antes de actuar. Por POST plano, el ejecutor devuelve la línea corregida en
  # segundos.
  tabla="$(printf '%s\n' "$rojo" | grep -oE 'tabla `[a-z_]+`' | head -1 | tr -d '`' | awk '{print $2}')"
  columna="$(printf '%s\n' "$rojo" | grep -oE 'columna `[a-z_]+`' | head -1 | tr -d '`' | awk '{print $2}')"
  arch="$(ls tareas/${tid}-*.md 2>/dev/null | head -1)"
  [ -n "$arch" ] || { fallo="${fallo:+$fallo; }$tid: no pude ubicar su archivo"; continue; }
  if [ -n "$tabla" ]; then
    QUE="tabla"; QUIEN="$tabla"
    ESQUEMA="Tablas que las migraciones YA crean: $TABLAS"
    SALIDAS="Elegís vos entre usar una tabla de la lista o que el enunciado prometa crear la que nombra."
  elif [ -n "$columna" ]; then
    QUE="columna"; QUIEN="$columna"
    ESQUEMA="Columnas que las migraciones YA crean, por tabla: $COLUMNAS"
    SALIDAS="Elegís vos entre usar una columna de esa lista o que el enunciado prometa agregar la que nombra con una migración."
  else
    fallo="${fallo:+$fallo; }$tid: el rojo no nombra tabla ni columna"; continue
  fi
  linea="$(grep -n "$QUE \`$QUIEN\`" "$arch" | head -1)"
  [ -n "$linea" ] || { fallo="${fallo:+$fallo; }$tid: no encontré la línea de \`$QUIEN\`"; continue; }
  printf '  · %s · %s `%s` · %s\n' "$tid" "$QUE" "$QUIEN" "$arch"
  t0=$(date +%s)
  printf '%s\n\n%s\n\nLínea del enunciado, tal cual:\n%s\n\nDevolvé SOLO esa línea corregida, COMPLETA y con el mismo prefijo que tiene: si empieza con \"- \" (es un item de lista) la tuya también. Sin número de línea, sin explicación, sin comillas de bloque. %s\n' \
    "$rojo" "$ESQUEMA" "${linea#*:}" "$SALIDAS" > "$SALIDA/in.txt"
  if ! PACIENCIA=400 python3 "$AQUI/pedir.py" "$MODELO" < "$SALIDA/in.txt" > "$SALIDA/out.txt" 2>"$SALIDA/err.txt"; then
    fallo="${fallo:+$fallo; }$tid: $(tr '\n' ' ' < "$SALIDA/err.txt" | cut -c1-60)"; continue
  fi
  # La extracción la hace `limpiar.py`, que es el único que sabe dónde termina el
  # razonamiento. Acá estaba copiada otra vez: cuarta copia de la misma regla.
  nueva="$(python3 "$AQUI/limpiar.py" --ultima-linea "$SALIDA/out.txt")"
  [ "$nueva" = "(vacío)" ] && nueva=""
  # La respuesta tiene que SER una línea de enunciado, no un comentario sobre ella.
  case "$nueva" in
    ""|*"</think>"*|DECISION:*|PORQUE:*) fallo="${fallo:+$fallo; }$tid: respuesta no utilizable"; continue ;;
  esac
  # EL PREFIJO DE LA LÍNEA NUEVA ES EXACTAMENTE EL DE LA VIEJA, ni más ni menos.
  #
  # Tres intentos fallaron antes de este, y los tres por motivos distintos:
  #   1. Sin guardia, el modelo COMIÓ el «- » de T28 y el item salió de la lista.
  #   2. Pidiéndoselo en el prompt, AGREGÓ un «- » a T26, que es un párrafo. Sobre-corrección.
  #   3. Normalizando con `sed`, no pasó nada: usé `\|` para alternancia, que anda en GNU sed
  #      y NO en el BSD sed de macOS. El mismo defecto de portabilidad que la suite ya vigila.
  # Por eso la normalización la hace python, que se comporta igual en las dos plataformas, y
  # el prefijo lo decide el ARCHIVO: el modelo aporta el contenido, nunca la forma.
  nueva="$(VIEJA="${linea#*:}" NUEVA="$nueva" python3 - <<'PYPRE'
import os, re
pat = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+|\s+)")
m = pat.match(os.environ["VIEJA"])
pre = m.group(1) if m else ""
cuerpo = pat.sub("", os.environ["NUEVA"], count=1).strip()
print(pre + cuerpo)
PYPRE
)"
  [ -n "$nueva" ] || { fallo="${fallo:+$fallo; }$tid: no pude normalizar el prefijo"; continue; }
  python3 - "$arch" "${linea%%:*}" "$nueva" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); n = int(sys.argv[2]); nueva = sys.argv[3]
ls = p.read_text().splitlines()
ls[n-1] = nueva
p.write_text("\n".join(ls) + "\n")
PY
  printf '    %3ds → %s\n' "$(( $(date +%s)-t0 ))" "$(printf '%s' "$nueva" | cut -c1-110)"
done <<ROJOS_FIN
$ROJOS
ROJOS_FIN
[ -n "$fallo" ] && echo "  ⚠ no todos los rojos se trataron: $fallo"

# ── Los jueces, iguales que en el camino con arnés.
mal=""
diff -rq "$RESPALDO" tareas >/dev/null 2>&1 && mal="el plan no cambió: no hubo replanificación"
CRIT_DESPUES="$(cat tareas/*.md | grep -c '^- \[ \]' || true)"
[ "${CRIT_DESPUES:-0}" -lt "${CRIT_ANTES:-0}" ] && mal="${mal:+$mal; }achicó criterios: de $CRIT_ANTES a $CRIT_DESPUES"
TESTS_DESPUES="$(grep -ohE '`[a-zA-Z0-9_/.]*tests?/[a-zA-Z0-9_.]+`[^|]*clase `[A-Za-z0-9_]+`' tareas/*.md | sort || true)"
[ "$TESTS_ANTES" != "$TESTS_DESPUES" ] && mal="${mal:+$mal; }cambió archivos o clases de test"
# EL JUEZ MIDE LO QUE EL ACTOR PUEDE HACER, y no más. Replanificar toca enunciados, así que
# se le exige que los rojos DE ENUNCIADO («TNN da por hecha la tabla») desaparezcan. Los rojos
# de CÓDIGO («el código consulta la tabla») no los puede arreglar: ésos salen de código ya
# commiteado y se corrigen corriendo la tarea.
#
# Primera versión exigía CERO rojos y descartó un arreglo correcto: las dos líneas quedaron
# bien en 3 segundos y el veredicto fue «se descarta» porque apareció el rojo de
# users_register.py, que el actor no podía tocar. Un juez que pide lo imposible reprueba al
# que hizo bien su parte, que es el defecto que este repo viene persiguiendo desde el día uno.
# El juez mide las dos clases de rojo de ENUNCIADO, que son las que este actor puede
# arreglar. Miraba sólo «da por hecha la tabla», así que un rojo de columna sin corregir
# pasaba por el juez sin que nadie lo notara: el chequeo que acepta el arreglo tiene que
# cubrir lo mismo que el que lo pidió.
ENUN_DESPUES="$(PROYECTO="$BASE" python3 "$AQUI/coherencia.py" 2>&1 | grep '✗' | grep -E 'da por hecha la tabla|nombra la columna' || true)"
[ -n "$ENUN_DESPUES" ] && mal="${mal:+$mal; }quedan contradicciones de ENUNCIADO: $(printf '%s' "$ENUN_DESPUES" | head -2 | tr '\n' ' ' | cut -c1-120)"
PLAN=PLAN.md python3 "$AQUI/validar-plan.py" >/dev/null 2>&1 || mal="${mal:+$mal; }el plan dejó de validar"

if [ -n "$mal" ]; then
  echo "  ✗ se descarta: $mal"; restaurar; exit 1
fi
echo "  ✓ el plan ya no se contradice y sigue validando"
diff -u "$RESPALDO" tareas | grep -E '^[+-][^+-]' | head -12 | sed 's/^/     /'
rm -rf "$RESPALDO"
