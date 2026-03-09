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

# ---------------- ESTILO CUSTOMIZADO (CSS ADAPTÁVEL) ----------------
# Usando rgba e variáveis nativas para funcionar perfeitamente no Modo Claro e Escuro
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.1);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    </style>
""", unsafe_allow_html=True)

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

# ---------------- SIDEBAR: CONEXÃO ----------------
with st.sidebar:
    st.title("🤖 Robô Trader Pro")
    st.markdown("---")
    st.header("🔑 Conexão IQ Option")
    conta_tipo = st.selectbox("Tipo de Conta", ["PRACTICE","REAL"])
    
    email = st.text_input("Email", value="", placeholder="Seu email da IQ")
    senha = st.text_input("Senha", type="password", value="", placeholder="Sua senha")

    if st.button("🔌 Conectar", use_container_width=True):
        if email and senha:
            with st.spinner("Conectando aos servidores..."):
                api = IQ_Option(email, senha)
                check,_ = api.connect()
                if check:
                    api.change_balance(conta_tipo)
                    st.session_state.api = api
                    st.session_state.conectado = True
                    st.toast(f"Conectado com sucesso na conta {conta_tipo}!", icon="✅")
                else:
                    st.error("Falha ao conectar. Verifique email/senha")
        else:
            st.warning("Informe email e senha")

    if st.session_state.conectado and st.session_state.api:
        st.success("✅ Status: Online")
        st.markdown("---")
        if st.button("🛑 Emergência: Parar Bot", use_container_width=True, type="primary"):
            st.session_state.rodando = False
            st.rerun()

# ---------------- DASHBOARD SUPERIOR ----------------
st.title("Painel de Operações")
col1, col2, col3, col4 = st.columns(4)
saldo = 0
moeda = ""

if st.session_state.api and st.session_state.conectado:
    try:
        saldo = st.session_state.api.get_balance()
        moeda = st.session_state.api.get_currency()
    except:
        saldo = 0
simbolo = "$" if moeda == "USD" else "R$"

with col1:
    st.metric("💰 Saldo Conta", f"{simbolo} {round(saldo,2)}")
with col2:
    st.metric("💵 Lucro Sessão", f"{simbolo} {round(st.session_state.lucro_sessao,2)}")
with col3:
    status = "🟢 Rodando (Buscando Sinais)" if st.session_state.rodando else "🔴 Parado"
    st.metric("⚙️ Status do Robô", status)
with col4:
    st.metric("📊 Total de Trades", len(st.session_state.historico))

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
        tipo = st.selectbox("Tipo Operação", ["digital","binaria"])
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
    if len(st.session_state.historico) > 0:
        df = pd.DataFrame(st.session_state.historico)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    else:
        st.info("Nenhum trade executado nesta sessão ainda.")

# ---------------- LOOP BOT POR CICLO (ÁREA DE EXECUÇÃO) ----------------
st.markdown("---")
log_container = st.empty()

if st.session_state.api and st.session_state.rodando:
    with log_container.container():
        try:
            with st.spinner("Analisando mercado e buscando oportunidades..."):
                lista, linha_idx = catag(
                    st.session_state.api,
                    niveis_mg=niveis_mg,
                    usar_mg=usar_mg
                )
                
            if len(lista) == 0:
                st.warning("Nenhum ativo disponível no momento.")
            else:
                melhor = lista[0]
                ativo = melhor[1]
                estrategia = st.session_state.estrategia_usuario
                
                col_info1, col_info2 = st.columns(2)
                col_info1.info(f"**Ativo Analisado:** {ativo}")
                col_info2.info(f"**Estratégia:** {estrategia}")

                direcao = analisar_entrada(st.session_state.api, ativo, estrategia)
                
                if direcao:
                    cor_dir = "🟢" if direcao == "call" else "🔴"
                    st.success(f"Sinal Encontrado! Operando {cor_dir} **{direcao.upper()}**")
                    
                    if tipo == "digital":
                        check, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_entrada, direcao, 1)
                    else:
                        check, id = st.session_state.api.buy(valor_entrada, ativo, direcao, 1)
                        
                    if check:
                        with st.status("Aguardando finalização da ordem...", expanded=True) as status_ordem:
                            st.write("Ordem aberta. Aguardando resultado...")
                            
                            valor_atual = valor_entrada
                            mg_atual = 0
                            
                            while True:
                                time.sleep(0.5) # Tempo reduzido para resposta imediata
                                
                                if tipo == "digital":
                                    status_op, resultado = st.session_state.api.check_win_digital_v2(id)
                                else:
                                    status_op, resultado = st.session_state.api.check_win_v4(id)
                                    
                                if status_op:
                                    # Salva o histórico da entrada que acabou de fechar
                                    st.session_state.lucro_sessao += resultado
                                    st.session_state.historico.append({
                                        "ativo": ativo,
                                        "direcao": direcao,
                                        "resultado": round(resultado, 2),
                                        "hora": datetime.now().strftime("%H:%M:%S")
                                    })
                                    
                                    # LÓGICA DE MARTINGALE IMEDIATO SEM PERDER 1 SEGUNDO
                                    if resultado < 0 and usar_mg and mg_atual < niveis_mg:
                                        mg_atual += 1
                                        valor_atual = valor_atual * fator_mg
                                        st.toast(f"LOSS! Disparando MG {mg_atual} imediatamente...", icon="⚡")
                                        st.write(f"Abrindo Martingale {mg_atual} com valor {valor_atual}...")
                                        
                                        # Executa a compra instantaneamente na mesma direção
                                        if tipo == "digital":
                                            check_mg, id = st.session_state.api.buy_digital_spot_v2(ativo, valor_atual, direcao, 1)
                                        else:
                                            check_mg, id = st.session_state.api.buy(valor_atual, ativo, direcao, 1)
                                            
                                        if not check_mg:
                                            st.error(f"Falha na API ao tentar abrir o MG {mg_atual}")
                                            break
                                            
                                        # O loop while continua girando, agora monitorando o novo 'id' do MG
                                    else:
                                        # Quando a operação dá WIN ou os MGs acabam, finaliza tudo
                                        status_ordem.update(label=f"Ciclo Finalizado! Resultado: {simbolo} {round(resultado, 2)}", state="complete")
                                        if resultado > 0:
                                            st.toast("WIN! Operação vitoriosa!", icon="🤑")
                                        else:
                                            st.toast("LOSS! Ciclo perdido.", icon="📉")
                                        break
                else:
                    st.info("Análise concluída: Sem sinal de entrada no momento.")

                # Verificação de Stop Loss / Stop Win
                if st.session_state.lucro_sessao >= stop_win:
                    st.success("🎉 STOP WIN ATINGIDO! Parabéns, meta batida.")
                    st.session_state.rodando = False
                elif st.session_state.lucro_sessao <= -stop_loss:
                    st.error("⚠️ STOP LOSS ATINGIDO! Cota máxima de perda atingida.")
                    st.session_state.rodando = False

        except Exception as e:
            st.error(f"Erro no ciclo: {e}")
            
    # Auto-recarregamento a cada 3 segundos se o bot estiver ativo
    if st.session_state.rodando:
        time.sleep(3) 
        st.rerun()
                                                   
