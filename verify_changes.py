import os
import sqlite3
import config
from trade_executor import TradeExecutor
from main import BotController
from api import app

def verify():
    print("🔍 Verifying Codebase Optimization...")
    
    # 1. Check Config
    try:
        print(f"   ✅ Config KLINE_LIMIT: {config.KLINE_LIMIT}")
        print(f"   ✅ Config SCAN_INTERVAL: {config.SCAN_INTERVAL}")
    except AttributeError as e:
        print(f"   ❌ Config Missing: {e}")

    # 2. Check Imports
    try:
        bot = BotController()
        print("   ✅ BotController initialized successfully.")
        print(f"   ✅ TradeExecutor attached: {isinstance(bot.executor, TradeExecutor)}")
    except Exception as e:
        print(f"   ❌ BotController Init Failed: {e}")

    # 3. Check DB WAL Mode
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        print(f"   ✅ DB Journal Mode: {mode}")
        if mode.upper() == 'WAL':
            print("      (WAL Mode Active - Concurrency Optimized)")
        else:
            print("      (⚠️ WAL Mode NOT Active - Check storage.py)")
        conn.close()
    except Exception as e:
        print(f"   ❌ DB Check Failed: {e}")

if __name__ == "__main__":
    verify()
