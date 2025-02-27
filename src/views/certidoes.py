import streamlit as st
from services.database import DatabaseService
from datetime import datetime, date

def render():
    st.header("Certidões Negativas")
    
    db = DatabaseService()
    
    # Tabs para diferentes funcionalidades
    tab1, tab2 = st.tabs(["Consultar Certidões", "Adicionar Certidão"])
    
    with tab1:
        # Filtros
        status = st.selectbox(
            "Status",
            ["Todas", "Vencidas", "A vencer em 30 dias", "Regulares"]
        )
        
        tipo = st.selectbox(
            "Tipo de Certidão",
            ["Todas", "Federal", "Estadual", "Municipal", "Trabalhista", "FGTS"]
        )
        
        # Busca certidões
        certidoes = db.listar_certidoes(status=status, tipo=tipo)
        
        # Exibe resultados
        for empresa in certidoes:
            with st.expander(f"{empresa['razao_social']} - {empresa['cnpj']}"):
                for cert in empresa['certidoes']:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**{cert['tipo']}**")
                    with col2:
                        st.write(f"Validade: {datetime.fromisoformat(cert['data_validade']).strftime('%d/%m/%Y')}")
                    with col3:
                        if cert['arquivo_url']:
                            st.download_button(
                                "📄 Download",
                                cert['arquivo_url'],
                                file_name=f"certidao_{cert['tipo']}.pdf"
                            )
    
    with tab2:
        # Formulário para nova certidão
        with st.form("nova_certidao"):
            cnpj = st.text_input("CNPJ")
            tipo = st.selectbox(
                "Tipo",
                ["Federal", "Estadual", "Municipal", "Trabalhista", "FGTS"]
            )
            data_emissao = st.date_input("Data de Emissão")
            data_validade = st.date_input("Data de Validade")
            numero = st.text_input("Número da Certidão")
            arquivo = st.file_uploader("Arquivo da Certidão", type=['pdf'])
            
            if st.form_submit_button("Adicionar"):
                if cnpj and tipo and data_emissao and data_validade:
                    empresa_id = db.obter_empresa_id(cnpj)
                    if empresa_id:
                        certidao = db.adicionar_certidao(
                            empresa_id=empresa_id,
                            tipo=tipo,
                            data_emissao=data_emissao,
                            data_validade=data_validade,
                            numero_certidao=numero,
                            arquivo=arquivo
                        )
                        if certidao:
                            st.success("Certidão adicionada com sucesso!")
                        else:
                            st.error("Erro ao adicionar certidão")
                    else:
                        st.error("Empresa não encontrada")
                else:
                    st.error("Preencha todos os campos obrigatórios") 