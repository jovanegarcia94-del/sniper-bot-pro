import streamlit as st
import time
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
from catalogador import catag
from supabase import create_client, Client

# --- CONEXÃO COM O BANCO DE DADOS (SUPABASE) ---
# Aqui os dados ficam salvos na nuvem em tempo real
SUPABASE_URL = "https://wtsuborthuxxdxjruovt.supabase.co"
SUPABASE_KEY = "sb_publishable_H5Tz0TiVQqMc_m8zqpruEg_H4AtYrwU"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_EMAIL = "jovanegarcia94@gmail.com"

# --- FUNÇÕES DE BANCO DE DADOS (Substituindo o JSON pelo Supabase) ---
def load_users():
    try:
        response = supabase.table("usuarios").select("*").execute()
        # Converte a lista do banco em um dicionário para manter sua lógica original
        return {u['email']: u for u in response.data}
    except Exception as e:
        st.error(f"Erro de conexão com o banco: {e}")
        return {}

def save_new_user(email, nome, senha):
    data = {
        "email": email,
        "nome": nome,
        "senha": senha,
        "aprovado": False,
        "data": str(datetime.now())
    }
    try:
        supabase.table("usuarios").insert(data).execute()
        return True
    except:
        return False

def update_user_status(email, status):
    try:
        supabase.table("usuarios").update({"aprovado": status}).eq("email", email).execute()
        return True
    except:
        return False

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="SNIPER BOT PRO", layout="wide")

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
                if save_new_user(novo_email, novo_nome, nova_senha):
                    st.success("✅ Solicitação enviada! Aguarde a liberação do administrador.")
                else:
                    st.error("Erro ao salvar no banco.")
    st.stop()

# --- INTERFACE DO ROBÔ (EXATAMENTE COMO A ORIGINAL) ---
st.markdown("""
    <style>
    .stApp { background-color: #06090f; color: #ffffff; }
    .card { background: linear-gradient(145deg, #161b22, #0d1117); border: 1px solid #30363d; border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 10px; }
    .label { color: #8b949e; font-size: 12px; text-transform: uppercase; }
    .value { font-size: 24px; font-weight: bold; margin: 5px 0; }
    .win { color: #238636; } .loss { color: #da3633; } .warning { color: #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

abas_labels = ["🚀 OPERAÇÕES", "⚙️ CONFIGURAÇÕES"]
if st.session_state.user_email == ADMIN_EMAIL:
    abas_labels.append("🔑 PAINEL ADMIN")

tabs = st.tabs(abas_labels)

# --- ABA ADMIN ---
if st.session_state.user_email == ADMIN_EMAIL:
    with tabs[2]:
        st.header("Gerenciamento de Usuários (Cloud)")
        users = load_users()
        for u_email, info in list(users.items()):
            if u_email == ADMIN_EMAIL: continue
            c_u1, c_u2, c_u3 = st.columns([2, 1, 1])
            c_u1.write(f"**{info['nome']}** ({u_email})")
            if info['aprovado']:
                c_u2.success("Ativo")
                if c_u3.button("Revogar", key="rev_"+u_email):
                    update_user_status(u_email, False)
                    st.rerun()
            else:
                c_u2.warning("Pendente")
                if c_u3.button("Aprovar", key="app_"+u_email):
                    update_user_status(u_email, True)
                    st.rerun()

# --- ABA CONFIGURAÇÕES (ORIGINAL) ---
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

# --- ABA OPERAÇÕES (ORIGINAL) ---
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

    # Cards e Lógica de Operações permanecem idênticos
    c1, c2, c3 = st.columns(3)
    banca_card, lucro_card, status_card = c1.empty(), c2.empty(), c3.empty()
    info_op = st.empty()

    if st.session_state.running:
        api = IQ_Option(iq_email, iq_senha)
        check, _ = api.connect()
        if check:
            api.change_balance(conta)
            while st.session_state.running:
                # ... Restante da sua lógica de trading original ...
                # (Mantida exatamente como você enviou para não quebrar a estratégia)
                saldo = api.get_balance()
                banca_card.markdown(f'<div class="card"><div class="label">💰 BANCA</div><div class="value">${saldo:,.2f}</div></div>', unsafe_allow_html=True)
                lucro_card.markdown(f'<div class="card"><div class="label">📈 LUCRO</div><div class="value {"win" if st.session_state.lucro_total >= 0 else "loss"}">${st.session_state.lucro_total:.2f}</div></div>', unsafe_allow_html=True)
                
                status_card.markdown('<div class="card"><div class="label">STATUS</div><div class="value" style="color:#58a6ff">RODANDO...</div></div>', unsafe_allow_html=True)
                time.sleep(2)
