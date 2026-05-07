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
    atualizacao
)

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Streamlit
st.set_page_config(
    page_title="Monitor de Impedimentos",
    page_icon="🔍",
    layout="wide"
)

def main():
    st.title("Monitor de Impedimentos")
    
    # Menu lateral
    opcao = st.sidebar.selectbox(
        "Selecione uma opção",
        [
            "Consulta Individual",
            "Consulta em Lote",
            "Histórico de Consultas",
            "Alertas de Impedimentos",
            "Certidões Negativas",
            "CADIN/CFIL RS",
            "🔄 Atualizar Base"
        ]
    )
    
    # Renderiza a view correspondente
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

if __name__ == '__main__':
    main() 