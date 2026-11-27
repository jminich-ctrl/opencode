import { describe, it, expect } from 'vitest';

describe('TestIndexHtmlFrontend', () => {
  it('debería crear el archivo frontend/index.html', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const indexPath = path.join(process.cwd(), 'frontend', 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);
  });

  it('debería tener el div root en frontend/index.html', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const indexPath = path.join(process.cwd(), 'frontend', 'index.html');
    const content = fs.readFileSync(indexPath, 'utf-8');
    
    // Debería tener el div con id root
    expect(content).toContain('<div id="root"></div>');
  });

  it('debería tener la referencia al script en frontend/index.html', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const indexPath = path.join(process.cwd(), 'frontend', 'index.html');
    const content = fs.readFileSync(indexPath, 'utf-8');
    
    // Debería tener la referencia al script principal
    expect(content).toContain('<script type="module" src="/src/main.tsx"></script>');
  });

  it('debería tener estructura HTML válida en frontend/index.html', async () => {
    const fs = await import('fs');
    const path = await import('path');
    
    const indexPath = path.join(process.cwd(), 'frontend', 'index.html');
    const content = fs.readFileSync(indexPath, 'utf-8');
    
    // Debería tener estructura básica de HTML
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('<html lang="es">');
    expect(content).toContain('<head>');
    expect(content).toContain('<body>');
    expect(content).toContain('<title>Clasificados</title>');
  });
});