import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import market, passive, education, portfolio, mt5 as mt5_router

load_dotenv()

app = FastAPI(title="Trading App API", version="1.0.0")

origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api/market")
app.include_router(passive.router, prefix="/api/passive")
app.include_router(education.router, prefix="/api/education")
app.include_router(portfolio.router, prefix="/api/portfolio")
app.include_router(mt5_router.router, prefix="/api/mt5")


@app.get("/")
def root():
    return {"status": "ok", "message": "Trading App API running"}
