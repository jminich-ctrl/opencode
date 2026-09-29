# T15 — El errante tiene que alternar fases de verdad

**Depende de:** T10, T13, T14 (todas hechas)
**Archivos que podés tocar:** `src/pacman/entidades.py`
**Prohibido tocar:** `tests/` (los tests ya están escritos), `laberinto.py`, `juego.py`, `render.py`, `__main__.py`

> **Esta tarea viene con sus tests ya escritos y fallando.** Tu trabajo es hacerlos pasar
> **sin modificarlos**. Si te parece que un test está mal, pará y decilo: no lo toques.

## El bug

```python
self._contador_errante += 1
if self._contador_errante >= 10:
    self._contador_errante = 0
    if self._contador_errante == 0:   # ← siempre verdadero: le acabás de asignar 0
        objetivo = self.inicio
    else:
        objetivo = objetivo          # ← rama muerta
```

El efecto real: persigue 9 turnos y vuelve a su esquina **un** turno. Eso no es alternar.

## Objetivo

Que el errante alterne **fases de 10 turnos**: 10 persiguiendo, 10 volviendo a su esquina,
y así.

## Alcance

Entra:
- Un método `_objetivo_errante(self, objetivo)` que devuelve a qué celda apunta este turno
  y avanza el contador.
- Los primeros 10 llamados devuelven `objetivo`; los 10 siguientes, `self.inicio`; y sigue
  alternando.
- `mover()` lo usa cuando `self.estilo == "errante"`.
- **El contador solo lo toca el errante**: los otros tres estilos no lo mueven.

No entra:
- Cambiar los otros estilos, el BFS del perseguidor ni el acortado del emboscador.
- Tocar los tests.

## Contrato

    def _objetivo_errante(self, objetivo: tuple[int, int]) -> tuple[int, int]:
        """Celda a la que apunta el errante este turno, alternando cada 10 turnos.

        Turnos 0-9 devuelven `objetivo`; 10-19 devuelven `self.inicio`; 20-29
        `objetivo` otra vez. Avanza el contador en cada llamada.
        """

## Criterio de terminado

- [ ] `python3 -m unittest discover -s tests -t . -q` pasa (los 5 tests de
      `TestErranteAlterna` incluidos), **sin modificar ningún test**
- [ ] `bash scripts/gate.sh` en verde, con el paso 4 incluido

## Verificación

    bash scripts/gate.sh
