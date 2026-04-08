import queue
import threading
import time
import json
import os
import secrets
from datetime import datetime, date

import streamlit as st

from bot import BinaryBot, load_config


# -----------------------------------------------------------------------------
# Estilo
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Nexus Binary Bot", page_icon="💹", layout="wide")

st.markdown(
    """
    <style>
    body {
        background: radial-gradient(120% 120% at 20% 20%, #0f1624 0%, #05080f 60%, #020409 100%);
        color: #eef3ff;
    }
    .big-title {
        font-size: 32px;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(90deg, #7ddcfe 0%, #b46bff 50%, #f6d365 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .sub {
        font-size: 15px;
        color: #aeb8d4;
    }
    .card {
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.04);
        box-shadow: 0 20px 80px rgba(0,0,0,0.35);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Estado
# -----------------------------------------------------------------------------
if "logs" not in st.session_state:
    st.session_state.logs = []
if "log_queue_obj" not in st.session_state:
    st.session_state.log_queue_obj = queue.Queue(maxsize=500)
if "bot_thread" not in st.session_state:
    st.session_state.bot_thread = None
if "bot_obj" not in st.session_state:
    st.session_state.bot_obj = None
if "running" not in st.session_state:
    st.session_state.running = False
if "saved" not in st.session_state:
    st.session_state.saved = {}
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "license_key" not in st.session_state:
    st.session_state.license_key = None
if "license_record" not in st.session_state:
    st.session_state.license_record = None


def enqueue_log(msg: str, queue_target=None):
    """Enfileira mensagem no buffer de log; aceita fila externa para uso em threads."""
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        lower = msg.lower()
        if "erro" in lower or "error" in lower:
            icon = "⚠️"
        elif "stop" in lower:
            icon = "⛔"
        elif "win" in lower:
            icon = "✅"
        elif "loss" in lower:
            icon = "❌"
        elif "melhor par" in lower or "assertividade" in lower:
            icon = "🎯"
        elif "catalog" in lower or "cataloga" in lower:
            icon = "🧭"
        else:
            icon = "ℹ️"

        target = queue_target or st.session_state.log_queue_obj
        target.put_nowait(f"{icon} {ts} | {msg}")
    except queue.Full:
        pass


# -----------------------------------------------------------------------------
# Supabase client
# -----------------------------------------------------------------------------
def get_supabase_client():
    default_url = "https://wtsuborthuxxdxjruovt.supabase.co"
    default_key = "sb_publishable_H5Tz0TiVQqMc_m8zqpruEg_H4AtYrwU"
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"].get("url", default_url)
            key = st.secrets["supabase"].get("key", default_key)
        else:
            url = os.environ.get("SUPABASE_URL", default_url)
            key = os.environ.get("SUPABASE_KEY", default_key)
    except Exception:
        url = os.environ.get("SUPABASE_URL", default_url)
        key = os.environ.get("SUPABASE_KEY", default_key)

    if not url or not key:
        return None, "Configure SUPABASE_URL e SUPABASE_KEY (ou st.secrets['supabase'])."
    try:
        from supabase import create_client
    except Exception:
        return None, "Instale o cliente: pip install supabase"
    try:
        client = create_client(url, key)
        return client, None
    except Exception as e:
        return None, f"Erro ao criar cliente Supabase: {e}"


def flush_queue():
    log_q = st.session_state.log_queue_obj
    while not log_q.empty():
        try:
            st.session_state.logs.append(log_q.get_nowait())
        except queue.Empty:
            break
    st.session_state.logs = st.session_state.logs[-500:]  # limita log


def stop_bot():
    bot: BinaryBot = st.session_state.bot_obj
    if bot:
        bot.stop()
    th = st.session_state.bot_thread
    if th and th.is_alive():
        th.join(timeout=0.1)
    st.session_state.running = False
    st.session_state.bot_thread = None
    st.session_state.bot_obj = None


# -----------------------------------------------------------------------------
# Conteúdo principal
# -----------------------------------------------------------------------------
col1, col2 = st.columns([2, 1])
with col1:
    st.markdown('<div class="big-title">Nexus Binary Bot</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Automatize MHI, Torres Gêmeas e MHI M5 com recatalogação inteligente e monitor em tempo real.</div>', unsafe_allow_html=True)
with col2:
    st.markdown("")

cfg = load_config()
defaults = {
    "LOGIN": {"email": "", "senha": ""},
    "AJUSTES": {
        "valor_entrada": 2,
        "tipo": "digital",
        "stop_win": 100,
        "stop_loss": 50,
        "analise_medias": "N",
        "velas_medias": 10,
    },
    "MARTINGALE": {"usar_martingale": "N", "niveis_martingale": 0, "fator_martingale": 2.0},
    "SOROS": {"usar_soros": "N", "niveis_soros": 0},
}

for sec, vals in defaults.items():
    if sec not in cfg:
        cfg[sec] = {}
    for k, v in vals.items():
        if k not in cfg[sec] or str(cfg[sec][k]).strip() == "":
            cfg[sec][k] = v


def cfg_float(sec, key):
    try:
        return float(cfg[sec][key])
    except Exception:
        return float(defaults[sec][key])


def cfg_int(sec, key):
    try:
        return int(cfg[sec][key])
    except Exception:
        return int(defaults[sec][key])


def cfg_str(sec, key):
    val = str(cfg[sec][key]) if key in cfg[sec] else str(defaults[sec][key])
    return val


def read_cache(key: str, fallback):
    return st.session_state.saved.get(key, fallback)


# -----------------------------------------------------------------------------
# Supabase helpers
# -----------------------------------------------------------------------------
supabase, supa_err = get_supabase_client()


def fetch_user_settings(email: str):
    if not supabase or not email:
        return {}
    try:
        resp = supabase.table("user_settings").select("data").eq("email", email).execute()
        if resp.data:
            return resp.data[0].get("data", {}) or {}
    except Exception as e:
        st.error(f"Erro ao buscar configurações: {e}")
    return {}


def save_user_settings(email: str, data: dict):
    if not supabase or not email:
        return False, "Supabase não configurado"
    try:
        supabase.table("user_settings").upsert(
            {"email": email, "data": data, "updated_at": datetime.utcnow().isoformat()}
        ).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def fetch_license(key: str):
    if not supabase:
        return None
    try:
        resp = supabase.table("licenses").select("*").eq("license_key", key).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        st.error(f"Erro Supabase licenses: {e}")
    return None


def license_status_record(record: dict, email: str):
    if not record:
        return False, "Licença não encontrada"
    exp = record.get("expires_at")
    if exp:
        try:
            if date.fromisoformat(exp[:10]) < date.today():
                return False, "Licença expirada"
        except Exception:
            return False, "Data de expiração inválida"
    status = (record.get("status") or "").lower()
    if status and status not in ("active", "ativa", "valid"):
        return False, f"Licença com status '{status}'"
    bound = (record.get("device_id") or "").strip()
    if bound and bound != email:
        return False, "Licença já vinculada a outro email"
    return True, ""


def login_form():
    if not supabase:
        st.error(supa_err or "Configure Supabase para autenticar.")
        st.stop()
    st.subheader("Ativar / Entrar")
    with st.form("login_form"):
        email_in = st.text_input("Email", key="login_email")
        lic = st.text_input("Licença", key="login_lic")
        submit = st.form_submit_button("Validar")
    if submit:
        lic_rec = fetch_license(lic)
        if not lic_rec:
            st.error("Licença inválida.")
            return
        ok, msg = license_status_record(lic_rec, email_in)
        if not ok:
            st.error(f"Licença inválida: {msg}")
            return
        if not lic_rec.get("device_id"):
            try:
                supabase.table("licenses").update({"device_id": email_in}).eq("id", lic_rec["id"]).execute()
                lic_rec["device_id"] = email_in
            except Exception as e:
                st.error(f"Erro ao vincular email: {e}")
                return
        st.session_state.user_email = email_in
        st.session_state.license_key = lic_rec.get("license_key")
        st.session_state.license_record = lic_rec
        st.session_state.saved = fetch_user_settings(email_in) or {}
        enqueue_log(f"Licença validada para {email_in}")
        st.success("Licença ativa")
        st.rerun()


# Gate de autenticação
if not st.session_state.user_email:
    login_form()
    st.stop()

# Checagem única de licença
if supabase:
    lic_rec = fetch_license(st.session_state.license_key or "")
    st.session_state.license_record = lic_rec
    ok_license, msg_license = license_status_record(lic_rec, st.session_state.user_email or "")
    if not ok_license:
        st.session_state.user_email = None
        st.session_state.license_key = None
        st.warning(f"Licença inválida: {msg_license}")
        st.stop()
else:
    st.error(supa_err or "Configure Supabase para usar o sistema de contas.")
    st.stop()

st.success(f"Licença ativa: {st.session_state.license_key}")

# carrega settings do usuário se ainda não estiverem na sessão
if st.session_state.user_email and supabase:
    if not st.session_state.saved:
        st.session_state.saved = fetch_user_settings(st.session_state.user_email) or st.session_state.saved

with st.sidebar:
    st.markdown("### Conta & Autenticação")
    email = st.text_input("Email IQ Option", value=read_cache("email", ""))
    senha = st.text_input("Senha", value=read_cache("senha", ""), type="password")
    conta_default = 0 if read_cache("conta", "DEMO").upper() == "DEMO" else 1
    conta = st.radio("Tipo de conta", options=["DEMO", "REAL"], index=conta_default, horizontal=True)

    st.markdown("### Estratégia")
    estrategia = st.selectbox("Selecione", ["MHI M1", "Torres Gêmeas", "MHI M5"])
    tipo_exec = st.selectbox("Tipo de entrada", ["automatico", "digital", "binary"], index=0)

    st.markdown("### Gerenciamento")
    valor_entrada = st.number_input(
        "Valor por entrada", min_value=0.5, value=read_cache("valor_entrada", cfg_float("AJUSTES", "valor_entrada")), step=0.5
    )
    stop_win = st.number_input(
        "Stop Win", min_value=1.0, value=read_cache("stop_win", cfg_float("AJUSTES", "stop_win")), step=1.0
    )
    stop_loss = st.number_input(
        "Stop Loss", min_value=1.0, value=read_cache("stop_loss", cfg_float("AJUSTES", "stop_loss")), step=1.0
    )
    recatalog = st.slider("Recatalogar a cada (min)", min_value=5, max_value=30, value=read_cache("recatalog", 10), step=1)

    st.markdown("### Martingale & Soros")
    usar_mg = st.checkbox("Usar Martingale", value=read_cache("usar_mg", cfg_str("MARTINGALE", "usar_martingale").upper() == "S"))
    niveis_mg = st.slider(
        "Níveis Martingale", 0, 3, read_cache("niveis_mg", cfg_int("MARTINGALE", "niveis_martingale")), disabled=not usar_mg
    )
    fator_mg = st.number_input(
        "Fator Martingale",
        min_value=1.1,
        max_value=5.0,
        value=read_cache("fator_mg", cfg_float("MARTINGALE", "fator_martingale")),
        step=0.1,
        disabled=not usar_mg,
    )

    usar_soros = st.checkbox("Usar Soros", value=read_cache("usar_soros", cfg_str("SOROS", "usar_soros").upper() == "S"))
    niveis_soros = st.slider(
        "Níveis Soros", 0, 3, read_cache("niveis_soros", cfg_int("SOROS", "niveis_soros")), disabled=not usar_soros
    )

    st.markdown("### Filtro de tendência")
    analise_medias = st.checkbox(
        "Confirmar por médias móveis", value=read_cache("analise_medias", cfg_str("AJUSTES", "analise_medias").upper() == "S")
    )
    velas_medias = st.slider("Velas para média", 5, 50, read_cache("velas_medias", cfg_int("AJUSTES", "velas_medias")))

    start_btn = st.button("🚀 Iniciar bot", type="primary", disabled=st.session_state.running)
    stop_btn = st.button("⏹ Parar bot", disabled=not st.session_state.running)
    save_btn = st.button("💾 Salvar configurações na conta", disabled=not st.session_state.user_email)

if start_btn:
    stop_bot()  # garante limpeza anterior
    estrategia_key = estrategia.lower().replace(" ", "_")

    log_queue_obj = st.session_state.log_queue_obj  # referência concreta, para não acessar session_state na thread

    def push_log_threadsafe(msg: str):
        enqueue_log(msg, queue_target=log_queue_obj)

    bot = BinaryBot(
        email=email,
        senha=senha,
        conta=conta,
        estrategia=estrategia_key,
        valor_entrada=valor_entrada,
        stop_win=stop_win,
        stop_loss=stop_loss,
        analise_medias=analise_medias,
        velas_medias=velas_medias,
        martingale_levels=niveis_mg if usar_mg else 0,
        fator_mg=fator_mg,
        usar_soros=usar_soros,
        niveis_soros=niveis_soros,
        recatalog_minutes=recatalog,
        log_fn=push_log_threadsafe,
    )

    def runner():
        bot.run(tipo_preferido=tipo_exec)

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    st.session_state.bot_thread = th
    st.session_state.bot_obj = bot
    st.session_state.running = True
    enqueue_log("Bot iniciado.")

if stop_btn:
    stop_bot()
    enqueue_log("Bot parado pelo usuário.")

# Salvar configurações no Supabase
if save_btn and st.session_state.user_email:
    payload = {
        "email": email,
        "senha": senha,
        "conta": conta,
        "valor_entrada": valor_entrada,
        "stop_win": stop_win,
        "stop_loss": stop_loss,
        "recatalog": recatalog,
        "usar_mg": usar_mg,
        "niveis_mg": niveis_mg,
        "fator_mg": fator_mg,
        "usar_soros": usar_soros,
        "niveis_soros": niveis_soros,
        "analise_medias": analise_medias,
        "velas_medias": velas_medias,
        "estrategia": estrategia,
        "tipo_exec": tipo_exec,
    }
    ok_save, err_save = save_user_settings(st.session_state.user_email, payload)
    if ok_save:
        st.session_state.saved = payload
        st.success("Configurações salvas na conta.")
    else:
        st.error(f"Não foi possível salvar: {err_save}")

# Persistência em sessão (associada ao cookie do navegador)
st.session_state.saved = {
    "email": email,
    "senha": senha,
    "conta": conta,
    "valor_entrada": valor_entrada,
    "stop_win": stop_win,
    "stop_loss": stop_loss,
    "recatalog": recatalog,
    "usar_mg": usar_mg,
    "niveis_mg": niveis_mg,
    "fator_mg": fator_mg,
    "usar_soros": usar_soros,
    "niveis_soros": niveis_soros,
    "analise_medias": analise_medias,
    "velas_medias": velas_medias,
}

# -----------------------------------------------------------------------------
# Painéis
# -----------------------------------------------------------------------------
flush_queue()

stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
with stats_col1:
    st.markdown('<div class="card">Status<br><b>{}</b></div>'.format("Rodando" if st.session_state.running else "Parado"), unsafe_allow_html=True)
with stats_col2:
    lucro = st.session_state.bot_obj.lucro_total if st.session_state.bot_obj else 0.0
    st.markdown(f'<div class="card">Lucro acumulado<br><b>{lucro:+.2f}</b></div>', unsafe_allow_html=True)
with stats_col3:
    par = st.session_state.bot_obj.current_pair if st.session_state.bot_obj else "--"
    st.markdown(f'<div class="card">Par atual<br><b>{par}</b></div>', unsafe_allow_html=True)
with stats_col4:
    streak = st.session_state.bot_obj.loss_streak if st.session_state.bot_obj else 0
    st.markdown(f'<div class="card">Loss seguidos<br><b>{streak}</b></div>', unsafe_allow_html=True)

st.markdown("### Log em tempo real")
log_text = "\n".join(st.session_state.logs[-200:])
st.text_area("Log", value=log_text, height=320, label_visibility="collapsed")

st.caption("Atualização automática a cada 2s enquanto o bot está rodando.")
if st.session_state.running:
    time.sleep(2)
    st.rerun()
