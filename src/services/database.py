from supabase import create_client
import os
from dotenv import load_dotenv
import logging

# Carrega variáveis de ambiente
load_dotenv()

class DatabaseService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logging.error("Credenciais do Supabase não encontradas!")
            raise ValueError("SUPABASE_URL e SUPABASE_KEY precisam estar definidas nas variáveis de ambiente")
        
        logging.info("Conectando ao Supabase...")
        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            logging.info("Conexão com Supabase estabelecida com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao conectar com Supabase: {str(e)}")
            raise e

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