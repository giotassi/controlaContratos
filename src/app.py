import os
from dotenv import load_dotenv
import streamlit as st
from views import (
    consulta_individual,
    consulta_lote,
    consulta_completa,
    historico,
    alertas,
    certidoes,
    atualizacao,
)

load_dotenv()

st.set_page_config(
    page_title="Monitor de Impedimentos",
    page_icon="🔎",
    layout="wide",
)


def main():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            max-width: 1180px;
        }
        [data-testid="stSidebar"] {
            background: #f7f9fc;
        }
        .app-hero {
            border: 1px solid #e6eaf0;
            border-radius: 8px;
            padding: 1.35rem 1.5rem;
            margin-bottom: 1.25rem;
            background: #ffffff;
        }
        .app-hero h1 {
            font-size: 2rem;
            margin: 0 0 .35rem 0;
            letter-spacing: 0;
        }
        .app-hero p {
            margin: 0;
            color: #566274;
            font-size: 1rem;
        }
        </style>
        <div class="app-hero">
            <h1>Monitor de Impedimentos</h1>
            <p>Consulta objetiva de restrições, certidões e histórico de fornecedores.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### Navegação")
    opcao = st.sidebar.selectbox(
        "Selecione uma opção",
        [
            "Consulta Individual",
            "Consulta em Lote",
            "Histórico de Consultas",
            "Alertas de Impedimentos",
            "Certidões Negativas",
            "CADIN/CFIL RS",
            "🔄 Atualizar Base",
        ],
    )

    if opcao == "Consulta em Lote":
        consulta_lote()
    elif opcao == "Consulta Individual":
        consulta_individual()
    elif opcao == "Histórico de Consultas":
        historico()
    elif opcao == "Alertas de Impedimentos":
        alertas()
    elif opcao == "Certidões Negativas":
        certidoes()
    elif opcao == "CADIN/CFIL RS":
        consulta_completa()
    elif opcao == "🔄 Atualizar Base":
        atualizacao()


if __name__ == "__main__":
    main()
