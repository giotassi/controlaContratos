import logging
from services.database import DatabaseService
from services.cadin import CADINService
from services.transparencia import TransparenciaService
from utils.formatters import format_cnpj, validate_cnpj
from datetime import datetime

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MonitorService:
    def __init__(self):
        """Inicializa o monitor de empresas"""
        self.db = DatabaseService()
        self.cadin = CADINService()
        self.transparencia = TransparenciaService()
        logging.info("MonitorService inicializado")
        
    def verificar_empresa(
        self,
        cnpj: str,
        razao_social: str = None,
        incluir_cadin: bool = True,
        incluir_cfil: bool = True,
    ):
        """Verifica uma empresa em todos os serviços."""
        try:
            cnpj_formatado = format_cnpj(cnpj)
            if not validate_cnpj(cnpj_formatado):
                return {"error": "CNPJ inválido"}

            # Portal da Transparencia (CEIS, CNEP)
            try:
                resultado_transparencia = self.transparencia.consultar(cnpj, razao_social) or {}
            except Exception as e:
                logging.error(f"Erro Transparência {cnpj}: {e}")
                resultado_transparencia = {
                    s: {'status': None, 'observacoes': f'Erro: {e}'}
                    for s in ['ceis', 'cnep']
                }

            # CADIN / CFIL (opcional)
            if incluir_cadin:
                try:
                    resultado_cadin = self.cadin.consultar(cnpj_formatado, incluir_cfil=incluir_cfil) or {}
                except Exception as e:
                    logging.error(f"Erro CADIN {cnpj}: {e}")
                    resultado_cadin = {
                        s: {'status': None, 'observacoes': f'Erro: {e}'}
                        for s in ['cadin', 'cfil']
                    }
            else:
                resultado_cadin = {
                    'cadin': {'status': None, 'observacoes': 'Não consultado'},
                    'cfil':  {'status': None, 'observacoes': 'Não consultado'},
                }

            resultado_combinado = {**resultado_transparencia, **resultado_cadin}

            # Status geral: ignora campos None (não consultados / sem API)
            statuses = [
                v.get('status')
                for k, v in resultado_combinado.items()
                if isinstance(v, dict) and k not in ('empresa_id',)
            ]
            consultados = [s for s in statuses if s is not None]
            resultado_combinado['status'] = all(consultados) if consultados else None

            return resultado_combinado

        except Exception as e:
            logging.error(f"Erro ao verificar empresa {cnpj}: {e}", exc_info=True)
            return {"error": str(e)}
            
    def buscar_impedimentos(self, data_limite, apenas_ativos=True):
        """
        Busca impedimentos no banco de dados
        
        Args:
            data_limite (datetime): Data limite para busca
            apenas_ativos (bool): Se True, retorna apenas impedimentos ativos
            
        Returns:
            list: Lista de impedimentos encontrados
        """
        try:
            # Busca os monitoramentos
            query = self.db.supabase.table('monitoramentos')\
                .select('*')\
                .gte('data_verificacao', data_limite.isoformat())\
                .eq('status', False)  # False significa que tem impedimento
            
            # Removemos o filtro de data_regularizacao já que a coluna não existe
            response = query.execute()
            
            if response.data:
                impedimentos = []
                # Para cada monitoramento, busca os dados da empresa
                for item in response.data:
                    empresa = self.db.supabase.table('empresas')\
                        .select('*')\
                        .eq('id', item['empresa_id'])\
                        .execute()
                    
                    if empresa.data:
                        impedimento = {
                            'cnpj': empresa.data[0]['cnpj'],
                            'razao_social': empresa.data[0]['razao_social'],
                            'sistema': item['tipo_verificacao'],
                            'data_verificacao': item['data_verificacao'],
                            'observacoes': item['observacoes']
                        }
                        impedimentos.append(impedimento)
                
                return impedimentos
            return []
            
        except Exception as e:
            logging.error(f"Erro ao buscar impedimentos: {str(e)}")
            return []
            
    def atualizar_base(self):
        """
        Atualiza a base de dados verificando todas as empresas cadastradas
        Returns:
            dict: Resultado da atualização
        """
        try:
            # Busca todas as empresas cadastradas
            response = self.db.supabase.table('empresas').select('*').execute()
            
            if not response.data:
                return {"error": "Nenhuma empresa cadastrada"}
                
            total = len(response.data)
            atualizadas = 0
            erros = 0
            
            for empresa in response.data:
                try:
                    resultado = self.verificar_empresa(
                        empresa['cnpj'],
                        empresa['razao_social']
                    )
                    
                    if "error" not in resultado:
                        atualizadas += 1
                    else:
                        erros += 1
                        
                except Exception as e:
                    logging.error(f"Erro ao atualizar empresa {empresa['id']}: {str(e)}")
                    erros += 1
                    
            return {
                "total": total,
                "atualizadas": atualizadas,
                "erros": erros
            }
            
        except Exception as e:
            logging.error(f"Erro ao atualizar base: {str(e)}")
            return {"error": str(e)} 
