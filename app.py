import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
import google.generativeai as genai
from textblob import TextBlob

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Alpha Scanner AI v3", page_icon="🚀", layout="wide")

# --- CHAVES DE API (Configure aqui) ---
NEWS_API_KEY = "640760e6c18045338e5ea0c4f5354a2f"
GEMINI_API_KEY = "AIzaSyAUc-_3tUhQp1ruHcyA5vkDcVmDZEzvFu0" # Coloque sua chave do Google AI aqui

# Configura o Google Gemini
if GEMINI_API_KEY != "AIzaSyAUc-_3tUhQp1ruHcyA5vkDcVmDZEzvFu0":
    genai.configure(api_key=GEMINI_API_KEY)

# --- ESTILIZAÇÃO CSS (CORREÇÃO DE CORES E VISIBILIDADE) ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    /* Estilo dos Cards de Top 3 */
    [data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #00ffcc;
        border-radius: 12px;
        padding: 15px;
    }
    [data-testid="stMetricLabel"] { 
        color: #00ffcc !important; 
        font-size: 20px !important; 
        font-weight: bold !important; 
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    
    .news-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 5px solid #4facfe;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---

def get_detailed_news(ticker):
    url = f'https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
    try:
        response = requests.get(url).json()
        return response.get('articles', [])[:5]
    except: return []

def ask_gemini_analysts(ticker):
    if GEMINI_API_KEY == "SUA_CHAVE_GEMINI_AQUI":
        return "⚠️ Configure a Gemini API Key para ver as recomendações dos bancos."
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"De forma curta e direta, liste as 3 recomendações mais recentes de grandes bancos (ex: Goldman Sachs, JP Morgan) para a ação {ticker}. Inclua se a recomendação é Compra/Venda e o preço alvo se disponível."
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Não foi possível carregar as recomendações dos analistas agora."

def fetch_data(symbol, interval="15m", period="5d"):
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# --- NAVEGAÇÃO ---
if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🚀 Alpha Scanner AI v3 - Mercado Americano")
    
    if st.sidebar.button("🔄 ESCANEAR MERCADO"):
        with st.spinner('Analisando gráficos e IA...'):
            tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY', 'QQQ', 'COIN', 'MSTR']
            results = []
            for t in tickers:
                stock = yf.Ticker(t)
                price = stock.fast_info['last_price']
                target = stock.info.get('targetMeanPrice', price)
                upside = ((target / price) - 1) * 100
                
                # Análise simples para o ranking
                df = fetch_data(t, "1h", "1mo")
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                score = 50 + (10 if upside > 10 else 0) + (20 if rsi < 70 else -10)
                
                results.append({
                    "Ticker": t, "Probabilidade %": round(score, 1), 
                    "Preço Atual": round(price, 2), "Alvo Analistas": round(target, 2),
                    "Upside %": round(upside, 1)
                })
            st.session_state.results = pd.DataFrame(results).sort_values("Probabilidade %", ascending=False)

    if 'results' in st.session_state:
        top = st.session_state.results.head(3).to_dict('records')
        c1, c2, c3 = st.columns(3)
        for i, col in enumerate([c1, c2, c3]):
            with col:
                st.metric(label=top[i]['Ticker'], value=f"${top[i]['Preço Atual']}", delta=f"{top[i]['Upside %']}% Upside")

        st.write("---")
        selected = st.selectbox("Escolha uma ação para análise profunda IA:", st.session_state.results['Ticker'])
        if st.button("🔍 ANALISAR COM IA E VER GRÁFICOS"):
            st.session_state.selected_stock = selected
            st.session_state.page = 'details'
            st.rerun()
        
        st.dataframe(st.session_state.results, use_container_width=True)

elif st.session_state.page == 'details':
    ticker = st.session_state.selected_stock
    st.button("⬅️ VOLTAR AO RANKING", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    st.title(f"📊 Relatório Alpha: {ticker}")
    
    # --- COLUNA DA ESQUERDA: GRÁFICO ---
    col_chart, col_ai = st.columns([2, 1])
    
    with col_chart:
        tf = st.selectbox("Tempo Gráfico", ["5m", "15m", "60m", "1d"], index=1)
        df_plot = fetch_data(ticker, tf, "1mo" if tf=="1d" else "5d")
        fig = go.Figure(data=[go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
                                            increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b')])
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Notícias Reais
        st.subheader("📰 Radar de Notícias Recentes")
        news_list = get_detailed_news(ticker)
        for art in news_list:
            st.markdown(f"""<div class="news-card">
                <b>{art['source']['name']}</b>: <a href="{art['url']}" target="_blank" style="color:#00ffcc">{art['title']}</a>
            </div>""", unsafe_allow_html=True)

    # --- COLUNA DA DIREITA: IA E BANCOS ---
    with col_ai:
        st.subheader("🤖 Recomendação de Bancos (IA)")
        with st.status("Consultando Inteligência do Google..."):
            summary = ask_gemini_analysts(ticker)
            st.write(summary)
        
        st.write("---")
        st.subheader("🎯 Potencial de Ganho")
        stock_info = yf.Ticker(ticker).info
        cur = stock_info.get('currentPrice', 1)
        target = stock_info.get('targetMeanPrice', cur)
        upside = ((target / cur) - 1) * 100
        
        st.metric("Upside Projetado", f"{round(upside, 1)}%", delta_color="normal")
        st.write(f"Preço Alvo Médio: **${target}**")
        st.caption("Baseado na média de analistas de Wall Street.")
    f2.write(f"**Target Price (Analistas):** ${info.get('targetMeanPrice', 'N/A')}")
    f3.write(f"**Setor:** {info.get('sector', 'N/A')}")

