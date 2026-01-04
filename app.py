import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import requests
from openai import OpenAI
import json
from finvizfinance.screener.overview import Overview

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner Global AI", page_icon="🎯", layout="wide")

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("❌ Configure as chaves OPENAI_API_KEY e NEWS_API_KEY nos Secrets do Streamlit.")
    st.stop()

# --- CSS DE ALTA VISIBILIDADE (Cores Neon e Texto Branco) ---
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
        background: #1e2130; padding: 25px; border-radius: 12px;
        border-left: 6px solid #00ffcc; color: white !important;
        line-height: 1.6; margin-bottom: 25px;
    }
    .ai-card h3, .ai-card b { color: #00ffcc !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE COLETA E SCANNER ---

def get_dynamic_market_universe():
    """Varre o mercado inteiro em busca de ações quentes (Volume + Strong Buy)"""
    try:
        framer = Overview()
        # Filtro: Volume acima de 1M e recomendação de analistas de bancos como Strong Buy
        filters_dict = {'Analyst Recom.': 'Strong Buy (1)', 'Current Volume': 'Over 1M'}
        framer.set_filter(filters_dict=filters_dict)
        df_market = framer.screener_view()
        return df_market['Ticker'].tolist()[:35] # Pega as 35 melhores para a IA refinar
    except:
        # Se o screener global falhar, usa as Big Techs como backup de segurança
        return ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR']

def fetch_clean_data(ticker, period="60d", interval="60m"):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def normalize_ai_response(resp):
    try:
        raw_list = resp.get('ranking', []) if isinstance(resp, dict) else []
        normalized = []
        for item in raw_list:
            clean_item = {k.lower(): v for k, v in item.items()}
            prob = clean_item.get('probabilidade', 0)
            if isinstance(prob, (float, int)) and prob <= 1.0:
                clean_item['probabilidade'] = int(prob * 100)
            normalized.append(clean_item)
        return normalized
    except: return []

# --- TELA HOME ---
if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🎯 IA Alpha Scanner: Mercado Global")
    st.subheader("Varrendo NYSE e NASDAQ em busca de Day Trades de alta probabilidade")

    if st.sidebar.button("🚀 ESCANEAR TODO O MERCADO"):
        with st.spinner('Escaneando milhares de ativos em busca de Volume e Recomendação de Bancos...'):
            dynamic_tickers = get_dynamic_market_universe()
            
            # Coleta dados técnicos das selecionadas
            batch = yf.download(dynamic_tickers, period="5d", interval="1h", group_by='ticker', progress=False)
            intelligence_list = []
            
            for t in dynamic_tickers:
                try:
                    d = batch[t].dropna()
                    if d.empty: continue
                    intelligence_list.append({
                        "ticker": t, "preco": round(d['Close'].iloc[-1], 2),
                        "rsi": round(ta.rsi(d['Close']).iloc[-1], 1),
                        "momentum": "ALTA" if d['Close'].iloc[-1] > d['Open'].iloc[-1] else "BAIXA"
                    })
                except: continue

            prompt = f"""
            Analise este universo de ações filtradas hoje: {intelligence_list}.
            Considere análise fundamentalista (upside), técnica (momentum) e notícias.
            Retorne um JSON com a chave 'ranking' contendo o TOP 10 para Day Trade (alvo 1%).
            Cada item deve ter: ticker, probabilidade(%), entrada, tecnico, fundamental, estrategia.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Você é um analista institucional."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            res_json = json.loads(response.choices[0].message.content)
            st.session_state.top_10 = normalize_ai_response(res_json)

    if 'top_10' in st.session_state:
        t10 = st.session_state.top_10
        cols = st.columns(min(3, len(t10)))
        for i in range(min(3, len(t10))):
            cols[i].metric(label=f"Ativo: {t10[i]['ticker']}", value=f"{t10[i]['probabilidade']}% Prob.")
        
        st.write("---")
        df_rank = pd.DataFrame(t10)
        st.subheader("📋 Ranking Dinâmico do Mercado")
        st.dataframe(df_rank, use_container_width=True)

        sel = st.selectbox("Selecione para abrir o terminal operacional:", [x['ticker'] for x in t10])
        if st.button("🔍 ABRIR DETALHES"):
            st.session_state.selected_ticker = sel
            st.session_state.page = 'details'
            st.rerun()

# --- TELA DETALHES ---
elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    tf = st.sidebar.selectbox("Tempo Gráfico", ["5m", "15m", "30m", "60m", "1d"], index=1)
    p_map = {"5m":"1d", "15m":"3d", "30m":"5d", "60m":"7d", "1d":"1y"}

    st.title(f"⚡ Terminal Operacional: {t}")
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        hist = fetch_clean_data(t, p_map[tf], tf)
        if hist is not None:
            hist['EMA9'] = ta.ema(hist['Close'], length=9)
            hist['EMA21'] = ta.ema(hist['Close'], length=21)
            bb = ta.bbands(hist['Close'], length=20)
            bbu = [c for c in bb.columns if c.startswith('BBU')][0]
            bbl = [c for c in bb.columns if c.startswith('BBL')][0]
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Candles",
                                        increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b'))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA9'], line=dict(color='yellow', width=1.5), name="EMA 9"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA21'], line=dict(color='cyan', width=1.5), name="EMA 21"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[bbu], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name="Banda Sup"))
            fig.add_trace(go.Scatter(x=hist.index, y=bb[bbl], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name="Banda Inf"))
            
            fig.update_layout(template="plotly_dark", height=550, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        
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
            <p><b>Probabilidade:</b> {d.get('probabilidade', 'N/A')}%</p>
            <p><b>Entrada:</b> ${d.get('entrada', 'N/A')}</p>
            <p><b>Estratégia:</b> {d.get('estrategia', 'N/A')}</p>
            <hr>
            <p><b>Técnico:</b> {d.get('tecnico', 'N/A')}</p>
            <p><b>Fundamental:</b> {d.get('fundamental', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            info = yf.Ticker(t).info
            st.metric("Alvo dos Bancos", f"${info.get('targetMeanPrice', 'N/A')}")
        except: pass
