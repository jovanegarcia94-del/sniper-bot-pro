import streamlit as st
import pandas as pd
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime

# ---------------- CONFIGURAÇÃO DE PÁGINA ----------------
st.set_page_config(page_title="Robô Trader Pro", layout="wide")

# ---------------- ESTADOS ----------------
if 'rodando' not in st.session_state:
    st.session_state.rodando = False
if 'lucro_sessao' not in st.session_state:
    st.session_state.lucro_sessao = 0.0
if 'historico' not in st.session_state:
    st.session_state.historico = []

if 'api' not in st.session_state:
    st.session_state.api = None
if 'conectado' not in st.session_state:
    st.session_state.conectado = False
if 'login_hash' not in st.session_state:
    st.session_state.login_hash = None  # Para diferenciar logins

# ---------------- FUNÇÃO DE ANÁLISE ----------------
def analisar_entrada(api, ativo, estrategia):
    timeframe = 300 if estrategia == 'MHI M5' else 60
    qnt_velas = 4 if estrategia == 'Torres Gêmeas' else 3
    velas = api.get_candles(ativo, timeframe, qnt_velas, time.time())
    cores = ["Verde" if v['open'] < v['close'] else "Vermelha" if v['open'] > v['close'] else "Doji" for v in velas]

    direcao = None
    if estrategia in ['MHI','MHI M5']:
        if cores.count('Verde') > cores.count('Vermelha') and 'Doji' not in cores:
            direcao = "put"
        elif cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
            direcao = "call"
    elif estrategia == 'Torres Gêmeas':
        if cores[0] == 'Verde':
            direcao = "call"
        elif cores[0] == 'Vermelha':
            direcao = "put"
    return direcao

# ---------------- DASHBOARD SUPERIOR ----------------
st.title("📈 Robô Trader Pro")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

saldo = 0
moeda = ""
if st.session_state.conectado and st.session_state.api:
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
    st.metric("Status do Bot", status)
with col4:
    st.metric("Total de Trades", len(st.session_state.historico))

st.markdown("---")

# ---------------- SIDEBAR: LOGIN ----------------
with st.sidebar:
    st.header("Conexão IQ Option")
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])

    email = st.text_input("Email", key="email_input")
    senha = st.text_input("Senha", type="password", key="senha_input")

    if st.button("Conectar IQ Option", use_container_width=True):
        login_hash = f"{email}-{senha}-{conta_tipo}"
        if st.session_state.login_hash != login_hash:
            # Se for um login diferente, limpar sessão anterior
            st.session_state.api = None
            st.session_state.conectado = False
            st.session_state.rodando = False
            st.session_state.login_hash = login_hash
        
        try:
            api = IQ_Option(email, senha)
            check, _ = api.connect()
            if check:
                api.change_balance(conta_tipo)
                st.session_state.api = api
                st.session_state.conectado = True
                st.session_state.login_hash = login_hash
                st.success(f"Conectado na conta {conta_tipo}")
                st.rerun()
            else:
                st.error("Falha ao conectar. Verifique suas credenciais.")
        except Exception as e:
            st.error(f"Erro: {e}")

    if st.session_state.conectado and st.session_state.api:
        st.success("✅ Conectado com sucesso")
        if st.button("Desconectar", use_container_width=True):
            st.session_state.api = None
            st.session_state.conectado = False
            st.session_state.rodando = False
            st.session_state.login_hash = None
            st.rerun()

# ---------------- ABAS ----------------
aba1, aba2, aba3 = st.tabs(["🎮 Controle", "⚙️ Configurações", "📊 Histórico de Operações"])

