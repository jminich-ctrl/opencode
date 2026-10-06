import React, { useState, useEffect } from 'react';
import { getAd } from '../services/ads';

/**
 * Componente que muestra los detalles de un anuncio específico.
 */
export default function AdDetail({ id }) {
  const [ad, setAd] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAd = async () => {
      try {
        const data = await getAd(id);
        setAd(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    if (id) {
      fetchAd();
    }
  }, [id]);

  if (loading) {
    return <div>Cargando anuncio...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!ad) {
    return <div>Anuncio no encontrado.</div>;
  }

  return (
    <div className="ad-detail">
      <h2>{ad.title}</h2>
      <p>{ad.description}</p>
      <p>Precio: ${ad.price}</p>
      {ad.image && <img src={ad.image} alt={ad.title} />}
    </div>
  );
}