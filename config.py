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
RSI_BUY_THRESHOLD = 25      # Compra abaixo de 30

# Trailing Stop (A Mágica Nova)
# Se o preço cair 3% em relação ao topo máximo atingido, vende.
TRAILING_DROP_PERCENT = 0.03 

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
RSI_BUY_THRESHOLD = 20       # Compra abaixo de 30

# Trailing Stop (A Mágica Nova)
# Se o preço cair 3% em relação ao topo máximo atingido, vende.
TRAILING_DROP_PERCENT = 0.03 

# Blacklist
IGNORED_COINS = [
    'USDCUSDT', 'FDUSDUSDT', 'USDPUSDT', 'TUSDUSDT', 'BUSDUSDT', 
    'EURUSDT', 'DAIUSDT', 'FRAXUSDT', 'USDDUSDT', 'AEURUSDT'
]

# Sistema
PORTFOLIO_FILE = 'portfolio_data.json'
SIMULATION_MODE = False

# Telegram
TELEGRAM_BOT_TOKEN = '8269724523:AAF2q7oDEo7P3uGPoJaFVLe2NrKi2MO4YUE'
TELEGRAM_CHAT_ID = '7213853752'
TELEGRAM_ENABLED = True