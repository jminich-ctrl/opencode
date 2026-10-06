// Tipo para los anuncios
export interface Anuncio {
  id: number;
  title: string;
  description: string;
  price: number;
  category: string;
  createdAt: string;
}

/**
 * Busca anuncios por texto y categoría
 * @param texto Texto a buscar
 * @param categoria Categoría opcional para filtrar
 * @returns Promesa con los anuncios encontrados
 */
export async function buscarAnuncios(texto: string, categoria?: string): Promise<Anuncio[]> {
  // Construir la URL con parámetros
  let url = `/api/search?q=${encodeURIComponent(texto)}`;
  if (categoria) {
    url += `&category=${encodeURIComponent(categoria)}`;
  }

  // Hacer la llamada a la API
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`Error en la búsqueda: ${response.status} ${response.statusText}`);
  }
  
  const anuncios: Anuncio[] = await response.json();
  return anuncios;
}