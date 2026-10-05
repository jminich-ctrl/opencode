from fastapi import FastAPI
import os
import importlib.util

# Crear la aplicación FastAPI
app = FastAPI()

# Inicializar la lista de routers montados
app.state.routers_montados = []

# Ruta donde se encuentran los routers
rutas_dir = os.path.join(os.path.dirname(__file__), "rutas")

# Importar automáticamente todos los routers
for filename in os.listdir(rutas_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = filename[:-3]  # Eliminar la extensión .py
        try:
            # Cargar el módulo
            spec = importlib.util.spec_from_file_location(module_name, os.path.join(rutas_dir, filename))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Si el módulo tiene un atributo router, incluirlo
            if hasattr(module, "router"):
                app.include_router(module.router)
                app.state.routers_montados.append(module_name)
        except Exception as e:
            # Si hay algún error al cargar el módulo, se propaga el error
            # con el nombre del módulo en el mensaje
            raise ImportError(f"Error al cargar el módulo {module_name}: {str(e)}")

# Endpoint de salud
@app.get("/salud")
def salud():
    return {"estado": "ok"}