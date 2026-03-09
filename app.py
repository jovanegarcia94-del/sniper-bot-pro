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

# ---------------- ESTILOS ----------------
st.markdown("""
<style>
.trade-log { padding: 8px; margin-bottom: 5px; border-radius: 5px; font-family: monospace; }
.win { background-color: #1e3f1e; color: #00ff88; }
.loss { background-color: #3f1e1e; color: #ff4b4b; }
.info { background-color: #1e1e3f; color: #00ccff; }
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION STATE ----------------
if 'rodando' not in st.session_state: st.session_state.rodando = False
if 'lucro_sessao' not in st.session_state: st.session_state.lucro_sessao = 0.0
if 'historico' not in st.session_state: st.session_state.historico = []
if 'estrategia_usuario' not in st.session_state: st.session_state.estrategia_usuario = "MHI"
if 'conectado' not in st.session_state: st.session_state.conectado = False
if 'api' not in st.session_state: st.session_state.api = None
if 'logs' not in st.session_state: st.session_state.logs = []

# ---------------- FUNÇÃO DE LOG ----------------
def log(msg, tipo="info"):
    hora = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append({"hora": hora, "msg": msg, "tipo": tipo})
    if len(st.session_state.logs) > 200:
        st.session_state.logs.pop(0)

# ---------------- SIDEBAR: CONEXÃO ----------------
with st.sidebar:
    st.title("🤖 Robô Trader Pro")
    st.markdown("---")
    st.header("🔑 Conexão IQ Option")
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
    
    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")

    if st.button("🔌 Conectar", use_container_width=True):
        if email and senha:
            with st.spinner("Conectando..."):
                try:
                    api = IQ_Option(email, senha)
                    check,_ = api.connect()
                    if check:
                        api.change_balance(conta_tipo)
                        st.session_state.api = api
                        st.session_state.conectado = True
                        log(f"Conectado com sucesso na conta {conta_tipo}!", "info")
                        st.rerun()
                    else:
                        st.error("Falha ao conectar. Verifique email/senha")
                except Exception as e:
                    st.error(str(e))
        else:
            st.warning("Informe email e senha")

    if st.session_state.conectado:
        st.success("✅ Online")
        if st.button("🛑 Parar Robô", use_container_width=True):
            st.session_state.rodando = False
            st.rerun()

# ---------------- DASHBOARD SUPERIOR ----------------
st.title("Painel de Operações")
col1, col2, col3, col4 = st.columns(4)
saldo, moeda = 0, ""
simbolo = ""

if st.session_state.api and st.session_state.conectado:
    try:
        saldo = st.session_state.api.get_balance()
        moeda = st.session_state.api.get_currency()
        simbolo = "$" if moeda == "USD" else "R$"
    except:
        saldo = 0
        simbolo = "R$"

with col1: st.metric("💰 Saldo Conta", f"{simbolo} {round(saldo,2)}")
with col2: st.metric("💵 Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
with col3: st.metric("⚙️ Status do Robô", "🟢 Rodando" if st.session_state.rodando else "🔴 Parado")
with col4: st.metric("📊 Total de Trades", len(st.session_state.historico))
st.markdown("---")

# ---------------- ABAS PRINCIPAIS ----------------
aba1, aba2, aba3 = st.tabs(["🎮 Controle", "⚙️ Configurações", "📜 Histórico de Operações"])

# ---------------- CONTROLE ----------------
with aba1:
    st.subheader("Gerenciamento do Robô")
    c1, c2 = st.columns(2)
    with c1:
        if not st.session_state.rodando:
            if st.button("▶ Iniciar Robô", use_container_width=True, type="primary"):
                if st.session_state.conectado:
                    st.session_state.rodando = True
                    st.rerun()
                else:
                    st.error("Conecte-se à IQ Option primeiro!")
        else:
            if st.button("⛔ Parar Robô", use_container_width=True):
                st.session_state.rodando = False
                st.rerun()

# ---------------- CONFIGURAÇÕES ----------------
with aba2:
    st.subheader("Parâmetros de Operação")
    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    
    with col_cfg1:
        st.session_state.estrategia_usuario = st.selectbox("Estratégia", ["MHI","MHI M5","Torres Gêmeas"])
        tipo_op = st.selectbox("Tipo Operação", ["digital","binaria"])
        valor_entrada = st.number_input("Valor Entrada", value=2.5, step=0.5)
        
    with col_cfg2:
        stop_win = st.number_input("Stop Win", value=4.0, step=1.0)
        stop_loss = st.number_input("Stop Loss", value=3.0, step=1.0)
        
    with col_cfg3:
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
        st.info("Nenhum trade executado nesta sessão ainda.")

# ---------------- LOGS ----------------
log_container = st.empty()

# ---------------- FUNÇÃO DO BOT ----------------
def analisar_e_operar():
    try:
        lista, _ = catag(st.session_state.api, niveis_mg=niveis_mg, usar_mg=usar_mg)
        if not lista:
            log("Nenhum ativo encontrado", "info")
            return
        
        melhor = lista[0]
        ativo = melhor[1]
        direcao = analisar_entrada(st.session_state.api, ativo, st.session_state.estrategia_usuario)
        log(f"Sinal encontrado: {ativo} -> {direcao}" if direcao else f"Sem sinal para {ativo}", "info")
        
        if direcao:
            valor_atual = valor_entrada
            mg_atual = 0
            while True:
                if tipo_op == "digital":
                    check, id_op = st.session_state.api.buy_digital_spot_v2(ativo, valor_atual, direcao, 1)
                else:
                    check, id_op = st.session_state.api.buy(valor_atual, ativo, direcao, 1)
                
                if not check:
                    log("Erro ao abrir operação", "loss")
                    break
                
                # Monitorar resultado
                status_op = False
                while not status_op:
                    time.sleep(1)
                    if tipo_op == "digital":
                        status_op, resultado = st.session_state.api.check_win_digital_v2(id_op)
                    else:
                        status_op, resultado = st.session_state.api.check_win_v4(id_op)
                
                st.session_state.lucro_sessao += resultado
                st.session_state.historico.append({
                    "ativo": ativo,
                    "direcao": direcao,
                    "resultado": round(resultado,2),
                    "hora": datetime.now().strftime("%H:%M:%S")
                })
                
                if resultado < 0 and usar_mg and mg_atual < niveis_mg:
                    mg_atual += 1
                    valor_atual *= fator_mg
                    log(f"LOSS! Abrindo Martingale {mg_atual} com valor {valor_atual}", "loss")
                else:
                    log(f"{'WIN!' if resultado>0 else 'LOSS!'} Resultado final: {resultado}", "win" if resultado>0 else "loss")
                    break
    except Exception as e:
        log(f"Erro no ciclo: {e}", "loss")

# ---------------- LOOP PRINCIPAL ----------------
if st.session_state.rodando and st.session_state.conectado:
    analisar_e_operar()
    
    # Atualiza métricas e logs dinamicamente
    saldo = st.session_state.api.get_balance()
    moeda = st.session_state.api.get_currency()
    simbolo = "$" if moeda=="USD" else "R$"
    col1.metric("💰 Saldo Conta", f"{simbolo} {round(saldo,2)}")
    col2.metric("💵 Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
    col3.metric("⚙️ Status do Robô", "🟢 Rodando" if st.session_state.rodando else "🔴 Parado")
    col4.metric("📊 Total de Trades", len(st.session_state.historico))
    
    # Mostra logs
    log_text = ""
    for item in reversed(st.session_state.logs[-50:]):
        cor = "win" if item["tipo"]=="win" else "loss" if item["tipo"]=="loss" else "info"
        log_text += f'<div class="trade-log {cor}">[{item["hora"]}] {item["msg"]}</div>'
    log_container.markdown(log_text, unsafe_allow_html=True)
    
    time.sleep(3)
    st.rerun()
