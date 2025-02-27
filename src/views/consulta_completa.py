import streamlit as st
from services.monitor import MonitorService
from utils.formatters import format_cnpj

def render():
    st.header("CADIN/CFIL RS - Consulta Completa")
    
    monitor = MonitorService()
    
    # Campo para CNPJ
    cnpj = st.text_input(
        "CNPJ da Empresa",
        help="Digite apenas números"
    )
    
    if st.button("Consultar"):
        if not cnpj:
            st.error("Por favor, digite um CNPJ")
            return
            
        with st.spinner("Consultando..."):
            # Consulta CADIN/CFIL
            resultado = monitor.verificar_empresa(cnpj)
            
            if resultado.get("error"):
                st.error(resultado["error"])
                return
            
            # Exibe resultados em colunas
            col1, col2 = st.columns(2)
            
            # CADIN
            with col1:
                st.subheader("CADIN/RS")
                if resultado['cadin']['status']:
                    st.success("✅ Regular")
                else:
                    st.error("❌ Irregular")
                st.info(resultado['cadin']['observacoes'])
            
            # CFIL
            with col2:
                st.subheader("CFIL/RS")
                if resultado['cfil']['status']:
                    st.success("✅ Regular")
                else:
                    st.error("❌ Irregular")
                st.info(resultado['cfil']['observacoes'])
            
            # Histórico
            st.subheader("Histórico de Consultas")
            historico = monitor.db.supabase.from_('monitoramentos')\
                .select('*')\
                .eq('empresa_id', resultado.get('empresa_id'))\
                .order('data_verificacao', desc=True)\
                .execute()
            
            if historico.data:
                for consulta in historico.data:
                    st.write(f"**{consulta['tipo_verificacao']}** - {consulta['data_verificacao']}")
                    st.write(f"Status: {'✅ Regular' if consulta['status'] else '❌ Irregular'}")
                    st.write(f"Observações: {consulta['observacoes']}")
                    st.write("---") 