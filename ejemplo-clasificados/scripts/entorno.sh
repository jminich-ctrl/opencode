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

vivo() { mysqladmin --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root ping >/dev/null 2>&1; }

# ¿Este proyecto ya necesita la base? Mientras no haya capa de datos no hay nada que
# conectar, y exigir el servidor pararía las etapas de andamiaje por una razón que todavía
# no existe. La condición es la que se puede verificar: si hay código en `datos/`, hace falta.
HACE_FALTA=0
ls "$PROY"/backend/app/datos/*.py >/dev/null 2>&1 && HACE_FALTA=1
ls "$PROY"/backend/migraciones/*.sql >/dev/null 2>&1 && HACE_FALTA=1

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
  mysql --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root \
        -e "CREATE DATABASE IF NOT EXISTS \`$BASE_DATOS\` CHARACTER SET utf8mb4" >/dev/null 2>&1
  escribir_entorno
  echo "· MySQL del proyecto ya está arriba en 127.0.0.1:$PUERTO"
  exit 0
fi

# El servidor tiene que poder arrancar. Si el binario está roto —acá lo estaba, por un
# icu4c que una actualización de brew se llevó— no lo arreglamos nosotros: tocar el MySQL
# del sistema es una decisión de la persona dueña de la máquina, no del runner.
if ! command -v mysqld >/dev/null 2>&1; then
  echo "⊘ no hay mysqld y OBJETIVO.md pide MySQL 8."
  echo "   Decide una persona: instalarlo (brew install mysql) o cambiar el encargo."
  aviso_o_falla
fi
# `mysqld --version` en un subshell con la salida capturada: si el binario aborta por una
# biblioteca que falta, el mensaje de dyld es lo único que explica qué pasó.
if ! VER="$(mysqld --version 2>&1)"; then
  echo "⊘ mysqld está instalado pero no arranca:"
  echo "$VER" | head -3 | sed 's/^/     /'
  echo "   Es el MySQL del sistema, no del proyecto: arreglarlo es una decisión tuya."
  echo "   Lo más probable: brew reinstall mysql"
  aviso_o_falla
fi

mkdir -p "$PROY/.mysql"
if [ ! -d "$DATADIR/mysql" ]; then
  echo "· inicializando una instancia de MySQL propia del proyecto en .mysql/"
  mysqld --initialize-insecure --datadir="$DATADIR" --log-error="$LOG" >/dev/null 2>&1 \
    || { echo "✗ no pude inicializar el datadir; mirá $LOG"; exit 1; }
fi

echo "· levantando MySQL del proyecto en 127.0.0.1:$PUERTO"
mysqld --datadir="$DATADIR" --port="$PUERTO" --socket="$SOCKET" \
       --log-error="$LOG" --skip-mysqlx --bind-address=127.0.0.1 >/dev/null 2>&1 &
for _ in $(seq 1 40); do vivo && break; sleep 1; done
if ! vivo; then
  echo "✗ MySQL no respondió en 40s. Últimas líneas de $LOG:"
  tail -10 "$LOG" 2>/dev/null | sed 's/^/     /'
  exit 1
fi
mysql --protocol=TCP -h 127.0.0.1 -P "$PUERTO" -u root \
      -e "CREATE DATABASE IF NOT EXISTS \`$BASE_DATOS\` CHARACTER SET utf8mb4" >/dev/null 2>&1
escribir_entorno
echo "· base \`$BASE_DATOS\` lista; credenciales en .entorno"
