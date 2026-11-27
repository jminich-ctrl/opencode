import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

/**
 * TestImportDisenoFrontend
 * 
 * Verifica que el sistema de diseño se importe correctamente en el punto de entrada
 * del frontend.
 */
describe('TestImportDisenoFrontend', () => {
  it('debería importar main.scss en main.tsx', () => {
    const mainPath = resolve('frontend/src/main.tsx');
    const content = readFileSync(mainPath, 'utf-8');
    
    // Verifica que se importe el archivo de diseño
    expect(content).toContain('./design/main.scss');
  });
});