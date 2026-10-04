from fastapi import FastAPI
import uvicorn
from app.calculation.router import router as calculation_router

app = FastAPI()
app.include_router(calculation_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)