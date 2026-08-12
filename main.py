import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import market, passive, education, portfolio, mt5 as mt5_router, bot as bot_router, backtest as backtest_router
import asyncio
import bot_engine

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(bot_engine.run_bot_loop())
    yield
    task.cancel()


app = FastAPI(title="Trading App API", version="1.0.0", lifespan=lifespan)

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
app.include_router(bot_router.router, prefix="/api/bot")
app.include_router(backtest_router.router, prefix="/api/backtest")


@app.get("/")
def root():
    return {"status": "ok", "message": "Trading App API running"}
