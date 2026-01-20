from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from storage import PortfolioManager
from binance_api import BinanceClient
import config
from typing import List, Dict, Optional, Any
import uvicorn
import pandas as pd
import sqlite3
from datetime import datetime
import math

app = FastAPI(title="DEX V2 API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from trade_executor import TradeExecutor
from telegram_notifier import TelegramNotifier

# Services
db = PortfolioManager()
api = BinanceClient()
notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
executor = TradeExecutor(api, db, notifier)

# Models
class Position(BaseModel):
    symbol: str
    buy_price: float
    highest_price: float
    amount_usdt: float
    rsi_at_entry: float
    entry_time: str
    current_price: Optional[float] = 0.0
    pnl_est_percent: Optional[float] = 0.0

# --- Endpoints ---

@app.get("/api/summary")
def get_summary():
    """Returns wallet KPIs."""
    data = db.data
    return {
        "wallet_summary": data['wallet_summary'],
        "updated_at": data['metadata']['updated_at'],
        "active_positions_count": len(data['active_positions'])
    }

@app.get("/api/positions")
def get_positions():
    """Returns active positions with live PnL estimation."""
    data_raw = db.data['active_positions']
    result = []
    
    # OTIMIZAÇÃO: Busca todos os preços de uma vez (Evita N+1 requests)
    # Se tiver muitas posições, isso é MUITO mais rápido.
    tickers = api.get_ticker_24hr()
    price_map = {}
    if tickers:
        for t in tickers:
            price_map[t['symbol']] = float(t['lastPrice'])

    for symbol, data in data_raw.items():
        # Tenta pegar do map, se não tiver (ex: erro de sync), tenta individual (fallback)
        current_price = price_map.get(symbol)
        if not current_price:
            current_price = api.get_price(symbol)
            
        pnl_est = 0.0
        pnl_usdt = 0.0
        
        if current_price and data['buy_price'] > 0:
            pnl_est = ((current_price - data['buy_price']) / data['buy_price']) * 100
            
            # Calcula PnL em USDT
            # Quantidade de moedas = Investido / Preço de Compra
            coin_qty = data['amount_usdt'] / data['buy_price']
            current_value = coin_qty * current_price
            pnl_usdt = current_value - data['amount_usdt']

        pos = {
            "symbol": symbol,
            "buy_price": data['buy_price'],
            "highest_price": data['highest_price'],
            "amount_usdt": data['amount_usdt'],
            "entry_time": data.get('entry_time', ''),
            "rsi_entry": data.get('rsi_entry', 0.0),
            "current_price": current_price,
            "pnl_est_percent": round(pnl_est, 2),
            "pnl_usdt": round(pnl_usdt, 2), # NOVO
            "stop_price": data.get('stop_price', 0.0),
            "status_label": data.get('status_label', 'HOLD')
        }
        result.append(pos)
        
    return result

@app.get("/api/logs")
def get_logs(limit: int = 50):
    """Returns system logs."""
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

@app.get("/api/history")
def get_history():
    """Returns balance history for charting."""
    data = db.data['balance_history']
    # Limit to last 100 points for performance if needed, but for now return all
    return data

@app.post("/api/trade/sell/{symbol}")
def sell_position(symbol: str, background_tasks: BackgroundTasks):
    """Triggers a market sell for a specific position."""
    # Run in background to not block API
    background_tasks.add_task(_execute_sell, symbol)
    return {"status": "Sell order queued", "symbol": symbol}

def _execute_sell(symbol: str):
    print(f"API: Triggering manual sell for {symbol}")
    executor.sell_position(symbol, "Manual via Dashboard")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
