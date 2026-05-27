import base64
import logging

import requests

logger = logging.getLogger(__name__)


class TCUAPFService:
    BASE_URL = "https://certidoes-apf.apps.tcu.gov.br/api/rest/publico"

    @staticmethod
    def tem_restricao(resultado: dict) -> bool:
        return any(
            str(certidao.get("situacao", "")).upper() != "NADA_CONSTA"
            for certidao in resultado.get("certidoes", [])
        )

    def consultar(self, cnpj: str, emitir_pdf: bool = False) -> dict:
        digits = "".join(c for c in str(cnpj) if c.isdigit())
        try:
            response = requests.get(
                f"{self.BASE_URL}/certidoes/{digits}",
                params={"seEmitirPDF": str(emitir_pdf).lower()},
                timeout=30 if emitir_pdf else 10,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("Erro ao consultar TCU APF para %s: %s", cnpj, e)
            return {"error": str(e)}

        result = {
            "cnpj": data.get("cnpj"),
            "razao_social": data.get("razaoSocial"),
            "nome_fantasia": data.get("nomeFantasia"),
            "certidoes": data.get("certidoes") or [],
            "pdf_bytes": None,
        }

        pdf_base64 = data.get("certidaoPDF")
        if emitir_pdf and pdf_base64:
            try:
                result["pdf_bytes"] = base64.b64decode(pdf_base64)
            except Exception as e:
                result["error"] = f"Consulta realizada, mas o PDF nao pode ser decodificado: {e}"

        return result
