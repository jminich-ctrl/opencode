import unittest

from src.pacman.laberinto import Laberinto, PARED, PUNTO, PODER, VACIO

MAPA = [
    "#####",
    "#.o.#",
    "#.#P#",
    "#..G#",
    "#####",
]


class TestLaberinto(unittest.TestCase):
    def setUp(self):
        self.lab = Laberinto(MAPA)

    def test_dimensiones(self):
        self.assertEqual(self.lab.alto, 5)
        self.assertEqual(self.lab.ancho, 5)

    def test_extrae_posiciones_iniciales(self):
        self.assertEqual(self.lab.inicio_pacman, (2, 3))
        self.assertEqual(self.lab.inicios_fantasmas, [(3, 3)])

    def test_las_celdas_de_inicio_quedan_vacias(self):
        self.assertEqual(self.lab.contenido((2, 3)), VACIO)
        self.assertEqual(self.lab.contenido((3, 3)), VACIO)

    def test_paredes(self):
        self.assertTrue(self.lab.es_pared((0, 0)))
        self.assertFalse(self.lab.es_pared((1, 1)))

    def test_fuera_de_la_grilla_es_pared(self):
        self.assertTrue(self.lab.es_pared((-1, 0)))
        self.assertTrue(self.lab.es_pared((99, 99)))
        self.assertFalse(self.lab.dentro((5, 0)))

    def test_comer_punto_vacia_la_celda(self):
        self.assertEqual(self.lab.contenido((1, 1)), PUNTO)
        self.assertEqual(self.lab.comer((1, 1)), PUNTO)
        self.assertEqual(self.lab.contenido((1, 1)), VACIO)

    def test_comer_dos_veces_la_misma_celda(self):
        self.lab.comer((1, 2))
        self.assertEqual(self.lab.comer((1, 2)), VACIO)

    def test_comer_pared_no_la_rompe(self):
        self.assertEqual(self.lab.comer((0, 0)), PARED)
        self.assertTrue(self.lab.es_pared((0, 0)))

    def test_puntos_restantes_baja_al_comer(self):
        antes = self.lab.puntos_restantes()
        self.lab.comer((1, 1))
        self.assertEqual(self.lab.puntos_restantes(), antes - 1)

    def test_pastilla_de_poder_cuenta_como_punto_restante(self):
        self.assertEqual(self.lab.contenido((1, 2)), PODER)
        antes = self.lab.puntos_restantes()
        self.lab.comer((1, 2))
        self.assertEqual(self.lab.puntos_restantes(), antes - 1)

    def test_vecinas_libres_excluye_paredes(self):
        self.assertEqual(self.lab.vecinas_libres((1, 1)), [(2, 1), (1, 2)])

    def test_vecinas_libres_orden_estable(self):
        # arriba, abajo, izquierda, derecha — los fantasmas dependen de este orden
        # en (2,1): arriba y abajo libres; a la izquierda y a la derecha hay pared
        self.assertEqual(self.lab.vecinas_libres((2, 1)), [(1, 1), (3, 1)])
        # en (3, 2): arriba es pared, el resto libre
        self.assertEqual(self.lab.vecinas_libres((3, 2)), [(3, 1), (3, 3)])

    def test_mapa_sin_pacman_falla(self):
        with self.assertRaises(ValueError):
            Laberinto(["###", "#.#", "###"])

    def test_mapa_vacio_falla(self):
        with self.assertRaises(ValueError):
            Laberinto([])

    def test_filas_desparejas_se_completan(self):
        lab = Laberinto(["####", "#P", "####"])
        self.assertEqual(lab.ancho, 4)
        self.assertEqual(lab.contenido((1, 3)), VACIO)


if __name__ == "__main__":
    unittest.main()
