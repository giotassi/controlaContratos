import logging
from datetime import datetime
from pathlib import Path

from fpdf import FPDF


class RelatorioService:
    def __init__(self):
        self.pdf = FPDF()

    def gerar_relatorio_impedimentos(self, dados_relatorio, filename: str | None = None):
        """Gera PDF apenas com empresas que tenham status False em algum sistema."""
        try:
            empresas = self._agrupar_impedimentos(dados_relatorio)
            if not empresas:
                return None

            data = datetime.now()
            self.pdf.add_page()
            self.pdf.set_font("Arial", "B", 16)
            self.pdf.cell(0, 10, "Relatorio de Impedimentos", 0, 1, "C")

            self.pdf.set_font("Arial", "", 10)
            self.pdf.cell(0, 10, f"Data do Relatorio: {data.strftime('%d/%m/%Y %H:%M')}", 0, 1, "R")

            self.pdf.set_font("Arial", "B", 12)
            self.pdf.cell(0, 10, "Empresas com impedimentos:", 0, 1)

            for cnpj, dados in empresas.items():
                self.pdf.set_font("Arial", "B", 11)
                self.pdf.cell(0, 8, f"CNPJ: {cnpj}", 0, 1)
                self.pdf.cell(0, 8, f"Razao Social: {dados['razao_social']}", 0, 1)

                self.pdf.set_font("Arial", "", 10)
                for imp in dados["impedimentos"]:
                    texto = f"{imp['sistema'].upper()}: {imp['observacoes']}"
                    self.pdf.multi_cell(0, 5, texto.encode("latin-1", "replace").decode("latin-1"))
                self.pdf.ln(4)

            if filename is None:
                filename = f"relatorio_impedimentos_{data.strftime('%Y%m%d_%H%M%S')}.pdf"
            self.pdf.output(filename)
            return filename
        except Exception as e:
            logging.error("Erro ao gerar relatorio: %s", e)
            return None

    def _agrupar_impedimentos(self, dados_relatorio):
        empresas = {}
        for item in dados_relatorio:
            cnpj = item["cnpj"]
            empresas.setdefault(cnpj, {
                "razao_social": item.get("razao_social", ""),
                "impedimentos": [],
            })

            for sistema, info in item.items():
                if sistema in ("cnpj", "razao_social") or not isinstance(info, dict):
                    continue
                if info.get("status") is False:
                    empresas[cnpj]["impedimentos"].append({
                        "sistema": sistema,
                        "observacoes": info.get("observacoes", "N/A"),
                    })

        return {
            cnpj: dados
            for cnpj, dados in empresas.items()
            if dados["impedimentos"]
        }

    def ler_relatorio(self, filename: str) -> bytes | None:
        try:
            return Path(filename).read_bytes()
        except Exception as e:
            logging.error("Erro ao ler relatorio %s: %s", filename, e)
            return None
