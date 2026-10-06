import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { buscarAnuncios } from '../src/services/search';
import SearchBar from '../src/components/SearchBar';

// Mock del fetch global
const mockFetch = vi.fn();

describe('TestSearchFrontend', () => {
  beforeEach(() => {
    // Mockear el fetch global
    global.fetch = mockFetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('debería buscar anuncios por texto', async () => {
    // Configurar mock
    const mockResponse = [
      {
        id: 1,
        title: 'Anuncio de prueba',
        description: 'Descripción del anuncio',
        price: 10000,
        category: 'autos',
        createdAt: '2023-01-01'
      }
    ];
    
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    // Ejecutar búsqueda
    const resultados = await buscarAnuncios('prueba');
    
    // Verificaciones
    expect(resultados).toHaveLength(1);
    expect(resultados[0].title).toBe('Anuncio de prueba');
    expect(mockFetch).toHaveBeenCalledWith('/api/search?q=prueba');
  });

  it('debería buscar anuncios por texto y categoría', async () => {
    // Configurar mock
    const mockResponse = [
      {
        id: 1,
        title: 'Anuncio de auto',
        description: 'Descripción del anuncio',
        price: 10000,
        category: 'autos',
        createdAt: '2023-01-01'
      }
    ];
    
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    // Ejecutar búsqueda
    const resultados = await buscarAnuncios('auto', 'autos');
    
    // Verificaciones
    expect(resultados).toHaveLength(1);
    expect(resultados[0].category).toBe('autos');
    expect(mockFetch).toHaveBeenCalledWith('/api/search?q=auto&category=autos');
  });

  it('debería manejar errores en la búsqueda', async () => {
    // Configurar mock para error
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error'
    });

    // Verificar que se lance un error
    await expect(buscarAnuncios('prueba')).rejects.toThrow('Error en la búsqueda: 500 Internal Server Error');
  });
});