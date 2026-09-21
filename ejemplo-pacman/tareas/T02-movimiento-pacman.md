# T02 — Movimiento de Pacman

**Estado:** ✅ hecha — agente (verde al 3er intento; el túnel se agregó a mano, ver BITACORA.md, hallazgo 8)
**Depende de:** T01
**Archivos que podés tocar:** `src/pacman/entidades.py`, `tests/test_entidades.py`
**Prohibido tocar:** `src/pacman/laberinto.py`, `src/pacman/juego.py`, `src/pacman/render.py`

## Objetivo

Pacman se mueve por el laberinto respetando las paredes y recordando hacia dónde va.

## Alcance

Entra:
- Clase `Pacman` con posición y dirección actual.
- `intentar_girar(direccion)`: guarda la dirección deseada aunque todavía no se pueda girar.
- `mover(laberinto)`: si la dirección deseada es posible, gira y avanza; si no, sigue derecho;
  si tampoco puede, se queda quieto.
- Túnel horizontal: salir por un borde lateral reaparece por el otro (solo izquierda/derecha).
  En `mapas/clasico.txt` la fila del túnel es la **9**: sus columnas de los extremos
  están abiertas. En las demás filas los extremos son pared, así que ahí no hay túnel.
  El envolvimiento se calcula con el módulo del ancho; si la celda del otro lado es
  pared, Pacman no se mueve.

No entra:
- Comer puntos ni sumar puntaje (eso es T03).
- Fantasmas (eso es T04).

## Contrato

    ARRIBA = (-1, 0); ABAJO = (1, 0); IZQUIERDA = (0, -1); DERECHA = (0, 1)

    class Pacman:
        def __init__(self, pos: tuple[int, int], direccion: tuple[int, int] = DERECHA)
        pos: tuple[int, int]
        direccion: tuple[int, int]
        def intentar_girar(self, direccion: tuple[int, int]) -> None
        def mover(self, laberinto) -> tuple[int, int]   # devuelve la posición nueva

## Criterio de terminado

- [ ] Contra una pared, Pacman se queda quieto y no cambia de dirección
- [ ] Un giro pedido en un pasillo recto se aplica recién cuando hay lugar
- [ ] El túnel horizontal funciona en los dos sentidos
- [ ] Hay un test por cada punto del alcance
- [ ] Los tests nuevos fallan si se revierte `entidades.py` (verificalo)
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

## Si algo no cierra

- Si necesitás un método del laberinto que no existe: **pará y decilo**, no lo agregues.
- Si encontrás un bug en `laberinto.py`: reportalo, no lo arregles.

---

## Intento anterior (falló) — leé esto antes de empezar

El gate quedó ROJO con 2 tests fallando. Los dos son **errores de los tests**, no del código:
las expectativas no coinciden con el mapa de prueba que vos mismo escribiste.

```
test_pacman_no_se_mueve_contra_pared:  AssertionError: (1, 1) != (1, 2)
test_pacman_gira_cuando_es_posible:    AssertionError: (1, 3) != (1, 2)
```

**Antes de escribir un assert sobre una posición, verificá qué hay en esa celda.**
Escribí el mapa de prueba con las columnas contadas, y comprobá con
`laberinto.es_pared((fila, col))` que la celda que creés pared lo sea de verdad.
Un mapa chico y explícito (5x5) es más fácil de razonar que uno grande.
