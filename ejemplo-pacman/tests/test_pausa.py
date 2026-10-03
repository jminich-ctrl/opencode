"""Tests de T40, escritos ANTES de la implementación (METODO.md P2).

El agente los tiene que hacer pasar sin tocarlos. Sirven de tarea para el A/B de
`ejecutor` (6 herramientas) contra `build` (10): misma tarea, mismo modelo, distinto harness.
"""
import unittest

from src.pacman.juego import Juego
from src.pacman.laberinto import Laberinto

# La `o` es la pastilla de poder (laberinto.PODER). La primera versión de este archivo no
# tenía ninguna y apuntaba a (1,5), que es el arranque de un fantasma: `comer_en` no activaba
# el modo asustado y el test fallaba contra una implementación correcta.
MAPA = [
    "#######",
    "#Po..G#",
    "#.###.#",
    "#.....#",
    "#######",
]
PASTILLA = (1, 2)


class TestPausa(unittest.TestCase):
    def test_arranca_sin_pausa(self):
        self.assertFalse(Juego(Laberinto(MAPA)).pausado)

    def test_alternar_pausa(self):
        juego = Juego(Laberinto(MAPA))
        juego.alternar_pausa()
        self.assertTrue(juego.pausado)
        juego.alternar_pausa()
        self.assertFalse(juego.pausado)

    def test_en_pausa_el_tick_no_avanza_el_modo_asustado(self):
        juego = Juego(Laberinto(MAPA))
        juego.comer_en(PASTILLA)        # la pastilla de poder activa el modo
        antes = juego.asustado_restante
        juego.alternar_pausa()
        juego.tick()
        self.assertEqual(juego.asustado_restante, antes,
                         "en pausa el tick no debería consumir el modo asustado")

    def test_sin_pausa_el_tick_si_avanza(self):
        juego = Juego(Laberinto(MAPA))
        juego.comer_en(PASTILLA)
        antes = juego.asustado_restante
        juego.tick()
        self.assertLess(juego.asustado_restante, antes)
