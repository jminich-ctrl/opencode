"""Entidades del juego: Pacman y los fantasmas.

Las coordenadas son `(fila, columna)`, igual que en `laberinto`. Este módulo no
imprime ni lee entrada: decide movimientos y nada más.
"""

ARRIBA = (-1, 0)
ABAJO = (1, 0)
IZQUIERDA = (0, -1)
DERECHA = (0, 1)


class Pacman:
    """Pacman: dónde está, hacia dónde va y hacia dónde quiere ir."""

    def __init__(self, pos: tuple[int, int], direccion: tuple[int, int] = DERECHA):
        """Arranca en `pos` mirando hacia `direccion`."""
        self.pos = pos
        self.direccion = direccion
        self.direccion_deseada = direccion

    def intentar_girar(self, direccion: tuple[int, int]) -> None:
        """Guarda la dirección deseada, aunque todavía no se pueda girar.

        El giro se aplica en el primer `mover()` en que haya lugar, como en el
        Pacman original: se puede pedir el giro antes de llegar a la esquina.
        """
        self.direccion_deseada = direccion

    def mover(self, laberinto) -> tuple[int, int]:
        """Avanza una celda y devuelve la posición nueva.

        Prioriza la dirección deseada; si está bloqueada sigue derecho; si eso
        también está bloqueado se queda quieto. Salir por un lateral reaparece
        por el otro extremo de la misma fila, si esa celda no es pared.
        """
        for direccion in (self.direccion_deseada, self.direccion):
            destino = self._destino(laberinto, direccion)
            if destino is not None:
                self.direccion = direccion
                self.pos = destino
                return self.pos
        return self.pos

    def _destino(self, laberinto, direccion: tuple[int, int]):
        """Celda a la que llevaría `direccion`, o None si hay pared.

        Envuelve horizontalmente: el túnel es simplemente el módulo del ancho.
        """
        fila = self.pos[0] + direccion[0]
        col = (self.pos[1] + direccion[1]) % laberinto.ancho
        destino = (fila, col)
        return None if laberinto.es_pared(destino) else destino


class Fantasma:
    """Fantasma que persigue un objetivo con una regla simple y determinista.

    Elige, entre las celdas vecinas sin pared, la que minimiza la distancia
    Manhattan al objetivo. No se da vuelta salvo que sea la única salida, y
    ante un empate gana la primera según el orden de `vecinas_libres`
    (arriba, abajo, izquierda, derecha). Sin azar: los tests dependen de eso.
    """

    def __init__(self, pos: tuple[int, int], direccion: tuple[int, int] = ARRIBA, estilo: str = "perseguidor"):
        """Arranca en `pos`, que además queda como su casa."""
        self.pos = pos
        self.inicio = pos
        self.direccion = direccion
        self.estilo = estilo
        self._contador_errante = 0

    def mover(self, laberinto, objetivo: tuple[int, int], direccion_pacman: tuple[int, int] = (0, 0),
              asustado: bool = False) -> tuple[int, int]:
        """Avanza una celda hacia `objetivo` y devuelve la posición nueva."""
        # Si está asustado, se aleja del objetivo
        if asustado:
            # Selecciona la celda que maximiza la distancia al objetivo
            opciones = laberinto.vecinas_libres(self.pos)
            if not opciones:
                return self.pos

            atras = (self.pos[0] - self.direccion[0], self.pos[1] - self.direccion[1])
            sin_volver = [c for c in opciones if c != atras]
            candidatas = sin_volver or opciones          # en un callejón, se da vuelta

            elegida = max(candidatas, key=lambda c: _manhattan(c, objetivo))
            self.direccion = (elegida[0] - self.pos[0], elegida[1] - self.pos[1])
            self.pos = elegida
            return self.pos
        
        # Si no está asustado, aplicar el estilo específico
        if self.estilo == "emboscador":
            # Apunta 4 celdas por delante de Pacman
            objetivo = (
                objetivo[0] + direccion_pacman[0] * 4,
                objetivo[1] + direccion_pacman[1] * 4
            )
        elif self.estilo == "timido":
            # Persigue si está a más de 8 celdas de distancia, sino se va a su esquina
            distancia = _manhattan(self.pos, objetivo)
            if distancia <= 8:
                # Se va a su esquina (inicio)
                objetivo = self.inicio
        elif self.estilo == "errante":
            # Alterna entre perseguir y volver a su esquina cada 10 movimientos
            self._contador_errante += 1
            if self._contador_errante >= 10:
                self._contador_errante = 0
                # Alternar entre objetivo normal y inicio
                if self._contador_errante == 0:
                    objetivo = self.inicio
                else:
                    objetivo = objetivo
            else:
                # Mantener el objetivo actual
                pass
        
        # Comportamiento común para todos los estilos (excepto asustado)
        opciones = laberinto.vecinas_libres(self.pos)
        if not opciones:
            return self.pos

        atras = (self.pos[0] - self.direccion[0], self.pos[1] - self.direccion[1])
        sin_volver = [c for c in opciones if c != atras]
        candidatas = sin_volver or opciones          # en un callejón, se da vuelta

        elegida = min(candidatas, key=lambda c: _manhattan(c, objetivo))
        self.direccion = (elegida[0] - self.pos[0], elegida[1] - self.pos[1])
        self.pos = elegida
        return self.pos


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Distancia Manhattan entre dos celdas."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
