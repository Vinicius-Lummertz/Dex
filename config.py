import os
from dotenv import load_dotenv

load_dotenv()

# Credenciais
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

if not API_KEY or not SECRET_KEY:
    raise ValueError("⚠️ CRÍTICO: Chaves API não encontradas no .env")

# URLs
BASE_URL = 'https://api.binance.com'

# Estratégia de Mercado
SYMBOL_QUOTE = 'USDT'
MIN_VOLUME_USDT = 2_000_000  # Liquidez mínima
AMOUNT_TO_TRADE = 15.0       # Valor base por trade

# Indicadores (RSI)
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 23       # Compra abaixo de 20

# Trailing Stop Dinâmico (Escadinha / Ladder Strategy)
# 1. O Berço (Proteção): Lucro < 3% -> Stop curto de 2.5%
LADDER_1_THRESHOLD = 0.03
LADDER_1_STOP = 0.025

# 2. A Tendência (Confirmação): Lucro entre 3% e 7% -> Stop médio de 4.5%
LADDER_2_THRESHOLD = 0.07
LADDER_2_STOP = 0.045

# 3. O Moonshot (Mão de Diamante): Lucro > 7% -> Stop longo de 6.0%
LADDER_3_STOP = 0.060

# Stop Loss e Take Profit (Segurança Adicional)
STOP_LOSS_PERCENT = 0.05     # 5% de prejuízo máximo (Emergência)
TAKE_PROFIT_PERCENT = 0.10   # 10% de lucro (Alvo fixo opcional)

# Blacklist
IGNORED_COINS = [
    'USDCUSDT', 'FDUSDUSDT', 'USDPUSDT', 'TUSDUSDT', 'BUSDUSDT', 
    'EURUSDT', 'DAIUSDT', 'FRAXUSDT', 'USDDUSDT', 'AEURUSDT'
]

# Sistema
PORTFOLIO_FILE = 'portfolio_data.json'
SIMULATION_MODE = False

# Configurações de Scan
KLINE_LIMIT = 110
SCAN_INTERVAL = 60

# Telegram
TELEGRAM_BOT_TOKEN = '8269724523:AAF2q7oDEo7P3uGPoJaFVLe2NrKi2MO4YUE'
TELEGRAM_CHAT_ID = '7213853752'
TELEGRAM_ENABLED = True