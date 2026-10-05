# T30 — Scaffolding Vite

**Estado:** ✅ hecha
**Depende de:** T01
**Archivos que podés tocar:** frontend/package.json, frontend/vite.config.ts
**Prohibido tocar:** 
**Modelo:** el del agente `build` (el ejecutor, un modelo no pensante): `opencode run`, que usa el runner, no puede elegir un subagente

## Objetivo

Crear el proyecto Vite con su package.json y vite.config.ts

## El corredor de tests es parte del andamiaje

El plan tiene catorce archivos `.test.ts` y **ninguna otra tarea declara con qué se corren**.
Entonces los declara esta: `package.json` tiene que traer, en `devDependencies`, `vite`,
`@vitejs/plugin-react`, `vitest`, `jsdom`, `@testing-library/react` y `sass`, más un script
`"test": "vitest run"`.

Y `vite.config.ts` tiene que configurar el entorno de los tests como jsdom, que en la
sintaxis de Vite es la clave `environment` dentro de `test`:

```ts
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
});
```

**Cómo verificar eso no es leyendo el archivo.** Un test que chequea que el texto del
config contenga cierta cadena pasa o falla según cómo esté escrito, no según qué haga; y si
la cadena que busca no es sintaxis válida, no puede pasar nunca. Lo que prueba que el
entorno es jsdom de verdad es que exista el DOM:

```ts
expect(typeof document).not.toBe('undefined');
```

Eso falla con el config sin configurar y pasa con él, que es lo que un test tiene que hacer.

**No borres lo que ya estaba declarado.** El `package.json` que encontrás lo creó T01:
ampliálo, no lo reescribas de cero. En el primer intento esta tarea perdió
`@vitejs/plugin-react`, que su propio `vite.config.ts` importaba, y la validación se cayó
con un «Cannot find package» que no decía nada de la causa.

Sin eso, cada tarea de frontend se cae con «falta el corredor», que no es culpa de quien
escribe el test.

## Alcance

Entra:
- Generar `package.json` con dependencias mínimas (react, react-dom, vite).
- Crear `vite.config.ts` básico.

No entra:
- Crear archivos de entrada como main.ts o App.jsx

## Contrato

N/A

## Tests

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `frontend/tests/test_scaffolding_frontend.test.ts`, clase `TestScaffoldingFrontend`.

## Criterio de terminado

- [ ] Archivo `frontend/package.json` creado con dependencias de Vite y React.
- [ ] Archivo `frontend/vite.config.ts` creado con configuración básica.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    bash scripts/gate.sh

## Verificación humana (si aplica)

N/A