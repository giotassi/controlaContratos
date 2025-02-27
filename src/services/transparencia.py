import os
from dotenv import load_dotenv
from pathlib import Path
import streamlit as st
import requests
import logging
from datetime import datetime
import time
from services.database import DatabaseService

# Carrega variáveis de ambiente
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class TransparenciaService:
    def __init__(self):
        try:
            # Primeiro tenta pegar das variáveis de ambiente
            self.api_key = os.getenv('API_KEY')
            
            if not self.api_key:
                try:
                    # Tenta pegar das secrets do Streamlit
                    self.api_key = st.secrets["transparencia"]["api_key"]
                except:
                    pass
                
            if not self.api_key:
                raise ValueError("API_KEY não encontrada")
                
        except Exception as e:
            raise ValueError("API_KEY precisa estar configurada nas variáveis de ambiente ou nas secrets do Streamlit")
        self.base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
        self.headers = {
            'Accept': 'application/json',
            'chave-api-dados': self.api_key
        }
        self.db = DatabaseService()  # Adiciona acesso ao banco de dados

    def testar_api(self):
        """Testa se a API está respondendo e autorizada"""
        try:
            # Teste rápido com CNPJ conhecido
            response = requests.get(
                f"{self.base_url}/ceis",
                headers=self.headers,
                params={'pagina': 1, 'codigoSancionado': '00000000000191'}
            )
            return response.status_code == 200
        except:
            return False

    def consultar(self, cnpj: str, razao_social: str = None):
        """Consulta CEIS, CNEP e CEPIM para um CNPJ"""
        logging.info(f"Iniciando consulta Portal da Transparência para CNPJ {cnpj}")
        
        # Primeiro verifica/cadastra a empresa
        empresa = self.db.supabase.table('empresas')\
            .select('*')\
            .eq('cnpj', cnpj)\
            .execute()
            
        if not empresa.data:
            empresa = self.db.supabase.table('empresas')\
                .insert({
                    'cnpj': cnpj,
                    'razao_social': razao_social or 'Empresa em Consulta',
                    'objeto_contrato': 'Consulta Individual'
                })\
                .execute()
        elif razao_social and empresa.data[0]['razao_social'] != razao_social:
            self.db.supabase.table('empresas')\
                .update({'razao_social': razao_social})\
                .eq('id', empresa.data[0]['id'])\
                .execute()
                
        empresa_id = empresa.data[0]['id']
        
        resultados = {}
        
        try:
            sistemas = ['ceis', 'cnep', 'cepim']
            for sistema in sistemas:
                try:
                    response = self._consultar_sistema(sistema, cnpj)
                    if response.status_code == 200:
                        dados = response.json() if response.text.strip() else []
                        
                        if sistema == 'cepim':
                            # CEPIM: considera apenas registros ativos
                            if not dados:
                                status = True  # Sem registros = regular
                                observacoes = "Regular"
                            else:
                                # Verifica se há registros ativos
                                hoje = datetime.now().date()
                                registros_ativos = []
                                
                                for reg in dados:
                                    # Verifica se o registro está ativo
                                    data_final = reg.get('dataFinal')
                                    if data_final:
                                        try:
                                            # A API retorna datas no formato DD/MM/YYYY
                                            dia, mes, ano = data_final.split('/')
                                            data_final = datetime(int(ano), int(mes), int(dia)).date()
                                            if data_final > hoje:
                                                registros_ativos.append(reg)
                                                logging.info(f"Registro CEPIM ativo encontrado: {reg}")
                                        except (ValueError, AttributeError) as e:
                                            logging.warning(f"Data inválida no CEPIM: {data_final} - Erro: {str(e)}")
                                            continue
                                
                                status = len(registros_ativos) == 0
                                if registros_ativos:
                                    observacoes = self._formatar_cepim(registros_ativos)
                                else:
                                    observacoes = "Regular - Registros encontrados, mas nenhum ativo"
                        else:
                            # CEIS e CNEP: mantém lógica original
                            status = len(dados) == 0
                            observacoes = getattr(self, f'_formatar_{sistema}')(dados) if dados else "Regular"
                        
                        # Salva o resultado no banco
                        self.db.supabase.table('monitoramentos').insert({
                            'empresa_id': empresa_id,
                            'tipo_verificacao': sistema.upper(),
                            'status': status,
                            'observacoes': observacoes,
                            'data_verificacao': datetime.now().isoformat()
                        }).execute()
                        
                        resultados[sistema] = {
                            'status': status,
                            'observacoes': observacoes
                        }
                    
                    time.sleep(1)
                    
                except Exception as e:
                    logging.error(f"Erro ao consultar {sistema}: {str(e)}")
                    resultados[sistema] = {
                        'status': False,
                        'observacoes': f"Erro na consulta: {str(e)}"
                    }
            
            return resultados

        except Exception as e:
            logging.error(f"Erro ao consultar Portal da Transparência: {str(e)}")
            return {sistema: {'status': False, 'observacoes': f'Erro na consulta: {str(e)}'} for sistema in sistemas}

    def _consultar_sistema(self, sistema, cnpj):
        """Consulta um sistema específico (CEIS, CNEP ou CEPIM)"""
        try:
            response = requests.get(
                f"{self.base_url}/{sistema}",
                headers=self.headers,
                params={
                    'pagina': 1,
                    'codigoSancionado' if sistema in ['ceis', 'cnep'] else 'numeroInscricao': cnpj
                }
            )
            return response
        except Exception as e:
            logging.error(f"Erro ao consultar {sistema}: {str(e)}")
            raise e

    def _formatar_ceis(self, dados):
        """Formata dados do CEIS"""
        registros = []
        for item in dados:
            registro = (
                f"Sanção: {item.get('descricaoResumida', 'N/A')}\n"
                f"Órgão: {item.get('orgaoSancionador', {}).get('nome', 'N/A')}\n"
                f"Início: {self._formatar_data(item.get('dataInicioSancao'))}\n"
                f"Fim: {self._formatar_data(item.get('dataFimSancao'))}"
            )
            registros.append(registro)
        return "\n\n".join(registros) if registros else "Registros encontrados no CEIS"

    def _formatar_cnep(self, dados):
        """Formata dados do CNEP"""
        registros = []
        for item in dados:
            registro = (
                f"Sanção: {item.get('tipoSancao', 'N/A')}\n"
                f"Órgão: {item.get('orgaoSancionador', {}).get('nome', 'N/A')}\n"
                f"Valor Multa: R$ {item.get('valorMulta', 'N/A')}"
            )
            registros.append(registro)
        return "\n\n".join(registros) if registros else "Regular"

    def _formatar_cepim(self, dados):
        """Formata dados do CEPIM"""
        registros = []
        for item in dados:
            registro = (
                f"Motivo: {item.get('motivo', 'N/A')}\n"
                f"Órgão: {item.get('orgaoSuperior', {}).get('nome', 'N/A')}\n"
                f"Convênio: {item.get('numeroConvenio', 'N/A')}"
            )
            registros.append(registro)
        return "\n\n".join(registros) if registros else "Regular"

    def _formatar_data(self, data_str):
        """Formata data de YYYY-MM-DD para DD/MM/YYYY"""
        if not data_str:
            return 'N/A'
        try:
            return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            return data_str 