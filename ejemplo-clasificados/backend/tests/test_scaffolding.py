import unittest
import os
from pathlib import Path

class TestScaffolding(unittest.TestCase):
    
    def test_estructura_carpetas_backend(self):
        """Verifica que se hayan creado las carpetas requeridas en backend/app"""
        expected_dirs = [
            "backend/app/datos",
            "backend/app/servicios", 
            "backend/app/rutas"
        ]
        
        for dir_path in expected_dirs:
            self.assertTrue(
                os.path.exists(dir_path), 
                f"No se encontró el directorio {dir_path}"
            )
            
    def test_archivo_requirements_txt(self):
        """Verifica que el archivo requirements.txt exista con contenido"""
        requirements_path = "backend/requirements.txt"
        self.assertTrue(
            os.path.exists(requirements_path),
            "No se encontró el archivo backend/requirements.txt"
        )
        
        with open(requirements_path, 'r') as f:
            content = f.read()
            self.assertTrue(
                len(content.strip()) > 0,
                "El archivo backend/requirements.txt está vacío"
            )
            
    def test_archivo_package_json(self):
        """Verifica que el archivo package.json exista con contenido"""
        package_path = "frontend/package.json"
        self.assertTrue(
            os.path.exists(package_path),
            "No se encontró el archivo frontend/package.json"
        )
        
        with open(package_path, 'r') as f:
            content = f.read()
            self.assertTrue(
                len(content.strip()) > 0,
                "El archivo frontend/package.json está vacío"
            )

if __name__ == '__main__':
    unittest.main()