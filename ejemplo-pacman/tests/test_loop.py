"""Tests del loop con una pantalla falsa.

`curses` no se puede usar en una suite automática, pero el loop sí: lo único que
necesita de la pantalla es `getch`, `addstr`, `getmaxyx`, `refresh` y `nodelay`.
Con un doble alcanza, y evita lo que nos pasó: el juego crasheaba al arrancar
mientras el gate estaba en verde, porque nadie lo ejecutaba.
"""
import unittest
from unittest import mock

from src.pacman import __main__ as juego_main
from src.pacman.entidades import DERECHA


class PantallaFalsa:
    """Lo mínimo de curses que usa el loop. Devuelve las teclas de una lista."""

    def __init__(self, teclas=()):
        self.teclas = list(teclas)
        self.dibujos = 0

    def getch(self):
        return self.teclas.pop(0) if self.teclas else -1

    def addstr(self, *_):
        self.dibujos += 1

    def getmaxyx(self):
        return (40, 80)

    def refresh(self):
        pass

    def nodelay(self, _):
        pass

    def keypad(self, _):
        pass

    def erase(self):
        pass


class TestArmado(unittest.TestCase):
    def test_hay_cuatro_fantasmas_con_estilos_distintos(self):
        _, _, fantasmas = juego_main.armar()
        self.assertEqual(len(fantasmas), 4)
        self.assertEqual(len({f.estilo for f in fantasmas}), 4)


class TestTick(unittest.TestCase):
    def test_un_tick_no_rompe_y_avanza_el_juego(self):
        juego, pacman, fantasmas = juego_main.armar()
        antes = pacman.pos
        for _ in range(50):
            juego_main.un_tick(juego, pacman, fantasmas)
        self.assertNotEqual(pacman.pos, antes)

    def test_una_partida_entera_termina_sin_romperse(self):
        """Una partida con alguien jugando (girando) llega a un final."""
        import itertools
        from src.pacman.entidades import ABAJO, ARRIBA, IZQUIERDA
        juego, pacman, fantasmas = juego_main.armar()
        giros = itertools.cycle([DERECHA, ABAJO, IZQUIERDA, ARRIBA])
        for turno in range(2000):
            if juego.terminado():
                break
            if turno % 5 == 0:
                pacman.intentar_girar(next(giros))
            juego_main.un_tick(juego, pacman, fantasmas)
        self.assertTrue(juego.terminado())
        self.assertIn(juego.resultado(), ("ganó", "perdió"))

    def test_los_fantasmas_se_mueven_la_mitad_de_rapido_si_estan_asustados(self):
        juego, pacman, fantasmas = juego_main.armar()
        juego.asustado_restante = 20
        movimientos = 0
        for _ in range(10):
            antes = [f.pos for f in fantasmas]
            juego_main.un_tick(juego, pacman, fantasmas)
            if [f.pos for f in fantasmas] != antes:
                movimientos += 1
        self.assertLess(movimientos, 10)


class TestTeclado(unittest.TestCase):
    def test_se_queda_con_la_ultima_tecla_del_buffer(self):
        pantalla = PantallaFalsa([curses_key := ord("w"), ord("d")])
        self.assertEqual(juego_main.leer_direccion(pantalla), DERECHA)

    def test_la_q_pide_salir(self):
        self.assertEqual(juego_main.leer_direccion(PantallaFalsa([ord("q")])), "salir")

    def test_sin_teclas_devuelve_none(self):
        self.assertIsNone(juego_main.leer_direccion(PantallaFalsa()))


class TestLoop(unittest.TestCase):
    def test_el_loop_arranca_dibuja_y_sale_con_q(self):
        pantalla = PantallaFalsa([ord("d")] + [-1] * 5 + [ord("q")])
        with mock.patch.object(juego_main.curses, "curs_set", lambda _: None), \
             mock.patch.object(juego_main.time, "sleep", lambda _: None):
            juego_main.loop(pantalla)
        self.assertGreater(pantalla.dibujos, 0)


if __name__ == "__main__":
    unittest.main()


class TestFinDePartida(unittest.TestCase):
    """Lo que hacía que la pantalla de fin se cerrara sola."""

    def test_vacia_el_buffer_antes_de_esperar(self):
        juego, pacman, fantasmas = juego_main.armar()
        pantalla = PantallaFalsa([ord("d"), ord("d")])   # teclas sobrantes de jugar
        juego.vidas = 0
        with mock.patch.object(juego_main.curses, "flushinp") as vaciar:
            juego_main.fin_de_partida(pantalla, juego, pacman, fantasmas)
        vaciar.assert_called_once()

    def test_muestra_el_resultado_y_el_puntaje(self):
        juego, pacman, fantasmas = juego_main.armar()
        juego.vidas = 0
        juego.puntaje = 1234
        escrito = []
        pantalla = PantallaFalsa()
        pantalla.addstr = lambda *a: escrito.append(a[-1] if isinstance(a[-1], str) else "")
        with mock.patch.object(juego_main.curses, "flushinp", lambda: None):
            juego_main.fin_de_partida(pantalla, juego, pacman, fantasmas)
        texto = " ".join(escrito)
        self.assertIn("PERDIÓ", texto)
        self.assertIn("1234", texto)

    def test_espera_una_tecla(self):
        juego, pacman, fantasmas = juego_main.armar()
        juego.vidas = 0
        pantalla = PantallaFalsa()
        llamadas = []
        pantalla.getch = lambda: (llamadas.append(1), ord("q"))[1]
        with mock.patch.object(juego_main.curses, "flushinp", lambda: None):
            juego_main.fin_de_partida(pantalla, juego, pacman, fantasmas)
        self.assertEqual(len(llamadas), 1)
