import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
import time
from selenium.webdriver.chrome.options import Options

def autorizar_api():
    """Testa autorização da API do Portal da Transparência usando Selenium"""
    try:
        api_key = '0a5acb096acf4893c84d90e3ae1ff2e9'
        print(f"Iniciando autorização com chave: {api_key}")
        
        # Configura o Chrome para rodar em background
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # options.add_argument('--headless')  # Modo headless
        options.add_argument('--disable-gpu')  # Desativa GPU
        options.add_argument('--no-sandbox')  # Modo sandbox
        options.add_argument('--disable-dev-shm-usage')  # Evita erros de memória
        
        # Inicia Chrome em background
        driver = webdriver.Chrome(options=options)
        print("Chrome iniciado em background")
        
        # Acessa a página
        driver.get("https://api.portaldatransparencia.gov.br/swagger-ui/index.html")
        print("Página carregada")
        
        time.sleep(1)  # Reduzido para 1 segundo
        
        # Clica no botão Authorize
        authorize_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "authorize"))
        )
        authorize_button.click()
        print("Clicou no botão Authorize")
        
        time.sleep(1)  # Reduzido para 1 segundo
        
        # Envia a chave
        actions = webdriver.ActionChains(driver)
        actions.send_keys(api_key)
        actions.perform()
        print("Enviou a chave API")
        
        time.sleep(1)  # Reduzido para 1 segundo
        
        # Clica no botão Authorize do modal
        modal_authorize = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal-btn.auth.authorize.button"))
        )
        modal_authorize.click()
        print("Clicou em Authorize no modal")
        
        time.sleep(1)  # Reduzido para 1 segundo
        
        # Fecha o modal
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal-btn.auth.btn-done.button"))
        )
        close_button.click()
        print("Modal fechado")
        
        # Verifica se o botão Authorize mudou de estado
        time.sleep(1)  # Reduzido para 1 segundo
        authorize_button = driver.find_element(By.CLASS_NAME, "authorize")
        button_class = authorize_button.get_attribute("class")
        print(f"Classes do botão: {button_class}")
        
        if "locked" not in button_class:
            print("Autorização não persistiu!")
            return False
            
        print("Autorização confirmada no portal!")
        input("Pressione Enter para continuar com os testes...")  # Quarta pausa
        
        # Testa a API
        print("\nTestando endpoints com múltiplos CNPJs:")
        base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
        cnpjs_teste = [
            "00000000000191",  # Banco do Brasil
            "08938288000151"   # Outro CNPJ
        ]
        
        endpoints = {
            'CEIS': '/ceis',
            'CNEP': '/cnep',
            'CEPIM': '/cepim/consulta/pessoa-juridica'
        }
        
        headers = {
            'Accept': 'application/json',
            'chave-api-dados': api_key
        }
        
        for cnpj in cnpjs_teste:
            print(f"\nTestando CNPJ: {cnpj}")
            for nome, endpoint in endpoints.items():
                try:
                    print(f"\nConsultando {nome}...")
                    
                    # Ajusta parâmetros conforme o endpoint
                    if nome == 'CEPIM':
                        params = {'numeroInscricao': cnpj}
                    else:
                        params = {'pagina': 1, 'codigoSancionado': cnpj}
                    
                    response = requests.get(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        params=params
                    )
                    
                    print(f"Status: {response.status_code}")
                    if response.status_code == 200:
                        # Tenta parsear a resposta
                        try:
                            dados = response.json() if response.text.strip() else []
                        except:
                            dados = []
                            print(f"Resposta vazia de {nome}")
                        
                        print(f"Registros encontrados: {len(dados)}")
                        if dados:
                            detalhes = ""
                            for registro in dados:
                                if nome in ['CEIS', 'CNEP']:
                                    orgao = registro.get('orgaoSancionador', {})
                                    detalhes += f"Data Sanção: {registro.get('dataInicioSancao', '')}\n"
                                    detalhes += f"Tipo Sanção: {registro.get('tipoSancao', '')}\n"
                                    detalhes += f"Órgão: {orgao.get('nome', '')}\n"
                                    detalhes += f"Esfera: {orgao.get('esfera', '')} | "
                                    detalhes += f"Poder: {orgao.get('poder', '')}\n"
                                    
                                    if registro.get('valorMulta') or registro.get('fundamentoLegal'):
                                        detalhes += "     "  # Indentação
                                        if registro.get('valorMulta'):
                                            detalhes += f"Multa: R$ {registro.get('valorMulta', '0,00')} | "
                                        if registro.get('fundamentoLegal'):
                                            detalhes += f"Base Legal: {registro.get('fundamentoLegal', '')}"
                                        detalhes += "\n"
                                    
                            print("Detalhes:", detalhes if detalhes else "Nenhum detalhe disponível")
                    else:
                        print(f"Erro: {response.text}")
                        
                except Exception as e:
                    print(f"Erro ao consultar {nome}: {str(e)}")
                    continue
        
        return True
            
    except Exception as e:
        print(f"Erro na autorização: {str(e)}")
        return False
    finally:
        if 'driver' in locals():
            driver.quit()

