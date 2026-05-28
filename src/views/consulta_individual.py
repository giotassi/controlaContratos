import streamlit as st

from services.monitor import MonitorService
from services.tcu_apf import TCUAPFService
from utils.formatters import format_cnpj


def _status(label: str, dados: dict):
    st.write(label)
    status = dados.get("status")
    if status is None:
        st.warning("Não conclusivo")
    elif status:
        st.success("Regular")
    else:
        st.error("Irregular")
    st.info(dados.get("observacoes", ""))


def render():
    st.header("Consulta Individual")

    monitor = MonitorService()
    tcu_service = TCUAPFService()

    cnpj = st.text_input(
        "CNPJ da Empresa",
        help="Digite apenas números",
    )

    if st.button("Consultar", type="primary"):
        if not cnpj:
            st.error("Por favor, digite um CNPJ")
            return

        cnpj_formatado = format_cnpj(cnpj)

        with st.spinner("Consultando..."):
            resultado = monitor.verificar_empresa(
                cnpj_formatado,
                incluir_cadin=True,
                incluir_cfil=True,
                salvar=True,
            )

        if resultado.get("error"):
            st.error(resultado["error"])
            return

        st.subheader("CADIN/CFIL RS")
        col1, col2 = st.columns(2)
        with col1:
            dados_cadin = resultado.get("cadin", {})
            _status("CADIN/RS", dados_cadin)
            if dados_cadin.get("status") is False:
                certidao_cadin = monitor.cadin.emitir_certidao_cadin(cnpj_formatado)
                if certidao_cadin.get("pdf_bytes"):
                    st.download_button(
                        "Baixar certidão CADIN/RS",
                        data=certidao_cadin["pdf_bytes"],
                        file_name=f"certidao_cadin_rs_{cnpj_formatado}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning(f"Certidão CADIN/RS não emitida: {certidao_cadin.get('error', 'sem retorno')}")
        with col2:
            _status("CFIL/RS", resultado.get("cfil", {}))

        st.subheader("Consulta Consolidada TCU")
        dados_tcu = resultado.get("tcu", {})
        _status("TCU", dados_tcu)
        if dados_tcu.get("status") is False:
            with st.spinner("Emitindo PDF consolidado do TCU..."):
                certidao_tcu = tcu_service.consultar(cnpj_formatado, emitir_pdf=True)
            if certidao_tcu.get("pdf_bytes"):
                st.download_button(
                    "Baixar PDF consolidado do TCU",
                    data=certidao_tcu["pdf_bytes"],
                    file_name=f"certidao_tcu_{cnpj_formatado}.pdf",
                    mime="application/pdf",
                )
            else:
                st.warning(f"PDF do TCU não emitido: {certidao_tcu.get('error', 'sem retorno')}")

        st.subheader("Portal da Transparência")
        col1, col2 = st.columns(2)
        with col1:
            _status("CEIS", resultado.get("ceis", {}))
        with col2:
            _status("CNEP", resultado.get("cnep", {}))
