# T13 — Mejorar movimiento de fantasmas persiguiendo

**Depende de:** T10 (ya hecha)
**Archivos que podés tocar:** `src/pacman/entidades.py`, `tests/test_entidades.py`
**Prohibido tocar:** `laberinto.py`, `juego.py`, `render.py`, `__main__.py`

## El problema

Los fantasmas persiguen a Pacman usando una distancia Manhattan codiciosa sin path‑finding. En laberintos con esquinas estrechas, los fantasmas se quedan atrapados oscilando entre dos celdas. La decisión original de usar distancia Manhattan está anotada en `PLAN.md` y necesita ser revisada.

## Objetivo

Implementar un algoritmo de búsqueda de camino (p. ej., BFS) para que el fantasma persigue por la ruta más corta, evitando quedar atrapado.

## Alcance

Entra:
- `Fantasma.mover(laberinto, objetivo, direccion_pacman=(0,0), asustado=False) -> tuple[int, int]` utiliza path‑finding cuando `self.estilo == "perseguidor"` (valor por defecto).
- Se mantiene determinismo: el desempate sigue siendo estable (orden de exploración fijo).
- Se usa `laberinto.vecinas_libres(pos)` para expandir el BFS: devuelve las celdas sin
  pared en orden estable (arriba, abajo, izquierda, derecha). **No existe `es_celda_libre`**;
  los métodos del laberinto son `es_pared`, `contenido`, `vecinas_libres` y `dentro`.

No entra:
- Cambiar el comportamiento de los demás estilos (`emboscador`, `timido`, `errante`).
- Modificar la lógica de renderizado o del bucle principal.

## Contrato

```python
class Fantasma:
    def mover(self, laberinto, objetivo, direccion_pacman=(0, 0), asustado=False) -> tuple[int, int]:
        """Devuelve la siguiente posición del fantasma.

        - Si ``self.estilo == "perseguidor"`` se calcula la ruta más corta
          desde la posición actual hasta ``objetivo`` usando BFS y se avanza
          un paso.
        - En los demás estilos se mantiene el comportamiento anterior.
        - ``asustado=True`` invierte la lógica: se elige el paso que maximiza
          la distancia Manhattan al objetivo.
        """
```

## Criterio de terminado

Estos tests deben existir, **con estos nombres**:

- [ ] `test_perseguidor_encuentra_camino_corto`
- [ ] `test_perseguidor_no_oscilacion_esquinas`
- [ ] `test_perseguidor_no_se_sale_del_mapa`
- [ ] `test_perseguidor_mantiene_determinismo`
- [ ] Los tests que ya existen siguen pasando sin modificarlos.
- [ ] `bash scripts/gate.sh` en verde

## Decisiones cerradas (las cerró un humano; no las rediscutas)

- **BFS, no A\*.** El laberinto son 17×19 celdas: A\* no compra nada y agrega una heurística
  que puede sesgar el desempate. BFS sobre `vecinas_libres` es determinista y suficiente.
- **Desempate:** ante varios caminos de igual longitud gana el primer vecino según el orden
  de `vecinas_libres` (arriba, abajo, izquierda, derecha). Es el mismo criterio que ya usa
  el código, así que no cambia el comportamiento en los casos sin empate.
- **Sigue sin darse vuelta 180°** salvo en callejón sin salida, como hoy.
- **Nada de `random`.** Los tests dependen de que todo sea determinista.

## Verificación

```bash
bash scripts/gate.sh
```
