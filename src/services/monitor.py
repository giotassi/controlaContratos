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
        
    def verificar_empresa(self, cnpj: str, razao_social: str = None):
        """
        Verifica uma empresa em todos os serviços
        Args:
            cnpj: CNPJ da empresa
            razao_social: Nome da empresa (opcional)
        """
        try:
            logging.info(f"Iniciando verificação para CNPJ: {cnpj}")
            
            # Formata o CNPJ antes de validar
            cnpj_formatado = format_cnpj(cnpj)
            logging.info(f"CNPJ formatado: {cnpj_formatado}")
            
            if not validate_cnpj(cnpj_formatado):
                logging.warning(f"CNPJ inválido: {cnpj_formatado}")
                return {"error": "CNPJ inválido"}

            # Consulta Portal da Transparência
            logging.info("Iniciando consulta Portal da Transparência")
            resultado_transparencia = self.transparencia.consultar(cnpj, razao_social)
            
            if not resultado_transparencia:
                logging.error("Erro ao consultar Portal da Transparência")
                return {"error": "Erro ao consultar Portal da Transparência"}
                
            logging.info(f"Resultado Portal da Transparência: {resultado_transparencia}")
            
            # Consulta CADIN/CFIL
            logging.info("Iniciando consulta CADIN/CFIL")
            resultado_cadin = self.cadin.consultar(cnpj_formatado)
            
            if not resultado_cadin:
                logging.error("Erro ao consultar CADIN/CFIL")
                return {"error": "Erro ao consultar CADIN/CFIL"}
                
            logging.info(f"Resultado CADIN/CFIL: {resultado_cadin}")
            
            # Combina os resultados e determina o status geral
            resultado_combinado = {
                **resultado_transparencia,
                **resultado_cadin
            }
            
            # Status geral é True apenas se todos os serviços retornarem True
            status_geral = all([
                resultado_transparencia.get('ceis', {}).get('status', False),
                resultado_transparencia.get('cnep', {}).get('status', False),
                resultado_transparencia.get('cepim', {}).get('status', False),
                resultado_cadin.get('cadin', {}).get('status', False),
                resultado_cadin.get('cfil', {}).get('status', False)
            ])
            
            resultado_combinado['status'] = status_geral
            return resultado_combinado

        except Exception as e:
            logging.error(f"Erro ao verificar empresa: {str(e)}", exc_info=True)
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
            
            if apenas_ativos:
                # Se apenas_ativos=True, busca registros SEM data de regularização
                query = query.is_('data_regularizacao', 'null')
            
            response = query.execute()
            
            if response.data:
                impedimentos = []
                # Para cada monitoramento, busca os dados da empresa
                for item in response.data:
                    # Busca dados da empresa
                    empresa_response = self.db.supabase.table('empresas')\
                        .select('id, cnpj, razao_social')\
                        .eq('id', item['empresa_id'])\
                        .execute()
                    
                    if empresa_response.data:
                        empresa = empresa_response.data[0]
                        impedimentos.append({
                            'id': empresa['id'],
                            'cnpj': empresa['cnpj'],  # Agora usando o campo CNPJ
                            'razao_social': empresa['razao_social'],
                            'sistema': item['tipo_verificacao'],
                            'data_verificacao': item['data_verificacao'],
                            'observacoes': item['observacoes']
                        })
                
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
                        empresa['id'],  # CNPJ está como ID
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