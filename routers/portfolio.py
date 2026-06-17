from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
import uuid
import httpx
import yfinance as yf

router = APIRouter()

positions: dict[str, dict] = {}

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "ADA": "cardano",
    "XRP": "ripple",
    "DOT": "polkadot",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
}


class AddPositionRequest(BaseModel):
    symbol: str
    quantity: float
    buy_price: float
    asset_type: Literal["crypto", "stock", "etf"]


async def get_crypto_price(symbol: str) -> float | None:
    coin_id = COINGECKO_IDS.get(symbol.upper())
    if not coin_id:
        return None
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get(coin_id, {}).get("usd")


def get_stock_price(symbol: str) -> float | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


@router.post("/add")
def add_position(body: AddPositionRequest):
    position_id = str(uuid.uuid4())
    position = {
        "id": position_id,
        "symbol": body.symbol.upper(),
        "quantity": body.quantity,
        "buy_price": body.buy_price,
        "asset_type": body.asset_type,
    }
    positions[position_id] = position
    return position


@router.get("/")
async def get_portfolio():
    result = []
    for pos in positions.values():
        current_price = None
        if pos["asset_type"] == "crypto":
            current_price = await get_crypto_price(pos["symbol"])
        else:
            current_price = get_stock_price(pos["symbol"])

        if current_price is None:
            current_price = pos["buy_price"]

        total_invested = pos["quantity"] * pos["buy_price"]
        current_value = pos["quantity"] * current_price
        pnl = current_value - total_invested
        pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0

        result.append({
            **pos,
            "current_price": round(current_price, 4),
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    return result


@router.delete("/{position_id}")
def delete_position(position_id: str):
    if position_id not in positions:
        raise HTTPException(status_code=404, detail="Position not found")
    del positions[position_id]
    return {"message": "Position deleted", "id": position_id}
