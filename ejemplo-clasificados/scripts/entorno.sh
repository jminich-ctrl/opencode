#!/usr/bin/env bash
# Servicios que este proyecto necesita para que el gate verifique algo. Idempotente.
# Lo llama `$AGENTES/scripts/preparar-entorno.sh`; no hace falta correrlo a mano.
#
# Por qué es del proyecto y no del método: el método no sabe qué base de datos usa nadie.
# Lo que sí es del método es la regla — **un rojo que no pueda atribuirse al agente es un
# defecto nuestro** — y que el entorno se prepare antes de gastar una llamada al modelo.
#
# Deja las credenciales en `.entorno` (gitignorado), en formato `export`. El gate lo lee
# si está, así que los tests ven la base sin que nadie exporte nada a mano, y el código
# nunca tiene una credencial escrita adentro.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROY="$(cd "$AQUI/.." && pwd)"

PUERTO="${MYSQL_PORT:-33306}"
BASE_DATOS="${MYSQL_DB:-clasificados}"
# UNA BASE POR ÁRBOL, un solo servidor. El servidor y su datadir son del tronco —levantar un
# mysqld por worktree sería absurdo— pero la BASE no: hasta el 2026-10-25 todos los worktrees
# escribían en `clasificados` y nadie la limpiaba, así que el validador de tests, que corre el
# mismo test DOS VECES, chocaba en la segunda con la fila que insertó la primera:
#   pymysql.err.IntegrityError: (1062, "Duplicate entry 'test@example.com' for key 'usuarios.email'")
# y el veredicto se lo cobraba al test.
#
# Estas dos perillas son lo que permite aislarla sin levantar otro servidor: el método corre
# ESTE script desde el tronco —que es el que tiene el cliente y el datadir— y lo apunta al
# worktree. Por omisión las dos valen `$PROY`, así que una corrida sobre el tronco no cambia.
ENTORNO_DESTINO="${ENTORNO_DESTINO:-$PROY}"     # dónde se escribe `.entorno`
MIGRACIONES_DESDE="${MIGRACIONES_DESDE:-$PROY}" # de dónde salen las migraciones
DATADIR="$PROY/.mysql/datos"
SOCKET="$PROY/.mysql/mysql.sock"
LOG="$PROY/.mysql/mysqld.log"

escribir_entorno() {
  mkdir -p "$ENTORNO_DESTINO"
  cat > "$ENTORNO_DESTINO/.entorno" <<EOF
# Generado por scripts/entorno.sh. No lo edites a mano ni lo commitees.
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=$PUERTO
export MYSQL_USER=root
export MYSQL_PASSWORD=
export MYSQL_DB=$BASE_DATOS
export MYSQL_SOCKET=$SOCKET
EOF
}

aplicar_migraciones() {
  # Las migraciones salen del ÁRBOL QUE SE PREPARA, no del tronco: con una base por worktree,
  # las migraciones del worktree son las que corresponden a esa base. Una tarea que agrega una
  # migración la necesita aplicada para que su test pase.
  local dir="$MIGRACIONES_DESDE/backend/migraciones" f nombre
  [ -d "$dir" ] || return 0
  ls "$dir"/*.sql >/dev/null 2>&1 || return 0
  mysql --no-defaults --default-character-set=utf8mb4 --protocol=TCP \
        -h 127.0.0.1 -P "$PUERTO" -u root "$BASE_DATOS" \
        -e "CREATE TABLE IF NOT EXISTS _migraciones (nombre VARCHAR(255) PRIMARY KEY,
             aplicada_en DATETIME DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB" 2>/dev/null
  for f in "$dir"/*.sql; do
    nombre="$(basename "$f")"
    case "$nombre" in *_down.sql) continue ;; esac   # la reversa no se aplica sola
    if mysql --no-defaults --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root "$BASE_DATOS" \
             -N -B -e "SELECT 1 FROM _migraciones WHERE nombre='$nombre'" 2>/dev/null | grep -q 1
    then continue; fi
    echo "· aplicando migración $nombre"
    # Sin pipe: `if cmd | head; then` prueba el estado de `head`, que sale 0 siempre, así
    # que una migración fallida quedaba registrada como aplicada. Verificado:
    #   $ if false | head -3; then echo "dio verdadero"; fi  → dio verdadero
    SALIDA_MIG="$(mysql --no-defaults --default-character-set=utf8mb4 --protocol=TCP \
                        -h 127.0.0.1 -P "$PUERTO" -u root "$BASE_DATOS" < "$f" 2>&1)"
    if [ $? -eq 0 ]; then
      mysql --no-defaults --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root "$BASE_DATOS" \
            -e "INSERT INTO _migraciones (nombre) VALUES ('$nombre')" 2>/dev/null
    else
      echo "✗ la migración $nombre falló: el esquema queda incompleto y el gate lo va a decir"
      echo "$SALIDA_MIG" | head -5 | sed 's/^/     /'
      return 1
    fi
  done
}

vivo() { mysqladmin --no-defaults --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root ping >/dev/null 2>&1; }

# ¿Este proyecto ya necesita la base? Mientras no haya capa de datos no hay nada que
# conectar, y exigir el servidor pararía las etapas de andamiaje por una razón que todavía
# no existe. La condición es la que se puede verificar: si hay código en `datos/`, hace falta.
# Un `__init__.py` vacío no usa la base: lo crea el andamiaje. La condición es que haya
# un módulo de datos de verdad, o una migración.
HACE_FALTA=0
for f in "$PROY"/backend/app/datos/*.py; do
  case "$f" in */__init__.py|*'*.py') continue ;; esac
  [ -s "$f" ] && HACE_FALTA=1
