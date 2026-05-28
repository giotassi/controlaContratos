import logging
from services.database import DatabaseService
from services.cadin import CADINService
from services.tcu_apf import TCUAPFService
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
        self.tcu = TCUAPFService()
        self.transparencia = TransparenciaService()
        logging.info("MonitorService inicializado")
        
    def verificar_empresa(
        self,
        cnpj: str,
        razao_social: str = None,
        incluir_cadin: bool = True,
        incluir_cfil: bool = True,
        salvar: bool = True,
    ):
        """Verifica uma empresa em todos os serviços."""
        try:
            cnpj_formatado = format_cnpj(cnpj)
            if not validate_cnpj(cnpj_formatado):
                return {"error": "CNPJ inválido"}

            # Portal da Transparencia (CEIS, CNEP)
            try:
                resultado_transparencia = self.transparencia.consultar(cnpj, razao_social, salvar=False) or {}
            except Exception as e:
                logging.error(f"Erro Transparência {cnpj}: {e}")
                resultado_transparencia = {
                    s: {'status': None, 'observacoes': f'Erro: {e}'}
                    for s in ['ceis', 'cnep']
                }

            # CADIN / CFIL (opcional)
            if incluir_cadin:
                try:
                    resultado_cadin = self.cadin.consultar(cnpj_formatado, incluir_cfil=incluir_cfil, salvar=False) or {}
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

            resultado_tcu = self._consultar_tcu(cnpj_formatado)
            resultado_combinado = {**resultado_transparencia, **resultado_cadin, **resultado_tcu}

            # Status geral: ignora campos None (não consultados / sem API)
            statuses = [
                v.get('status')
                for k, v in resultado_combinado.items()
                if isinstance(v, dict) and k not in ('empresa_id',)
            ]
            consultados = [s for s in statuses if s is not None]
            resultado_combinado['status'] = all(consultados) if consultados else None

            if salvar:
                self._salvar_monitoramento_consolidado(
                    cnpj_formatado,
                    razao_social,
                    resultado_combinado,
                )

            return resultado_combinado

        except Exception as e:
            logging.error(f"Erro ao verificar empresa {cnpj}: {e}", exc_info=True)
            return {"error": str(e)}

    def _consultar_tcu(self, cnpj: str):
        try:
            consulta_tcu = self.tcu.consultar(cnpj, emitir_pdf=False)
            if consulta_tcu.get("error"):
                return {"tcu": {"status": None, "observacoes": consulta_tcu["error"]}}
            restricoes = [
                certidao for certidao in consulta_tcu.get("certidoes", [])
                if str(certidao.get("situacao", "")).upper() != "NADA_CONSTA"
            ]
            return {
                "tcu": {
                    "status": not bool(restricoes),
                    "observacoes": self._formatar_tcu(restricoes) if restricoes else "Regular",
                }
            }
        except Exception as e:
            logging.error(f"Erro TCU {cnpj}: {e}")
            return {"tcu": {"status": None, "observacoes": f"Erro: {e}"}}

    def _formatar_tcu(self, restricoes: list[dict]) -> str:
        return "\n".join(
            " | ".join([
                f"Tipo: {certidao.get('tipo', 'TCU')}",
                f"Situação: {certidao.get('situacao', 'Restrição')}",
                f"Emissor: {certidao.get('emissor', 'N/A')}",
                f"Observação: {certidao.get('observacao') or 'N/A'}",
            ])
            for certidao in restricoes
        )

    def _salvar_monitoramento_consolidado(self, cnpj: str, razao_social: str | None, resultado: dict):
        try:
            empresa_id = self._garantir_empresa(cnpj, razao_social)
            if empresa_id is None:
                return

            observacoes = self._formatar_observacoes_consolidadas(resultado)
            self.db.supabase.table("monitoramentos").insert({
                "empresa_id": empresa_id,
                "tipo_verificacao": "CONSOLIDADO",
                "status": resultado.get("status"),
                "observacoes": observacoes,
                "data_verificacao": datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            logging.error(f"Erro ao salvar monitoramento consolidado {cnpj}: {e}")

    def _garantir_empresa(self, cnpj: str, razao_social: str | None) -> int | None:
        try:
            resp = self.db.supabase.table("empresas").select("id, razao_social").eq("cnpj", cnpj).execute()
            if resp.data:
                empresa = resp.data[0]
                if razao_social and empresa.get("razao_social") != razao_social:
                    self.db.supabase.table("empresas").update({"razao_social": razao_social}).eq("id", empresa["id"]).execute()
                return empresa["id"]
            resp = self.db.supabase.table("empresas").insert({
                "cnpj": cnpj,
                "razao_social": razao_social or "Empresa em Consulta",
                "objeto_contrato": "Consulta Individual",
            }).execute()
            return resp.data[0]["id"] if resp.data else None
        except Exception as e:
            logging.error(f"Erro ao garantir empresa {cnpj}: {e}")
            return None

    def _formatar_observacoes_consolidadas(self, resultado: dict) -> str:
        linhas = []
        for sistema, dados in resultado.items():
            if sistema in ("status", "empresa_id") or not isinstance(dados, dict):
                continue
            status = dados.get("status")
            if status is False:
                label = "IRREGULAR"
            elif status is True:
                label = "REGULAR"
            else:
                label = "NÃO CONCLUSIVO"
            linhas.append(f"{sistema.upper()} [{label}]: {dados.get('observacoes', '')}")
        return "\n\n".join(linhas)
            
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
            self._limpar_impedimentos_de_erro()

            # Busca os monitoramentos
            query = self.db.supabase.table('monitoramentos')\
                .select('*')\
                .gte('data_verificacao', data_limite.isoformat())\
                .eq('status', False)\
                .eq('tipo_verificacao', 'CONSOLIDADO')
            
            # Removemos o filtro de data_regularizacao já que a coluna não existe
            response = query.execute()
            
            if response.data:
                impedimentos = []
                # Para cada monitoramento, busca os dados da empresa
                for item in response.data:
                    if self._observacao_eh_erro(item.get('observacoes', '')):
                        continue
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

    def _observacao_eh_erro(self, observacoes: str) -> bool:
        texto = (observacoes or "").lower()
        if "irregular" in texto:
            return False
        indicadores = [
            "erro na consulta",
            "erro http",
            "stacktrace",
            "chromedriver",
            "timeout",
            "exception",
        ]
        return any(indicador in texto for indicador in indicadores)

    def _limpar_impedimentos_de_erro(self):
        filtros = [
            "%Erro na consulta%",
            "%Erro HTTP%",
            "%Stacktrace%",
            "%chromedriver%",
            "%timeout%",
        ]
        for filtro in filtros:
            try:
                self.db.supabase.table("monitoramentos")\
                    .delete()\
                    .eq("status", False)\
                    .neq("tipo_verificacao", "CONSOLIDADO")\
                    .ilike("observacoes", filtro)\
                    .execute()
            except Exception as e:
                logging.error(f"Erro ao limpar impedimentos técnicos ({filtro}): {e}")
            
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
