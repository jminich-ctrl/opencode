# Material crudo, cosechado al repo

Generado por `scripts/cosechar.sh` el 2026-11-23 (UTC). **No se edita a mano.**

Esto es una COPIA. Los originales siguen donde el método los escribe
(`../fallidos-TNN/`, `~/rechazados/`) porque el runner y `replanificar.sh` leen de ahí.
Está acá porque material de investigación que vive sólo afuera del repo no está
guardado: el 2026-11-10 se perdió `gate_publico.py` con su banco y su venv cuando el
sistema limpió /tmp.

## Intentos reprobados, por tarea

| tarea | intentos | parches | veredictos del arnés |
|---|---|---|---|
| T04 | 8 | 6 | 5 |
| T04b | 2 | 0 | 0 |
| T05 | 15 | 7 | 0 |
| T05a | 22 | 6 | 0 |
| T05b | 1 | 0 | 0 |
| T05c | 8 | 7 | 0 |
| T06 | 1 | 0 | 0 |
| T06a | 2 | 0 | 0 |
| T06c | 5 | 0 | 0 |
| T06c-1 | 1 | 0 | 0 |
| T06c-2 | 1 | 0 | 0 |
| T11 | 1 | 0 | 0 |
| T12 | 2 | 0 | 0 |
| T14 | 1 | 0 | 0 |
| T15 | 2 | 0 | 0 |
| T16 | 9 | 9 | 7 |
| T20 | 7 | 1 | 0 |
| T21 | 1 | 0 | 0 |
| T26 | 27 | 15 | 2 |
| T28 | 22 | 14 | 6 |

El **veredicto del arnés** es el dato nuevo y es el que vale: hasta el 2026-11-10 el
motivo del rechazo sólo existía en stdout y moría con la corrida, así que de los
intentos viejos hay transcript y parche pero no veredicto. El transcript NO lo
reemplaza: el agente imprime el gate varias veces mientras trabaja y el último que
imprime no es el veredicto (ver `banco/PROCEDENCIA.md`).

## El banco con código real

`banco/` — 22 carpetas, 16 de ellas con veredicto ✗ ROJO y el parche que un modelo
escribió de verdad. Su procedencia, modelo por modelo, está en `banco/PROCEDENCIA.md`.

## Replanificación

`replan/` — lo que el arquitecto hizo cuando recibió el motivo del rechazo. Son los
transcripts que el 2026-11-10 refutaron la hipótesis de que el arquitecto no actuaba
porque recibía la categoría en vez del dato: con el dato adelante tampoco reescribió.

## El registro de mediciones

`metricas/` — `intentos.csv` (una fila por intento, con la huella del
instrumento que la produjo) y `veredictos.jsonl` (el veredicto del gate con el
enunciado y el test completos, que es el insumo del dataset). Vivían sólo en
`.metricas/`, que está gitignoreado: correcto para el worktree de una tarea,
falso para la serie con la que se decide si un cambio del método sirvió.

## Historia

`historia/` — handoffs viejos, traídos del home. Los supera `../../ESTADO.md`;
están acá porque el de 2026-10-19 tiene la tabla de afirmaciones mías que resultaron
FALSAS, que es material y no ruido.
