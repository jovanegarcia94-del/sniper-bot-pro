import streamlit as st
import time
import json
import os
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
from catalogador import catag

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="SNIPER BOT PRO", layout="wide")

# --- SISTEMA DE BANCO DE DADOS (USUÁRIOS) ---
DB_FILE = "users_db.json"
ADMIN_EMAIL = "jovanegarcia94@gmail.com"

def load_users():
    # Se o arquivo não existir ou estiver vazio, cria com o seu acesso de ADMIN
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size == 0:
        admin_data = {
            ADMIN_EMAIL: {
                "nome": "Jovane Garcia",
                "senha": "fofinha15",
                "aprovado": True
            }
        }
        with open(DB_FILE, "w") as f:
            json.dump(admin_data, f, indent=4)
        return admin_data
    
    with open(DB_FILE, "r") as f:
        try:
            users = json.load(f)
            # Força a atualização da sua senha mestre caso você mude no código
            if ADMIN_EMAIL in users:
                users[ADMIN_EMAIL]['senha'] = "fofinha15"
                users[ADMIN_EMAIL]['aprovado'] = True
            return users
        except json.JSONDecodeError:
            return {}

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

# --- ESTADOS DE SESSÃO ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'running' not in st.session_state: st.session_state.running = False
if 'lucro_total' not in st.session_state: st.session_state.lucro_total = 0.0

# --- TELA DE ACESSO ---
if not st.session_state.logged_in:
    st.title("🔐 SNIPER BOT - CONTROLE DE ACESSO")
    aba_login, aba_cadastro = st.tabs(["Entrar no Sistema", "Solicitar Nova Conta"])
    users = load_users()

    with aba_login:
        email_l = st.text_input("E-mail cadastrado").strip().lower()
        senha_l = st.text_input("Senha", type="password")
        if st.button("🚀 Acessar Robô", use_container_width=True):
            if email_l in users and users[email_l]['senha'] == senha_l:
                if users[email_l]['aprovado']:
                    st.session_state.logged_in = True
                    st.session_state.user_email = email_l
                    st.rerun()
                else:
                    st.warning(f"⏳ Sua conta aguarda aprovação de {ADMIN_EMAIL}")
            else:
                st.error("❌ E-mail ou senha incorretos.")

    with aba_cadastro:
        novo_nome = st.text_input("Seu Nome")
        novo_email = st.text_input("Seu E-mail").strip().lower()
        nova_senha = st.text_input("Crie uma Senha", type="password")
        if st.button("📩 Enviar para Aprovação", use_container_width=True):
            if novo_email in users: st.error("E-mail já registrado.")
            elif novo_email and nova_senha:
                users[novo_email] = {"nome": novo_nome, "senha": nova_senha, "aprovado": False, "data": str(datetime.now())}
                save_users(users)
                st.success("✅ Solicitação enviada! Aguarde a liberação do administrador.")
    st.stop()

