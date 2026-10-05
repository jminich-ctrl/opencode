import { describe, it, expect, vi, beforeEach } from 'vitest';
import { registrarUsuario } from '../src/services/register';

// Mock del fetch global
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('TestRegisterFrontend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('debería enviar datos al backend al registrar usuario', async () => {
    // Configurar mock para respuesta exitosa
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    });

    await registrarUsuario('test@example.com', 'password123');

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/register',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: 'test@example.com',
          password: 'password123',
        }),
      }
    );
  });

  it('debería manejar errores de registro', async () => {
    // Configurar mock para respuesta con error
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: vi.fn().mockResolvedValue({
        detail: 'Email already in use'
      }),
    });

    try {
      await registrarUsuario('test@example.com', 'password123');
      expect.fail('Debería haber lanzado un error');
    } catch (error) {
      expect(error.message).toBe('Email already in use');
    }
  });

  it('debería manejar errores de red', async () => {
    // Configurar mock para error de red
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    try {
      await registrarUsuario('test@example.com', 'password123');
      expect.fail('Debería haber lanzado un error');
    } catch (error) {
      expect(error.message).toBe('Network error');
    }
  });
});