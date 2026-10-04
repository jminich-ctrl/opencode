import pytest
import os

class TestMigracion:
    """Tests para la migración inicial de la base de datos."""
    
    def test_archivos_migracion_existen(self):
        """Verifica que los archivos de migración existen."""
        initial_file = '/Users/jose/tests-T03/ejemplo-clasificados/backend/migraciones/001_initial.sql'
        down_file = '/Users/jose/tests-T03/ejemplo-clasificados/backend/migraciones/001_initial_down.sql'
        
        assert os.path.exists(initial_file), "El archivo de migración inicial no existe"
        assert os.path.exists(down_file), "El archivo de reversa no existe"
        
        # Verificar que los archivos no están vacíos
        assert os.path.getsize(initial_file) > 0, "El archivo de migración inicial está vacío"
        assert os.path.getsize(down_file) > 0, "El archivo de reversa está vacío"
        
    def test_esquema_correcto(self):
        """Verifica que el esquema contiene las tablas requeridas."""
        initial_file = '/Users/jose/tests-T03/ejemplo-clasificados/backend/migraciones/001_initial.sql'
        
        with open(initial_file, 'r') as f:
            content = f.read()
            
        # Verificar que contiene las tablas requeridas
        assert 'CREATE TABLE usuarios' in content
        assert 'CREATE TABLE categorias' in content
        assert 'CREATE TABLE anuncios' in content
        assert 'CREATE TABLE favoritos' in content
        assert 'CREATE TABLE mensajes' in content
        assert 'CREATE TABLE sesiones' in content
        
        # Verificar que tiene las columnas requeridas
        assert 'id INT AUTO_INCREMENT PRIMARY KEY' in content
        assert 'nombre VARCHAR(255) NOT NULL' in content
        assert 'email VARCHAR(255) UNIQUE NOT NULL' in content
        assert 'password VARCHAR(255) NOT NULL' in content
        assert 'precio INT NOT NULL' in content
        assert 'created_at DATETIME DEFAULT CURRENT_TIMESTAMP' in content
        assert 'updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP' in content
        
        # Verificar que tiene las claves foráneas
        assert 'FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE' in content
        assert 'FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE' in content
        
    def test_reversa_correcta(self):
        """Verifica que el script de reversa tiene el orden correcto."""
        down_file = '/Users/jose/tests-T03/ejemplo-clasificados/backend/migraciones/001_initial_down.sql'
        
        with open(down_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith('--')]
            
        # Verificar que contiene las tablas en orden correcto (inverso al de creación)
        drop_statements = [line for line in lines if line.startswith('DROP TABLE')]
        assert len(drop_statements) == 6, f"Se esperaban 6 sentencias DROP, se encontraron {len(drop_statements)}"
        
        # Verificar que las tablas se eliminan en orden inverso
        # sesiones, mensajes, favoritos, anuncios, usuarios, categorias
        expected_order = [
            'DROP TABLE IF EXISTS sesiones;',
            'DROP TABLE IF EXISTS mensajes;',
            'DROP TABLE IF EXISTS favoritos;',
            'DROP TABLE IF EXISTS anuncios;',
            'DROP TABLE IF EXISTS usuarios;',
            'DROP TABLE IF EXISTS categorias;'
        ]
        
        assert drop_statements == expected_order, f"El orden de DROP no es correcto. Se esperaba {expected_order}, se obtuvo {drop_statements}"