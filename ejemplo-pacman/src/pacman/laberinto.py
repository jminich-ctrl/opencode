"""Laberinto: parsea el mapa de texto y responde qué hay en cada celda.

El mapa se escribe como texto (ver `mapas/clasico.txt`) con estos símbolos:

    #   pared
    .   punto
    o   pastilla de poder
    P   posición inicial de Pacman
    G   posición inicial de un fantasma
    ' ' celda vacía

Las coordenadas son `(fila, columna)`, enteras, con origen arriba a la izquierda.
Este módulo no imprime ni lee entrada: es lógica pura.
"""

PARED = "#"
PUNTO = "."
PODER = "o"
VACIO = " "
INICIO_PACMAN = "P"
INICIO_FANTASMA = "G"


class Laberinto:
    """Grilla del juego, con los puntos que todavía no se comieron."""

    def __init__(self, filas: list[str]):
        """Construye el laberinto desde una lista de filas de texto.

        Las posiciones de Pacman y de los fantasmas se extraen y la celda
        queda vacía: las entidades no son parte de la grilla.
        """
        if not filas:
            raise ValueError("el mapa está vacío")
        ancho = max(len(f) for f in filas)
        self.celdas: list[list[str]] = []
        self.inicio_pacman: tuple[int, int] | None = None
        self.inicios_fantasmas: list[tuple[int, int]] = []

        for nro_fila, fila in enumerate(filas):
            fila = fila.ljust(ancho)
            celdas_fila = []
            for nro_col, simbolo in enumerate(fila):
                if simbolo == INICIO_PACMAN:
                    self.inicio_pacman = (nro_fila, nro_col)
                    simbolo = VACIO
                elif simbolo == INICIO_FANTASMA:
                    self.inicios_fantasmas.append((nro_fila, nro_col))
                    simbolo = VACIO
                celdas_fila.append(simbolo)
            self.celdas.append(celdas_fila)

        if self.inicio_pacman is None:
            raise ValueError("el mapa no tiene posición inicial de Pacman (P)")

    @classmethod
    def desde_archivo(cls, ruta: str) -> "Laberinto":
        """Carga un laberinto desde un archivo de texto."""
        with open(ruta, encoding="utf-8") as archivo:
            return cls(archivo.read().splitlines())

    @property
    def alto(self) -> int:
        """Cantidad de filas."""
        return len(self.celdas)

    @property
    def ancho(self) -> int:
        """Cantidad de columnas."""
        return len(self.celdas[0])

    def dentro(self, pos: tuple[int, int]) -> bool:
        """¿La posición cae dentro de la grilla?"""
        fila, col = pos
        return 0 <= fila < self.alto and 0 <= col < self.ancho

    def es_pared(self, pos: tuple[int, int]) -> bool:
        """¿Hay pared en esa posición? Fuera de la grilla cuenta como pared."""
        if not self.dentro(pos):
            return True
        fila, col = pos
        return self.celdas[fila][col] == PARED

    def contenido(self, pos: tuple[int, int]) -> str:
        """Qué hay en la celda: PARED, PUNTO, PODER o VACIO."""
        if not self.dentro(pos):
            return PARED
        fila, col = pos
        return self.celdas[fila][col]

    def comer(self, pos: tuple[int, int]) -> str:
        """Vacía la celda y devuelve lo que había (PUNTO, PODER o VACIO)."""
        habia = self.contenido(pos)
        if habia in (PUNTO, PODER):
            fila, col = pos
            self.celdas[fila][col] = VACIO
        return habia

    def puntos_restantes(self) -> int:
        """Cuántos puntos y pastillas quedan sin comer."""
        return sum(fila.count(PUNTO) + fila.count(PODER) for fila in self.celdas)

    def vecinas_libres(self, pos: tuple[int, int]) -> list[tuple[int, int]]:
        """Celdas adyacentes (arriba, abajo, izquierda, derecha) sin pared.

        El orden es estable: arriba, abajo, izquierda, derecha. Los fantasmas
        dependen de ese orden para desempatar.
        """
        fila, col = pos
        candidatas = [(fila - 1, col), (fila + 1, col), (fila, col - 1), (fila, col + 1)]
        return [c for c in candidatas if not self.es_pared(c)]
