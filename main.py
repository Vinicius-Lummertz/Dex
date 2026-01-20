import time
import config
from storage import PortfolioManager
from binance_api import BinanceClient
from telegram_notifier import TelegramNotifier
from trade_executor import TradeExecutor
from datetime import datetime, timedelta, timezone
import math

class BotController:
    def __init__(self):
        self.db = PortfolioManager()
        self.api = BinanceClient()
        self.notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
        self.executor = TradeExecutor(self.api, self.db, self.notifier)
        
        self.last_equity = 0.0
        self.alert_tracker = set() # Para evitar spam de alertas de PnL
        
        # Cooldown System
        self.cooldowns = {} 
        self.COOLDOWN_TIME_MINUTES = 30

    # --- LÓGICA DE INDICADORES ---
    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1: return None
        gains, losses = [], []
        for i in range(1, len(prices)):
            delta = prices[i] - prices[i-1]
            gains.append(max(delta, 0))
            losses.append(abs(min(delta, 0)))
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0: return 100.0
        return 100 - (100 / (1 + (avg_gain / avg_loss)))

    def calculate_ema(self, prices, period=100):
        if len(prices) < period: return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period # Começa com SMA simples
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def calculate_rvol(self, volumes):
        # Volume Relativo: Volume da última vela / Média das 24 anteriores
        if len(volumes) < 25: return 1.0
        current_vol = volumes[-1]
        avg_vol = sum(volumes[-25:-1]) / 24
        if avg_vol == 0: return 0.0
        return current_vol / avg_vol

    # --- HELPER DE LOG ---
    def log_event(self, level, type, message):
        """Centraliza logs para Console e DB"""
        print(f"   {message}") # Console
        self.db.log_system_event(level, type, message) # DB

    # --- GESTÃO DE CARTEIRA ---
    def update_financials(self):
        # 1. Atualiza Saldo USDT
        acc = self.api.get_account()
        usdt_free = 0.0
        if acc:
            for b in acc['balances']:
                if b['asset'] == 'USDT':
                    usdt_free = float(b['free'])
                    break
        else:
            # Em simulação, estimamos o livre subtraindo o alocado do inicial
            invested = sum(p['amount_usdt'] for p in self.db.data['active_positions'].values())
            usdt_free = max(0, 100.0 - invested) # Assumindo 100 inicial

        # 2. Soma Valor das Posições (Mark-to-Market)
        positions_value = 0.0
        positions = self.db.data['active_positions']
        
        for symbol, data in positions.items():
            current_price = self.api.get_price(symbol)
            if current_price:
                # Estima quantidade de moedas
                coin_qty = data['amount_usdt'] / data['buy_price']
                positions_value += (coin_qty * current_price)
            else:
                positions_value += data['amount_usdt'] # Fallback
        
        total_equity = usdt_free + positions_value
        
        # 3. Salva e Loga
        self.db.update_wallet_summary(total_equity)
        
        # Log histórico se mudou significativamente
        fluctuation = 0.0
        if self.last_equity > 0:
            fluctuation = ((total_equity - self.last_equity) / self.last_equity) * 100
            
        self.db.log_history(total_equity, f"{fluctuation:+.2f}%")
        self.last_equity = total_equity
        
        return total_equity

    def manage_portfolio(self):
        positions = self.db.data['active_positions']
        if not positions: return

        print(f"   💼 Gerenciando {len(positions)} posições...")
        
        for symbol, data in list(positions.items()):
            current_price = self.api.get_price(symbol)
            if not current_price: continue

            buy_price = data['buy_price']
            highest = data['highest_price']
            
            # Atualiza Topo
            if current_price > highest:
                highest = current_price
                self.db.update_position_high(symbol, highest)

            # Cálculos
            pnl_pct = (current_price - buy_price) / buy_price
            
            # Lucro Máximo Atingido (High Water Mark)
            max_profit_pct = (highest - buy_price) / buy_price
            
            # --- DYNAMIC TRAILING STOP (LADDER STRATEGY) ---
            if max_profit_pct < config.LADDER_1_THRESHOLD:
                # Nível 1: Proteção (Lucro < 3%)
                drop_limit = config.LADDER_1_STOP # 2.5%
                mode = "🛡️ PROTEÇÃO"
            elif max_profit_pct < config.LADDER_2_THRESHOLD:
                # Nível 2: Tendência (Lucro 3% - 7%)
                drop_limit = config.LADDER_2_STOP # 4.5%
                mode = "📈 TENDÊNCIA"
            else:
                # Nível 3: Moonshot (Lucro > 7%)
                drop_limit = config.LADDER_3_STOP # 6.0%
                mode = "🚀 MOONSHOT"

            # Define Stop Price (Trailing)
            stop_price = highest * (1 - drop_limit)
            
            # Define Status
            status_label = "HOLD"
            if pnl_pct > 0.01: status_label = "PROFIT"
            if pnl_pct < -0.01: status_label = "LOSS"
            
            # Salva status no DB para o Dashboard
            self.db.update_position_status(symbol, stop_price, status_label)

            # 1. Trailing Stop Loss Dinâmico
            if current_price <= stop_price:
                reason = f"Trailing Stop {mode} (Topo ${highest:.4f})"
                self.log_event("INFO", "SELL", f"🔻 SAÍDA {symbol} | PnL: {pnl_pct*100:.2f}% | {mode}")
                self.close_position(symbol, current_price, reason)
                continue

            # 2. Stop Loss de Emergência (Fixo)
            if pnl_pct <= -config.STOP_LOSS_PERCENT:
                reason = "Stop Loss Fixo"
                self.log_event("WARNING", "SELL", f"🛑 STOP LOSS {symbol} | PnL: {pnl_pct*100:.2f}%")
                self.close_position(symbol, current_price, reason)
                continue
            
            # 3. Take Profit (Alvo Fixo - Opcional, o Trailing costuma ser melhor)
            if pnl_pct >= config.TAKE_PROFIT_PERCENT:
                reason = "Take Profit Alvo"
                self.log_event("SUCCESS", "SELL", f"💰 TAKE PROFIT {symbol} | PnL: {pnl_pct*100:.2f}%")
                self.close_position(symbol, current_price, reason)
                continue

            # Notificações de PnL (Telegram)
            if pnl_pct > 0.03 and f"{symbol}_3%" not in self.alert_tracker:
                self.notifier.send_alert(symbol, "Lucro > 3%", "HOLD", current_price, f"📈 PnL: +{pnl_pct*100:.1f}%")
                self.alert_tracker.add(f"{symbol}_3%")
            
            if pnl_pct > 0.05 and f"{symbol}_5%" not in self.alert_tracker:
                self.notifier.send_alert(symbol, "Lucro > 5%", "HOLD", current_price, f"🚀 PnL: +{pnl_pct*100:.1f}%")
                self.alert_tracker.add(f"{symbol}_5%")

    def find_zombie_position(self, candidate_rsi=100):
        """
        Procura uma posição 'Zumbi' para sacrificar.
        Se o RSI da nova oportunidade for MUITO baixo (<18), ignora o tempo de casa.
        """
        positions = self.db.data['active_positions']
        worst_symbol = None
        worst_pnl = 0.0
        
        # Define urgência
        # Padrão: 2 horas de paciência
        # Urgência (RSI < 18): 0 horas de paciência (Vende qualquer coisa negativa)
        min_hours = 2.0
        if candidate_rsi < 18.0:
            min_hours = 0.0
            self.log_event("WARNING", "SWAP", f"🚨 URGÊNCIA DETECTADA (RSI {candidate_rsi:.1f}): Ignorando tempo mínimo de posição.")

        now = datetime.now(timezone.utc)
        
        for symbol, data in positions.items():
            # 1. Calcula tempo de casa
            try:
                entry_dt = datetime.strptime(data['entry_time'], '%Y-%m-%d %H:%M:%S')
                # Adiciona info de timezone se o python reclamar de offset-naive vs aware
                # Assumindo que o storage salva sem timezone info explícito mas é UTC/BRT
                entry_dt = entry_dt.replace(tzinfo=datetime.now(timezone.utc)) 
                
                duration = (now - entry_dt).total_seconds() / 3600 
            except:
                duration = 0

            # 2. Calcula PnL atual
            current_price = self.api.get_price(symbol)
            if not current_price: continue
            
            pnl_pct = ((current_price - data['buy_price']) / data['buy_price']) * 100

            # CRITÉRIO DE CORTE DINÂMICO:
            # Se tem mais tempo que o minimo exigido E está no prejuízo
            if duration >= min_hours and pnl_pct < -0.05: # -0.05% margem para não vender 0x0
                # self.log_event("INFO", "ZOMBIE", f"💀 Candidato a Zumbi: {symbol} (PnL {pnl_pct:.2f}% | {duration:.1f}h)")
                
                # Queremos o PIOR desempenho para eliminar (Stop Loss tático)
                if pnl_pct < worst_pnl:
                    worst_pnl = pnl_pct
                    worst_symbol = symbol
        
        return worst_symbol

    def close_position(self, symbol, price, reason):
        # Usa o TradeExecutor para vender
        success = self.executor.sell_position(symbol, price, reason)
        if success:
            # Limpa tracker de alertas
            keys_to_remove = [k for k in self.alert_tracker if k.startswith(symbol)]
            for k in keys_to_remove: self.alert_tracker.remove(k)
            
            # Cooldown: Não compra a mesma moeda por X minutos
            self.cooldowns[symbol] = datetime.now() + timedelta(minutes=self.COOLDOWN_TIME_MINUTES)
            self.log_event("INFO", "COOLDOWN", f"❄️ {symbol} em cooldown por {self.COOLDOWN_TIME_MINUTES}min")

    # --- SCANNER ---
    def scan_market(self):
        print("\n🔍 ESCANEANDO (Filtros: RSI < 30 + Tendência + RVOL)...")
        tickers = self.api.get_ticker_24hr()
        if not tickers: return

        candidates = []
        active_symbols = self.db.data['active_positions']
        
        # 1. Filtro Bruto (Liquidez e Volatilidade)
        for t in tickers:
            sym = t['symbol']
            if not sym.endswith(config.SYMBOL_QUOTE) or sym in config.IGNORED_COINS: continue
            if sym in active_symbols: continue
            if float(t['quoteVolume']) < config.MIN_VOLUME_USDT: continue
            
            # Verifica Cooldown
            if sym in self.cooldowns:
                if datetime.now() < self.cooldowns[sym]:
                    continue
                else:
                    del self.cooldowns[sym] # Expired

            candidates.append({'symbol': sym, 'change': float(t['priceChangePercent'])})

        # Ordena pelas que mais caíram/subiram (Interesse do mercado)
        candidates.sort(key=lambda x: abs(x['change']), reverse=True)
        
        # 2. Filtro Fino (Indicadores Técnicos)
        # Analisa até 15 candidatos para achar O MELHOR
        
        watchlist = [] # Lista para salvar no banco
        
        for cand in candidates[:15]: 
            sym = cand['symbol']
            # Pega dados (Preço e Volume)
            klines_data = self.api.get_klines(sym, limit=110)
            if not klines_data: continue

            prices = [x[0] for x in klines_data]
            volumes = [x[1] for x in klines_data]

            # A. Calcula RSI
            rsi = self.calculate_rsi(prices)
            if not rsi: continue

            # B. Calcula EMA (Tendência)
            ema = self.calculate_ema(prices, period=100)
            current_price = prices[-1]
            
            trend_ok = True
            status_reason = "WAIT"
            
            if rsi > config.RSI_BUY_THRESHOLD:
                status_reason = f"RSI High ({rsi:.1f})"
                trend_ok = False
            
            if ema and current_price < ema:
                # Tendência de baixa
                if rsi > 20: 
                    trend_ok = False
                    status_reason = "Downtrend"
            
            # C. Calcula RVOL (Volume Relativo)
            rvol = self.calculate_rvol(volumes)
            
            # Adiciona à Watchlist
            watchlist.append({
                'symbol': sym,
                'price': current_price,
                'rsi': rsi,
                'rvol': rvol,
                'status': "BUY" if trend_ok else status_reason
            })
            
            # LOG DO CANDIDATO
            status_icon = "✅" if trend_ok else "❌"
            print(f"   🧐 {sym:<10} | RSI: {rsi:.1f} | EMA: {status_icon} | RVOL: {rvol:.1f}x | {status_reason}")

            if trend_ok:
                success = self.execute_buy(sym, current_price, rsi)
                
                if not success: 
                    # --- LÓGICA DE SWAP ---
                    if rsi < 20:
                        self.log_event("WARNING", "SWAP", f"🔄 Sem saldo para {sym}. Procurando Zumbis para troca...")
                        zombie = self.find_zombie_position(candidate_rsi=rsi)
                        
                        if zombie:
                            self.log_event("WARNING", "SWAP", f"⚔️ TROCA TÁTICA: Vendendo {zombie} para comprar {sym}")
                            self.close_position(zombie, self.api.get_price(zombie), "SWAP por Oportunidade Melhor")
                            time.sleep(2) 
                            self.execute_buy(sym, current_price, rsi) 
                        else:
                            print("   ❄️ Nenhuma posição Zumbi encontrada.")
                
                if success or (rsi < 20 and zombie): 
                    break
            
            time.sleep(0.2) # Delay leve

        # Salva Watchlist no Banco
        if watchlist:
            self.db.save_candidates(watchlist)

    def execute_buy(self, symbol, price, rsi):
        # --- GESTÃO DE CAPITAL PARA PEQUENAS CONTAS ---
        # Objetivo: Abrir o máximo de posições possíveis com o saldo disponível.
        
        balance = 0.0
        if not config.SIMULATION_MODE:
            acc = self.api.get_account()
            if acc:
                for b in acc['balances']:
                    if b['asset'] == 'USDT': balance = float(b['free'])
        else:
            balance = 100.0 # Simulação

        # Custo mínimo operacional (Binance pede $5, usamos $5.5 para garantir taxas e flutuação)
        MIN_VIABLE_TRADE = 5.5 

        if balance < MIN_VIABLE_TRADE:
            return False

        # Definimos o valor da compra.
        amount = MIN_VIABLE_TRADE

        # Trava de segurança: Se o saldo for tipo $5.80, usa tudo ($5.80) em vez de tentar guardar $0.30
        if balance < (MIN_VIABLE_TRADE * 1.5):
            amount = balance

        # Arredonda para 2 casas para evitar erros de precisão na API
        amount = round(amount - 0.1, 2) # Tira 10 centavos para garantir que não vai faltar taxa

        self.log_event("SUCCESS", "BUY", f"🚀 COMPRANDO {symbol} | RSI {rsi:.2f} | Alvo: ${amount:.2f}")
        
        if not config.SIMULATION_MODE:
            res = self.api.place_order(symbol, 'BUY', amount)
            if not res: return False
        
        self.db.add_position(symbol, price, amount, rsi)
        
        # Notifica Telegram
        self.notifier.send_alert(symbol, "RSI Oversold", "BUY", price, f"📉 RSI: {rsi:.1f}")

        return True

    # --- LOOP ---
    def run(self):
        print(f"🤖 BOT V2 INICIADO (Trailing Stop Dinâmico)")
        print(f"📂 Configuração: Escadinha (2.5% -> 4.5% -> 6.0%)")
        
        while True:
            try:

                equity = self.update_financials()    
                # 1. Auditoria e Trailing Stop
                self.manage_portfolio()
                
                # 2. Novas Compras
                self.scan_market()
                
                print("\n⏳ Aguardando 60s...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n🛑 Parando...")
                break
            except Exception as e:
                print(f"❌ Erro Loop: {e}")
                time.sleep(10)

if __name__ == "__main__":
    BotController().run()