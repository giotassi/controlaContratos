import streamlit as st
from services.cadin import CADINService
from services.tcu_apf import TCUAPFService
from services.transparencia import TransparenciaService
from utils.formatters import format_cnpj
from views.cadin_auth import exibir_status_cadin

def render():
    st.header("Consulta Individual")

    exibir_status_cadin()

    # Inicializa serviços
    cadin_service = CADINService()
    transparencia_service = TransparenciaService()
    tcu_service = TCUAPFService()

    # Campo para CNPJ
    cnpj = st.text_input(
        "CNPJ da Empresa",
        help="Digite apenas números"
    )

    emitir_pdf_tcu = st.checkbox(
        "Emitir PDF consolidado do TCU nesta consulta",
        value=False,
        help="Pode deixar a consulta mais lenta. Use apenas quando precisar anexar a certidao consolidada.",
    )

    if st.button("Consultar"):
        if not cnpj:
            st.error("Por favor, digite um CNPJ")
            return

        with st.spinner("Consultando..."):
            cnpj_formatado = format_cnpj(cnpj)

            resultado_cadin = cadin_service.consultar(cnpj_formatado)
            if resultado_cadin:
                st.subheader("CADIN/CFIL RS")
                col1, col2 = st.columns(2)

                with col1:
                    st.write("CADIN/RS")
                    status_cadin = resultado_cadin['cadin']['status']
                    if status_cadin is None:
                        st.warning("⚠️ Não consultado (sem sessão)")
                    elif status_cadin:
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
                # Verifica se API está configurada (todos os status None = sem chave)
                sem_api = all(
                    resultado_transparencia[sistema]['status'] is None
                    for sistema in ('ceis', 'cnep')
                    if sistema in resultado_transparencia
                )
                if sem_api:
                    st.info("ℹ️ Consulta ao Portal da Transparência (CEIS/CNEP) não disponível — API_KEY não configurada.")
                else:
                    col1, col2 = st.columns(2)
                    sistemas_transp = [
                        (col1, "CEIS", "ceis"),
                        (col2, "CNEP", "cnep"),
                    ]
                    for col, label, key in sistemas_transp:
                        with col:
                            st.write(label)
                            status = resultado_transparencia[key]['status']
                            if status:
                                st.success("✅ Regular")
                            else:
                                st.error("❌ Irregular")
                            st.info(resultado_transparencia[key]['observacoes'])

            if emitir_pdf_tcu:
                with st.spinner("Emitindo PDF consolidado do TCU..."):
                    resultado_tcu = tcu_service.consultar(cnpj_formatado, emitir_pdf=True)
                if resultado_tcu.get("error"):
                    st.warning(f"PDF do TCU nao emitido: {resultado_tcu['error']}")
                elif resultado_tcu.get("pdf_bytes"):
                    st.download_button(
                        "Baixar PDF consolidado do TCU",
                        data=resultado_tcu["pdf_bytes"],
                        file_name=f"certidao_tcu_{cnpj_formatado}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning("O TCU respondeu sem PDF para este CNPJ.")
