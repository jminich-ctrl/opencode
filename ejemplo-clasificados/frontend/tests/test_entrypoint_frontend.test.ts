import { describe, it, expect } from 'vitest';

describe('TestEntrypointFrontend', () => {
  it('debería crear el archivo frontend/src/main.tsx', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const mainPath = path.join(process.cwd(), 'frontend', 'src', 'main.tsx');
    expect(fs.existsSync(mainPath)).toBe(true);
  });

  it('debería crear el archivo frontend/src/App.jsx', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const appPath = path.join(process.cwd(), 'frontend', 'src', 'App.jsx');
    expect(fs.existsSync(appPath)).toBe(true);
  });

  it('debería tener contenido válido en frontend/src/main.tsx', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const mainPath = path.join(process.cwd(), 'frontend', 'src', 'main.tsx');
    const content = fs.readFileSync(mainPath, 'utf-8');
    
    // Debería tener imports y ReactDOM.render
    expect(content).toContain('React');
    expect(content).toContain('ReactDOM');
    expect(content).toContain('render');
    expect(content).toContain('<App />');
  });

  it('debería tener contenido válido en frontend/src/App.jsx', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const appPath = path.join(process.cwd(), 'frontend', 'src', 'App.jsx');
    const content = fs.readFileSync(appPath, 'utf-8');
    
    // Debería tener un componente básico de React
    expect(content).toContain('function App');
    expect(content).toContain('return');
    expect(content).toContain('<div>');
  });
});