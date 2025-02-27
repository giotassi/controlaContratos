from supabase import create_client
import os
from datetime import datetime, date, timedelta
import pandas as pd
from dotenv import load_dotenv
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import warnings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO

# Desabilitar avisos do TensorFlow
logging.getLogger('tensorflow').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Debug: imprimir as variáveis
print("URL:", SUPABASE_URL)
print("Conectando ao Supabase...")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Conexão com Supabase estabelecida com sucesso!")
except Exception as e:
    print(f"Erro ao conectar com Supabase: {e}")
    print(f"Tipo do erro: {type(e)}")
    exit()

class MonitorEmpresas:
    def __init__(self):
        """Inicializa o monitor de empresas"""
        # Obtém credenciais do ambiente
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.api_key = '0a5acb096acf4893c84d90e3ae1ff2e9'  # Chave API do Portal da Transparência
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY precisam estar definidas nas variáveis de ambiente")
        
        print("Conectando ao Supabase...")
        
        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            print("Conexão com Supabase estabelecida com sucesso!")
        except Exception as e:
            print(f"Erro ao conectar com Supabase: {str(e)}")
            raise e
        self.tipos_verificacao = {
            'CADIN': 'Cadastro de Inadimplentes',
            'CFIL': 'Cadastro de Fornecedores Impedidos de Licitar',
            'CEIS': 'Cadastro de Empresas Inidôneas e Suspensas',
            'CNEP': 'Cadastro Nacional de Empresas Punidas',
            'CND_FEDERAL': 'Certidão Negativa de Débitos Federais',
            'CND_ESTADUAL': 'Certidão Negativa de Débitos Estaduais',
            'CND_MUNICIPAL': 'Certidão Negativa de Débitos Municipais',
            'CND_TRABALHISTA': 'Certidão Negativa de Débitos Trabalhistas',
            'CRF_FGTS': 'Certificado de Regularidade do FGTS',
            'CEIS_FEDERAL': 'Certidão Negativa de Débitos Federais',
            'CEIS_ESTADUAL': 'Certidão Negativa de Débitos Estaduais'
        }

    def verificar_certidao(self, cnpj: str, tipo: str):
        """
        Verifica uma certidão específica para um CNPJ
        Retorna: (status, data_validade, observacoes)
        """
        try:
            if tipo == 'CND_FEDERAL':
                # Implementar verificação no site da Receita Federal
                return True, "2024-12-31", "Certidão válida"
            
            elif tipo == 'CND_ESTADUAL':
                # Implementar verificação no site da SEFAZ-RS
                return True, "2024-12-31", "Certidão válida"
            
            elif tipo == 'CND_MUNICIPAL':
                # Implementar verificação no site da prefeitura
                return True, "2024-12-31", "Certidão válida"
            
            elif tipo == 'CND_TRABALHISTA':
                # Implementar verificação no site do TST
                return True, "2024-12-31", "Certidão válida"
            
            elif tipo == 'CRF_FGTS':
                # Implementar verificação no site da Caixa
                return True, "2024-12-31", "Certificado válido"
            
            else:
                return False, None, f"Tipo de verificação '{tipo}' não implementado"
                
        except Exception as e:
            return False, None, f"Erro ao verificar certidão: {str(e)}"

    def verificar_ceis_estadual(self, cnpj: str):
        """
        Verifica CEIS Estadual via web scraping
        """
        try:
            print("Iniciando verificação CEIS Estadual...")
            
            # Configurar o Chrome em modo headless
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")  # Novo modo headless
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-browser-side-navigation")
            
            print("Iniciando Chrome...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            try:
                print("Acessando site do Portal da Transparência RS...")
                driver.get("https://www.transparencia.rs.gov.br/webpart/system/SancoesApenados.aspx")
                
                print("Aguardando carregamento da página...")
                wait = WebDriverWait(driver, 20)
                
                print("Procurando campo de CNPJ...")
                cnpj_input = wait.until(
                    EC.presence_of_element_located((By.ID, "txtCNPJ"))
                )
                print(f"Preenchendo CNPJ: {cnpj}")
                cnpj_input.send_keys(cnpj)
                
                print("Procurando botão 'Pesquisar'...")
                pesquisar_btn = wait.until(
                    EC.element_to_be_clickable((By.ID, "btnPesquisar"))
                )
                print("Clicando em 'Pesquisar'...")
                pesquisar_btn.click()
                
                print("Aguardando resultados...")
                time.sleep(5)
                
                try:
                    print("Verificando resultados...")
                    registros = driver.find_elements(By.XPATH, "//table[@id='grdSancoes']//tr")
                    if len(registros) > 1:
                        return False, "Empresa possui registro no CEIS Estadual"
                    else:
                        return True, "Sem impedimentos no CEIS Estadual"
                except Exception as e:
                    print(f"Erro ao verificar resultados: {str(e)}")
                    return True, "Sem impedimentos no CEIS Estadual"
                
            finally:
                print("Fechando navegador...")
                driver.quit()
                
        except Exception as e:
            print(f"Erro ao verificar CEIS Estadual: {str(e)}")
            return False, f"Erro ao verificar CEIS Estadual: {str(e)}"

    def verificar_ceis_federal(self, cnpj: str):
        """
        Verifica CEIS Federal via web scraping
        """
        try:
            print("Iniciando verificação CEIS Federal...")
            
            # Configurar o Chrome em modo headless
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")  # Novo modo headless
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-browser-side-navigation")
            
            print("Iniciando Chrome...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            try:
                print("Acessando Portal da Transparência...")
                driver.get("https://portaldatransparencia.gov.br/sancoes/consulta?cadastro=1&ordenarPor=nomeSancionado&direcao=asc")
                
                wait = WebDriverWait(driver, 20)
                
                print("Procurando campo de CPF/CNPJ...")
                # Primeiro clica no campo CPF/CNPJ SANCIONADO
                campo_cpf_cnpj = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'CPF / CNPJ sancionado')]"))
                )
                print("Clicando no campo CPF/CNPJ...")
                campo_cpf_cnpj.click()
                
                # Agora clica no campo para digitar
                input_cpf_cnpj = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='CPF / CNPJ sancionado']"))
                )
                print(f"Preenchendo CNPJ: {cnpj}")
                input_cpf_cnpj.click()
                input_cpf_cnpj.send_keys(cnpj)
                
                print("Procurando botão 'Adicionar'...")
                adicionar_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar')]"))
                )
                print("Clicando em 'Adicionar' (primeira vez)...")
                adicionar_btn.click()
                
                time.sleep(2)  # Pequena pausa entre os cliques
                
                print("Clicando em 'Adicionar' (segunda vez)...")
                adicionar_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar')]"))
                )
                adicionar_btn.click()
                
                print("Procurando botão 'Consultar'...")
                consultar_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Consultar')]"))
                )
                print("Clicando em 'Consultar'...")
                consultar_btn.click()
                
                time.sleep(5)  # Aguarda carregamento dos resultados
                
                try:
                    print("Verificando resultados...")
                    # Procura por linhas na tabela de resultados
                    resultados = driver.find_elements(By.XPATH, "//table//tbody/tr")
                    if len(resultados) > 0:
                        return False, "Empresa possui registro no CEIS Federal"
                    return True, "Sem impedimentos no CEIS Federal"
                except Exception as e:
                    print(f"Erro ao verificar resultados: {str(e)}")
                    return False, f"Erro ao verificar resultados: {str(e)}"
                
            finally:
                print("Fechando navegador...")
                driver.quit()
                
        except Exception as e:
            print(f"Erro ao verificar CEIS Federal: {str(e)}")
            return False, f"Erro ao verificar CEIS Federal: {str(e)}"

    def validar_cnpj(self, cnpj: str) -> bool:
        """
        Valida o formato e os dígitos verificadores do CNPJ
        """
        try:
            # Remove caracteres não numéricos
            cnpj = ''.join(filter(str.isdigit, cnpj))
            
            # Verifica se tem 14 dígitos
            if len(cnpj) != 14:
                print(f"CNPJ com tamanho inválido: {len(cnpj)} dígitos")
                return False
                
            # Verifica se todos os dígitos são iguais
            if len(set(cnpj)) == 1:
                print("CNPJ com todos os dígitos iguais")
                return False
                
            # Cálculo do primeiro dígito verificador
            soma = sum(int(cnpj[i]) * (6 - (i + 1) if i < 4 else 14 - (i + 1)) for i in range(12))
            digito1 = 11 - (soma % 11)
            digito1 = 0 if digito1 > 9 else digito1
            
            # Cálculo do segundo dígito verificador
            soma = sum(int(cnpj[i]) * (7 - (i + 1) if i < 5 else 15 - (i + 1)) for i in range(13))
            digito2 = 11 - (soma % 11)
            digito2 = 0 if digito2 > 9 else digito2
            
            # Verifica os dígitos calculados com os dígitos informados
            if int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2:
                print(f"CNPJ válido: {cnpj}")
                return True
            else:
                print(f"Dígitos verificadores inválidos. Esperado: {digito1}{digito2}, Recebido: {cnpj[12]}{cnpj[13]}")
                return False
                
        except Exception as e:
            print(f"Erro ao validar CNPJ: {str(e)}")
            return False

    def verificar_impedimentos(self, cnpj: str):
        """
        Verifica impedimentos em todos os cadastros via CGU
        """
        try:
            print("Iniciando verificação via CGU...")
            
            # Validar CNPJ antes de prosseguir
            if not self.validar_cnpj(cnpj):
                print("CNPJ inválido: {}".format(cnpj))
                return {
                    cadastro: {
                        'status': False,
                        'observacoes': "CNPJ inválido - Verificação não realizada"
                    } for cadastro in ['CEIS', 'CNEP', 'CEPIM', 'CGU-PJ', 'ePAD']
                }
            
            # Limpar CNPJ - remover pontos, traços e barras
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            print("CNPJ válido, prosseguindo com a verificação: {}".format(cnpj_limpo))
            
            # Configurar o Chrome com opções adicionais para menor consumo de recursos
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")  # Modo headless novo
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-browser-side-navigation")
            chrome_options.add_argument("--disable-features=EnableTensorFlowLiteDelegate")
            chrome_options.add_argument("--disable-javascript")  # Desabilita JS quando possível
            chrome_options.add_argument("--window-size=800,600")  # Janela menor
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # Desabilita imagens
            chrome_options.add_argument("--disk-cache-size=1")  # Cache mínimo
            chrome_options.add_argument("--media-cache-size=1")  # Cache de mídia mínimo
            chrome_options.add_argument("--process-per-site")  # Reduz processos
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-notifications")
            
            print("Iniciando Chrome...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            resultados = {}
            
            try:
                print("Acessando portal da CGU...")
                driver.get("https://certidoes.cgu.gov.br/")
                
                wait = WebDriverWait(driver, 20)
                
                # Marcar a checkbox da certidão
                print("Selecionando tipo de certidão...")
                certidao_checkbox = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox' and ancestor::tr[contains(., 'Certidão negativa correcional - Entes Privados')]]"))
                )
                print("Checkbox encontrada, tentando clicar...")
                certidao_checkbox.click()
                
                # Preencher CNPJ
                print("Procurando campo de CNPJ...")
                cnpj_input = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'CPF/CNPJ')]/following-sibling::input"))
                )
                print(f"Campo encontrado, preenchendo CNPJ: {cnpj_limpo}")
                cnpj_input.clear()
                for digito in cnpj_limpo:
                    cnpj_input.send_keys(digito)
                    time.sleep(0.1)
                
                print("Aguardando campo ser preenchido...")
                time.sleep(1)
                
                # Clicar em Consultar
                print("Procurando botão Consultar...")
                consultar_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Consultar')]"))
                )
                print("Clicando em Consultar...")
                consultar_btn.click()
                
                # Aguardar resultados e voltar ao topo da página
                print("Aguardando resultados...")
                time.sleep(5)
                
                # Scroll para o topo da página
                print("Voltando ao topo da página...")
                driver.execute_script("window.scrollTo(0, 0)")
                time.sleep(3)
                
                # Lista de cadastros a verificar
                cadastros = ['CEIS', 'CNEP', 'CEPIM', 'CGU-PJ', 'ePAD']
                
                # Verificar cada cadastro
                for cadastro in cadastros:
                    print(f"\nVerificando {cadastro}...")
                    try:
                        # Encontra a célula com o nome do cadastro
                        nome_cell = wait.until(
                            EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{cadastro}']"))
                        )
                        
                        # Pega a célula seguinte (status)
                        status_cell = nome_cell.find_element(By.XPATH, "following-sibling::td")
                        
                        # Tenta encontrar link primeiro
                        try:
                            link = status_cell.find_element(By.TAG_NAME, "a")
                            url = link.get_attribute('href')
                            print(f"Link de restrição encontrado em {cadastro}: {url}")
                            
                            # Armazena apenas uma vez
                            if cadastro not in resultados:
                                resultados[cadastro] = {
                                    'status': False,
                                    'observacoes': "Encontrada restrição no {} - Ver detalhes em: {}".format(cadastro, url)
                                }
                        except:
                            # Se não encontrar link, verifica o texto
                            situacao = status_cell.text.strip()
                            print(f"Status {cadastro}: {situacao}")
                            
                            # Armazena apenas se ainda não foi registrado
                            if cadastro not in resultados:
                                if "Nada Consta" in situacao:
                                    resultados[cadastro] = {
                                        'status': True,
                                        'observacoes': "Sem registros no {}".format(cadastro)
                                    }
                                else:
                                    resultados[cadastro] = {
                                        'status': False,
                                        'observacoes': "Situação {}".format(cadastro) + situacao
                                    }
                            
                    except Exception as e:
                        print(f"Erro ao verificar {cadastro}: {str(e)}")
                        if cadastro not in resultados:
                            resultados[cadastro] = {
                                'status': False,
                                'observacoes': "Erro ao verificar {}".format(cadastro)
                            }
                
                return resultados
                
            finally:
                print("Aguardando 5 segundos antes de fechar...")
                time.sleep(5)
                print("Fechando navegador...")
                driver.quit()
                
        except Exception as e:
            print(f"Erro geral na verificação CGU: {str(e)}")
            return {cadastro: {'status': False, 'observacoes': "Erro na verificação"} for cadastro in ['CEIS', 'CNEP', 'CEPIM', 'CGU-PJ', 'ePAD']}

    def testar_api(self):
        """Testa se a API está respondendo e autorizada"""
        try:
            base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
            headers = {
                'Accept': 'application/json',
                'chave-api-dados': self.api_key
            }
            
            # Teste rápido com CNPJ conhecido
            response = requests.get(
                f"{base_url}/ceis",
                headers=headers,
                params={'pagina': 1, 'codigoSancionado': '00000000000191'}
            )
            
            return response.status_code == 200
        except:
            return False

    def verificar_impedimentos_api(self, cnpj, callback=None):
        """Verifica impedimentos via API oficial"""
        def update_status(message):
            if callback:
                callback(message)
            print(message)  # Mantém o print para logs
        
        try:
            update_status("Iniciando verificação de impedimentos...")
            
            # Primeiro verifica se a empresa existe
            update_status("Verificando cadastro da empresa...")
            empresa = self.supabase.table('empresas').select("*").eq('cnpj', cnpj).execute()
            
            empresa_id = None
            if not empresa.data:
                update_status(f"Empresa {cnpj} não encontrada. Cadastrando...")
                # Cadastra a empresa e obtém o ID
                nova_empresa = self.supabase.table('empresas').insert({
                    'cnpj': cnpj,
                    'razao_social': 'Empresa em Consulta',
                    'objeto_contrato': 'Consulta Individual'
                }).execute()
                
                if nova_empresa.data:
                    empresa_id = nova_empresa.data[0]['id']
                    update_status(f"Empresa cadastrada com ID: {empresa_id}")
                else:
                    raise Exception("Erro ao cadastrar empresa")
            else:
                empresa_id = empresa.data[0]['id']
                update_status(f"Empresa encontrada com ID: {empresa_id}")
            
            # Teste rápido antes de autorizar
            update_status("Verificando autorização da API...")
            if not self.testar_api():
                update_status("API não autorizada. Iniciando processo de autorização...")
                if not self.autorizar_api(callback=update_status):
                    raise Exception("Falha na autorização da API")
                
                if not self.testar_api():
                    raise Exception("API continua não autorizada após tentativa de autorização")
            
            update_status("API autorizada. Iniciando consultas...")
            
            # Configuração da API
            base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
            headers = {
                'Accept': 'application/json',
                'chave-api-dados': self.api_key
            }
            
            # Endpoints e parâmetros
            endpoints = {
                'CEIS': {'url': f"{base_url}/ceis", 'params': {'pagina': 1, 'codigoSancionado': cnpj}},
                'CNEP': {'url': f"{base_url}/cnep", 'params': {'pagina': 1, 'codigoSancionado': cnpj}},
                'CEPIM': {'url': f"{base_url}/cepim/consulta/pessoa-juridica", 'params': {'numeroInscricao': cnpj}}
            }
            
            resultados = {}
            
            # Consulta cada endpoint
            for sistema, config in endpoints.items():
                try:
                    update_status(f"Consultando {sistema}...")
                    response = requests.get(config['url'], headers=headers, params=config['params'])
                    update_status(f"Status {sistema}: {response.status_code}")
                    
                    if response.status_code == 200:
                        try:
                            # Trata resposta vazia
                            if not response.text.strip():
                                dados = []
                            else:
                                dados = response.json()
                            
                            resultados[sistema] = {
                                'status': len(dados) == 0,
                                'observacoes': self.formatar_resultados(dados, sistema) if dados else "Nenhum registro encontrado"
                            }
                            
                            # Salva no banco usando o ID correto da empresa
                            monitoramento = self.supabase.table('monitoramentos').insert({
                                'empresa_id': empresa_id,
                                'tipo_verificacao': sistema,
                                'status': resultados[sistema]['status'],
                                'observacoes': resultados[sistema]['observacoes'],
                                'data_verificacao': datetime.now().isoformat()
                            }).execute()
                            
                            update_status(f"Dados de {sistema} salvos com sucesso")
                            
                        except json.JSONDecodeError:
                            update_status(f"Resposta vazia de {sistema}")
                            resultados[sistema] = {
                                'status': True,  # Consideramos sem restrições se não há dados
                                'observacoes': "Nenhum registro encontrado"
                            }
                
                except Exception as e:
                    update_status(f"Erro ao consultar {sistema}: {str(e)}")
                    continue
            
            update_status("Verificação concluída!")
            return resultados
            
        except Exception as e:
            update_status(f"Erro na verificação de impedimentos: {str(e)}")
            return None

    def autorizar_api(self, callback=None):
        """Testa autorização da API do Portal da Transparência usando Selenium"""
        def update_status(message):
            if callback:
                callback(message)
            print(message)  # Mantém o print para logs
        
        try:
            print(f"Iniciando autorização com chave: {self.api_key}")
            
            # Configura o Chrome para rodar em background
            options = webdriver.ChromeOptions()
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Inicia Chrome em background
            driver = webdriver.Chrome(options=options)
            print("Chrome iniciado em background")
            
            # Acessa a página
            driver.get("https://api.portaldatransparencia.gov.br/swagger-ui/index.html")
            print("Página carregada")
            
            # Clica no botão Authorize
            authorize_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "authorize"))
            )
            authorize_button.click()
            print("Clicou no botão Authorize")
            
            time.sleep(1)
            
            # Envia a chave
            actions = webdriver.ActionChains(driver)
            actions.send_keys(self.api_key)
            actions.perform()
            print("Enviou a chave API")
            
            # Clica no botão Authorize do modal
            modal_authorize = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal-btn.auth.authorize.button"))
            )
            modal_authorize.click()
            print("Clicou em Authorize no modal")
            
            time.sleep(1)
            
            # Fecha o modal
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal-btn.auth.btn-done.button"))
            )
            close_button.click()
            print("Modal fechado")
            
            # Verifica se o botão Authorize mudou de estado
            time.sleep(1)
            authorize_button = driver.find_element(By.CLASS_NAME, "authorize")
            button_class = authorize_button.get_attribute("class")
            print(f"Classes do botão: {button_class}")
            
            if "locked" not in button_class:
                print("Autorização não persistiu!")
                return False
            
            print("Autorização confirmada no portal!")
            return True
            
        except Exception as e:
            print(f"Erro na autorização: {str(e)}")
            return False
        finally:
            if 'driver' in locals():
                driver.quit()

    def verificar_empresa(self, empresa_id: int):
        """
        Realiza todas as verificações para uma empresa via APIs
        """
        try:
            # Buscar dados da empresa
            empresa = self.supabase.table('empresas').select("*").eq('id', empresa_id).execute()
            if not empresa.data:
                return f"Empresa ID {empresa_id} não encontrada"
            
            empresa = empresa.data[0]
            cnpj = empresa['cnpj']
            print(f"\nVerificando empresa: {empresa['razao_social']}")
            print(f"CNPJ: {cnpj}")
            print("-" * 50)
            
            resultados = []

            # Verificar impedimentos via APIs
            impedimentos_api = self.verificar_impedimentos_api(cnpj)
            if isinstance(impedimentos_api, dict):
                for tipo, resultado in impedimentos_api.items():
                    if isinstance(resultado, dict):
                        self.registrar_monitoramento(
                            empresa_id=empresa_id,
                            tipo=tipo,
                            status=resultado.get('status', False),
                            observacoes=resultado.get('observacoes', 'Erro na verificação')
                        )
                        resultados.append(f"{tipo}: {resultado.get('observacoes', 'Erro na verificação')}")

            print("\nResultados da verificação:")
            print("-" * 50)
            return "\n".join(sorted(list(set(resultados))))  # Remove duplicatas e ordena

        except Exception as e:
            print(f"Erro ao verificar empresa: {str(e)}")
            return f"Erro ao verificar empresa: {str(e)}"

    def adicionar_empresa(self, cnpj: str, razao_social: str, objeto_contrato: str = None):
        """
        Adiciona uma nova empresa ou retorna a existente
        """
        try:
            # Primeiro verifica se a empresa já existe
            empresa_existente = self.supabase.table('empresas').select("*").eq('cnpj', cnpj).execute()
            
            if empresa_existente.data:
                print(f"Empresa com CNPJ {cnpj} já cadastrada.")
                return empresa_existente.data[0]
            
            # Se não existe, adiciona nova empresa
            data = {
                "cnpj": cnpj,
                "razao_social": razao_social,
                "objeto_contrato": objeto_contrato
            }
            
            response = self.supabase.table('empresas').insert(data).execute()
            print(f"Nova empresa cadastrada com sucesso: {razao_social}")
            return response.data[0]
            
        except Exception as e:
            print(f"Erro ao adicionar empresa: {e}")
            return None

    def registrar_monitoramento(self, empresa_id: int, tipo: str, status: bool, 
                              data_validade=None, observacoes: str = None):
        try:
            data = {
                "empresa_id": empresa_id,
                "tipo_verificacao": tipo,
                "status": status,
                "data_validade": data_validade,
                "observacoes": observacoes
            }
            
            response = self.supabase.table('monitoramentos').insert(data).execute()
            return response.data[0]
        except Exception as e:
            print(f"Erro ao registrar monitoramento: {e}")
            return None

    def listar_empresas(self):
        try:
            response = self.supabase.from_('empresas').select('*').execute()
            if response.data:
                return response.data  # Retorna a lista de dicionários diretamente
            return []
        except Exception as e:
            print(f"Erro ao listar empresas: {e}")
            return []

    def importar_planilha(self, arquivo):
        """
        Importa planilha com CNPJs e nomes das empresas
        """
        try:
            print("Iniciando importação da planilha...")
            empresas = []
            
            # Lê a planilha
            df = pd.read_excel(arquivo)
            print(f"Colunas encontradas: {df.columns.tolist()}")
            
            # Normaliza os nomes das colunas (remove espaços extras e acentos)
            df.columns = [col.strip().upper() for col in df.columns]
            
            # Mapeia as possíveis variações dos nomes das colunas
            coluna_cnpj = next((col for col in df.columns if 'CPF' in col or 'CNPJ' in col), None)
            coluna_nome = next((col for col in df.columns if 'CONTRATADO' in col or 'EMPRESA' in col or 'RAZAO' in col), None)
            
            print(f"Usando colunas: CNPJ='{coluna_cnpj}', Nome='{coluna_nome}'")
            
            if coluna_cnpj and coluna_nome:
                for _, row in df.iterrows():
                    cnpj = str(row[coluna_cnpj]).strip()
                    razao_social = str(row[coluna_nome]).strip()
                    
                    # Remove caracteres não numéricos do CNPJ
                    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
                    
                    if len(cnpj_limpo) == 14:  # Valida se é um CNPJ
                        print(f"Processando CNPJ: {cnpj_limpo}, Razão Social: {razao_social}")
                        
                        # Verifica se a empresa já existe
                        empresa_existente = self.supabase.from_('empresas')\
                            .select('*')\
                            .eq('cnpj', cnpj_limpo)\
                            .execute()
                        
                        if empresa_existente.data:
                            # Atualiza razão social se diferente
                            if empresa_existente.data[0]['razao_social'] == 'Empresa em Consulta':
                                print(f"Atualizando razão social para: {razao_social}")
                                self.supabase.from_('empresas')\
                                    .update({'razao_social': razao_social})\
                                    .eq('id', empresa_existente.data[0]['id'])\
                                    .execute()
                            empresa = empresa_existente.data[0]
                        else:
                            # Insere nova empresa
                            print(f"Inserindo nova empresa: {razao_social}")
                            nova_empresa = self.supabase.from_('empresas')\
                                .insert({
                                    'cnpj': cnpj_limpo,
                                    'razao_social': razao_social,
                                    'objeto_contrato': 'Importação em Lote'
                                })\
                                .execute()
                            empresa = nova_empresa.data[0]
                        
                        empresas.append({
                            'id': empresa['id'],
                            'cnpj': cnpj_limpo,
                            'razao_social': razao_social
                        })
            
            print(f"Importação concluída. {len(empresas)} empresas processadas.")
            return empresas
        except Exception as e:
            print(f"Erro ao importar planilha: {str(e)}")
            print(f"Tipo do erro: {type(e)}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return None

    def exportar_resultados(self, empresas, nome_arquivo="resultados_consulta.xlsx"):
        """
        Exporta os resultados das verificações para uma planilha Excel
        """
        try:
            resultados_list = []
            
            for empresa in empresas:
                print(f"\nProcessando resultados de: {empresa['razao_social']}")
                
                # Busca os últimos resultados de monitoramento para a empresa
                monitoramentos = self.supabase.table('monitoramentos')\
                    .select("*")\
                    .eq('empresa_id', empresa['id'])\
                    .order('data_verificacao', desc=True)\
                    .execute()
                
                if monitoramentos.data:
                    # Agrupa resultados por tipo de verificação
                    resultados = {}
                    for mon in monitoramentos.data:
                        tipo = mon['tipo_verificacao']
                        if tipo not in resultados:  # Pega apenas o resultado mais recente
                            resultados[tipo] = {
                                'status': mon['status'],
                                'observacoes': mon['observacoes'],
                                'data_verificacao': mon['data_verificacao']
                            }
                    
                    # Cria linha do DataFrame
                    row = {
                        'CNPJ': empresa['cnpj'],
                        'Razão Social': empresa['razao_social'],
                        'Objeto Contrato': empresa['objeto_contrato'],
                        'Data Verificação': max(r['data_verificacao'] for r in resultados.values())
                    }
                    
                    # Adiciona resultados de cada verificação
                    for tipo, resultado in resultados.items():
                        row[f'{tipo} - Status'] = "Regular" if resultado['status'] else "Irregular"
                        row[f'{tipo} - Observações'] = resultado['observacoes']
                    
                    resultados_list.append(row)
            
            if resultados_list:
                # Cria DataFrame e exporta para Excel
                df = pd.DataFrame(resultados_list)
                
                # Formata a data
                df['Data Verificação'] = pd.to_datetime(df['Data Verificação']).dt.strftime('%d/%m/%Y %H:%M')
                
                # Ordena as colunas
                first_cols = ['CNPJ', 'Razão Social', 'Objeto Contrato', 'Data Verificação']
                other_cols = [col for col in df.columns if col not in first_cols]
                df = df[first_cols + sorted(other_cols)]
                
                # Exporta para Excel
                df.to_excel(nome_arquivo, index=False)
                print(f"\nResultados exportados para: {nome_arquivo}")
                return True
            else:
                print("Nenhum resultado para exportar")
                return False
                
        except Exception as e:
            print(f"Erro ao exportar resultados: {str(e)}")
            return False

    def adicionar_certidao(self, empresa_id: int, tipo: str, data_emissao: date, 
                          data_validade: date, numero_certidao: str, arquivo=None):
        try:
            # Upload do arquivo se existir
            arquivo_url = None
            if arquivo:
                arquivo_url = self.upload_arquivo_certidao(arquivo)
            
            # Insere certidão
            certidao = self.supabase.table('certidoes').insert({
                'empresa_id': empresa_id,
                'tipo': tipo,
                'data_emissao': data_emissao.isoformat(),
                'data_validade': data_validade.isoformat(),
                'numero_certidao': numero_certidao,
                'status': data_validade >= date.today(),
                'arquivo_url': arquivo_url
            }).execute()
            
            return certidao.data[0]
        except Exception as e:
            print(f"Erro ao adicionar certidão: {str(e)}")
            return None

    def listar_certidoes(self, status=None, tipo=None):
        try:
            query = self.supabase.from_('certidoes').select('*, empresas(*)').order('data_validade', desc=True)
            
            if status == "Vencidas":
                query = query.lt('data_validade', date.today().isoformat())
            elif status == "Regulares":
                query = query.gte('data_validade', date.today().isoformat())
            elif status == "A vencer em 30 dias":
                data_limite = (date.today() + timedelta(days=30)).isoformat()
                query = query.lte('data_validade', data_limite).gte('data_validade', date.today().isoformat())
            
            if tipo and tipo != "Todas":
                query = query.eq('tipo', tipo)
            
            certidoes = query.execute()
            
            # Agrupa por empresa
            empresas_dict = {}
            for certidao in certidoes.data:
                empresa_id = certidao['empresa_id']
                if empresa_id not in empresas_dict:
                    empresas_dict[empresa_id] = {
                        'razao_social': certidao['empresas']['razao_social'],
                        'cnpj': certidao['empresas']['cnpj'],
                        'certidoes': []
                    }
                empresas_dict[empresa_id]['certidoes'].append(certidao)
            
            return list(empresas_dict.values())
        except Exception as e:
            print(f"Erro ao listar certidões: {str(e)}")
            return []

    def upload_arquivo_certidao(self, arquivo):
        try:
            # Upload para o storage do Supabase
            arquivo_path = f"certidoes/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo.name}"
            self.supabase.storage.from_('certidoes').upload(arquivo_path, arquivo)
            return arquivo_path
        except Exception as e:
            print(f"Erro ao fazer upload do arquivo: {str(e)}")
            return None

    def verificar_certidoes_vencimento(self):
        try:
            # Busca certidões a vencer em 30 dias
            data_limite = (date.today() + timedelta(days=30)).isoformat()
            certidoes = self.supabase.from_('certidoes')\
                .select('*, empresas(*)')\
                .lte('data_validade', data_limite)\
                .gte('data_validade', date.today().isoformat())\
                .execute()
            
            alertas = []
            for certidao in certidoes.data:
                dias_restantes = (datetime.strptime(certidao['data_validade'], '%Y-%m-%d').date() - date.today()).days
                alertas.append({
                    'empresa': certidao['empresas']['razao_social'],
                    'cnpj': certidao['empresas']['cnpj'],
                    'tipo': certidao['tipo'],
                    'validade': certidao['data_validade'],
                    'dias_restantes': dias_restantes
                })
            
            return alertas
        except Exception as e:
            print(f"Erro ao verificar certidões: {str(e)}")
            return []

    def consultar_certidao_federal(self, cnpj):
        try:
            # Busca ou cria empresa
            empresa = self.supabase.from_('empresas').select('*').eq('cnpj', cnpj).execute()
            if not empresa.data:
                empresa = self.supabase.from_('empresas').insert({
                    'cnpj': cnpj,
                    'razao_social': 'Empresa em Consulta',
                    'objeto_contrato': 'Consulta Individual'
                }).execute()
            
            empresa_id = empresa.data[0]['id']
            
            # Remove caracteres não numéricos do CNPJ
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            
            # URL da API do Portal da Transparência
            url = f"http://api.portaldatransparencia.gov.br/api-de-dados/ceis/v2/consulta/cnpj/{cnpj_limpo}"
            
            # Headers necessários
            headers = {
                'chave-api-dados': 'SUA-CHAVE-API',  # Precisa solicitar no portal
                'Accept': 'application/json'
            }
            
            # Faz a requisição
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                dados = response.json()
                
                # Processa os dados
                status = True  # Regular por padrão
                observacoes = []
                
                # Verifica impedimentos
                for impedimento in dados:
                    if impedimento['dataFinal'] is None or datetime.strptime(impedimento['dataFinal'], '%Y-%m-%d') > datetime.now():
                        status = False
                        observacoes.append(f"Impedimento: {impedimento['tipoSancao']} - {impedimento['orgaoSancionador']}")
                
                # Salva a certidão no banco
                certidao = self.supabase.table('certidoes').insert({
                    'empresa_id': empresa_id,
                    'tipo': 'Federal',
                    'data_emissao': datetime.now().date().isoformat(),
                    'data_validade': (datetime.now() + timedelta(days=30)).date().isoformat(),  # Validade de 30 dias
                    'status': status,
                    'observacoes': '; '.join(observacoes) if observacoes else 'Regular'
                }).execute()
                
                return certidao.data[0]
            
            return None
            
        except Exception as e:
            print(f"Erro ao consultar certidão federal: {str(e)}")
            return None

    def gerar_certidao_impedimentos(self, cnpj: str, resultados: dict):
        try:
            # Cria um buffer para o PDF
            buffer = BytesIO()
            
            # Configura o documento
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                title=f"Certidão de Consulta - {cnpj}"
            )
            
            # Estilos
            styles = getSampleStyleSheet()
            titulo_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30
            )
            
            # Elementos do documento
            elements = []
            
            # Título
            elements.append(Paragraph(f"Certidão de Consulta de Impedimentos", titulo_style))
            elements.append(Paragraph(f"CNPJ: {cnpj}", styles["Normal"]))
            elements.append(Paragraph(f"Data da Consulta: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles["Normal"]))
            elements.append(Spacer(1, 20))
            
            # Resultados
            for sistema, resultado in resultados.items():
                # Cabeçalho do sistema
                elements.append(Paragraph(f"Sistema: {sistema}", styles["Heading2"]))
                
                # Status
                status_text = "✓ REGULAR" if resultado['status'] else "✗ IRREGULAR"
                status_color = colors.green if resultado['status'] else colors.red
                
                data = [
                    ["Status:", status_text],
                    ["Observações:", resultado['observacoes']]
                ]
                
                # Cria tabela
                t = Table(data, colWidths=[100, 400])
                t.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('TEXTCOLOR', (1, 0), (1, 0), status_color),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BOX', (0, 0), (-1, -1), 2, colors.black),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                
                elements.append(t)
                elements.append(Spacer(1, 20))
            
            # Gera o PDF
            doc.build(elements)
            
            # Retorna o buffer
            buffer.seek(0)
            return buffer.getvalue()
            
        except Exception as e:
            print(f"Erro ao gerar certidão: {str(e)}")
            return None

    def buscar_empresa_receita(self, cnpj):
        """Busca dados da empresa na Receita Federal usando múltiplas APIs"""
        try:
            # Remove caracteres não numéricos do CNPJ
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            
            # Lista de APIs para tentar
            apis = [
                {
                    'url': f"https://receitaws.com.br/v1/cnpj/{cnpj_limpo}",
                    'headers': {}
                },
                {
                    'url': f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
                    'headers': {}
                },
                {
                    'url': f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}",
                    'headers': {}
                }
            ]
            
            for api in apis:
                try:
                    time.sleep(1)  # Delay entre requisições
                    response = requests.get(api['url'], headers=api['headers'], timeout=5)
                    
                    if response.status_code == 200:
                        dados = response.json()
                        
                        # Mapeamento diferente para cada API
                        if 'receitaws' in api['url']:
                            return {
                                'razao_social': dados.get('nome', ''),
                                'nome_fantasia': dados.get('fantasia', ''),
                                'situacao': dados.get('situacao', '')
                            }
                        elif 'brasilapi' in api['url']:
                            return {
                                'razao_social': dados.get('razao_social', ''),
                                'nome_fantasia': dados.get('nome_fantasia', ''),
                                'situacao': dados.get('descricao_situacao_cadastral', '')
                            }
                        elif 'cnpj.ws' in api['url']:
                            return {
                                'razao_social': dados.get('razao_social', ''),
                                'nome_fantasia': dados.get('estabelecimento', {}).get('nome_fantasia', ''),
                                'situacao': dados.get('estabelecimento', {}).get('situacao_cadastral', '')
                            }
                except Exception as e:
                    print(f"Erro na API {api['url']}: {str(e)}")
                    continue
                
            return None
            
        except Exception as e:
            print(f"Erro ao buscar empresa: {str(e)}")
            return None

    def formatar_resultados(self, dados, sistema):
        """Formata os resultados da consulta de acordo com o sistema"""
        try:
            if not dados:
                return "Nenhum registro encontrado"
            
            if sistema == 'CEIS':
                registros = []
                for item in dados:
                    # Trata o caso específico do descricaoResumida
                    if isinstance(item, dict) and 'descricaoResumida' in item:
                        sancao = item['descricaoResumida']
                    else:
                        sancao = item.get('tipoSancao', 'N/A')
                    
                    # Formata a data
                    data_inicio = item.get('dataInicioSancao', '')
                    if data_inicio:
                        try:
                            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
                        except:
                            pass
                    
                    data_fim = item.get('dataFimSancao', '')
                    if data_fim:
                        try:
                            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')
                        except:
                            pass
                    
                    registro = (
                        f"Sanção: {sancao}\n"
                        f"Órgão: {item.get('orgaoSancionador', 'N/A')}\n"
                        f"Início: {data_inicio}\n"
                        f"Fim: {data_fim}"
                    )
                    registros.append(registro)
                return "\n\n".join(registros)
            
            elif sistema == 'CNEP':
                registros = []
                for item in dados:
                    registro = (
                        f"Sanção: {item.get('tipoSancao', 'N/A')} - "
                        f"Órgão: {item.get('orgaoSancionador', 'N/A')} - "
                        f"Valor Multa: {item.get('valorMulta', 'N/A')}"
                    )
                    registros.append(registro)
                return " | ".join(registros)
            
            elif sistema == 'CEPIM':
                registros = []
                for item in dados:
                    registro = (
                        f"Motivo: {item.get('motivo', 'N/A')} - "
                        f"Órgão: {item.get('orgaoSuperior', 'N/A')} - "
                        f"Convênio: {item.get('numeroConvenio', 'N/A')}"
                    )
                    registros.append(registro)
                return " | ".join(registros)
            
            return "Formato não reconhecido"
            
        except Exception as e:
            print(f"Erro ao formatar resultados: {str(e)}")
            return f"Erro ao formatar resultados: {str(e)}"

    def limpar_base_dados(self, callback=None):
        """Limpa todas as tabelas do banco de dados de forma segura"""
        def update_status(message):
            if callback:
                callback(message)
            print(message)
        
        try:
            update_status("Iniciando limpeza da base de dados...")
            
            # 1. Primeiro deleta os monitoramentos usando gt para pegar todos os IDs
            update_status("Deletando registros de monitoramentos...")
            delete_monitoramentos = self.supabase.table('monitoramentos')\
                .delete()\
                .gt('id', 0)\
                .execute()
            total_monitoramentos = len(delete_monitoramentos.data) if delete_monitoramentos.data else 0
            update_status(f"✓ {total_monitoramentos} monitoramentos deletados")
            
            # 2. Depois deleta as empresas usando gt para pegar todos os IDs
            update_status("Deletando registros de empresas...")
            delete_empresas = self.supabase.table('empresas')\
                .delete()\
                .gt('id', 0)\
                .execute()
            total_empresas = len(delete_empresas.data) if delete_empresas.data else 0
            update_status(f"✓ {total_empresas} empresas deletadas")
            
            update_status("Base de dados limpa com sucesso!")
            return {
                'monitoramentos': total_monitoramentos,
                'empresas': total_empresas
            }
            
        except Exception as e:
            error_msg = f"Erro ao limpar base de dados: {str(e)}"
            update_status(error_msg)
            return None

    def buscar_empresas_impedidas(self):
        """Busca empresas com impedimentos"""
        try:
            # Busca monitoramentos com status False (irregulares)
            query = self.supabase.table('monitoramentos')\
                .select(
                    """
                    *,
                    empresas (
                        id,
                        cnpj,
                        razao_social
                    )
                    """
                )\
                .eq('status', False)\
                .order('data_verificacao', desc=True)\
                .execute()
            
            if not query.data:
                return []
            
            # Agrupa por empresa
            empresas = {}
            empresas_para_atualizar = []
            
            for mon in query.data:
                empresa_id = mon['empresa_id']
                if empresa_id not in empresas:
                    # Pega dados da empresa
                    razao_social = mon['empresas']['razao_social']
                    cnpj = mon['empresas']['cnpj']
                    
                    # Se for empresa em consulta, adiciona para atualização posterior
                    if razao_social == 'Empresa em Consulta':
                        empresas_para_atualizar.append({
                            'id': empresa_id,
                            'cnpj': cnpj
                        })
                    
                    empresas[empresa_id] = {
                        'id': empresa_id,
                        'cnpj': cnpj,
                        'razao_social': razao_social,
                        'ultima_consulta': datetime.fromisoformat(mon['data_verificacao']),
                        'impedimentos': []
                    }
                
                empresas[empresa_id]['impedimentos'].append({
                    'data_verificacao': mon['data_verificacao'],
                    'Sistema': mon['tipo_verificacao'],
                    'Status': 'Irregular',
                    'Observações': self.formatar_observacao(mon['observacoes'])
                })
            
            # Atualiza as empresas em background
            for empresa in empresas_para_atualizar:
                dados_receita = self.buscar_empresa_receita(empresa['cnpj'])
                if dados_receita and dados_receita.get('razao_social'):
                    # Atualiza no banco
                    self.supabase.table('empresas')\
                        .update({'razao_social': dados_receita['razao_social']})\
                        .eq('id', empresa['id'])\
                        .execute()
                    # Atualiza no dicionário local
                    if empresa['id'] in empresas:
                        empresas[empresa['id']]['razao_social'] = dados_receita['razao_social']
            
            # Converte para lista e ordena por última consulta
            empresas_list = list(empresas.values())
            empresas_list.sort(key=lambda x: x['ultima_consulta'], reverse=True)
            
            return empresas_list
            
        except Exception as e:
            print(f"Erro ao buscar empresas impedidas: {str(e)}")
            return []

    def formatar_observacao(self, observacao):
        """Formata a observação para exibição mais amigável"""
        try:
            # Se for uma string JSON, tenta converter
            if isinstance(observacao, str) and observacao.startswith('{'):
                try:
                    dados = json.loads(observacao)
                    if 'descricaoResumida' in dados:
                        return dados['descricaoResumida']
                except:
                    pass
            
            # Remove marcadores JSON
            texto = observacao.replace("{'descricaoResumida': '", "")
            texto = texto.replace("'}", "")
            texto = texto.replace('{"descricaoResumida": "', "")
            texto = texto.replace('"}', "")
            
            # Capitaliza primeira letra
            texto = texto.strip()
            if texto:
                texto = texto[0].upper() + texto[1:]
            
            return texto
            
        except Exception as e:
            print(f"Erro ao formatar observação: {str(e)}")
            return observacao

    def iniciar_chrome_cadin(self):
        """Inicia uma instância do Chrome configurada para consultas CADIN/CFIL"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            return driver
        except Exception as e:
            print(f"Erro ao iniciar Chrome: {str(e)}")
            return None

    def fechar_chrome_cadin(self, driver):
        """Fecha a instância do Chrome de forma segura"""
        try:
            if driver:
                driver.quit()
        except Exception as e:
            print(f"Erro ao fechar Chrome: {str(e)}")

    def consultar_cadin_rs(self, cnpj):
        """
        Consulta CADIN/CFIL RS usando Selenium
        Retorna: (status_cadin, status_cfil, observacoes)
        """
        try:
            # Configurar Chrome em modo headless
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Acessar site
                print("Acessando CADIN RS...")
                driver.get("https://cadin.sefaz.rs.gov.br/")
                wait = WebDriverWait(driver, 10)
                
                # Localizar campo de CNPJ
                try:
                    input_cnpj = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Digite o CPF ou CNPJ']"))
                    )
                except:
                    try:
                        input_cnpj = driver.find_element(By.CSS_SELECTOR, "input.form-control")
                    except:
                        input_cnpj = driver.find_element(By.XPATH, "//input[@type='text']")
                
                print(f"Preenchendo CNPJ: {cnpj}")
                input_cnpj.click()
                input_cnpj.clear()
                time.sleep(0.1)
                
                for digito in cnpj:
                    input_cnpj.send_keys(digito)
                    time.sleep(0.05)
                
                # Localizar e clicar no botão Consultar
                print("Clicando em Consultar...")
                try:
                    consultar_btn = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-success"))
                    )
                except:
                    try:
                        consultar_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Consultar')]")
                    except:
                        consultar_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                
                consultar_btn.click()
                time.sleep(1)
                
                # Verificar resultados
                try:
                    resultado_cadin = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CADIN: Não foram encontrados registros') or contains(text(), 'CADIN:')]"))
                    ).text
                    status_cadin = "REGULAR" if "NÃO FORAM ENCONTRADOS REGISTROS" in resultado_cadin.upper() else "IRREGULAR"
                    obs_cadin = resultado_cadin.strip()
                    print(f"CADIN: {status_cadin} - {obs_cadin}")
                except Exception as e:
                    print(f"Erro ao verificar CADIN: {str(e)}")
                    status_cadin = "ERRO"
                    obs_cadin = "Não foi possível verificar CADIN"
                
                # Verificar CFIL
                try:
                    resultado_cfil = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CFIL: Não foram encontrados registros') or contains(text(), 'CFIL:')]"))
                    ).text
                    status_cfil = "REGULAR" if "NÃO FORAM ENCONTRADOS REGISTROS" in resultado_cfil.upper() else "IRREGULAR"
                    obs_cfil = resultado_cfil.strip()
                    print(f"CFIL: {status_cfil} - {obs_cfil}")
                except Exception as e:
                    print(f"Erro ao verificar CFIL: {str(e)}")
                    status_cfil = "ERRO"
                    obs_cfil = "Não foi possível verificar CFIL"
                
                return {
                    'cadin': {
                        'status': status_cadin == "REGULAR",
                        'observacoes': obs_cadin
                    },
                    'cfil': {
                        'status': status_cfil == "REGULAR",
                        'observacoes': obs_cfil
                    }
                }
                
            finally:
                print("Fechando navegador...")
                driver.quit()
                
        except Exception as e:
            print(f"Erro ao consultar CADIN/CFIL RS: {str(e)}")
            return None

    def obter_empresa_id(self, cnpj):
        """Obtém ID da empresa ou cria se não existir"""
        try:
            empresa = self.supabase.from_('empresas').select('id').eq('cnpj', cnpj).execute()
            if empresa.data:
                return empresa.data[0]['id']
            else:
                nova_empresa = self.supabase.from_('empresas').insert({
                    'cnpj': cnpj,
                    'razao_social': 'Empresa em Consulta'
                }).execute()
                return nova_empresa.data[0]['id']
        except Exception as e:
            print(f"Erro ao obter empresa: {str(e)}")
            return None

    def consultar_cadin_rs_lote(self, empresas):
        """
        Consulta CADIN/CFIL RS para múltiplas empresas
        """
        try:
            # Configurar Chrome em modo headless
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            resultados = {}
            
            try:
                for empresa in empresas:
                    cnpj = empresa['cnpj']
                    print(f"\nConsultando {empresa['razao_social']} - {cnpj}")
                    
                    # Acessar site para cada consulta
                    driver.get("https://cadin.sefaz.rs.gov.br/")
                    wait = WebDriverWait(driver, 10)
                    
                    # Localizar campo de CNPJ
                    try:
                        input_cnpj = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Digite o CPF ou CNPJ']"))
                        )
                    except:
                        try:
                            input_cnpj = driver.find_element(By.CSS_SELECTOR, "input.form-control")
                        except:
                            input_cnpj = driver.find_element(By.XPATH, "//input[@type='text']")
                    
                    input_cnpj.click()
                    input_cnpj.clear()
                    time.sleep(0.1)
                    
                    for digito in cnpj:
                        input_cnpj.send_keys(digito)
                        time.sleep(0.05)
                    
                    # Clicar em Consultar
                    try:
                        consultar_btn = wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-success"))
                        )
                    except:
                        try:
                            consultar_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Consultar')]")
                        except:
                            consultar_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    
                    consultar_btn.click()
                    time.sleep(1)
                    
                    # Verificar resultados
                    resultado = {
                        'cadin': {'status': True, 'observacoes': 'Regular'},
                        'cfil': {'status': True, 'observacoes': 'Regular'}
                    }
                    
                    # Verificar CADIN
                    try:
                        resultado_cadin = wait.until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CADIN:')]"))
                        ).text
                        
                        if "NÃO FORAM ENCONTRADOS REGISTROS" in resultado_cadin.upper():
                            resultado['cadin']['status'] = True
                            resultado['cadin']['observacoes'] = "Regular - Não foram encontrados registros"
                        else:
                            resultado['cadin']['status'] = False
                            resultado['cadin']['observacoes'] = resultado_cadin.strip()
                    except Exception as e:
                        resultado['cadin']['status'] = False
                        resultado['cadin']['observacoes'] = "Erro ao verificar CADIN"
                    
                    # Verificar CFIL
                    try:
                        resultado_cfil = wait.until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CFIL:')]"))
                        ).text
                        
                        if "NÃO FORAM ENCONTRADOS REGISTROS" in resultado_cfil.upper():
                            resultado['cfil']['status'] = True
                            resultado['cfil']['observacoes'] = "Regular - Não foram encontrados registros"
                        else:
                            resultado['cfil']['status'] = False
                            resultado['cfil']['observacoes'] = resultado_cfil.strip()
                    except Exception as e:
                        resultado['cfil']['status'] = False
                        resultado['cfil']['observacoes'] = "Erro ao verificar CFIL"
                    
                    # Registrar resultados
                    self.registrar_monitoramento(
                        empresa_id=empresa['id'],
                        tipo="CADIN_RS",
                        status=resultado['cadin']['status'],
                        observacoes=resultado['cadin']['observacoes']
                    )
                    
                    self.registrar_monitoramento(
                        empresa_id=empresa['id'],
                        tipo="CFIL_RS",
                        status=resultado['cfil']['status'],
                        observacoes=resultado['cfil']['observacoes']
                    )
                    
                    resultados[cnpj] = resultado
                    
                return resultados
                
            finally:
                print("Fechando navegador...")
                driver.quit()
                
        except Exception as e:
            print(f"Erro na consulta em lote: {str(e)}")
            return None