import pytest
from unittest.mock import patch, MagicMock
from backend.app.servicios.ads import crear_anuncio, obtener_anuncio, actualizar_anuncio, eliminar_anuncio
from backend.app.datos.ads import insert_ad, get_ad_by_id, update_ad, delete_ad

class TestAdsBackend:
    
    def test_crear_anuncio_valido(self):
        """Debe crear un anuncio válido con título, descripción y precio"""
        # Mockear la función de inserción
        with patch('backend.app.datos.ads.insert_ad') as mock_insert:
            mock_insert.return_value = 123
            
            # Llamar a la función
            ad_id = crear_anuncio(
                titulo="Anuncio de prueba",
                descripcion="Descripción de prueba",
                precio=1000
            )
            
            # Verificar que se llamó correctamente
            assert ad_id == 123
            mock_insert.assert_called_once_with(
                "Anuncio de prueba",
                "Descripción de prueba",
                1000
            )
    
    def test_crear_anuncio_titulo_invalido(self):
        """Debe fallar al crear un anuncio con título inválido"""
        with pytest.raises(ValueError, match="Título inválido"):
            crear_anuncio("", "Descripción de prueba", 1000)
        
        with pytest.raises(ValueError, match="Título inválido"):
            crear_anuncio(None, "Descripción de prueba", 1000)
    
    def test_crear_anuncio_descripcion_invalida(self):
        """Debe fallar al crear un anuncio con descripción inválida"""
        with pytest.raises(ValueError, match="Descripción inválida"):
            crear_anuncio("Anuncio de prueba", "", 1000)
        
        with pytest.raises(ValueError, match="Descripción inválida"):
            crear_anuncio("Anuncio de prueba", None, 1000)
    
    def test_crear_anuncio_precio_invalido(self):
        """Debe fallar al crear un anuncio con precio inválido"""
        with pytest.raises(ValueError, match="Precio inválido"):
            crear_anuncio("Anuncio de prueba", "Descripción de prueba", -100)
        
        with pytest.raises(ValueError, match="Precio inválido"):
            crear_anuncio("Anuncio de prueba", "Descripción de prueba", None)
    
    def test_obtener_anuncio_existente(self):
        """Debe obtener un anuncio existente"""
        # Mockear la función de obtención
        with patch('backend.app.datos.ads.get_ad_by_id') as mock_get:
            mock_get.return_value = {
                "id": 123,
                "titulo": "Anuncio de prueba",
                "descripcion": "Descripción de prueba",
                "precio": 1000
            }
            
            # Llamar a la función
            ad = obtener_anuncio(123)
            
            # Verificar que se llamó correctamente
            assert ad["id"] == 123
            assert ad["titulo"] == "Anuncio de prueba"
            mock_get.assert_called_once_with(123)
    
    def test_obtener_anuncio_inexistente(self):
        """Debe fallar al obtener un anuncio inexistente"""
        with patch('backend.app.datos.ads.get_ad_by_id') as mock_get:
            mock_get.return_value = None
            
            # Llamar a la función
            result = obtener_anuncio(999)
            
            # Verificar que se devolvió None
            assert result is None
            mock_get.assert_called_once_with(999)
    
    def test_actualizar_anuncio_valido(self):
        """Debe actualizar un anuncio válido"""
        # Mockear la función de actualización
        with patch('backend.app.datos.ads.update_ad') as mock_update:
            mock_update.return_value = True
            
            # Llamar a la función
            success = actualizar_anuncio(
                123,
                titulo="Anuncio actualizado",
                descripcion="Descripción actualizada",
                precio=2000
            )
            
            # Verificar que se llamó correctamente
            assert success is True
            mock_update.assert_called_once_with(
                123,
                "Anuncio actualizado",
                "Descripción actualizada",
                2000
            )
    
    def test_actualizar_anuncio_inexistente(self):
        """Debe fallar al actualizar un anuncio inexistente"""
        with patch('backend.app.datos.ads.update_ad') as mock_update:
            mock_update.return_value = False
            
            # Llamar a la función
            success = actualizar_anuncio(999, "Anuncio actualizado", "Descripción actualizada", 2000)
            
            # Verificar que se devolvió False
            assert success is False
            mock_update.assert_called_once_with(999, "Anuncio actualizado", "Descripción actualizada", 2000)
    
    def test_eliminar_anuncio_existente(self):
        """Debe eliminar un anuncio existente"""
        # Mockear la función de eliminación
        with patch('backend.app.datos.ads.delete_ad') as mock_delete:
            mock_delete.return_value = True
            
            # Llamar a la función
            success = eliminar_anuncio(123)
            
            # Verificar que se llamó correctamente
            assert success is True
            mock_delete.assert_called_once_with(123)
    
    def test_eliminar_anuncio_inexistente(self):
        """Debe fallar al eliminar un anuncio inexistente"""
        with patch('backend.app.datos.ads.delete_ad') as mock_delete:
            mock_delete.return_value = False
            
            # Llamar a la función
            success = eliminar_anuncio(999)
            
            # Verificar que se devolvió False
            assert success is False
            mock_delete.assert_called_once_with(999)