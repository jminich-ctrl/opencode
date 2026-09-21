"""Dibujo del juego en la terminal.

Este módulo solo **lee** el estado: no decide nada. `componer()` arma las líneas
como texto puro y no depende de curses, así que es lo que se puede testear;
`dibujar()` las manda a la pantalla.
"""

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
            filas[fila][col] = FANTASMA_ASUSTADO if juego.asustados else FANTASMA

    fila, col = pacman.pos
    if lab.dentro((fila, col)):
        filas[fila][col] = PACMAN

    lineas = ["".join(f) for f in filas]
    lineas.append("")
    lineas.append(f"Puntaje: {juego.puntaje}    Vidas: {juego.vidas}" +
                  (f"    ¡ASUSTADOS! {juego.asustado_restante}" if juego.asustados else ""))
    return lineas


def dibujar(pantalla, juego, pacman, fantasmas) -> None:
    """Pinta el tablero en una pantalla de curses.

    Si la terminal es más chica que el tablero, muestra un aviso en vez de
    reventar: escribir fuera de la pantalla en curses lanza una excepción.
    """
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
