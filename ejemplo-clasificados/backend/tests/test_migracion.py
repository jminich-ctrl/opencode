import pytest
import os

# Rutas relativas a la raíz del proyecto, que es desde donde el método corre siempre la
# suite (scripts/correr-suite.sh). La primera versión de este archivo clavaba la ruta
# absoluta del worktree temporal donde el agente lo escribió, así que pasaba ahí adentro
# y fallaba en todos lados a partir del merge.
MIGRACIONES = os.path.join('backend', 'migraciones')
INICIAL = os.path.join(MIGRACIONES, '001_initial.sql')
REVERSA = os.path.join(MIGRACIONES, '001_initial_down.sql')

class TestMigracion:
    """Tests para la migración inicial de la base de datos."""
    
    def test_archivos_migracion_existen(self):
        """Verifica que los archivos de migración existen."""
        initial_file = INICIAL
        down_file = REVERSA
        
        assert os.path.exists(initial_file), "El archivo de migración inicial no existe"
        assert os.path.exists(down_file), "El archivo de reversa no existe"
        
        # Verificar que los archivos no están vacíos
        assert os.path.getsize(initial_file) > 0, "El archivo de migración inicial está vacío"
        assert os.path.getsize(down_file) > 0, "El archivo de reversa está vacío"
        
    def test_esquema_correcto(self):
        """Verifica que el esquema contiene las tablas requeridas."""
        initial_file = INICIAL
        
        with open(initial_file, 'r') as f:
            content = f.read()
            
        # Verificar que contiene las tablas requeridas
        assert 'CREATE TABLE usuarios' in content
        assert 'CREATE TABLE categorias' in content
        assert 'CREATE TABLE anuncios' in content
        assert 'CREATE TABLE favoritos' in content
        assert 'CREATE TABLE mensajes' in content
        assert 'CREATE TABLE sesiones' in content
        
        # Las columnas que PLAN.md cierra en G0, con los nombres del plan.
        #
        # Esta sección afirmaba OTRO esquema: `precio`, `created_at`, `updated_at`,
        # `password` — nombres en inglés que el plan nunca tuvo. El plan dice
        # `precio_centavos`, `creado_en`, `actualizado_en`, `clave_hash`, `clave_salt`, y
        # la tarea T03 lo pedía en negrita: «No inventes columnas ni cambies nombres».
        # O sea que el test contradecía el plan que venía a codificar, y reprobaba una
        # migración correcta. El gate no podía verlo: compara la implementación contra los
        # tests, nunca los tests contra el plan.
        for columna in (
            'id INT AUTO_INCREMENT PRIMARY KEY',
            'email VARCHAR(255) UNIQUE NOT NULL',   # usuarios
            'clave_hash', 'clave_salt',
            'nombre VARCHAR(255) UNIQUE NOT NULL',  # categorias
            'orden',
            'precio_centavos INT NOT NULL',         # anuncios
            'titulo', 'descripcion', 'foto_url',
            'creado_en DATETIME DEFAULT CURRENT_TIMESTAMP',
            'actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
            'de_usuario_id', 'a_usuario_id', 'cuerpo',   # mensajes
            'token VARCHAR(255) PRIMARY KEY', 'expira_en',  # sesiones
        ):
            assert columna in content, f"falta la columna del plan: {columna}"

        # Clave compuesta en favoritos, que el plan cierra explícitamente.
        assert 'PRIMARY KEY (usuario_id, anuncio_id)' in content

        # Verificar que tiene las claves foráneas
        assert 'FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE' in content
        assert 'FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE' in content

    def test_reversa_correcta(self):
        """Verifica que el script de reversa tiene el orden correcto."""
        down_file = REVERSA
        
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