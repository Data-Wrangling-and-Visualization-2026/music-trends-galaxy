from fastapi import FastAPI
from app.routers import init, api, galaxy

app = FastAPI(title="StarPoint Backend")

app.include_router(init.router)
app.include_router(api.router)
app.include_router(galaxy.router)

@app.get("/health")
async def health():
    return {"status": "ok"}