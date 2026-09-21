"""Dibujo del juego en la terminal.

Este módulo solo **lee** el estado: no decide nada. `componer()` arma las líneas
como texto puro y no depende de curses, así que es lo que se puede testear;
`dibujar()` las manda a la pantalla.
"""

import curses
from .laberinto import PARED, PODER, PUNTO

PACMAN = "C"
FANTASMA = "M"
FANTASMA_ASUSTADO = "w"


def componer(juego, pacman, fantasmas) -> list[str]:
    """Arma el tablero como lista de líneas de texto, más el marcador.

    Dibuja primero el laberinto, después los fantasmas y por último a Pacman,
    para que Pacman quede visible cuando comparte celda con alguno.
    """
    lab = juego.laberinto
    filas = [list(fila) for fila in lab.celdas]

    for fantasma in fantasmas:
        fila, col = fantasma.pos
        if lab.dentro((fila, col)):
            # Para el modo asustado, alternar entre dos caracteres en los últimos 3 turnos
            if juego.asustados and juego.asustado_restante <= 3:
                # Alternar entre FANTASMA_ASUSTADO y FANTASMA
                if juego.asustado_restante % 2 == 0:
                    filas[fila][col] = FANTASMA_ASUSTADO
                else:
                    filas[fila][col] = FANTASMA
            else:
                filas[fila][col] = FANTASMA_ASUSTADO if juego.asustados else FANTASMA

    fila, col = pacman.pos
    if lab.dentro((fila, col)):
        filas[fila][col] = PACMAN

    lineas = ["".join(f) for f in filas]
    lineas.append("")
    
    # Formatear el marcador con símbolos para vidas y barra de asustado
    vidas_simbolo = "♥" * juego.vidas
    marcador = f"Puntaje: {juego.puntaje}    Vidas: {vidas_simbolo}"
    
    if juego.asustados:
        marcador += f"    ¡ASUSTADOS! {juego.asustado_restante}"
    
    lineas.append(marcador)
    return lineas


def _color(par):
    """Atributo de color, o 0 si la terminal no los soporta."""
    try:
        return curses.color_pair(par)
    except Exception:
        return 0


def dibujar(pantalla, juego, pacman, fantasmas) -> None:
    """Pinta el tablero en una pantalla de curses.

    Si la terminal es más chica que el tablero, muestra un aviso en vez de
    reventar: escribir fuera de la pantalla en curses lanza una excepción.
    """
    # Verificar si la terminal soporta colores
    try:
        hay_color = curses.has_colors()
    except Exception:
        hay_color = False          # no estamos dentro de curses (tests, tubería)
    if hay_color:
        # Inicializar pares de colores
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)      # Paredes
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)     # Puntos
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)    # Pastillas
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)    # Pacman
        curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)       # Fantasmas normales
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)      # Fantasmas asustados
        
        # Dibujar el tablero con colores
        lineas = componer(juego, pacman, fantasmas)
        alto, ancho = pantalla.getmaxyx()
        pantalla.erase()
        
        if alto < len(lineas) + 1 or ancho < max(len(l) for l in lineas) + 1:
            mensaje = f"Agrandá la terminal: hacen falta {max(len(l) for l in lineas) + 1}x{len(lineas) + 1}"
            try:
                pantalla.addstr(0, 0, mensaje[:max(0, ancho - 1)])
            except Exception:
                pass
            pantalla.refresh()
            return
            
        # Dibujar cada línea con sus colores correspondientes
        for nro, linea in enumerate(lineas):
            # Para el marcador, usar un color diferente
            if nro >= len(juego.laberinto.celdas):
                pantalla.addstr(nro, 0, linea, _color(2))  # Color para marcador
            else:
                # Procesar cada carácter con su color correspondiente
                for i, char in enumerate(linea):
                    if char == PARED:
                        pantalla.addstr(nro, i, char, _color(1))  # Azul para paredes
                    elif char == PUNTO:
                        pantalla.addstr(nro, i, char, _color(2))  # Blanco para puntos
                    elif char == PODER:
                        pantalla.addstr(nro, i, char, _color(3))  # Amarillo para pastillas
                    elif char == PACMAN:
                        pantalla.addstr(nro, i, char, _color(4))  # Amarillo brillante para Pacman
                    elif char == FANTASMA:
                        pantalla.addstr(nro, i, char, _color(5))  # Rojo para fantasmas normales
                    elif char == FANTASMA_ASUSTADO:
                        pantalla.addstr(nro, i, char, _color(6))  # Azul para fantasmas asustados
                    else:
                        pantalla.addstr(nro, i, char)  # Carácter normal por defecto
                        
    else:
        # Si no hay colores, dibujar como antes
        lineas = componer(juego, pacman, fantasmas)
        alto, ancho = pantalla.getmaxyx()
        pantalla.erase()
        if alto < len(lineas) + 1 or ancho < max(len(l) for l in lineas) + 1:
            mensaje = f"Agrandá la terminal: hacen falta {max(len(l) for l in lineas) + 1}x{len(lineas) + 1}"
            try:
                pantalla.addstr(0, 0, mensaje[:max(0, ancho - 1)])
            except Exception:
                pass
            pantalla.refresh()
            return
        for nro, linea in enumerate(lineas):
            pantalla.addstr(nro, 0, linea)
    
    pantalla.refresh()
