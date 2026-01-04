import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import openai
import json
import requests
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="Alpha Scanner v9 - High Precision", page_icon="💎", layout="wide")

try:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
except Exception as e:
    st.error("❌ ERRO DE CONFIGURAÇÃO: Vá em Settings > Secrets e insira sua OPENAI_API_KEY.")
    st.stop()

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #00ffcc; border-radius: 12px; }
    .report-card { background: #1e2130; padding: 20px; border-radius: 15px; border-left: 8px solid #00ffcc; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- ENGINE DE CÁLCULO TÉCNICO ---

def get_market_intelligence():
    """Coleta e processa indicadores técnicos para 20 ativos líderes"""
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'AVGO', 'SMCI', 'PLTR', 'SPY', 'QQQ', 'IWM']
    
    try:
        data = yf.download(tickers, period="1mo", interval="1h", group_by='ticker', progress=False)
        processed_data = []
        
        for t in tickers:
            df = data[t].dropna()
            if df.empty: continue
            
            # Cálculo de Indicadores para enviar à IA
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['EMA9'] = ta.ema(df['Close'], length=9)
            df['EMA21'] = ta.ema(df['Close'], length=21)
            atr = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
            
            stock = yf.Ticker(t)
            info = stock.info
            
            processed_data.append({
                "ticker": t,
                "preco_atual": round(df['Close'].iloc[-1], 2),
                "rsi": round(df['RSI'].iloc[-1], 2),
                "tendencia_ema": "ALTA" if df['EMA9'].iloc[-1] > df['EMA21'].iloc[-1] else "BAIXA",
                "volatilidade_atr": round(atr, 2),
                "target_bancos": info.get('targetMeanPrice', 0),
                "consenso_bancos": info.get('recommendationKey', 'N/A'),
                "volume_avg": info.get('averageVolume', 0)
            })
        return processed_data
    except Exception as e:
        st.error(f"Erro na coleta: {e}")
        return []

def brain_ai_analysis(market_data):
    """O Prompt Perfeito: Age como um Comitê de Investimento"""
    
    prompt = f"""
    VOCÊ É UM SISTEMA DE INTELIGÊNCIA QUANTITATIVA DE UM HEDGE FUND.
    DADOS DE MERCADO ATUAIS: {market_data}
    
    SUA TAREFA:
    1. Analise a convergência entre:
       - Análise Técnica (RSI ideal entre 45-65 para momentum, tendência de médias).
       - Análise Fundamentalista (Upside em relação ao preço alvo dos bancos).
       - Liquidez (Volume médio para garantir saída no Day Trade).
    2. Identifique as 10 melhores oportunidades para buscar 1% de lucro hoje.
    3. Para cada ativo, defina um índice de probabilidade de 0 a 100%.

    RETORNE RIGOROSAMENTE UM JSON:
    {{
      "data_analise": "{pd.Timestamp.now()}",
      "ranking": [
        {{
          "ticker": "TICKER",
          "probabilidade": 95,
          "setup_tecnico": "Explicação técnica ultra-detalhada",
          "setup_fundamental": "Visão dos bancos e alvo",
          "estrategia_daytrade": "Preço de entrada, stop e alvo de 1%",
          "score_volatilidade": "Alto/Médio/Baixo"
        }}
      ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Modelo de maior precisão disponível
            messages=[
                {"role": "system", "content": "Você é um terminal financeiro de alta precisão que só emite relatórios em JSON estruturado."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

# --- INTERFACE ---

if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("💎 Alpha Scanner v9: Consenso Institucional")
    st.write("Escaner de Alta Precisão: Análise Técnica Multi-Timeframe + Bancos + IA GPT-4o")

    if st.sidebar.button("🚀 EXECUTAR ANÁLISE DE ALTA PRECISÃO"):
        with st.status("🧠 IA e Algoritmos Analisando Mercado...", expanded=True) as status:
            st.write("1. Calculando indicadores técnicos (RSI, EMA, ATR)...")
            intel_data = get_market_intelligence()
            
            st.write("2. Consultando consenso de analistas de Wall Street...")
            st.write("3. Gerando Veredito com GPT-4o (Hedge Fund Mode)...")
            
            final_report = brain_ai_analysis(intel_data)
            
            if "ranking" in final_report:
                st.session_state.top_10 = final_report["ranking"]
                status.update(label="Análise Concluída!", state="complete")
            else:
                st.error(f"Erro na IA: {final_report.get('error')}")

    if 'top_10' in st.session_state:
        st.write("---")
        # Visualização Top 3
        t10 = st.session_state.top_10
        c1, c2, c3 = st.columns(3)
        for i, col in enumerate([c1, c2, c3]):
            col.metric(t10[i]['ticker'], f"Probabilidade", f"{t10[i]['probabilidade']}%")

        st.subheader("📋 Ranking Estruturado pela IA")
        df_rank = pd.DataFrame(t10)
        st.dataframe(df_rank[['ticker', 'probabilidade', 'score_volatilidade', 'setup_tecnico']], use_container_width=True)

        selected = st.selectbox("Selecione o ativo para o Relatório de Operação:", df_rank['ticker'])
        if st.button("🔍 ABRIR TERMINAL"):
            st.session_state.selected_stock = selected
            st.session_state.page = 'details'
            st.rerun()

elif st.session_state.page == 'details':
    t = st.session_state.selected_stock
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    # Busca detalhes da IA
    details = next((item for item in st.session_state.top_10 if item["ticker"] == t), {})
    
    st.title(f"⚡ Operação Day Trade: {t}")
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        hist = yf.download(t, period="5d", interval="15m", progress=False)
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                                            increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b')])
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Notícias (NewsAPI)
        st.subheader("📰 Notícias e Sentimento")
        try:
            res = requests.get(f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}').json()
            for art in res.get('articles', [])[:3]:
                st.info(f"**{art['source']['name']}**: {art['title']}")
        except: st.write("Radar de notícias offline.")

    with col_r:
        st.markdown(f"""
        <div class="report-card">
            <h3>🎯 Plano de Trade IA</h3>
            <p><b>Probabilidade:</b> {details.get('probabilidade')}%</p>
            <p><b>Estratégia:</b> {details.get('estrategia_daytrade')}</p>
            <hr>
            <p><b>Análise Técnica:</b> {details.get('setup_tecnico')}</p>
            <p><b>Análise Fundamentalista:</b> {details.get('setup_fundamental')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Dados em tempo real
        si = yf.Ticker(t).info
        st.metric("Preço Alvo Médio (Bancos)", f"${si.get('targetMeanPrice', 'N/A')}")

