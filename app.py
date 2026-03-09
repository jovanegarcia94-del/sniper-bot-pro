import streamlit as st
import pandas as pd
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(page_title="Robô Trader Pro", layout="wide")

# ---------------- ESTADOS ----------------
if 'rodando' not in st.session_state:
    st.session_state.rodando = False
if 'lucro_sessao' not in st.session_state:
    st.session_state.lucro_sessao = 0.0
if 'historico' not in st.session_state:
    st.session_state.historico = []
if 'estrategia_usuario' not in st.session_state:
    st.session_state.estrategia_usuario = "MHI"
if 'conectado' not in st.session_state:
    st.session_state.conectado = False
if 'api' not in st.session_state:
    st.session_state.api = None

# ---------------- FUNÇÃO DE ANÁLISE ----------------
def analisar_entrada(api, ativo, estrategia):
    timeframe = 300 if estrategia == 'MHI M5' else 60
    qnt_velas = 4 if estrategia == 'Torres Gêmeas' else 3
    velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
    cores = []
    for v in velas:
        if v['open'] < v['close']:
            cores.append("Verde")
        elif v['open'] > v['close']:
            cores.append("Vermelha")
        else:
            cores.append("Doji")
    direcao = None
    if estrategia in ['MHI','MHI M5']:
        if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores:
            direcao = "put"
        if cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
            direcao = "call"
    elif estrategia == 'Torres Gêmeas':
        if cores[0] == 'Verde':
            direcao = "call"
        if cores[0] == 'Vermelha':
            direcao = "put"
    return direcao

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("Conexão")
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
    
    email = st.text_input("Email", value="")
    senha = st.text_input("Senha", type="password", value="")

    if st.button("Conectar IQ Option"):
        if email and senha:
            api = IQ_Option(email, senha)
            check,_ = api.connect()
            if check:
                api.change_balance(conta_tipo)
                st.session_state.api = api
                st.session_state.conectado = True
                st.success(f"Conectado na conta {conta_tipo}")
            else:
                st.error("Falha ao conectar. Verifique email/senha")
        else:
            st.warning("Informe email e senha")

    if st.session_state.conectado and st.session_state.api:
        st.success("✅ Conectado")
        if st.button("Parar Bot"):
            st.session_state.rodando = False

# ---------------- ABAS ----------------
aba1, aba2, aba3 = st.tabs(["Controle","Configurações","Histórico"])

# ---------------- CONTROLE ----------------
with aba1:
    if not st.session_state.rodando:
        if st.button("▶ Iniciar Robô"):
            st.session_state.rodando = True
    else:
        if st.button("⛔ Parar Robô"):
            st.session_state.rodando = False

# ---------------- CONFIGURAÇÕES ----------------
with aba2:
    st.subheader("Parâmetros do Bot")
    st.session_state.estrategia_usuario = st.selectbox(
        "Estratégia",
        ["MHI","MHI M5","Torres Gêmeas"]
    )

    valor_entrada = st.number_input("Valor Entrada", value=2.5)
    stop_win = st.number_input("Stop Win", value=4.0)
    stop_loss = st.number_input("Stop Loss", value=3.0)
    tipo = st.selectbox("Tipo Operação", ["digital","binaria"])
    usar_mg = st.checkbox("Usar Martingale")
    niveis_mg = st.number_input("Níveis Martingale", value=1)
    fator_mg = st.number_input("Fator Martingale", value=2.0)
    usar_soros = st.checkbox("Usar Soros")
    niveis_soros = st.number_input("Níveis Soros", value=2)

# ---------------- HISTÓRICO ----------------
with aba3:
    if len(st.session_state.historico) > 0:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df,use_container_width=True)
    else:
        st.info("Nenhum trade executado ainda")

# ---------------- DASHBOARD ----------------
col1, col2, col3, col4 = st.columns(4)
saldo = 0
moeda = ""
if st.session_state.api:
    try:
        saldo = st.session_state.api.get_balance()
        moeda = st.session_state.api.get_currency()
    except:
        saldo = 0
simbolo = "$" if moeda == "USD" else "R$"

with col1:
    st.metric("Saldo Conta", f"{simbolo} {round(saldo,2)}")
with col2:
    st.metric("Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
with col3:
    status = "🟢 Rodando" if st.session_state.rodando else "🔴 Parado"
    st.metric("Status", status)
with col4:
    st.metric("Trades", len(st.session_state.historico))

# ---------------- LOOP BOT POR CICLO ----------------
if st.session_state.api and st.session_state.rodando:
    try:
        lista, linha_idx = catag(
            st.session_state.api,
            niveis_mg=niveis_mg,
            usar_mg=usar_mg
        )
        if len(lista) == 0:
            st.warning("Nenhum ativo disponível")
        else:
            melhor = lista[0]
            ativo = melhor[1]
            estrategia = st.session_state.estrategia_usuario
            st.write("Ativo:", ativo)
            st.write("Estratégia:", estrategia)

            direcao = analisar_entrada(st.session_state.api, ativo, estrategia)
            if direcao:
                st.success(f"Operando {direcao}")
                if tipo == "digital":
                    check, id = st.session_state.api.buy_digital_spot_v2(
                        ativo, valor_entrada, direcao, 1
                    )
                else:
                    check, id = st.session_state.api.buy(
                        valor_entrada, ativo, direcao, 1
                    )
                if check:
                    while True:
                        time.sleep(1)
                        if tipo == "digital":
                            status, resultado = st.session_state.api.check_win_digital_v2(id)
                        else:
                            status, resultado = st.session_state.api.check_win_v4(id)
                        if status:
                            st.session_state.lucro_sessao += resultado
                            st.session_state.historico.append({
                                "ativo": ativo,
                                "direcao": direcao,
                                "resultado": resultado,
                                "hora": datetime.now().strftime("%H:%M:%S")
                            })
                            break
            else:
                st.warning("Sem sinal")

            if st.session_state.lucro_sessao >= stop_win or st.session_state.lucro_sessao <= -stop_loss:
                st.error("Stop atingido")
                st.session_state.rodando = False
    except Exception as e:
        st.error(f"Erro no ciclo: {e}")
