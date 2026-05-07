import logging
import time
from datetime import datetime
from services.database import DatabaseService

logger = logging.getLogger(__name__)


class CADINService:
    TRANSPARENCIA_URL = "https://www.transparencia.rs.gov.br/licitacoes-e-sancoes/lista-de-sancionados/dados/"
    CADIN_URL = "https://cadin.sefaz.rs.gov.br/"

    def __init__(self):
        self.db = DatabaseService()
        self._cfil_driver = None   # reutilizado entre consultas em lote
        self._cfil_ready = False

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def consultar(self, cnpj: str) -> dict | None:
        """Consulta CADIN e CFIL/RS para um CNPJ. Retorna dict ou None em erro."""
        cnpj_digits = "".join(c for c in cnpj if c.isdigit())
        try:
            empresa_id = self._garantir_empresa(cnpj_digits)
            cfil = self._consultar_cfil(cnpj_digits)
            cadin = self._consultar_cadin(cnpj_digits)
            resultado = {"cadin": cadin, "cfil": cfil}
            self._salvar_monitoramentos(empresa_id, resultado)
            return resultado
        except Exception as e:
            logger.error(f"Erro ao consultar CADIN/CFIL para {cnpj}: {e}", exc_info=True)
            return None

    def fechar(self):
        """Fecha o browser do CFIL se estiver aberto (chamar após consultas em lote)."""
        if self._cfil_driver:
            try:
                self._cfil_driver.quit()
            except Exception:
                pass
            self._cfil_driver = None
            self._cfil_ready = False

    # ------------------------------------------------------------------
    # CFIL — Transparência RS (Power BI, sem CAPTCHA)
    # ------------------------------------------------------------------

    def _consultar_cfil(self, cnpj: str) -> dict:
        try:
            driver = self._obter_driver_cfil()
            return self._buscar_cnpj_no_relatorio(driver, cnpj)
        except Exception as e:
            logger.error(f"Erro CFIL para {cnpj}: {e}", exc_info=True)
            self._cfil_driver = None
            self._cfil_ready = False
            return {"status": False, "observacoes": f"Erro na consulta CFIL: {e}"}

    def _obter_driver_cfil(self):
        """Retorna driver já na página do Power BI, carregando-a se necessário."""
        if self._cfil_driver and self._cfil_ready:
            return self._cfil_driver

        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from utils.selenium_utils import get_chrome_options, get_chrome_service

        options = get_chrome_options()
        driver = webdriver.Chrome(service=get_chrome_service(), options=options)
        driver.get(self.TRANSPARENCIA_URL)
        logger.info("Aguardando Power BI carregar…")
        time.sleep(25)

        # Aceita cookies se aparecer
        try:
            driver.find_element(
                By.XPATH, "//button[contains(text(),'Concordo')]"
            ).click()
            time.sleep(1)
        except Exception:
            pass

        # Entra no iframe do Power BI
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if not iframes:
            driver.quit()
            raise RuntimeError("iframe do Power BI não encontrado")
        driver.switch_to.frame(iframes[0])
        time.sleep(3)

        self._cfil_driver = driver
        self._cfil_ready = True
        return driver

    def _buscar_cnpj_no_relatorio(self, driver, cnpj: str) -> dict:
        from selenium.webdriver.common.by import By

        # Limpa filtro anterior: clica fora do slicer e espera
        try:
            driver.find_element(By.XPATH, "//h3[@class='slicer-header-text']").click()
            time.sleep(1)
        except Exception:
            pass

        # Abre o slicer CPF/CNPJ
        combo = driver.find_element(
            By.XPATH, "//*[@role='combobox' and @aria-label='CPF/CNPJ']"
        )
        combo.click()
        time.sleep(2)

        # Digita o CNPJ no campo de pesquisa visível
        pesquisar_inputs = driver.find_elements(
            By.XPATH, "//input[@placeholder='Pesquisar']"
        )
        campo = next((p for p in pesquisar_inputs if p.is_displayed()), None)
        if not campo:
            combo.click()  # fecha
            return {"status": True, "observacoes": "Regular — campo de pesquisa não encontrado"}

        # Limpa o campo antes de digitar
        campo.clear()
        campo.send_keys(cnpj)
        time.sleep(3)

        opcoes = driver.find_elements(
            By.XPATH,
            "//*[@role='option' and not(contains(@aria-label,'Selecionar'))]",
        )
        cnpj_encontrado = any(
            op.text.strip() == cnpj for op in opcoes if op.text.strip()
        )

        if not cnpj_encontrado:
            combo.click()  # fecha slicer
            time.sleep(1)
            return {"status": True, "observacoes": "Regular — não inscrito no CFIL/RS"}

        # Seleciona o CNPJ encontrado para carregar os detalhes na tabela
        for op in opcoes:
            if op.text.strip() == cnpj:
                op.click()
                break
        time.sleep(1)
        combo.click()   # fecha slicer
        time.sleep(3)

        # Lê as células da tabela filtrada
        cells = driver.find_elements(
            By.XPATH, "//*[contains(@class,'pivotTableCellWrap')]"
        )
        valores = [c.text.strip() for c in cells if c.text.strip()]

        # Cabeçalhos conhecidos da tabela (posição fixa)
        HEADERS = [
            "CPF/CNPJ", "Fornecedor", "Órgão/Entidade", "Categoria Sanção",
            "Natureza Sanção", "Complemento", "Data Publicação DOE",
            "Data Inicial Suspensão", "Data Final Suspensão", "Data Início Inidoneidade",
        ]
        n = len(HEADERS)
        # Remove os cabeçalhos que vêm no início da lista de cells
        dados = valores[n:] if len(valores) > n else valores

        observacoes = self._formatar_cfil(dados, n)

        # Determina se o impedimento ainda está ativo
        status_ativo = self._cfil_ainda_ativo(dados, n)

        # Limpa o filtro para a próxima consulta
        self._limpar_filtro_cnpj(driver)

        return {
            "status": not status_ativo,
            "observacoes": observacoes,
        }

    def _cfil_ainda_ativo(self, dados: list, n: int) -> bool:
        """Verifica se existe pelo menos um registro CFIL com suspensão ainda vigente."""
        hoje = datetime.now().date()
        # dados é lista plana: registro1_col0, registro1_col1, …, registro2_col0, …
        # Índice 8 (base 0) = "Data Final Suspensão"  (9ª coluna, descontando cabeçalho)
        IDX_DATA_FIM = 8
        for i in range(0, len(dados), n):
            bloco = dados[i : i + n]
            if len(bloco) <= IDX_DATA_FIM:
                return True  # sem data de fim → assume ativo
            data_str = bloco[IDX_DATA_FIM].strip()
            if not data_str or data_str.lower() in ("-", "n/a", ""):
                return True
            try:
                dia, mes, ano = data_str.split("/")
                data_fim = datetime(int(ano), int(mes), int(dia)).date()
                if data_fim >= hoje:
                    return True
            except ValueError:
                return True
        return False

    def _formatar_cfil(self, dados: list, n: int) -> str:
        if not dados:
            return "Inscrito no CFIL/RS — sem detalhes disponíveis"
        HEADERS = [
            "CPF/CNPJ", "Fornecedor", "Órgão/Entidade", "Categoria",
            "Natureza", "Complemento", "Publicação DOE",
            "Início Suspensão", "Fim Suspensão", "Início Inidoneidade",
        ]
        linhas = []
        for i in range(0, len(dados), n):
            bloco = dados[i : i + n]
            partes = []
            for j, header in enumerate(HEADERS):
                val = bloco[j] if j < len(bloco) else "—"
                if val and val != "—":
                    partes.append(f"{header}: {val}")
            linhas.append(" | ".join(partes))
        return "\n".join(linhas)

    def _limpar_filtro_cnpj(self, driver):
        """Remove a seleção atual do slicer CPF/CNPJ."""
        from selenium.webdriver.common.by import By
        try:
            combo = driver.find_element(
                By.XPATH, "//*[@role='combobox' and @aria-label='CPF/CNPJ']"
            )
            combo.click()
            time.sleep(1)
            # Clica em "Selecionar tudo" para limpar a seleção
            selecionar_tudo = driver.find_element(
                By.XPATH, "//*[@role='option' and contains(@aria-label,'Selecionar')]"
            )
            selecionar_tudo.click()
            time.sleep(1)
            combo.click()
            time.sleep(1)
        except Exception as e:
            logger.debug(f"Erro ao limpar filtro CNPJ: {e}")

    # ------------------------------------------------------------------
    # CADIN — cadin.sefaz.rs.gov.br (sessão persistente Gov.Br)
    # ------------------------------------------------------------------

    def _consultar_cadin(self, cnpj: str) -> dict:
        from utils.cadin_session import consultar_cnpj
        return consultar_cnpj(cnpj)

    # ------------------------------------------------------------------
    # Banco de dados
    # ------------------------------------------------------------------

    def _garantir_empresa(self, cnpj: str) -> int:
        resp = (
            self.db.supabase.table("empresas")
            .select("id")
            .eq("cnpj", cnpj)
            .execute()
        )
        if resp.data:
            return resp.data[0]["id"]
        resp = (
            self.db.supabase.table("empresas")
            .insert({"cnpj": cnpj, "razao_social": "Empresa em Consulta", "objeto_contrato": "Consulta Individual"})
            .execute()
        )
        return resp.data[0]["id"]

    def _salvar_monitoramentos(self, empresa_id: int, resultado: dict):
        agora = datetime.now().isoformat()
        for sistema, dados in resultado.items():
            try:
                self.db.supabase.table("monitoramentos").insert({
                    "empresa_id": empresa_id,
                    "tipo_verificacao": sistema.upper(),
                    "status": dados["status"],
                    "observacoes": dados["observacoes"],
                    "data_verificacao": agora,
                }).execute()
            except Exception as e:
                logger.error(f"Erro ao salvar monitoramento {sistema}: {e}")
