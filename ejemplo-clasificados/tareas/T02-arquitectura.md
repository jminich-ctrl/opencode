# T02 — Script de arquitectura (_arquitectura.py)

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T01
**Archivos que podés tocar:** scripts/_arquitectura.py
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Generar y validar que la arquitectura de capas del backend sigue la dirección correcta: `app/datos` → `app/servicios` → `app/rutas`.

## Alcance

Entra:
- Leer la estructura de carpetas bajo `backend/app`.
- Verificar que cada módulo solo importe de capas anteriores.
- Salida: imprimir reporte de validación y devolver código de salida 0/1.

No entra:
- Modificar código existente.

## Contrato

```python
def validar_arquitectura(base_path: str = "backend/app") -> int:
    """Valida que la arquitectura de capas respete el orden datos->servicios->rutas.
    Devuelve 0 si todo está correcto, 1 si hay violaciones.
    """
```

## Tests (ya escritos, fallando)

Los tests de esta tarea **ya están en el repo y fallan**. Archivo: `tests/test_arquitectura.py`, clase `TestArquitectura`.

## Criterio de terminado

- [ ] Script `_arquitectura.py` creado y ejecutable.
- [ ] Validación pasa en el repositorio.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A