# ---------------- CONFIGURAÇÕES ----------------
with aba2:
    st.subheader("Parâmetros do Robô")
    cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
    
    with cfg_col1:
        st.selectbox("Estratégia", ["MHI", "MHI M5", "Torres Gêmeas"], key="estrategia_usuario")
        st.selectbox("Tipo de Operação", ["digital", "binaria"], key="tipo")
        st.number_input("Valor de Entrada", value=2.5, step=0.5, key="valor_entrada")
    with cfg_col2:
        st.number_input("Stop Win", value=4.0, step=1.0, key="stop_win")
        st.number_input("Stop Loss", value=3.0, step=1.0, key="stop_loss")
    with cfg_col3:
        st.checkbox("Usar Martingale", key="usar_mg")
        st.number_input("Níveis Martingale", value=1, min_value=1, key="niveis_mg")
        st.number_input("Fator Martingale", value=2.0, step=0.1, key="fator_mg")
        st.checkbox("Usar Soros", key="usar_soros")
        st.number_input("Níveis Soros", value=2, min_value=1, key="niveis_soros")

# ---------------- CONTROLE ----------------
with aba1:
    st.subheader("Painel de Controle")
    if not st.session_state.rodando:
        if st.button("▶ INICIAR ROBÔ", type="primary", use_container_width=True):
            if st.session_state.conectado:
                st.session_state.rodando = True
                st.rerun()
            else:
                st.warning("Conecte-se à IQ Option primeiro!")
    else:
        if st.button("⛔ PARAR ROBÔ", type="primary", use_container_width=True):
            st.session_state.rodando = False
            st.rerun()

# ---------------- HISTÓRICO ----------------
with aba3:
    if len(st.session_state.historico) > 0:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum trade executado ainda nesta sessão.")

# ---------------- LOOP DO BOT ----------------
if st.session_state.conectado and st.session_state.rodando:
    st.markdown("---")
    st.subheader("🔄 Processando ciclo de operação...")
    
    estrategia = st.session_state.estrategia_usuario
    tipo = st.session_state.tipo
    valor_entrada = st.session_state.valor_entrada
    stop_win = st.session_state.stop_win
    stop_loss = st.session_state.stop_loss
    usar_mg = st.session_state.usar_mg
    niveis_mg = st.session_state.niveis_mg
    fator_mg = st.session_state.fator_mg

    # Catalogação de ativos
    lista, linha_idx = catag(
        st.session_state.api,
        niveis_mg=niveis_mg,
        usar_mg=usar_mg
    )
    
    if lista:
        melhor = lista[0]
        ativo = melhor[1]
        direcao = analisar_entrada(st.session_state.api, ativo, estrategia)
        
        if direcao:
            st.success(f"Sinal encontrado! Operando {direcao.upper()} em {ativo}")
            
            gale_atual = 0
            max_gale = niveis_mg if usar_mg else 0
            
            while gale_atual <= max_gale:
                valor_operacao = valor_entrada * (fator_mg ** gale_atual)
                lucro_trade = 0
                
                if tipo == "digital":
                    check, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_operacao, direcao, 1)
                else:
                    check, id = st.session_state.api.buy(valor_operacao, ativo, direcao, 1)
                
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
                                "Ativo": ativo,
                                "Direção": direcao.upper(),
                                "Etapa": f"Gale {gale_atual}" if gale_atual > 0 else "Entrada Normal",
                                "Resultado": round(resultado,2),
                                "Hora": datetime.now().strftime("%H:%M:%S")
                            })
                            lucro_trade = resultado
                            break
                
                if lucro_trade > 0:
                    break
                else:
                    gale_atual += 1

        else:
            st.info(f"Aguardando sinal para o ativo {ativo}...")
    else:
        st.warning("Nenhum ativo catalogado.")

    # Stops
    if st.session_state.lucro_sessao >= stop_win:
        st.success("🏆 STOP WIN ATINGIDO! Encerrando o robô.")
        st.session_state.rodando = False
    elif st.session_state.lucro_sessao <= -stop_loss:
        st.error("🛑 STOP LOSS ATINGIDO! Encerrando o robô.")
        st.session_state.rodando = False

    if st.session_state.rodando:
        time.sleep(5)
        st.rerun()