done
for f in "$PROY"/backend/migraciones/*.sql; do [ -s "$f" ] && HACE_FALTA=1; done

aviso_o_falla() {
  if [ "$HACE_FALTA" = "1" ]; then
    echo "   Hay código que usa la base, así que esto para la etapa. Es correcto que pare:"
    echo "   un test de base de datos que pasa sin base no verifica nada."
    exit 1
  fi
  echo "   Todavía no hay capa de datos ni migraciones, así que seguimos sin la base."
  echo "   Cuando T03 o las tareas de datos entren, esto va a parar la corrida hasta que se arregle."
  exit 0
}

# El cliente, antes de cualquier uso: el del proyecto si está, el del sistema si no. Mezclar
# un cliente del sistema con un servidor propio es cómo aparecen errores de protocolo.
if [ -x "$PROY/.mysql/dist/bin/mysql" ]; then PATH="$PROY/.mysql/dist/bin:$PATH"; fi

# ── `--tirar`: la base de un worktree se va con el worktree.
#
# Es del PROYECTO y no del método, por la misma razón que todo lo demás de este archivo: el
# método no sabe qué base de datos usa nadie, ni dónde está el cliente. Lo que el método hace
# es llamar a esto antes de borrar un worktree.
#
# NO se tira la base del tronco: ésa es la del proyecto, la que el humano mira entre corridas,
# y un `--tirar` mal invocado no puede llevársela. Por eso se exige que el nombre no sea el
# de por omisión.
if [ "${1:-}" = "--tirar" ]; then
  if [ "$BASE_DATOS" = "clasificados" ]; then
    echo "✗ me pedís tirar la base del tronco (\`clasificados\`). No lo hago." >&2
    echo "   Pasá MYSQL_DB con la base del worktree." >&2
    exit 1
  fi
  if ! vivo; then
    echo "· el servidor no está arriba: no hay base que tirar"
    exit 0
  fi
  mysql --no-defaults --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root \
        -e "DROP DATABASE IF EXISTS \`$BASE_DATOS\`" >/dev/null 2>&1 \
    && echo "· base \`$BASE_DATOS\` tirada" \
    || { echo "⚠ no pude tirar \`$BASE_DATOS\`: queda ocupando espacio en el servidor" >&2; exit 1; }
  exit 0
fi

if vivo; then
  mysql --no-defaults --default-character-set=utf8mb4 --protocol=TCP \
        -h 127.0.0.1 -P "$PUERTO" -u root \
        -e "CREATE DATABASE IF NOT EXISTS \`$BASE_DATOS\` CHARACTER SET utf8mb4" >/dev/null 2>&1
  escribir_entorno
  echo "· MySQL del proyecto ya está arriba en 127.0.0.1:$PUERTO"
  # Y las migraciones TAMBIÉN acá: ésta es la rama normal —el servidor queda levantado
  # entre etapas— y salía antes de llegar a aplicarlas, así que el esquema no se creaba
  # nunca por el método. Las tablas existían por accidente, creadas por algún agente.
  aplicar_migraciones || exit 1
  exit 0
fi

# El servidor tiene que poder arrancar. Si el binario está roto —acá lo estaba, por un
# icu4c que una actualización de brew se llevó— no lo arreglamos nosotros: tocar el MySQL
# del sistema es una decisión de la persona dueña de la máquina, no del runner.
# Qué mysqld usamos. Orden: el propio del proyecto si ya está, el del sistema si arranca,
# y si no, nos traemos uno. El del sistema puede estar instalado y **no arrancar** —acá una
# actualización de brew se llevó el icu4c que linkea mysql 8.0.30— y arreglarlo pide
# actualizar las Command Line Tools, que es `sudo` y no es decisión del runner.
DIST="$PROY/.mysql/dist"
MYSQLD=""
if [ -x "$DIST/bin/mysqld" ] && "$DIST/bin/mysqld" --version >/dev/null 2>&1; then
  MYSQLD="$DIST/bin/mysqld"
elif command -v mysqld >/dev/null 2>&1 && VER="$(mysqld --version 2>&1)"; then
  MYSQLD="$(command -v mysqld)"
else
  if command -v mysqld >/dev/null 2>&1; then
    echo "· el mysqld del sistema está instalado y no arranca:"
    echo "${VER:-}" | head -2 | sed 's/^/     /'
  else
    echo "· no hay mysqld en el sistema"
  fi
  # Versión fija y con checksum: un servidor que cambia de versión solo es un servidor que
  # puede romper la corrida de mañana sin que nadie haya tocado nada.
  TARBALL="mysql-8.0.39-macos14-$(uname -m).tar.gz"
  URL="https://cdn.mysql.com/archives/mysql-8.0/$TARBALL"
  echo "· bajando MySQL propio del proyecto a .mysql/dist (no instala nada en el sistema)"
  echo "    $URL"
  mkdir -p "$PROY/.mysql"
  if ! curl -fsSL -o "$PROY/.mysql/$TARBALL" "$URL"; then
    echo "⊘ no pude bajar $TARBALL."
    echo "   Decide una persona: arreglar el mysqld del sistema o cambiar el encargo."
    aviso_o_falla
  fi
  rm -rf "$DIST"; mkdir -p "$DIST"
  tar -xzf "$PROY/.mysql/$TARBALL" -C "$DIST" --strip-components=1 \
    || { echo "✗ el tarball no se pudo descomprimir"; aviso_o_falla; }
  rm -f "$PROY/.mysql/$TARBALL"
  if ! "$DIST/bin/mysqld" --version >/dev/null 2>&1; then
    echo "⊘ el mysqld que bajamos tampoco arranca:"
    "$DIST/bin/mysqld" --version 2>&1 | head -3 | sed 's/^/     /'
    aviso_o_falla
  fi
  MYSQLD="$DIST/bin/mysqld"
  echo "· MySQL propio listo: $("$MYSQLD" --version | sed 's/.*Ver //;s/ for .*//')"
