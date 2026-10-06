/**
 * Obtiene la lista de anuncios desde la API.
 * @returns Una promesa que resuelve en un array de anuncios.
 */
export async function getAds(): Promise<any[]> {
  const response = await fetch('/api/ads');
  
  if (!response.ok) {
    throw new Error('Error al obtener los anuncios');
  }
  
  return response.json();
}

/**
 * Obtiene un anuncio específico por su ID desde la API.
 * @param id - El ID del anuncio a obtener.
 * @returns Una promesa que resuelve en el anuncio solicitado.
 */
export async function getAd(id: string): Promise<any> {
  const response = await fetch(`/api/ads/${id}`);
  
  if (!response.ok) {
    throw new Error('Error al obtener el anuncio');
  }
  
  return response.json();
}