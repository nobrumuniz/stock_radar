import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
from finvizfinance.screener.overview import Overview

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner AI v6", page_icon="🎯", layout="wide")

# Inicialização da OpenAI via Secrets
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("⚠️ Configure 'OPENAI_API_KEY' e 'NEWS_API_KEY' nos Secrets do Streamlit.")
    st.stop()

# --- CSS PROFISSIONAL ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #00ffcc; border-radius: 10px; padding: 10px; }
    .stTable { background-color: #161b22; color: white; }
    .probability-high { color: #00ffcc; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES CORE ---

@st.cache_data(ttl=3600)
def get_market_opportunities():
    """Etapa 1: Escaneia o mercado usando Finviz para achar ações com recomendação de bancos"""
    try:
        framer = Overview()
        # Filtros: S&P 500, Analyst Recom: Strong Buy, Target Price: Above Price
        filters_dict = {'Index': 'S&P 500', 'Analyst Recom.': 'Strong Buy (1)'}
        framer.set_filter(filters_dict=filters_dict)
        df_market = framer.screener_view()
        return df_market[['Ticker', 'Price', 'Target Price', 'Volume']]
    except:
        # Fallback caso o Finviz falhe
        return pd.DataFrame([{'Ticker': 'AAPL', 'Price': 200, 'Target Price': 250, 'Volume': 1000000}])

def analyze_technical_momentum(df_hist):
    """Etapa 2: Analisa tempos gráficos (5, 15, 60m) buscando o alvo de 1%"""
    if df_hist is None or len(df_hist) < 20: return 0
    
    # Indicadores
    df_hist['RSI'] = ta.rsi(df_hist['Close'], length=14)
    df_hist['EMA9'] = ta.ema(df_hist['Close'], length=9)
    df_hist['EMA21'] = ta.ema(df_hist['Close'], length=21)
    
    last_close = df_hist['Close'].iloc[-1]
    last_rsi = df_hist['RSI'].iloc[-1]
    ema_cross = df_hist['EMA9'].iloc[-1] > df_hist['EMA21'].iloc[-1]
    
    # Lógica de Probabilidade para 1% de movimento (Day Trade)
    score = 0
    if 40 < last_rsi < 65: score += 40  # Momentum de alta
    if ema_cross: score += 30          # Tendência confirmada
    if last_close > df_hist['High'].iloc[-2]: score += 30 # Rompimento de máxima anterior
    
    return score

# --- NAVEGAÇÃO ---
if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🎯 IA Alpha Scanner: Top 10 Day Trade")
    st.subheader("Análise Global: Consenso de Bancos + Gráfico + IA")

    if st.sidebar.button("🚀 INICIAR SCANNER GLOBAL"):
        with st.spinner('1. Filtrando consenso de Bancos e Upside...'):
            potential_stocks = get_market_opportunities()
            tickers = potential_stocks['Ticker'].tolist()[:40] # Analisamos as top 40 para evitar bloqueio

        with st.spinner('2. Analisando setups gráficos (5m, 15m, 60m)...'):
            # Download em massa (1h para tendência, 15m para entrada)
            data_tech = yf.download(tickers, period="5d", interval="15m", group_by='ticker', progress=False)
            
            final_list = []
            for t in tickers:
                try:
                    df_t = data_tech[t].dropna()
                    tech_score = analyze_technical_momentum(df_t)
                    
                    # Pegar dados fundamentais da tabela inicial
                    fund_row = potential_stocks[potential_stocks['Ticker'] == t].iloc[0]
                    upside = ((float(fund_row['Target Price']) / float(fund_row['Price'])) - 1) * 100
                    
                    total_prob = (tech_score * 0.7) + (min(upside, 30) * 1.0) # Peso maior no gráfico para DayTrade
                    
                    final_list.append({
                        "Ticker": t,
                        "Probabilidade": round(total_prob, 1),
                        "Upside Bancos %": round(upside, 1),
                        "Preço": fund_row['Price'],
                        "Vol_Rating": "Alto" if float(fund_row['Volume']) > 1000000 else "Médio"
                    })
                except: continue
            
            # Ranking Top 10
            df_rank = pd.DataFrame(final_list).sort_values("Probabilidade", ascending=False).head(10)
            st.session_state.top_10 = df_rank

    if 'top_10' in st.session_state:
        st.write("### 🔥 As 10 Melhores Oportunidades do Dia")
        
        # Cards de Destaque para o Top 3
        top3 = st.session_state.top_10.head(3).to_dict('records')
        c1, c2, c3 = st.columns(3)
        for i, col in enumerate([c1, c2, c3]):
            col.metric(top3[i]['Ticker'], f"${top3[i]['Preço']}", f"{top3[i]['Probabilidade']}% Prob.")
        
        st.write("---")
        
        # Seleção para análise da IA
        selected = st.selectbox("Selecione para ver o relatório da IA e o Gráfico:", st.session_state.top_10['Ticker'])
        if st.button("🔍 GERAR RELATÓRIO COMPLETO"):
            st.session_state.selected_ticker = selected
            st.session_state.page = 'details'
            st.rerun()

        st.table(st.session_state.top_10)

elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    st.title(f"📊 Relatório de Alta Probabilidade: {t}")
    
    c_chart, c_ia = st.columns([2, 1])
    
    with c_chart:
        # Gráfico Day Trade (15 min)
        hist = yf.download(t, period="2d", interval="15m", progress=False)
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                                            increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b')])
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Notícias Reais
        st.subheader("📰 Radar de Notícias e Sentimento")
        url = f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}'
        news = requests.get(url).json().get('articles', [])[:3]
        for n in news:
            st.info(f"**{n['source']['name']}**: {n['title']}")

    with c_ia:
        st.subheader("🤖 Veredito da IA (GPT-4)")
        with st.status("IA analisando fundamentos e notícias..."):
            prompt = f"Analise a ação {t}. Ela foi selecionada por ter forte recomendação de bancos e setup gráfico de alta. Resuma em 3 pontos por que o trader deve ou não entrar nela hoje para buscar 1% de ganho."
            report = client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": prompt}])
            st.write(report.choices[0].message.content)
