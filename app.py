import streamlit as st
import pandas as pd
import time
import sqlite3
from datetime import datetime
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag

# ---------------- CONFIGURAÇÃO ----------------
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
if 'usuario_id' not in st.session_state:
    st.session_state.usuario_id = None

# ---------------- BANCO DE DADOS ----------------
conn = sqlite3.connect("usuarios.db", check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    senha TEXT,
    conta_tipo TEXT
)
''')
conn.commit()

# ---------------- FUNÇÃO DE LOGIN ----------------
def cadastrar_usuario(email, senha, conta_tipo):
    try:
        c.execute("INSERT INTO usuarios (email, senha, conta_tipo) VALUES (?, ?, ?)", (email, senha, conta_tipo))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def validar_usuario(email, senha):
    c.execute("SELECT id, conta_tipo FROM usuarios WHERE email=? AND senha=?", (email, senha))
    resultado = c.fetchone()
    if resultado:
        return resultado[0], resultado[1]
    return None, None

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

# ---------------- SIDEBAR DE LOGIN ----------------
with st.sidebar:
    st.header("🔑 Login IQ Option")
    if st.session_state.usuario_id is None:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login"):
                usuario_id, conta_bd = validar_usuario(email, senha)
                if usuario_id:
                    st.session_state.usuario_id = usuario_id
                    st.session_state.conta_tipo = conta_bd
                    st.success(f"Logado com sucesso na conta {conta_bd}")
                    
                    # Conectar à IQ Option
                    api = IQ_Option(email, senha)
                    check, _ = api.connect()
                    if check:
                        api.change_balance(conta_bd)
                        st.session_state.api = api
                        st.toast("Conexão IQ Option estabelecida!", icon="✅")
                    else:
                        st.error("Erro ao conectar na IQ Option.")
                    st.rerun()
                else:
                    st.error("Email ou senha incorretos!")
        with col2:
            if st.button("Cadastrar"):
                if cadastrar_usuario(email, senha, conta_tipo):
                    st.success("Usuário cadastrado com sucesso!")
                else:
                    st.warning("Email já cadastrado!")
    else:
        st.success("✅ Conectado")
        if st.button("Logout"):
            st.session_state.usuario_id = None
            st.session_state.api = None
            st.session_state.rodando = False
            st.rerun()

# ---------------- DASHBOARD ----------------
st.title("📈 Robô Trader Pro")
st.markdown("---")

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
    st.metric("Status do Bot", status)
with col4:
    st.metric("Total de Trades", len(st.session_state.historico))

st.markdown("---")

# ---------------- ABAS ----------------
aba1, aba2, aba3 = st.tabs(["🎮 Controle", "⚙️ Configurações", "📊 Histórico"])

# ABA 2: CONFIGURAÇÕES
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

# ABA 1: CONTROLE
with aba1:
    st.subheader("Painel de Controle")
    if not st.session_state.rodando:
        if st.button("▶ INICIAR ROBÔ", type="primary", use_container_width=True):
            if st.session_state.api:
                st.session_state.rodando = True
                st.rerun()
            else:
                st.warning("Conecte-se à IQ Option primeiro!")
    else:
        if st.button("⛔ PARAR ROBÔ", type="primary", use_container_width=True):
            st.session_state.rodando = False
            st.rerun()

# ABA 3: HISTÓRICO
with aba3:
    if len(st.session_state.historico) > 0:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    else:
        st.info("Nenhum trade executado nesta sessão.")

# ---------------- LOOP BOT ----------------
if st.session_state.api and st.session_state.rodando:
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

    lista, linha_idx = catag(
        st.session_state.api,
        niveis_mg=niveis_mg,
        usar_mg=usar_mg
    )
    
    if lista:
        melhor = lista[0]
        ativo = melhor[1]

        info_col1, info_col2 = st.columns(2)
        info_col1.info(f"**Ativo Analisado:** {ativo}")
        info_col2.info(f"**Estratégia:** {estrategia}")

        direcao = analisar_entrada(st.session_state.api, ativo, estrategia)

        if direcao:
            st.success(f"Sinal Encontrado! Operando {direcao.upper()} em {ativo}")
            
            gale_atual = 0
            max_tentativas = niveis_mg if usar_mg else 0
            
            while gale_atual <= max_tentativas:
                valor_operacao = valor_entrada * (fator_mg ** gale_atual)
                lucro_trade = 0
                
                if tipo == "digital":
                    check, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_operacao, direcao, 1)
                else:
                    check, id = st.session_state.api.buy(valor_operacao, ativo, direcao, 1)

                if check:
                    with st.spinner(f"Aguardando resultado (Gale {gale_atual})..." if gale_atual>0 else "Aguardando resultado da entrada..."):
                        while True:
                            time.sleep(1)
                            if tipo=="digital":
                                status, resultado = st.session_state.api.check_win_digital_v2(id)
                            else:
                                status, resultado = st.session_state.api.check_win_v4(id)
                            if status:
                                st.session_state.lucro_sessao += resultado
                                tipo_entrada = "Entrada Normal" if gale_atual==0 else f"Gale {gale_atual}"
                                st.session_state.historico.append({
                                    "Ativo": ativo,
                                    "Direção": direcao.upper(),
                                    "Etapa": tipo_entrada,
                                    "Resultado": round(resultado,2),
                                    "Hora": datetime.now().strftime("%H:%M:%S")
                                })
                                lucro_trade = resultado
                                break

                if lucro_trade > 0:
                    break
                gale_atual += 1
        else:
            st.warning(f"Aguardando sinal para o ativo {ativo}...")
    else:
        st.error("Nenhum ativo catalogado.")

    # Stop Win / Stop Loss
    if st.session_state.lucro_sessao >= stop_win:
        st.success("🏆 STOP WIN ATINGIDO!")
        st.session_state.rodando = False
        st.rerun()
    elif st.session_state.lucro_sessao <= -stop_loss:
        st.error("🛑 STOP LOSS ATINGIDO!")
        st.session_state.rodando = False
        st.rerun()

    if st.session_state.rodando:
        time.sleep(10)
        st.rerun()
