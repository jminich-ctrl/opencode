import { describe, it, expect } from 'vitest';

describe('TestScaffoldingFrontend', () => {
  it('debería tener las dependencias necesarias en package.json', () => {
    // Verificar que el archivo package.json exista
    const fs = require('fs');
    const path = require('path');
    
    const packagePath = path.join(__dirname, '..', 'package.json');
    expect(fs.existsSync(packagePath)).toBe(true);
    
    const packageContent = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    
    // Verificar que tenga las dependencias requeridas
    expect(packageContent.dependencies).toHaveProperty('react');
    expect(packageContent.dependencies).toHaveProperty('react-dom');
    expect(packageContent.devDependencies).toHaveProperty('@vitejs/plugin-react');
    expect(packageContent.devDependencies).toHaveProperty('vite');
    expect(packageContent.devDependencies).toHaveProperty('vitest');
    expect(packageContent.devDependencies).toHaveProperty('jsdom');
    expect(packageContent.devDependencies).toHaveProperty('@testing-library/react');
    
    // Verificar que tenga el script de test
    expect(packageContent.scripts).toHaveProperty('test');
    expect(packageContent.scripts.test).toBe('vitest run');
  });

  it('debería tener el archivo vite.config.ts', () => {
    // Verificar que el archivo vite.config.ts exista
    const fs = require('fs');
    const path = require('path');
    
    const viteConfigPath = path.join(__dirname, '..', 'vite.config.ts');
    expect(fs.existsSync(viteConfigPath)).toBe(true);
  });

  it('debería tener configuración de vite con environment jsdom', () => {
    // Verificar que el contenido del archivo tenga la configuración requerida
    const fs = require('fs');
    const path = require('path');
    
    const viteConfigPath = path.join(__dirname, '..', 'vite.config.ts');
    const content = fs.readFileSync(viteConfigPath, 'utf8');
    
    // Verificar que contenga la configuración requerida
    expect(content).toContain('environment: \'jsdom\'');
    expect(content).toContain('plugins: [react()]');
  });
});