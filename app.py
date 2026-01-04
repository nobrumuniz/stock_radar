import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from textblob import TextBlob
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AI Alpha Trader", page_icon="📈", layout="wide")

# --- ESTILIZAÇÃO CSS (INTERFACE LINDA) ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e445e; }
    .stDataFrame { border-radius: 10px; }
    h1, h2, h3 { color: #00ffcc !important; font-family: 'Inter', sans-serif; }
    .stButton>button { 
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%); 
        color: white; border: none; border-radius: 20px; padding: 10px 25px;
        font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0px 4px 15px rgba(0, 242, 254, 0.4); }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES E APIs ---
NEWS_API_KEY = "640760e6c18045338e5ea0c4f5354a2f"
TICKERS = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY', 'QQQ', 'COIN']

# --- FUNÇÕES DE ANÁLISE ---

def get_sentiment(ticker):
    """Analisa o sentimento das notícias via NewsAPI"""
    url = f'https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
    try:
        response = requests.get(url).json()
        articles = response.get('articles', [])[:5] # Pega as 5 mais recentes
        if not articles: return 0
        
        sentiments = []
        for art in articles:
            analysis = TextBlob(art['title'])
            sentiments.append(analysis.sentiment.polarity)
        return sum(sentiments) / len(sentiments)
    except:
        return 0

def analyze_tech(symbol):
    """Análise Multi-Timeframe e Indicadores"""
    try:
        # Puxando dados
        df_daily = yf.download(symbol, period="1y", interval="1d", progress=False)
        df_15m = yf.download(symbol, period="5d", interval="15m", progress=False)
        
        # Tendência Diária (EMA 200)
        df_daily['EMA200'] = ta.ema(df_daily['Close'], length=200)
        trend_up = df_daily['Close'].iloc[-1] > df_daily['EMA200'].iloc[-1]
        
        # Indicadores 15min (Day Trade)
        df_15m['RSI'] = ta.rsi(df_15m['Close'], length=14)
        df_15m['EMA9'] = ta.ema(df_15m['Close'], length=9)
        df_15m['EMA21'] = ta.ema(df_15m['Close'], length=21)
        
        last_rsi = df_15m['RSI'].iloc[-1]
        crossover = df_15m['EMA9'].iloc[-1] > df_15m['EMA21'].iloc[-1]
        
        # Score Técnico (0-70)
        score = 0
        if trend_up: score += 25
        if crossover: score += 25
        if 40 < last_rsi < 70: score += 20
        
        return score, df_15m, last_rsi
    except:
        return 0, None, 50

# --- DASHBOARD UI ---

st.sidebar.title("⚡ Alpha Scanner v2")
st.sidebar.write("Mercado Americano (Real-time)")

if st.sidebar.button("ESCANEAR OPORTUNIDADES"):
    results = []
    progress_bar = st.progress(0)
    
    for i, t in enumerate(TICKERS):
        # 1. Análise Técnica
        score_tech, df_hist, rsi = analyze_tech(t)
        
        # 2. Análise de Sentimento (Notícias)
        sentiment = get_sentiment(t)
        score_news = (sentiment + 1) * 15 # Normaliza de -1/1 para 0-30
        
        # 3. Score Final (0-100)
        total_score = score_tech + score_news
        
        results.append({
            "Ticker": t,
            "Probabilidade": round(total_score, 1),
            "RSI": round(rsi, 2),
            "Sentimento": "Positivo" if sentiment > 0 else "Negativo",
            "Preço": round(yf.Ticker(t).fast_info['last_price'], 2),
            "df": df_hist
        })
        progress_bar.progress((i + 1) / len(TICKERS))

    # Ranking
    df_results = pd.DataFrame(results).sort_values(by="Probabilidade", ascending=False)

    # Destaque: Top 3 Cards
    st.subheader("🏆 Melhores Entradas para Agora")
    c1, c2, c3 = st.columns(3)
    top_stocks = df_results.head(3).to_dict('records')
    
    for i, col in enumerate([c1, c2, c3]):
        with col:
            st.metric(label=f"#{i+1} {top_stocks[i]['Ticker']}", 
                      value=f"${top_stocks[i]['Preço']}", 
                      delta=f"{top_stocks[i]['Probabilidade']}% Score")

    # Tabela Geral
    st.write("---")
    st.subheader("📋 Ranking Completo de Probabilidade")
    st.table(df_results[['Ticker', 'Probabilidade', 'Sentimento', 'RSI', 'Preço']])

    # Gráfico do Top #1
    st.write("---")
    st.subheader(f"🔍 Análise Detalhada: {top_stocks[0]['Ticker']} (15 min)")
    fig = go.Figure(data=[go.Candlestick(
        x=top_stocks[0]['df'].index,
        open=top_stocks[0]['df']['Open'],
        high=top_stocks[0]['df']['High'],
        low=top_stocks[0]['df']['Low'],
        close=top_stocks[0]['df']['Close'],
        name="Candles"
    )])
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

else:
    # Estado Inicial
    st.info("👋 Bem-vindo ao AI Alpha Trader. Clique no botão lateral para analisar o mercado americano em tempo real.")
    
    # Exibir algumas notícias globais enquanto não carrega
    st.subheader("🌐 Radar de Notícias Global (Market Sentiment)")
    try:
        url_global = f'https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}'
        news = requests.get(url_global).json()['articles'][:4]
        n1, n2 = st.columns(2)
        for i, article in enumerate(news):
            with (n1 if i % 2 == 0 else n2):
                st.warning(f"**{article['source']['name']}**: {article['title']}")
    except:
        st.write("Conectando ao radar de notícias...")