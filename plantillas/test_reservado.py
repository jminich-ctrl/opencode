#!/usr/bin/env python3
"""PLANTILLA de suite reservada. Copiala FUERA del repo.

    mkdir ~/reservados-<tu-proyecto>
    cp plantillas/test_reservado.py ~/reservados-<tu-proyecto>/test_composicion.py

Por qué afuera y no sólo sin documentar: está medido que **leer los tests reservados es el
hack más común** de un agente que no puede pasarlos de otra forma. Afuera del repo no viaja
en los worktrees, no se commitea por accidente, y OpenCode la rechaza por
`external_directory` desde cualquier sesión de tarea.

El paso 6 del gate la corre **sólo en modo integración** (sobre el tronco).

## Qué va acá y qué no

**Va:** invariantes que cruzan módulos y que ningún test de tarea afirma. Cosas que tienen
que ser verdad siempre, no casos particulares. Se escriben mejor como "jugá/usá la cosa
muchas veces al azar y exigí que esto nunca pase".

**No va:** repetir los tests de las tareas. Si lo que escribís acá ya lo cubre un test de
tarea, no estás midiendo nada nuevo.

## Por qué existe, en una línea

Los gates de tarea verifican lo que los tests de la tarea cubren, y el agente optimiza
contra eso. Medido: la brecha de reward hacking crece ~27 puntos por cada 10× de tamaño de
código, y los puntajes de validación se saturan mientras los reservados divergen — peor en
modelos chicos. **Es el único gate que mide lo que el agente no pudo haber optimizado.**

## Lo que nos pasó al escribir la primera

Dos cosas, y las dos valen más que los tests:

1. **La primera versión asumía una API que no existía.** Escribir desde afuera, sin mirar
   los tests de las tareas, obliga a leer el código de verdad.
2. **El primer fallo fue del test, no del producto**: jugaba pasado el fin de partida y
   llegaba a vidas negativas. El juego ya exponía `terminado()`. Un invariante mal escrito
   da rojo igual, así que la suite reservada también se depura.

Y para ser claros sobre lo que todavía **no** demostramos: en nuestro ejemplo, cada
regresión que probamos la atrapaba también la suite normal — que ya tiene 96 tests después
de muchas vueltas. El argumento a favor de esto es estructural y de escala, no "nos
encontró un bug que los otros no vieron".
"""
import random
import unittest

# ADAPTAR: importá tu código. La ruta del proyecto entra por PYTHONPATH, que pone el gate.
# from src.mi_modulo import Cosa


class TestInvariantesDeComposicion(unittest.TestCase):
    """ADAPTAR. El patrón: ejercitá el sistema muchas veces y exigí lo que nunca puede pasar."""

    def ejercitar(self, pasos, semilla):
        """Usá el sistema como lo usaría alguien, al azar, y devolvé la historia de estados."""
        random.seed(semilla)
        historia = []
        # ... acá va tu bucle ...
        return historia

    def test_un_invariante_que_cruza_modulos(self):
        for semilla in range(6):
            historia = self.ejercitar(150, semilla)
            self.assertIsNotNone(historia)
            # self.assertTrue(todo_lo_que_nunca_puede_pasar(historia))

    def test_nada_que_sea_monotono_se_da_vuelta(self):
        """Puntajes, contadores, totales: si sólo pueden crecer, verificá que nunca bajen."""

    def test_el_sistema_para_cuando_tiene_que_parar(self):
        """La condición de fin suele vivir en un módulo y consultarse en otro. Nadie la testea."""


if __name__ == "__main__":
    unittest.main()
