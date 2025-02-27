import streamlit as st
from services.cadin import CADINService
from services.transparencia import TransparenciaService
from utils.formatters import format_cnpj

def render():
    st.header("Consulta Individual")
    
    # Inicializa serviços
    cadin_service = CADINService()
    transparencia_service = TransparenciaService()
    
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
            # Formata CNPJ
            cnpj_formatado = format_cnpj(cnpj)
            
            # Consulta CADIN/CFIL
            resultado_cadin = cadin_service.consultar(cnpj_formatado)
            if resultado_cadin:
                st.subheader("CADIN/CFIL RS")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("CADIN/RS")
                    if resultado_cadin['cadin']['status']:
                        st.success("✅ Regular")
                    else:
                        st.error("❌ Irregular")
                    st.info(resultado_cadin['cadin']['observacoes'])
                
                with col2:
                    st.write("CFIL/RS")
                    if resultado_cadin['cfil']['status']:
                        st.success("✅ Regular")
                    else:
                        st.error("❌ Irregular")
                    st.info(resultado_cadin['cfil']['observacoes'])
            
            # Consulta Portal da Transparência
            resultado_transparencia = transparencia_service.consultar(cnpj_formatado)
            if resultado_transparencia:
                st.subheader("Portal da Transparência")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("CEIS")
                    if resultado_transparencia['ceis']['status']:
                        st.success("✅ Regular")
                    else:
                        st.error("❌ Irregular")
                    st.info(resultado_transparencia['ceis']['observacoes'])
                
                with col2:
                    st.write("CNEP")
                    if resultado_transparencia['cnep']['status']:
                        st.success("✅ Regular")
                    else:
                        st.error("❌ Irregular")
                    st.info(resultado_transparencia['cnep']['observacoes'])
                
                with col3:
                    st.write("CEPIM")
                    if resultado_transparencia['cepim']['status']:
                        st.success("✅ Regular")
                    else:
                        st.error("❌ Irregular")
                    st.info(resultado_transparencia['cepim']['observacoes']) 