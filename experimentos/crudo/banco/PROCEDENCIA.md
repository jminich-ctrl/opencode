# Intentos RECHAZADOS por el gate — código real, preservado

Archivado el 2026-10-07 desde worktrees de experimentos que estaban por borrarse.

Por qué existe: `recordar_falla` sólo escribe un registro cuando el veredicto es VERDE,
así que el método NO guarda nada de un intento reprobado. Y `marcar_hecha_y_limpiar`
hace `worktree remove --force`: el código se destruye con el worktree. Esto es la única
copia que existe, y es el material que la condición D_unver del experimento de memoria
necesita (diagnóstico y parche de un intento que el gate reprobó).

| carpeta | tarea | modelo | agente | archivos | líneas | veredicto |
|---|---|---|---|---|---|---|
| dm-1 | T06c | cc2f4c65 | build | 1 | 82 | ⊘ sin dato |
| dm-3 | T06c | cc2f4c65 | build | 3 | 94 | ✗ ROJO |
| dm-4 | T06c | cc2f4c65 | build | 1 | 69 | ✗ ROJO |
| dm-5 | T06c | cc2f4c65 | build | 1 | 69 | ✗ ROJO |
| dm-6 | T06c | cc2f4c65 | build | 1 | 68 | ✗ ROJO |
| dm-7 | T06c | cc2f4c65 | build | 1 | 69 | ✗ ROJO |
| dm-8 | T06c | cc2f4c65 | build | 1 | 19 | ⊘ sin dato |
| dm-9 | T06c | cc2f4c65 | build | 7 | 356 | ✗ ROJO |
| duelo-1 | T41 | 66a57a2b | build | 1 | 168 | ✗ ROJO |
| duelo-2 | T41 | f5d76140 | build | 1 | 173 | ✗ ROJO |
| mat-1 | T40 | 4fb55ab3 | build | 1 | 172 | ✓ VERDE |
| mat-10 | T41 | f5d76140 | build | 1 | 174 | ✓ VERDE |
| mat-2 | T40 | cc2f4c65 | build | 1 | 165 | ⊘ plataforma |
| mat-3 | T40 | 669dce01 | build | 1 | 165 | ✗ ROJO |
| mat-4 | T40 | 66a57a2b | build | 1 | 168 | ✗ ROJO |
| mat-5 | T40 | f5d76140 | build | 1 | 173 | ✓ VERDE |
| mat-6 | T41 | 4fb55ab3 | build | 1 | 175 | ✗ ROJO |
| mat-7 | T41 | cc2f4c65 | build | 1 | 167 | ✗ ROJO |
| mat-8 | T41 | 669dce01 | build | 1 | 167 | ✗ ROJO |
| mat-9 | T41 | 66a57a2b | build | 1 | 167 | ✗ ROJO |
| tests-T04 | T04 | f5d76140 | ejecutor | 4 | 208 | ✗ ROJO |
| tests-T26 | (no consta) | f5d76140 | ejecutor | 2 | 215 | ✗ ROJO |
## El veredicto sale del arnés, no del log

Las columnas de veredicto son la salida de `matriz.sh` y `demo-memoria.sh`, que corrieron el
gate ellos mismos. **No** salen del log del agente: intenté eso primero y el último
`GATE ROJO` del log de `mat-1`, `mat-5` y `mat-10` contradice el `✓` que el arnés registró
para esas tres celdas. El agente imprime el gate varias veces mientras trabaja, y el último
que imprime no es el veredicto — es el que vio antes de arreglar. Grepear «GATE VERDE/ROJO»
de un transcripto es la misma falla que el método existe para evitar (P2: el juez es un
comando, no el modelo).

`⊘ sin dato` = la corrida no produjo veredicto (plataforma o corte), y no cuenta ni a favor
ni en contra.

## Qué sirve y qué no, para la condición D_unver

Sirven los **16 rechazados** (`✗ ROJO`): tienen el parche que un modelo escribió de verdad
y que un comando reprobó. Es el material que el diseño daba por inexistente.

NO sirven los 3 verdes ni los 3 sin dato (2 sin veredicto + 1 por plataforma), y están acá porque el archivo es el archivo: se
preserva todo y se etiqueta, no se poda hasta que quede lo que convenía.

Faltan todavía los **diagnósticos**: un rechazado trae el parche y el transcripto, no una
redacción de «falló así / se arregla así» con la forma que escribe `recordar_falla`. Esa
redacción hay que producirla, y quién la escriba es la decisión que define si D_unver mide
«verificado vs no verificado» o «bien redactado vs mal redactado».
