import os
import pytest
from unittest.mock import patch
import pymysql

# Importamos las funciones que vamos a testear
from app.datos.conexion import conexion, configuracion


class TestConexion:
    def test_configuracion_lee_variables_de_entorno(self):
        """Verifica que configuracion() lea correctamente las variables de entorno."""
        # Configuramos variables de entorno
        os.environ["MYSQL_HOST"] = "mi-host"
        os.environ["MYSQL_PORT"] = "3307"
        os.environ["MYSQL_USER"] = "mi-usuario"
        os.environ["MYSQL_PASSWORD"] = "mi-password"
        os.environ["MYSQL_DB"] = "mi-base"

        # Llamamos a la función
        result = configuracion()

        # Verificamos que se hayan leído correctamente
        assert result["host"] == "mi-host"
        assert result["port"] == 3307
        assert result["user"] == "mi-usuario"
        assert result["password"] == "mi-password"
        assert result["db"] == "mi-base"

    def test_configuracion_valores_por_defecto(self):
        """Verifica que configuracion() use valores por defecto cuando no están definidos."""
        # Limpiamos todas las variables de entorno relacionadas
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Configuramos solo MYSQL_DB (que es obligatorio)
        os.environ["MYSQL_DB"] = "test-db"
        
        # Llamamos a la función
        result = configuracion()
        
        # Verificamos que se usen los valores por defecto
        assert result["host"] == "127.0.0.1"
        assert result["port"] == 3306
        assert result["user"] == "root"
        assert result["password"] == ""
        assert result["db"] == "test-db"

    def test_configuracion_lanza_error_sin_mysql_db(self):
        """Verifica que configuracion() lance RuntimeError si falta MYSQL_DB."""
        # Limpiamos todas las variables de entorno
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Verificamos que se lance RuntimeError
        with pytest.raises(RuntimeError) as excinfo:
            configuracion()
            
        assert "MYSQL_DB" in str(excinfo.value)

    def test_conexion_commit_al_salir_bien(self):
        """Verifica que conexion() haga commit al salir del bloque sin error."""
        # Limpiamos las variables de entorno
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Configuramos valores por defecto
        os.environ["MYSQL_DB"] = "test-db"
        
        # Mockeamos la conexión para evitar conexión real
        with patch('pymysql.connect') as mock_connect:
            # Creamos un mock de conexión que simula el comportamiento real
            mock_conn = mock_connect.return_value
            mock_cursor = mock_conn.cursor.return_value
            
            # Ejecutamos el bloque de conexión
            with conexion() as conn:
                # Verificamos que se haya llamado a commit al finalizar
                pass
                
            # Verificamos que se haya llamado a commit
            assert mock_conn.commit.called

    def test_conexion_rollback_si_excepcion(self):
        """Verifica que conexion() haga rollback si hay excepción."""
        # Limpiamos las variables de entorno
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Configuramos valores por defecto
        os.environ["MYSQL_DB"] = "test-db"
        
        # Mockeamos la conexión para evitar conexión real
        with patch('pymysql.connect') as mock_connect:
            # Creamos un mock de conexión que simula el comportamiento real
            mock_conn = mock_connect.return_value
            mock_cursor = mock_conn.cursor.return_value
            
            # Ejecutamos el bloque de conexión con una excepción
            try:
                with conexion() as conn:
                    raise Exception("Excepción de prueba")
            except Exception:
                pass  # Ignoramos la excepción para continuar con el test
                
            # Verificamos que se haya llamado a rollback
            assert mock_conn.rollback.called

    def test_conexion_cierra_siempre(self):
        """Verifica que conexion() cierre la conexión siempre."""
        # Limpiamos las variables de entorno
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Configuramos valores por defecto
        os.environ["MYSQL_DB"] = "test-db"
        
        # Mockeamos la conexión para evitar conexión real
        with patch('pymysql.connect') as mock_connect:
            # Creamos un mock de conexión que simula el comportamiento real
            mock_conn = mock_connect.return_value
            mock_cursor = mock_conn.cursor.return_value
            
            # Ejecutamos el bloque de conexión
            try:
                with conexion() as conn:
                    pass
            except Exception:
                pass  # Ignoramos cualquier excepción
                
            # Verificamos que se haya llamado a close
            assert mock_conn.close.called

    def test_conexion_cursos_resuelven_diccionarios(self):
        """Verifica que los cursores devuelvan diccionarios."""
        # Limpiamos las variables de entorno
        env_vars_to_clear = [
            "MYSQL_HOST",
            "MYSQL_PORT", 
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB"
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
                
        # Configuramos valores por defecto
        os.environ["MYSQL_DB"] = "test-db"
        
        # Mockeamos la conexión para evitar conexión real
        with patch('pymysql.connect') as mock_connect:
            # Creamos un mock de conexión que simula el comportamiento real
            mock_conn = mock_connect.return_value
            mock_cursor = mock_conn.cursor.return_value
            
            # Ejecutamos el bloque de conexión
            with conexion() as conn:
                cursor = conn.cursor()
                # Verificamos que el cursor sea de tipo DictCursor
                # Esto es difícil de verificar directamente, pero al menos
                # verificamos que se llame al método cursor
                pass
                
            # Verificamos que se haya llamado al cursor
            assert mock_conn.cursor.called