import sqlite3
import json
from datetime import datetime, timedelta, timezone
import os

# Nome do Banco de Dados
DB_FILE = 'bot_database.db'

class PortfolioManager:
    def __init__(self):
        self.conn = None
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(DB_FILE, check_same_thread=False)

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Enable WAL Mode
        conn.execute("PRAGMA journal_mode=WAL;")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                buy_price REAL,
                highest_price REAL,
                amount_usdt REAL,
                rsi_at_entry REAL,
                entry_time TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                equity REAL,
                fluctuation TEXT,
                positions_count INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_equity REAL,
                updated_at TEXT
            )
        ''')
        
        # Inicializa wallet se vazio
        cursor.execute('INSERT OR IGNORE INTO wallet (id, current_equity, updated_at) VALUES (1, 0.0, "")')

        # --- NOVAS TABELAS (V2) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                price REAL,
                rsi REAL,
                volume_24h REAL,
                rvol REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                level TEXT,
                type TEXT,
                message TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                symbol TEXT PRIMARY KEY,
                price REAL,
                rsi REAL,
                rvol REAL,
                status TEXT,
                updated_at TEXT
            )
        ''')

        # --- MIGRAÇÃO AUTOMÁTICA (Adiciona colunas novas se não existirem) ---
        # Verifica se stop_price existe na tabela positions
        cursor.execute("PRAGMA table_info(positions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'stop_price' not in columns:
            print("⚙️ Migrando DB: Adicionando coluna 'stop_price'...")
            cursor.execute("ALTER TABLE positions ADD COLUMN stop_price REAL DEFAULT 0.0")
            
        if 'status_label' not in columns:
            print("⚙️ Migrando DB: Adicionando coluna 'status_label'...")
            cursor.execute("ALTER TABLE positions ADD COLUMN status_label TEXT DEFAULT 'HOLD'")

        # Verifica se status existe na tabela candidates
        cursor.execute("PRAGMA table_info(candidates)")
        c_columns = [info[1] for info in cursor.fetchall()]
        
        if 'status' not in c_columns:
            print("⚙️ Migrando DB: Adicionando coluna 'status' em candidates...")
            cursor.execute("ALTER TABLE candidates ADD COLUMN status TEXT")
        
        conn.commit()
        conn.close()

    def get_timestamp_brt(self):
        brt_time = datetime.now(timezone.utc) - timedelta(hours=3)
        return brt_time.strftime('%Y-%m-%d %H:%M:%S')

    # ==============================================================================
    # 🎩 A MÁGICA DA COMPATIBILIDADE (Dashboard lê isso aqui)
    # ==============================================================================
    @property
    def data(self):
        """
        Reconstrói o dicionário antigo on-the-fly lendo do SQLite.
        Isso permite que main.py e dashboard.py funcionem sem refatoração pesada.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
        cursor = conn.cursor()
        
        # 1. Posições
        active_positions = {}
        cursor.execute("SELECT * FROM positions")
        for row in cursor.fetchall():
            active_positions[row['symbol']] = {
                'buy_price': row['buy_price'],
                'highest_price': row['highest_price'],
                'amount_usdt': row['amount_usdt'],
                'rsi_at_entry': row['rsi_at_entry'],
                'entry_time': row['entry_time'],
                'stop_price': row['stop_price'] if 'stop_price' in row.keys() else 0.0,
                'status_label': row['status_label'] if 'status_label' in row.keys() else 'HOLD'
            }
            
        # 2. Histórico (Pega os últimos 1000 para não pesar)
        balance_history = []
        cursor.execute("SELECT timestamp, equity, fluctuation, positions_count FROM history ORDER BY id ASC")
        for row in cursor.fetchall():
            balance_history.append({
                'timestamp': row['timestamp'],
                'equity': row['equity'], # Nome unificado
                'equity_usdt': row['equity'], # Compatibilidade
                'fluctuation': row['fluctuation'],
                'positions': row['positions_count']
            })
            
        # 3. Wallet
        cursor.execute("SELECT current_equity, updated_at FROM wallet WHERE id=1")
        w_row = cursor.fetchone()
        
        conn.close()
        
        return {
            "metadata": {"updated_at": w_row['updated_at'] if w_row else ""},
            "wallet_summary": {"current_equity": w_row['current_equity'] if w_row else 0.0},
            "active_positions": active_positions,
            "balance_history": balance_history
        }

    # ==============================================================================
    # ⚙️ MÉTODOS DE ESCRITA (Bot usa isso)
    # ==============================================================================

    def add_position(self, symbol, price, amount, rsi):
        conn = self._get_conn()
        conn.execute('''
            INSERT OR REPLACE INTO positions (symbol, buy_price, highest_price, amount_usdt, rsi_at_entry, entry_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, price, price, amount, rsi, self.get_timestamp_brt()))
        conn.commit()
        conn.close()

    def remove_position(self, symbol):
        conn = self._get_conn()
        conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    def update_position_high(self, symbol, new_high):
        """Atualiza o topo histórico para o Trailing Stop"""
        conn = self._get_conn()
        conn.execute("UPDATE positions SET highest_price = ? WHERE symbol = ?", (new_high, symbol))
        conn.commit()
        conn.close()

    def update_wallet_summary(self, equity):
        conn = self._get_conn()
        ts = self.get_timestamp_brt()
        conn.execute("UPDATE wallet SET current_equity = ?, updated_at = ? WHERE id = 1", (equity, ts))
        conn.commit()
        conn.close()

    def log_history(self, equity, fluctuation):
        conn = self._get_conn()
        
        # Conta posições ativas para o log
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM positions")
        count = cursor.fetchone()[0]
        
        conn.execute('''
            INSERT INTO history (timestamp, equity, fluctuation, positions_count)
            VALUES (?, ?, ?, ?)
        ''', (self.get_timestamp_brt(), round(equity, 4), fluctuation, count))
        
        # Limpeza automática: Mantém apenas os últimos 2000 registros para o banco não explodir
        conn.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 2000)")
        
        conn.commit()
        conn.close()

    # Método auxiliar para limpar tudo (se precisar resetar)
    def reset_database(self):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        self._init_db()

    # --- NOVOS MÉTODOS DE LOG ---

    def log_market_data(self, symbol, price, rsi, volume, rvol):
        """Salva dados de mercado para ML"""
        conn = self._get_conn()
        conn.execute('''
            INSERT INTO market_data_history (timestamp, symbol, price, rsi, volume_24h, rvol)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self.get_timestamp_brt(), symbol, price, rsi, volume, rvol))
        
        # Limpeza (Mantém últimos 10k registros)
        # conn.execute("DELETE FROM market_data_history WHERE id NOT IN (SELECT id FROM market_data_history ORDER BY id DESC LIMIT 10000)")
        conn.commit()
        conn.close()

    def log_system_event(self, level, type, message):
        """Salva logs do sistema"""
        conn = self._get_conn()
        conn.execute('''
            INSERT INTO system_logs (timestamp, level, type, message)
            VALUES (?, ?, ?, ?)
        ''', (self.get_timestamp_brt(), level, type, message))
        
        # Limpeza (Mantém últimos 2000 logs)
        conn.execute("DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 2000)")
        conn.commit()
        conn.close()

    def update_position_status(self, symbol, stop_price, status_label):
        """Atualiza status dinâmico da posição"""
        conn = self._get_conn()
        # Verifica se as colunas existem antes de tentar update (caso a migração tenha falhado silenciosamente, mas o _init_db deve garantir)
        try:
            conn.execute("UPDATE positions SET stop_price = ?, status_label = ? WHERE symbol = ?", 
                         (stop_price, status_label, symbol))
            conn.commit()
        except Exception as e:
            print(f"Erro ao atualizar status da posição: {e}")
        conn.close()

    # --- CANDIDATES WATCHLIST ---
    def save_candidates(self, candidates):
        """Salva a lista de candidatos (Top 10)"""
        conn = self._get_conn()
        
        # Limpa tabela anterior (queremos apenas o snapshot atual)
        conn.execute("DELETE FROM candidates")
        
        ts = self.get_timestamp_brt()
        for c in candidates:
            conn.execute('''
                INSERT INTO candidates (symbol, price, rsi, rvol, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c['symbol'], c['price'], c['rsi'], c['rvol'], c['status'], ts))
            
        conn.commit()
        conn.close()

    def get_candidates(self):
        """Retorna a lista de candidatos"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates ORDER BY rsi ASC") # Ordena por RSI (menor = melhor oportunidade)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows