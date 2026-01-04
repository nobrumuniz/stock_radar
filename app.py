import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
import json

# --- CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="Alpha Scanner Global AI", page_icon="🎯", layout="wide")

# Inicialização Segura das APIs
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("❌ ERRO: Configure 'OPENAI_API_KEY' e 'NEWS_API_KEY' nos Secrets do Streamlit.")
    st.stop()

# --- CSS DEFINITIVO (VISIBILIDADE TOTAL E CORES NEON) ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14 !important; color: white !important; }
    [data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 2px solid #00ffcc !important;
        border-radius: 12px !important;
        padding: 15px !important;
    }
    [data-testid="stMetricLabel"] div { color: #00ffcc !important; font-size: 20px !important; font-weight: bold !important; }
    [data-testid="stMetricValue"] div { color: #ffffff !important; font-size: 28px !important; }
    .ai-card {
        background: #1e2130; padding: 25px; border-radius: 15px;
        border-left: 8px solid #00ffcc; color: white !important;
        line-height: 1.6; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .ai-card h3, .ai-card b { color: #00ffcc !important; }
    .stDataFrame { border: 1px solid #00ffcc !important; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- ENGINE DE SCANNER GLOBAL ---

@st.cache_data(ttl=3600)
def get_global_universe():
    """Busca dinamicamente a lista do S&P 500 para escanear o mercado inteiro"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        return df['Symbol'].tolist()
    except:
        return ['AAPL', 'NVDA', 'TSLA', 'AMD', 'MSFT', 'META', 'AMZN', 'GOOGL', 'NFLX', 'COIN']

def normalize_ai_data(resp):
    """Garante que 'ticker' seja legível e 'probabilidade' esteja em % real"""
    try:
        items = resp.get('ranking', [])
        clean = []
        for i in items:
            d = {k.lower(): v for k, v in i.items()}
            # Fix Probabilidade: 0.85 ou 0.9 -> 85% ou 90%
            p = d.get('probabilidade', 0)
            if isinstance(p, (float, int)) and p <= 1.0: d['probabilidade'] = int(p * 100)
            elif isinstance(p, str): d['probabilidade'] = p.replace('%', '')
            clean.append(d)
        return clean
    except: return []

# --- NAVEGAÇÃO ---
if 'page' not in st.session_state: st.session_state.page = 'home'

# --- TELA HOME ---
if st.session_state.page == 'home':
    st.title("🎯 IA Alpha Scanner: Universo Global")
    st.subheader("Análise Institucional: S&P 500 + NASDAQ (Foco Day Trade 1%)")

    if st.sidebar.button("🚀 ESCANEAR TODO O MERCADO AGORA"):
        with st.spinner('Varrendo mercado global em busca de Volume e Upside...'):
            universe = get_global_universe()
            # Filtramos as 40 mais ativas do momento para a IA não travar
            batch_data = yf.download(universe[:40], period="5d", interval="1h", group_by='ticker', progress=False)
            
            market_snapshot = []
            for t in universe[:40]:
                try:
                    df = batch_data[t].dropna()
                    if df.empty: continue
                    market_snapshot.append({
                        "ticker": t, "preco": round(df['Close'].iloc[-1], 2),
                        "rsi": round(ta.rsi(df['Close']).iloc[-1], 1),
                        "volatilidade": round(df['Close'].pct_change().std()*100, 2)
                    })
                except: continue

            # PROMPT DE ELITE (HEDGE FUND MODE)
            prompt = f"""
            Analise este snapshot quantitativo: {market_snapshot}.
            Seu objetivo é selecionar o TOP 10 para Day Trade hoje com alvo de 1%.
            Considere: Médias Móveis, RSI e Momentum.
            Retorne EXCLUSIVAMENTE um JSON com a chave 'ranking' contendo: 
            ticker, probabilidade, entrada, tecnico, fundamental, estrategia.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Você é um analista sênior quantitativo."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            res_json = json.loads(response.choices[0].message.content)
            st.session_state.top_10 = normalize_ai_data(res_json)

    if 'top_10' in st.session_state:
        t10 = st.session_state.top_10
        cols = st.columns(min(3, len(t10)))
        for i in range(min(3, len(t10))):
            cols[i].metric(label=f"Ativo: {t10[i].get('ticker')}", value=f"{t10[i].get('probabilidade')}% Prob.")
        
        st.write("---")
        st.subheader("📋 Ranking Estruturado (Consenso IA)")
        df_rank = pd.DataFrame(t10)
        st.dataframe(df_rank, use_container_width=True)

        sel = st.selectbox("Selecione para abrir o terminal:", [x.get('ticker') for x in t10])
        if st.button("🔍 ABRIR TERMINAL OPERACIONAL"):
            st.session_state.selected_ticker = sel
            st.session_state.page = 'details'
            st.rerun()

# --- TELA DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR AO RANKING", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    # Seletor de Timeframe (5, 15, 30, 60m, 1d)
    tf = st.sidebar.selectbox("Frequência Gráfica", ["5m", "15m", "30m", "60m", "1d"], index=1)
    p_map = {"5m":"1d", "15m":"3d", "30m":"5d", "60m":"7d", "1d":"1y"}

    st.title(f"⚡ Operação Detalhada: {t}")
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        hist = yf.download(t, period=p_map[tf], interval=tf, progress=False)
        if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
        
        if not hist.empty:
            # Indicadores Profissionais
            hist['EMA9'] = ta.ema(hist['Close'], length=9)
            hist['EMA21'] = ta.ema(hist['Close'], length=21)
            bb = ta.bbands(hist['Close'], length=20)
            bbu = [c for c in bb.columns if c.startswith('BBU')][0]
            bbl = [c for c in bb.columns if c.startswith('BBL')][0]
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Preço",
                                        increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b'))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA9'], line=dict(color='#FFD700', width=1.5), name="EMA 9 (Amarela)"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA21'], line=dict(color='#00FFFF', width=1.5), name="EMA 21 (Ciano)"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[bbu], line=dict(color='rgba(255,255,255,0.3)', dash='dash'), name="Banda Sup"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[bbl], line=dict(color='rgba(255,255,255,0.3)', dash='dash'), name="Banda Inf"))
            
            fig.update_layout(template="plotly_dark", height=550, xaxis_rangeslider_visible=False, paper_bgcolor="#0b0e14", plot_bgcolor="#0b0e14")
            st.plotly_chart(fig, use_container_width=True)
        
        # Notícias Reais
        st.subheader("📰 Radar de Notícias")
        try:
            n_res = requests.get(f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}').json()
            for art in n_res.get('articles', [])[:2]:
                st.info(f"**{art['source']['name']}**: {art['title']}")
        except: st.write("Serviço de notícias indisponível.")

    with col_r:
        d = next((item for item in st.session_state.top_10 if item.get("ticker") == t), {})
        st.markdown(f"""
        <div class="ai-card">
            <h3>🎯 Plano de Trade IA</h3>
            <p><b>Probabilidade:</b> {d.get('probabilidade', 'N/A')}%</p>
            <p><b>Ponto de Entrada:</b> ${d.get('entrada', 'N/A')}</p>
            <p><b>Estratégia:</b> {d.get('estrategia', 'N/A')}</p>
            <hr>
            <p><b>Análise Técnica:</b> {d.get('tecnico', 'N/A')}</p>
            <p><b>Análise Fundamentalista:</b> {d.get('fundamental', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            info = yf.Ticker(t).info
            st.metric("Alvo dos Bancos", f"${info.get('targetMeanPrice', 'N/A')}")
            st.metric("Upside Estimado", f"{round(((info.get('targetMeanPrice',1)/info.get('currentPrice',1))-1)*100,1)}%")
        except: pass
