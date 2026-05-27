import streamlit as st

from services.cadin import CADINService
from services.tcu_apf import TCUAPFService
from services.transparencia import TransparenciaService
from utils.formatters import format_cnpj


def _status(label: str, status):
    st.write(label)
    if status is None:
        st.warning("Não consultado")
    elif status:
        st.success("Regular")
    else:
        st.error("Irregular")


def render():
    st.header("Consulta Individual")

    cadin_service = CADINService()
    transparencia_service = TransparenciaService()
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

        with st.spinner("Consultando CADIN/CFIL RS..."):
            resultado_cadin = cadin_service.consultar(cnpj_formatado)

        if resultado_cadin:
            st.subheader("CADIN/CFIL RS")
            col1, col2 = st.columns(2)

            with col1:
                dados_cadin = resultado_cadin["cadin"]
                _status("CADIN/RS", dados_cadin.get("status"))
                st.info(dados_cadin.get("observacoes", ""))
                if dados_cadin.get("status") is False:
                    certidao_cadin = cadin_service.emitir_certidao_cadin(cnpj_formatado)
                    if certidao_cadin.get("pdf_bytes"):
                        st.download_button(
                            "Baixar certidão CADIN/RS",
                            data=certidao_cadin["pdf_bytes"],
                            file_name=f"certidao_cadin_rs_{cnpj_formatado}.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.warning(
                            f"Certidão CADIN/RS não emitida: {certidao_cadin.get('error', 'sem retorno')}"
                        )

            with col2:
                dados_cfil = resultado_cadin["cfil"]
                _status("CFIL/RS", dados_cfil.get("status"))
                st.info(dados_cfil.get("observacoes", ""))

        with st.spinner("Consultando TCU..."):
            resultado_tcu = tcu_service.consultar(cnpj_formatado, emitir_pdf=False)

        if resultado_tcu and resultado_tcu.get("error"):
            st.warning(f"Consulta TCU não realizada: {resultado_tcu['error']}")
        elif resultado_tcu:
            st.subheader("Consulta Consolidada TCU")
            certidoes_tcu = resultado_tcu.get("certidoes", [])
            cols = st.columns(min(len(certidoes_tcu), 4) or 1)
            for idx, certidao in enumerate(certidoes_tcu):
                with cols[idx % len(cols)]:
                    st.write(certidao.get("tipo", "TCU"))
                    if str(certidao.get("situacao", "")).upper() == "NADA_CONSTA":
                        st.success("Regular")
                    else:
                        st.error(certidao.get("situacao", "Restrição"))

            if tcu_service.tem_restricao(resultado_tcu):
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

        with st.spinner("Consultando Portal da Transparência..."):
            resultado_transparencia = transparencia_service.consultar(cnpj_formatado)

        if resultado_transparencia:
            st.subheader("Portal da Transparência")
            sistemas = ("ceis", "cnep")
            sem_api = all(
                resultado_transparencia[sistema]["status"] is None
                for sistema in sistemas
                if sistema in resultado_transparencia
            )
            if sem_api:
                st.info("Consulta CEIS/CNEP não disponível. API_KEY não configurada.")
            else:
                col1, col2 = st.columns(2)
                for col, label, key in ((col1, "CEIS", "ceis"), (col2, "CNEP", "cnep")):
                    with col:
                        dados = resultado_transparencia[key]
                        _status(label, dados.get("status"))
                        st.info(dados.get("observacoes", ""))
