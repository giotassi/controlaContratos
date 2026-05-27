from datetime import datetime, timedelta

import pytz
import streamlit as st

from services.database import DatabaseService


def render():
    st.header("Histórico de Consultas")

    db = DatabaseService()

    col1, col2 = st.columns(2)
    with col1:
        periodo = st.selectbox("Período", ["Últimos 7 dias", "Últimos 30 dias", "Todos"])
    with col2:
        status = st.selectbox("Status", ["Todos", "Regular", "Irregular"])

    monitoramentos = (
        db.supabase.from_("monitoramentos")
        .select("*, empresas(cnpj, razao_social)")
        .eq("tipo_verificacao", "CONSOLIDADO")
        .order("data_verificacao", desc=True)
        .execute()
    )

    dados = monitoramentos.data or []
    if periodo != "Todos":
        dias = 7 if "7" in periodo else 30
        data_limite = datetime.now(pytz.UTC) - timedelta(days=dias)
        dados = [
            m for m in dados
            if datetime.fromisoformat(m["data_verificacao"]) > data_limite
        ]

    if status != "Todos":
        is_regular = status == "Regular"
        dados = [m for m in dados if m["status"] == is_regular]

    if not dados:
        st.info("Nenhum registro encontrado")
        return

    tz = pytz.timezone("America/Sao_Paulo")
    for mon in dados:
        data = datetime.fromisoformat(mon["data_verificacao"]).astimezone(tz)
        empresa = mon.get("empresas") or {}
        razao = empresa.get("razao_social", "Empresa")
        cnpj = empresa.get("cnpj", "")
        with st.expander(f"{razao} - {data.strftime('%d/%m/%Y %H:%M')}"):
            st.write(f"CNPJ: {cnpj}")
            if mon["status"] is None:
                status_label = "Não conclusivo"
            else:
                status_label = "Regular" if mon["status"] else "Irregular"
            st.write(f"Status: {status_label}")
            st.write(f"Observações: {mon.get('observacoes', '')}")
