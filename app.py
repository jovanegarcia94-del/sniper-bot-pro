import streamlit as st
import pandas as pd
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(
    page_title="Robô Trader Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- ESTADOS ----------------
if 'rodando' not in st.session_state: st.session_state.rodando = False
if 'lucro_sessao' not in st.session_state: st.session_state.lucro_sessao = 0.0
if 'historico' not in st.session_state: st.session_state.historico = []
if 'estrategia_usuario' not in st.session_state: st.session_state.estrategia_usuario = "MHI"
if 'conectado' not in st.session_state: st.session_state.conectado = False
if 'api' not in st.session_state: st.session_state.api = None

# ---------------- FUNÇÃO DE ANÁLISE ----------------
def analisar_entrada(api, ativo, estrategia):
    try:
        timeframe = 300 if estrategia == 'MHI M5' else 60
        qnt_velas = 4 if estrategia == 'Torres Gêmeas' else 3
        velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
        cores = []
        for v in velas:
            if v['open'] < v['close']: cores.append("Verde")
            elif v['open'] > v['close']: cores.append("Vermelha")
            else: cores.append("Doji")
        direcao = None
        if estrategia in ['MHI','MHI M5']:
            if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores: direcao = "put"
            if cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores: direcao = "call"
        elif estrategia == 'Torres Gêmeas':
            if cores[0] == 'Verde': direcao = "call"
            if cores[0] == 'Vermelha': direcao = "put"
        return direcao
    except:
        return None

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🤖 Robô Trader Pro")
    st.markdown("---")
    st.header("🔑 Conexão IQ Option")
    
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")
    
    if st.button("🔌 Conectar"):
        if email and senha:
            try:
                api = IQ_Option(email, senha)
                check, _ = api.connect()
                if check:
                    api.change_balance(conta_tipo)
                    st.session_state.api = api
                    st.session_state.conectado = True
                    st.toast(f"Conectado na conta {conta_tipo} ✅")
                else:
                    st.error("Falha ao conectar. Verifique email/senha")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
        else:
            st.warning("Informe email e senha")

    if st.session_state.conectado and st.session_state.api:
        st.success("✅ Online")
        st.markdown("---")
        if st.button("🛑 Parar Bot"):
            st.session_state.rodando = False

# ---------------- DASHBOARD SUPERIOR ----------------
col1, col2, col3, col4 = st.columns(4)
saldo = 0
moeda = ""
if st.session_state.api and st.session_state.conectado:
    try:
        saldo = st.session_state.api.get_balance()
        moeda = st.session_state.api.get_currency()
    except: saldo = 0
simbolo = "$" if moeda=="USD" else "R$"

col1.metric("💰 Saldo Conta", f"{simbolo} {round(saldo,2)}")
col2.metric("💵 Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
status = "🟢 Rodando" if st.session_state.rodando else "🔴 Parado"
col3.metric("⚙️ Status do Robô", status)
col4.metric("📊 Total de Trades", len(st.session_state.historico))

st.markdown("---")

# ---------------- ABAS ----------------
aba1, aba2, aba3 = st.tabs(["🎮 Controle", "⚙️ Configurações", "📜 Histórico"])

# ---------------- CONTROLE ----------------
with aba1:
    st.subheader("Gerenciamento do Robô")
    if not st.session_state.rodando:
        if st.button("▶ Iniciar Robô"):
            if st.session_state.conectado:
                st.session_state.rodando = True
                st.rerun()
            else:
                st.error("Conecte-se à IQ Option primeiro!")
    else:
        if st.button("⛔ Parar Robô"):
            st.session_state.rodando = False
            st.rerun()

# ---------------- CONFIGURAÇÕES ----------------
with aba2:
    st.subheader("Parâmetros de Operação")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.estrategia_usuario = st.selectbox("Estratégia", ["MHI","MHI M5","Torres Gêmeas"])
        tipo = st.selectbox("Tipo Operação", ["digital","binaria"])
        valor_entrada = st.number_input("Valor Entrada", value=2.5)
    with col2:
        stop_win = st.number_input("Stop Win", value=4.0)
        stop_loss = st.number_input("Stop Loss", value=3.0)
    with col3:
        usar_mg = st.checkbox("Usar Martingale")
        niveis_mg = st.number_input("Níveis Martingale", value=1, min_value=1) if usar_mg else 1
        fator_mg = st.number_input("Fator Martingale", value=2.0, step=0.1) if usar_mg else 2.0
        usar_soros = st.checkbox("Usar Soros")
        niveis_soros = st.number_input("Níveis Soros", value=2, min_value=1) if usar_soros else 2

# ---------------- HISTÓRICO ----------------
with aba3:
    if st.session_state.historico:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    else:
        st.info("Nenhum trade nesta sessão")

# ---------------- MOTOR DO BOT ----------------
log_container = st.empty()

if st.session_state.rodando and st.session_state.conectado:
    with log_container.container():
        try:
            lista, _ = catag(
                st.session_state.api,
                niveis_mg=niveis_mg,
                usar_mg=usar_mg
            )
            if not lista:
                st.warning("Nenhum ativo disponível")
            else:
                melhor = lista[0]
                ativo = melhor[1]
                estrategia = st.session_state.estrategia_usuario
                direcao = analisar_entrada(st.session_state.api, ativo, estrategia)

                if direcao:
                    st.success(f"Sinal Encontrado: {ativo} | {direcao.upper()}")
                    if tipo=="digital":
                        check, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_entrada, direcao, 1)
                    else:
                        check, id = st.session_state.api.buy(valor_entrada, ativo, direcao, 1)

                    if check:
                        valor_atual = valor_entrada
                        mg_atual = 0

                        while True:
                            time.sleep(1)
                            if tipo=="digital":
                                status_op, resultado = st.session_state.api.check_win_digital_v2(id)
                            else:
                                status_op, resultado = st.session_state.api.check_win_v4(id)
                            if status_op:
                                st.session_state.lucro_sessao += resultado
                                st.session_state.historico.append({
                                    "ativo": ativo,
                                    "direcao": direcao,
                                    "resultado": round(resultado,2),
                                    "hora": datetime.now().strftime("%H:%M:%S")
                                })

                                # Martingale imediato
                                if resultado<0 and usar_mg and mg_atual<niveis_mg:
                                    mg_atual += 1
                                    valor_atual *= fator_mg
                                    st.toast(f"LOSS! Executando MG {mg_atual} com {valor_atual}", icon="⚡")
                                    if tipo=="digital":
                                        check, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_atual, direcao, 1)
                                    else:
                                        check, id = st.session_state.api.buy(valor_atual, ativo, direcao, 1)
                                    continue
                                break

            # Stop win / stop loss
            if st.session_state.lucro_sessao >= stop_win:
                st.success("🎉 STOP WIN atingido!")
                st.session_state.rodando = False
            elif st.session_state.lucro_sessao <= -stop_loss:
                st.error("⚠️ STOP LOSS atingido!")
                st.session_state.rodando = False

        except Exception as e:
            st.error(f"Erro no ciclo: {e}")

    if st.session_state.rodando:
        time.sleep(3)
        st.rerun()
