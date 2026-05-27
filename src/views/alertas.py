from datetime import datetime, timedelta

import streamlit as st

from services.email import EmailService
from services.monitor import MonitorService
from services.relatorio import RelatorioService


def _dados_relatorio(impedimentos):
    return [
        {
            "cnpj": imp["cnpj"],
            "razao_social": imp["razao_social"],
            imp["sistema"].lower(): {
                "status": False,
                "observacoes": imp["observacoes"],
            },
        }
        for imp in impedimentos
    ]


def render():
    st.header("Alertas de Impedimentos")

    monitor = MonitorService()

    col1, col2 = st.columns(2)
    with col1:
        dias = st.number_input(
            "Últimos dias",
            min_value=1,
            value=30,
            help="Filtrar alertas dos últimos X dias",
        )
    with col2:
        apenas_ativos = st.checkbox("Apenas impedimentos ativos", value=True)

    data_limite = datetime.now() - timedelta(days=dias)
    impedimentos = monitor.buscar_impedimentos(data_limite, apenas_ativos)

    if not impedimentos:
        st.info("Nenhum impedimento encontrado no período selecionado.")
        return

    st.subheader(f"Impedimentos encontrados: {len(impedimentos)}")

    for imp in impedimentos:
        with st.expander(f"{imp['cnpj']} - {imp['razao_social']}"):
            st.write(f"**Sistema:** {imp['sistema']}")
            st.write(f"**Data Verificação:** {imp['data_verificacao']}")
            st.write(f"**Observações:** {imp['observacoes']}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gerar Relatório"):
            relatorio = RelatorioService()
            arquivo_relatorio = relatorio.gerar_relatorio_impedimentos(_dados_relatorio(impedimentos))
            if arquivo_relatorio:
                pdf_bytes = relatorio.ler_relatorio(arquivo_relatorio)
                if pdf_bytes:
                    st.download_button(
                        label="Baixar Relatório",
                        data=pdf_bytes,
                        file_name=arquivo_relatorio,
                        mime="application/pdf",
                    )
                st.success("Relatório gerado com sucesso!")
            else:
                st.error("Erro ao gerar relatório")

    with col2:
        if st.button("Enviar por E-mail"):
            relatorio = RelatorioService()
            arquivo_relatorio = relatorio.gerar_relatorio_impedimentos(_dados_relatorio(impedimentos))
            if not arquivo_relatorio:
                st.error("Erro ao gerar relatório")
                return

            email_service = EmailService(
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                username=st.secrets["email"]["username"],
                password=st.secrets["email"]["password"],
            )
            destinatarios = st.secrets["email"]["destinatarios"]
            if email_service.enviar_relatorio(destinatarios, arquivo_relatorio):
                st.success("Relatório enviado por e-mail com sucesso!")
            else:
                st.error("Erro ao enviar relatório por e-mail")
