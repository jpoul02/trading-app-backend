from fastapi import APIRouter, HTTPException
import httpx
import yfinance as yf

router = APIRouter()

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
HEADERS = {"accept": "application/json"}


@router.get("/prices")
async def get_prices():
    url = (
        f"{COINGECKO_BASE}/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=20"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=HEADERS)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="CoinGecko error")
    return resp.json()


@router.get("/trending")
async def get_trending():
    url = f"{COINGECKO_BASE}/search/trending"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=HEADERS)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="CoinGecko error")
    return resp.json()


@router.get("/stocks")
def get_stocks():
    tickers = ["SPY", "QQQ", "VTI", "BND", "VT"]
    result = []
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if len(hist) < 2:
                continue
            prev_close = float(hist["Close"].iloc[-2])
            current = float(hist["Close"].iloc[-1])
            change_pct = ((current - prev_close) / prev_close) * 100
            result.append({
                "symbol": symbol,
                "price": round(current, 2),
                "change_pct_24h": round(change_pct, 2),
            })
        except Exception:
            continue
    return result


@router.get("/global")
async def get_global_stats():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.coingecko.com/api/v3/global")
            r.raise_for_status()
            data = r.json()["data"]
            return {
                "btc_dominance": round(data["market_cap_percentage"].get("btc", 0), 1),
                "total_market_cap": data["total_market_cap"].get("usd", 0),
                "total_volume_24h": data["total_volume"].get("usd", 0),
                "active_cryptocurrencies": data["active_cryptocurrencies"],
            }
    except Exception as e:
        return {"error": str(e)}


@router.get("/fear-greed")
async def get_fear_greed():
    url = "https://api.alternative.me/fng/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Fear & Greed API no disponible")
        data = resp.json()
        entry = data["data"][0]
        return {
            "value": int(entry["value"]),
            "classification": entry["value_classification"],
            "timestamp": entry["timestamp"],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Fear & Greed API no disponible")
