from services.monitor import MonitorService
from services.relatorio import RelatorioService
from services.email import EmailService
import streamlit as st
from datetime import datetime, timedelta

def render():
    st.header("Alertas de Impedimentos")
    
    monitor = MonitorService()
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        dias = st.number_input(
            "Últimos dias", 
            min_value=1, 
            value=30,
            help="Filtrar alertas dos últimos X dias"
        )
    
    with col2:
        apenas_ativos = st.checkbox("Apenas impedimentos ativos", value=True)
    
    # Busca impedimentos
    data_limite = datetime.now() - timedelta(days=dias)
    impedimentos = monitor.buscar_impedimentos(data_limite, apenas_ativos)
    
    if impedimentos:
        st.subheader(f"Impedimentos encontrados: {len(impedimentos)}")
        
        # Exibe impedimentos
        for imp in impedimentos:
            with st.expander(f"{imp['cnpj']} - {imp['razao_social']}"):
                st.write(f"**Sistema:** {imp['sistema']}")
                st.write(f"**Data Verificação:** {imp['data_verificacao']}")
                st.write(f"**Observações:** {imp['observacoes']}")
        
        # Botões de ação
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Gerar Relatório"):
                relatorio = RelatorioService()
                
                # Organiza dados para o relatório em uma lista
                dados_relatorio = []
                for imp in impedimentos:
                    # Cria um dicionário para cada empresa
                    empresa = {
                        'cnpj': imp['cnpj'],
                        'razao_social': imp['razao_social'],
                        imp['sistema'].lower(): {
                            'status': False,
                            'observacoes': imp['observacoes']
                        }
                    }
                    dados_relatorio.append(empresa)
                
                arquivo_relatorio = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
                
                if arquivo_relatorio:
                    # Lê o arquivo PDF gerado
                    with open(arquivo_relatorio, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                    
                    # Cria botão de download
                    st.download_button(
                        label="📥 Baixar Relatório",
                        data=pdf_bytes,
                        file_name=arquivo_relatorio,
                        mime="application/pdf"
                    )
                    st.success(f"Relatório gerado com sucesso!")
                else:
                    st.error("Erro ao gerar relatório")
        
        with col2:
            if st.button("📧 Enviar por E-mail"):
                relatorio = RelatorioService()
                
                # Organiza dados para o relatório
                dados_relatorio = {}
                for imp in impedimentos:
                    if imp['cnpj'] not in dados_relatorio:
                        dados_relatorio[imp['cnpj']] = {}
                    
                    dados_relatorio[imp['cnpj']][imp['sistema'].lower()] = {
                        'status': False,
                        'observacoes': imp['observacoes']
                    }
                
                arquivo_relatorio = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
                
                if arquivo_relatorio:
                    # Configurações de e-mail
                    email_service = EmailService(
                        smtp_server="smtp.gmail.com",
                        smtp_port=587,
                        username=st.secrets["email"]["username"],
                        password=st.secrets["email"]["password"]
                    )
                    
                    # Lista de destinatários
                    destinatarios = st.secrets["email"]["destinatarios"]
                    
                    if email_service.enviar_relatorio(destinatarios, arquivo_relatorio):
                        st.success("Relatório enviado por e-mail com sucesso!")
                    else:
                        st.error("Erro ao enviar relatório por e-mail")
                else:
                    st.error("Erro ao gerar relatório")
    else:
        st.info("Nenhum impedimento encontrado no período selecionado.") 