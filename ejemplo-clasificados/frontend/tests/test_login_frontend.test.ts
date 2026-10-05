import { describe, it, expect, vi, beforeEach } from 'vitest';
import { login } from '../src/services/auth';

// Mock del fetch global
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('TestLoginFrontend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Limpiar cualquier cookie previa
    document.cookie = 'session=';
  });

  it('debería hacer login exitoso y guardar la cookie', async () => {
    // Configurar el mock para devolver una respuesta exitosa
    mockFetch.mockResolvedValueOnce({
      ok: true,
      headers: new Map([['set-cookie', 'session=abc123']]),
    });

    await login('usuario', 'contraseña');

    // Verificar que fetch fue llamado con los parámetros correctos
    expect(mockFetch).toHaveBeenCalledWith(
      '/login',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'usuario',
          password: 'contraseña'
        })
      }
    );

    // Verificar que la cookie fue guardada
    expect(document.cookie).toContain('session=abc123');
  });

  it('debería fallar si el login retorna error', async () => {
    // Configurar el mock para devolver una respuesta con error
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: vi.fn().mockResolvedValue({ error: 'Credenciales inválidas' }),
    });

    try {
      await login('usuario', 'contraseña');
      expect.fail('Debería haber lanzado un error');
    } catch (error) {
      expect(error.message).toBe('Credenciales inválidas');
    }

    // Verificar que fetch fue llamado con los parámetros correctos
    expect(mockFetch).toHaveBeenCalledWith(
      '/login',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'usuario',
          password: 'contraseña'
        })
      }
    );
  });
});