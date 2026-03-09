import streamlit as st
import time
from datetime import datetime
from iqoptionapi.stable_api import IQ_Option

from catag import catag


# ------------------------------
# CONFIG STREAMLIT
# ------------------------------

st.set_page_config(
    page_title="Sniper Bot Pro",
    layout="wide"
)

st.title("🤖 SNIPER BOT PRO")


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
# SIDEBAR
# ------------------------------

with st.sidebar:

    st.header("🔐 Conexão")

    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")

    conta = st.selectbox(
        "Tipo de Conta",
        ["PRACTICE", "REAL"]
    )

    conectar = st.button("🔌 Conectar")

    st.divider()

    st.header("⚙️ Configuração")

    entrada = st.number_input("Valor entrada", value=2.0)

    fator_mg = st.number_input("Fator MG", value=2.2)

    usar_mg = st.checkbox("Usar Martingale", value=True)

    usar_soros = st.checkbox("Usar Soros", value=False)

    payout_min = st.slider("Payout mínimo", 50, 100, 80)


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

            log("Conectado com sucesso")

        else:

            st.error(reason)

    except Exception as e:

        st.error(str(e))


# ------------------------------
# BOTÕES
# ------------------------------

col1, col2 = st.columns(2)

with col1:

    if st.button("▶️ Iniciar Bot"):

        if st.session_state.conectado:

            st.session_state.rodando = True

            log("BOT INICIADO")

with col2:

    if st.button("⛔ Parar Bot"):

        st.session_state.rodando = False

        log("BOT PARADO")


# ------------------------------
# LOG AREA
# ------------------------------

st.subheader("📜 Logs do Robô")

log_box = st.empty()


# ------------------------------
# MOTOR DO BOT
# ------------------------------

def executar_bot():

    api = st.session_state.api

    try:

        lista, linha_idx = catag()

    except Exception as e:

        log(f"Erro na catalogação: {e}")
        return

    if not lista:

        log("Nenhum ativo encontrado")
        return

    ativo = lista[0]["ativo"]
    direcao = lista[0]["direcao"]

    log(f"Sinal encontrado {ativo} {direcao}")

    valor = entrada

    check, id_o = api.buy_digital_spot_v2(
        ativo,
        valor,
        direcao,
        1
    )

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

            if usar_soros:
                valor = entrada + res
            else:
                valor = entrada

            break

        else:

            log(f"LOSS {res:.2f}")

            if usar_mg and gale < 2:

                gale += 1

                valor = valor * fator_mg

                log(f"MARTINGALE {gale} valor {valor}")

                check, id_o = api.buy_digital_spot_v2(
                    ativo,
                    valor,
                    direcao,
                    1
                )

                if not check:

                    log("Erro MG")
                    break

            else:

                break

    st.session_state.lucro += resultado_total

    log(f"Lucro sessão {st.session_state.lucro:.2f}")


# ------------------------------
# LOOP PRINCIPAL
# ------------------------------

if st.session_state.rodando:

    executar_bot()

    time.sleep(2)


# ------------------------------
# MOSTRAR LOGS
# ------------------------------

log_text = "\n".join(st.session_state.logs[::-1])

log_box.text(log_text)
