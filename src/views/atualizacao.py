import streamlit as st
from services.monitor import MonitorService
from services.database import DatabaseService

def render():
    st.header("🔄 Atualizar Base de Dados")
    
    db = DatabaseService()
    monitor = MonitorService()
    
    # Opções de atualização
    opcao = st.radio(
        "O que você deseja fazer?",
        ["Atualizar todas as empresas", "Limpar base de dados"]
    )
    
    if opcao == "Atualizar todas as empresas":
        if st.button("Iniciar Atualização"):
            empresas = db.get_empresas()
            
            if not empresas:
                st.warning("Nenhuma empresa cadastrada na base")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, empresa in enumerate(empresas):
                # Atualiza progresso
                progress = (i + 1) / len(empresas)
                progress_bar.progress(progress)
                status_text.text(f"Processando {i+1} de {len(empresas)} empresas...")
                
                # Atualiza empresa
                monitor.verificar_empresa(empresa['cnpj'])
            
            status_text.text("✅ Atualização concluída!")
            
    else:  # Limpar base
        st.warning("⚠️ Essa ação irá remover todos os dados da base!")
        
        if st.button("Confirmar Limpeza"):
            with st.spinner("Limpando base de dados..."):
                resultado = db.limpar_base_dados()
                
                if resultado:
                    st.success(
                        f"Base limpa com sucesso!\n"
                        f"- {resultado['monitoramentos']} monitoramentos removidos\n"
                        f"- {resultado['empresas']} empresas removidas"
                    )
                else:
                    st.error("Erro ao limpar base de dados") 