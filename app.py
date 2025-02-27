import streamlit as st
from monitor import MonitorEmpresas
import pandas as pd
import os
from datetime import datetime
import requests
import tempfile
from openpyxl import load_workbook
import xlrd
from bs4 import BeautifulSoup
import io
import re
import time
from datetime import timedelta
import warnings
import logging

# Configura logging
logging.getLogger('streamlit').setLevel(logging.ERROR)

# Suprime avisos específicos
warnings.filterwarnings('ignore', message='.*missing ScriptRunContext.*')
warnings.filterwarnings('ignore', category=DeprecationWarning)

st.set_page_config(
    page_title="Monitor de Impedimentos",
    page_icon="🔍",
    layout="wide"
)

def formatar_cnpj(cnpj):
    """Formata CNPJ: 00.000.000/0000-00"""
    cnpj = ''.join(filter(str.isdigit, cnpj))
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def main():
    st.title("Monitor de Impedimentos")
    
    # Inicializa o monitor usando variáveis de ambiente
    monitor = MonitorEmpresas()
    
    # Sidebar com menu
    with st.sidebar:
        st.header("Menu")
        opcao = st.radio(
            "Escolha uma opção:",
            [
                "Consulta em Lote",
                "Consulta Individual",
                "Histórico de Consultas",
                "Alertas de Impedimentos",
                "Certidões Negativas",
                "CADIN/CFIL RS",
                "🔄 Atualizar Base"
            ]
        )
    
    if opcao == "Consulta em Lote":
        st.header("Consulta em Lote")
        st.info("📁 Faça upload de uma planilha com os CNPJs para consulta")
        
        uploaded_file = st.file_uploader(
            "Escolha uma planilha Excel",
            type=['xlsx', 'xls'],
            help="A planilha deve conter as colunas: CPF/CNPJ, Contratado"
        )
        
        if uploaded_file:
            # Cria placeholder para a barra de progresso
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            time_placeholder = st.empty()
            
            try:
                # Inicia o timer
                start_time = time.time()
                total_steps = 5  # Total de etapas do processamento
                
                # Etapa 1: Salvando arquivo
                progress_placeholder.progress(0)
                status_placeholder.info("📥 Salvando arquivo...")
                temp_file = "temp_input.xls"
                with open(temp_file, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                # Atualiza progresso
                progress_placeholder.progress(20)
                status_placeholder.info("📊 Lendo planilha...")
                
                # Etapa 2: Lendo arquivo
                try:
                    df = pd.read_excel(temp_file, engine='xlrd')
                except:
                    try:
                        df = pd.read_excel(temp_file, engine='openpyxl')
                    except:
                        status_placeholder.error("""
                        ⚠️ Não foi possível ler o arquivo. Por favor, siga estes passos:
                        
                        1. Abra o arquivo no Excel
                        2. Clique em "Arquivo" > "Salvar Como"
                        3. Selecione o formato "Pasta de Trabalho do Excel (.xlsx)"
                        4. Salve o arquivo
                        5. Faça upload do novo arquivo .xlsx
                        """)
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        return
                
                # Remove arquivo temporário de entrada
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                # Etapa 3: Processando dados
                progress_placeholder.progress(40)
                status_placeholder.info("🔄 Processando dados...")
                
                # Debug info
                st.write(f"Colunas encontradas: {df.columns.tolist()}")
                st.write(f"Número de linhas: {len(df)}")
                
                # Etapa 4: Verificando colunas
                progress_placeholder.progress(60)
                status_placeholder.info("✔️ Verificando dados...")
                
                if 'CPF/CNPJ' in df.columns and 'Contratado' in df.columns:
                    # Salva DataFrame como Excel
                    output_file = "temp_output.xlsx"
                    df.to_excel(output_file, index=False)
                    
                    # Etapa 5: Importando dados
                    progress_placeholder.progress(80)
                    status_placeholder.info("📥 Importando dados...")
                    
                    # Importa os dados
                    empresas = monitor.importar_planilha(output_file)
                    
                    if empresas:
                        # Cria contadores para o progresso
                        total_empresas = len(empresas)
                        consultas_realizadas = 0
                        
                        # Cria placeholders para informações detalhadas
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        count_text = st.empty()
                        time_text = st.empty()
                        error_text = st.empty()
                        
                        def format_time(seconds):
                            """Formata segundos em horas:minutos:segundos"""
                            hours = int(seconds // 3600)
                            minutes = int((seconds % 3600) // 60)
                            seconds = int(seconds % 60)
                            if hours > 0:
                                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                            else:
                                return f"{minutes:02d}:{seconds:02d}"
                        
                        # Tempo inicial
                        start_time = time.time()
                        
                        # Realiza as consultas para cada empresa
                        for i, empresa in enumerate(empresas):
                            try:
                                # Atualiza contadores e progresso
                                consultas_realizadas = i + 1
                                progress = int(consultas_realizadas * 100 / total_empresas)
                                
                                # Atualiza interface com spinner animado
                                progress_bar.progress(progress)
                                status_text.markdown(f"""
                                <div style='display: flex; align-items: center; gap: 10px;'>
                                    <div class='stSpinner'>
                                        <div class='st-spinner-container'>
                                            <div class='st-spinner'></div>
                                        </div>
                                    </div>
                                    <div>🔍 Consultando: {empresa['razao_social']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                count_text.markdown(f"""
                                ### Progresso
                                - ✅ Concluído: {consultas_realizadas}/{total_empresas} empresas
                                - 📊 Percentual: {progress}%
                                """)
                                
                                # Calcula e mostra tempo estimado
                                elapsed_time = time.time() - start_time
                                avg_time_per_company = elapsed_time / consultas_realizadas
                                remaining_companies = total_empresas - consultas_realizadas
                                estimated_remaining = avg_time_per_company * remaining_companies
                                
                                time_text.markdown(f"""
                                ### ⏱️ Tempo
                                - ⌛ Decorrido: {format_time(elapsed_time)}
                                - 🔄 Estimado restante: {format_time(estimated_remaining)}
                                - ⚡ Média por empresa: {format_time(avg_time_per_company)}
                                
                                <div style='display: flex; align-items: center; gap: 10px;'>
                                    <div>🔄 Processando...</div>
                                    <div class='stSpinner'>
                                        <div class='st-spinner-container'>
                                            <div class='st-spinner'></div>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Realiza a consulta
                                monitor.verificar_impedimentos_api(empresa['cnpj'])
                                
                                # Pequena pausa para evitar sobrecarga
                                time.sleep(1)
                                
                            except Exception as e:
                                error_text.error(f"❌ Erro ao consultar {empresa['razao_social']}: {str(e)}")
                                continue
                        
                        # Finaliza
                        progress_bar.progress(100)
                        status_text.success("✅ Processamento concluído com sucesso!")
                        time_text.success(f"""
                        ### ⏱️ Processamento finalizado
                        - Tempo total: {format_time(time.time() - start_time)}
                        - Total de empresas: {total_empresas}
                        """)
                        
                        # Download do resultado
                        with open("resultados_consulta.xlsx", "rb") as f:
                            st.download_button(
                                "📥 Baixar Resultados",
                                f,
                                "resultados_consulta.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    
                    # Remove arquivo temporário de saída
                    if os.path.exists(output_file):
                        os.remove(output_file)
                else:
                    status_placeholder.error("A planilha deve conter as colunas 'CPF/CNPJ' e 'Contratado'")
                
            except Exception as e:
                status_placeholder.error(f"""
                ⚠️ Erro ao processar planilha. Por favor, siga estes passos:
                
                1. Abra o arquivo no Excel
                2. Clique em "Arquivo" > "Salvar Como"
                3. Selecione o formato "Pasta de Trabalho do Excel (.xlsx)"
                4. Salve o arquivo
                5. Faça upload do novo arquivo .xlsx
                
                Detalhes técnicos do erro: {str(e)}""")
                
                # Remove arquivos temporários em caso de erro
                for temp_file in ["temp_input.xls", "temp_output.xlsx"]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
    
    elif opcao == "Consulta Individual":
        st.header("Consulta Individual")
        
        # Input do CNPJ com formatação
        cnpj = st.text_input(
            "Digite o CNPJ:",
            help="Digite apenas números"
        )
        
        # Botão de consulta centralizado
        col1, col2, col3 = st.columns([2,1,2])
        with col2:
            consultar = st.button("🔍 Consultar", use_container_width=True)
        
        if consultar and cnpj:
            with st.spinner("Consultando..."):
                cnpj_formatado = formatar_cnpj(cnpj)
                cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
                
                # Busca na API do CNPJ.ws
                url = f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}"
                
                try:
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        dados = response.json()
                        empresa = {
                            'cnpj': cnpj_formatado,
                            'razao_social': dados.get('razao_social', 'Não informado'),
                            'nome_fantasia': dados.get('estabelecimento', {}).get('nome_fantasia', 'Não informado'),
                            'data_abertura': dados.get('estabelecimento', {}).get('data_inicio_atividade', 'Não informado'),
                            'situacao_cadastral': dados.get('estabelecimento', {}).get('situacao_cadastral', 'Não informado'),
                            'capital_social': dados.get('capital_social', 0),
                            'natureza_juridica': dados.get('natureza_juridica', {}).get('descricao', 'Não informado'),
                            'porte': dados.get('porte', {}).get('descricao', 'Não informado')
                        }
                        
                        # Exibe os dados básicos
                        st.markdown("### 🏢 Dados Básicos")
                        st.write("**CNPJ**: " + empresa['cnpj'])
                        st.write("**Razão Social**: " + empresa['razao_social'])
                        st.write("**Nome Fantasia**: " + empresa['nome_fantasia'])
                        st.write("**Data de Abertura**: " + empresa['data_abertura'])
                        
                        # Consulta impedimentos
                        try:
                            resultados = monitor.verificar_impedimentos_api(cnpj_limpo)
                            if resultados:
                                st.success("✅ Consulta realizada com sucesso!")
                                
                                # Container para os resultados
                                for sistema, resultado in resultados.items():
                                    with st.expander("📊 " + str(sistema), expanded=True):
                                        if resultado['status']:
                                            st.markdown(
                                                "<div style='background-color: #dff0d8; padding: 10px; border-radius: 5px;'>" +
                                                "✅ " + str(resultado['observacoes']) +
                                                "</div>",
                                                unsafe_allow_html=True
                                            )
                                        else:
                                            st.markdown(
                                                "<div style='background-color: #f2dede; padding: 10px; border-radius: 5px;'>" +
                                                "❌ " + str(resultado['observacoes']) +
                                                "</div>",
                                                unsafe_allow_html=True
                                            )
                        except Exception as e:
                            st.error("Erro ao consultar impedimentos: " + str(e))
                except Exception as e:
                    st.error("Erro ao consultar impedimentos: " + str(e))

        if consultar and not cnpj:
            st.warning("⚠️ Digite um CNPJ para consultar")
    
    elif opcao == "Histórico de Consultas":
        st.header("Histórico de Consultas")
        
        # Adiciona toggle para mostrar todas as consultas
        mostrar_todas = st.toggle('Mostrar todas as consultas', value=False)
        
        try:
            # Buscar histórico do Supabase
            if mostrar_todas:
                consultas = monitor.supabase.from_('monitoramentos').select('*, empresas(*)').filter('observacoes', 'not.ilike', '%CNPJ inválido%').order('data_verificacao', desc=True).execute()
            else:
                # Busca apenas a última consulta de cada empresa
                consultas = monitor.supabase.from_('monitoramentos').select('*, empresas(*)').filter('observacoes', 'not.ilike', '%CNPJ inválido%').order('data_verificacao', desc=True).limit(1).execute()
            
            if consultas.data:
                # Agrupa consultas por empresa
                empresas_dict = {}
                for consulta in consultas.data:
                    cnpj = consulta['empresas']['cnpj']
                    data = pd.to_datetime(consulta['data_verificacao']).strftime('%d/%m/%Y')
                    
                    if cnpj not in empresas_dict:
                        empresas_dict[cnpj] = {
                            'empresa': consulta['empresas']['razao_social'],
                            'ultima_consulta': pd.to_datetime(consulta['data_verificacao']).strftime('%d/%m/%Y %H:%M'),
                            'consultas_por_data': {}
                        }
                    
                    if data not in empresas_dict[cnpj]['consultas_por_data']:
                        empresas_dict[cnpj]['consultas_por_data'][data] = []
                        
                    empresas_dict[cnpj]['consultas_por_data'][data].append({
                        'hora': pd.to_datetime(consulta['data_verificacao']).strftime('%H:%M'),
                        'sistema': consulta['tipo_verificacao'],
                        'status': '✅ Regular' if consulta['status'] else '❌ Irregular',
                        'observacoes': consulta['observacoes']
                    })
                
                # Exibe empresas com expanders
                for cnpj, dados in empresas_dict.items():
                    with st.expander(f"📊 {dados['empresa']} - CNPJ: {cnpj} (Última consulta: {dados['ultima_consulta']})"):
                        for data, consultas in dados['consultas_por_data'].items():
                            st.markdown(f"### 📅 Consultas em {data}")
                            df_consultas = pd.DataFrame(consultas)
                            
                            st.dataframe(
                                df_consultas,
                                column_config={
                                    "hora": st.column_config.TextColumn(
                                        "Horário",
                                        width=80,
                                        help="Horário da verificação"
                                    ),
                                    "sistema": st.column_config.TextColumn(
                                        "Sistema",
                                        width=100,
                                        help="Sistema consultado"
                                    ),
                                    "status": st.column_config.TextColumn(
                                        "Situação",
                                        width=100,
                                        help="Status da verificação"
                                    ),
                                    "observacoes": st.column_config.TextColumn(
                                        "Detalhes da Restrição",
                                        width=500,
                                        help="Informações sobre a restrição encontrada"
                                    ),
                                },
                                hide_index=True,
                                use_container_width=True,
                                height=None
                            )
                            st.markdown("---")
            else:
                st.info("Nenhuma consulta realizada ainda.")
                
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {str(e)}")
    
    elif opcao == "Alertas de Impedimentos":
        st.header("🚨 Alertas de Impedimentos")
        
        # Buscar empresas com impedimentos
        monitor = MonitorEmpresas()
        empresas_impedidas = monitor.buscar_empresas_impedidas()
        
        if empresas_impedidas:
            st.warning(f"⚠️ Encontrados impedimentos em {len(empresas_impedidas)} empresa(s)")
            
            for empresa in empresas_impedidas:
                with st.expander(f"📋 {empresa['razao_social']} - CNPJ: {empresa['cnpj']}", expanded=False):
                    # Cabeçalho com dados da empresa
                    st.markdown(f"""
                    **Empresa:** {empresa['razao_social']}
                    **CNPJ:** {empresa['cnpj']}
                    **Última consulta:** {empresa['ultima_consulta'].strftime('%d/%m/%Y %H:%M')}
                    """)
                    
                    # Tabela de impedimentos
                    df = pd.DataFrame(empresa['impedimentos'])
                    df['Hora'] = pd.to_datetime(df['data_verificacao']).dt.strftime('%H:%M')
                    
                    # Formatar colunas para melhor visualização
                    df = df[['Hora', 'Sistema', 'Status', 'Observações']]
                    df['Status'] = df['Status'].apply(lambda x: 
                        "❌ Irregular" if x == "Irregular" else "✅ Regular")
                    
                    # Ajustar largura das colunas e permitir quebra de linha nas observações
                    st.dataframe(
                        df,
                        column_config={
                            "Hora": st.column_config.TextColumn(width=100),
                            "Sistema": st.column_config.TextColumn(width=150),
                            "Status": st.column_config.TextColumn(width=150),
                            "Observações": st.column_config.TextColumn(
                                width="medium",
                                help="Detalhes da sanção/impedimento"
                            ),
                        },
                        hide_index=True,
                        height=300  # Altura fixa para comportar múltiplas linhas
                    )
        else:
            st.success("✅ Nenhum impedimento encontrado")
    
    elif opcao == "Certidões Negativas":
        st.header("📄 Certidões Negativas")
        
        # Tabs para diferentes funcionalidades
        tab1, tab2 = st.tabs(["📋 Lista de Certidões", "➕ Adicionar Certidão"])
        
        with tab1:
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_status = st.selectbox(
                    "Status",
                    ["Todas", "Regulares", "Vencidas", "A vencer em 30 dias"]
                )
            with col2:
                filtro_tipo = st.selectbox(
                    "Tipo de Certidão",
                    ["Todas", "FGTS", "Federal", "Estadual", "Municipal", "Trabalhista"]
                )
            
            # Lista de certidões
            certidoes = monitor.listar_certidoes(status=filtro_status, tipo=filtro_tipo)
            
            for empresa in certidoes:
                with st.expander(f"🏢 {empresa['razao_social']} - {empresa['cnpj']}"):
                    for certidao in empresa['certidoes']:
                        status_icon = "✅" if certidao['status'] else "❌"
                        dias_validade = (datetime.strptime(certidao['data_validade'], '%Y-%m-%d').date() - datetime.now().date()).days
                        
                        col1, col2 = st.columns([3,1])
                        with col1:
                            st.markdown(f"""
                                ### {status_icon} {certidao['tipo']}
                                - **Validade**: {datetime.strptime(certidao['data_validade'], '%Y-%m-%d').strftime('%d/%m/%Y')} ({dias_validade} dias)
                                - **Número**: {certidao['numero_certidao']}
                                - **Observações**: {certidao['observacoes'] or ''}
                            """)
                        
                        with col2:
                            if certidao['arquivo_url']:
                                st.download_button(
                                    "📥 Download",
                                    monitor.supabase.storage.from_('certidoes').download(certidao['arquivo_url']),
                                    certidao['arquivo_url'].split('/')[-1]
                                )
        
        with tab2:
            st.subheader("Consulta Automática de Certidões")
            
            # Seleciona empresa
            empresas = monitor.listar_empresas()
            if empresas:
                empresa_selecionada = st.selectbox(
                    "Empresa",
                    options=empresas,
                    format_func=lambda x: f"{x.get('razao_social', '')} - {x.get('cnpj', '')}"
                )
            
            if empresa_selecionada:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔄 Consultar Certidão Trabalhista"):
                        with st.spinner("Consultando..."):
                            certidao = monitor.consultar_certidao_trabalhista(
                                empresa_selecionada['cnpj']
                            )
                            if certidao:
                                st.success("✅ Certidão trabalhista atualizada!")
                            else:
                                st.error("❌ Erro ao consultar certidão")
                
                # Futuros botões para outras certidões
                with col2:
                    st.button("🔄 Consultar FGTS", disabled=True, 
                             help="Em desenvolvimento - Requer certificado digital")
                
                with col3:
                    st.button("🔄 Consultar Federal", disabled=True,
                             help="Em desenvolvimento - Requer certificado digital")

                with col2:
                    # Link para o portal de certidões da CGU
                    st.markdown("""
                        <a href='https://certidoes.cgu.gov.br/' target='_blank'>
                            <button style='
                                background-color: #0066cc;
                                color: white;
                                padding: 8px 15px;
                                border: none;
                                border-radius: 5px;
                                cursor: pointer;
                                width: 100%;
                            '>
                                🔗 Emitir Certidão
                            </button>
                        </a>
                    """, unsafe_allow_html=True)
    
    elif opcao == "CADIN/CFIL RS":
        st.header("Consulta CADIN/CFIL RS")
        
        # Tabs para diferentes tipos de consulta
        tab1, tab2, tab3 = st.tabs(["📋 Consulta Individual", "📊 Consulta em Lote", "🔄 Consulta Completa"])
        
        with tab1:
            # Input do CNPJ com formatação
            cnpj = st.text_input(
                "Digite o CNPJ:",
                help="Digite apenas números"
            )
            
            if st.button("🔍 Consultar", use_container_width=True) and cnpj:
                with st.spinner("Consultando CADIN/CFIL RS..."):
                    resultado = monitor.consultar_cadin_rs(cnpj)
                    if resultado:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("CADIN")
                            status = "✅ Regular" if resultado['cadin']['status'] else "❌ Irregular"
                            st.markdown(f"**Status:** {status}")
                            st.markdown(f"**Observações:** {resultado['cadin']['observacoes']}")
                        
                        with col2:
                            st.subheader("CFIL")
                            status = "✅ Regular" if resultado['cfil']['status'] else "❌ Irregular"
                            st.markdown(f"**Status:** {status}")
                            st.markdown(f"**Observações:** {resultado['cfil']['observacoes']}")
    
        with tab2:
            st.subheader("Selecione as empresas para consulta:")
            empresas_selecionadas = st.multiselect(
                "Empresas:",
                options=[{
                    'id': emp['id'],
                    'cnpj': emp['cnpj'],
                    'razao_social': emp['razao_social']
                } for emp in monitor.listar_empresas()],
                format_func=lambda x: f"{x['razao_social']} ({x['cnpj']})"
            )
            
            if st.button("🔍 Consultar Selecionadas", key="btn_consulta_lote"):
                if not empresas_selecionadas:
                    st.warning("Selecione pelo menos uma empresa para consultar")
                else:
                    with st.spinner(f"Consultando {len(empresas_selecionadas)} empresas..."):
                        # Usa apenas as empresas selecionadas
                        resultados = monitor.consultar_cadin_rs_lote(empresas_selecionadas)
                        
                        if resultados:
                            for i, empresa in enumerate(empresas_selecionadas):  # Itera apenas sobre selecionadas
                                # ... resto do código ...
        
        with tab3:
            st.subheader("Consulta Completa")
            
            # Busca todas as empresas antes do botão
            empresas = monitor.listar_empresas()
            total_empresas = len(empresas) if empresas else 0
            
            st.write(f"Esta opção irá consultar todas as {total_empresas} empresas da base de dados.")
            
            # Adiciona confirmação antes de iniciar
            col1, col2 = st.columns([1,3])
            with col1:
                iniciar_consulta = st.button("🔍 Iniciar Consulta", key="btn_consulta_completa")
            
            if iniciar_consulta:
                # Mostra diálogo de confirmação
                confirmar = st.warning("Deseja realmente iniciar a consulta completa?")
                col1, col2 = st.columns([1,3])
                with col1:
                    cancelar = st.button("❌ Cancelar")
                
                if confirmar and not cancelar:
                    with st.spinner(f"Consultando todas as {total_empresas} empresas da base de dados..."):
                        if not empresas:
                            st.warning("Nenhuma empresa cadastrada.")
                        else:
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            time_text = st.empty()
                            
                            start_time = time.time()
                            resultados = monitor.consultar_cadin_rs_lote(empresas)
                            
                            if resultados:
                                for i, empresa in enumerate(empresas):
                                    cnpj = empresa['cnpj']
                                    if cnpj in resultados:
                                        with st.expander(f"🏢 {empresa['razao_social']} - {cnpj}", expanded=False):
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                status = "✅ Regular" if resultados[cnpj]['cadin']['status'] else "❌ Irregular"
                                                st.markdown(f"**CADIN:** {status}")
                                                st.markdown(f"**Obs:** {resultados[cnpj]['cadin']['observacoes']}")
                                            with col2:
                                                status = "✅ Regular" if resultados[cnpj]['cfil']['status'] else "❌ Irregular"
                                                st.markdown(f"**CFIL:** {status}")
                                                st.markdown(f"**Obs:** {resultados[cnpj]['cfil']['observacoes']}")
                                        
                                    progress = (i + 1) / len(empresas)
                                    progress_bar.progress(progress)
                                    
                                    elapsed_time = time.time() - start_time
                                    avg_time = elapsed_time / (i + 1)
                                    remaining_time = avg_time * (len(empresas) - (i + 1))
                                    
                                    status_text.text(f"Processando... {i + 1} de {len(empresas)} empresas")
                                    time_text.text(f"⏱️ Tempo estimado restante: {int(remaining_time/60)}min {int(remaining_time%60)}s")
                                
                                status_text.text("✅ Consulta completa finalizada!")
                                time_text.text(f"⏱️ Tempo total: {int((time.time() - start_time)/60)}min {int((time.time() - start_time)%60)}s")
                            else:
                                st.error("Erro ao realizar consultas")
    
    elif opcao == "🔄 Atualizar Base":
        st.header("Administração da Base de Dados")
        
        # Criar abas para diferentes operações
        tab1, tab2 = st.tabs(["⚠️ Limpeza Total", "⚡ Limpeza Seletiva"])
        
        with tab1:
            st.warning("⚠️ Esta operação irá deletar TODOS os dados do sistema!")
            
            # Adiciona nota sobre o tempo de atualização
            st.info("ℹ️ Nota: Após a limpeza, pode levar alguns segundos até todos os dados desaparecerem da interface.")
            
            col1, col2 = st.columns([3,1])
            with col1:
                if st.button("🗑️ Limpar Base de Dados", use_container_width=True):
                    if 'confirmar_limpeza' not in st.session_state:
                        st.session_state.confirmar_limpeza = False
                    
                    if st.session_state.confirmar_limpeza:
                        monitor = MonitorEmpresas()
                        
                        with st.spinner("Limpando base de dados..."):
                            progress_placeholder = st.empty()
                            
                            resultado = monitor.limpar_base_dados(
                                callback=lambda msg: progress_placeholder.info(msg)
                            )
                            
                            if resultado:
                                st.success(
                                    f"Base limpa com sucesso!\n\n"
                                    f"- {resultado['monitoramentos']} monitoramentos removidos\n"
                                    f"- {resultado['empresas']} empresas removidas\n\n"
                                    "Aguarde alguns segundos para a atualização completa da interface."
                                )
                                # Adiciona um timer visual
                                with st.spinner("Atualizando interface..."):
                                    time.sleep(3)  # Dá tempo para o Supabase sincronizar
                            else:
                                st.error("Erro ao limpar base de dados")
                            
                            st.session_state.confirmar_limpeza = False
                    else:
                        st.warning("Clique novamente para confirmar a limpeza total da base")
                        st.session_state.confirmar_limpeza = True
        
        with tab2:
            st.info("Limpe apenas registros antigos mantendo o histórico recente")
            
            col1, col2 = st.columns([2,1])
            with col1:
                dias = st.slider("Manter registros dos últimos X dias:", 
                               min_value=7, max_value=180, value=30)
            
            if st.button("⚡ Limpar Registros Antigos", use_container_width=True):
                monitor = MonitorEmpresas()
                
                with st.spinner("Limpando registros antigos..."):
                    progress_placeholder = st.empty()
                    
                    total = monitor.limpar_registros_antigos(
                        dias=dias,
                        callback=lambda msg: progress_placeholder.info(msg)
                    )
                    
                    if total is not None:
                        st.success(f"✓ {total} registros antigos removidos com sucesso!")
                    else:
                        st.error("Erro ao limpar registros antigos")

if __name__ == '__main__':
    main() 