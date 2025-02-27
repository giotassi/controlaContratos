import streamlit as st
from services.database import DatabaseService
from datetime import datetime, timedelta
import pytz

def render():
    st.header("Histórico de Consultas")
    
    db = DatabaseService()
    
    # Filtros
    col1, col2 = st.columns(2)
    
    with col1:
        periodo = st.selectbox(
            "Período",
            ["Últimos 7 dias", "Últimos 30 dias", "Todos"]
        )
    
    with col2:
        status = st.selectbox(
            "Status",
            ["Todos", "Regular", "Irregular"]
        )
    
    # Busca dados
    monitoramentos = db.supabase.from_('monitoramentos')\
        .select('*, empresas(cnpj, razao_social)')\
        .order('data_verificacao', desc=True)\
        .execute()
    
    if monitoramentos.data:
        # Filtra por período
        if periodo != "Todos":
            dias = 7 if "7" in periodo else 30
            data_limite = datetime.now(pytz.UTC) - timedelta(days=dias)
            monitoramentos.data = [
                m for m in monitoramentos.data 
                if datetime.fromisoformat(m['data_verificacao']) > data_limite
            ]
        
        # Filtra por status
        if status != "Todos":
            is_regular = status == "Regular"
            monitoramentos.data = [
                m for m in monitoramentos.data 
                if m['status'] == is_regular
            ]
        
        # Exibe resultados
        for mon in monitoramentos.data:
            data = datetime.fromisoformat(mon['data_verificacao']).astimezone(pytz.timezone('America/Sao_Paulo'))
            with st.expander(
                f"{mon['empresas']['razao_social']} - "
                f"{mon['tipo_verificacao']} - "
                f"{data.strftime('%d/%m/%Y %H:%M')}"
            ):
                st.write(f"CNPJ: {mon['empresas']['cnpj']}")
                st.write(f"Status: {'✅ Regular' if mon['status'] else '❌ Irregular'}")
                st.write(f"Observações: {mon['observacoes']}")
    else:
        st.info("Nenhum registro encontrado") 