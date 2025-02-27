import streamlit as st
from services.monitor import MonitorService
import pandas as pd
import time
from datetime import datetime, timedelta
from services.relatorio import RelatorioService
from services.email import EmailService

def formatar_cnpj(cnpj):
    """Formata o CNPJ para o padrão XX.XXX.XXX/XXXX-XX"""
    # Remove caracteres não numéricos
    cnpj = ''.join(filter(str.isdigit, str(cnpj)))
    
    # Completa com zeros à esquerda se necessário
    cnpj = cnpj.zfill(14)
    
    # Formata
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def render():
    st.header("Consulta em Lote")
    
    monitor = MonitorService()
    
    uploaded_file = st.file_uploader(
        "Escolha uma planilha Excel",
        type=['xlsx', 'xls'],
        help="A planilha deve conter uma coluna com os CNPJs"
    )
    
    if uploaded_file:
        try:
            df = pd.read_excel(
                uploaded_file,
                dtype={
                    'Instrumento': str,
                    'N° Contrato': str,
                    'Ano Contrato': str,
                    'Contratado': str,
                    'CPF/CNPJ': str
                }
            )
            st.write("Preview da planilha:")
            st.dataframe(df.head())
            
            if st.button("Processar Planilha"):
                # Container para informações de progresso
                progress_container = st.container()
                
                with progress_container:
                    st.subheader("Progresso")
                    
                    # Métricas de progresso
                    total = len(df)
                    progress_bar = st.progress(0)
                    concluidos = st.empty()  # Para atualizar número de concluídos
                    percentual = st.empty()  # Para atualizar percentual
                    
                    # Métricas de tempo
                    st.subheader("⏱️ Tempo")
                    tempo_decorrido = st.empty()
                    tempo_restante = st.empty()
                    media_empresa = st.empty()
                    
                    # Status atual
                    status_atual = st.empty()
                    
                    start_time = time.time()
                    tempos_processamento = []
                    resultados = []
                    
                    for i, row in df.iterrows():
                        item_start_time = time.time()
                        
                        # Atualiza status atual
                        status_atual.text(f"🔄 Consultando: {row['Contratado']}")
                        
                        # Processa CNPJ
                        cnpj = str(row['CPF/CNPJ']).strip()
                        razao_social = str(row['Contratado']).strip()
                        
                        resultado = monitor.verificar_empresa(cnpj, razao_social)
                        resultados.append(resultado)
                        
                        # Calcula métricas de tempo
                        item_time = time.time() - item_start_time
                        tempos_processamento.append(item_time)
                        media_tempo = sum(tempos_processamento) / len(tempos_processamento)
                        
                        # Atualiza progresso e tempos
                        progress = (i + 1) / total
                        progress_bar.progress(progress)
                        concluidos.markdown(f"✅ Concluído: {i+1}/{total} empresas")
                        percentual.markdown(f"📊 Percentual: {progress*100:.0f}%")
                        
                        # Atualiza tempos no contexto principal
                        tempo_atual = time.time() - start_time
                        tempo_decorrido.markdown(f"⏰ Decorrido: {str(timedelta(seconds=int(tempo_atual)))}")
                        
                        tempo_estimado_restante = media_tempo * (total - (i + 1))
                        tempo_restante.markdown(f"⏳ Estimado restante: {str(timedelta(seconds=int(tempo_estimado_restante)))}")
                        media_empresa.markdown(f"⚡ Média por empresa: {str(timedelta(seconds=int(media_tempo)))}")
                        
                        # Força atualização da interface
                        st.empty()
                        time.sleep(0.1)
                    
                    status_atual.text("✅ Processamento concluído!")
                    
                    # Exibe resultados
                    st.subheader("Resultados")
                    for cnpj, resultado in zip(df['CPF/CNPJ'], resultados):
                        if isinstance(resultado, dict):
                            # Verifica se há alguma irregularidade em qualquer sistema
                            sistemas_irregulares = []
                            for sistema, res in resultado.items():
                                if isinstance(res, dict) and not res.get('status', True):
                                    sistemas_irregulares.append((sistema, res.get('observacoes', 'N/A')))
                            
                            if sistemas_irregulares:
                                st.error(f"{cnpj}: Irregular em um ou mais sistemas")
                                for sistema, obs in sistemas_irregulares:
                                    st.write(f"- {sistema.upper()}: {obs}")
                            else:
                                st.success(f"{cnpj}: Regular em todos os sistemas")
                        else:
                            st.error(f"{cnpj}: Erro ao processar - {resultado}")
                            
                    # Gera relatório
                    relatorio = RelatorioService()
                    arquivo_relatorio = relatorio.gerar_relatorio_impedimentos(
                        {row['CPF/CNPJ']: resultado for row, resultado in zip(df.itertuples(), resultados)}
                    )
                    
                    if arquivo_relatorio:
                        st.success(f"Relatório gerado: {arquivo_relatorio}")
                        
                        # Configurações de e-mail (pode vir de variáveis de ambiente)
                        email_service = EmailService(
                            smtp_server="smtp.gmail.com",
                            smtp_port=587,
                            username=st.secrets["email"]["username"],
                            password=st.secrets["email"]["password"]
                        )
                        
                        # Lista de destinatários (pode vir de configuração)
                        destinatarios = st.secrets["email"]["destinatarios"]
                        
                        if email_service.enviar_relatorio(destinatarios, arquivo_relatorio):
                            st.success("Relatório enviado por e-mail com sucesso!")
                        else:
                            st.error("Erro ao enviar relatório por e-mail")
                            
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {str(e)}") 