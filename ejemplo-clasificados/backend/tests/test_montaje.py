import importlib
import pathlib
import sys
from unittest.mock import patch

import pytest
from fastapi import FastAPI

# Importamos el módulo principal para verificar su estado
import app.main as main_module


def _recargar():
    """Reimporta app.main y devuelve el módulo. La instancia nueva es `mod.app`."""
    import app.main as mod
    return importlib.reload(mod)


def _sembrar(nombre, contenido):
    """Escribe un módulo de rutas y devuelve una función para limpiarlo."""
    RUTAS = pathlib.Path("backend/app/rutas")
    f = RUTAS / f"{nombre}.py"
    f.write_text(contenido)
    
    def limpiar():
        f.unlink(missing_ok=True)
        sys.modules.pop(f"app.rutas.{nombre}", None)
        _recargar()  # deja app.main sano para los tests que siguen
    
    return limpiar


class TestMontaje:
    def test_router_nuevo_se_monta(self):
        """Un router nuevo en rutas se monta automáticamente"""
        # Creamos un router de prueba
        router_content = '''
from fastapi import APIRouter

router = APIRouter(prefix="/prueba")

@router.get("/")
def prueba():
    return {"mensaje": "ok"}
'''
        
        limpiar = _sembrar("prueba_router", router_content)
        
        try:
            # Recargamos el módulo para que detecte el nuevo router
            mod = _recargar()
            
            # Verificamos que el router se haya montado
            assert hasattr(mod.app.state, 'routers_montados')
            assert "prueba_router" in mod.app.state.routers_montados
            
            # Verificamos que el endpoint esté disponible
            assert hasattr(mod.app.router.routes[0], 'path')  # Al menos un route existe
            
        finally:
            limpiar()

    def test_modulo_rotulo_hace_fallar_import(self):
        """Un módulo de rutas que no se puede importar hace fallar el import de app.main"""
        # Creamos un módulo con error de sintaxis
        router_content = '''
from fastapi import APIRouter

router = APIRouter(prefix="/rotulo")

@router.get("/")
def rotulo():
    return {"mensaje": "ok"}
    # Error de sintaxis intencional
    if True
'''
        
        limpiar = _sembrar("modulo_rotulo", router_content)
        
        try:
            # Intentamos recargar, esto debería fallar
            with pytest.raises(Exception) as exc_info:
                _recargar()
                
            # Verificamos que el mensaje contenga el nombre del módulo
            assert "modulo_rotulo" in str(exc_info.value)
            
        finally:
            limpiar()

    def test_helper_no_se_monta(self):
        """Un módulo helper (sin router) no se monta"""
        # Creamos un módulo helper (sin router)
        helper_content = '''
def funcion_util():
    return "dato útil"
'''
        
        limpiar = _sembrar("helper", helper_content)
        
        try:
            # Recargamos el módulo
            mod = _recargar()
            
            # Verificamos que el helper no esté en los routers montados
            assert hasattr(mod.app.state, 'routers_montados')
            assert "helper" not in mod.app.state.routers_montados
            
        finally:
            limpiar()