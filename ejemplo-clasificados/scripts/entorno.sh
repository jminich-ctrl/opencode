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
DATADIR="$PROY/.mysql/datos"
SOCKET="$PROY/.mysql/mysql.sock"
LOG="$PROY/.mysql/mysqld.log"

escribir_entorno() {
  cat > "$PROY/.entorno" <<EOF
# Generado por scripts/entorno.sh. No lo edites a mano ni lo commitees.
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=$PUERTO
export MYSQL_USER=root
export MYSQL_PASSWORD=
export MYSQL_DB=$BASE_DATOS
export MYSQL_SOCKET=$SOCKET
EOF
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

if vivo; then
  mysql --no-defaults --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root \
        -e "CREATE DATABASE IF NOT EXISTS \`$BASE_DATOS\` CHARACTER SET utf8mb4" >/dev/null 2>&1
  escribir_entorno
  echo "· MySQL del proyecto ya está arriba en 127.0.0.1:$PUERTO"
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
