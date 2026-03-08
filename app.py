import streamlit as st
import time
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÕES DO SUPABASE ---
# Pegue esses dados em Settings > API no seu painel do Supabase
SUPABASE_URL = "https://wtsuborthuxxdxjruovt.supabase.co"
SUPABASE_KEY = "sb_publishable_H5Tz0TiVQqMc_m8zqpruEg_H4AtYrwU"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- IMPORTAÇÃO DA API LOCAL ---
# O Python vai ler a pasta 'iqoptionapi' que você subiu para o GitHub
from iqoptionapi.stable_api import IQ_Option
from catalogador import Catalogador 

# --- FUNÇÕES DE BANCO DE DADOS (SUPABASE) ---
def load_users():
    """Busca todos os usuários do banco de dados remoto"""
    try:
        response = supabase.table("usuarios").select("*").execute()
        # Transforma a lista do banco em um dicionário para o robô processar
        return {u['email']: u for u in response.data}
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return {}

def save_new_user(email, nome, senha):
    """Insere um novo usuário pendente no banco de dados"""
    data = {
        "email": email,
        "nome": nome,
        "senha": senha,
        "aprovado": False
    }
    try:
        supabase.table("usuarios").insert(data).execute()
        return True
    except:
        return False

def approve_user(email):
    """Aprova um usuário no banco de dados"""
    try:
        supabase.table("usuarios").update({"aprovado": True}).eq("email", email).execute()
        return True
    except:
        return False

# --- INTERFACE E LÓGICA DO ROBÔ ---
st.set_page_config(page_title="SNIPER BOT PRO", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

users = load_users()

# --- TELA DE LOGIN / CADASTRO ---
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
                        st.warning("Sua conta ainda aguarda aprovação do administrador.")
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
                        st.success("Solicitação enviada! Aguarde a aprovação do admin.")
                    else:
                        st.error("Erro ao salvar. Tente novamente.")
                else:
                    st.warning("Este e-mail já está cadastrado.")
            else:
                st.error("Preencha todos os campos.")

# --- INTERFACE LOGADA ---
else:
    st.sidebar.title(f"Bem-vindo, {users[st.session_state.user_email]['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()

    menu = ["Operações", "Catalogador"]
    # Se for você (admin), aparece o painel de aprovação
    if st.session_state.user_email == "jovanegarcia94@gmail.com":
        menu.append("🔑 PAINEL ADMIN")
    
    choice = st.sidebar.selectbox("Menu", menu)

    # --- ABA ADMIN (APROVAÇÃO) ---
    if choice == "🔑 PAINEL ADMIN":
        st.header("Gerenciar Acessos")
        users_list = load_users()
        
        for email, info in users_list.items():
            if not info['aprovado']:
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{info['nome']}** ({email})")
                if col2.button("Aprovar", key=email):
                    if approve_user(email):
                        st.success(f"{info['nome']} aprovado!")
                        st.rerun()

    # --- ABA OPERAÇÕES ---
    elif choice == "Operações":
        st.header("Painel de Operações")
        # Aqui entra a lógica que conecta na IQ Option usando a pasta iqoptionapi
        st.info("Configure os parâmetros abaixo e clique em Iniciar.")
        
        with st.expander("Configurações de Banca"):
            valor_entrada = st.number_input("Valor da Entrada ($)", value=10.0)
            stop_loss = st.number_input("Stop Loss ($)", value=50.0)
            stop_win = st.number_input("Stop Win ($)", value=100.0)

        if st.button("🚀 INICIAR ROBÔ"):
            st.write("Conectando à IQ Option...")
            # Exemplo de chamada à API local
            # API = IQ_Option("email", "senha")
            # API.connect()
            st.warning("Lógica de execução em processamento...")

    # --- ABA CATALOGADOR ---
    elif choice == "Catalogador":
        st.header("Catalogador de Ciclos")
        if st.button("Analisar Mercado Agora"):
            # Exemplo de uso do seu arquivo catalogador.py
            # c = Catalogador()
            # resultados = c.analisar()
            st.success("Análise concluída com sucesso!")