def verificar_impedimentos_api(self, cnpj):
    """Verifica impedimentos via API oficial"""
    try:
        # Primeiro verifica se a empresa existe
        empresa = self.supabase.table('empresas').select("*").eq('cnpj', cnpj).execute()
        
        if not empresa.data:
            print(f"Empresa {cnpj} não encontrada. Cadastrando...")
            # Cadastra a empresa
            self.supabase.table('empresas').insert({
                'cnpj': cnpj,
                'razao_social': 'Empresa em Consulta',  # Nome temporário
                'objeto_contrato': 'Consulta Individual'
            }).execute()
            print(f"Empresa {cnpj} cadastrada com sucesso")
            
            # Busca o ID da empresa recém cadastrada
            empresa = self.supabase.table('empresas').select("*").eq('cnpj', cnpj).execute()
        
        empresa_id = empresa.data[0]['id']
        print(f"Usando empresa_id: {empresa_id}")
        
    except Exception as e:
        print(f"Erro ao verificar/cadastrar empresa: {str(e)}")
        return None

def consultar_cadin_rs(driver, cnpj: str):
    """
    Consulta CADIN/CFIL RS usando Selenium
    Retorna: (status_cadin, status_cfil, observacoes)
    """
    try:
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
        print("Botão clicado")
        
        # Aguardar e verificar resultados
        time.sleep(1)
        
        # Verificar resultados CADIN
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
        
        # Verificar resultados CFIL
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
            
    except Exception as e:
        print(f"Erro ao consultar CADIN/CFIL RS: {str(e)}")
        return None

if __name__ == "__main__":
    print("Testando consulta CADIN/CFIL RS...")
    
    # Configurar e iniciar Chrome uma única vez
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--start-maximized')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Acessar site uma única vez
        print("Acessando CADIN RS...")
        driver.get("https://cadin.sefaz.rs.gov.br/")
        
        # Lista de CNPJs para teste
        cnpjs_teste = [
            "00000000000191",  # CNPJ do Banco do Brasil
            "11493437000120"   # CNPJ com restrição
        ]
        
        for cnpj_teste in cnpjs_teste:
            print(f"\nConsultando CNPJ: {cnpj_teste}")
            resultado = consultar_cadin_rs(driver, cnpj_teste)
            
            if resultado:
                print("\nResultados:")
                print("-" * 30)
                print("CADIN:")
                print(f"Status: {'✅ Regular' if resultado['cadin']['status'] else '❌ Irregular'}")
                print(f"Observações: {resultado['cadin']['observacoes']}")
                print("\nCFIL:")
                print(f"Status: {'✅ Regular' if resultado['cfil']['status'] else '❌ Irregular'}")
                print(f"Observações: {resultado['cfil']['observacoes']}")
                print("-" * 30)
            else:
                print("Erro na consulta")
            
            print("\n" + "="*50 + "\n")
            input("Pressione Enter para continuar...")
            
    finally:
        print("Fechando navegador...")
        driver.quit()