"""Punto de entrada: arma el juego y corre el loop.

    python3 -m src.pacman

Flechas o WASD para moverse, `q` para salir.
"""

import curses
import os
import time

from .entidades import ABAJO, ARRIBA, DERECHA, IZQUIERDA, Fantasma, Pacman
from .juego import Juego
from .laberinto import Laberinto
from .render import dibujar

MAPA = os.path.join(os.path.dirname(__file__), "..", "..", "mapas", "clasico.txt")
SEGUNDOS_POR_TICK = 0.15

TECLAS = {
    curses.KEY_UP: ARRIBA, curses.KEY_DOWN: ABAJO,
    curses.KEY_LEFT: IZQUIERDA, curses.KEY_RIGHT: DERECHA,
    ord("w"): ARRIBA, ord("s"): ABAJO, ord("a"): IZQUIERDA, ord("d"): DERECHA,
}


def armar():
    """Crea laberinto, juego, Pacman y fantasmas desde el mapa."""
    laberinto = Laberinto.desde_archivo(os.path.normpath(MAPA))
    juego = Juego(laberinto)
    pacman = Pacman(laberinto.inicio_pacman)
    fantasmas = [Fantasma(pos) for pos in laberinto.inicios_fantasmas]
    return juego, pacman, fantasmas


def un_tick(juego, pacman, fantasmas) -> None:
    """Avanza el juego un turno: mueve a todos y resuelve los encuentros.

    Se chequea la colisión dos veces —después de mover a Pacman y después de
    mover a los fantasmas— para que no se crucen sin tocarse.
    """
    pacman.mover(juego.laberinto)
    juego.comer_en(pacman.pos)
    if juego.colision(pacman.pos, fantasmas) == "perdio":
        return
    for fantasma in fantasmas:
        fantasma.mover(juego.laberinto, pacman.pos)
    juego.colision(pacman.pos, fantasmas)
    juego.tick()


def loop(pantalla) -> None:
    """Loop principal: lee el teclado, avanza el juego y dibuja."""
    curses.curs_set(0)
    pantalla.nodelay(True)
    pantalla.keypad(True)
    juego, pacman, fantasmas = armar()

    while not juego.terminado():
        tecla = pantalla.getch()
        if tecla in (ord("q"), 27):
            return
        if tecla in TECLAS:
            pacman.intentar_girar(TECLAS[tecla])
        un_tick(juego, pacman, fantasmas)
        dibujar(pantalla, juego, pacman, fantasmas)
        time.sleep(SEGUNDOS_POR_TICK)

    dibujar(pantalla, juego, pacman, fantasmas)
    pantalla.nodelay(False)
    alto, _ = pantalla.getmaxyx()
    pantalla.addstr(min(alto - 1, juego.laberinto.alto + 3),
                    0, f"{juego.resultado().upper()} — puntaje {juego.puntaje}. Tecla para salir.")
    pantalla.refresh()
    pantalla.getch()


def main() -> None:
    """Arranca curses y se asegura de restaurar la terminal al salir."""
    curses.wrapper(loop)


if __name__ == "__main__":
    main()
