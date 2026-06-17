from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import market, passive, education, portfolio

app = FastAPI(title="Trading App API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api/market")
app.include_router(passive.router, prefix="/api/passive")
app.include_router(education.router, prefix="/api/education")
app.include_router(portfolio.router, prefix="/api/portfolio")


@app.get("/")
def root():
    return {"status": "ok", "message": "Trading App API running"}
