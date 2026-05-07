"""
Componente Streamlit: autenticação CADIN/RS.

O usuário faz login no CADIN no seu Chrome habitual.
O app lê os cookies do Chrome e cria uma sessão Selenium autenticada.
"""
import streamlit as st


def exibir_status_cadin() -> bool:
    from utils.cadin_session import has_valid_session, confirmar_login, invalidar_sessao

    with st.expander("🔐 Autenticação CADIN/RS", expanded=not has_valid_session()):

        if has_valid_session():
            st.success("✅ Sessão CADIN ativa")
            _, col2 = st.columns([3, 1])
            with col2:
                if st.button("Encerrar sessão", key="cadin_logout"):
                    invalidar_sessao()
                    st.rerun()
            return True

        st.warning("⚠️ Sessão CADIN não autenticada.")

        st.markdown("""
**Como autenticar:**

1. Abra o **Google Chrome** que você usa normalmente
2. Acesse **[cadin.sefaz.rs.gov.br](https://cadin.sefaz.rs.gov.br)** e clique em **Login gov.br**
3. Faça login normalmente (2FA incluído)
4. Quando o botão **Consultar** estiver habilitado, volte aqui e clique abaixo

> O app lê os cookies do seu Chrome — nenhum browser extra é aberto.
""")

        if st.button("✅ Já fiz login — conectar", key="cadin_confirmar", type="primary"):
            with st.spinner("Lendo cookies do Chrome e criando sessão…"):
                sucesso = confirmar_login()
            if sucesso:
                st.success("Sessão conectada com sucesso!")
                st.rerun()
            else:
                st.error(
                    "Não foi possível detectar a sessão. Verifique se:\n"
                    "- O Chrome está aberto e você está logado no CADIN\n"
                    "- O botão Consultar está habilitado no CADIN\n"
                    "- O Chrome é o Google Chrome (não Edge nem Firefox)"
                )

    return False
