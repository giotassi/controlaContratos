from fpdf import FPDF
from datetime import datetime
import logging

class RelatorioService:
    def __init__(self):
        self.pdf = FPDF()
        
    def gerar_relatorio_impedimentos(self, dados_relatorio):
        """Gera relatório PDF com os impedimentos encontrados"""
        try:
            self.pdf.add_page()
            
            # Cabeçalho
            self.pdf.set_font('Arial', 'B', 16)
            self.pdf.cell(0, 10, 'Relatório de Impedimentos', 0, 1, 'C')
            
            # Data da emissão do relatório
            self.pdf.set_font('Arial', '', 10)
            data = datetime.now()
            self.pdf.cell(0, 10, f'Data do Relatório: {data.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
            
            # Conteúdo
            self.pdf.set_font('Arial', 'B', 12)
            self.pdf.cell(0, 10, 'Empresas com Impedimentos:', 0, 1)
            
            # Agrupa impedimentos por CNPJ
            empresas = {}
            for item in dados_relatorio:
                cnpj = item['cnpj']
                if cnpj not in empresas:
                    empresas[cnpj] = {
                        'razao_social': item['razao_social'],
                        'impedimentos': []
                    }
                
                # Adiciona cada sistema de impedimento
                for sistema, info in item.items():
                    if sistema not in ['cnpj', 'razao_social'] and isinstance(info, dict):
                        empresas[cnpj]['impedimentos'].append({
                            'sistema': sistema,
                            'observacoes': info.get('observacoes', 'N/A')
                        })
            
            # Gera o relatório para cada empresa
            for cnpj, dados in empresas.items():
                self.pdf.set_font('Arial', 'B', 11)
                self.pdf.cell(0, 10, f'CNPJ: {cnpj}', 0, 1)
                self.pdf.cell(0, 10, f'Razão Social: {dados["razao_social"]}', 0, 1)
                
                self.pdf.set_font('Arial', '', 10)
                for imp in dados['impedimentos']:
                    self.pdf.multi_cell(0, 5, f'{imp["sistema"].upper()}: {imp["observacoes"]}')
                self.pdf.ln(5)
            
            # Salva o arquivo
            filename = f'relatorio_impedimentos_{data.strftime("%Y%m%d_%H%M%S")}.pdf'
            self.pdf.output(filename)
            return filename
            
        except Exception as e:
            logging.error(f"Erro ao gerar relatório: {str(e)}")
            return None 