import unittest

from src.pacman.entidades import Pacman
from src.pacman.juego import Juego
from src.pacman.laberinto import Laberinto
from src.pacman.render import FANTASMA, FANTASMA_ASUSTADO, PACMAN, componer

MAPA = [
    "#####",
    "#.o.#",
    "# .P#",
    "#####",
]


class FantasmaFalso:
    def __init__(self, pos):
        self.pos = pos
        self.inicio = pos


class TestComponer(unittest.TestCase):
    """componer() no usa curses, así que se puede testear sin terminal."""

    def setUp(self):
        self.lab = Laberinto(MAPA)
        self.juego = Juego(self.lab)
        self.pacman = Pacman(self.lab.inicio_pacman)

    def test_pacman_aparece_en_su_celda(self):
        lineas = componer(self.juego, self.pacman, [])
        fila, col = self.pacman.pos
        self.assertEqual(lineas[fila][col], PACMAN)

    def test_el_fantasma_aparece_en_su_celda(self):
        lineas = componer(self.juego, self.pacman, [FantasmaFalso((1, 1))])
        self.assertEqual(lineas[1][1], FANTASMA)

    def test_el_fantasma_asustado_se_dibuja_distinto(self):
        self.juego.comer_en((1, 2))
        lineas = componer(self.juego, self.pacman, [FantasmaFalso((1, 1))])
        self.assertEqual(lineas[1][1], FANTASMA_ASUSTADO)

    def test_pacman_tapa_al_fantasma_en_la_misma_celda(self):
        lineas = componer(self.juego, self.pacman, [FantasmaFalso(self.pacman.pos)])
        fila, col = self.pacman.pos
        self.assertEqual(lineas[fila][col], PACMAN)

    def test_el_marcador_muestra_puntaje_y_vidas(self):
        self.juego.comer_en((1, 1))
        marcador = componer(self.juego, self.pacman, [])[-1]
        self.assertIn("Puntaje: 10", marcador)
        self.assertIn("Vidas: 3", marcador)

    def test_el_marcador_avisa_el_modo_asustado(self):
        self.juego.comer_en((1, 2))
        self.assertIn("ASUSTADOS", componer(self.juego, self.pacman, [])[-1])

    def test_el_tablero_conserva_el_tamano_del_mapa(self):
        lineas = componer(self.juego, self.pacman, [])
        self.assertEqual(len(lineas), self.lab.alto + 2)  # + línea en blanco + marcador
        self.assertEqual(len(lineas[0]), self.lab.ancho)


if __name__ == "__main__":
    unittest.main()
