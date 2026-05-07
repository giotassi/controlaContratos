import streamlit as st
from services.cadin import CADINService
from services.transparencia import TransparenciaService
from utils.formatters import format_cnpj
from views.cadin_auth import exibir_status_cadin

def render():
    st.header("Consulta Individual")

    exibir_status_cadin()

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
                sem_api = all(v['status'] is None for v in resultado_transparencia.values())
                if sem_api:
                    st.info("ℹ️ Consulta ao Portal da Transparência (CEIS/CNEP/CEPIM) não disponível — API_KEY não configurada.")
                else:
                    col1, col2, col3 = st.columns(3)
                    sistemas_transp = [
                        (col1, "CEIS", "ceis"),
                        (col2, "CNEP", "cnep"),
                        (col3, "CEPIM", "cepim"),
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