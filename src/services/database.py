from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
import streamlit as st
from datetime import datetime

# Carrega variáveis de ambiente
load_dotenv()

class DatabaseService:
    def __init__(self):
        try:
            # Primeiro tenta pegar das variáveis de ambiente (desenvolvimento)
            self.supabase_url = os.getenv('SUPABASE_URL')
            self.supabase_key = os.getenv('SUPABASE_KEY')
            
            # Se não encontrar, tenta pegar das secrets do Streamlit (produção)
            if not self.supabase_url or not self.supabase_key:
                self.supabase_url = st.secrets["supabase"]["url"]
                self.supabase_key = st.secrets["supabase"]["key"]
            
            self.supabase: Client = create_client(
                self.supabase_url,
                self.supabase_key
            )
        except Exception as e:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY precisam estar configuradas nas variáveis de ambiente ou nas secrets do Streamlit")

    def test_connection(self):
        """Testa a conexão com o Supabase"""
        try:
            # Tenta fazer uma query simples
            self.supabase.table('empresas').select("count", count='exact').execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao testar conexão: {str(e)}")
            return False

    def get_empresas(self):
        try:
            response = self.supabase.from_('empresas').select('*').execute()
            return response.data or []
        except Exception as e:
            logging.error(f"Erro ao listar empresas: {e}")
            return []

    def add_empresa(self, cnpj: str, razao_social: str, objeto_contrato: str = None):
        try:
            empresa_existente = self.supabase.table('empresas').select("*").eq('cnpj', cnpj).execute()
            
            if empresa_existente.data:
                return empresa_existente.data[0]
            
            data = {
                "cnpj": cnpj,
                "razao_social": razao_social,
                "objeto_contrato": objeto_contrato
            }
            
            response = self.supabase.table('empresas').insert(data).execute()
            return response.data[0]
            
        except Exception as e:
            logging.error(f"Erro ao adicionar empresa: {e}")
            return None

    def add_monitoramento(self, empresa_id: int, tipo: str, status: bool, 
                         data_validade=None, observacoes: str = None):
        try:
            data = {
                "empresa_id": empresa_id,
                "tipo_verificacao": tipo,
                "status": status,
                "data_validade": data_validade,
                "observacoes": observacoes,
                "data_verificacao": datetime.now().isoformat()
            }
            
            response = self.supabase.table('monitoramentos').insert(data).execute()
            return response.data[0]
        except Exception as e:
            logging.error(f"Erro ao registrar monitoramento: {e}")
            return None

    def obter_empresa_id(self, cnpj: str):
        try:
            response = self.supabase.table('empresas').select('id').eq('cnpj', cnpj).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            logging.error(f"Erro ao obter empresa_id: {e}")
            return None

    def listar_certidoes(self, status: str = "Todas", tipo: str = "Todas"):
        try:
            query = self.supabase.table('certidoes').select('*, empresas(cnpj, razao_social)')
            if tipo != "Todas":
                query = query.eq('tipo', tipo)
            response = query.order('data_validade').execute()

            hoje = datetime.now().date()
            empresas_map = {}
            for cert in (response.data or []):
                empresa_info = cert.get('empresas') or {}
                cnpj = empresa_info.get('cnpj', '')
                razao_social = empresa_info.get('razao_social', '')

                try:
                    validade = datetime.fromisoformat(cert['data_validade']).date()
                    dias_restantes = (validade - hoje).days
                    if status == "Vencidas" and dias_restantes >= 0:
                        continue
                    if status == "A vencer em 30 dias" and not (0 <= dias_restantes <= 30):
                        continue
                    if status == "Regulares" and dias_restantes < 0:
                        continue
                except (ValueError, KeyError):
                    pass

                if cnpj not in empresas_map:
                    empresas_map[cnpj] = {'cnpj': cnpj, 'razao_social': razao_social, 'certidoes': []}
                empresas_map[cnpj]['certidoes'].append(cert)

            return list(empresas_map.values())
        except Exception as e:
            logging.error(f"Erro ao listar certidões: {e}")
            return []

    def adicionar_certidao(self, empresa_id: int, tipo: str, data_emissao,
                           data_validade, numero_certidao: str = None, arquivo=None):
        try:
            arquivo_url = None
            if arquivo is not None:
                bucket = self.supabase.storage.from_('certidoes')
                filename = f"{empresa_id}_{tipo}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                bucket.upload(filename, arquivo.read(), {'content-type': 'application/pdf'})
                arquivo_url = bucket.get_public_url(filename)

            data = {
                'empresa_id': empresa_id,
                'tipo': tipo,
                'data_emissao': data_emissao.isoformat() if hasattr(data_emissao, 'isoformat') else str(data_emissao),
                'data_validade': data_validade.isoformat() if hasattr(data_validade, 'isoformat') else str(data_validade),
                'numero_certidao': numero_certidao,
                'arquivo_url': arquivo_url,
            }
            response = self.supabase.table('certidoes').insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logging.error(f"Erro ao adicionar certidão: {e}")
            return None

    def excluir_certidao(self, certidao_id: int) -> bool:
        try:
            self.supabase.table('certidoes').delete().eq('id', certidao_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao excluir certidão {certidao_id}: {e}")
            return False

    def listar_certidoes_proximas(self, dias: int = 30) -> list:
        """Retorna certidões que vencem nos próximos `dias` dias ou já vencidas."""
        from datetime import date, timedelta
        hoje = date.today()
        limite = hoje + timedelta(days=dias)
        try:
            resp = (
                self.supabase.table('certidoes')
                .select('*, empresas(cnpj, razao_social)')
                .lte('data_validade', limite.isoformat())
                .order('data_validade')
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logging.error(f"Erro ao listar certidões próximas: {e}")
            return []

    def limpar_base_dados(self):
        """Limpa as tabelas do banco de dados na ordem correta"""
        try:
            # Primeiro limpa a tabela de monitoramentos (tabela dependente)
            monitoramentos = self.supabase.table('monitoramentos').delete().neq('id', 0).execute()
            total_monitoramentos = len(monitoramentos.data) if monitoramentos.data else 0
            
            # Depois limpa a tabela de empresas
            empresas = self.supabase.table('empresas').delete().neq('id', 0).execute()
            total_empresas = len(empresas.data) if empresas.data else 0
            
            return {
                'success': True,
                'message': "Base de dados limpa com sucesso",
                'monitoramentos': total_monitoramentos,
                'empresas': total_empresas
            }
        except Exception as e:
            logging.error(f"Erro ao limpar base de dados: {str(e)}")
            return {
                'success': False,
                'message': f"Erro ao limpar base de dados: {str(e)}",
                'monitoramentos': 0,
                'empresas': 0
            } 