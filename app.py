import streamlit as st
import time
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÕES DO SUPABASE ---
SUPABASE_URL = "https://wtsuborthuxxdxjruovt.supabase.co"
SUPABASE_KEY = "sb_publishable_H5Tz0TiVQqMc_m8zqpruEg_H4AtYrwU"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- IMPORTAÇÃO DA API LOCAL E FUNÇÕES ---
from iqoptionapi.stable_api import IQ_Option
# Correção: Importando a função 'catag' do arquivo catalogador.py
from catalogador import catag 

# --- FUNÇÕES DE BANCO DE DADOS (SUPABASE) ---
def load_users():
    try:
        response = supabase.table("usuarios").select("*").execute()
        return {u['email']: u for u in response.data}
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return {}

def save_new_user(email, nome, senha):
    data = {"email": email, "nome": nome, "senha": senha, "aprovado": False}
    try:
        supabase.table("usuarios").insert(data).execute()
        return True
    except:
        return False

def approve_user(email):
    try:
        supabase.table("usuarios").update({"aprovado": True}).eq("email", email).execute()
        return True
    except:
        return False

# --- INTERFACE ---
st.set_page_config(page_title="SNIPER BOT PRO", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

users = load_users()

if not st.session_state.logged_in:
    st.title("🎯 SNIPER BOT - LOGIN")
    tab_login, tab_cadastro = st.tabs(["Entrar", "Solicitar Acesso"])
    
    with tab_login:
        email_input = st.text_input("E-mail")
        pass_input = st.text_input("Senha", type="password")
        if st.button("Acessar Painel"):
            if email_input in users:
                if users[email_input]['senha'] == pass_input:
                    if users[email_input]['aprovado']:
                        st.session_state.logged_in = True
                        st.session_state.user_email = email_input
                        st.rerun()
                    else:
                        st.warning("Aguarde a aprovação do administrador.")
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado.")
                
    with tab_cadastro:
        new_nome = st.text_input("Seu Nome")
        new_email = st.text_input("Seu melhor E-mail")
        new_pass = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            if new_email and new_pass and new_nome:
                if new_email not in users:
                    if save_new_user(new_email, new_nome, new_pass):
                        st.success("Solicitação enviada!")
                    else:
                        st.error("Erro ao salvar no banco de dados.")
                else:
                    st.warning("E-mail já cadastrado.")

else:
    st.sidebar.title(f"Olá, {users[st.session_state.user_email]['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()

    menu = ["Operações", "Catalogador"]
    if st.session_state.user_email == "jovanegarcia94@gmail.com":
        menu.append("🔑 PAINEL ADMIN")
    
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "🔑 PAINEL ADMIN":
        st.header("Gerenciar Acessos")
        users_list = load_users()
        for email, info in users_list.items():
            if not info.get('aprovado', False):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{info['nome']}** ({email})")
                if col2.button("Aprovar", key=email):
                    if approve_user(email):
                        st.success(f"{info['nome']} aprovado!")
                        st.rerun()

    elif choice == "Operações":
        st.header("Painel de Operações")
        st.info("Configure os parâmetros abaixo.")
        with st.expander("Configurações de Banca"):
            valor_entrada = st.number_input("Valor da Entrada ($)", value=10.0)
            stop_loss = st.number_input("Stop Loss ($)", value=50.0)
            stop_win = st.number_input("Stop Win ($)", value=100.0)
        
        if st.button("🚀 INICIAR ROBÔ"):
            st.write("A iniciar conexão...")
            # Aqui você poderá adicionar a lógica para chamar o robô
            st.warning("Lógica de execução pronta para ser integrada.")

    elif choice == "Catalogador":
        st.header("Catalogador de Ciclos")
        if st.button("Analisar Mercado Agora"):
            st.warning("Para analisar, o robô precisa de uma conexão ativa com a IQ Option.")
            # Exemplo de como a sua função 'catag' será chamada:
            # resultados, linha = catag(API_CONECTADA)
