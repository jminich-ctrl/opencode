import importlib
import os
from fastapi import FastAPI

app = FastAPI()

# Lista para almacenar los routers montados
app.state.routers_montados = []

# Función para cargar routers automáticamente
def _cargar_routers():
    """Carga automáticamente los routers desde backend/app/rutas/"""
    rutas_dir = os.path.join(os.path.dirname(__file__), "rutas")
    
    # Verificamos que el directorio exista
    if not os.path.exists(rutas_dir):
        return
        
    # Iteramos sobre los archivos .py en el directorio rutas
    for filename in os.listdir(rutas_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]  # Eliminamos la extensión .py
            
            try:
                # Importamos el módulo
                spec = importlib.util.spec_from_file_location(
                    f"app.rutas.{module_name}", 
                    os.path.join(rutas_dir, filename)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Verificamos si el módulo tiene un atributo router
                if hasattr(module, 'router'):
                    # Incluimos el router en la aplicación
                    app.include_router(module.router)
                    # Agregamos el nombre del módulo a la lista de routers montados
                    app.state.routers_montados.append(module_name)
                    
            except Exception as e:
                # Si hay un error al importar, lo propagamos con el nombre del módulo
                raise ImportError(f"Error al cargar el router '{module_name}': {str(e)}")

# Cargamos los routers al iniciar la aplicación
_cargar_routers()

@app.get("/salud")
def salud():
    return {"estado": "ok"}