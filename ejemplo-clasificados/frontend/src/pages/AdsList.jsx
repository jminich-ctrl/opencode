import React, { useState, useEffect } from 'react';
import { getAds } from '../services/ads';

/**
 * Componente que muestra una lista de anuncios.
 */
export default function AdsList() {
  const [ads, setAds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAds = async () => {
      try {
        const data = await getAds();
        setAds(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchAds();
  }, []);

  if (loading) {
    return <div>Cargando anuncios...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="ads-list">
      <h2>Anuncios</h2>
      {ads.length === 0 ? (
        <p>No hay anuncios disponibles.</p>
      ) : (
        <ul>
          {ads.map((ad) => (
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