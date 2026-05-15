import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
import bcrypt

st.set_page_config(
    page_title="Chamados LegalOne - Molina",
    layout="wide",
    page_icon="⚖️"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

query_params = st.query_params
modo_tv = query_params.get("tv", "0") == "1"


# =========================
# FUNÇÕES
# =========================

def verificar_senha(senha_digitada, senha_salva):
    if senha_salva and senha_salva.startswith("$2b$"):
        return bcrypt.checkpw(
            senha_digitada.encode("utf-8"),
            senha_salva.encode("utf-8")
        )
    return senha_digitada == senha_salva


def fazer_login(email, senha):

    try:
        response = supabase.table("usuarios_painel") \
            .select("*") \
            .eq("email", email) \
            .execute()

        st.write("DEBUG:")
        st.write(response.data)

        if response.data:
            usuario = response.data[0]

            senha_salva = usuario.get(
                "senha_hash",
                ""
            )

            if verificar_senha(
                senha,
                senha_salva
            ):
                return usuario

        return None

    except Exception as e:
        st.error("ERRO REAL:")
        st.code(str(e))
        return None

def carregar_chamados():
    response = supabase.table("chamados") \
        .select("*") \
        .eq("setor", "LegalOne") \
        .order("criado_em", desc=True) \
        .execute()

    return pd.DataFrame(response.data)


def calcular_sla(row):
    prioridade = row.get("prioridade", "Média")
    status = row.get("status", "Aberto")
    criado_em = row.get("criado_em")

    if status in ["Finalizado", "Cancelado"]:
        return "Concluído"

    if pd.isna(criado_em):
        return "Sem data"

    prazos = {
        "Urgente": 1,
        "Alta": 4,
        "Média": 24,
        "Baixa": 72
    }

    prazo_final = criado_em + timedelta(hours=prazos.get(prioridade, 24))
    agora = datetime.now(timezone.utc)

    if prazo_final < agora:
        return "Atrasado"

    return "No prazo"


def criar_protocolo(chamado_id):
    return f"CH-{chamado_id:05d}"


# =========================
# LOGIN
# =========================

if "logado" not in st.session_state:
    st.session_state.logado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = {}

if not st.session_state.logado:
    st.title("🔐 Login - Chamados LegalOne")

    with st.form("login_form"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

        if entrar:
            usuario_login = fazer_login(email, senha)

            if usuario_login:
                st.session_state.logado = True
                st.session_state.usuario = usuario_login
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

    st.stop()

usuario = st.session_state.usuario


# =========================
# MODO TV / MENU
# =========================

if modo_tv:
    st_autorefresh(interval=30000, key="tvrefresh_legalone")

    st.markdown("""
    <style>
    section[data-testid="stSidebar"]{display:none;}
    header{display:none;}
    footer{visibility:hidden;}
    #MainMenu{visibility:hidden;}
    .block-container{padding-top:1rem; max-width:100%;}
    </style>
    """, unsafe_allow_html=True)

    menu = "TV Operacional"

else:
    st.sidebar.title("⚖️ Chamados LegalOne")
    st.sidebar.success(f"👤 {usuario.get('nome', 'Usuário')}")
    st.sidebar.write(f"Perfil: {usuario.get('perfil', 'LegalOne')}")

    if st.sidebar.button("🚪 Sair"):
        st.session_state.logado = False
        st.session_state.usuario = {}
        st.rerun()

    menu = st.sidebar.radio(
        "Menu",
        [
            "Abrir Chamado",
            "Painel Geral",
            "TV Operacional",
            "Relatórios",
            "Atualizar Chamado",
            "Gerenciar Usuários"
        ]
    )


# =========================
# ABRIR CHAMADO
# =========================

if menu == "Abrir Chamado":
    st.title("➕ Abrir Chamado LegalOne")

    with st.form("form_chamado_legalone"):
        col1, col2 = st.columns(2)

        with col1:
            solicitante = st.text_input(
                "Nome do solicitante",
                value=usuario.get("nome", "")
            )

            email_solicitante = st.text_input(
                "E-mail",
                value=usuario.get("email", "")
            )

            unidade = st.text_input(
                "Unidade",
                value=usuario.get("unidade") or "LegalOne"
            )

        with col2:
            categoria = st.selectbox(
                "Categoria",
                [
                    "Prazo",
                    "Processo",
                    "Andamento",
                    "Tarefa",
                    "Documento",
                    "GED",
                    "Acesso",
                    "Relatório",
                    "Mesa de Trabalho",
                    "Sincronização",
                    "Cadastro",
                    "Contrato",
                    "Lentidão",
                    "Erro Geral"
                ]
            )

            prioridade = st.selectbox(
                "Prioridade",
                ["Baixa", "Média", "Alta", "Urgente"]
            )

            status = st.selectbox(
                "Status",
                ["Aberto", "Em andamento", "Aguardando", "Finalizado", "Cancelado"]
            )

        descricao = st.text_area("Descrição do chamado", height=160)

        enviar = st.form_submit_button("✅ Abrir chamado")

        if enviar:
            if not solicitante or not descricao:
                st.error("Preencha o solicitante e a descrição.")
            else:
                dados = {
                    "solicitante": solicitante,
                    "email_solicitante": email_solicitante,
                    "unidade": unidade,
                    "setor": "LegalOne",
                    "categoria": categoria,
                    "prioridade": prioridade,
                    "descricao": descricao,
                    "status": status,
                    "criado_em": datetime.now(timezone.utc).isoformat()
                }

                result = supabase.table("chamados").insert(dados).execute()

                chamado_id = result.data[0]["id"]
                protocolo = criar_protocolo(chamado_id)

                supabase.table("chamados") \
                    .update({"protocolo": protocolo}) \
                    .eq("id", chamado_id) \
                    .execute()

                st.success(f"Chamado LegalOne criado com sucesso! {protocolo}")


# =========================
# GERENCIAR USUÁRIOS
# =========================

elif menu == "Gerenciar Usuários":
    st.title("👥 Gerenciar Usuários")

    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")

    with col2:
        perfil = st.selectbox(
            "Perfil",
            ["Administrador", "Gestor", "Colaborador", "TV"]
        )

        setor = st.selectbox(
            "Setor",
            ["Agendamento", "Protocolo", "Análise", "Inicial", "TI"]
        )

        unidade = st.selectbox(
            "Unidade",
            ["Atrium", "Online", "Cidade Nova"]
        )

    if st.button("✅ Cadastrar usuário"):
        if not nome or not email or not senha:
            st.error("Preencha nome, e-mail e senha.")
            st.stop()

        dados = {
            "nome": nome,
            "email": email,
            "senha_hash": bcrypt.hashpw(
                senha.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8"),
            "perfil": perfil,
            "setor": setor,
            "unidade": unidade
        }

        try:
            supabase.table("usuarios_painel").insert(dados).execute()
            st.success("Usuário cadastrado com sucesso!")
        except Exception:
            st.error("E-mail já cadastrado ou erro ao salvar.")

    st.divider()
    st.subheader("📋 Usuários cadastrados")

    try:
        usuarios = supabase.table("usuarios_painel") \
            .select("id,nome,email,perfil,setor,unidade") \
            .order("nome") \
            .execute()

        df_usuarios = pd.DataFrame(usuarios.data)

        if df_usuarios.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            st.dataframe(
                df_usuarios,
                use_container_width=True,
                hide_index=True
            )

    except Exception:
        st.warning("Não foi possível carregar a lista de usuários.")


# =========================
# PAINEL GERAL
# =========================

elif menu == "Painel Geral":
    st.title("📊 Painel Geral - LegalOne")
    st.caption("Molina Advogados - Chamados Operacionais LegalOne")

    df = carregar_chamados()

    if df.empty:
        st.info("Nenhum chamado LegalOne encontrado.")
        st.stop()

    df["criado_em"] = pd.to_datetime(df["criado_em"], errors="coerce", utc=True)
    df["sla"] = df.apply(calcular_sla, axis=1)

    total = len(df)
    abertos = len(df[df["status"] == "Aberto"])
    andamento = len(df[df["status"] == "Em andamento"])
    finalizados = len(df[df["status"] == "Finalizado"])
    urgentes = len(df[df["prioridade"] == "Urgente"])
    atrasados = len(df[df["sla"] == "Atrasado"])

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Total", total)
    c2.metric("Abertos", abertos)
    c3.metric("Andamento", andamento)
    c4.metric("Finalizados", finalizados)
    c5.metric("Urgentes", urgentes)
    c6.metric("Atrasados", atrasados)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        resumo_categoria = (
            df.groupby("categoria")
            .size()
            .reset_index(name="quantidade")
            .sort_values("quantidade", ascending=False)
        )

        fig = px.bar(
            resumo_categoria,
            x="categoria",
            y="quantidade",
            text="quantidade",
            title="Chamados por Categoria"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        resumo_prioridade = (
            df.groupby("prioridade")
            .size()
            .reset_index(name="quantidade")
            .sort_values("quantidade", ascending=False)
        )

        fig = px.bar(
            resumo_prioridade,
            x="prioridade",
            y="quantidade",
            text="quantidade",
            title="Chamados por Prioridade"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Lista de chamados LegalOne")

    colunas = [
        "protocolo",
        "status",
        "prioridade",
        "sla",
        "categoria",
        "solicitante",
        "email_solicitante",
        "descricao",
        "criado_em"
    ]

    colunas_existentes = [c for c in colunas if c in df.columns]

    st.dataframe(
        df[colunas_existentes],
        use_container_width=True,
        hide_index=True
    )


# =========================
# TV OPERACIONAL
# =========================

elif menu == "TV Operacional":
    st.markdown("""
    <style>
    .main {background: #0f172a;}
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    .tv-header {
        background: linear-gradient(90deg, #111827, #1e293b);
        color: white;
        padding: 24px;
        border-radius: 22px;
        margin-bottom: 22px;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    }
    .tv-title {
        font-size: 48px;
        font-weight: 900;
    }
    .tv-subtitle {
        font-size: 22px;
        color: #cbd5e1;
        margin-top: 8px;
        font-weight: 700;
    }
    .tv-card {
        padding: 24px;
        border-radius: 22px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35);
        margin-bottom: 18px;
    }
    .tv-number {
        font-size: 58px;
        font-weight: 900;
        line-height: 1;
    }
    .tv-label {
        font-size: 21px;
        margin-top: 10px;
        font-weight: 800;
    }
    .card-total {background: linear-gradient(135deg, #2563eb, #1e40af);}
    .card-abertos {background: linear-gradient(135deg, #f97316, #c2410c);}
    .card-andamento {background: linear-gradient(135deg, #eab308, #a16207);}
    .card-urgentes {background: linear-gradient(135deg, #dc2626, #991b1b);}
    .card-atrasados {background: linear-gradient(135deg, #7f1d1d, #450a0a);}
    .card-finalizados {background: linear-gradient(135deg, #16a34a, #166534);}
    .section-title {
        color: white;
        font-size: 30px;
        font-weight: 900;
        margin-top: 16px;
        margin-bottom: 12px;
    }
    .alert-card {
        background: #fee2e2;
        color: #111827;
        padding: 18px;
        border-radius: 16px;
        margin-bottom: 12px;
        border-left: 10px solid #dc2626;
        font-size: 20px;
        font-weight: 700;
    }
    .last-card {
        background: #ffffff;
        color: #111827;
        padding: 14px;
        border-radius: 14px;
        margin-bottom: 10px;
        font-size: 18px;
        font-weight: 700;
        border-left: 8px solid #2563eb;
    }
    .ok-card {
        background: #dcfce7;
        color: #14532d;
        padding: 22px;
        border-radius: 16px;
        font-size: 24px;
        font-weight: 900;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    agora_tela = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    st.markdown(f"""
    <div class="tv-header">
        <div class="tv-title">⚖️ CENTRAL LEGALONE MOLINA</div>
        <div class="tv-subtitle">Chamados operacionais LegalOne • Atualizado em {agora_tela}</div>
    </div>
    """, unsafe_allow_html=True)

    df = carregar_chamados()

    if df.empty:
        st.markdown("""
        <div class="ok-card">
            Nenhum chamado LegalOne encontrado.
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    df["criado_em"] = pd.to_datetime(df["criado_em"], errors="coerce", utc=True)
    df["sla"] = df.apply(calcular_sla, axis=1)

    total = len(df)
    abertos = len(df[df["status"] == "Aberto"])
    andamento = len(df[df["status"] == "Em andamento"])
    finalizados = len(df[df["status"] == "Finalizado"])
    urgentes = len(df[df["prioridade"] == "Urgente"])
    atrasados = len(df[df["sla"] == "Atrasado"])

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    cards = [
        (col1, "Total", total, "card-total"),
        (col2, "Abertos", abertos, "card-abertos"),
        (col3, "Em andamento", andamento, "card-andamento"),
        (col4, "Urgentes", urgentes, "card-urgentes"),
        (col5, "Atrasados", atrasados, "card-atrasados"),
        (col6, "Finalizados", finalizados, "card-finalizados"),
    ]

    for col, label, number, css in cards:
        with col:
            st.markdown(f"""
            <div class="tv-card {css}">
                <div class="tv-number">{number}</div>
                <div class="tv-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    colg1, colg2 = st.columns(2)

    with colg1:
        st.markdown('<div class="section-title">📌 Ranking por Categoria</div>', unsafe_allow_html=True)

        ranking_categoria = (
            df.groupby("categoria")
            .size()
            .reset_index(name="quantidade")
            .sort_values("quantidade", ascending=False)
            .head(8)
        )

        fig = px.bar(
            ranking_categoria,
            x="categoria",
            y="quantidade",
            text="quantidade"
        )

        fig.update_layout(
            paper_bgcolor="#0f172a",
            plot_bgcolor="#111827",
            font=dict(color="white", size=18),
            xaxis=dict(title="", tickfont=dict(size=16, color="white")),
            yaxis=dict(title="Quantidade", tickfont=dict(size=16, color="white")),
            margin=dict(l=20, r=20, t=30, b=20),
            height=420
        )

        fig.update_traces(
            textfont_size=18,
            textfont_color="white",
            textposition="outside",
            cliponaxis=False
        )

        st.plotly_chart(fig, use_container_width=True)

    with colg2:
        st.markdown('<div class="section-title">🚨 Chamados Críticos</div>', unsafe_allow_html=True)

        df_criticos = df[
            (df["sla"] == "Atrasado") |
            (df["prioridade"] == "Urgente")
        ].head(6)

        if df_criticos.empty:
            st.markdown("""
            <div class="ok-card">
                Nenhum chamado crítico no momento.
            </div>
            """, unsafe_allow_html=True)
        else:
            for _, row in df_criticos.iterrows():
                st.markdown(f"""
                <div class="alert-card">
                    <b>{row.get("protocolo", "")}</b> • {row.get("prioridade", "")} • {row.get("sla", "")}<br>
                    <b>Categoria:</b> {row.get("categoria", "")}<br>
                    <b>Descrição:</b> {row.get("descricao", "")}
                </div>
                """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">🕒 Últimos Chamados</div>', unsafe_allow_html=True)

    for _, row in df.head(6).iterrows():
        st.markdown(f"""
        <div class="last-card">
            <b>{row.get("protocolo", "")}</b> • {row.get("status", "")} • {row.get("prioridade", "")}<br>
            <b>{row.get("categoria", "")}</b><br>
            {row.get("descricao", "")}
        </div>
        """, unsafe_allow_html=True)


# =========================
# RELATÓRIOS
# =========================

elif menu == "Relatórios":
    st.title("📄 Relatórios LegalOne")

    df = carregar_chamados()

    if df.empty:
        st.info("Nenhum chamado LegalOne encontrado.")
        st.stop()

    df["criado_em"] = pd.to_datetime(df["criado_em"], errors="coerce", utc=True)
    df["sla"] = df.apply(calcular_sla, axis=1)
    df["data"] = df["criado_em"].dt.date

    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input("Data inicial", value=df["data"].min())

    with col2:
        data_fim = st.date_input("Data final", value=df["data"].max())

    with col3:
        status_filtro = st.multiselect(
            "Status",
            sorted(df["status"].dropna().unique()),
            default=list(df["status"].dropna().unique())
        )

    col4, col5 = st.columns(2)

    with col4:
        categoria_filtro = st.multiselect(
            "Categoria",
            sorted(df["categoria"].dropna().unique()),
            default=list(df["categoria"].dropna().unique())
        )

    with col5:
        prioridade_filtro = st.multiselect(
            "Prioridade",
            sorted(df["prioridade"].dropna().unique()),
            default=list(df["prioridade"].dropna().unique())
        )

    df_relatorio = df[
        (df["data"] >= data_inicio) &
        (df["data"] <= data_fim) &
        (df["status"].isin(status_filtro)) &
        (df["categoria"].isin(categoria_filtro)) &
        (df["prioridade"].isin(prioridade_filtro))
    ]

    st.divider()
    st.metric("Total filtrado", len(df_relatorio))

    st.subheader("Resumo por categoria")

    resumo = (
        df_relatorio.groupby("categoria")
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )

    st.dataframe(resumo, use_container_width=True, hide_index=True)

    st.subheader("Chamados do relatório")

    colunas = [
        "protocolo",
        "status",
        "prioridade",
        "sla",
        "categoria",
        "solicitante",
        "email_solicitante",
        "descricao",
        "criado_em"
    ]

    colunas_existentes = [c for c in colunas if c in df_relatorio.columns]

    st.dataframe(
        df_relatorio[colunas_existentes],
        use_container_width=True,
        hide_index=True
    )

    csv = df_relatorio[colunas_existentes].to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar relatório CSV",
        data=csv,
        file_name="relatorio_legalone.csv",
        mime="text/csv"
    )


# =========================
# ATUALIZAR CHAMADO
# =========================

elif menu == "Atualizar Chamado":
    st.title("✏️ Atualizar Chamado LegalOne")

    df = carregar_chamados()

    if df.empty:
        st.info("Nenhum chamado LegalOne encontrado.")
        st.stop()

    df["opcao"] = (
        df["protocolo"].fillna(df["id"].astype(str))
        + " - "
        + df["descricao"].fillna("").str[:60]
    )

    opcao = st.selectbox("Selecione o chamado", df["opcao"].tolist())

    chamado = df[df["opcao"] == opcao].iloc[0]

    st.info(f"Descrição: {chamado.get('descricao', '')}")

    novo_status = st.selectbox(
        "Novo status",
        ["Aberto", "Em andamento", "Aguardando", "Finalizado", "Cancelado"],
        index=0
    )

    responsavel = st.text_input(
        "Responsável",
        value=chamado.get("responsavel") or ""
    )

    observacoes = st.text_area(
        "Observações",
        value=chamado.get("observacoes") or ""
    )

    if st.button("💾 Salvar alteração"):
        dados_update = {
            "status": novo_status,
            "responsavel": responsavel,
            "observacoes": observacoes,
            "atualizado_em": datetime.now(timezone.utc).isoformat()
        }

        if novo_status == "Finalizado":
            dados_update["finalizado_em"] = datetime.now(timezone.utc).isoformat()

        supabase.table("chamados") \
            .update(dados_update) \
            .eq("id", int(chamado["id"])) \
            .execute()

        st.success("Chamado LegalOne atualizado com sucesso.")
        st.rerun()