fi

# Los clientes (mysql, mysqladmin) salen del mismo lugar que el servidor: mezclar un
# cliente del sistema con un servidor propio es cómo aparecen errores de protocolo.
BIN="$(dirname "$MYSQLD")"
PATH="$BIN:$PATH"

mkdir -p "$PROY/.mysql"
if [ ! -d "$DATADIR/mysql" ]; then
  echo "· inicializando una instancia de MySQL propia del proyecto en .mysql/"
  "$MYSQLD" --no-defaults --initialize-insecure --datadir="$DATADIR" --log-error="$LOG" >/dev/null 2>&1 \
    || { echo "✗ no pude inicializar el datadir; mirá $LOG"; exit 1; }
fi

echo "· levantando MySQL del proyecto en 127.0.0.1:$PUERTO"
nohup "$MYSQLD" --no-defaults --datadir="$DATADIR" --port="$PUERTO" --socket="$SOCKET" \
       --log-error="$LOG" --skip-mysqlx --bind-address=127.0.0.1 >/dev/null 2>&1 &
disown 2>/dev/null || true
for _ in $(seq 1 40); do vivo && break; sleep 1; done
if ! vivo; then
  echo "✗ MySQL no respondió en 40s. Últimas líneas de $LOG:"
  tail -10 "$LOG" 2>/dev/null | sed 's/^/     /'
  exit 1
fi
mysql --no-defaults --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root \
      -e "CREATE DATABASE IF NOT EXISTS \`$BASE_DATOS\` CHARACTER SET utf8mb4" >/dev/null 2>&1
escribir_entorno
echo "· base \`$BASE_DATOS\` lista; credenciales en .entorno"

# ── Las migraciones. Aplicarlas es del método, no de la tarea: el esquema tiene que existir
# para que un test de datos verifique algo, y ninguna tarea del plan lo tiene asignado —T03
# escribe el `.sql` y nadie lo corre—. Fue el cuarto hueco de la misma forma: pasó que el
# endpoint de login devolvía 500 en vez de 401 porque la tabla `usuarios` no existía, y el
# método lo informaba como "el test no pasa ni con la implementación del propio agente".
#
# Se lleva registro en `_migraciones` para no reaplicar: los `.sql` del plan usan
# `CREATE TABLE` sin `IF NOT EXISTS` —y está bien que así sea, una migración se aplica una
# vez— así que reaplicar a ciegas sería un error disfrazado de idempotencia.
aplicar_migraciones || exit 1
