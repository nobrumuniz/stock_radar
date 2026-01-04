import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner v4", page_icon="📈", layout="wide")

# Carregar chaves dos Secrets (Segurança)
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception:
    st.error("⚠️ Erro: Configure as chaves 'OPENAI_API_KEY' e 'NEWS_API_KEY' nos Secrets do Streamlit.")
    st.stop()

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    div[data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 1px solid #00ffcc !important;
        border-radius: 10px; padding: 15px;
    }
    [data-testid="stMetricLabel"] { 
        color: #00ffcc !important; 
        font-weight: bold !important;
        font-size: 20px !important;
    }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; }
    .news-card {
        background-color: #1e2130; padding: 12px; border-radius: 8px;
        margin-bottom: 10px; border-left: 5px solid #00ffcc; color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---

def get_gpt_analysis(ticker):
    try:
        prompt = f"Aja como um analista sênior. Resuma as 3 últimas recomendações de grandes bancos para a ação {ticker}. Inclua preço alvo e se é compra ou manutenção."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content
    except:
        return "Resumo de analistas temporariamente indisponível."

# --- NAVEGAÇÃO ---
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# --- TELA HOME ---
if st.session_state.page == 'home':
    st.title("🚀 Alpha Scanner v4 - Pro Trader")
    
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY', 'QQQ', 'COIN', 'MSTR']

    if st.sidebar.button("🔄 ESCANEAR MERCADO"):
        with st.spinner('Baixando dados e calculando probabilidades...'):
            # Download em massa para evitar bloqueio do Yahoo Finance
            data_all = yf.download(tickers, period="1mo", interval="1h", group_by='ticker', progress=False)
            
            results = []
            for t in tickers:
                try:
                    df = data_all[t].dropna()
                    if df.empty: continue
                    
                    price = df['Close'].iloc[-1]
                    rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                    
                    # Score de probabilidade
                    score = 50
                    if rsi < 40: score += 20
                    elif rsi > 70: score -= 10
                    if df['Close'].iloc[-1] > df['Open'].iloc[-1]: score += 15
                    
                    results.append({
                        "Ticker": t, 
                        "Probabilidade %": round(score, 1), 
                        "Preço": round(float(price), 2), 
                        "RSI": round(float(rsi), 1)
                    })
                except:
                    continue
            
            st.session_state.full_data = pd.DataFrame(results).sort_values("Probabilidade %", ascending=False)

    if 'full_data' in st.session_state:
        # Cards de Destaque
        top3 = st.session_state.full_data.head(3).to_dict('records')
        c1, c2, c3 = st.columns(3)
        for i, col in enumerate([c1, c2, c3]):
            col.metric(label=f"Ticker: {top3[i]['Ticker']}", 
                       value=f"${top3[i]['Preço']}", 
                       delta=f"{top3[i]['Probabilidade %']}% Score")

        st.write("---")
        
        # Seleção de Detalhes
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            selected = st.selectbox("Selecione uma ação para relatório completo:", st.session_state.full_data['Ticker'])
        with col_btn:
            st.write("##")
            if st.button("🔍 VER DETALHES"):
                st.session_state.selected_ticker = selected
                st.session_state.page = 'details'
                st.rerun()
            
        st.dataframe(st.session_state.full_data, use_container_width=True)

# --- TELA DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    if st.button("⬅️ VOLTAR AO RANKING"):
        st.session_state.page = 'home'
        st.rerun()
    
    st.title(f"📊 Relatório Alpha: {t}")
    
    col_chart, col_ia = st.columns([2, 1])
    
    with col_chart:
        # Gráfico em Tempo Real
        df_plot = yf.download(t, period="5d", interval="15m", progress=False)
        fig = go.Figure(data=[go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
            low=df_plot['Low'], close=df_plot['Close'],
            increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b'
        )])
        fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Notícias
        st.subheader("📰 Notícias Recentes")
        try:
            url = f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}'
            news = requests.get(url).json().get('articles', [])[:3]
            for n in news:
                st.markdown(f'<div class="news-card"><b>{n["source"]["name"]}</b><br>{n["title"]}</div>', unsafe_allow_html=True)
        except:
            st.write("Notícias indisponíveis no momento.")

    with col_ia:
        st.subheader("🤖 Analista IA (ChatGPT)")
        with st.status("Analisando recomendações de Bancos..."):
            analise = get_gpt_analysis(t)
            st.info(analise)
        
        st.write("---")
        # Upside e Target
        try:
            si = yf.Ticker(t).info
            atual = si.get('currentPrice', 1)
            alvo = si.get('targetMeanPrice', atual)
            upside = ((alvo/atual)-1)*100
            st.metric("Upside Estimado", f"{round(upside, 1)}%", delta=f"Alvo: ${alvo}")
        except:
            st.write("Dados fundamentalistas indisponíveis.")
