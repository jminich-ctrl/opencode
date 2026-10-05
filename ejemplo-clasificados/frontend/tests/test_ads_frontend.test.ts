import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('TestAdsFrontend', () => {
  beforeEach(() => {
    // Limpiar mocks antes de cada test
    mockFetch.mockClear();
  });

  it('debería definir el servicio ads.ts con funciones getAds y getAd', async () => {
    // Importar dinámicamente el servicio para asegurar que se cargue correctamente
    const adsService = await import('../src/services/ads');
    
    // Verificar que existan las funciones requeridas
    expect(typeof adsService.getAds).toBe('function');
    expect(typeof adsService.getAd).toBe('function');
  });

  it('debería obtener la lista de anuncios desde /api/ads', async () => {
    // Mock de respuesta de la API
    const mockAds = [
      { id: '1', title: 'Anuncio 1', description: 'Descripción 1', price: 10000 },
      { id: '2', title: 'Anuncio 2', description: 'Descripción 2', price: 20000 }
    ];
    
    mockFetch.mockResolvedValueOnce({
      json: vi.fn().mockResolvedValue(mockAds),
      ok: true
    });

    const adsService = await import('../src/services/ads');
    const ads = await adsService.getAds();
    
    // Verificar que se hizo la llamada correcta
    expect(mockFetch).toHaveBeenCalledWith('/api/ads');
    
    // Verificar que se devolvieron los datos esperados
    expect(ads).toEqual(mockAds);
  });

  it('debería obtener un anuncio específico desde /api/ads/{id}', async () => {
    // Mock de respuesta de la API para un anuncio específico
    const mockAd = { id: '1', title: 'Anuncio 1', description: 'Descripción 1', price: 10000 };
    
    mockFetch.mockResolvedValueOnce({
      json: vi.fn().mockResolvedValue(mockAd),
      ok: true
    });

    const adsService = await import('../src/services/ads');
    const ad = await adsService.getAd('1');
    
    // Verificar que se hizo la llamada correcta
    expect(mockFetch).toHaveBeenCalledWith('/api/ads/1');
    
    // Verificar que se devolvió el dato esperado
    expect(ad).toEqual(mockAd);
  });

  it('debería tener el componente AdsList.jsx', async () => {
    // Verificar que el archivo exista
    const fs = require('fs');
    const path = require('path');
    
    const adsListPath = path.join(__dirname, '..', 'src', 'pages', 'AdsList.jsx');
    expect(fs.existsSync(adsListPath)).toBe(true);
  });

  it('debería tener el componente AdDetail.jsx', async () => {
    // Verificar que el archivo exista
    const fs = require('fs');
    const path = require('path');
    
    const adDetailPath = path.join(__dirname, '..', 'src', 'pages', 'AdDetail.jsx');
    expect(fs.existsSync(adDetailPath)).toBe(true);
  });
});