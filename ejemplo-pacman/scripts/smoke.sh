#!/usr/bin/env bash
# Smoke de arranque: levanta el juego de verdad, en una terminal falsa (pty),
# le manda 'q' y verifica que salga limpio.
#
# Los tests unitarios no cubren esto: el bug vive en el arranque y el cableado.
# Este chequeo habría atrapado los cuatro que encontramos jugando.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

python3 - <<'PY'
import os, pty, select, signal, sys, time

SEGUNDOS = 6
pid, fd = pty.fork()
if pid == 0:                                   # hijo: el juego, con una tty de verdad
    os.environ["TERM"] = "xterm"
    os.execvp("python3", ["python3", "-m", "src.pacman"])

salida = b""
t0 = time.time()
os.write(fd, b"d")                             # que se mueva un poco
while time.time() - t0 < SEGUNDOS:
    if select.select([fd], [], [], 0.2)[0]:
        try:
            trozo = os.read(fd, 4096)
        except OSError:
            break
        if not trozo:
            break
        salida += trozo
    if time.time() - t0 > SEGUNDOS / 2:
        os.write(fd, b"q")                     # y que salga
        break

time.sleep(0.5)
try:
    os.write(fd, b"q")
except OSError:
    pass
pid_fin, estado = os.waitpid(pid, os.WNOHANG)
if pid_fin == 0:                               # sigue vivo: lo bajamos
    os.kill(pid, signal.SIGTERM)
    time.sleep(0.3)
    pid_fin, estado = os.waitpid(pid, os.WNOHANG)

texto = salida.decode("utf-8", "replace")
if "Traceback" in texto or "Error" in texto:
    print("     el juego imprimió un error al arrancar:")
    for linea in texto.splitlines():
        if "Error" in linea or "line " in linea:
            print("     " + linea.strip()[:100])
    sys.exit(1)
if "Puntaje" not in texto:
    print("     el juego arrancó pero no dibujó el tablero (sin 'Puntaje' en la salida)")
    sys.exit(1)
print(f"     arrancó, dibujó el tablero y aceptó teclas ({len(salida)} bytes de salida)")
PY
