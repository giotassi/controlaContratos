import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging
from typing import List

class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def enviar_relatorio(self, destinatarios: List[str], arquivo_relatorio: str, assunto: str = None):
        """Envia relatório por e-mail"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = ', '.join(destinatarios)
            msg['Subject'] = assunto or 'Relatório de Impedimentos'
            
            # Corpo do e-mail
            corpo = """
            Segue em anexo o relatório de impedimentos gerado automaticamente.
            
            Este é um e-mail automático, por favor não responda.
            """
            msg.attach(MIMEText(corpo, 'plain'))
            
            # Anexa o relatório
            with open(arquivo_relatorio, 'rb') as f:
                part = MIMEApplication(f.read(), Name=arquivo_relatorio)
                part['Content-Disposition'] = f'attachment; filename="{arquivo_relatorio}"'
                msg.attach(part)
            
            # Envia o e-mail
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            logging.error(f"Erro ao enviar e-mail: {str(e)}")
            return False 