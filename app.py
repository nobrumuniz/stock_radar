import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
import json

# --- CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="Alpha Scanner Pro v10", page_icon="📈", layout="wide")

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("❌ Configure as chaves nos Secrets.")
    st.stop()

# --- CSS DE ALTA VISIBILIDADE (FIX CORES) ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14 !important; }
    
    /* Correção de Visibilidade nos Metrics */
    [data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 2px solid #00ffcc !important;
        border-radius: 15px !important;
        padding: 20px !important;
    }
    [data-testid="stMetricLabel"] div {
        color: #00ffcc !important; 
        font-size: 20px !important; 
        font-weight: bold !important;
    }
    [data-testid="stMetricValue"] div {
        color: #ffffff !important;
        font-size: 28px !important;
    }

    /* Estilo do Plano de Trade AI */
    .ai-report-container {
        background: linear-gradient(145deg, #1e2130, #161b22);
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #3e445e;
        color: #ffffff !important;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .ai-report-container h3 { color: #00ffcc !important; }
    .ai-report-container b { color: #00ffcc !important; }
    
    /* Tabelas */
    .stDataFrame { border: 1px solid #3e445e; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---

def get_market_data():
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'AVGO', 'SMCI', 'PLTR', 'SPY', 'QQQ']
    data = yf.download(tickers, period="1mo", interval="1h", group_by='ticker', progress=False)
    processed = []
    for t in tickers:
        try:
            df = data[t].dropna()
            if df.empty: continue
            rsi = ta.rsi(df['Close'], length=14).iloc[-1]
            processed.append({
                "ticker": t, "preco": round(df['Close'].iloc[-1], 2),
                "rsi": round(rsi, 2), "vol": int(df['Volume'].iloc[-1]),
                "ema_trend": "Alta" if df['Close'].iloc[-1] > ta.ema(df['Close'], length=21).iloc[-1] else "Baixa"
            })
        except: continue
    return processed

def get_ai_ranking(market_data):
    prompt = f"Analise estes dados: {market_data}. Retorne um JSON com o Top 10 para Day Trade hoje (Alvo 1%). Inclua ticker, probabilidade(%), entrada, tecnico, fundamental e estrategia."
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um analista JSON."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except: return None

# --- NAVEGAÇÃO ---
if 'page' not in st.session_state: st.session_state.page = 'home'

# --- HOME ---
if st.session_state.page == 'home':
    st.title("🚀 Alpha Scanner AI - v10")
    
    if st.sidebar.button("🔍 ESCANEAR MERCADO AGORA"):
        with st.spinner('IA analisando o mercado...'):
            m_data = get_market_data()
            ai_res = get_ai_ranking(m_data)
            if ai_res: st.session_state.top_10 = ai_res['ranking']

    if 'top_10' in st.session_state:
        t10 = st.session_state.top_10
        cols = st.columns(3)
        for i in range(min(3, len(t10))):
            cols[i].metric(label=t10[i]['ticker'], value=f"{t10[i]['probabilidade']}% Prob.", delta="Alta Probabilidade")
        
        st.write("---")
        df_rank = pd.DataFrame(t10)
        st.subheader("📋 Ranking Detalhado")
        st.dataframe(df_rank[['ticker', 'probabilidade', 'entrada', 'tecnico']], use_container_width=True)

        selected = st.selectbox("Selecione o ativo:", df_rank['ticker'])
        if st.button("🔍 ABRIR PAINEL OPERACIONAL"):
            st.session_state.selected_ticker = selected
            st.session_state.page = 'details'
            st.rerun()

# --- DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    st.title(f"⚡ Terminal Operacional: {t}")
    
    # 1. SELETOR DE TEMPO GRÁFICO
    timeframe = st.sidebar.selectbox("Selecionar Tempo Gráfico", ["5m", "15m", "30m", "60m", "1d"], index=1)
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        # Busca dados do gráfico com base no tempo escolhido
        period_map = {"5m":"1d", "15m":"3d", "30m":"5d", "60m":"7d", "1d":"1y"}
        hist = yf.download(t, period=period_map[timeframe], interval=timeframe, progress=False)
        
        if not hist.empty:
            # Indicadores para o Gráfico
            hist['EMA9'] = ta.ema(hist['Close'], length=9)
            hist['EMA21'] = ta.ema(hist['Close'], length=21)
            bbands = ta.bbands(hist['Close'], length=20, std=2)
            
            fig = go.Figure()
            # Candles
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Candles"))
            # Médias
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA9'], line=dict(color='yellow', width=1), name="EMA 9"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA21'], line=dict(color='cyan', width=1), name="EMA 21"))
            # Bandas de Bollinger
            fig.add_trace(go.Scatter(x=hist.index, y=bbands['BBU_20_2.0'], line=dict(color='gray', dash='dash'), name="Banda Sup"))
            fig.add_trace(go.Scatter(x=hist.index, y=bbands['BBL_20_2.0'], line=dict(color='gray', dash='dash'), name="Banda Inf"))
            
            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, 
                              margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#0b0e14", plot_bgcolor="#0b0e14")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aguardando dados do mercado para este ativo...")

        # Notícias
        st.subheader("📰 Radar de Notícias")
        try:
            n_res = requests.get(f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}').json()
            for art in n_res.get('articles', [])[:3]:
                st.info(f"**{art['source']['name']}**: {art['title']}")
        except: st.write("Radar de notícias indisponível.")

    with col_r:
        # Puxa o detalhe da IA que guardamos na home
        details = next((item for item in st.session_state.top_10 if item["ticker"] == t), {})
        
        st.markdown(f"""
        <div class="ai-report-container">
            <h3>🎯 Plano de Trade IA</h3>
            <p><b>Probabilidade:</b> {details.get('probabilidade')}%</p>
            <p><b>Estratégia:</b> {details.get('estrategia')}</p>
            <hr>
            <p><b>Técnico:</b> {details.get('tecnico')}</p>
            <p><b>Fundamental:</b> {details.get('fundamental')}</p>
            <p><b>Entrada Sugerida:</b> ${details.get('entrada')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Alvo de Analistas de Bancos
        try:
            si = yf.Ticker(t).info
            target = si.get('targetMeanPrice', 'N/A')
            st.metric("Alvo Médio dos Bancos", f"${target}")
        except: st.write("Dados fundamentalistas em carga...")
