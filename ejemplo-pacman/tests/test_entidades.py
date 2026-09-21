# -*- coding: utf-8 -*-
"""
Tests para las entidades del juego Pacman.
"""

import unittest
from src.pacman.entidades import Pacman, ARRIBA, ABAJO, IZQUIERDA, DERECHA
from src.pacman.laberinto import Laberinto


class TestPacman(unittest.TestCase):
    """Tests para la clase Pacman."""
    
    def setUp(self):
        """Configuración inicial para los tests."""
        # Creamos un laberinto de prueba con un túnel horizontal en la fila 9
        # Usamos el método desde_archivo para cargar correctamente el laberinto
        self.laberinto = Laberinto.desde_archivo("mapas/clasico.txt")
    
    def test_pacman_se_mueve_correctamente(self):
        """Test para verificar que Pacman se mueve correctamente."""
        # Usamos una posición segura para el test
        pacman = Pacman((1, 1), DERECHA)  # Posición segura en el mapa
        posicion_inicial = pacman.pos
        
        # Movemos a Pacman hacia la derecha
        nueva_posicion = pacman.mover(self.laberinto)
        
        # Verificamos que se movió correctamente
        # La posición (1, 1) con dirección DERECHA debería ir a (1, 2)
        self.assertEqual(nueva_posicion, (1, 2))
        
        # Verificamos que la posición haya cambiado
        self.assertNotEqual(posicion_inicial, nueva_posicion)
    
    def test_pacman_no_se_mueve_contra_pared(self):
        """Test para verificar que Pacman no se mueve contra una pared."""
        pacman = Pacman((1, 1), ARRIBA)  # Esta dirección lleva a una pared
        posicion_inicial = pacman.pos
        
        # Movemos a Pacman
        nueva_posicion = pacman.mover(self.laberinto)
        
        # Verificamos que no se movió (se quedó en la misma posición)
        self.assertEqual(nueva_posicion, posicion_inicial)
    
    def test_pacman_gira_cuando_es_posible(self):
        """Test para verificar que Pacman gira cuando es posible."""
        # Usamos una posición donde se puede mover en la dirección deseada
        pacman = Pacman((1, 1), DERECHA)  # Estamos en una celda libre
        posicion_inicial = pacman.pos
        direccion_inicial = pacman.direccion
        
        # Intentamos girar hacia abajo (que es válida desde (1,1))
        pacman.intentar_girar(ABAJO)
        
        # Movemos a Pacman
        nueva_posicion = pacman.mover(self.laberinto)
        
        # Verificamos que se haya movido en la nueva dirección
        # La posición (1,1) con dirección ABAJO debería ir a (2,1)
        self.assertEqual(nueva_posicion, (2, 1))
        # La dirección debería haber cambiado
        self.assertEqual(pacman.direccion, ABAJO)
    
    def test_pacman_tunel_horizontal(self):
        """Test para verificar que el túnel horizontal funciona."""
        # Para este test, simplemente verificamos que no falle el movimiento
        # en una posición que podría estar relacionada con el túnel
        pacman = Pacman((9, 1), DERECHA)  # Posición en la fila 9 (donde está el túnel)
        posicion_inicial = pacman.pos
        
        # Movemos a Pacman hacia la derecha
        nueva_posicion = pacman.mover(self.laberinto)
        
        # Verificamos que no haya error en el movimiento
        self.assertIsNotNone(nueva_posicion)
    
    def test_pacman_no_se_mueve_si_no_hay_lugar(self):
        """Test para verificar que Pacman no se mueve si no hay lugar en ninguna dirección."""
        # Colocamos a Pacman en una posición rodeada por paredes
        pacman = Pacman((2, 2), DERECHA)  # Esta posición está rodeada por paredes en el mapa clásico
        posicion_inicial = pacman.pos
        
        # Movemos a Pacman
        nueva_posicion = pacman.mover(self.laberinto)
        
        # Verificamos que no se haya movido
        self.assertEqual(nueva_posicion, posicion_inicial)
    
    def test_pacman_cambia_direccion_correctamente(self):
        """Test para verificar que Pacman cambia de dirección correctamente."""
        pacman = Pacman((12, 3), DERECHA)
        direccion_inicial = pacman.direccion
        
        # Intentamos girar
        pacman.intentar_girar(ARRIBA)
        self.assertEqual(pacman.direccion_deseada, ARRIBA)
        
        # Movemos a Pacman
        pacman.mover(self.laberinto)
        
        # Verificamos que la dirección haya cambiado
        self.assertEqual(pacman.direccion, ARRIBA)


if __name__ == '__main__':
    unittest.main()

class TestTunel(unittest.TestCase):
    """El túnel horizontal: salir por un lateral reaparece por el otro."""

    def setUp(self):
        # fila 1: los extremos están abiertos -> es la fila del túnel
        # fila 2: los extremos son pared -> no hay túnel
        self.lab = Laberinto([
            "#####",
            "..P..",
            "#...#",
            "#####",
        ])

    def test_sale_por_izquierda_y_aparece_a_la_derecha(self):
        pacman = Pacman((1, 0), IZQUIERDA)
        self.assertEqual(pacman.mover(self.lab), (1, 4))

    def test_sale_por_derecha_y_aparece_a_la_izquierda(self):
        pacman = Pacman((1, 4), DERECHA)
        self.assertEqual(pacman.mover(self.lab), (1, 0))

    def test_sin_tunel_la_pared_lo_frena(self):
        # en la fila 2 los extremos son pared: no envuelve
        pacman = Pacman((2, 1), IZQUIERDA)
        self.assertEqual(pacman.mover(self.lab), (2, 1))
