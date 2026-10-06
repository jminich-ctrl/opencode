import { useState } from 'react';
import { buscarAnuncios } from '../services/search';

const SearchBar = () => {
  const [texto, setTexto] = useState('');
  const [categoria, setCategoria] = useState('');
  const [resultados, setResultados] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  // Categorías disponibles (pueden venir de una fuente externa)
  const categorias = [
    '',
    'autos',
    'inmuebles',
    'electrodomesticos',
    'ropa',
    'muebles'
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setCargando(true);
    setError(null);
    
    try {
      const resultadosBusqueda = await buscarAnuncios(texto, categoria || undefined);
      setResultados(resultadosBusqueda);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="search-bar">
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Buscar anuncios..."
          className="search-input"
        />
        <select
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          className="category-select"
        >
          {categorias.map((cat) => (
            <option key={cat} value={cat}>
              {cat ? cat.charAt(0).toUpperCase() + cat.slice(1) : 'Todas las categorías'}
            </option>
          ))}
        </select>
        <button type="submit" disabled={cargando} className="search-button">
          {cargando ? 'Buscando...' : 'Buscar'}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}
      
      {resultados.length > 0 && (
        <div className="search-results">
          <h3>Resultados ({resultados.length})</h3>
          <ul>
            {resultados.map((anuncio) => (
              <li key={anuncio.id} className="result-item">
                <strong>{anuncio.title}</strong> - {anuncio.category}
                <p>{anuncio.description}</p>
                <span>${anuncio.price}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default SearchBar;