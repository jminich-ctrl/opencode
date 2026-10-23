import pytest
from unittest.mock import patch
from backend.app.servicios.ads import crear_anuncio, obtener_anuncio, actualizar_anuncio, eliminar_anuncio


class TestAdsServicio:
    
    def test_crear_anuncio_valido(self):
        """Debe crear un anuncio válido y devolver su ID"""
        with patch('backend.app.datos.ads.insert_ad', return_value=123) as mock_insert:
            result = crear_anuncio(7, 1, "título", "descripción", 10000)
            assert result == 123
            mock_insert.assert_called_once_with(7, 1, "título", "descripción", 10000)
    
    def test_crear_anuncio_titulo_vacio(self):
        """Debe lanzar ValueError si el título está vacío"""
        with pytest.raises(ValueError, match="Título no puede estar vacío"):
            crear_anuncio(7, 1, "", "descripción", 10000)
    
    def test_crear_anuncio_descripcion_vacia(self):
        """Debe lanzar ValueError si la descripción está vacía"""
        with pytest.raises(ValueError, match="Descripción no puede estar vacía"):
            crear_anuncio(7, 1, "título", "", 10000)
    
    def test_crear_anuncio_precio_negativo(self):
        """Debe lanzar ValueError si el precio es negativo"""
        with pytest.raises(ValueError, match="Precio no puede ser negativo"):
            crear_anuncio(7, 1, "título", "descripción", -100)
    
    def test_crear_anuncio_precio_no_entero(self):
        """Debe lanzar ValueError si el precio no es un entero"""
        with pytest.raises(ValueError, match="Precio debe ser un número entero"):
            crear_anuncio(7, 1, "título", "descripción", 100.5)
    
    def test_obtener_anuncio(self):
        """Debe obtener un anuncio por ID"""
        with patch('backend.app.datos.ads.get_ad_by_id', return_value={"id": 1, "titulo": "título"}) as mock_get:
            result = obtener_anuncio(1)
            assert result == {"id": 1, "titulo": "título"}
            mock_get.assert_called_once_with(1)
    
    def test_obtener_anuncio_inexistente(self):
        """Debe devolver None si el anuncio no existe"""
        with patch('backend.app.datos.ads.get_ad_by_id', return_value=None) as mock_get:
            result = obtener_anuncio(999)
            assert result is None
            mock_get.assert_called_once_with(999)
    
    def test_actualizar_anuncio_valido(self):
        """Debe actualizar un anuncio válido y devolver True"""
        with patch('backend.app.datos.ads.update_ad', return_value=True) as mock_update:
            result = actualizar_anuncio(1, 7, "título", "descripción", 10000)
            assert result is True
            mock_update.assert_called_once_with(1, 7, "título", "descripción", 10000)
    
    def test_actualizar_anuncio_titulo_vacio(self):
        """Debe lanzar ValueError si el título está vacío"""
        with pytest.raises(ValueError, match="Título no puede estar vacío"):
            actualizar_anuncio(1, 7, "", "descripción", 10000)
    
    def test_actualizar_anuncio_descripcion_vacia(self):
        """Debe lanzar ValueError si la descripción está vacía"""
        with pytest.raises(ValueError, match="Descripción no puede estar vacía"):
            actualizar_anuncio(1, 7, "título", "", 10000)
    
    def test_actualizar_anuncio_precio_negativo(self):
        """Debe lanzar ValueError si el precio es negativo"""
        with pytest.raises(ValueError, match="Precio no puede ser negativo"):
            actualizar_anuncio(1, 7, "título", "descripción", -100)
    
    def test_actualizar_anuncio_precio_no_entero(self):
        """Debe lanzar ValueError si el precio no es un entero"""
        with pytest.raises(ValueError, match="Precio debe ser un número entero"):
            actualizar_anuncio(1, 7, "título", "descripción", 100.5)
    
    def test_eliminar_anuncio_valido(self):
        """Debe eliminar un anuncio válido y devolver True"""
        with patch('backend.app.datos.ads.delete_ad', return_value=True) as mock_delete:
            result = eliminar_anuncio(1, 7)
            assert result is True
            mock_delete.assert_called_once_with(1, 7)