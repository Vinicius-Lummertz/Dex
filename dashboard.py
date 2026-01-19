import streamlit as st
import pandas as pd
import json
import time
import plotly.express as px
from datetime import datetime
import os

# Configuração da Página
st.set_page_config(
    page_title="🤖 Bot Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# Constantes
PORTFOLIO_FILE = 'portfolio_data.json'
REFRESH_RATE = 2  # Segundos

# --- FUNÇÕES DE CARREGAMENTO ---
def load_data():
    """Lê o JSON com tratamento de erro (caso o bot esteja escrevendo no momento)"""
    if not os.path.exists(PORTFOLIO_FILE):
        return None
    
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None

# --- UI PRINCIPAL ---
st.title("⚡ Painel de Controle - Trading Bot")

# Placeholder para atualização automática
placeholder = st.empty()

while True:
    data = load_data()
    
    with placeholder.container():
        if not data:
            st.warning("⚠️ Aguardando dados do Bot... (Arquivo JSON não encontrado ou vazio)")
            time.sleep(2)
            continue

        # 1. KPIs do Topo
        # Pega as chaves corretas do JSON atual
        equity = data.get('wallet_summary', {}).get('current_equity', 0.0)
        positions = data.get('active_positions', {})
        history = data.get('balance_history', [])
        
        # Calcula variação desde o início
        # Procura o primeiro registro que tenha equity > 0 para ser a base
        start_equity = 16.60 
        for entry in history:
            val = entry.get('equity_usdt', 0)
            if val > 5: # Filtra os registros 0.0 iniciais
                start_equity = val
                break
            
        pnl_total_val = equity - start_equity
        pnl_total_pct = (pnl_total_val / start_equity) * 100 if start_equity > 0 else 0

        # KPI Layout
        kpi1, kpi2, kpi3 = st.columns(3)
        
        # Cor dinâmica para o lucro
        delta_color = "normal"
        if pnl_total_val > 0: delta_color = "normal" # Streamlit usa verde para positivo por padrão no delta
        elif pnl_total_val < 0: delta_color = "inverse"

        kpi1.metric("Patrimônio Total", f"${equity:.2f}", f"{pnl_total_pct:.2f}%", delta_color=delta_color)
        kpi2.metric("Posições Abertas", f"{len(positions)}")
        
        last_update = data.get('metadata', {}).get('updated_at', '-')
        kpi3.metric("Última Atualização", str(last_update).split(' ')[-1])

        st.markdown("---")

        # 2. Layout Principal
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("🎒 Carteira Ativa")
            
            if positions:
                df_pos = pd.DataFrame.from_dict(positions, orient='index')
                df_pos.reset_index(inplace=True)
                
                # Renomeia colunas para ficar bonito na tela
                # Mapeia chaves do JSON -> Colunas da Tabela
                df_pos.rename(columns={
                    'index': 'Símbolo', 
                    'buy_price': 'Entrada ($)', 
                    'highest_price': 'Max Topo ($)', 
                    'amount_usdt': 'Alocado ($)',
                    'entry_time': 'Horário Entrada'
                }, inplace=True)
                
                # Seleciona apenas as colunas que interessam
                cols_to_show = ['Símbolo', 'Entrada ($)', 'Max Topo ($)', 'Alocado ($)', 'Horário Entrada']
                # Garante que as colunas existam (para evitar KeyError se o JSON mudar)
                existing_cols = [c for c in cols_to_show if c in df_pos.columns]
                
                st.dataframe(
                    df_pos[existing_cols],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("💤 Nenhuma posição aberta no momento.")

            st.subheader("📈 Curva de Patrimônio")
            if len(history) > 1:
                df_hist = pd.DataFrame(history)
                # Garante que a coluna equity_usdt existe
                if 'equity_usdt' in df_hist.columns:
                    fig = px.line(df_hist, x='timestamp', y='equity_usdt', 
                                  title='Evolução do Saldo (USDT)', markers=True)
                    # Remove eixos desnecessários para limpar visual
                    fig.update_layout(height=350, xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{time.time()}")

        with col_right:
            st.subheader("📜 Histórico Recente")
            if history:
                df_log = pd.DataFrame(history).sort_index(ascending=False).head(15)
                
                # Renomeia para visualização
                df_log.rename(columns={
                    'timestamp': 'Hora', 
                    'fluctuation_since_last_check': 'Variação', 
                    'equity_usdt': 'Saldo'
                }, inplace=True)
                
                if 'Hora' in df_log.columns:
                    # Formata hora para tirar a data e economizar espaço
                    df_log['Hora'] = df_log['Hora'].apply(lambda x: str(x).split(' ')[-1])
                
                st.dataframe(
                    df_log[['Hora', 'Variação', 'Saldo']], 
                    use_container_width=True,
                    hide_index=True
                )

        time.sleep(REFRESH_RATE)