import React, { useState, useEffect } from 'react';
import { getAds } from '../services/ads';
import '../design/_filters.scss';

/**
 * Filtra los anuncios por categoría
 */
export function filterAdsByCategory(ads, category) {
  return ads.filter(ad => ad.category === category);
}

/**
 * Componente que muestra una lista de anuncios.
 */
export default function AdsList() {
  const [ads, setAds] = useState([]);
  const [filteredAds, setFilteredAds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('');

  useEffect(() => {
    const fetchAds = async () => {
      try {
        const data = await getAds();
        setAds(data);
        setFilteredAds(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchAds();
  }, []);

  useEffect(() => {
    if (selectedCategory === '') {
      setFilteredAds(ads);
    } else {
      const filtered = filterAdsByCategory(ads, selectedCategory);
      setFilteredAds(filtered);
    }
  }, [selectedCategory, ads]);

  if (loading) {
    return <div>Cargando anuncios...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  // Obtener categorías únicas para el filtro
  const categories = [...new Set(ads.map(ad => ad.category))];

  return (
    <div className="ads-list">
      <h2>Anuncios</h2>
      
      {/* Filtro por categoría */}
      <div className="filters-container">
        <div className="category-filter">
          <label htmlFor="categoryFilter">Filtrar por categoría:</label>
          <select 
            id="categoryFilter"
            value={selectedCategory} 
            onChange={(e) => setSelectedCategory(e.target.value)}
          >
            <option value="">Todas las categorías</option>
            {categories.map(category => (
              <option key={category} value={category}>{category}</option>
            ))}
          </select>
        </div>
      </div>
      
      {filteredAds.length === 0 ? (
        <p>No hay anuncios disponibles.</p>
      ) : (
        <ul>
          {filteredAds.map((ad) => (
            <li key={ad.id}>
              <h3>{ad.title}</h3>
              <p>{ad.description}</p>
              <p>Precio: ${ad.price}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}