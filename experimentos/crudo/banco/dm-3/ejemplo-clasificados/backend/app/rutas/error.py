from fastapi import HTTPException

# Simulamos un error HTTP 500
raise HTTPException(status_code=500, detail="Error de servidor")