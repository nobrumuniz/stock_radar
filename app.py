import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner AI v12", page_icon="📈", layout="wide")

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("❌ Configure as chaves nos Secrets do Streamlit.")
    st.stop()

# --- CSS DE ALTA VISIBILIDADE ---
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
    [data-testid="stMetricValue"] div { color: #ffffff !important; font-size: 26px !important; }
    
    .ai-card {
        background: #1e2130; padding: 25px; border-radius: 12px;
        border-left: 6px solid #00ffcc; color: white !important;
        line-height: 1.6; margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .ai-card h3, .ai-card b { color: #00ffcc !important; }
    .stDataFrame { border: 1px solid #00ffcc; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---

def fetch_clean_data(ticker, period="60d", interval="60m"):
    """Baixa dados e garante colunas limpas"""
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def get_ai_ranking(market_data):
    prompt = f"""
    Analise estes dados: {market_data}.
    Selecione as 10 melhores para Day Trade hoje (Alvo 1%).
    Retorne um JSON com a chave 'ranking'.
    Para a 'probabilidade', use números INTEIROS de 0 a 100 (ex: 85 e NÃO 0.85).
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um analista que retorna JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        res = json.loads(response.choices[0].message.content)
        return res if 'ranking' in res else {"ranking": list(res.values())[0]}
    except: return None

# --- TELA HOME ---
if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🚀 Alpha Scanner AI v12")
    
    if st.sidebar.button("🔍 INICIAR SCANNER"):
        with st.spinner('IA analisando oportunidades...'):
            tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'PLTR', 'SPY', 'QQQ']
            raw_market = []
            # Coleta em lote
            batch = yf.download(tickers, period="5d", interval="1h", group_by='ticker', progress=False)
            for t in tickers:
                try:
                    d = batch[t].dropna()
                    if d.empty: continue
                    raw_market.append({"t": t, "p": round(d['Close'].iloc[-1], 2), "rsi": round(ta.rsi(d['Close']).iloc[-1], 1)})
                except: continue
            
            res = get_ai_ranking(raw_market)
            if res: st.session_state.top_10 = res['ranking']

    if 'top_10' in st.session_state:
        # Correção automática de probabilidade (ex: 0.85 -> 85)
        for item in st.session_state.top_10:
            if float(item['probabilidade']) <= 1.0:
                item['probabilidade'] = int(float(item['probabilidade']) * 100)
        
        t10 = st.session_state.top_10
        cols = st.columns(3)
        for i in range(min(3, len(t10))):
            cols[i].metric(label=t10[i]['ticker'], value=f"{int(t10[i]['probabilidade'])}% Prob.", delta="Destaque IA")
        
        st.write("---")
        df_rank = pd.DataFrame(t10)
        st.subheader("📋 Ranking de Entradas")
        st.dataframe(df_rank[['ticker', 'probabilidade', 'entrada', 'tecnico']], use_container_width=True)

        sel = st.selectbox("Selecione para abrir o terminal:", df_rank['ticker'])
        if st.button("🔍 ABRIR TERMINAL OPERACIONAL"):
            st.session_state.selected_ticker = sel
            st.session_state.page = 'details'
            st.rerun()

# --- TELA DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR AO RANKING", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    # Seletor de Timeframe
    tf = st.sidebar.selectbox("Frequência", ["5m", "15m", "30m", "60m", "1d"], index=1)
    p_map = {"5m":"1d", "15m":"3d", "30m":"5d", "60m":"7d", "1d":"1y"}

    st.title(f"⚡ Operação Day Trade: {t}")
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        hist = fetch_clean_data(t, p_map[tf], tf)
        if hist is not None:
            # Cálculos Técnicos
            hist['EMA9'] = ta.ema(hist['Close'], length=9)
            hist['EMA21'] = ta.ema(hist['Close'], length=21)
            bb = ta.bbands(hist['Close'], length=20)
            
            # Identificação segura das colunas das Bandas de Bollinger
            col_bbu = [c for c in bb.columns if c.startswith('BBU')][0]
            col_bbl = [c for c in bb.columns if c.startswith('BBL')][0]
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Preço"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA9'], line=dict(color='#FFD700', width=1.2), name="Média 9"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA21'], line=dict(color='#00FFFF', width=1.2), name="Média 21"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[col_bbu], line=dict(color='gray', dash='dash', width=1), name="Banda Sup"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[col_bbl], line=dict(color='gray', dash='dash', width=1), name="Banda Inf"))
            
            fig.update_layout(template="plotly_dark", height=550, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Dados indisponíveis para este ativo neste tempo gráfico.")

        st.subheader("📰 Radar de Notícias")
        try:
            n_res = requests.get(f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}').json()
            for art in n_res.get('articles', [])[:2]:
                st.info(f"**{art['source']['name']}**: {art['title']}")
        except: pass

    with col_r:
        d = next((item for item in st.session_state.top_10 if item["ticker"] == t), {})
        st.markdown(f"""
        <div class="ai-card">
            <h3>🎯 Plano de Trade IA</h3>
            <p><b>Probabilidade:</b> {int(d.get('probabilidade', 0))}%</p>
            <p><b>Estratégia:</b> {d.get('estrategia')}</p>
            <p><b>Sugestão de Entrada:</b> ${d.get('entrada')}</p>
            <hr>
            <p><b>Análise Técnica:</b> {d.get('tecnico')}</p>
            <p><b>Análise Fundamentalista:</b> {d.get('fundamental')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            si = yf.Ticker(t).info
            st.metric("Alvo Médio (Bancos)", f"${si.get('targetMeanPrice', 'N/A')}")
        except: pass
