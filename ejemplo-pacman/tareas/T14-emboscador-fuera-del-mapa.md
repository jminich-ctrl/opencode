# T14 — El emboscador no puede apuntar fuera del mapa

**Depende de:** T10 (ya hecha), T13
**Archivos que podés tocar:** `src/pacman/entidades.py`, `tests/test_entidades.py`
**Prohibido tocar:** `laberinto.py`, `juego.py`, `render.py`, `__main__.py`

## El problema

El estilo `emboscador` apunta 4 celdas por delante de Pacman, en la dirección en la que
Pacman va. Si Pacman está contra una pared o cerca del borde, ese objetivo cae **fuera de
la grilla o dentro de una pared**, y el fantasma persigue una celda a la que nunca podría
llegar. El resultado se ve raro: se queda pegado a un borde en vez de emboscar.

## Objetivo

Que el objetivo del emboscador sea siempre una celda alcanzable del laberinto.

## Alcance

Entra:
- Al calcular el objetivo adelantado, si la celda cae fuera de la grilla o es pared,
  **acortar la distancia**: probar 4, 3, 2, 1 celdas adelante y quedarse con la primera
  que sea válida.
- Si ninguna sirve (Pacman contra una pared mirando hacia ella), el objetivo es la celda
  de Pacman: se comporta como perseguidor.
- Determinista, sin `random`.

No entra:
- Cambiar los otros tres estilos.
- Tocar el túnel horizontal: el objetivo no envuelve de un lado al otro del mapa.

## Contrato

    def _objetivo_emboscador(self, laberinto, objetivo, direccion_pacman) -> tuple[int, int]:
        """Celda 4 adelante de Pacman, acortada hasta que sea válida.

        Prueba 4, 3, 2 y 1 celdas en `direccion_pacman`; devuelve la primera que
        esté dentro de la grilla y no sea pared. Si ninguna lo está, devuelve
        `objetivo` (la celda de Pacman).
        """

## Criterio de terminado

Estos tests tienen que existir, **con estos nombres**:

- [ ] `test_emboscador_acorta_si_el_objetivo_es_pared`
- [ ] `test_emboscador_acorta_si_el_objetivo_sale_del_mapa`
- [ ] `test_emboscador_cae_en_pacman_si_nada_sirve`
- [ ] `test_emboscador_sin_obstaculos_apunta_a_cuatro_celdas`
- [ ] Los tests que ya existen siguen pasando **sin modificarlos**
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

## Nota

T13 y T14 **tocan el mismo archivo**: no se lanzan en paralelo. T14 va después de que T13
esté mergeada.
