from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
import time
import logging
from utils.selenium_utils import get_chrome_options
from datetime import datetime
from services.database import DatabaseService

class CADINService:
    def __init__(self):
        self.url = "https://cadin.sefaz.rs.gov.br/"
        self.timeout = 20
        self.db = DatabaseService()
        
    def consultar(self, cnpj: str):
        """Consulta CADIN/CFIL RS para um CNPJ"""
        driver = None
        try:
            logging.info(f"Iniciando consulta CADIN/CFIL para CNPJ {cnpj}")
            
            # Primeiro verifica/cadastra a empresa
            empresa = self.db.supabase.table('empresas')\
                .select('id')\
                .eq('cnpj', cnpj)\
                .execute()
                
            if not empresa.data:
                empresa = self.db.supabase.table('empresas')\
                    .insert({
                        'cnpj': cnpj,
                        'razao_social': 'Empresa em Consulta',
                        'objeto_contrato': 'Consulta Individual'
                    })\
                    .execute()
            
            empresa_id = empresa.data[0]['id']
            
            # Configurar Chrome
            chrome_options = get_chrome_options()
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Consulta CADIN/CFIL
            resultado = self._realizar_consulta(driver, cnpj)
            
            # Salvar resultados CADIN
            self.db.supabase.table('monitoramentos').insert({
                'empresa_id': empresa_id,
                'tipo_verificacao': 'CADIN',
                'status': resultado['cadin']['status'],
                'observacoes': resultado['cadin']['observacoes'],
                'data_verificacao': datetime.now().isoformat()
            }).execute()
            
            # Salvar resultados CFIL
            self.db.supabase.table('monitoramentos').insert({
                'empresa_id': empresa_id,
                'tipo_verificacao': 'CFIL',
                'status': resultado['cfil']['status'],
                'observacoes': resultado['cfil']['observacoes'],
                'data_verificacao': datetime.now().isoformat()
            }).execute()
            
            return resultado
            
        except Exception as e:
            logging.error(f"Erro ao consultar CADIN/CFIL: {str(e)}", exc_info=True)
            return None
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def _realizar_consulta(self, driver, cnpj):
        """Realiza a consulta no site do CADIN/CFIL"""
        try:
            # Acessar site
            logging.info("Acessando site do CADIN/CFIL")
            driver.get(self.url)
            time.sleep(3)
            
            # Localizar e preencher campo CNPJ
            input_cnpj = self._encontrar_campo_cnpj(driver)
            if not input_cnpj:
                raise Exception("Campo de CNPJ não encontrado")
            
            input_cnpj.clear()
            input_cnpj.send_keys(cnpj)
            time.sleep(1)
            
            # Localizar e clicar botão Consultar
            button = self._encontrar_botao_consultar(driver)
            if not button:
                raise Exception("Botão Consultar não encontrado")
            
            button.click()
            time.sleep(3)
            
            # Processar resultados
            return self._processar_resultados(driver)
            
        except Exception as e:
            logging.error(f"Erro na consulta: {str(e)}")
            raise e

    def _encontrar_campo_cnpj(self, driver):
        """Tenta encontrar o campo de CNPJ usando diferentes seletores"""
        selectors = [
            "input[placeholder='Digite o CPF ou CNPJ']",
            "input.form-control",
            "input[type='text']"
        ]
        
        for selector in selectors:
            try:
                return WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            except:
                continue
        return None

    def _encontrar_botao_consultar(self, driver):
        """Tenta encontrar o botão Consultar usando diferentes seletores"""
        button_selectors = [
            "button.btn-success",
            "button[type='submit']",
            "//button[contains(text(), 'Consultar')]",
            "//input[@type='submit']"
        ]
        
        for selector in button_selectors:
            try:
                if selector.startswith("//"):
                    return WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    return WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
            except:
                continue
        return None

    def _processar_resultados(self, driver):
        """Processa os resultados da consulta"""
        resultado = {
            'cadin': {'status': True, 'observacoes': 'Não foram encontrados registros'},
            'cfil': {'status': True, 'observacoes': 'Não foram encontrados registros'}
        }
        
        try:
            mensagens = driver.find_elements(By.XPATH, "//*[contains(text(), 'CADIN:') or contains(text(), 'CFIL:')]")
            for msg in mensagens:
                texto = msg.text.upper()
                if 'CADIN:' in texto:
                    resultado['cadin']['status'] = 'NÃO FORAM ENCONTRADOS REGISTROS' in texto
                    resultado['cadin']['observacoes'] = msg.text.strip()
                elif 'CFIL:' in texto:
                    resultado['cfil']['status'] = 'NÃO FORAM ENCONTRADOS REGISTROS' in texto
                    resultado['cfil']['observacoes'] = msg.text.strip()
        except Exception as e:
            logging.warning(f"Erro ao processar resultados: {str(e)}")
        
        return resultado 