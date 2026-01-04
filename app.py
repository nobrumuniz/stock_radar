import streamlit as st
import yfinance as yf
import pandas as pd
import openai
import json
import requests
import plotly.graph_objects as go

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Alpha Scanner AI v8", page_icon="🧪", layout="wide")

# Inicialização Robusta da OpenAI
try:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")
except Exception as e:
    st.error(f"❌ Erro Crítico de Configuração: {e}")
    st.stop()

# --- CSS DE ALTA VISIBILIDADE ---
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #00ffcc; border-radius: 10px; }
    [data-testid="stMetricLabel"] p { color: #00ffcc !important; font-weight: bold; }
    .debug-box { padding: 10px; background-color: #262730; border-radius: 5px; font-family: monospace; font-size: 12px; color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE COLETA (DEBUGADAS) ---

@st.cache_data(ttl=600)
def get_market_snapshot():
    """Coleta dados fundamentais e técnicos reais para enviar à IA"""
    # Foco em ações de alta volatilidade e recomendação de bancos (S&P 500 tech)
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR', 'AMD', 'AVGO', 'SMCI', 'PLTR', 'BABA', 'JPM']
    
    try:
        # Download em lote (muito mais rápido)
        data = yf.download(tickers, period="5d", interval="1h", group_by='ticker', progress=False)
        
        snapshot = []
        for t in tickers:
            df = data[t].dropna()
            if df.empty: continue
            
            # Pegando recomendações de bancos (pode ser lento, então pegamos apenas das principais)
            stock = yf.Ticker(t)
            try:
                target = stock.info.get('targetMeanPrice', df['Close'].iloc[-1] * 1.1)
                recom = stock.info.get('recommendationKey', 'N/A')
            except:
                target, recom = 0, 'N/A'

            snapshot.append({
                "ticker": t,
                "price": round(df['Close'].iloc[-1], 2),
                "volatilidade_5d": f"{round(df['Close'].pct_change().std() * 100, 2)}%",
                "target_bancos": target,
                "recom_bancos": recom,
                "volume_24h": int(df['Volume'].iloc[-1])
            })
        return snapshot
    except Exception as e:
        st.error(f"Erro no Yahoo Finance: {e}")
        return []

def ask_ai_expert(data_snapshot):
    """Envia o snapshot para a IA com Fallback de Modelos"""
    if not data_snapshot:
        return {"error": "Nenhum dado de mercado disponível para análise."}

    prompt = f"""
    Aja como um Analista de Hedge Fund. Analise estes dados reais do mercado: {data_snapshot}.
    Selecione as 10 melhores para DAY TRADE hoje (foco em alvos de 1% de ganho rápido).
    
    Retorne APENAS um JSON no formato exato:
    {{
      "ranking": [
        {{
          "ticker": "NOME",
          "probabilidade": 95,
          "entrada": 150.00,
          "motivo_tecnico": "Explicação curta",
          "motivo_fundament": "Explicação curta",
          "upside": "1.2%"
        }}
      ]
    }}
    """
    
    # Lista de modelos para tentar (do melhor para o mais acessível)
    models = ["gpt-4o", "gpt-4-turbo-preview", "gpt-4o-mini"]
    
    last_error = ""
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "Você é um terminal financeiro JSON."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=30
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            last_error = str(e)
            continue # Tenta o próximo modelo
            
    return {"error": f"Falha em todos os modelos de IA. Último erro: {last_error}"}

# --- INTERFACE ---

if 'page' not in st.session_state: st.session_state.page = 'home'

if st.session_state.page == 'home':
    st.title("🧪 Alpha Scanner v8 (Debug Mode)")
    st.subheader("Análise Multi-Modelos: Bancos + Gráfico + IA")

    with st.sidebar:
        if st.button("🚀 EXECUTAR SCANNER IA"):
            st.session_state.running = True
        if st.button("🧹 LIMPAR CACHE"):
            st.cache_data.clear()
            st.rerun()

    if st.session_state.get('running'):
        with st.status("🔍 Processando Dados...", expanded=True) as status:
            st.write("1. Coletando dados fundamentais e técnicos...")
            market_data = get_market_snapshot()
            
            if not market_data:
                st.error("Falha ao coletar dados do Yahoo Finance. O serviço pode estar fora do ar.")
            else:
                st.write(f"2. Analisando {len(market_data)} ativos com GPT-4o...")
                ai_res = ask_ai_expert(market_data)
                
                if "ranking" in ai_res:
                    st.session_state.top_10 = ai_res["ranking"]
                    status.update(label="Análise Concluída com Sucesso!", state="complete")
                else:
                    st.markdown(f'<div class="debug-box">ERRO DA IA: {ai_res.get("error")}</div>', unsafe_allow_html=True)

    if 'top_10' in st.session_state:
        st.write("---")
        t10 = st.session_state.top_10
        cols = st.columns(min(3, len(t10)))
        
        for i in range(min(3, len(t10))):
            cols[i].metric(t10[i]['ticker'], f"${t10[i]['entrada']}", f"{t10[i]['probabilidade']}% Prob.")

        st.subheader("📋 Ranking Detalhado")
        df = pd.DataFrame(t10)
        st.dataframe(df[['ticker', 'probabilidade', 'upside', 'motivo_tecnico', 'motivo_fundament']], use_container_width=True)

        selected = st.selectbox("Selecione para abrir o terminal:", df['ticker'])
        if st.button("🔍 ABRIR TERMINAL DE TRADE"):
            st.session_state.selected_ticker = selected
            st.session_state.page = 'details'
            st.rerun()

elif st.session_state.page == 'details':
    t = st.session_state.selected_ticker
    st.button("⬅️ VOLTAR", on_click=lambda: setattr(st.session_state, 'page', 'home'))
    
    # Recupera info do JSON
    info_ia = next((item for item in st.session_state.top_10 if item["ticker"] == t), {})

    st.title(f"⚡ Terminal: {t}")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        hist = yf.download(t, period="2d", interval="15m", progress=False)
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                        increasing_line_color='#00ffcc', decreasing_line_color='#ff4b4b')])
        fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Notícias
        st.subheader("📰 Notícias")
        if NEWS_API_KEY:
            try:
                n_url = f'https://newsapi.org/v2/everything?q={t}&language=en&apiKey={NEWS_API_KEY}'
                arts = requests.get(n_url).json().get('articles', [])[:3]
                for a in arts:
                    st.write(f"**{a['source']['name']}**: {a['title']}")
            except: st.write("Erro nas notícias.")

    with c2:
        st.success(f"**Probabilidade IA:** {info_ia.get('probabilidade')}%")
        st.info(f"**Técnico:** {info_ia.get('motivo_tecnico')}")
        st.warning(f"**Fundamental:** {info_ia.get('motivo_fundament')}")
        st.metric("Upside Esperado", info_ia.get('upside'))
