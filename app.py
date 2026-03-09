import streamlit as st
import pandas as pd
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime
import gc  # Para limpeza de memória

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(page_title="Robô Trader Pro", layout="wide")
st.title("📈 Robô Trader Pro")
st.markdown("---")

# ---------------- ESTADOS ----------------
if 'rodando' not in st.session_state:
    st.session_state.rodando = False
if 'lucro_sessao' not in st.session_state:
    st.session_state.lucro_sessao = 0.0
if 'historico' not in st.session_state:
    st.session_state.historico = []

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

# ---------------- DASHBOARD SUPERIOR ----------------
col1, col2, col3, col4 = st.columns(4)
saldo, moeda = 0, ""
if 'api' in st.session_state and st.session_state.api:
    try:
        saldo = st.session_state.api.get_balance()
        moeda = st.session_state.api.get_currency()
    except:
        saldo = 0
simbolo = "$" if moeda == "USD" else "R$"

with col1: st.metric("Saldo Conta", f"{simbolo} {round(saldo,2)}")
with col2: st.metric("Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
with col3: st.metric("Status do Bot", "🟢 Rodando" if st.session_state.rodando else "🔴 Parado")
with col4: st.metric("Total de Trades", len(st.session_state.historico))
st.markdown("---")

# ---------------- SIDEBAR: LOGIN SEGURO ----------------
with st.sidebar:
    st.header("Conexão IQ Option")
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])

    # Sempre solicita novas credenciais
    email = st.text_input("Email", key="email_input")
    senha = st.text_input("Senha", type="password", key="senha_input")

    if st.button("Conectar IQ Option", use_container_width=True):
        if email and senha:
            # Destrói sessão antiga, se existir
            if 'api' in st.session_state:
                try:
                    st.session_state.api.close()  # Tenta fechar sessão antiga
                except: pass
                del st.session_state['api']
                gc.collect()  # Limpeza de memória

            # Cria nova conexão
            api = IQ_Option(email, senha)
            check, _ = api.connect()
            if check:
                api.change_balance(conta_tipo)
                st.session_state.api = api
                st.success(f"Conectado na conta {conta_tipo}")
                st.rerun()
            else:
                st.error("Falha na conexão. Verifique suas credenciais.")
        else:
            st.warning("Informe email e senha")

    # Botão de desconexão
    if 'api' in st.session_state and st.session_state.api:
        if st.button("Desconectar", use_container_width=True):
            try:
                st.session_state.api.close()
            except: pass
            del st.session_state['api']
            st.session_state.rodando = False
            st.success("Desconectado com sucesso")
            st.rerun()

# ---------------- ABAS PRINCIPAIS ----------------
aba1, aba2, aba3 = st.tabs(["🎮 Controle", "⚙️ Configurações", "📊 Histórico"])

# ---------------- CONFIGURAÇÕES ----------------
with aba2:
    st.subheader("Parâmetros do Robô")
    col1_cfg, col2_cfg, col3_cfg = st.columns(3)
    with col1_cfg:
        st.selectbox("Estratégia", ["MHI", "MHI M5", "Torres Gêmeas"], key="estrategia_usuario")
        st.selectbox("Tipo de Operação", ["digital", "binaria"], key="tipo")
        st.number_input("Valor de Entrada", value=2.5, step=0.5, key="valor_entrada")
    with col2_cfg:
        st.number_input("Stop Win", value=4.0, step=1.0, key="stop_win")
        st.number_input("Stop Loss", value=3.0, step=1.0, key="stop_loss")
    with col3_cfg:
        st.checkbox("Usar Martingale", key="usar_mg")
        st.number_input("Níveis Martingale", value=1, min_value=1, key="niveis_mg")
        st.number_input("Fator Martingale", value=2.0, step=0.1, key="fator_mg")
        st.checkbox("Usar Soros", key="usar_soros")
        st.number_input("Níveis Soros", value=2, min_value=1, key="niveis_soros")

# ---------------- CONTROLE ----------------
with aba1:
    st.subheader("Painel de Controle")
    if not st.session_state.rodando:
        if st.button("▶ INICIAR ROBÔ", use_container_width=True):
            if 'api' in st.session_state and st.session_state.api:
                st.session_state.rodando = True
                st.rerun()
            else:
                st.warning("Conecte-se à IQ Option primeiro!")
    else:
        if st.button("⛔ PARAR ROBÔ", use_container_width=True):
            st.session_state.rodando = False
            st.rerun()

# ---------------- HISTÓRICO ----------------
with aba3:
    if len(st.session_state.historico) > 0:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum trade executado ainda nesta sessão.")

# ---------------- LOOP DO BOT COM MARTINGALE ----------------
if 'api' in st.session_state and st.session_state.rodando:
    st.markdown("---")
    st.subheader("🔄 Executando ciclo de operação...")

    # Parâmetros
    api = st.session_state.api
    estrategia = st.session_state.estrategia_usuario
    tipo = st.session_state.tipo
    valor_entrada = st.session_state.valor_entrada
    stop_win = st.session_state.stop_win
    stop_loss = st.session_state.stop_loss
    usar_mg = st.session_state.usar_mg
    niveis_mg = st.session_state.niveis_mg
    fator_mg = st.session_state.fator_mg

    # Catalogação
    lista, _ = catag(api, niveis_mg=niveis_mg, usar_mg=usar_mg)
    if lista:
        melhor = lista[0]
        ativo = melhor[1]

        st.info(f"Ativo Analisado: {ativo}")
        st.info(f"Estratégia: {estrategia}")

        direcao = analisar_entrada(api, ativo, estrategia)
        if direcao:
            st.success(f"Sinal encontrado: {direcao.upper()} em {ativo}")
            gale_atual = 0
            max_gale = niveis_mg if usar_mg else 0
            while gale_atual <= max_gale:
                valor_operacao = valor_entrada * (fator_mg ** gale_atual)
                lucro_trade = 0
                # Abrir operação
                if tipo == "digital":
                    check, id_op = api.buy_digital_spot_v2(ativo, valor_operacao, direcao, 1)
                else:
                    check, id_op = api.buy(valor_operacao, ativo, direcao, 1)
                if check:
                    with st.spinner(f"Aguardando resultado (Gale {gale_atual})..."):
                        while True:
                            time.sleep(1)
                            if tipo == "digital":
                                status, resultado = api.check_win_digital_v2(id_op)
                            else:
                                status, resultado = api.check_win_v4(id_op)
                            if status:
                                st.session_state.lucro_sessao += resultado
                                tipo_entrada = "Entrada Normal" if gale_atual == 0 else f"Gale {gale_atual}"
                                st.session_state.historico.append({
                                    "Ativo": ativo,
                                    "Direção": direcao.upper(),
                                    "Etapa": tipo_entrada,
                                    "Resultado": round(resultado, 2),
                                    "Hora": datetime.now().strftime("%H:%M:%S")
                                })
                                lucro_trade = resultado
                                break
                # Verifica se é WIN ou precisa de gale
                if lucro_trade > 0:
                    break
                gale_atual += 1
        else:
            st.warning(f"Aguardando sinal para {ativo}")
    else:
        st.error("Nenhum ativo catalogado.")

    # Stop Win / Stop Loss
    if st.session_state.lucro_sessao >= stop_win:
        st.success("🏆 STOP WIN atingido!")
        st.session_state.rodando = False
        st.rerun()
    elif st.session_state.lucro_sessao <= -stop_loss:
        st.error("🛑 STOP LOSS atingido!")
        st.session_state.rodando = False
        st.rerun()

    if st.session_state.rodando:
        time.sleep(10)
        st.rerun()
