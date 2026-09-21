# T10 — Fantasmas con personalidad y huida

**Estado:** ✅ hecha — agente (verde al 1er intento)
**Depende de:** T04 (ya hecha)
**Archivos que podés tocar:** `src/pacman/entidades.py`, `tests/test_entidades.py`
**Prohibido tocar:** `juego.py`, `laberinto.py`, `render.py`, `__main__.py`

## El problema

Los cuatro fantasmas hacen exactamente lo mismo —perseguir por distancia Manhattan— así
que se amontonan y se traban oscilando en las esquinas. Y en modo asustado siguen
persiguiendo, cuando deberían escapar.

## Objetivo

Que cada fantasma se comporte distinto y que huyan cuando están asustados.

## Alcance

Entra:
- `Fantasma` recibe un `estilo` que cambia a qué apunta:
  - `"perseguidor"`: va a la celda de Pacman (lo que ya hace).
  - `"emboscador"`: apunta 4 celdas **por delante** de Pacman, en la dirección en la que
    Pacman está yendo (recibida como parámetro).
  - `"timido"`: persigue si está a más de 8 celdas de distancia Manhattan; si está más
    cerca, se va a su esquina (`self.inicio`).
  - `"errante"`: alterna entre perseguir y volver a su esquina cada 10 llamadas a `mover`.
- `mover(laberinto, objetivo, direccion_pacman=(0,0), asustado=False)`.
  Con `asustado=True` elige la celda que **maximiza** la distancia al objetivo.
- Todo sigue siendo determinista: sin `random`, mismo desempate estable.

No entra:
- Velocidades distintas (eso es T11).
- Cambiar quién llama a `mover` (eso es `__main__.py`).

## Contrato

    class Fantasma:
        def __init__(self, pos, direccion=ARRIBA, estilo="perseguidor")
        estilo: str
        def mover(self, laberinto, objetivo, direccion_pacman=(0, 0),
                  asustado=False) -> tuple[int, int]

El valor por defecto de `estilo` mantiene el comportamiento actual, así que **los tests
que ya existen tienen que seguir pasando sin tocarlos**.

## Criterio de terminado

Estos tests tienen que existir, **con estos nombres**:

- [ ] `test_perseguidor_se_acerca`
- [ ] `test_emboscador_apunta_delante_de_pacman`
- [ ] `test_timido_se_aleja_cuando_esta_cerca`
- [ ] `test_errante_alterna_objetivo`
- [ ] `test_asustado_huye_en_vez_de_perseguir`
- [ ] `test_estilo_por_defecto_es_el_de_siempre`
- [ ] Los tests que ya existen pasan **sin modificarlos**
- [ ] `bash scripts/gate.sh` en verde

## Si algo no cierra

Nada de `random`. Si te parece que hace falta azar para que los fantasmas no se amontonen,
el plan está mal: pará y decilo.
