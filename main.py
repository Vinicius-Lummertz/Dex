import time
import config
from storage import PortfolioManager
from binance_api import BinanceClient
from datetime import datetime


class BotController:
    def __init__(self):
        self.db = PortfolioManager()
        self.api = BinanceClient()
        self.last_equity = 0.0

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

    def find_zombie_position(self):
        """
        Procura uma posição 'Zumbi' para sacrificar.
        Critério: Segurando há mais de 4 horas E PnL Negativo.
        """
        positions = self.db.data['active_positions']
        worst_symbol = None
        worst_pnl = 0.0
        
        # Horário agora (UTC) para comparação justa
        now = datetime.utcnow() # JSON salva em BRT, mas vamos simplificar o delta
        # Nota: Idealmente converteríamos tudo para objetos datetime conscientes,
        # mas para estimativa de horas, comparar timestamps simples funciona se o formato for consistente.
        
        for symbol, data in positions.items():
            # 1. Calcula tempo de casa
            try:
                # O formato salvo no storage.py é '%Y-%m-%d %H:%M:%S'
                # Precisamos calcular quantas horas se passaram
                entry_dt = datetime.strptime(data['entry_time'], '%Y-%m-%d %H:%M:%S')
                # Ajuste fuso horário manual se necessário, mas vamos focar na diferença bruta
                # Se entry_time é BRT (UTC-3) e now é UTC, temos que ajustar
                entry_dt_adjusted = entry_dt + timedelta(hours=3) # Converte BRT visual para UTC real
                
                duration = (now - entry_dt_adjusted).total_seconds() / 3600 # Horas
            except:
                duration = 0

            # 2. Calcula PnL atual
            current_price = self.api.get_price(symbol)
            if not current_price: continue
            pnl_pct = ((current_price - data['buy_price']) / data['buy_price']) * 100

            # CRITÉRIO DE CORTE:
            # Se tem mais de 3 horas de vida E está no prejuízo
            if duration > 3.0 and pnl_pct < 0:
                print(f"   💀 Candidato a Zumbi: {symbol} (PnL {pnl_pct:.2f}% | {duration:.1f}h)")
                
                # Queremos eliminar o que tem o PIOR desempenho ou MAIOR tempo
                # Aqui vamos priorizar quem está dando mais prejuízo para estancar sangria
                if pnl_pct < worst_pnl:
                    worst_pnl = pnl_pct
                    worst_symbol = symbol

        return worst_symbol

    # --- LÓGICA DE TRAILING STOP & GESTÃO ---
    def manage_portfolio(self):
        positions = self.db.data['active_positions']
        if not positions: return

        print(f"\n📋 GESTÃO DE CARTEIRA ({len(positions)} Ativos)")
        print(f"{'MOEDA':<10} | {'ENTRADA':<10} | {'ATUAL':<10} | {'MÁXIMO':<10} | {'PNL %':<8} | {'STATUS'}")
        print("-" * 75)

        for symbol in list(positions.keys()): # Lista auxiliar para poder deletar
            data = positions[symbol]
            current_price = self.api.get_price(symbol)
            if not current_price: continue

            # 1. Atualiza Trailing Stop (Highest Price)
            # Se o preço atual for maior que o histórico, atualizamos o topo
            if current_price > data['highest_price']:
                data['highest_price'] = current_price
                self.db.save_data() # Salva o novo topo

            # 2. Cálculos
            buy_price = data['buy_price']
            highest_price = data['highest_price']
            
            pnl_pct = ((current_price - buy_price) / buy_price) * 100
            
            # Cálculo da Queda do Topo (Drawdown)
            drop_from_high = (current_price - highest_price) / highest_price
            
            # Corzinha para o log ficar bonito
            color = "\033[92m" if pnl_pct >= 0 else "\033[91m"
            reset = "\033[0m"
            
            print(f"{symbol:<10} | {buy_price:<10.5f} | {current_price:<10.5f} | {highest_price:<10.5f} | {color}{pnl_pct:+.2f}%{reset} | ", end="")

            # 3. Decisão de Venda (Trailing Stop)
            # Se cair X% (definido no config) do topo máximo atingido, VENDE.
            # Isso protege o lucro se subir muito e cair, e estanca o prejuízo se cair direto da entrada.
            if drop_from_high <= -config.TRAILING_DROP_PERCENT:
                print("🛑 TRAILING STOP")
                self.close_position(symbol, current_price, f"Caiu {drop_from_high*100:.2f}% do topo")
            else:
                print(f"HOLD (Stop a {highest_price * (1 - config.TRAILING_DROP_PERCENT):.5f})")

    def close_position(self, symbol, price, reason):
        if not config.SIMULATION_MODE:
            # Lógica simples de venda total. Em prod real, precisa tratar 'lot size'
            # Tentar vender via API. Se falhar (ex: precisão), avisa mas remove do banco para destravar
            self.api.place_order(symbol, 'SELL', 0) # Qty 0 aqui é simbólico, precisaria da lógica de saldo
            
        # PnL Realizado
        data = self.db.data['active_positions'][symbol]
        profit_usd = data['amount_usdt'] * ((price - data['buy_price']) / data['buy_price'])
        print(f"   💰 VENDIDO: {symbol} | Lucro: ${profit_usd:.2f} | Motivo: {reason}")
        
        self.db.remove_position(symbol)

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
            
            candidates.append({'symbol': sym, 'change': float(t['priceChangePercent'])})

        # Ordena pelas que mais caíram/subiram (Interesse do mercado)
        candidates.sort(key=lambda x: abs(x['change']), reverse=True)
        
        # 2. Filtro Fino (Indicadores Técnicos)
        # Analisa até 10 candidatos para achar O MELHOR, não o primeiro que aparecer
        checked_count = 0
        
        for cand in candidates[:15]: 
            sym = cand['symbol']
            # Pega dados (Preço e Volume)
            klines_data = self.api.get_klines(sym, limit=110)
            if not klines_data: continue

            prices = [x[0] for x in klines_data]
            volumes = [x[1] for x in klines_data]

            # A. Calcula RSI
            rsi = self.calculate_rsi(prices)
            if not rsi or rsi > config.RSI_BUY_THRESHOLD: 
                continue # Falhou no RSI, ignora

            # B. Calcula EMA (Tendência)
            # Queremos comprar apenas se o preço estiver ACIMA da EMA 100 (Tendência de Alta)
            # OU se estivermos agressivos, podemos ignorar isso, mas para segurança é bom.
            ema = self.calculate_ema(prices, period=100)
            current_price = prices[-1]
            
            trend_ok = True
            if ema and current_price < ema:
                # O preço está abaixo da média de 100 períodos. É uma tendência de baixa.
                # Só compramos se o RSI for MUITO baixo (Ex: < 20) para justificar o risco.
                if rsi > 20: 
                    trend_ok = False
            
            # C. Calcula RVOL (Volume Relativo)
            # Queremos ver se o volume está aumentando (interesse comprador)
            rvol = self.calculate_rvol(volumes)
            
            # LOG DO CANDIDATO (Feedback visual do porquê comprou ou rejeitou)
            status_icon = "✅" if trend_ok else "❌"
            print(f"   🧐 {sym:<10} | RSI: {rsi:.1f} | EMA: {status_icon} | RVOL: {rvol:.1f}x")

            if trend_ok:
                
                success = self.execute_buy(sym, current_price, rsi)
                
                if not success: 
                    # --- LÓGICA DE SWAP (NOVO) ---
                    # Se falhou por saldo E o sinal é MUITO bom (RSI < 20), tenta trocar
                    if rsi < 20:
                        print(f"   🔄 Sem saldo para {sym}. Procurando Zumbis para troca...")
                        zombie = self.find_zombie_position()
                        
                        if zombie:
                            print(f"   ⚔️ TROCA TÁTICA: Vendendo {zombie} para comprar {sym}")
                            self.close_position(zombie, self.api.get_price(zombie), "SWAP por Oportunidade Melhor")
                            time.sleep(2) # Espera vender e liberar saldo
                            self.execute_buy(sym, current_price, rsi) # Tenta comprar de novo
                        else:
                            print("   ❄️ Nenhuma posição Zumbi encontrada (todas recentes ou no lucro).")
                
                if success or (rsi < 20 and zombie): # Se comprou ou trocou, para o scanner
                    break
            
            time.sleep(0.2) # Delay leve

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
        # Isso maximiza o número de "balas" que temos para atirar.
        MIN_VIABLE_TRADE = 5.5 

        if balance < MIN_VIABLE_TRADE:
            # Se o saldo for menor que o mínimo, não adianta tentar, a API rejeita (Erro -2010)
            # Mas aqui podemos adicionar um log silencioso ou warning apenas se for muito critico
            # print(f"   ⚠️ Saldo insuficiente (${balance:.2f}) para {symbol}")
            return False

        # Definimos o valor da compra.
        # Em vez de % da banca, usamos o valor fixo mínimo para diversificar ao máximo.
        amount = MIN_VIABLE_TRADE

        # Trava de segurança: Se o saldo for tipo $5.80, usa tudo ($5.80) em vez de tentar guardar $0.30
        if balance < (MIN_VIABLE_TRADE * 1.5):
            amount = balance

        # Arredonda para 2 casas para evitar erros de precisão na API
        amount = round(amount - 0.1, 2) # Tira 10 centavos para garantir que não vai faltar taxa

        print(f"   🚀 COMPRANDO {symbol} | RSI {rsi:.2f} | Alvo: ${amount:.2f}")
        
        if not config.SIMULATION_MODE:
            res = self.api.place_order(symbol, 'BUY', amount)
            if not res: return False
        
        self.db.add_position(symbol, price, amount, rsi)

        return True

    # --- LOOP ---
    def run(self):
        print(f"🤖 BOT V2 INICIADO (Trailing Stop Ativo)")
        print(f"📂 Configuração: Queda Max {config.TRAILING_DROP_PERCENT*100}% do Topo")
        
        while True:
            try:
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