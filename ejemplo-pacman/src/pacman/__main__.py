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
TIEMPO_DE_ESPERA_POR_ITERACION = 0.02  # 20 ms por iteración
TICKS_ASUSTADO = 20  # Para mantener consistencia

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
    # Un estilo por fantasma, en orden: si hay más de cuatro, se repiten.
    estilos = ["perseguidor", "emboscador", "timido", "errante"]
    fantasmas = [Fantasma(pos, estilo=estilos[i % len(estilos)])
                 for i, pos in enumerate(laberinto.inicios_fantasmas)]
    return juego, pacman, fantasmas


def un_tick(juego, pacman, fantasmas) -> None:
    """Avanza el juego un turno: mueve a todos y resuelve los encuentros.

    Se chequea la colisión dos veces —después de mover a Pacman y después de
    mover a los fantasmas— para que no se crucen sin tocarse.
    """
    previa_pacman = pacman.pos
    pacman.mover(juego.laberinto)
    juego.comer_en(pacman.pos)
    if juego.colision(pacman.pos, fantasmas, previa_pacman,
                      {id(f): f.pos for f in fantasmas}) == "perdio":
        return

    # Asustados se mueven la mitad de rápido: solo en los turnos pares.
    if not juego.asustados or juego.asustado_restante % 2 == 0:
        previas = {id(f): f.pos for f in fantasmas}
        for fantasma in fantasmas:
            fantasma.mover(juego.laberinto, pacman.pos,
                           direccion_pacman=pacman.direccion,
                           asustado=juego.asustados)
        juego.colision(pacman.pos, fantasmas, pacman.pos, previas)
    juego.tick()


def leer_direccion(pantalla):
    """Vacía el buffer de teclado y devuelve la última dirección pedida.

    Devuelve `"salir"` si se pidió salir, `None` si no hubo ninguna tecla útil.
    Vaciar el buffer es lo que evita perder teclas: con un solo `getch()` por
    turno, apretar dos direcciones rápido descarta la segunda.
    """
    direccion = None
    while True:
        tecla = pantalla.getch()
        if tecla == -1:
            return direccion
        if tecla in (ord("q"), 27):
            return "salir"
        if tecla in TECLAS:
            direccion = TECLAS[tecla]


def esperar_turno(pantalla, pacman, segundos=SEGUNDOS_POR_TICK):
    """Espera el turno leyendo el teclado en tramos cortos.

    Dormir de una sola vez es lo que hace que el juego se sienta trabado: una
    tecla apretada al principio del turno no se ve hasta el siguiente. Devuelve
    True si hay que salir.
    """
    tramos = max(1, int(segundos / TIEMPO_DE_ESPERA_POR_ITERACION))
    for _ in range(tramos):
        pedido = leer_direccion(pantalla)
        if pedido == "salir":
            return True
        if pedido:
            pacman.intentar_girar(pedido)
        time.sleep(TIEMPO_DE_ESPERA_POR_ITERACION)
    return False


def loop(pantalla) -> None:
    """Loop principal: lee el teclado, avanza el juego y dibuja."""
    curses.curs_set(0)
    pantalla.nodelay(True)
    pantalla.keypad(True)
    juego, pacman, fantasmas = armar()

    while not juego.terminado():
        # un_tick() es el único que mueve: acá no se duplica nada.
        un_tick(juego, pacman, fantasmas)
        dibujar(pantalla, juego, pacman, fantasmas)
        if esperar_turno(pantalla, pacman):
            return

    fin_de_partida(pantalla, juego, pacman, fantasmas)


def fin_de_partida(pantalla, juego, pacman, fantasmas) -> None:
    """Muestra el resultado y espera una tecla de verdad.

    Vaciar el buffer antes de esperar no es un detalle: las teclas que quedaron
    de la partida hacen que el `getch()` devuelva al instante y la pantalla de
    fin se cierre sin que nadie la vea.
    """
    dibujar(pantalla, juego, pacman, fantasmas)
    try:
        curses.flushinp()
    except Exception:
        pass
    pantalla.nodelay(False)
    alto, _ = pantalla.getmaxyx()
    mensaje = f"  {juego.resultado().upper()} — puntaje {juego.puntaje}   ·   tecla para salir  "
    pantalla.addstr(min(alto - 1, juego.laberinto.alto + 3), 0, mensaje)
    pantalla.refresh()
    pantalla.getch()


def main() -> None:
    """Arranca curses y se asegura de restaurar la terminal al salir."""
    curses.wrapper(loop)


if __name__ == "__main__":
    main()
