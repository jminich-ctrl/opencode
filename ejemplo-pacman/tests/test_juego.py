import unittest

from src.pacman.juego import Juego
from src.pacman.laberinto import Laberinto, PODER, PUNTO, VACIO

# (1,1) punto · (1,2) pastilla · (1,3) punto · (2,1) vacío · (2,3) Pacman
MAPA = [
    "#####",
    "#.o.#",
    "# .P#",
    "#####",
]


class TestJuego(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(Laberinto(MAPA))

    def test_comer_punto_suma_10(self):
        self.assertEqual(self.juego.comer_en((1, 1)), PUNTO)
        self.assertEqual(self.juego.puntaje, 10)

    def test_comer_pastilla_suma_50(self):
        self.assertEqual(self.juego.comer_en((1, 2)), PODER)
        self.assertEqual(self.juego.puntaje, 50)

    def test_comer_celda_vacia_no_suma(self):
        self.assertEqual(self.juego.comer_en((2, 1)), VACIO)
        self.assertEqual(self.juego.puntaje, 0)

    def test_comer_la_misma_celda_dos_veces_suma_una_sola(self):
        self.juego.comer_en((1, 1))
        self.juego.comer_en((1, 1))
        self.assertEqual(self.juego.puntaje, 10)

    def test_comer_pared_no_suma(self):
        self.juego.comer_en((0, 0))
        self.assertEqual(self.juego.puntaje, 0)

    def test_ultima_pastilla_solo_con_pastilla(self):
        self.juego.comer_en((1, 1))
        self.assertFalse(self.juego.ultima_pastilla)
        self.juego.comer_en((1, 2))
        self.assertTrue(self.juego.ultima_pastilla)
        self.juego.comer_en((1, 3))
        self.assertFalse(self.juego.ultima_pastilla)

    def test_nivel_limpio_falso_al_empezar(self):
        self.assertFalse(self.juego.nivel_limpio())

    def test_nivel_limpio_cuando_no_queda_nada(self):
        for pos in ((1, 1), (1, 2), (1, 3), (2, 2)):
            self.juego.comer_en(pos)
        self.assertTrue(self.juego.nivel_limpio())

    def test_nivel_no_limpio_si_queda_uno(self):
        for pos in ((1, 1), (1, 2), (1, 3)):
            self.juego.comer_en(pos)
        self.assertFalse(self.juego.nivel_limpio())


if __name__ == "__main__":
    unittest.main()


class FantasmaFalso:
    """Mínimo necesario para probar colisiones sin depender de T04."""

    def __init__(self, pos):
        self.pos = pos
        self.inicio = pos


class TestModoAsustado(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(Laberinto(MAPA))

    def test_comer_pastilla_activa_el_modo(self):
        self.assertFalse(self.juego.asustados)
        self.juego.comer_en((1, 2))
        self.assertTrue(self.juego.asustados)
        self.assertEqual(self.juego.asustado_restante, 20)

    def test_el_modo_dura_20_ticks(self):
        self.juego.comer_en((1, 2))
        for _ in range(19):
            self.juego.tick()
        self.assertTrue(self.juego.asustados)
        self.juego.tick()
        self.assertFalse(self.juego.asustados)

    def test_comer_un_punto_no_activa_el_modo(self):
        self.juego.comer_en((1, 1))
        self.assertFalse(self.juego.asustados)

    def test_cuatro_fantasmas_duplican_el_puntaje(self):
        self.juego.comer_en((1, 2))  # 50 por la pastilla
        for _ in range(4):
            fantasma = FantasmaFalso((3, 3))
            self.assertEqual(self.juego.colision((3, 3), [fantasma]), "comio")
        self.assertEqual(self.juego.puntaje, 50 + 200 + 400 + 800 + 1600)

    def test_el_multiplicador_se_reinicia_con_cada_modo(self):
        self.juego.comer_en((1, 2))
        self.juego.colision((3, 3), [FantasmaFalso((3, 3))])
        for _ in range(20):
            self.juego.tick()
        self.juego.comer_en((1, 5))  # fuera del mapa: no es pastilla
        self.juego.asustado_restante = 20
        self.juego._comidos_en_este_modo = 0
        antes = self.juego.puntaje
        self.juego.colision((3, 3), [FantasmaFalso((3, 3))])
        self.assertEqual(self.juego.puntaje - antes, 200)

    def test_el_fantasma_comido_vuelve_a_su_inicio(self):
        self.juego.comer_en((1, 2))
        fantasma = FantasmaFalso((2, 2))
        fantasma.pos = (3, 3)
        self.juego.colision((3, 3), [fantasma])
        self.assertEqual(fantasma.pos, fantasma.inicio)

    def test_sin_modo_la_colision_es_perdida(self):
        self.assertEqual(self.juego.colision((3, 3), [FantasmaFalso((3, 3))]), "perdio")

    def test_sin_fantasma_en_la_celda_no_pasa_nada(self):
        self.assertEqual(self.juego.colision((1, 1), [FantasmaFalso((3, 3))]), "nada")


class TestVidas(unittest.TestCase):
    def setUp(self):
        self.juego = Juego(Laberinto(MAPA))

    def test_empieza_con_tres_vidas(self):
        self.assertEqual(self.juego.vidas, 3)

    def test_perder_las_tres_vidas_termina_la_partida(self):
        for _ in range(3):
            self.juego.colision((3, 3), [FantasmaFalso((3, 3))])
        self.assertEqual(self.juego.vidas, 0)
        self.assertTrue(self.juego.terminado())
        self.assertEqual(self.juego.resultado(), "perdió")

    def test_limpiar_el_nivel_gana(self):
        for pos in ((1, 1), (1, 2), (1, 3), (2, 2)):
            self.juego.comer_en(pos)
        self.assertTrue(self.juego.terminado())
        self.assertEqual(self.juego.resultado(), "ganó")

    def test_perder_una_vida_devuelve_los_fantasmas_al_inicio(self):
        fantasma = FantasmaFalso((2, 2))
        fantasma.pos = (3, 3)
        self.juego.colision((3, 3), [fantasma])
        self.assertEqual(fantasma.pos, (2, 2))

    def test_perder_una_vida_apaga_el_modo_asustado(self):
        self.juego.comer_en((1, 2))
        self.juego.asustado_restante = 0  # se acabó el modo
        self.juego.colision((3, 3), [FantasmaFalso((3, 3))])
        self.assertEqual(self.juego.asustado_restante, 0)
        self.assertEqual(self.juego.vidas, 2)

    def test_la_partida_no_termina_con_vidas_y_puntos(self):
        self.assertFalse(self.juego.terminado())
        self.assertIsNone(self.juego.resultado())
