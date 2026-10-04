import { describe, it, expect } from 'vitest';
import * as sass from 'sass';

describe('TestDesignSystemFrontend', () => {
  it('debería compilar sin errores', () => {
    // Esta prueba verifica que el archivo main.scss se pueda compilar
    // sin errores relacionados con imports o variables/mixins no definidos
    expect(() => {
      sass.compile('frontend/src/design/main.scss');
    }).not.to.throw();
  });

  it('debería aplicar estilos base a body', () => {
    // Esta prueba verifica que los estilos base se apliquen correctamente
    const result = sass.compile('frontend/src/design/main.scss');
    const css = result.css;
    
    // Verificar que haya una regla para body con color y font-family resueltos
    expect(css).toContain('body {');
    expect(css).toContain('color: #333333;');
    expect(css).toContain('font-family: "Arial", sans-serif;');
  });

  it('debería aplicar correctamente los mixins', () => {
    // Esta prueba verifica que los mixins definidos en _mixins.scss funcionen
    const result = sass.compile('frontend/src/design/main.scss');
    const css = result.css;
    
    // Verificar que el mixin shadow-box se aplique correctamente
    expect(css).toContain('box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);');
  });
});