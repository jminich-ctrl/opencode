import pytest
from unittest.mock import patch
from backend.app.servicios.favorites import toggle_favorite_service

class TestFavoritesServicio:
    
    def test_toggle_favorite_service_success(self):
        """Prueba que toggle_favorite_service llame correctamente a la capa de datos."""
        with patch('backend.app.servicios.favorites.toggle_favorite') as mock_toggle:
            # Configurar el mock para devolver True
            mock_toggle.return_value = True
            
            # Llamar al servicio
            result = toggle_favorite_service(1, 2)
            
            # Verificar que se llamó a la función de datos con los parámetros correctos
            mock_toggle.assert_called_once_with(1, 2)
            
            # Verificar que el resultado es el esperado
            assert result is True
    
    def test_toggle_favorite_service_false(self):
        """Prueba que toggle_favorite_service maneje correctamente el caso donde se devuelve False."""
        with patch('backend.app.servicios.favorites.toggle_favorite') as mock_toggle:
            # Configurar el mock para devolver False
            mock_toggle.return_value = False
            
            # Llamar al servicio
            result = toggle_favorite_service(1, 2)
            
            # Verificar que se llamó a la función de datos con los parámetros correctos
            mock_toggle.assert_called_once_with(1, 2)
            
            # Verificar que el resultado es el esperado
            assert result is False

if __name__ == "__main__":
    pytest.main([__file__])