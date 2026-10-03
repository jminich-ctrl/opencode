import unittest
from src.pacman.juego import Juego
from src.pacman.laberinto import Laberinto

class TestRecord(unittest.TestCase):
    
    def setUp(self):
        """Configura un laberinto básico para los tests."""
        laberinto = Laberinto([
            "#####",
            "#...#",
            "#.P.#",
            "#...#",
            "#####"
        ])
        self.juego = Juego(laberinto)
    
    def test_record_arranca_en_cero(self):
        """El record debe arrancar en 0."""
        self.assertEqual(self.juego.record, 0)
    
    def test_record_se_actualiza_al_subir_puntaje(self):
        """El record se actualiza cuando el puntaje supera el record actual."""
        # Comer un punto debería aumentar el puntaje a 10 y el record también
        self.juego.comer_en((1, 1))  # Comer un punto
        self.assertEqual(self.juego.puntaje, 10)
        self.assertEqual(self.juego.record, 10)
        
        # Comer otro punto para llegar a 20
        self.juego.comer_en((1, 2))  # Comer otro punto
        self.assertEqual(self.juego.puntaje, 20)
        self.assertEqual(self.juego.record, 20)
        
        # Comer otro punto para llegar a 30
        self.juego.comer_en((1, 3))  # Comer otro punto
        self.assertEqual(self.juego.puntaje, 30)
        self.assertEqual(self.juego.record, 30)
        
        # Comer otro punto para llegar a 40
        self.juego.comer_en((2, 1))  # Comer otro punto
        self.assertEqual(self.juego.puntaje, 40)
        self.assertEqual(self.juego.record, 40)
        
        # Comer otro punto para llegar a 50
        self.juego.comer_en((2, 3))  # Comer otro punto
        self.assertEqual(self.juego.puntaje, 50)
        self.assertEqual(self.juego.record, 50)
    
    def test_record_no_baja_al_perder_vida(self):
        """El record no debe bajar al perder una vida."""
        # Subir el puntaje a un valor alto
        self.juego.comer_en((1, 1))  # Comer un punto (10 pts)
        self.juego.comer_en((1, 2))  # Comer otro punto (10 pts)  
        self.juego.comer_en((1, 3))  # Comer otro punto (10 pts)
        self.juego.comer_en((2, 1))  # Comer otro punto (10 pts)
        self.juego.comer_en((2, 3))  # Comer otro punto (10 pts)
        
        # Verificar que el puntaje es mayor a 0
        self.assertGreater(self.juego.puntaje, 0)
        
        # Guardamos el record actual (debería ser igual al puntaje)
        record_guardado = self.juego.puntaje
        self.assertEqual(self.juego.record, record_guardado)
        
        # Simular pérdida de vida (esto debería mantener el record)
        self.juego.perder_vida((2, 1), [])
        
        # Verificar que el record no bajó
        self.assertEqual(self.juego.record, record_guardado)
        
        # Verificar que el puntaje se mantuvo (o se redujo por perder vida)
        # Pero el record debe mantenerse
        self.assertEqual(self.juego.record, record_guardado)

if __name__ == '__main__':
    unittest.main()