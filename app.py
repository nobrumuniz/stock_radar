import streamlit as st
import yfinance as yf
import pandas as pd
import openai
import json
import requests
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha IA Scanner v7", page_icon="🧠", layout="wide")

# Inicialização OpenAI
try:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except:
    st.error("⚠️ Erro: Configure as chaves nos Secrets do Streamlit.")
    st.stop()

# --- CSS DE ALTA PERFORMANCE ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: white; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #00ffcc; border-radius: 10px; }
    [data-testid="stMetricLabel"] { color: #00ffcc !important; font-weight: bold !important; }
    .stTable { background-color: #161b22; }
    .status-box { padding: 20px; border-radius: 10px; border: 1px solid #4facfe; background-color: #1e2130; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---

@st.cache_data(ttl=3600)
def get_raw_market_data():
    """Coleta dados brutos das 30 ações mais líquidas/importantes para a IA filtrar"""
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'AVGO', 'SMCI', 'TSM', 'PLTR', 'BABA', 'UBER', 'JPM', 'GS']
    data = yf.download(tickers, period="5d", interval="1h", group_by='ticker', progress=False)
    
    summary = []
    for t in tickers:
        try:
            df = data[t].dropna()
            price = df['Close'].iloc[-1]
            change = ((price / df['Close'].iloc[0]) - 1) * 100
            # Adicionando volume e volatilidade para a IA
            vol = df['Volume'].iloc[-1]
            summary.append({"ticker": t, "price": round(price,2), "5d_change": round(change,2), "volume": int(vol)})
        except: continue
    return summary

def ask_ai_to_rank(market_summary):
    """O CÉREBRO: Envia dados para o GPT-4 e recebe o Ranking em JSON"""
    prompt = f"""
    Aja como um Quant Trader de um Hedge Fund. Analise estes dados brutos de mercado: {market_summary}.
    Seu objetivo é encontrar as 10 melhores oportunidades de DAY TRADE para hoje (Alvo 1% de ganho).
    Considere: Momentum, Volume e Consenso de mercado.
    
    RETORNE RIGOROSAMENTE APENAS UM JSON (sem texto antes ou depois) no formato:
    {{
      "ranking": [
        {{
          "ticker": "TSLA",
          "probabilidade": 92,
          "entrada": 245.50,
          "motivo_tecnico": "Rompimento de canal de 15min com volume",
          "motivo_fundament": "Upgrade do Goldman Sachs esta manhã",
          "upside_estimado": "1.5%"
        }}
      ]
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "system", "content": "Você é um analista financeiro que só responde em JSON."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

# --- INTERFACE ---

if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🧠 Alpha Scanner AI v7: Inteligência Pura")
    
    with st.sidebar:
        st.header("Comandos")
        run_scan = st.button("🚀 EXECUTAR ANÁLISE IA")
        st.caption("Tempo estimado: 15-30 segundos")

    if run_scan:
        with st.status("🧠 IA Processando Mercado...", expanded=True) as status:
            st.write("1. Coletando dados das 30 ações mais voláteis...")
            raw_data = get_raw_market_data()
            
            st.write("2. Enviando para o GPT-4 Analista (Hedge Fund Mode)...")
            ai_response = ask_ai_to_rank(raw_data)
            
            if "ranking" in ai_response:
                st.session_state.top_10 = ai_response["ranking"]
                status.update(label="Análise Concluída!", state="complete")
            else:
                st.error("Erro na resposta da IA")

    if 'top_10' in st.session_state:
        # Cards de Destaque (Seguro contra IndexError)
        st.write("### 🔥 Top Oportunidades Selecionadas pela IA")
        num_items = len(st.session_state.top_10)
        cols = st.columns(min(3, num_items))
        
        for i in range(min(3, num_items)):
            item = st.session_state.top_10[i]
            cols[i].metric(item['ticker'], f"${item['entrada']}", f"{item['probabilidade']}% Prob.")

        st.write("---")
        
        # Tabela Detalhada
        df_display = pd.DataFrame(st.session_state.top_10)
        st.subheader("📋 Ranking Estruturado (JSON Parsed)")
        st.dataframe(df_display[['ticker', 'probabilidade', 'upside_estimado', 'motivo_tecnico', 'motivo_fundament']], use_container_width=True)

        selected = st.selectbox("Selecione para ver Gráfico e Notícias:", df_display['ticker'])
        if st.button("🔍 VER PAINEL DE OPERAÇÃO"):
            st.session_state.selected_ticker = selected
            st.session_state.page = 'details'
            st.rerun()

elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    # Encontrar dados da IA para este ticker
    stock_detail = next((item for item in st.session_state.top_10 if item["ticker"] == t), None)
    
    st.title(f"⚡ Terminal de Trade: {t}")
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        # Gráfico Day Trade
        hist = yf.download(t, period="3d", interval="15m", progress=False)
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                                            increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b')])
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Radar de Notícias
        st.subheader("📰 Radar de Notícias em Tempo Real")
        url = f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}'
        news = requests.get(url).json().get('articles', [])[:3]
        for n in news:
            st.markdown(f"""<div style='background:#161b22; padding:10px; border-radius:5px; margin-bottom:5px; border-left:4px solid #00ffcc;'>
                <b>{n['source']['name']}</b>: {n['title']}</div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown(f"""
        <div class='status-box'>
            <h2 style='color:#00ffcc;'>Veredito da IA</h2>
            <p><b>Probabilidade:</b> {stock_detail['probabilidade']}%</p>
            <p><b>Entrada Sugerida:</b> ${stock_detail['entrada']}</p>
            <hr>
            <p><b>Técnico:</b> {stock_detail['motivo_tecnico']}</p>
            <p><b>Fundamental:</b> {stock_detail['motivo_fundament']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Botão de Refresh
        if st.button("🔄 RE-ANALISAR ESTE ATIVO"):
            st.rerun()
