import streamlit as st
import time
from datetime import datetime
from iqoptionapi.stable_api import IQ_Option

from catalogador import catag  # função atualizada


# ------------------------------
# CONFIG STREAMLIT
# ------------------------------

st.set_page_config(
    page_title="Sniper Bot Pro",
    layout="wide"
)

st.title("🤖 SNIPER BOT")


# ------------------------------
# SESSION STATE
# ------------------------------

if "api" not in st.session_state:
    st.session_state.api = None

if "conectado" not in st.session_state:
    st.session_state.conectado = False

if "rodando" not in st.session_state:
    st.session_state.rodando = False

if "logs" not in st.session_state:
    st.session_state.logs = []

if "lucro" not in st.session_state:
    st.session_state.lucro = 0

if "proxima_entrada" not in st.session_state:
    st.session_state.proxima_entrada = 0.0

if "melhor_ativo" not in st.session_state:
    st.session_state.melhor_ativo = None


# ------------------------------
# FUNÇÃO LOG
# ------------------------------

def log(msg):
    hora = datetime.now().strftime("%H:%M:%S")
    linha = f"[{hora}] {msg}"
    st.session_state.logs.append(linha)
    if len(st.session_state.logs) > 200:
        st.session_state.logs.pop(0)


# ------------------------------
# SIDEBAR - CONEXÃO
# ------------------------------

with st.sidebar:

    st.header("🔐 Conexão")

    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")
    conta = st.selectbox("Tipo de Conta", ["PRACTICE", "REAL"])
    conectar = st.button("🔌 Conectar")

    st.divider()

    st.header("⚙️ Configurações")

    entrada = st.number_input("Valor da entrada", value=2.0)
    fator_mg = st.number_input("Fator Martingale", value=2.2)
    usar_mg = st.checkbox("Usar Martingale", value=True)
    usar_soros = st.checkbox("Usar Soros", value=False)
    stop_win = st.number_input("Stop Win", value=10.0)
    stop_loss = st.number_input("Stop Loss", value=5.0)


# ------------------------------
# CONEXÃO
# ------------------------------

if conectar:
    try:
        api = IQ_Option(email, senha)
        check, reason = api.connect()
        if check:
            api.change_balance(conta)
            st.session_state.api = api
            st.session_state.conectado = True
            log(f"Conectado com sucesso na conta {conta}")
        else:
            st.error(reason)
    except Exception as e:
        st.error(str(e))


# ------------------------------
# BOTÕES INICIAR/PARAR
# ------------------------------

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Iniciar Bot"):
        if st.session_state.conectado:
            st.session_state.rodando = True
            st.session_state.proxima_entrada = entrada
            log("BOT INICIADO")

with col2:
    if st.button("⛔ Parar Bot"):
        st.session_state.rodando = False
        log("BOT PARADO")


# ------------------------------
# ÁREA DE LOGS
# ------------------------------

st.subheader("📜 Logs do Robô")
log_box = st.empty()


# ------------------------------
# FUNÇÃO DO MOTOR DO ROBÔ
# ------------------------------

def executar_bot():
    api = st.session_state.api

    try:
        # passa os parâmetros do martingale para o catalogador
        lista, linha_idx = catag(usar_mg=usar_mg, niveis_mg=2)
    except Exception as e:
        log(f"Erro na catalogação: {e}")
        return

    if not lista:
        log("Nenhum ativo encontrado")
        return

    ativo = lista[0]["ativo"]
    direcao = lista[0]["direcao"]
    log(f"Sinal encontrado {ativo} {direcao}")

    valor = st.session_state.proxima_entrada
    check, id_o = api.buy_digital_spot_v2(ativo, valor, direcao, 1)

    if not check:
        log("Erro ao abrir operação")
        return

    gale = 0
    resultado_total = 0

    while True:
        check_res = False
        while not check_res:
            time.sleep(1)
            check_res, res = api.check_win_digital_v2(id_o)

        resultado_total += res

        if res > 0:
            log(f"WIN {res:.2f}")
            st.session_state.proxima_entrada = entrada + res if usar_soros else entrada
            break
        else:
            log(f"LOSS {res:.2f}")
            if usar_mg and gale < 2:
                gale += 1
                valor *= fator_mg
                st.session_state.proxima_entrada = valor
                log(f"MARTINGALE {gale} valor {valor:.2f}")
                check, id_o = api.buy_digital_spot_v2(ativo, valor, direcao, 1)
                if not check:
                    log("Erro MG")
                    break
            else:
                st.session_state.proxima_entrada = entrada
                break

    st.session_state.lucro += resultado_total
    log(f"Lucro sessão {st.session_state.lucro:.2f}")


# ------------------------------
# LOOP PRINCIPAL
# ------------------------------

if st.session_state.rodando and st.session_state.conectado:
    executar_bot()
    time.sleep(2)
    st.rerun()


# ------------------------------
# MOSTRAR LOGS
# ------------------------------

log_text = "\n".join(st.session_state.logs[::-1])
log_box.text(log_text)
