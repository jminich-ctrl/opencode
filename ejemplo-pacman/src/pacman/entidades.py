"""Entidades del juego: Pacman y los fantasmas.

Las coordenadas son `(fila, columna)`, igual que en `laberinto`. Este módulo no
imprime ni lee entrada: decide movimientos y nada más.
"""

from collections import deque

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

    def _objetivo_errante(self, objetivo: tuple[int, int]) -> tuple[int, int]:
        """Celda a la que apunta el errante este turno, alternando cada 10 turnos.

        Turnos 0-9 devuelven `objetivo`; 10-19 devuelven `self.inicio`; 20-29
        `objetivo` otra vez. Avanza el contador en cada llamada.
        """
        # Incrementar el contador
        self._contador_errante += 1
        
        # Determinar la fase actual basada en el valor del contador
        # Cada 10 turnos se cambia de fase
        fase_actual = (self._contador_errante - 1) // 10
        
        # Si estamos en una fase par (0, 2, 4, ...), perseguimos
        # Si estamos en una fase impar (1, 3, 5, ...), regresamos a inicio
        if fase_actual % 2 == 0:
            return objetivo
        else:
            return self.inicio
    
    def mover(self, laberinto, objetivo: tuple[int, int], direccion_pacman: tuple[int, int] = (0, 0),
              asustado: bool = False) -> tuple[int, int]:
        """Avanza una celda hacia `objetivo` y devuelve la posición nueva.

        - Si ``self.estilo == "perseguidor"`` se calcula la ruta más corta
          desde la posición actual hasta ``objetivo`` usando BFS y se avanza
          un paso.
        - En los demás estilos se mantiene el comportamiento anterior.
        - ``asustado=True`` invierte la lógica: se elige el paso que maximiza
          la distancia Manhattan al objetivo.
        """
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
            # Apunta 4 celdas por delante de Pacman, ajustadas si están fuera del mapa o son paredes
            objetivo = _objetivo_emboscador(laberinto, objetivo, direccion_pacman)
        elif self.estilo == "timido":
            # Persigue si está a más de 8 celdas de distancia, sino se va a su esquina
            distancia = _manhattan(self.pos, objetivo)
            if distancia <= 8:
                # Se va a su esquina (inicio)
                objetivo = self.inicio
        elif self.estilo == "errante":
            # Usar el nuevo método para alternar correctamente
            objetivo = self._objetivo_errante(objetivo)
        elif self.estilo == "perseguidor":
            # Usar BFS para encontrar el camino más corto
            return self._mover_con_bfs(laberinto, objetivo)
        
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
    
    def _mover_con_bfs(self, laberinto, objetivo: tuple[int, int]) -> tuple[int, int]:
        """Usa BFS para encontrar el camino más corto al objetivo."""
        # Si ya estamos en la posición objetivo, no nos movemos
        if self.pos == objetivo:
            return self.pos
            
        # BFS para encontrar el camino más corto
        queue = deque([(self.pos, [])])  # (posición, camino)
        visited = {self.pos}
        
        while queue:
            current_pos, path = queue.popleft()
            
            # Obtener vecinas libres
            vecinas = laberinto.vecinas_libres(current_pos)
            
            for vecina in vecinas:
                # Si ya visitamos esta posición, ignorarla
                if vecina in visited:
                    continue
                    
                # Agregar a la cola
                new_path = path + [vecina]
                queue.append((vecina, new_path))
                visited.add(vecina)
                
                # Si llegamos al objetivo, devolvemos el primer paso del camino
                if vecina == objetivo:
                    # Devolver el primer paso del camino
                    if new_path:
                        next_pos = new_path[0]
                        # Actualizar dirección
                        self.direccion = (next_pos[0] - self.pos[0], next_pos[1] - self.pos[1])
                        self.pos = next_pos
                        return self.pos
                    else:
                        # Si no hay camino, mantenerse en la posición actual
                        return self.pos
                        
        # Si no se encontró camino, mantenerse en la posición actual
        return self.pos


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Distancia Manhattan entre dos celdas."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _objetivo_emboscador(laberinto, objetivo: tuple[int, int], direccion_pacman: tuple[int, int]) -> tuple[int, int]:
    """Celda 4 adelante de Pacman, acortada hasta que sea válida.

    Prueba 4, 3, 2 y 1 celdas en `direccion_pacman`; devuelve la primera que
    esté dentro de la grilla y no sea pared. Si ninguna lo está, devuelve
    `objetivo` (la celda de Pacman).
    """
    # Probar desde 4 celdas adelante hasta 1
    for distancia in [4, 3, 2, 1]:
        candidato = (
            objetivo[0] + direccion_pacman[0] * distancia,
            objetivo[1] + direccion_pacman[1] * distancia
        )
        
        # Verificar si está dentro del laberinto y no es una pared
        if laberinto.dentro(candidato) and not laberinto.es_pared(candidato):
            return candidato
    
    # Si ninguna distancia funciona, retornar la posición actual de Pacman
    return objetivo
