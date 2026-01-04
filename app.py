import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from textblob import TextBlob

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AI Alpha Trader Pro", page_icon="📈", layout="wide")

# --- ESTILIZAÇÃO CSS (CORREÇÃO DE CORES) ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 24px !important; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: bold !important; }
    [data-testid="stMetricDelta"] { color: #00ffcc !important; }
    .stDataFrame { background-color: #161b22; border-radius: 10px; }
    h1, h2, h3 { color: #00ffcc !important; }
    .stButton>button { 
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%); 
        color: white; border: none; border-radius: 10px; font-weight: bold; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = None

# --- CONFIGURAÇÕES ---
NEWS_API_KEY = "640760e6c18045338e5ea0c4f5354a2f"
TICKERS = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY', 'QQQ', 'COIN', 'BA', 'MSTR']

# --- FUNÇÕES ---

def get_sentiment(ticker):
    url = f'https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
    try:
        response = requests.get(url).json()
        articles = response.get('articles', [])[:5]
        if not articles: return 0.1
        sentiments = [TextBlob(art['title']).sentiment.polarity for art in articles]
        return sum(sentiments) / len(sentiments)
    except: return 0

def fetch_data(symbol, interval="15m", period="5d"):
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def analyze_stock(symbol):
    try:
        df_daily = fetch_data(symbol, "1d", "1y")
        df_15m = fetch_data(symbol, "15m", "5d")
        
        # Técnica
        df_daily['EMA200'] = ta.ema(df_daily['Close'], length=200)
        trend_up = df_daily['Close'].iloc[-1] > df_daily['EMA200'].iloc[-1]
        df_15m['RSI'] = ta.rsi(df_15m['Close'], length=14)
        df_15m['EMA9'] = ta.ema(df_15m['Close'], length=9)
        df_15m['EMA21'] = ta.ema(df_15m['Close'], length=21)
        
        score = 0
        if trend_up: score += 40
        if df_15m['EMA9'].iloc[-1] > df_15m['EMA21'].iloc[-1]: score += 30
        rsi = df_15m['RSI'].iloc[-1]
        if 40 < rsi < 70: score += 30
        
        sentiment = get_sentiment(symbol)
        final_score = (score * 0.7) + ((sentiment + 1) * 15)
        
        return round(final_score, 1), rsi, "Positivo" if sentiment > 0 else "Neutro/Neg"
    except: return 0, 50, "N/A"

# --- RENDERIZAÇÃO ---

if st.session_state.page == 'home':
    st.title("🚀 Alpha Scanner v2 - Mercado Americano")
    
    if st.sidebar.button("🔄 ATUALIZAR RANKING"):
        with st.spinner('Analisando mercado...'):
            results = []
            for t in TICKERS:
                score, rsi, sent = analyze_stock(t)
                price = yf.Ticker(t).fast_info['last_price']
                results.append({"Ticker": t, "Probabilidade %": score, "Sentimento": sent, "RSI": round(rsi,1), "Preço": round(price,2)})
            st.session_state.results = pd.DataFrame(results).sort_values("Probabilidade %", ascending=False)

    if 'results' in st.session_state:
        # Top Cards
        top = st.session_state.results.head(3).to_dict('records')
        cols = st.columns(3)
        for i, c in enumerate(cols):
            with c:
                st.metric(label=f"#{i+1} {top[i]['Ticker']}", value=f"${top[i]['Preço']}", delta=f"{top[i]['Probabilidade %']}% Prob.")

        st.write("---")
        st.subheader("📋 Ranking de Entradas (Clique no Ticker para Detalhes)")
        
        # Seleção de Ação para Detalhes
        selected = st.selectbox("Selecione uma ação para análise profunda:", st.session_state.results['Ticker'])
        if st.button("🔍 VER ANÁLISE DETALHADA"):
            st.session_state.selected_stock = selected
            st.session_state.page = 'details'
            st.rerun()

        st.dataframe(st.session_state.results, use_container_width=True)
    else:
        st.info("Clique no botão à esquerda para iniciar.")

elif st.session_state.page == 'details':
    ticker = st.session_state.selected_stock
    st.button("⬅️ VOLTAR AO RANKING", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    st.title(f"📊 Análise Detalhada: {ticker}")
    
    # Controles de Gráfico
    c1, c2 = st.columns([1, 3])
    with c1:
        st.subheader("Configurações")
        tf = st.selectbox("Timeframe", ["5m", "15m", "30m", "60m", "1d"], index=1)
        periodo = "1d" if tf in ["5m", "15m"] else "1mo"
        if st.button("🔄 Refresh Dados"): st.rerun()
        
    # Busca dados para o gráfico
    df_chart = fetch_data(ticker, tf, periodo)
    df_chart['EMA9'] = ta.ema(df_chart['Close'], length=9)
    df_chart['EMA21'] = ta.ema(df_chart['Close'], length=21)

    with c2:
        fig = go.Figure(data=[
            go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], 
                           name="Price", increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b'),
            go.Scatter(x=df_chart.index, y=df_chart['EMA9'], line=dict(color='yellow', width=1), name='EMA 9'),
            go.Scatter(x=df_chart.index, y=df_chart['EMA21'], line=dict(color='magenta', width=1), name='EMA 21')
        ])
        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # Info Fundamentalista Básica
    st.write("---")
    info = yf.Ticker(ticker).info
    f1, f2, f3 = st.columns(3)
    f1.write(f"**Volume Médio:** {info.get('averageVolume', 'N/A')}")
    f2.write(f"**Target Price (Analistas):** ${info.get('targetMeanPrice', 'N/A')}")
    f3.write(f"**Setor:** {info.get('sector', 'N/A')}")