# --- INTERFACE DO ROBÔ (APÓS LOGIN) ---
st.markdown("""
    <style>
    .stApp { background-color: #06090f; color: #ffffff; }
    .card { background: linear-gradient(145deg, #161b22, #0d1117); border: 1px solid #30363d; border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 10px; }
    .label { color: #8b949e; font-size: 12px; text-transform: uppercase; }
    .value { font-size: 24px; font-weight: bold; margin: 5px 0; }
    .win { color: #238636; } .loss { color: #da3633; } .warning { color: #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Definição das Abas dinâmicas
abas_labels = ["🚀 OPERAÇÕES", "⚙️ CONFIGURAÇÕES"]
if st.session_state.user_email == ADMIN_EMAIL:
    abas_labels.append("🔑 PAINEL ADMIN")

tabs = st.tabs(abas_labels)

# --- ABA ADMIN (EXCLUSIVA) ---
if st.session_state.user_email == ADMIN_EMAIL:
    with tabs[2]:
        st.header("Gerenciamento de Usuários")
        users = load_users()
        for u_email, info in list(users.items()):
            if u_email == ADMIN_EMAIL: continue
            c_u1, c_u2, c_u3 = st.columns([2, 1, 1])
            c_u1.write(f"**{info['nome']}** ({u_email})")
            if info['aprovado']:
                c_u2.success("Ativo")
                if c_u3.button("Revogar", key="rev_"+u_email):
                    users[u_email]['aprovado'] = False
                    save_users(users); st.rerun()
            else:
                c_u2.warning("Pendente")
                if c_u3.button("Aprovar", key="app_"+u_email):
                    users[u_email]['aprovado'] = True
                    save_users(users); st.rerun()

# --- ABA CONFIGURAÇÕES ---
with tabs[1]:
    st.header("⚙️ Ajustes de Trading")
    col_a, col_b = st.columns(2)
    with col_a:
        iq_email = st.text_input("E-mail IQ Option")
        iq_senha = st.text_input("Senha IQ Option", type="password")
        valor_entrada = st.number_input("Entrada ($)", min_value=1.0, value=2.0)
    with col_b:
        stop_win = st.number_input("Stop Win ($)", min_value=1.0, value=20.0)
        stop_loss = st.number_input("Stop Loss ($)", min_value=1.0, value=10.0)
        usar_gale = st.toggle("Martingale", value=True)
        n_gales = st.number_input("Níveis", min_value=0, max_value=2, value=1) if usar_gale else 0
        fator_gale = st.number_input("Multiplicador", value=2.2)

# --- ABA OPERAÇÕES ---
with tabs[0]:
    with st.sidebar:
        st.info(f"👤 Logado como: {st.session_state.user_email}")
        conta = st.selectbox("CONTA", ["PRACTICE", "REAL"])
        estrat_alvo = st.selectbox("ESTRATÉGIA", ["MHI", "Torres Gêmeas", "MHI M5"])
        filtro_90 = st.toggle("Filtro 90%+", value=True)
        
        if st.button("🚀 INICIAR", use_container_width=True, type="primary"):
            if not iq_email: st.error("Configure o login da corretora!")
            else: st.session_state.running = True
        if st.button("🛑 PARAR", use_container_width=True):
            st.session_state.running = False; st.rerun()
        if st.button("🚪 SAIR DO SISTEMA"):
            st.session_state.logged_in = False; st.rerun()

    c1, c2, c3 = st.columns(3)
    banca_card, lucro_card, status_card = c1.empty(), c2.empty(), c3.empty()
    info_op = st.empty()

    if st.session_state.running:
        api = IQ_Option(iq_email, iq_senha)
        check, _ = api.connect()
        if check:
            api.change_balance(conta)
            while st.session_state.running:
                if not api.check_connect():
                    status_card.markdown('<div class="card"><div class="value warning">RECONECTANDO...</div></div>', unsafe_allow_html=True)
                    api.connect(); time.sleep(5); continue
                try:
                    saldo = api.get_balance()
                    banca_card.markdown(f'<div class="card"><div class="label">💰 BANCA</div><div class="value">${saldo:,.2f}</div></div>', unsafe_allow_html=True)
                    lucro_card.markdown(f'<div class="card"><div class="label">📈 LUCRO</div><div class="value {"win" if st.session_state.lucro_total >= 0 else "loss"}">${st.session_state.lucro_total:.2f}</div></div>', unsafe_allow_html=True)
                    
                    if st.session_state.lucro_total >= stop_win or st.session_state.lucro_total <= (stop_loss * -1):
                        status_card.markdown('<div class="card"><div class="value win">STOP ATINGIDO</div></div>', unsafe_allow_html=True)
                        st.session_state.running = False; break

                    status_card.markdown('<div class="card"><div class="label">STATUS</div><div class="value" style="color:#58a6ff">ANALISANDO...</div></div>', unsafe_allow_html=True)
                    
                    lista, _ = catag(api)
                    dados = next((item for item in lista if item[0] == estrat_alvo and (float(item[2]) >= 90 if filtro_90 else True)), None)
                    
                    if not dados:
                        info_op.markdown('<div class="card"><div class="value warning">BUSCANDO PAR...</div></div>', unsafe_allow_html=True)
                        time.sleep(10); continue

                    par, assertividade = dados[1], dados[2]
                    while st.session_state.running and api.check_connect():
                        ts = api.get_server_timestamp()
                        minutos = float(datetime.fromtimestamp(ts).strftime('%M.%S'))
                        info_op.markdown(f'<div class="card"><div class="label">{par} ({assertividade}%)</div><div class="value" style="color:#f1c40f">⏰ {minutos:.2f}</div></div>', unsafe_allow_html=True)

                        entrar = False
                        if estrat_alvo == "MHI": entrar = (minutos >= 4.58 and minutos <= 5.00) or (minutos >= 9.58)
                        elif estrat_alvo == "Torres Gêmeas": entrar = (minutos >= 3.58 and minutos <= 4.00) or (minutos >= 8.58)
                        elif estrat_alvo == "MHI M5": entrar = (minutos >= 29.58 or minutos >= 59.58)

                        if entrar:
                            tf = 5 if "M5" in estrat_alvo else 1
                            velas = api.get_candles(par, tf * 60, 4, ts)
                            cores = ['Verde' if v['open'] < v['close'] else 'Vermelha' for v in velas]
                            direcao = 'put' if cores.count('Verde') > cores.count('Vermelha') else 'call'
                            
                            valor = valor_entrada
                            for g in range(int(n_gales) + 1):
                                if not st.session_state.running: break
                                status_card.markdown(f'<div class="card"><div class="value warning">GALE {g}</div></div>', unsafe_allow_html=True)
                                ok, id_op = api.buy_digital_spot_v2(par, valor, direcao, tf)
                                if ok:
                                    while st.session_state.running:
                                        s, r = api.check_win_digital_v2(id_op)
                                        if s: break
                                        info_op.markdown('<div class="card"><div class="value" style="color:#58a6ff">PROCESSANDO...</div></div>', unsafe_allow_html=True)
                                        time.sleep(1)
                                    st.session_state.lucro_total += round(r, 2)
                                    if r > 0: break
                                    else: valor *= fator_gale if g < n_gales else 1
                            break
                        time.sleep(0.5)
                except: time.sleep(2)
        else: st.error("Falha na conexão IQ Option.")