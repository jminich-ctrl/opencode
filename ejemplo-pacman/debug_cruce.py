#!/usr/bin/env python3
"""Script para probar el comportamiento del cruce en la función colision."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.pacman.juego import Juego
from src.pacman.laberinto import Laberinto

# Mapa de prueba
MAPA = [
    "#####",
    "#.o.#",
    "# .P#",
    "#####",
]

class FantasmaFalso:
    """Mínimo necesario para probar colisiones sin depender de T04."""
    
    def __init__(self, pos):
        self.pos = pos
        self.inicio = pos

def test_cruce():
    """Prueba para verificar el comportamiento del cruce."""
    juego = Juego(Laberinto(MAPA))
    
    # Creamos un fantasma en una posición
    fantasma = FantasmaFalso((2, 2))
    
    # Caso 1: Sin posiciones anteriores, debe comportarse como antes
    print("Caso 1: Sin posiciones anteriores")
    resultado = juego.colision((2, 2), [fantasma])
    print(f"Resultado: {resultado}")
    print(f"Esperado: perdido (porque no está en modo asustado)")
    print()
    
    # Caso 2: Con posiciones anteriores, pero sin cruce real
    print("Caso 2: Con posiciones anteriores, pero sin cruce")
    fantasma2 = FantasmaFalso((2, 2))
    resultado = juego.colision((2, 2), [fantasma2], (2, 3), {id(fantasma2): (2, 3)})
    print(f"Resultado: {resultado}")
    print(f"Esperado: perdido (porque hay colisión directa)")
    print()
    
    # Caso 3: Intento de simular cruce (esto es lo que podría estar mal)
    print("Caso 3: Simulación de cruce")
    juego.comer_en((1, 2))  # Activa modo asustado
    fantasma3 = FantasmaFalso((2, 2))
    # Simula un cruce: Pacman va de (2,3) a (2,2) y fantasma va de (2,2) a (2,3)
    resultado = juego.colision((2, 2), [fantasma3], (2, 3), {id(fantasma3): (2, 3)})
    print(f"Resultado: {resultado}")
    print(f"Esperado: comio (porque está en modo asustado)")
    print()

if __name__ == "__main__":
    test_cruce()