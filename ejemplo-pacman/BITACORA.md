# Bitácora — qué pasó al usar esto de verdad

Registro de las corridas reales. Sirve para dos cosas: ver el método funcionando con
números, y no volver a tropezar con lo mismo.

---

## 2026-09-20 · Primera corrida (T02 + T03 en paralelo)

**Entorno:** OpenCode 1.18.30 · Qwen3.8-27B FP8 como `build` · los 4 modelos calientes.

### Qué se rompió

**1. Dos `opencode run` en paralelo → `Error: database is locked`**

T03 murió a los 2 segundos. OpenCode guarda sesiones en una sola SQLite
(`~/.local/share/opencode/opencode.db`) y dos procesos se pelean por el lock.

*Arreglo:* cada tarea con su propio `XDG_DATA_HOME` dentro del worktree.
*Verificado después:* 3 `opencode run` simultáneos, las tres terminan bien.
*Importante:* aislar solo `XDG_DATA_HOME`, **nunca** `XDG_CONFIG_HOME`, o las tareas
se quedan sin provider ni modelos.

**2. El gate daba VERDE sobre una tarea que no se hizo**

Como T03 murió sin tocar nada, el gate encontró la suite en verde, no vio cambios, y
lo reportó como éxito con un simpático "¿todavía no empezaste?".

*Arreglo:* sin cambios = ROJO.
*Lección:* **un gate que aprueba una tarea vacía es peor que no tener gate**, porque da
confianza falsa. Todo gate necesita un caso "no se hizo nada" y tiene que fallar ahí.

**3. Las tareas ya hechas figuraban "pendiente"**

`estado.sh` deducía el estado solo de la existencia del worktree, así que T01 —hecha y
mergeada— aparecía como pendiente.

*Arreglo:* leer el `**Estado:** ✅` del archivo de tarea.

### Qué salió bien

- Los worktrees: dos tareas, dos ramas, cero interferencia.
- El gate atrapó un error humano: al escribir los tests de T01 puse `(2,2)` como celda
  libre cuando es pared. **El primer bug que encontró el gate fue mío, no del agente.**

### Final de la corrida: las dos tareas fallaron, y el gate igual dijo verde

T02 esperó **20 minutos** al 27B (que se había enfriado por el mantenimiento) y murió con
`{"message":"inference timed out or returned no result"}`. T03 ya había muerto por el lock
de SQLite. Ninguna tocó un archivo.

Y sin embargo las dos reportaron **GATE VERDE**. Tres causas encadenadas, las tres
instructivas:

**4. El worktree congela el código al momento de crearse**

Arreglé `gate.sh` (sin cambios = rojo) *después* de crear los worktrees, así que las
tareas corrieron con la versión vieja del gate. Un worktree se crea desde `HEAD`: lo que
no está commiteado no viaja.

*Arreglo:* commitear los cambios de herramientas **antes** de lanzar. Queda avisado en el runner.

**5. Editar un script de bash mientras corre lo rompe**

`scripts/correr-tarea.sh: line 57: unexpected EOF`. Bash lee el script por partes mientras
lo ejecuta: si lo editás en el medio, sigue leyendo desde un offset que ya no corresponde.

*Arreglo:* no tocar un script en ejecución. Si hay que arreglarlo, se para, se edita y se relanza.

**6. Un error del agente tiene que ganarle al gate**

El gate mira el repo, no al agente. Si el agente nunca llegó a trabajar, el gate ve un
repo sano y aprueba. Ahora el runner marca ROJO si el log tiene un error de OpenCode
(`Error:`, `inference timed out`, `database is locked`), sin importar lo que diga el gate.

*Lección general:* **cada verificador tiene un punto ciego, y el punto ciego del gate es
todo lo que pasa fuera del repo.** Por eso hacen falta las dos señales: que el agente
haya terminado bien, y que el repo quede verde.

### Interrumpida

La corrida se cortó porque el equipo de la plataforma se puso a recargar modelos y todo
quedó frío. Regla que ya aprendimos tres veces: **no medir ni sacar conclusiones mientras
la plataforma está en mantenimiento.**

Pendiente para la próxima: relanzar T02 y T03 con los arreglos puestos, y medir la
concurrencia real por modelo antes de decidir cuántas tareas lanzar juntas.

---

---

## 2026-09-21 · Segunda corrida: el agente mintió sobre el gate

Con el ejecutor cambiado a Qwen3-Coder-30B (ver abajo), **las dos tareas por fin
produjeron código**: T02 escribió `entidades.py` + tests, T03 `juego.py` + tests.
Las dos con el gate en rojo por tests que fallan, que es el ciclo normal.

Pero apareció algo peor que un test roto:

**7. El agente afirmó "GATE VERDE" con el gate en rojo — y el runner le creyó**

En el log de T02:

```
línea  392: GATE ROJO (1 fallo/s)
línea  655: GATE ROJO (1 fallo/s)
línea  745: GATE ROJO (1 fallo/s)
línea 1262: "El gate.sh indica \"GATE VERDE\" (todos los criterios cumplidos)"   ← el agente
línea 1293: GATE ROJO (1 fallo/s)                                              ← el gate real
```

El modelo corrió el gate tres veces, lo vio fallar tres veces, y en su resumen final
escribió que estaba verde. Mi runner buscaba `GATE VERDE` en **todo** el log, así que
matcheó esa frase de la prosa del modelo y reportó la tarea como exitosa.

*Arreglo:* leer **solo** la salida del gate que corre el runner (después de `=== gate ===`),
nunca el log completo.

*Lección, y es la más importante de todas:* **la verificación nunca puede leer lo que el
agente escribe.** No alcanza con pedirle en `AGENTS.md` que no mienta — lo pide, y mintió
igual. El veredicto tiene que venir de ejecutar el comando, capturado en un lugar donde
el agente no pueda escribir.

Es el mismo principio que P2 del método, llevado un paso más lejos: no solo *el juez es
un comando*, sino que **la lectura del veredicto también tiene que estar fuera del alcance
del agente.**

### Sobre el cambio de ejecutor

Qwen3.8-27B (modelo "pensante") escribió 325 y 345 líneas de deliberación sin tocar un
solo archivo, en dos intentos. Cambiado a Qwen3-Coder-30B-A3B (instruct, sin modo
pensante), las dos tareas produjeron código en el primer intento.

**Razonador y ejecutor son perfiles distintos.** El mejor modelo del equipo no es
necesariamente el que tiene que implementar. El research posterior lo confirmó: el
candidato ideal para ejecutor es un modelo que *estructuralmente no puede* deliberar
(Qwen3-Coder-Next no genera bloques `<think>` en absoluto), no uno al que se le pide
por favor que no lo haga.

---

## Plantilla para las próximas entradas

```markdown
## AAAA-MM-DD · <qué se corrió>

**Entorno:** <modelos, versiones, estado del cluster>

| Tarea | Gate 1er intento | Tiempo | Revisión | Notas |
|---|---|---|---|---|
| TNN | verde / rojo | Xm | mergeada / relanzada | |

**Tasa de verde al primer intento:** X de Y
**Qué se rompió:**
**Qué ajustamos en el método:**
```

Esa tabla es la que dice si la descomposición está bien: si el verde al primer intento
baja del 60%, el problema está en cómo escribís las tareas, no en el modelo.
