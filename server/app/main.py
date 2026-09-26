# 组长锁定：后端入口，成员只读不改。骨架约定见 server/README.md。
from fastapi import FastAPI
from app.recognition.router import router as recognition_router
from app.calculation.router import router as calculation_router

app = FastAPI()

app.include_router(recognition_router)
app.include_router(calculation_router)
