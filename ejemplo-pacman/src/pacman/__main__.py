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


def loop(pantalla) -> None:
    """Loop principal: lee el teclado, avanza el juego y dibuja."""
    curses.curs_set(0)
    pantalla.nodelay(True)
    pantalla.keypad(True)
    juego, pacman, fantasmas = armar()

    # Variable para controlar cuándo mover los fantasmas (cada 2 ticks en modo asustado)
    tick_count = 0
    
    while not juego.terminado():
        # Vaciamos el buffer de teclado: leemos todas las teclas disponibles
        ultima_tecla_valida = None
        while True:
            tecla = pantalla.getch()
            if tecla == -1:  # No hay más teclas en el buffer
                break
            if tecla in (ord("q"), 27):
                return
            if tecla in TECLAS:
                ultima_tecla_valida = tecla
        
        # Aplicamos la última tecla válida si existe
        if ultima_tecla_valida is not None:
            pacman.intentar_girar(TECLAS[ultima_tecla_valida])
        
        # Mover fantasmas solo en ciertos ticks si están asustados
        for fantasma in fantasmas:
            # Solo mover si no está en modo asustado o si es un tick par
            if not juego.asustados or tick_count % 2 == 0:
                fantasma.mover(juego.laberinto, pacman.pos, juego.asustados)
        
        un_tick(juego, pacman, fantasmas)
        dibujar(pantalla, juego, pacman, fantasmas)
        
        # Dormir en tramos cortos para mejorar la sensación de respuesta
        tiempo_total = SEGUNDOS_POR_TICK
        iteraciones = int(tiempo_total / TIEMPO_DE_ESPERA_POR_ITERACION)
        for _ in range(iteraciones):
            time.sleep(TIEMPO_DE_ESPERA_POR_ITERACION)
            
        # Incrementar el contador de ticks
        tick_count += 1

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
