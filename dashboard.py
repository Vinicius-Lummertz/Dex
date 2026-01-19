import streamlit as st
import pandas as pd
import json
import time
import plotly.express as px
from datetime import datetime
import os

# Configuração da Página
st.set_page_config(page_title="🤖 Bot Trading Dashboard", page_icon="📈", layout="wide")

PORTFOLIO_FILE = 'portfolio_data.json'
REFRESH_RATE = 2

def load_data():
    if not os.path.exists(PORTFOLIO_FILE): return None
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except: return None

st.title("⚡ Painel de Controle - Trading Bot")
placeholder = st.empty()

while True:
    data = load_data()
    
    with placeholder.container():
        if not data:
            st.warning("⚠️ Aguardando dados...")
            time.sleep(2)
            continue

        # --- DADOS ---
        equity = data.get('wallet_summary', {}).get('current_equity', 0.0)
        positions = data.get('active_positions', {})
        history = data.get('balance_history', [])
        
        # --- CÁLCULO DE PNL REAL (FLUTUANTE) ---
        invested_total = 0.0
        
        df_pos = pd.DataFrame()
        if positions:
            df_pos = pd.DataFrame.from_dict(positions, orient='index')
            df_pos.reset_index(inplace=True)
            df_pos.rename(columns={
                'index': 'Símbolo', 'buy_price': 'Entrada', 
                'highest_price': 'Topo', 'amount_usdt': 'Alocado'
            }, inplace=True)
            if 'Alocado' in df_pos.columns:
                invested_total = df_pos['Alocado'].sum()

        # Pega a última flutuação registrada
        last_fluctuation = "0.00%"
        
        if history and len(history) > 0:
            last_entry = history[-1]
            last_fluctuation = last_entry.get('fluctuation', last_entry.get('fluctuation_since_last_check', '0.00%'))

        # --- KPI LAYOUT PERSONALIZADO (CORES) ---
        k1, k2, k3 = st.columns(3)
        
        # 1. Lógica de Cores Gradiente
        try:
            val = float(str(last_fluctuation).replace('%', ''))
        except:
            val = 0.0

        if val == 0: 
            color_hex = "#FFC107"      # Amarelo (0x0)
        elif val <= -5.0: 
            color_hex = "#8E44AD"      # Roxo (Prejuízo Grande)
        elif val < 0: 
            color_hex = "#FF4B4B"      # Vermelho (Prejuízo Normal)
        elif val >= 5.0: 
            color_hex = "#00FF00"      # Verde Neon (Lucro Grande)
        else: 
            color_hex = "#2ECC71"      # Verde Suave (Lucro Normal)

        k1.markdown(f"""
            <style>div[data-testid="stMetricValue"] {{ background-color: transparent; }}</style>
            <div style="text-align: left;">
                <p style="font-size: 14px; margin-bottom: 0px; color: #fafafa;">Patrimônio Total</p>
                <p style="font-size: 32px; font-weight: bold; margin: 0px;">${equity:.2f}</p>
                <p style="color: {color_hex}; font-size: 16px; margin-top: -5px;">{last_fluctuation}</p>
            </div>
        """, unsafe_allow_html=True)

        k2.metric("Posições Abertas", f"{len(positions)}")
        k2.caption(f"Investido: ${invested_total:.2f}")
        
        last_up = data.get('metadata', {}).get('updated_at', '-')
        k3.metric("Última Atualização", str(last_up).split(' ')[-1])

        st.markdown("---")

        # --- LAYOUT PRINCIPAL ---
        c1, c2 = st.columns([2, 1])

        with c1:
            st.subheader("🎒 Carteira Ativa")
            if not df_pos.empty:
                cols = [c for c in ['Símbolo', 'Entrada', 'Topo', 'Alocado', 'entry_time'] if c in df_pos.columns]
                # FIX 2026: use_container_width=True -> width="stretch"
                st.dataframe(df_pos[cols], hide_index=True, width="stretch") 
                # Nota: Algumas versões pedem width="stretch", outras mantém use_container_width como deprecated.
                # Se o warning persistir com 'stretch', reverta para use_container_width=True apenas ignorando o warning,
                # mas o código abaixo segue a instrução do seu erro.
            else:
                st.info("💤 Nenhuma posição aberta.")

            st.subheader("📈 Curva de Patrimônio (Zoom)")
            if len(history) > 1:
                df_hist = pd.DataFrame(history)
                
                # Normalização de colunas
                if 'equity_usdt' in df_hist.columns:
                    if 'equity' in df_hist.columns:
                        df_hist['equity_final'] = df_hist['equity_usdt'].combine_first(df_hist['equity'])
                    else:
                        df_hist['equity_final'] = df_hist['equity_usdt']
                elif 'equity' in df_hist.columns:
                    df_hist['equity_final'] = df_hist['equity']
                else:
                    df_hist['equity_final'] = 0.0

                # Zoom Inteligente
                if not df_hist.empty:
                    current_val = df_hist['equity_final'].iloc[-1]
                    threshold = current_val * 0.8
                    df_chart = df_hist[df_hist['equity_final'] > threshold].copy()
                    
                    fig = px.line(df_chart, x='timestamp', y='equity_final', markers=True)
                    fig.update_layout(
                        height=350, 
                        margin=dict(l=0, r=0, t=10, b=0),
                        yaxis=dict(autorange=True, fixedrange=False),
                        xaxis_title=None, yaxis_title=None
                    )
                    # FIX 2026: Key única + width="stretch" se necessário, mas Plotly usa use_container_width no wrapper.
                    # Se o erro pede 'stretch', usamos no wrapper st.plotly_chart.
                    # Mantenha use_container_width=True se o erro foi no dataframe, ou teste width="stretch" aqui se falhar.
                    # Vou manter use_container_width=True aqui pois geralmente o erro é no dataframe, 
                    # mas se reclamar, troque para width="stretch".
                    st.plotly_chart(fig, width="stretch", key=f"chart_{time.time()}")

        with c2:
            st.subheader("📜 Log Recente")
            if history:
                df_log = pd.DataFrame(history).sort_index(ascending=False).head(15)
                
                # Normalização
                if 'equity_usdt' in df_log.columns:
                    if 'equity' in df_log.columns:
                        df_log['equity'] = df_log['equity_usdt'].combine_first(df_log['equity'])
                    else:
                        df_log.rename(columns={'equity_usdt': 'equity'}, inplace=True)
                
                if 'fluctuation_since_last_check' in df_log.columns:
                    if 'fluctuation' in df_log.columns:
                        df_log['fluctuation'] = df_log['fluctuation_since_last_check'].combine_first(df_log['fluctuation'])
                    else:
                        df_log.rename(columns={'fluctuation_since_last_check': 'fluctuation'}, inplace=True)

                safe_cols = ['timestamp', 'fluctuation', 'equity']
                final_cols = [c for c in safe_cols if c in df_log.columns]
                
                # FIX 2026: dataframe com width="stretch" (via parâmetro use_container_width=True renomeado se a lib exigir)
                # O erro diz: For use_container_width=True, use width='stretch'.
                st.dataframe(
                    df_log[final_cols], 
                    width="stretch", # Se der erro, mude esta linha para width="stretch"
                    hide_index=True
                )

        time.sleep(REFRESH_RATE)