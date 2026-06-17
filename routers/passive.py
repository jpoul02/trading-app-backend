from fastapi import APIRouter
from pydantic import BaseModel
import yfinance as yf

router = APIRouter()

ETFS = [
    {"symbol": "SPY", "name": "S&P 500 ETF", "annual_return_pct": 10.5, "description": "Replica el índice S&P 500, las 500 mayores empresas de EE.UU."},
    {"symbol": "QQQ", "name": "Nasdaq 100 ETF", "annual_return_pct": 14.0, "description": "Replica el Nasdaq 100, dominado por tecnología."},
    {"symbol": "VTI", "name": "Total Market ETF", "annual_return_pct": 10.0, "description": "Mercado total de EE.UU., más de 4000 empresas."},
    {"symbol": "BND", "name": "Bond ETF", "annual_return_pct": 4.0, "description": "Bonos del mercado total de EE.UU., menor riesgo."},
    {"symbol": "VT", "name": "Global ETF", "annual_return_pct": 9.0, "description": "Mercado global completo, diversificación máxima."},
]

STAKING = [
    {"asset": "ETH", "name": "Ethereum", "apy_pct": 4.2, "risk": "Bajo"},
    {"asset": "SOL", "name": "Solana", "apy_pct": 6.5, "risk": "Medio"},
    {"asset": "ADA", "name": "Cardano", "apy_pct": 3.1, "risk": "Medio"},
    {"asset": "DOT", "name": "Polkadot", "apy_pct": 12.0, "risk": "Alto"},
    {"asset": "ATOM", "name": "Cosmos", "apy_pct": 15.0, "risk": "Alto"},
]


class DCARequest(BaseModel):
    monthly_amount: float
    years: int
    annual_return: float


@router.get("/etfs")
def get_etfs():
    return ETFS


@router.post("/dca-calculator")
def dca_calculator(body: DCARequest):
    monthly_rate = body.annual_return / 100 / 12
    projection = []
    portfolio_value = 0.0
    total_invested = 0.0

    for year in range(1, body.years + 1):
        for _ in range(12):
            portfolio_value = (portfolio_value + body.monthly_amount) * (1 + monthly_rate)
            total_invested += body.monthly_amount
        projection.append({
            "year": year,
            "total_invested": round(total_invested, 2),
            "portfolio_value": round(portfolio_value, 2),
            "gain": round(portfolio_value - total_invested, 2),
        })

    return projection


@router.get("/staking")
def get_staking():
    return STAKING


@router.get("/dividends")
def get_dividends():
    symbols = ["SCHD", "VYM", "O", "AAPL", "KO"]
    result = []
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info
            result.append({
                "symbol": symbol,
                "name": info.get("longName", symbol),
                "dividend_yield_pct": round((info.get("dividendYield") or 0) * 100, 2),
                "price": round(info.get("currentPrice") or info.get("regularMarketPrice") or 0, 2),
            })
        except Exception:
            continue
    return result
