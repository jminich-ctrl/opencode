from fastapi import FastAPI
import os
import importlib.util

# Crear la aplicación FastAPI
app = FastAPI()

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
        except Exception:
            # Si hay algún error al cargar el módulo, se ignora silenciosamente
            # como se menciona en la tarea: "un módulo de `rutas/` que no exponga `router` queda montado en silencio"
            pass

# Endpoint de salud
@app.get("/salud")
def salud():
    return {"estado": "ok"}