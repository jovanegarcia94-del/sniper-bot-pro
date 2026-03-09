import streamlit as st
import pandas as pd
import time
from iqoptionapi.stable_api import IQ_Option
from catalogador import catag
from datetime import datetime

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(page_title="Robô Trader Logs + Martingale", layout="wide")

# ---------------- ESTADOS ----------------
for key, default in [
    ('rodando', False),
    ('lucro_sessao', 0.0),
    ('historico', []),
    ('estrategia_usuario', 'MHI'),
    ('conectado', False),
    ('api', None),
    ('mg_ativo', False),
    ('mg_valor', 0)
]:
    if key not in st.session_state:
        st.session_state[key] = default

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
    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")

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
aba1, aba2, aba3 = st.tabs(["Controle","Configurações","Logs"])

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

# ---------------- LOGS ----------------
placeholder_logs = aba3.empty()

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
    
    placeholder_logs.write("\n".join(logs))

# ---------------- LOOP DO BOT COM MARTINGALE ----------------
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

            atualizar_logs()
            st.write(f"Ativo escolhido: {ativo} | Estratégia: {estrategia}")

            direcao = analisar_entrada(st.session_state.api, ativo, estrategia)
            if direcao:
                # Valor da operação com martingale
                if st.session_state.mg_ativo:
                    valor_operacao = st.session_state.mg_valor
                else:
                    valor_operacao = valor_entrada

                st.success(f"Operando {direcao} | Valor: {valor_operacao}")
                
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
                            # Martingale: se perdeu, ativa próximo com fator
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
