import streamlit as st
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(page_title="Sniper Bot Streamlit", layout="wide")

# ---------------- ESTADOS ----------------
estado_inicial = [
    ('rodando', False),
    ('lucro_sessao', 0.0),
    ('historico', []),
    ('estrategia_usuario', 'MHI'),
    ('conectado', False),
    ('api', None),
    ('mg_ativo', False),
    ('mg_valor', 0.0),
    ('ultimo_ativo', '')
]

for key, default in estado_inicial:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------- FUNÇÕES ----------------
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
        elif cores.count('Verde') < cores.count('Vermelha') and 'Doji' not in cores:
            direcao = "call"
    elif estrategia == 'Torres Gêmeas':
        if cores[0] == 'Verde':
            direcao = "call"
        elif cores[0] == 'Vermelha':
            direcao = "put"
    return direcao

def atualizar_logs():
    logs = []
    if st.session_state.api:
        try:
            saldo = st.session_state.api.get_balance()
            moeda = st.session_state.api.get_currency()
            simbolo = "$" if moeda=="USD" else "R$"
        except:
            saldo = 0
            simbolo = "R$"
    else:
        saldo = 0
        simbolo = "R$"

    logs.append(f"Saldo Conta: {simbolo} {round(saldo,2)}")
    logs.append(f"Lucro Sessão: {simbolo} {round(st.session_state.lucro_sessao,2)}")
    logs.append(f"Status: {'Rodando' if st.session_state.rodando else 'Parado'}")
    logs.append("Últimos Trades:")
    if st.session_state.historico:
        for trade in st.session_state.historico[-5:]:
            logs.append(f"{trade['hora']} | {trade['ativo']} | {trade['direcao']} | {trade['resultado']}")
    else:
        logs.append("Nenhum trade executado ainda")
    
    st.session_state.placeholder_logs.write("\n".join(logs))

# ---------------- SIDEBAR ----------------
st.sidebar.header("Conexão IQ Option")
conta_tipo = st.sidebar.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
email = st.sidebar.text_input("Email")
senha = st.sidebar.text_input("Senha", type="password")

if st.sidebar.button("Conectar"):
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
    if st.sidebar.button("Parar Robô"):
        st.session_state.rodando = False

# ---------------- CONFIGURAÇÕES ----------------
st.sidebar.header("Configurações do Bot")
st.session_state.estrategia_usuario = st.sidebar.selectbox(
    "Estratégia", ["MHI","MHI M5","Torres Gêmeas"]
)
valor_entrada = st.sidebar.number_input("Valor Entrada", value=2.5)
stop_win = st.sidebar.number_input("Stop Win", value=4.0)
stop_loss = st.sidebar.number_input("Stop Loss", value=3.0)
tipo = st.sidebar.selectbox("Tipo Operação", ["digital","binaria"])
usar_mg = st.sidebar.checkbox("Usar Martingale")
niveis_mg = st.sidebar.number_input("Níveis Martingale", value=1)
fator_mg = st.sidebar.number_input("Fator Martingale", value=2.0)
usar_soros = st.sidebar.checkbox("Usar Soros")
niveis_soros = st.sidebar.number_input("Níveis Soros", value=2)

# ---------------- LOGS ----------------
st.header("Logs do Bot")
if 'placeholder_logs' not in st.session_state:
    st.session_state.placeholder_logs = st.empty()
st.session_state.placeholder_logs.empty()

# ---------------- LOOP DO BOT ----------------
if st.session_state.api and st.session_state.rodando:
    try:
        lista, linha_idx = catag(
            st.session_state.api,
            niveis_mg=niveis_mg,
            usar_mg=usar_mg
        )
        if lista:
            melhor = lista[0]
            ativo = melhor[1]
            estrategia = st.session_state.estrategia_usuario

            st.write(f"Ativo escolhido: {ativo} | Estratégia: {estrategia}")

            direcao = analisar_entrada(st.session_state.api, ativo, estrategia)
            if direcao:
                # Martingale
                valor_operacao = st.session_state.mg_valor if st.session_state.mg_ativo else valor_entrada

                st.write(f"Operando {direcao} | Valor: {valor_operacao}")
                
                if tipo == "digital":
                    check, id = st.session_state.api.buy_digital_spot_v2(
                        ativo, valor_operacao, direcao, 1
                    )
                else:
                    check, id = st.session_state.api.buy(
                        valor_operacao, ativo, direcao, 1
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
                            # Martingale
                            if resultado < 0 and usar_mg:
                                st.session_state.mg_ativo = True
                                st.session_state.mg_valor = valor_operacao * fator_mg
                                st.info(f"Martingale ativado! Próximo valor: {st.session_state.mg_valor}")
                            else:
                                st.session_state.mg_ativo = False
                                st.session_state.mg_valor = 0
                            atualizar_logs()
                            break
            else:
                st.warning("Sem sinal")
            
            # Stop loss / stop win
            if st.session_state.lucro_sessao >= stop_win or st.session_state.lucro_sessao <= -stop_loss:
                st.error("Stop atingido")
                st.session_state.rodando = False
                atualizar_logs()
        else:
            st.warning("Nenhum ativo disponível")
            atualizar_logs()
    except Exception as e:
        st.error(f"Erro no ciclo: {e}")
        atualizar_logs()
