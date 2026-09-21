# T01 — Laberinto: parseo del mapa

**Estado:** ✅ hecha — sirve de referencia de calidad para las demás
**Depende de:** ninguna
**Archivos que podés tocar:** `src/pacman/laberinto.py`, `tests/test_laberinto.py`, `mapas/clasico.txt`
**Prohibido tocar:** todo lo demás

## Objetivo

Cargar el mapa desde texto y poder preguntarle qué hay en cada celda.

## Alcance

Entra:
- Parsear el mapa desde una lista de líneas y desde un archivo.
- Extraer las posiciones iniciales de Pacman y de los fantasmas; esas celdas quedan vacías.
- Responder: ¿es pared?, ¿qué hay acá?, ¿cuántos puntos quedan?
- Comer una celda (devuelve lo que había y la vacía).
- Listar las celdas vecinas sin pared, en orden estable.

No entra:
- Movimiento de entidades (eso es T02).
- Puntaje (eso es T03).
- Cualquier cosa que imprima por pantalla.

## Contrato

    class Laberinto:
        def __init__(self, filas: list[str]) -> None
        @classmethod
        def desde_archivo(cls, ruta: str) -> "Laberinto"
        alto: int
        ancho: int
        def dentro(self, pos: tuple[int, int]) -> bool
        def es_pared(self, pos: tuple[int, int]) -> bool      # fuera de grilla = pared
        def contenido(self, pos: tuple[int, int]) -> str
        def comer(self, pos: tuple[int, int]) -> str          # devuelve lo que había
        def puntos_restantes(self) -> int
        def vecinas_libres(self, pos: tuple[int, int]) -> list[tuple[int, int]]

`vecinas_libres` devuelve en orden **arriba, abajo, izquierda, derecha**. No lo cambies:
el desempate de los fantasmas (T04) depende de ese orden.

## Criterio de terminado

- [x] Un mapa sin `P` levanta `ValueError`
- [x] Fuera de la grilla cuenta como pared
- [x] Comer dos veces la misma celda no rompe nada
- [x] Comer una pared no la convierte en vacío
- [x] Filas de distinto largo se completan a la más ancha
- [x] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh
