import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="Painel LegalOne - Molina",
    layout="wide",
    page_icon="⚖️"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


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


st.title("⚖️ Painel de Chamados LegalOne")
st.caption("Molina Advogados - Operacional LegalOne")

df = carregar_chamados()

if df.empty:
    st.info("Nenhum chamado LegalOne encontrado.")
    st.stop()

df["criado_em"] = pd.to_datetime(
    df["criado_em"],
    errors="coerce",
    utc=True
)

df["sla"] = df.apply(calcular_sla, axis=1)
df["data"] = df["criado_em"].dt.date

st.sidebar.title("Filtros")

status_filtro = st.sidebar.multiselect(
    "Status",
    sorted(df["status"].dropna().unique()),
    default=list(df["status"].dropna().unique())
)

categoria_filtro = st.sidebar.multiselect(
    "Categoria",
    sorted(df["categoria"].dropna().unique()),
    default=list(df["categoria"].dropna().unique())
)

prioridade_filtro = st.sidebar.multiselect(
    "Prioridade",
    sorted(df["prioridade"].dropna().unique()),
    default=list(df["prioridade"].dropna().unique())
)

df_filtrado = df[
    (df["status"].isin(status_filtro)) &
    (df["categoria"].isin(categoria_filtro)) &
    (df["prioridade"].isin(prioridade_filtro))
]

total = len(df_filtrado)
abertos = len(df_filtrado[df_filtrado["status"] == "Aberto"])
andamento = len(df_filtrado[df_filtrado["status"] == "Em andamento"])
finalizados = len(df_filtrado[df_filtrado["status"] == "Finalizado"])
urgentes = len(df_filtrado[df_filtrado["prioridade"] == "Urgente"])
atrasados = len(df_filtrado[df_filtrado["sla"] == "Atrasado"])

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
        df_filtrado.groupby("categoria")
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )

    fig_categoria = px.bar(
        resumo_categoria,
        x="categoria",
        y="quantidade",
        text="quantidade",
        title="Chamados por Categoria"
    )

    st.plotly_chart(fig_categoria, use_container_width=True)

with col2:
    resumo_prioridade = (
        df_filtrado.groupby("prioridade")
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )

    fig_prioridade = px.bar(
        resumo_prioridade,
        x="prioridade",
        y="quantidade",
        text="quantidade",
        title="Chamados por Prioridade"
    )

    st.plotly_chart(fig_prioridade, use_container_width=True)

st.divider()

st.subheader("🚨 Chamados críticos")

df_criticos = df_filtrado[
    (df_filtrado["prioridade"] == "Urgente") |
    (df_filtrado["sla"] == "Atrasado")
]

if df_criticos.empty:
    st.success("Nenhum chamado crítico no momento.")
else:
    st.dataframe(
        df_criticos[
            [
                "protocolo",
                "status",
                "prioridade",
                "sla",
                "categoria",
                "solicitante",
                "descricao",
                "criado_em"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

st.divider()

st.subheader("📋 Todos os chamados LegalOne")

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

colunas_existentes = [c for c in colunas if c in df_filtrado.columns]

st.dataframe(
    df_filtrado[colunas_existentes],
    use_container_width=True,
    hide_index=True
)

csv = df_filtrado[colunas_existentes].to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Baixar relatório CSV",
    data=csv,
    file_name="relatorio_legalone.csv",
    mime="text/csv"
)