from fastapi import FastAPI
from app.recognition.router import router as recognition_router
from app.calculation.router import router as calculation_router

app = FastAPI()

app.include_router(recognition_router)
app.include_router(calculation_router)


@app.get("/health")
def health():
    return {"status": "ok"}
