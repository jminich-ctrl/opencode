from fastapi import FastAPI

app = FastAPI()

@app.get("/salud")
def salud():
    return {"estado": "ok"}