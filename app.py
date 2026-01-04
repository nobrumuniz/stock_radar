import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner AI v11", page_icon="📈", layout="wide")

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("❌ Configure OPENAI_API_KEY e NEWS_API_KEY nos Secrets do Streamlit.")
    st.stop()

# --- CSS DE ALTA VISIBILIDADE (FIX TOTAL DE CORES) ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14 !important; }
    [data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 2px solid #00ffcc !important;
        border-radius: 12px !important;
        padding: 15px !important;
    }
    [data-testid="stMetricLabel"] div { color: #00ffcc !important; font-size: 18px !important; font-weight: bold !important; }
    [data-testid="stMetricValue"] div { color: #ffffff !important; font-size: 24px !important; }
    
    .ai-card {
        background: #1e2130; padding: 20px; border-radius: 10px;
        border-left: 5px solid #00ffcc; color: white !important;
        line-height: 1.6; margin-bottom: 20px;
    }
    .ai-card h3, .ai-card b { color: #00ffcc !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---

def fetch_clean_data(ticker, period="60d", interval="60m"):
    """Baixa dados e limpa colunas MultiIndex do yfinance"""
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def get_ai_ranking(market_data):
    """Prompt reforçado para evitar KeyError"""
    prompt = f"""
    Analise estes dados de mercado: {market_data}.
    Selecione as 10 melhores ações para Day Trade hoje (Alvo 1%).
    Retorne OBRIGATORIAMENTE um JSON com a chave 'ranking' contendo uma lista de objetos.
    Cada objeto deve ter: 'ticker', 'probabilidade', 'entrada', 'tecnico', 'fundamental', 'estrategia'.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um robô que só responde JSON financeiro."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        res_json = json.loads(response.choices[0].message.content)
        # Garantia que a chave 'ranking' existe
        if 'ranking' not in res_json:
            return {"ranking": list(res_json.values())[0]} if isinstance(res_json, dict) else None
        return res_json
    except:
        return None

# --- LÓGICA DE NAVEGAÇÃO ---
if 'page' not in st.session_state: st.session_state.page = 'home'

# --- TELA HOME ---
if st.session_state.page == 'home':
    st.title("🚀 IA Alpha Scanner v11")
    
    if st.sidebar.button("🔍 ESCANEAR MERCADO"):
        with st.spinner('IA Processando Top Picks...'):
            tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'AVGO', 'SMCI', 'PLTR', 'SPY', 'QQQ']
            # Coleta simplificada para a IA decidir
            raw_market = []
            data_batch = yf.download(tickers, period="5d", interval="1h", group_by='ticker', progress=False)
            for t in tickers:
                try:
                    d = data_batch[t].dropna()
                    raw_market.append({"t": t, "p": round(d['Close'].iloc[-1], 2), "rsi": round(ta.rsi(d['Close']).iloc[-1], 1)})
                except: continue
            
            ai_res = get_ai_ranking(raw_market)
            if ai_res and 'ranking' in ai_res:
                st.session_state.top_10 = ai_res['ranking']
            else:
                st.error("IA falhou ao gerar ranking. Tente novamente.")

    if 'top_10' in st.session_state:
        t10 = st.session_state.top_10
        cols = st.columns(3)
        for i in range(min(3, len(t10))):
            cols[i].metric(label=t10[i]['ticker'], value=f"{t10[i]['probabilidade']}% Prob.", delta="🔥 Alta")
        
        st.write("---")
        df_rank = pd.DataFrame(t10)
        st.subheader("📋 Ranking Estratégico")
        st.dataframe(df_rank[['ticker', 'probabilidade', 'entrada', 'tecnico']], use_container_width=True)

        sel = st.selectbox("Selecione para abrir o terminal:", df_rank['ticker'])
        if st.button("🔍 ABRIR TERMINAL OPERACIONAL"):
            st.session_state.selected_ticker = sel
            st.session_state.page = 'details'
            st.rerun()

# --- TELA DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    st.title(f"⚡ Terminal: {t}")
    
    # Seleção de Timeframe
    tf = st.sidebar.selectbox("Frequência", ["5m", "15m", "30m", "60m", "1d"], index=1)
    p_map = {"5m":"1d", "15m":"3d", "30m":"5d", "60m":"7d", "1d":"1y"}

    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        hist = fetch_clean_data(t, p_map[tf], tf)
        if hist is not None:
            # Indicadores
            hist['EMA9'] = ta.ema(hist['Close'], length=9)
            hist['EMA21'] = ta.ema(hist['Close'], length=21)
            bb = ta.bbands(hist['Close'], length=20)
            
            fig = go.Figure()
            # Candles (Verde e Vermelho padrão)
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Preço"))
            # Médias
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA9'], line=dict(color='#FFD700', width=1.5), name="Média 9"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA21'], line=dict(color='#00FFFF', width=1.5), name="Média 21"))
            # Bandas de Bollinger
            fig.add_trace(go.Scatter(x=hist.index, y=bb['BBU_20_2.0'], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name="Banda Sup"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb['BBL_20_2.0'], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name="Banda Inf"))
            
            fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Erro ao carregar gráfico. Tente outro tempo gráfico.")

        # Notícias
        st.subheader("📰 Notícias Recentes")
        try:
            n_res = requests.get(f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}').json()
            for art in n_res.get('articles', [])[:2]:
                st.info(f"**{art['source']['name']}**: {art['title']}")
        except: st.write("Serviço de notícias offline.")

    with col_r:
        # Puxar dados da IA guardados
        d = next((item for item in st.session_state.top_10 if item["ticker"] == t), {})
        st.markdown(f"""
        <div class="ai-card">
            <h3>🎯 Plano de Trade IA</h3>
            <p><b>Probabilidade:</b> {d.get('probabilidade')}%</p>
            <p><b>Sugestão de Entrada:</b> ${d.get('entrada')}</p>
            <p><b>Estratégia:</b> {d.get('estrategia')}</p>
            <hr>
            <p><b>Técnico:</b> {d.get('tecnico')}</p>
            <p><b>Fundamental:</b> {d.get('fundamental')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Fundamentalista direto do Ticker
        try:
            target = yf.Ticker(t).info.get('targetMeanPrice', 'N/A')
            st.metric("Alvo dos Bancos", f"${target}")
        except: pass
